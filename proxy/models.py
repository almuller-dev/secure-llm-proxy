"""Request and response schemas for proxy chat completion endpoints."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant", "tool"]


class ChatMessage(BaseModel):
    role: Role
    content: str = Field(default="")


class ChatCompletionsRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    temperature: float | None = None
    max_tokens: int | None = None
    metadata: dict[str, Any] | None = None


class ProxyMetadata(BaseModel):
    request_id: str
    tenant: str
    redactions: dict[str, int]
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_usd: float


class ChatCompletionsResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    model: str
    choices: list[dict[str, Any]]
    proxy_metadata: ProxyMetadata
