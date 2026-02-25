from pathlib import Path

import pytest
from fastapi import HTTPException

from proxy.auth import require_proxy_key
from proxy.config import KeyPolicy
from proxy.limits import RateLimiter, UsageStore, enforce_budgets, record_usage


def _policy() -> KeyPolicy:
    return KeyPolicy(
        key="demo-key",
        tenant="demo",
        rpm=30,
        burst=2,
        max_requests_per_day=3,
        max_tokens_per_day=100,
        max_usd_per_day=0.0,
        max_usd_per_month=0.0,
    )


def test_missing_proxy_key_denied() -> None:
    with pytest.raises(HTTPException) as exc:
        require_proxy_key({"demo-key": _policy()}, None)
    assert exc.value.status_code == 401


def test_invalid_proxy_key_denied() -> None:
    with pytest.raises(HTTPException) as exc:
        require_proxy_key({"demo-key": _policy()}, "wrong")
    assert exc.value.status_code == 403


def test_rate_limiter_blocks_after_burst() -> None:
    limiter = RateLimiter()
    limiter.check(key="demo", rpm=1, burst=1)
    with pytest.raises(HTTPException) as exc:
        limiter.check(key="demo", rpm=1, burst=1)
    assert exc.value.status_code == 429


def test_budget_enforcement_and_recording(tmp_path: Path) -> None:
    store = UsageStore(tmp_path / "usage.sqlite")
    pol = _policy()

    enforce_budgets(
        store,
        policy=pol,
        api_key=pol.key,
        add_requests=1,
        add_tokens=10,
        add_usd=0.0,
    )
    record_usage(store, api_key=pol.key, tenant=pol.tenant, requests=1, tokens=10, usd=0.0)

    snap = store.snapshot(api_key=pol.key)
    assert int(snap["day"]["requests"]) == 1
    assert int(snap["day"]["tokens"]) == 10
