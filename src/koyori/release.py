"""Compatibility gate; rollback cannot reverse commercial effects."""

CONTRACTS = {
    "domainSchema": "1.0",
    "eventSchema": "1.0",
    "approvalBinding": "exact-body-and-revision-v1",
    "commerceIntent": "stable-business-id-v1",
    "mcpProtocol": "2025-11-25",
    "voiceProtocol": "1.0",
}
RECOVERY = "offline-current-suppression-ledger-and-provider-reconciliation"


def compatible(previous, candidate):
    for key, value in CONTRACTS.items():
        if candidate.get("contracts", {}).get(key) != value:
            raise ValueError(f"Unsupported release contract: {key}")
        if previous and previous.get("contracts", {}).get(key) != value:
            raise ValueError(f"Migration review required: {key}")
    if candidate.get("restoration") != RECOVERY:
        raise ValueError("Recovery contract is missing")
    return True
