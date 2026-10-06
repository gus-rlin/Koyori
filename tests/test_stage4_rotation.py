"""Rotating local public identity and cursor secrets rejects prior capabilities."""

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from koyori.demo import token
from koyori.errors import Problem
from koyori.security import Cursors


def test_public_signing_key_rotation_refuses_previous_access_token(harness):
    h = harness
    previous = token(h.settings, "alex", mcp=True)
    assert h.tokens.verify(previous, resource=h.settings.mcp_resource)["sub"] == "alex"
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    from pathlib import Path

    Path(h.settings.key_dir, "jwt-public.pem").write_bytes(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    )
    with pytest.raises(Problem):
        h.tokens.verify(previous, resource=h.settings.mcp_resource)


def test_cursor_secret_rotation_does_not_change_domain_ids(harness):
    h = harness
    current = h.domain.cursors.encode(
        "alex", h.h, "personal-export", {"PK": "H#fixture", "SK": "META"}
    )
    rotated = Cursors(b"new-synthetic-secret-material-48-bytes" * 2, h.clock)
    with pytest.raises(Problem):
        rotated.decode(current, "alex", h.h, "personal-export")
    tid = h.command()
    assert h.domain.task_access(h.domain.context("alex", h.h), tid)[0]["id"] == tid
