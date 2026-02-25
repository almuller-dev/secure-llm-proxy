"""Environment-backed settings and per-key budget policy loading utilities."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class KeyPolicy:
    key: str
    tenant: str
    rpm: int
    burst: int
    max_requests_per_day: int
    max_tokens_per_day: int
    max_usd_per_day: float
    max_usd_per_month: float


@dataclass(frozen=True)
class Settings:
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = int(os.getenv("PORT", "8080"))

    data_dir: Path = Path(os.getenv("DATA_DIR", "data"))
    usage_db_path: Path = Path(os.getenv("USAGE_DB_PATH", "data/usage.sqlite"))
    audit_log_path: Path = Path(os.getenv("AUDIT_LOG_PATH", "data/audit.jsonl"))

    redact_emails_phones: bool = os.getenv("REDACT_EMAILS_PHONES", "0") == "1"
    store_raw_in_audit: bool = os.getenv("STORE_RAW_IN_AUDIT", "0") == "1"

    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    upstream_model_default: str = os.getenv("UPSTREAM_MODEL_DEFAULT", "gpt-4o-mini")
    upstream_timeout_s: float = float(os.getenv("UPSTREAM_TIMEOUT_S", "60"))

    price_per_1k_input_usd: float = float(os.getenv("PRICE_PER_1K_INPUT_USD", "0"))
    price_per_1k_output_usd: float = float(os.getenv("PRICE_PER_1K_OUTPUT_USD", "0"))

    max_request_bytes: int = int(os.getenv("MAX_REQUEST_BYTES", str(256 * 1024)))


def _default_keys_json() -> str:
    return json.dumps(
        [
            {
                "key": "demo-dev-key-change-me",
                "tenant": "demo",
                "rpm": 30,
                "burst": 10,
                "max_requests_per_day": 500,
                "max_tokens_per_day": 200_000,
                "max_usd_per_day": 0.0,
                "max_usd_per_month": 0.0,
            }
        ]
    )


def load_key_policies() -> dict[str, KeyPolicy]:
    raw = os.getenv("PROXY_KEYS_JSON", _default_keys_json())
    items = json.loads(raw)
    policies: dict[str, KeyPolicy] = {}
    for it in items:
        kp = KeyPolicy(
            key=str(it["key"]),
            tenant=str(it.get("tenant", "default")),
            rpm=int(it.get("rpm", 60)),
            burst=int(it.get("burst", 10)),
            max_requests_per_day=int(it.get("max_requests_per_day", 2000)),
            max_tokens_per_day=int(it.get("max_tokens_per_day", 500_000)),
            max_usd_per_day=float(it.get("max_usd_per_day", 0.0)),
            max_usd_per_month=float(it.get("max_usd_per_month", 0.0)),
        )
        policies[kp.key] = kp
    return policies
