import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from uuid import uuid4

import jwt
import pytest

from koyori.contracts import Command, MemberCreate
from koyori.demo import issuer_dir, token
from koyori.domain import hkey
from koyori.errors import Problem
from koyori.store import Conflict, put, revised


def test_acceptance_idempotence_conflicts_and_revision(harness):
    h = harness
    key = uuid4().hex
    body = Command(operation="synthetic.checkpoint", label="Synthetic").model_dump()
    first = h.client.post("/v1/commands", json=body, headers=h.headers(key=key))
    second = h.client.post("/v1/commands", json=body, headers=h.headers(key=key))
    assert first.status_code == second.status_code == 202
    assert first.json() == second.json()
    tid = first.json()["taskId"]
    assert h.task(tid)["status"] == "READY"
    assert h.domain.store.get("Delivery", h.engine.run_key(tid))["status"] == "PENDING"
    assert h.domain.context("alex", h.h).household["activeTasks"] == 1
    assert (
        h.client.post(
            "/v1/commands", json={**body, "label": "different"}, headers=h.headers(key=key)
        ).status_code
        == 409
    )
    stale = h.client.post(f"/v1/tasks/{tid}/pause", headers=h.headers(version=2))
    assert stale.status_code == 412
    assert h.client.post(f"/v1/tasks/{tid}/pause", headers=h.headers()).status_code == 428
    assert h.client.post(f"/v1/tasks/{tid}/pause", headers=h.headers(version=1)).status_code == 202
    assert h.task(tid)["status"] == "PAUSED"


def test_explicit_iana_zone_is_accepted_on_windows_and_unknown_zone_rejected(harness):
    accepted = harness.client.post(
        "/v1/households",
        json={"name": "Synthetic timezone fixture", "timeZone": "Europe/Paris"},
        headers=harness.headers(),
    )
    assert accepted.status_code == 201 and accepted.json()["timeZone"] == "Europe/Paris"
    refused = harness.client.post(
        "/v1/households",
        json={"name": "Synthetic timezone fixture", "timeZone": "Mars/Olympus"},
        headers=harness.headers(),
    )
    assert refused.status_code == 422


def test_private_data_isolation_including_administrator(harness):
    h = harness
    alex, sam = h.command(), h.command("sam")
    assert h.client.get(f"/v1/tasks/{alex}", headers=h.headers("sam")).status_code == 404
    assert h.client.get(f"/v1/tasks/{sam}", headers=h.headers()).status_code == 404
    assert h.client.get(f"/v1/tasks/{alex}", headers=h.headers("robin", h.h2)).status_code == 404
    assert h.client.get(f"/v1/tasks/{alex}", headers=h.headers("robin", h.h)).status_code == 403
    listed = h.client.get("/v1/tasks", headers=h.headers("sam")).json()["items"]
    assert [t["id"] for t in listed] == [sam]


def test_unknown_fields_and_provider_mode_are_rejected(harness):
    body = {"operation": "synthetic.checkpoint", "label": "demo", "owner": "robin", "mode": "live"}
    response = harness.client.post("/v1/commands", json=body, headers=harness.headers())
    assert response.status_code == 422
    assert "robin" not in response.text
    assert (
        harness.client.post(
            "/v1/commands",
            json={"operation": "purchase", "label": "demo"},
            headers=harness.headers(),
        ).status_code
        == 422
    )
    assert (
        harness.client.post(
            "/v1/commands",
            json={"operation": "synthetic.checkpoint", "label": "demo"},
            headers={**harness.headers(), "Idempotency-Key": "predictable"},
        ).status_code
        == 400
    )


@pytest.mark.parametrize(
    "alteration",
    ["issuer", "client", "scope", "malformed-scope", "expired", "id", "audience", "algorithm"],
)
def test_invalid_token_boundaries(harness, alteration):
    h = harness
    now = h.clock()
    claims = dict(
        iss=h.settings.issuer,
        sub="alex",
        iat=now,
        auth_time=now,
        exp=now + 600,
        token_use="access",
        client_id=h.settings.client_id,
        scope="koyori/control",
        aud=h.settings.audience,
    )
    if alteration == "issuer":
        claims["iss"] = "https://untrusted.invalid"
    elif alteration == "client":
        claims["client_id"] = "another-client"
    elif alteration == "scope":
        claims["scope"] = "openid"
    elif alteration == "malformed-scope":
        claims["scope"] = ["koyori/control"]
    elif alteration == "expired":
        claims["exp"] = now - 1
    elif alteration == "id":
        claims["token_use"] = "id"
    elif alteration == "audience":
        claims["aud"] = "another-api"
    encoded = (
        jwt.encode(claims, b"fake-symmetric-key-for-negative-test-32bytes", algorithm="HS256")
        if alteration == "algorithm"
        else jwt.encode(
            claims, (issuer_dir(h.settings) / "jwt-private.pem").read_bytes(), algorithm="RS256"
        )
    )
    response = h.client.get(
        "/v1/tasks", headers={**h.headers(), "Authorization": f"Bearer {encoded}"}
    )
    assert response.status_code == 401
    assert encoded not in response.text


def test_shared_device_uses_server_kind_and_shared_resources_only(harness):
    h = harness
    private, shared = h.command(), h.command(visibility="household")
    assert h.client.get(f"/v1/tasks/{private}", headers=h.headers("speaker")).status_code == 404
    assert h.client.get(f"/v1/tasks/{shared}", headers=h.headers("speaker")).status_code == 200
    assert (
        h.client.post(
            "/v1/commands",
            json={"operation": "synthetic.checkpoint", "label": "demo"},
            headers=h.headers("speaker"),
        ).status_code
        == 403
    )
    assert (
        h.client.post(
            f"/v1/tasks/{shared}/pause", headers=h.headers("speaker", version=1)
        ).status_code
        == 404
    )
    assert (
        h.client.post(
            "/v1/households", json={"name": "demo"}, headers=h.headers("speaker")
        ).status_code
        == 403
    )
    assert (
        h.client.get(f"/v1/households/{h.h}/members", headers=h.headers("speaker")).status_code
        == 403
    )


def test_step_up_binding_consumption_and_idempotent_replay(harness):
    h = harness
    path = f"/v1/households/{h.h}/members"
    body = MemberCreate(principalId="new-member").model_dump()
    assert h.client.post(path, json=body, headers=h.headers()).status_code == 403
    grant = h.grant(f"POST {path}", body)
    assert (
        h.client.post(
            path, json={**body, "principalId": "wrong-member"}, headers=h.headers(grant=grant)
        ).status_code
        == 403
    )
    key = uuid4().hex
    headers = h.headers(grant=grant, key=key)
    result = h.client.post(path, json=body, headers=headers)
    assert result.status_code == 201, result.text
    # A committed repeat is authorized now, but does not consume the grant again.
    replay = h.client.post(path, json=body, headers=h.headers(key=key))
    assert replay.status_code == 201 and replay.json() == result.json()
    assert (
        h.client.post(
            path, json={**body, "principalId": "another"}, headers=h.headers(grant=grant)
        ).status_code
        == 403
    )


def test_member_expiry_reduction_needs_no_grant_but_expansion_does(harness):
    h = harness
    path = f"/v1/households/{h.h}/members/sam"
    bounded = h.clock() + 120
    for expiry, revision in ((bounded, 1), (bounded - 30, 2)):
        result = h.client.patch(
            path, json={"expiresAt": expiry}, headers=h.headers(version=revision)
        )
        assert result.status_code == 200, result.text
    for expiry in (bounded + 60, None):
        body = {"expiresAt": expiry}
        rejected = h.client.patch(path, json=body, headers=h.headers(version=3))
        assert rejected.status_code == 403 and rejected.json()["code"] == "STEP_UP_REQUIRED"
    body = {"expiresAt": bounded + 60}
    grant = h.grant(f"PATCH {path}", body, version=3)
    extended = h.client.patch(path, json=body, headers=h.headers(version=3, grant=grant))
    assert extended.status_code == 200
    body = {"expiresAt": None}
    grant = h.grant(f"PATCH {path}", body, version=4)
    assert (
        h.client.patch(path, json=body, headers=h.headers(version=4, grant=grant)).status_code
        == 200
    )


def test_expired_member_reactivation_requires_fresh_proof_and_changes_generation(harness):
    h = harness
    path = f"/v1/households/{h.h}/members/sam"
    h.clock.advance(-11)
    assert (
        h.client.patch(
            path, json={"expiresAt": h.clock() + 10}, headers=h.headers(version=1)
        ).status_code
        == 200
    )
    h.clock.advance(11)
    body = {"expiresAt": None}
    assert h.client.patch(path, json=body, headers=h.headers(version=2)).status_code == 403
    grant = h.grant(f"PATCH {path}", body, version=2)
    restored = h.client.patch(path, json=body, headers=h.headers(version=2, grant=grant))
    assert restored.status_code == 200 and restored.json()["accessEpoch"] == 2


@pytest.mark.parametrize("case", ["nonce", "subject", "freshness", "expired-challenge"])
def test_step_up_rejects_invalid_proof(harness, case):
    h = harness
    response = h.client.post(
        "/v1/auth/step-up",
        json={"operation": "POST /v1/commands", "requestHash": "a" * 64},
        headers=h.headers(),
    )
    challenge = response.json()
    actor = "sam" if case == "subject" else "alex"
    nonce = "wrong" if case == "nonce" else challenge["nonce"]
    proof = token(
        h.settings, actor, nonce=nonce, now=h.clock() - 60 if case == "freshness" else h.clock()
    )
    if case == "expired-challenge":
        h.clock.advance(181)
    result = h.client.post(
        f"/v1/auth/step-up/{challenge['id']}/complete",
        json={"identityProof": proof},
        headers=h.headers(),
    )
    assert result.status_code == 403


def test_delegation_expiry_revocation_and_no_transitive_authority(harness):
    h = harness
    tid = h.command()
    path = f"/v1/tasks/{tid}/delegations"
    body = dict(
        schemaVersion="1.0",
        principalId="sam",
        permissions=["control", "read"],
        expiresAt=h.clock() + 100,
    )
    grant = h.grant(f"POST {path}", body)
    added = h.client.post(path, json=body, headers=h.headers(grant=grant))
    assert added.status_code == 201, added.text
    assert h.client.get(f"/v1/tasks/{tid}", headers=h.headers("sam")).status_code == 200
    assert h.client.post(path, json=body, headers=h.headers("sam")).status_code == 404
    assert (
        h.client.patch(
            f"/v1/tasks/{tid}",
            json={"visibility": "household"},
            headers=h.headers("sam", version=1),
        ).status_code
        == 404
    )
    h.clock.advance(101)
    assert h.client.get(f"/v1/tasks/{tid}", headers=h.headers("sam")).status_code == 404
    # Row remains physically present: logical expiry wins over TTL cleanup.
    item = h.domain.store.get("Domain", (hkey(h.h), f"DELEGATION#{tid}#sam"))
    assert item["active"] is True
    revoked = h.client.delete(f"{path}/sam", headers=h.headers(version=item["rev"]))
    assert revoked.status_code == 200


def test_revoke_membership_blocks_reads_and_command_replay(harness):
    h = harness
    key = uuid4().hex
    tid = h.command("sam", key=key)
    result = h.client.delete(f"/v1/households/{h.h}/members/sam", headers=h.headers(version=1))
    assert result.status_code == 200
    assert h.client.get(f"/v1/tasks/{tid}", headers=h.headers("sam")).status_code == 403
    body = Command(operation="synthetic.checkpoint", label="Synthetic checkpoint").model_dump()
    assert (
        h.client.post("/v1/commands", json=body, headers=h.headers("sam", key=key)).status_code
        == 403
    )


def test_reenrollment_does_not_resurrect_old_delegation_or_execution(harness):
    h = harness
    delegated = h.command()
    owned = h.command("sam")
    path = f"/v1/tasks/{delegated}/delegations"
    body = {
        "schemaVersion": "1.0",
        "principalId": "sam",
        "permissions": ["read"],
        "expiresAt": h.clock() + 500,
    }
    assert (
        h.client.post(
            path, json=body, headers=h.headers(grant=h.grant(f"POST {path}", body))
        ).status_code
        == 201
    )
    assert (
        h.client.delete(
            f"/v1/households/{h.h}/members/sam", headers=h.headers(version=1)
        ).status_code
        == 200
    )
    path = f"/v1/households/{h.h}/members"
    body = MemberCreate(principalId="sam").model_dump()
    assert (
        h.client.post(
            path, json=body, headers=h.headers(grant=h.grant(f"POST {path}", body))
        ).status_code
        == 201
    )
    assert h.client.get(f"/v1/tasks/{delegated}", headers=h.headers("sam")).status_code == 404
    h.start(owned)
    assert h.task(owned, "sam")["status"] == "FAILED"


def test_last_administrator_is_protected_under_concurrency(harness):
    h = harness
    ctx = h.domain.context("alex", h.h)
    body = MemberCreate(principalId="co-admin", role="admin").model_dump()
    _, writes, _ = h.domain.add_member(ctx, body)
    h.domain.store.transact(ctx.guards() + writes)

    def demote(principal):
        try:
            return h.domain.mutate(
                "alex",
                h.h,
                f"PATCH /v1/households/{h.h}/members/{principal}",
                {"role": "member"},
                uuid4().hex,
                1,
                None,
                lambda ctx: h.domain.change_member(
                    ctx, principal, {"role": "member"}, 1, revoke=False
                ),
                auth="admin",
            )
        except Problem as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(demote, ["alex", "co-admin"]))
    assert sum(isinstance(x, dict) for x in outcomes) == 1
    household = h.domain.store.get("Domain", (hkey(h.h), "META"))
    assert household["adminCount"] == 1


def test_authority_is_revalidated_after_transaction_conflict(harness, monkeypatch):
    h = harness
    original = h.domain.store.transact
    invoked = False

    def racing(changes):
        nonlocal invoked
        if not invoked:
            invoked = True
            member = h.domain.store.get("Domain", (hkey(h.h), "MEMBER#sam"))
            original([put("Domain", revised(member, active=False), member)])
            raise Conflict
        original(changes)

    monkeypatch.setattr(h.domain.store, "transact", racing)
    response = h.client.post(
        "/v1/commands",
        json={"operation": "synthetic.checkpoint", "label": "demo"},
        headers=h.headers("sam"),
    )
    assert response.status_code == 403
    assert h.domain.context("alex", h.h).household["activeTasks"] == 0
    assert h.domain.store.query("Domain", hkey(h.h), prefix="TASK#")[0] == []


def test_admission_limit_and_terminal_release(harness):
    h = harness
    h.domain.settings = replace(h.settings, max_tasks=2)
    first = h.command()
    h.command()
    response = h.client.post(
        "/v1/commands",
        json={"operation": "synthetic.checkpoint", "label": "demo"},
        headers=h.headers(),
    )
    assert response.status_code == 429
    assert (
        h.client.post(f"/v1/tasks/{first}/cancel", headers=h.headers(version=1)).status_code == 202
    )
    h.command()
    assert h.domain.context("alex", h.h).household["activeTasks"] == 2


def test_errors_and_logs_do_not_include_input_or_dependency_details(harness, monkeypatch, caplog):
    h = harness
    marker = "PRIVATE_SECRET_NOT_FOR_LOGS"
    invalid = h.client.post(
        "/v1/commands", content=json.dumps({"label": marker}), headers=h.headers()
    )
    assert invalid.status_code == 422 and marker not in invalid.text

    def broken(*args, **kwargs):
        raise RuntimeError(marker)

    monkeypatch.setattr(h.domain.store, "get", broken)
    error = h.client.get("/health/ready")
    assert error.status_code == 503 and marker not in error.text
    assert marker not in caplog.text
    assert "application/problem+json" in error.headers["Content-Type"]
    assert error.headers["Cache-Control"] == "no-store"


def test_http_body_is_bounded_without_content_length(harness, caplog):
    caplog.set_level("INFO", logger="koyori.http")
    response = harness.client.post(
        "/v1/commands", content=iter([b"x" * 20000, b"x" * 20000]), headers=harness.headers()
    )
    assert response.status_code == 413
    assert response.headers["X-Request-Id"] == response.json()["requestId"]
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.json()["requestId"] in caplog.text


@pytest.mark.parametrize("content", [json.dumps({"owner": "robin", "mode": "live"}), "{", b"\xff"])
def test_control_operations_reject_hidden_arguments(harness, content, caplog):
    tid = harness.command()
    caplog.clear()
    caplog.set_level("INFO", logger="koyori.http")
    response = harness.client.post(
        f"/v1/tasks/{tid}/cancel",
        content=content,
        headers=harness.headers(version=1),
    )
    assert response.status_code == 422
    assert response.headers["X-Request-Id"] == response.json()["requestId"]
    assert response.headers["Cache-Control"] == "no-store"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.json()["requestId"] in caplog.text
    assert "robin" not in response.text + caplog.text
    assert harness.task(tid)["status"] == "READY"


def test_method_not_allowed_preserves_allow_header(harness):
    response = harness.client.post("/health/live")
    assert response.status_code == 405
    assert "GET" in response.headers["Allow"].split(", ")
    assert response.headers["Content-Type"] == "application/problem+json"


def test_cursors_are_principal_household_and_route_bound(harness):
    h = harness
    cursor = h.domain.cursors.encode("alex", h.h, "tasks", {"PK": hkey(h.h), "SK": "TASK#x"})
    assert (
        h.client.get("/v1/tasks", params={"cursor": cursor}, headers=h.headers()).status_code == 200
    )
    assert (
        h.client.get("/v1/tasks", params={"cursor": cursor}, headers=h.headers("sam")).status_code
        == 400
    )
    assert (
        h.client.get("/v1/activity", params={"cursor": cursor}, headers=h.headers()).status_code
        == 400
    )
    assert (
        h.client.get(
            "/v1/tasks", params={"cursor": cursor[:-1] + "!"}, headers=h.headers()
        ).status_code
        == 400
    )
    h.clock.advance(3601)
    assert (
        h.client.get("/v1/tasks", params={"cursor": cursor}, headers=h.headers()).status_code == 400
    )


def test_cursor_does_not_disclose_a_private_discovery_key(harness):
    import base64

    private_id = "private-object-identifier"
    cursor = harness.domain.cursors.encode(
        "alex", harness.h, "tasks", {"PK": hkey(harness.h), "SK": f"TASK#{private_id}"}
    )
    decoded = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
    assert private_id.encode() not in decoded
