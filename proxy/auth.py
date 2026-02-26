"""
#########################################
##      created by: Al Muller
##       filename: proxy/auth.py
#########################################
"""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, status

from .config import KeyPolicy


@dataclass(frozen=True)
class AuthContext:
    key_policy: KeyPolicy


def require_proxy_key(
    policies: dict[str, KeyPolicy],
    x_proxy_key: str | None,
) -> AuthContext:
    if not x_proxy_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-Proxy-Key")

    pol = policies.get(x_proxy_key)
    if not pol:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid proxy key")

    return AuthContext(key_policy=pol)
