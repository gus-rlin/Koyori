import time
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from koyori.config import Settings
from koyori.contracts import HouseholdCreate, MemberCreate
from koyori.control.app import create_app
from koyori.demo import initialize_keys, token
from koyori.domain import Domain
from koyori.security import Cursors, Tokens, request_hash
from koyori.store import MemoryStore
from koyori.workers.engine import Engine


class Clock:
    def __init__(self):
        self.value = int(time.time())

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class Harness:
    def __init__(self, settings, store, clock):
        self.settings, self.clock = settings, clock
        self.domain = Domain(store, settings, Cursors(settings.cursor_secret(), clock), clock)
        self.engine = Engine(self.domain)
        self.tokens = Tokens(settings, clock)
        self.client = TestClient(create_app(domain=self.domain, tokens=self.tokens))
        self.h = self.domain.create_household(
            "alex", HouseholdCreate(name="Synthetic A").model_dump(), uuid4().hex
        )["id"]
        self.h2 = self.domain.create_household(
            "robin", HouseholdCreate(name="Synthetic B").model_dump(), uuid4().hex
        )["id"]
        for principal, kind in (("sam", "personal"), ("speaker", "shared")):
            ctx = self.domain.context("alex", self.h)
            _, writes, _ = self.domain.add_member(
                ctx, MemberCreate(principalId=principal, kind=kind).model_dump()
            )
            store.transact(ctx.guards() + writes)

    def headers(self, actor="alex", h=None, version=None, key=None, grant=None):
        result = {
            "Authorization": f"Bearer {token(self.settings, actor)}",
            "X-Household-Id": h or self.h,
            "Idempotency-Key": key or uuid4().hex,
        }
        if version is not None:
            result["If-Match"] = f'"{version}"'
        if grant is not None:
            result["X-Step-Up-Grant"] = grant
        return result

    def grant(self, operation, body, *, actor="alex", version=None):
        headers = self.headers(actor)
        response = self.client.post(
            "/v1/auth/step-up",
            json={"operation": operation, "requestHash": request_hash(body, version)},
            headers=headers,
        )
        assert response.status_code == 201, response.text
        challenge = response.json()
        proof = token(self.settings, actor, nonce=challenge["nonce"])
        response = self.client.post(
            f"/v1/auth/step-up/{challenge['id']}/complete",
            json={"identityProof": proof},
            headers=self.headers(actor),
        )
        assert response.status_code == 200, response.text
        return response.json()["grant"]

    def command(self, actor="alex", visibility="private", key=None):
        body = {
            "schemaVersion": "1.0",
            "operation": "synthetic.checkpoint",
            "label": "Synthetic checkpoint",
            "visibility": visibility,
        }
        grant = (
            self.grant("POST /v1/commands", body, actor=actor)
            if visibility == "household"
            else None
        )
        response = self.client.post(
            "/v1/commands", json=body, headers=self.headers(actor, key=key, grant=grant)
        )
        assert response.status_code == 202, response.text
        return response.json()["taskId"]

    def task(self, tid, actor="alex"):
        response = self.client.get(f"/v1/tasks/{tid}", headers=self.headers(actor))
        assert response.status_code == 200, response.text
        return response.json()

    def start(self, tid):
        for event in self.engine.pending("OUTBOX"):
            if event["envelope"]["aggregateId"] == tid and event["envelope"]["wake"]:
                self.engine.consume(event["envelope"])
        return self.engine.acquire(self.h, tid)


@pytest.fixture
def harness(tmp_path, monkeypatch):
    monkeypatch.setenv("KOYORI_ISSUER_DIR", str(tmp_path / "issuer"))
    settings = replace(Settings(), key_dir=str(tmp_path / "keys"))
    initialize_keys(settings)
    return Harness(settings, MemoryStore(), Clock())
