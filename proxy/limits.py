"""Rate-limiting and usage accounting helpers backed by SQLite."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, status

from .config import KeyPolicy


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def day_key(dt: datetime | None = None) -> str:
    d = dt or utc_now()
    return d.strftime("%Y-%m-%d")


def month_key(dt: datetime | None = None) -> str:
    d = dt or utc_now()
    return d.strftime("%Y-%m")


@dataclass
class TokenBucket:
    capacity: float
    refill_per_sec: float
    tokens: float
    last_ts: float

    def take(self, amount: float = 1.0) -> bool:
        now = time.time()
        elapsed = max(0.0, now - self.last_ts)
        self.last_ts = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_per_sec)
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False


class RateLimiter:
    def __init__(self) -> None:
        self._buckets: dict[str, TokenBucket] = {}

    def check(self, *, key: str, rpm: int, burst: int) -> None:
        if rpm <= 0:
            return
        b = self._buckets.get(key)
        if not b:
            b = TokenBucket(
                capacity=float(burst),
                refill_per_sec=float(rpm) / 60.0,
                tokens=float(burst),
                last_ts=time.time(),
            )
            self._buckets[key] = b
        if not b.take(1.0):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded"
            )


class UsageStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.db_path))
        c.execute("PRAGMA journal_mode=WAL;")
        return c

    def _init_db(self) -> None:
        with self._conn() as c:
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS usage (
                  scope TEXT NOT NULL,
                  scope_key TEXT NOT NULL,
                  api_key TEXT NOT NULL,
                  tenant TEXT NOT NULL,
                  requests INTEGER NOT NULL,
                  tokens INTEGER NOT NULL,
                  usd REAL NOT NULL,
                  PRIMARY KEY (scope, scope_key, api_key)
                )
                """
            )

    def get(self, *, scope: str, scope_key: str, api_key: str) -> tuple[int, int, float]:
        with self._conn() as c:
            row = c.execute(
                "SELECT requests, tokens, usd FROM usage "
                "WHERE scope=? AND scope_key=? AND api_key=?",
                (scope, scope_key, api_key),
            ).fetchone()
        if not row:
            return (0, 0, 0.0)
        return (int(row[0]), int(row[1]), float(row[2]))

    def add(
        self,
        *,
        scope: str,
        scope_key: str,
        api_key: str,
        tenant: str,
        req: int,
        tok: int,
        usd: float,
    ) -> None:
        with self._conn() as c:
            cur = c.execute(
                "SELECT requests, tokens, usd FROM usage "
                "WHERE scope=? AND scope_key=? AND api_key=?",
                (scope, scope_key, api_key),
            ).fetchone()
            if not cur:
                c.execute(
                    "INSERT INTO usage(scope, scope_key, api_key, tenant, requests, tokens, usd) "
                    "VALUES(?,?,?,?,?,?,?)",
                    (scope, scope_key, api_key, tenant, req, tok, usd),
                )
            else:
                c.execute(
                    "UPDATE usage SET requests=?, tokens=?, usd=? "
                    "WHERE scope=? AND scope_key=? AND api_key=?",
                    (
                        int(cur[0]) + req,
                        int(cur[1]) + tok,
                        float(cur[2]) + usd,
                        scope,
                        scope_key,
                        api_key,
                    ),
                )

    def snapshot(self, *, api_key: str) -> dict[str, dict[str, int | float | str]]:
        dk = day_key()
        mk = month_key()
        d = self.get(scope="day", scope_key=dk, api_key=api_key)
        m = self.get(scope="month", scope_key=mk, api_key=api_key)
        return {
            "day": {"key": dk, "requests": d[0], "tokens": d[1], "usd": d[2]},
            "month": {"key": mk, "requests": m[0], "tokens": m[1], "usd": m[2]},
        }


def enforce_budgets(
    store: UsageStore,
    *,
    policy: KeyPolicy,
    api_key: str,
    add_requests: int,
    add_tokens: int,
    add_usd: float,
) -> None:
    dk = day_key()
    mk = month_key()

    d_req, d_tok, d_usd = store.get(scope="day", scope_key=dk, api_key=api_key)
    _, _, m_usd = store.get(scope="month", scope_key=mk, api_key=api_key)

    if d_req + add_requests > policy.max_requests_per_day:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Daily request cap exceeded"
        )

    if d_tok + add_tokens > policy.max_tokens_per_day:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Daily token cap exceeded"
        )

    if policy.max_usd_per_day > 0 and (d_usd + add_usd) > policy.max_usd_per_day:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Daily spend cap exceeded"
        )

    if policy.max_usd_per_month > 0 and (m_usd + add_usd) > policy.max_usd_per_month:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Monthly spend cap exceeded"
        )


def record_usage(
    store: UsageStore,
    *,
    api_key: str,
    tenant: str,
    requests: int,
    tokens: int,
    usd: float,
) -> None:
    dk = day_key()
    mk = month_key()
    store.add(
        scope="day", scope_key=dk, api_key=api_key, tenant=tenant, req=requests, tok=tokens, usd=usd
    )
    store.add(
        scope="month",
        scope_key=mk,
        api_key=api_key,
        tenant=tenant,
        req=requests,
        tok=tokens,
        usd=usd,
    )
