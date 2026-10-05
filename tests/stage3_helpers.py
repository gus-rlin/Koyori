"""Explicit simulated planning helpers; no live model or merchant is implied."""

from koyori.actions import Actions
from koyori.domain import hkey
from koyori.planner import SimulatedPlanner


def goals(h):
    service = h.client.app.state.goals
    service.planning = SimulatedPlanner()
    return service


def submit(h, text="Prépare le dîner pour deux demain à 20 h", key=None):
    response = h.client.post("/v1/goals", json={"text": text}, headers=h.headers(key=key))
    assert response.status_code == 202, response.text
    return response.json()["id"]


def task(h, tid):
    return h.domain.store.get("Domain", (hkey(h.h), f"TASK#{tid}"))


def progress(h, tid, service=None, *, advance=True, iterations=30):
    service = service or goals(h)
    for _ in range(iterations):
        service.sweep()
        Actions(h.domain).sweep()
        current = task(h, tid)
        if current["status"] in {
            "SUCCEEDED",
            "NEEDS_ATTENTION",
            "WAITING_APPROVAL",
            "PAUSED",
            "CANCELLED",
            "FAILED",
        }:
            return current
        if advance:
            h.clock.advance(5)
    return task(h, tid)


def control(h, tid, action, **kwargs):
    version = task(h, tid)["rev"]
    response = h.client.post(
        f"/v1/goals/{tid}/{action}", headers=h.headers(version=version, **kwargs)
    )
    assert response.status_code == 202, response.text
    return response.json()
