import json

from proxy.audit import AuditEvent, AuditLogger, prompt_fingerprint


def _event(*, request_id: str, ts_ms: int) -> AuditEvent:
    return AuditEvent(
        request_id=request_id,
        ts_ms=ts_ms,
        tenant="demo",
        api_key_prefix="demo-k",
        path="/v1/chat.completions",
        status_code=200,
        latency_ms=42,
        redactions={"openai_key": 1},
        estimated_input_tokens=10,
        estimated_output_tokens=20,
        estimated_cost_usd=0.0,
        prompt_fingerprint_sha256=prompt_fingerprint("hello"),
        request_redacted={"prompt": "USER: [REDACTED]"},
    )


def test_prompt_fingerprint_is_stable() -> None:
    a = prompt_fingerprint("same prompt")
    b = prompt_fingerprint("same prompt")
    c = prompt_fingerprint("different prompt")
    assert a == b
    assert a != c
    assert len(a) == 64


def test_audit_logger_rotates_daily_by_event_timestamp(tmp_path) -> None:
    logger = AuditLogger(tmp_path / "audit.jsonl")

    logger.write(_event(request_id="r1", ts_ms=1735689600000))  # 2025-01-01T00:00:00Z
    logger.write(_event(request_id="r2", ts_ms=1735776000000))  # 2025-01-02T00:00:00Z

    p1 = tmp_path / "audit-2025-01-01.jsonl"
    p2 = tmp_path / "audit-2025-01-02.jsonl"

    assert p1.exists()
    assert p2.exists()

    line1 = p1.read_text(encoding="utf-8").strip()
    line2 = p2.read_text(encoding="utf-8").strip()

    assert json.loads(line1)["request_id"] == "r1"
    assert json.loads(line2)["request_id"] == "r2"
