"""Suppression overlay and admission fencing survive restoration and compatibility checks."""

import hashlib
import json

import pytest

from koyori.backup import apply_suppressions, erasure_ledger
from koyori.domain import row
from koyori.release import CONTRACTS, RECOVERY, compatible
from koyori.store import put


def test_ledger_refuses_accepted_but_incomplete_erasure():
    class Source:
        prefix = "OfflineSource"

        def __init__(self):
            self.client = self

        def name(self, table):
            return self.prefix + table

        def decode(self, value):
            return value

        def scan(self, **arguments):
            return {"Items": [row("H#house", "PRIVACY#owner", status="ERASING")]}

    with pytest.raises(ValueError, match="Complete pending memory erasures"):
        erasure_ledger(Source())


def test_post_snapshot_erasure_invalidates_credentials_approvals_sessions():
    mid = "a" * 32
    entries = [{"PK": "H#house", "SK": f"MEMORY#{mid}", "revision": 3}]
    ledger = {
        "schemaVersion": "1.0",
        "entries": entries,
        "sha256": hashlib.sha256(
            json.dumps(entries, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
    }
    tables = {
        "Domain": [
            {
                "PK": "H#house",
                "SK": f"MEMORY#{mid}",
                "rev": 1,
                "id": mid,
                "text": "Erased after backup",
                "privacyEpoch": 1,
            },
            {"PK": "H#house", "SK": "CONNECTION#c", "rev": 1, "active": True},
        ],
        "Sessions": [
            row("GRANT#old"),
            row("TICKET#old"),
            row("CHANNELGRANT#old"),
            row("VOICE#old"),
            row("IDEMP2#receipt", response={"id": "task"}),
        ],
        "Connections": [row("OAUTH#private", ciphertext="private")],
        "Delivery": [],
    }
    restored = apply_suppressions(tables, ledger)
    assert restored["Domain"][0]["text"] == "" and restored["Domain"][0]["deleted"]
    assert restored["Domain"][1]["active"] is False
    assert len(restored["Sessions"]) == 1 and restored["Sessions"][0]["response"] == {"id": "task"}
    assert restored["Connections"] == []
    cleanup = restored["Delivery"][0]
    assert cleanup["GSI1PK"].startswith("MEMERASE#") and cleanup["GSI1SK"].endswith(mid)
    with pytest.raises(ValueError, match="integrity"):
        apply_suppressions(tables, {**ledger, "sha256": "wrong"})


def test_restored_namespace_blocks_mutating_ingress(harness):
    h = harness
    h.domain.store.transact([put("Sessions", row("RESTORE_FENCE", blocked=True))])
    response = h.client.post("/v1/goals", json={"text": "Buy dinner"}, headers=h.headers())
    assert response.status_code == 503 and response.json()["code"] == "RESTORE_OFFLINE"
    assert h.domain.context("alex", h.h).household["activeTasks"] == 0


def test_release_gate_preserves_meaning_of_existing_approvals_and_actions():
    candidate = {"contracts": CONTRACTS, "restoration": RECOVERY}
    assert compatible(None, candidate)
    assert compatible(candidate, candidate)
    changed = {**candidate, "contracts": {**CONTRACTS, "approvalBinding": "unbound"}}
    with pytest.raises(ValueError, match="approvalBinding"):
        compatible(candidate, changed)
