from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AuditEvent:
    request_id: str
    ts_ms: int
    tenant: str
    api_key_prefix: str
    path: str
    status_code: int
    latency_ms: int
    redactions: dict[str, int]
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_cost_usd: float
    request_redacted: dict[str, Any] | None = None
    request_raw: dict[str, Any] | None = None
    error: str | None = None


class AuditLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def new_request_id(self) -> str:
        return uuid.uuid4().hex

    def write(self, ev: AuditEvent) -> None:
        line = json.dumps(ev.__dict__, ensure_ascii=False)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def now_ms() -> int:
    return int(time.time() * 1000)
