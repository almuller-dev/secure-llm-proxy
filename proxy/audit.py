"""Audit event models and log writers with daily rotation and prompt fingerprints."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
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
    prompt_fingerprint_sha256: str | None = None
    request_redacted: dict[str, Any] | None = None
    request_raw: dict[str, Any] | None = None
    error: str | None = None


class AuditLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def new_request_id(self) -> str:
        return uuid.uuid4().hex

    def _path_for_event(self, *, ts_ms: int) -> Path:
        day = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
        return self.path.with_name(f"{self.path.stem}-{day}{self.path.suffix}")

    def write(self, ev: AuditEvent) -> None:
        line = json.dumps(ev.__dict__, ensure_ascii=False)
        out_path = self._path_for_event(ts_ms=ev.ts_ms)
        with out_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def now_ms() -> int:
    return int(time.time() * 1000)


def prompt_fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
