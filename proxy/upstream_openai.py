"""OpenAI upstream client wrapper used by the proxy service layer."""

from __future__ import annotations

import os
from dataclasses import dataclass

from openai import OpenAI


@dataclass
class OpenAIUpstream:
    api_key: str
    timeout_s: float = 60.0

    def __post_init__(self) -> None:
        self.client = OpenAI(api_key=self.api_key, timeout=self.timeout_s)

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        temperature: float | None,
        max_tokens: int | None,
    ) -> str:
        resp = self.client.responses.create(
            model=model,
            input=prompt,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        return (resp.output_text or "").strip()


def ping() -> None:
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    u = OpenAIUpstream(api_key=key, timeout_s=30)
    out = u.generate(
        model=os.getenv("UPSTREAM_MODEL_DEFAULT", "gpt-4o-mini"),
        prompt="Say 'pong'.",
        temperature=0,
        max_tokens=10,
    )
    if "pong" not in out.lower():
        raise RuntimeError(f"Unexpected response: {out}")
