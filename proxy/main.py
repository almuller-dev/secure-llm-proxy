"""FastAPI application wiring for secure, budgeted, auditable LLM proxying."""

from __future__ import annotations

import math
import time
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from .audit import AuditEvent, AuditLogger, now_ms, prompt_fingerprint
from .auth import AuthContext, require_proxy_key
from .config import Settings, load_key_policies
from .limits import RateLimiter, UsageStore, enforce_budgets, record_usage
from .models import ChatCompletionsRequest, ChatCompletionsResponse, ProxyMetadata
from .redaction import redact_text
from .upstream_openai import OpenAIUpstream


def estimate_tokens(text: str) -> int:
    """Estimate token count using a stable character-to-token heuristic."""
    return max(1, math.ceil(len(text) / 4))


def build_prompt(messages) -> str:
    """Serialize chat messages into a deterministic upstream prompt string."""
    parts: list[str] = []
    for m in messages:
        parts.append(f"{m.role.upper()}: {m.content}")
    return "\n".join(parts).strip() + "\nASSISTANT:"


def estimate_cost_usd(settings: Settings, *, input_tokens: int, output_tokens: int) -> float:
    """Estimate request cost from configured per-1k token pricing."""
    if settings.price_per_1k_input_usd <= 0 and settings.price_per_1k_output_usd <= 0:
        return 0.0
    return (input_tokens / 1000.0) * max(0.0, settings.price_per_1k_input_usd) + (
        output_tokens / 1000.0
    ) * max(0.0, settings.price_per_1k_output_usd)


settings = Settings()
policies = load_key_policies()
rate_limiter = RateLimiter()
usage_store = UsageStore(settings.usage_db_path)
audit = AuditLogger(settings.audit_log_path)

app = FastAPI(title="Secure LLM Proxy", version="0.1.0")


def get_auth_context(
    x_proxy_key: str | None = Header(default=None, alias="X-Proxy-Key"),
) -> AuthContext:
    """Resolve and validate proxy auth context from request headers."""
    return require_proxy_key(policies, x_proxy_key)


@app.get("/health")
def health() -> dict[str, str]:
    """Return a lightweight readiness signal for probes and monitors."""
    return {"status": "ok"}


@app.get("/v1/usage")
def usage(
    ctx: Annotated[AuthContext, Depends(get_auth_context)],
) -> dict[str, dict[str, int | float | str]]:
    """Return current day/month usage snapshot for the authenticated key."""
    return usage_store.snapshot(api_key=ctx.key_policy.key)


@app.post("/v1/keys/verify")
def verify_key(ctx: Annotated[AuthContext, Depends(get_auth_context)]) -> dict[str, bool | str]:
    """Validate the presented proxy key and return tenant metadata."""
    return {"ok": True, "tenant": ctx.key_policy.tenant}


@app.post("/v1/chat.completions")
async def chat_completions(
    req: Request,
    body: ChatCompletionsRequest,
    ctx: Annotated[AuthContext, Depends(get_auth_context)],
):
    """Handle proxy chat requests with policy checks, auditing, and upstream routing."""
    t0 = time.time()
    request_id = audit.new_request_id()

    raw_bytes = await req.body()
    if len(raw_bytes) > settings.max_request_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Request too large",
        )

    rate_limiter.check(
        key=ctx.key_policy.key,
        rpm=ctx.key_policy.rpm,
        burst=ctx.key_policy.burst,
    )

    prompt_raw = build_prompt(body.messages)
    red = redact_text(prompt_raw, redact_emails_phones=settings.redact_emails_phones)
    prompt_redacted = red.text
    prompt_fp = prompt_fingerprint(prompt_redacted)

    est_in_tokens = estimate_tokens(prompt_redacted)
    est_out_tokens = int(body.max_tokens or 256)
    est_cost = estimate_cost_usd(
        settings,
        input_tokens=est_in_tokens,
        output_tokens=est_out_tokens,
    )

    enforce_budgets(
        usage_store,
        policy=ctx.key_policy,
        api_key=ctx.key_policy.key,
        add_requests=1,
        add_tokens=est_in_tokens + est_out_tokens,
        add_usd=est_cost,
    )

    if not settings.openai_api_key:
        raise HTTPException(status_code=500, detail="Upstream OPENAI_API_KEY not configured")

    upstream_model = body.model or settings.upstream_model_default
    upstream = OpenAIUpstream(
        api_key=settings.openai_api_key,
        timeout_s=settings.upstream_timeout_s,
    )

    status_code = 200
    err: str | None = None
    try:
        out_text = upstream.generate(
            model=upstream_model,
            prompt=prompt_redacted,
            temperature=body.temperature,
            max_tokens=body.max_tokens,
        )
    except Exception as e:
        status_code = 502
        err = f"upstream_error: {type(e).__name__}: {e}"
        out_text = ""

    record_usage(
        usage_store,
        api_key=ctx.key_policy.key,
        tenant=ctx.key_policy.tenant,
        requests=1,
        tokens=est_in_tokens + est_out_tokens,
        usd=est_cost,
    )

    latency_ms = int((time.time() - t0) * 1000)

    audit.write(
        AuditEvent(
            request_id=request_id,
            ts_ms=now_ms(),
            tenant=ctx.key_policy.tenant,
            api_key_prefix=ctx.key_policy.key[:6],
            path=str(req.url.path),
            status_code=status_code,
            latency_ms=latency_ms,
            redactions=red.counts,
            estimated_input_tokens=est_in_tokens,
            estimated_output_tokens=est_out_tokens,
            estimated_cost_usd=est_cost,
            prompt_fingerprint_sha256=prompt_fp,
            request_redacted={"model": upstream_model, "prompt": prompt_redacted}
            if not settings.store_raw_in_audit
            else None,
            request_raw={"model": upstream_model, "prompt": prompt_raw}
            if settings.store_raw_in_audit
            else None,
            error=err,
        )
    )

    if status_code != 200:
        return JSONResponse(
            status_code=status_code,
            content={"error": err or "Upstream error", "request_id": request_id},
        )

    return ChatCompletionsResponse(
        id=request_id,
        model=upstream_model,
        choices=[
            {
                "index": 0,
                "message": {"role": "assistant", "content": out_text},
                "finish_reason": "stop",
            }
        ],
        proxy_metadata=ProxyMetadata(
            request_id=request_id,
            tenant=ctx.key_policy.tenant,
            redactions=red.counts,
            estimated_input_tokens=est_in_tokens,
            estimated_output_tokens=est_out_tokens,
            estimated_cost_usd=est_cost,
        ),
    )
