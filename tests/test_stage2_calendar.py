import json
import logging
from dataclasses import replace
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.exceptions import InvalidTag

from koyori.calendar import SCOPES, Calendar, Envelope, Google
from koyori.domain import hkey
from koyori.errors import Conflict, Problem
from koyori.stage2_contracts import CalendarAuthorize
from koyori.store import put, revised


class FakeGoogle:
    """Provider-contract fixture; it does not qualify a real Google account."""

    def __init__(self, clock):
        self.clock = clock
        self.allowed = True
        self.pages = [
            {
                "items": [
                    {
                        "id": "event-one",
                        "summary": "Dinner",
                        "etag": "v1",
                        "start": {"date": "2026-10-05"},
                    }
                ],
                "nextSyncToken": "sync-1",
            }
        ]
        self.refreshes = 0
        self.revoked = False
        self.watches = []

    def config(self):
        return {}

    def exchange(self, code, verifier):
        assert code == "test-code" and len(verifier) > 40
        return {
            "access_token": "private-access",
            "refresh_token": "private-refresh",
            "expires_in": 3600,
            "scope": " ".join(SCOPES),
        }

    def calendars(self, token):
        if not self.allowed:
            return []
        return [{"id": "calendar@example.invalid", "accessRole": "reader"}]

    def refresh(self, token):
        assert token == "private-refresh"
        self.refreshes += 1
        return {"access_token": "private-refreshed", "expires_in": 3600}

    def events(self, token, calendar, **kwargs):
        assert calendar == "calendar@example.invalid"
        page = self.pages.pop(0)
        if isinstance(page, Exception):
            raise page
        return page

    def watch(self, token, calendar, channel, secret):
        self.watches.append((channel, secret))
        return {"resourceId": "resource-one", "expiration": str((self.clock() + 7200) * 1000)}

    def revoke(self, token):
        assert token == "private-refresh"
        self.revoked = True
        return {}


@pytest.fixture
def calendar(harness, tmp_path):
    h = harness
    key = tmp_path / "provider.key"
    key.write_bytes(b"a" * 32)
    settings = replace(
        h.settings,
        token_key_file=str(key),
        google_client_id="fixture-google-client",
        google_redirect_uri="http://127.0.0.1:8088/v1/oauth/google/callback",
        google_webhook_url="https://example.invalid/v1/webhooks/google-calendar",
    )
    h.domain.settings = settings
    service = h.client.app.state.calendar
    service.google = FakeGoogle(h.clock)
    service.envelope = Envelope(settings)
    h.client.app.state.calendar = service
    return h, service


def connect(h, service):
    body = CalendarAuthorize(calendarIds=["calendar@example.invalid"]).model_dump()
    grant = h.grant("POST /v1/connections/google-calendar/authorize", body)
    response = h.client.post(
        "/v1/connections/google-calendar/authorize", json=body, headers=h.headers(grant=grant)
    )
    assert response.status_code == 201, response.text
    authorization = response.json()
    state = parse_qs(urlparse(authorization["authorizationUrl"]).query)["state"][0]
    callback = h.client.get(
        "/v1/oauth/google/callback", params={"state": state, "code": "test-code"}
    )
    assert callback.status_code == 200, callback.text
    return callback.json(), state


def test_oauth_is_single_use_scoped_and_credentials_are_encrypted(calendar):
    h, service = calendar
    connection, state = connect(h, service)
    assert (
        h.client.get(
            "/v1/oauth/google/callback", params={"state": state, "code": "test-code"}
        ).status_code
        == 409
    )
    assert (
        h.client.get(f"/v1/connections/{connection['id']}", headers=h.headers("sam")).status_code
        == 404
    )
    dumped = json.dumps(list(h.domain.store.rows.values()))
    assert "private-access" not in dumped and "private-refresh" not in dumped
    assert state not in dumped
    assert service.get(h.domain.context("alex", h.h), connection["id"])["capabilities"] == [
        "calendar.read"
    ]


def test_selected_calendar_sync_read_and_revocation(calendar):
    h, service = calendar
    connection, _ = connect(h, service)
    ctx = h.domain.context("alex", h.h)
    service.sync(ctx, connection["id"])
    assert service.events(ctx, connection["id"])["items"][0]["summary"] == "Dinner"
    assert (
        h.client.get(
            f"/v1/connections/{connection['id']}/events", headers=h.headers("sam")
        ).status_code
        == 404
    )
    service.google.allowed = False
    with pytest.raises(Problem, match="CALENDAR_ACCESS_REVOKED"):
        service.sync(ctx, connection["id"])
    assert (
        h.client.get(f"/v1/connections/{connection['id']}/events", headers=h.headers()).status_code
        == 409
    )


def test_sync_pagination_and_expired_cursor_remove_stale_events(calendar):
    h, service = calendar
    connection, _ = connect(h, service)
    ctx = h.domain.context("alex", h.h)
    service.sync(ctx, connection["id"])
    service.google.pages = [
        Problem(409, "SYNC_TOKEN_EXPIRED", "expired"),
        {"items": [{"id": "new-one", "summary": "New"}], "nextPageToken": "page-two"},
        {"items": [], "nextSyncToken": "sync-two"},
    ]
    service.sync(ctx, connection["id"])
    assert service.events(ctx, connection["id"])["items"] == []
    service.sync(ctx, connection["id"])
    assert service.events(ctx, connection["id"])["items"] == []
    service.sync(ctx, connection["id"])
    assert [x["id"] for x in service.events(ctx, connection["id"])["items"]] == ["new-one"]


def test_incremental_deletion_and_duplicate_notification_are_coherent(calendar):
    h, service = calendar
    connection, _ = connect(h, service)
    ctx = h.domain.context("alex", h.h)
    service.sync(ctx, connection["id"])
    service.register_watch(ctx, connection["id"])
    channel, secret = service.google.watches[0]
    headers = {
        "x-goog-channel-id": channel,
        "x-goog-channel-token": secret,
        "x-goog-resource-id": "resource-one",
        "x-goog-message-number": "5",
    }
    service.webhook(headers)
    intent = h.domain.store.get("Delivery", (f"CALRUN#{connection['id']}", "META"))
    service.webhook(headers)
    service.webhook({**headers, "x-goog-message-number": "3"})
    assert h.domain.store.get("Delivery", (intent["PK"], intent["SK"]))["rev"] == intent["rev"]
    with pytest.raises(Problem, match="WEBHOOK_INVALID"):
        service.webhook({**headers, "x-goog-channel-token": "wrong"})
    service.google.pages = [
        {"items": [{"id": "event-one", "status": "cancelled"}], "nextSyncToken": "sync-two"}
    ]
    service.sync(ctx, connection["id"])
    assert service.events(ctx, connection["id"])["items"] == []


def test_refresh_lease_and_revocation_fence_prevent_token_resurrection(calendar):
    h, service = calendar
    connection, _ = connect(h, service)
    ctx = h.domain.context("alex", h.h)
    conn = service.get(ctx, connection["id"])
    secret_row = h.domain.store.get("Connections", service.token_key(conn))
    credentials = service.envelope.open(secret_row["envelope"], "alex", conn["id"])
    credentials["expiresAt"] = h.clock()
    expired = revised(secret_row, envelope=service.envelope.seal(credentials, "alex", conn["id"]))
    h.domain.store.transact([put("Connections", expired, secret_row)])
    refresh = service.google.refresh

    def race(token):
        _, writes, _ = service.revoke(ctx, conn["id"], conn["rev"])
        h.domain.store.transact(ctx.guards() + writes)
        return refresh(token)

    service.google.refresh = race
    with pytest.raises(Conflict):
        service.access_token(ctx, conn)
    assert not service.get(ctx, conn["id"], inactive=True)["active"]
    secret_row = h.domain.store.get("Connections", service.token_key(conn))
    assert "private-refreshed" not in json.dumps(secret_row)


def test_expired_watch_is_renewed_and_revocation_erases_credentials(calendar):
    h, service = calendar
    connection, _ = connect(h, service)
    ctx = h.domain.context("alex", h.h)
    assert service.register_watch(ctx, connection["id"]) == 1
    assert service.register_watch(ctx, connection["id"]) == 0
    h.clock.advance(3601)
    assert service.register_watch(ctx, connection["id"]) == 1
    conn = service.get(ctx, connection["id"])
    _, writes, _ = service.revoke(ctx, conn["id"], conn["rev"])
    h.domain.store.transact(ctx.guards() + writes)
    service.sweep()
    assert service.google.revoked
    assert h.domain.store.get("Connections", service.token_key(conn))["envelope"] is None


def test_provider_envelope_is_bound_to_owner_connection_and_environment(calendar):
    h, service = calendar
    envelope = service.envelope.seal({"refresh": "secret"}, "alex", "conn1")
    assert service.envelope.open(envelope, "alex", "conn1") == {"refresh": "secret"}
    with pytest.raises(InvalidTag):
        service.envelope.open(envelope, "sam", "conn1")
    with pytest.raises(InvalidTag):
        service.envelope.open(envelope, "alex", "conn2")


def test_google_http_contract_does_not_follow_redirect_or_expose_provider_errors(harness, tmp_path):
    seen = []

    def handler(request):
        seen.append(request)
        if request.url.path.endswith("/events"):
            assert request.headers["authorization"] == "Bearer private-access"
            assert request.url.params["syncToken"] == "old"
            return httpx.Response(200, json={"items": [], "nextSyncToken": "new"})
        return httpx.Response(
            302, headers={"location": "https://attacker.invalid"}, text="private-access"
        )

    google = Google(harness.settings, httpx.MockTransport(handler))
    assert google.events("private-access", "private/calendar", sync="old")["nextSyncToken"] == "new"
    assert "private%2Fcalendar" in str(seen[0].url)
    with pytest.raises(Problem) as error:
        google.calendars("private-access")
    assert "private-access" not in error.value.detail
    assert len(seen) == 2


def test_oauth_callback_authority_revoked_and_invalid_scope_are_refused(calendar):
    h, service = calendar
    body = CalendarAuthorize(calendarIds=["calendar@example.invalid"]).model_dump()
    response, writes, _ = service.authorize(h.domain.context("sam", h.h), body)
    h.domain.store.transact(writes)
    ctx = h.domain.context("alex", h.h)
    _, revoke, _ = h.domain.change_member(ctx, "sam", {}, 1, revoke=True)
    h.domain.store.transact(ctx.guards() + revoke)
    state = parse_qs(urlparse(response["authorizationUrl"]).query)["state"][0]
    with pytest.raises(Problem):
        service.callback(state, "test-code")
    exchange = service.google.exchange

    def bad_scope(code, verifier):
        return {**exchange(code, verifier), "scope": ""}

    service.google.exchange = bad_scope
    response, writes, _ = service.authorize(h.domain.context("alex", h.h), body)
    h.domain.store.transact(writes)
    state = parse_qs(urlparse(response["authorizationUrl"]).query)["state"][0]
    with pytest.raises(Problem, match="OAUTH_SCOPE_MISSING"):
        service.callback(state, "test-code")


def test_sync_result_cannot_commit_after_connection_revocation(calendar):
    h, service = calendar
    connection, _ = connect(h, service)
    ctx = h.domain.context("alex", h.h)
    events = service.google.events

    def race(*args, **kwargs):
        conn = service.get(ctx, connection["id"])
        _, writes, _ = service.revoke(ctx, conn["id"], conn["rev"])
        h.domain.store.transact(ctx.guards() + writes)
        return events(*args, **kwargs)

    service.google.events = race
    with pytest.raises(Conflict):
        service.sync(ctx, connection["id"])
    rows, _ = h.domain.store.query("Domain", hkey(h.h), prefix=f"CALEVENT#{connection['id']}#")
    assert rows == []


def test_repeated_delete_and_lost_provider_revocation_reply_complete_after_restart(calendar):
    h, service = calendar
    connection, _ = connect(h, service)
    attempts = []

    def handler(request):
        assert request.url.path == "/revoke"
        attempts.append(request)
        if len(attempts) == 1:
            raise httpx.ReadTimeout("fixture response lost after revocation", request=request)
        return httpx.Response(400, json={"error": "invalid_token"})

    google = Google(h.domain.settings, httpx.MockTransport(handler))
    service.google = google
    response = h.client.delete(f"/v1/connections/{connection['id']}", headers=h.headers(version=1))
    assert response.status_code == 200
    service.sweep()
    pending = service.get(h.domain.context("alex", h.h), connection["id"], inactive=True)
    assert pending["revokePending"] and pending["rev"] == 2
    assert (
        h.client.delete(f"/v1/connections/{connection['id']}", headers=h.headers(version=2)).json()[
            "rev"
        ]
        == 2
    )
    restarted = Calendar(h.domain, google=google, envelope=service.envelope)
    assert restarted.sweep() == 0
    h.clock.advance(31)
    restarted.sweep()
    finished = service.get(h.domain.context("alex", h.h), connection["id"], inactive=True)
    assert not finished["revokePending"] and not finished["active"]
    assert h.domain.store.get("Connections", service.token_key(finished))["envelope"] is None
    response = h.client.delete(
        f"/v1/connections/{connection['id']}", headers=h.headers(version=finished["rev"])
    )
    assert response.status_code == 200 and response.json()["rev"] == finished["rev"]
    assert restarted.sweep() == 0 and len(attempts) == 2


def test_failed_revocation_does_not_block_other_connection_sync(calendar):
    h, service = calendar
    failed, _ = connect(h, service)
    response = h.client.delete(f"/v1/connections/{failed['id']}", headers=h.headers(version=1))
    assert response.status_code == 200
    other, _ = connect(h, service)
    intent = h.domain.store.get("Delivery", (f"CALRUN#{failed['id']}", "META"))
    h.domain.store.transact(
        [
            put(
                "Delivery",
                revised(intent, dueAt=h.clock() - 1, GSI1SK=f"{h.clock() - 1:020d}#{failed['id']}"),
                intent,
            )
        ]
    )

    def unavailable(token):
        raise Problem(503, "PROVIDER_UNAVAILABLE", "fixture outage", True)

    service.google.revoke = unavailable
    service.sweep()
    ctx = h.domain.context("alex", h.h)
    assert service.events(ctx, other["id"])["items"][0]["summary"] == "Dinner"
    intent = h.domain.store.get("Delivery", (f"CALRUN#{failed['id']}", "META"))
    assert intent["status"] == "PENDING" and intent["dueAt"] > h.clock()


def test_google_transport_does_not_log_private_calendar_identifiers_cursors_or_tokens(
    harness, caplog
):
    caplog.set_level(logging.INFO)
    google = Google(
        harness.settings,
        httpx.MockTransport(lambda request: httpx.Response(200, json={"items": []})),
    )
    google.events(
        "fixture-private-access",
        "private-calendar@example.invalid",
        sync="fixture-private-sync",
        page="fixture-private-page",
    )
    assert not any(
        secret in caplog.text
        for secret in (
            "fixture-private-access",
            "private-calendar",
            "fixture-private-sync",
            "fixture-private-page",
        )
    )


@pytest.mark.parametrize(
    "error,status,revoked", [("invalid_client", 401, False), ("invalid_grant", 400, True)]
)
def test_google_oauth_client_failure_is_distinct_from_revoked_user_grant(
    calendar, error, status, revoked
):
    h, service = calendar
    connection, _ = connect(h, service)
    ctx = h.domain.context("alex", h.h)
    conn = service.get(ctx, connection["id"])
    secret = h.domain.store.get("Connections", service.token_key(conn))
    credentials = service.envelope.open(secret["envelope"], "alex", conn["id"])
    credentials["expiresAt"] = h.clock()
    h.domain.store.transact(
        [
            put(
                "Connections",
                revised(secret, envelope=service.envelope.seal(credentials, "alex", conn["id"])),
                secret,
            )
        ]
    )
    service.google = Google(
        h.domain.settings,
        httpx.MockTransport(lambda request: httpx.Response(status, json={"error": error})),
    )
    # Test the real refresh HTTP path without loading a real client secret.
    service.google.config = lambda: {"client_id": "fixture", "client_secret": "fixture"}
    with pytest.raises(Problem) as result:
        service.access_token(ctx, conn)
    assert result.value.code == ("OAUTH_REJECTED" if revoked else "OAUTH_CLIENT_INVALID")
    assert service.get(ctx, conn["id"], inactive=True)["active"] is not revoked


def test_unrecognized_revoke_error_remains_pending(harness):
    google = Google(
        harness.settings,
        httpx.MockTransport(lambda request: httpx.Response(400, json={"error": "invalid_request"})),
    )
    with pytest.raises(Problem, match="PROVIDER_UNAVAILABLE"):
        google.revoke("fixture-private-refresh")


def test_revocation_still_erases_token_after_provider_calendar_access_was_removed(calendar):
    h, service = calendar
    connection, _ = connect(h, service)
    ctx = h.domain.context("alex", h.h)
    service.google.allowed = False
    with pytest.raises(Problem, match="CALENDAR_ACCESS_REVOKED"):
        service.sync(ctx, connection["id"])
    disabled = service.get(ctx, connection["id"], inactive=True)
    assert not disabled["active"] and not disabled["revokePending"]
    response = h.client.delete(
        f"/v1/connections/{connection['id']}", headers=h.headers(version=disabled["rev"])
    )
    assert response.status_code == 200 and response.json()["rev"] == disabled["rev"] + 1
    service.sweep()
    assert service.google.revoked
    assert h.domain.store.get("Connections", service.token_key(disabled))["envelope"] is None
