"""Verify Cognito ID tokens before using their identity claims."""

from __future__ import annotations

import json
import time
from urllib.request import urlopen

from jose import JWTError, jwt

from app.core.config import settings

_keys: dict[str, dict] = {}
_keys_expires_at = 0.0


def _issuer() -> str:
    pool = settings.cognito_user_pool_id
    if not pool or not settings.cognito_client_id or not pool.startswith(f"{settings.aws_region}_"):
        raise RuntimeError("Cognito user pool and client ID must be configured")
    return f"https://cognito-idp.{settings.aws_region}.amazonaws.com/{pool}"


def _refresh_keys(issuer: str) -> None:
    global _keys, _keys_expires_at
    with urlopen(f"{issuer}/.well-known/jwks.json", timeout=5) as response:
        keys = json.load(response)["keys"]
    _keys = {key["kid"]: key for key in keys if key.get("kty") == "RSA"}
    _keys_expires_at = time.monotonic() + 3600


def verify_id_token(token: str) -> dict:
    """Check signature, expiry, issuer, audience and type; refresh rotated keys."""
    issuer = _issuer()
    header = jwt.get_unverified_header(token)
    if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
        raise JWTError("Unsupported token signing key")
    if time.monotonic() >= _keys_expires_at or header["kid"] not in _keys:
        _refresh_keys(issuer)
    key = _keys.get(header["kid"])
    if key is None:
        raise JWTError("Unknown token signing key")
    claims = jwt.decode(
        token, key, algorithms=["RS256"], audience=settings.cognito_client_id,
        issuer=issuer, options={"require_exp": True, "require_sub": True,
                                "require_aud": True, "require_iat": True})
    if claims.get("token_use") != "id" or not isinstance(claims.get("sub"), str):
        raise JWTError("Expected a Cognito ID token")
    return claims
