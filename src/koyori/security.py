"""Token validation, exact-request step-up binding, and scoped pagination cursors."""

import base64
import hashlib
import json
import re
import secrets
import time
from pathlib import Path

import jwt
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from koyori.config import Settings
from koyori.errors import Problem


def digest(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def request_hash(body: dict, version: int | None) -> str:
    """Bind the normalized write body and its exact revision precondition."""
    return digest({"body": body, "version": version})


def idempotency_key(value: str | None) -> str:
    if not value or not re.fullmatch(
        r"[a-fA-F0-9]{32}|[a-fA-F0-9]{8}(?:-[a-fA-F0-9]{4}){3}-[a-fA-F0-9]{12}", value
    ):
        raise Problem(
            400,
            "IDEMPOTENCY_REQUIRED",
            "Use a random UUID or 32 hexadecimal characters as Idempotency-Key.",
        )
    return value.lower()


def expected_version(value: str | None) -> int:
    if value is None:
        raise Problem(428, "PRECONDITION_REQUIRED", "If-Match is required.")
    if not re.fullmatch(r'"[1-9][0-9]{0,12}"', value):
        raise Problem(400, "INVALID_ETAG", "If-Match must contain one quoted resource revision.")
    return int(value[1:-1])


class Tokens:
    def __init__(self, settings: Settings, clock=time.time):
        self.settings, self.clock = settings, clock
        self.jwks = (
            jwt.PyJWKClient(f"{settings.issuer}/.well-known/jwks.json", timeout=3)
            if settings.env != "local"
            else None
        )

    def verify(self, token: str, *, identity: bool = False) -> dict:
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") != "RS256":
                raise jwt.InvalidTokenError
            key = (
                self.jwks.get_signing_key_from_jwt(token).key
                if self.jwks
                else Path(self.settings.key_dir, "jwt-public.pem").read_bytes()
            )
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                issuer=self.settings.issuer,
                audience=self.settings.client_id if identity else None,
                options={
                    "verify_aud": identity,
                    "require": ["exp", "iat", "sub", "token_use", "iss", "auth_time"],
                },
            )
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", claims["sub"]):
                raise jwt.InvalidTokenError
            if claims["token_use"] != ("id" if identity else "access"):
                raise jwt.InvalidTokenError
            if not identity:
                if not isinstance(claims.get("scope"), str):
                    raise jwt.InvalidTokenError
                if (
                    claims.get("client_id") != self.settings.client_id
                    or "koyori/control" not in claims.get("scope", "").split()
                ):
                    raise jwt.InvalidTokenError
                # Cognito access-token audience is optional unless resource binding is used.
                if "aud" in claims and claims["aud"] != self.settings.audience:
                    raise jwt.InvalidTokenError
            for field in ("iat", "exp", "auth_time"):
                if type(claims[field]) is not int:
                    raise jwt.InvalidTokenError
            return claims
        except (jwt.PyJWTError, OSError, ValueError, TypeError, KeyError):
            raise Problem(
                401,
                "INVALID_IDENTITY_PROOF" if identity else "INVALID_TOKEN",
                "Authentication is missing, invalid or expired.",
            ) from None

    def bearer(self, authorization: str | None) -> str:
        if (
            not authorization
            or not authorization.startswith("Bearer ")
            or len(authorization) > 8192
        ):
            raise Problem(401, "INVALID_TOKEN", "Bearer authentication is required.")
        return self.verify(authorization[7:])["sub"]


class Cursors:
    """Opaque cursors bind the principal, household, endpoint and expiration."""

    def __init__(self, secret: bytes, clock=time.time):
        if len(secret) < 32:
            raise ValueError("Cursor key too short")
        self.cipher, self.clock = AESGCM(hashlib.sha256(secret).digest()), clock

    def encode(self, actor: str, household: str, route: str, key: dict) -> str:
        raw = json.dumps(
            {"p": actor, "h": household, "r": route, "k": key, "exp": int(self.clock()) + 3600},
            separators=(",", ":"),
            sort_keys=True,
        ).encode()
        # Discovery pages can end on a currently private object's key. Authentication
        # alone would expose that key inside a readable base64 cursor; encrypt it too.
        nonce = secrets.token_bytes(12)
        return (
            base64.urlsafe_b64encode(nonce + self.cipher.encrypt(nonce, raw, b"koyori.cursor.v1"))
            .decode()
            .rstrip("=")
        )

    def decode(self, value: str | None, actor: str, household: str, route: str) -> dict | None:
        if value is None:
            return None
        try:
            if len(value) > 2048:
                raise ValueError
            decoded = base64.b64decode(
                value + "=" * (-len(value) % 4), altchars=b"-_", validate=True
            )
            raw = self.cipher.decrypt(decoded[:12], decoded[12:], b"koyori.cursor.v1")
            data = json.loads(raw)
            if (data["p"], data["h"], data["r"]) != (actor, household, route) or data[
                "exp"
            ] <= self.clock():
                raise ValueError
            if not isinstance(data["k"], dict):
                raise ValueError
            return data["k"]
        except (ValueError, KeyError, TypeError, InvalidTag):
            raise Problem(
                400, "INVALID_CURSOR", "Pagination cursor is invalid or expired."
            ) from None
