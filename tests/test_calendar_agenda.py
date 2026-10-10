from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import pytest
from test_stage2_calendar import FakeGoogle
from test_stage2_calendar import calendar as calendar  # noqa: F401 - shared fixture
from test_stage4_sessions import admission

from koyori.agenda import _instant
from koyori.calendar import READ_SCOPES
from koyori.channel_tools import ChannelTools
from koyori.domain import hkey, row
from koyori.errors import Problem
from koyori.sessions import Sessions
from koyori.stage2_contracts import CalendarAuthorize
from koyori.store import put
from koyori.voice import VoiceSession

CALENDAR = "calendar@example.invalid"


class WritableGoogle(FakeGoogle):
    """Provider-contract fixture with an owned primary calendar; not a real Google account."""

    def __init__(self, clock):
        super().__init__(clock)
        self.role = "owner"
        self.created = {}
        self.inserts = []
        self.lose_response = False

    def calendars(self, token):
        return [
            {"id": CALENDAR, "accessRole": self.role, "primary": True},
            {"id": "shared@example.invalid", "accessRole": "reader"},
        ]

    def event(self, token, calendar, event_id):
        return self.created.get((calendar, event_id))

    def insert(self, token, calendar, event):
        self.inserts.append((calendar, event))
        self.created[(calendar, event["id"])] = {**event, "htmlLink": "https://calendar.example/e"}
        if self.lose_response:
            raise Problem(503, "PROVIDER_UNAVAILABLE", "Google request failed.", True)
        return self.created[(calendar, event["id"])]


@pytest.fixture
def agenda(calendar):  # noqa: F811
    h, service = calendar
    service.google = WritableGoogle(h.clock)
    return h, service, h.client.app.state.agenda


def connect(h, calendar_ids=("primary",)):
    body = CalendarAuthorize(calendarIds=list(calendar_ids)).model_dump()
    grant = h.grant("POST /v1/connections/google-calendar/authorize", body)
    response = h.client.post(
        "/v1/connections/google-calendar/authorize", json=body, headers=h.headers(grant=grant)
    )
    assert response.status_code == 201, response.text
    state = parse_qs(urlparse(response.json()["authorizationUrl"]).query)["state"][0]
    callback = h.client.get(
        "/v1/oauth/google/callback", params={"state": state, "code": "test-code"}
    )
    assert callback.status_code == 200, callback.text
    connection = h.client.get(f"/v1/connections/{callback.json()['id']}", headers=h.headers())
    return connection.json()


def draft(h, **values):
    return {
        "title": "Dentiste",
        "startAt": h.clock() + 86400,
        "endAt": h.clock() + 86400 + 1800,
        "location": "Cabinet du centre",
        **values,
    }


def propose(h, body, actor="alex"):
    response = h.client.post("/v1/calendar-proposals", json=body, headers=h.headers(actor))
    assert response.status_code == 201, response.text
    return response.json()


def decide(h, proposal, decision, actor="alex"):
    return h.client.post(
        f"/v1/calendar-proposals/{proposal['id']}/decision",
        json={"decision": decision},
        headers=h.headers(actor, version=proposal["rev"]),
    )


def intent(h, proposal):
    return h.domain.store.get("Delivery", (f"CALWRITE#{proposal['id']}", "META"))


def test_primary_alias_resolves_to_owned_calendar_labels_account_and_grants_write(agenda):
    h, _, _ = agenda
    connection = connect(h)
    assert connection["calendarIds"] == [CALENDAR]
    assert connection["account"] == CALENDAR
    assert connection["capabilities"] == ["calendar.read", "calendar.write"]


def test_read_only_grant_keeps_reading_but_refuses_event_proposals(agenda):
    h, service, _ = agenda
    exchange = service.google.exchange
    service.google.exchange = lambda code, verifier: {
        **exchange(code, verifier),
        "scope": " ".join(READ_SCOPES),
    }
    connection = connect(h)
    assert connection["capabilities"] == ["calendar.read"]
    response = h.client.post("/v1/calendar-proposals", json=draft(h), headers=h.headers())
    assert response.status_code == 409
    assert response.json()["code"] == "CALENDAR_READ_ONLY"


def test_confirmed_proposal_is_created_once_in_the_owners_timezone(agenda):
    h, service, agenda_service = agenda
    connect(h)
    proposal = propose(h, draft(h))
    assert proposal["status"] == "PENDING" and proposal["origin"] == "person"
    assert proposal["calendarId"] == CALENDAR
    assert agenda_service.sweep() == 0 and not service.google.inserts

    response = decide(h, proposal, "approve")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "APPROVED"
    agenda_service.sweep()

    ((calendar_id, event),) = service.google.inserts
    assert calendar_id == CALENDAR
    assert event["summary"] == "Dentiste" and event["location"] == "Cabinet du centre"
    assert event["start"]["timeZone"] == "Europe/Paris"
    start = datetime.fromisoformat(event["start"]["dateTime"])
    assert int(start.timestamp()) == proposal["startAt"]
    assert set(event["id"]) <= set("0123456789abcdefghijklmnopqrstuv")

    saved = h.client.get("/v1/calendar-proposals", headers=h.headers()).json()["items"][0]
    assert saved["status"] == "CREATED" and saved["link"] == "https://calendar.example/e"
    assert intent(h, proposal)["status"] == "DONE"
    assert decide(h, saved, "approve").json()["code"] == "PROPOSAL_DECIDED"


def test_lost_provider_response_is_retried_without_a_duplicate_event(agenda):
    h, service, agenda_service = agenda
    connect(h)
    proposal = propose(h, draft(h))
    decide(h, proposal, "approve")
    service.google.lose_response = True
    agenda_service.sweep()
    assert (
        h.domain.store.get("Domain", (hkey(h.h), f"CALPROPOSAL#{proposal['id']}"))["status"]
        == "APPROVED"
    )

    service.google.lose_response = False
    h.clock.advance(3600)
    agenda_service.sweep()
    assert len(service.google.inserts) == 1
    saved = h.domain.store.get("Domain", (hkey(h.h), f"CALPROPOSAL#{proposal['id']}"))
    assert saved["status"] == "CREATED"


def test_rejection_writes_nothing_and_a_non_owned_calendar_fails_visibly(agenda):
    h, service, agenda_service = agenda
    connect(h)
    rejected = decide(h, propose(h, draft(h)), "reject").json()
    assert rejected["status"] == "REJECTED" and intent(h, rejected) is None

    proposal = propose(h, draft(h, title="Réunion"))
    decide(h, proposal, "approve")
    service.google.role = "writer"
    agenda_service.sweep()
    saved = h.domain.store.get("Domain", (hkey(h.h), f"CALPROPOSAL#{proposal['id']}"))
    assert saved["status"] == "FAILED" and saved["error"] == "CALENDAR_NOT_WRITABLE"
    assert not service.google.inserts


def test_proposals_are_private_to_their_owner(agenda):
    h, _, _ = agenda
    connect(h)
    proposal = propose(h, draft(h))
    assert h.client.get("/v1/calendar-proposals", headers=h.headers("sam")).json()["items"] == []
    assert decide(h, proposal, "approve", actor="sam").status_code == 404


def test_invalid_times_are_refused(agenda):
    h, _, _ = agenda
    connect(h)
    for body in (
        draft(h, startAt=h.clock() - 7200, endAt=h.clock() - 3600),
        draft(h, endAt=h.clock() + 86400),
        draft(h, startAt=h.clock() + 400 * 86400, endAt=h.clock() + 400 * 86400 + 60),
    ):
        response = h.client.post("/v1/calendar-proposals", json=body, headers=h.headers())
        assert response.status_code == 422, response.text


def test_assistant_can_only_propose_and_replays_idempotently(agenda):
    h, _, _ = agenda
    connect(h)
    ctx = h.domain.context("alex", h.h)
    tools, secret = ChannelTools(h.domain), Sessions(h.domain).grant(ctx)
    arguments = {**draft(h), "idempotencyKey": "a" * 32}
    first = tools.call(secret, "propose_calendar_event", arguments)
    again = tools.call(secret, "propose_calendar_event", arguments)
    assert first == again
    assert first["status"] == "PENDING" and first["origin"] == "assistant"
    assert intent(h, first) is None


def test_agenda_window_lists_synced_events_in_order(agenda):
    h, service, _ = agenda
    connection = connect(h)
    now = h.clock()

    def iso(seconds):
        return datetime.fromtimestamp(seconds, UTC).isoformat()

    service.google.pages = [
        {
            "items": [
                {
                    "id": "late",
                    "summary": "Cinéma",
                    "start": {"dateTime": iso(now + 7200)},
                    "end": {"dateTime": iso(now + 10800)},
                },
                {
                    "id": "early",
                    "summary": "Café",
                    "start": {"dateTime": iso(now + 600)},
                    "end": {"dateTime": iso(now + 1200)},
                },
                {
                    "id": "far",
                    "summary": "Vacances",
                    "start": {"dateTime": iso(now + 40 * 86400)},
                    "end": {"dateTime": iso(now + 41 * 86400)},
                },
                {"id": "gone", "summary": "Annulé", "status": "cancelled"},
            ],
            "nextSyncToken": "sync-1",
        }
    ]
    service.sync(h.domain.context("alex", h.h), connection["id"])
    response = h.client.get(
        "/v1/agenda", params={"from": now, "to": now + 7 * 86400}, headers=h.headers()
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert [e["title"] for e in body["items"]] == ["Café", "Cinéma"]
    assert body["syncedAt"] == now and body["mode"] == "real"
    too_wide = h.client.get(
        "/v1/agenda", params={"from": now, "to": now + 40 * 86400}, headers=h.headers()
    )
    assert too_wide.status_code == 422


def test_consent_popup_gets_a_static_page_and_cancellation_is_explained(agenda):
    h, _, _ = agenda
    body = CalendarAuthorize(calendarIds=["primary"]).model_dump()
    grant = h.grant("POST /v1/connections/google-calendar/authorize", body)
    url = h.client.post(
        "/v1/connections/google-calendar/authorize", json=body, headers=h.headers(grant=grant)
    ).json()["authorizationUrl"]
    state = parse_qs(urlparse(url).query)["state"][0]
    html = {"Accept": "text/html"}
    denied = h.client.get(
        "/v1/oauth/google/callback", params={"state": state, "error": "access_denied"}, headers=html
    )
    assert denied.status_code == 400 and "Annulée" in denied.text
    page = h.client.get(
        "/v1/oauth/google/callback", params={"state": state, "code": "test-code"}, headers=html
    )
    assert page.status_code == 200 and "Google Agenda connecté" in page.text
    assert state not in page.text and page.headers["cache-control"] == "no-store"


def test_reconnected_account_replaces_its_connection(agenda):
    h, service, _ = agenda
    now = h.clock()
    page = {
        "items": [
            {
                "id": "standup",
                "summary": "Point du matin",
                "start": {"dateTime": datetime.fromtimestamp(now + 600, UTC).isoformat()},
                "end": {"dateTime": datetime.fromtimestamp(now + 1200, UTC).isoformat()},
            }
        ],
        "nextSyncToken": "sync-1",
    }
    connections = []
    for _ in range(2):
        connections.append(connect(h))
        service.google.pages = [page]
        service.sync(h.domain.context("alex", h.h), connections[-1]["id"])
    first, second = (
        h.domain.store.get("Domain", (hkey(h.h), f"CONNECTION#{c['id']}")) for c in connections
    )
    assert first["active"] is False and second["active"] is True
    # The previous grant is discarded, not revoked: Google may tie it to the new one.
    assert h.domain.store.get("Connections", service.token_key(first))["envelope"] is None
    assert service.google.revoked is False
    items = h.client.get(
        "/v1/agenda", params={"from": now, "to": now + 86400}, headers=h.headers()
    ).json()["items"]
    assert [e["title"] for e in items] == ["Point du matin"]
    # One writable account is left, so a proposal need not name it.
    assert propose(h, draft(h))["connectionId"] == second["id"]


def test_proposals_follow_a_reconnected_account(agenda):
    h, service, agenda_service = agenda
    old = connect(h)
    approved = propose(h, draft(h))
    assert decide(h, approved, "approve").status_code == 200
    waiting = propose(h, draft(h, title="Kiné"))
    new = connect(h)
    response = decide(h, waiting, "approve")
    assert response.status_code == 200, response.text
    agenda_service.sweep()
    for proposal in (approved, waiting):
        saved = h.domain.store.get("Domain", (hkey(h.h), f"CALPROPOSAL#{proposal['id']}"))
        assert saved["status"] == "CREATED" and saved["connectionId"] == new["id"] != old["id"]
    assert len(service.google.inserts) == 2


def test_a_followed_proposal_still_needs_its_calendar_selected(agenda):
    h, service, agenda_service = agenda
    connect(h, ("primary", "shared@example.invalid"))
    approved = propose(h, draft(h, calendarId="shared@example.invalid"))
    assert decide(h, approved, "approve").status_code == 200
    waiting = propose(h, draft(h, calendarId="shared@example.invalid"))
    connect(h)
    refused = decide(h, waiting, "approve")
    assert refused.status_code == 422 and refused.json()["code"] == "CALENDAR_NOT_SELECTED"
    agenda_service.sweep()
    saved = h.domain.store.get("Domain", (hkey(h.h), f"CALPROPOSAL#{approved['id']}"))
    assert saved["status"] == "FAILED" and saved["error"] == "CALENDAR_NOT_SELECTED"
    assert not service.google.inserts


def test_an_offsetless_time_uses_the_events_named_zone():
    paris = {"dateTime": "2026-10-11T09:00:00", "timeZone": "Europe/Paris"}
    assert _instant(paris, None) == (int(datetime(2026, 10, 11, 7, tzinfo=UTC).timestamp()), False)
    assert _instant({**paris, "timeZone": "Nowhere/Invalid"}, None) == (None, False)


def test_a_repeated_voice_proposal_is_created_once(agenda):
    h, _, _ = agenda
    connect(h)
    sessions, grant = admission(h)
    sessions.consume(grant["ticket"], grant["runtimeSessionId"])
    bridge = VoiceSession(h.domain, grant["runtimeSessionId"], h.client.app.state.mcp.tools)
    first, again = (
        bridge.tool("call-1", "propose_calendar_event", {**draft(h), "idempotencyKey": key})
        for key in ("a" * 32, "b" * 32)
    )
    assert first["id"] == again["id"]


def test_an_event_created_during_a_revocation_is_still_recorded(agenda):
    h, service, agenda_service = agenda
    connection = connect(h)
    proposal = propose(h, draft(h))
    decide(h, proposal, "approve")
    insert = service.google.insert

    def revoked_meanwhile(token, calendar, event):
        created = insert(token, calendar, event)
        response = h.client.delete(
            f"/v1/connections/{connection['id']}", headers=h.headers(version=connection["rev"])
        )
        assert response.status_code == 200, response.text
        return created

    service.google.insert = revoked_meanwhile
    agenda_service.sweep()
    saved = h.domain.store.get("Domain", (hkey(h.h), f"CALPROPOSAL#{proposal['id']}"))
    assert saved["status"] == "CREATED" and len(service.google.inserts) == 1


def test_an_unfinished_first_sync_is_reported_as_incomplete(agenda):
    h, service, _ = agenda
    connection = connect(h)
    now = h.clock()

    def window():
        return h.client.get(
            "/v1/agenda", params={"from": now, "to": now + 86400}, headers=h.headers()
        ).json()

    assert window()["truncated"] is True
    service.google.pages = [{"items": [], "nextSyncToken": "sync-1"}]
    service.sync(h.domain.context("alex", h.h), connection["id"])
    assert window()["truncated"] is False


def test_proposal_changes_reach_only_the_owners_activity(agenda):
    h, _, _ = agenda
    connect(h)
    propose(h, draft(h))
    for event in h.engine.pending("OUTBOX"):
        if event["envelope"]["type"] == "koyori.proposal.changed.v1":
            h.engine.project_activity(event["envelope"])
    own = h.client.get("/v1/activity", headers=h.headers()).json()["items"]
    other = h.client.get("/v1/activity", headers=h.headers("sam")).json()["items"]
    assert any(e["type"] == "koyori.proposal.changed.v1" for e in own)
    assert not any(e["type"] == "koyori.proposal.changed.v1" for e in other)


def test_voice_playback_rechecks_a_proposal_not_a_task(agenda):
    h, _, _ = agenda
    connect(h)
    sessions, grant = admission(h)
    sessions.consume(grant["ticket"], grant["runtimeSessionId"])
    bridge = VoiceSession(h.domain, grant["runtimeSessionId"], h.client.app.state.mcp.tools)
    proposal = bridge.tool("call-1", "propose_calendar_event", draft(h))
    bridge.validate_result(proposal)
    decide(h, proposal, "reject")
    with pytest.raises(Problem, match="CONTEXT_CHANGED"):
        bridge.validate_result(proposal)


def test_an_ended_proposal_is_neither_approved_nor_written(agenda):
    h, service, agenda_service = agenda
    connect(h)
    pending, approved = propose(h, draft(h)), propose(h, draft(h))
    assert decide(h, approved, "approve").status_code == 200
    h.clock.advance(2 * 86400)
    refused = decide(h, pending, "approve")
    assert refused.status_code == 422 and refused.json()["code"] == "PROPOSAL_EXPIRED"
    agenda_service.sweep()
    saved = h.domain.store.get("Domain", (hkey(h.h), f"CALPROPOSAL#{approved['id']}"))
    assert saved["status"] == "FAILED" and saved["error"] == "PROPOSAL_EXPIRED"
    assert not service.google.inserts


def test_reconnect_finds_the_previous_connection_beyond_the_first_page(agenda):
    h, _, _ = agenda
    first = connect(h)
    ctx = h.domain.context("alex", h.h)
    # Sixty lower-sorting rows push the first connection past the first page of fifty.
    for i in range(60):
        other = row(hkey(h.h), f"CONNECTION#{i:032x}", owner="sam", provider="google-calendar")
        h.domain.store.transact([put("Domain", {**other, "active": True})])
    assert len(h.client.app.state.calendar.accounts(ctx)) == 1
    connect(h)
    retired = h.domain.store.get("Domain", (hkey(h.h), f"CONNECTION#{first['id']}"))
    assert retired["active"] is False


def test_without_a_calendar_a_proposal_uses_a_selected_one(agenda):
    h, _, _ = agenda
    connect(h, ("shared@example.invalid",))
    assert propose(h, draft(h))["calendarId"] == "shared@example.invalid"
