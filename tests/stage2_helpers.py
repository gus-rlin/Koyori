"""Synthetic API recipe helpers; all grants are issued by the existing test issuer."""

from uuid import uuid4

from koyori.stage2_contracts import ApprovalCreate, BudgetPut, MemoryWrite, QuoteCreate


def memory(h, **kwargs):
    body = MemoryWrite(kind="exchange", text="Breakfast tomorrow", **kwargs).model_dump()
    grant = h.grant("POST /v1/memories", body) if body["visibility"] == "household" else None
    response = h.client.post("/v1/memories", json=body, headers=h.headers(grant=grant))
    assert response.status_code == 201, response.text
    return response.json()


def commerce(h, *, limit=10000, per_action=10000, approval=False):
    response = h.client.post("/v1/connections/simulated", json={}, headers=h.headers())
    assert response.status_code == 201, response.text
    connection = response.json()
    body = BudgetPut(
        limitMinor=limit, perActionMinor=per_action, approvalRequired=approval
    ).model_dump()
    grant = h.grant("PUT /v1/budget", body, version=0)
    response = h.client.put("/v1/budget", json=body, headers=h.headers(version=0, grant=grant))
    assert response.status_code == 200, response.text
    return connection


def quote(
    h, connection, *, sku="milk", quantity=1, intention=None, operation="create", target=None
):
    body = QuoteCreate(
        connectionId=connection["id"],
        capability="commerce.meals" if "meal" in sku else "commerce.groceries",
        intentionId=intention or uuid4().hex,
        operation=operation,
        targetActionId=target,
        lines=[] if operation == "cancel" else [{"sku": sku, "quantity": quantity}],
        deliveryAt=h.clock() + 3600,
    ).model_dump()
    response = h.client.post("/v1/quotes", json=body, headers=h.headers())
    assert response.status_code == 201, response.text
    return response.json()


def approve(h, q):
    body = ApprovalCreate(quoteId=q["id"]).model_dump()
    grant = h.grant("POST /v1/approvals", body)
    response = h.client.post("/v1/approvals", json=body, headers=h.headers(grant=grant))
    assert response.status_code == 201, response.text
    return response.json()


def reserve(h, q, approval=None, headers=None):
    response = h.client.post(
        "/v1/actions",
        json={"quoteId": q["id"], "approvalId": approval["id"] if approval else None},
        headers=headers or h.headers(),
    )
    assert response.status_code == 202, response.text
    return response.json()
