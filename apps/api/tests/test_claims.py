"""Synthetic claim workflows in rollback-only PostgreSQL schemas."""

from uuid import uuid4

import pytest
from test_invoice_po_workflow import (
    INVOICE,
    create_case,
    upload,
)
from test_invoice_po_workflow import client as workflow_client

from vaultline_api.claims.engine import detect

client = workflow_client


def record(client, base, doc, **changes):
    return client.post(
        base + "/claims",
        json={
            "invoice_document_id": doc["id"],
            "claim_reference": "SYNTHETIC-" + uuid4().hex,
            "lender": "SYNTHETIC lender",
            "amount": "60.00",
            "currency": "USD",
            "status": "active",
            **changes,
        },
    )


def categories(client, base):
    response = client.get(base + "/claim-conflicts")
    assert response.status_code == 200
    return {f["category"] for f in response.json()["findings"]}


def test_records_and_status_history(client):
    base = create_case(client)
    doc, _ = upload(client, base, "invoice", INVOICE)
    first = record(client, base, doc)
    assert first.status_code == 201
    first = first.json()
    assert categories(client, base) == {"no_conflict_found"}
    assert record(client, base, doc, claim_reference=first["claim_reference"]).status_code == 409
    second = record(client, base, doc).json()
    assert categories(client, base) == {"confirmed_duplicate_records", "aggregate_exceeds_invoice"}
    assert client.get("/api/v1/claims/" + first["id"]).json() == first
    endpoint = "/api/v1/claims/" + second["id"] + "/status"
    changed = client.patch(endpoint, json={"status": "released"}).json()
    assert len(changed["status_history"]) == 2
    assert changed["evidence_snapshot"] == second["evidence_snapshot"]
    assert client.patch(endpoint, json={"status": "active"}).status_code == 409
    assert categories(client, base) == {"no_conflict_found"}
    assert client.get(base + "/claims?limit=1").json()["total"] == 2
    assert len(client.get(base + "/claims?limit=1").json()["items"]) == 1


@pytest.mark.parametrize("status", ["active", "proposed", "released", "cancelled"])
def test_cross_case_and_lenders(client, status):
    base, other = create_case(client), create_case(client)
    doc, _ = upload(client, base, "invoice", INVOICE)
    second, _ = upload(client, other, "invoice", INVOICE)
    assert record(client, base, doc).status_code == 201
    assert (
        record(client, other, second, lender="SYNTHETIC other lender", status=status).status_code
        == 201
    )
    found = categories(client, base)
    assert ("potential_competing_claims" in found) == (status == "active")
    assert ("aggregate_exceeds_invoice" in found) == (status == "active")
    assert len(client.get(base + "/claims").json()["items"]) == 1
    assert record(client, base, second).status_code == 404


@pytest.mark.parametrize(
    "changes",
    [
        {"amount": "-1"},
        {"amount": "NaN"},
        {"amount": 1.2},
        {"amount": "1.001"},
        {"currency": "ZZZ"},
        {"status": "approved"},
        {"lender": ""},
    ],
)
def test_invalid_input(client, changes):
    base = create_case(client)
    doc, _ = upload(client, base, "invoice", INVOICE)
    assert record(client, base, doc, **changes).status_code == 422


def test_missing_currency_and_proposed(client):
    base = create_case(client)
    doc, _ = upload(client, base, "invoice", {"invoice_number": "SYNTHETIC"})
    assert record(client, base, doc).status_code == 201
    assert "insufficient_evidence" in categories(client, base)
    other = create_case(client)
    doc, _ = upload(client, other, "invoice", INVOICE)
    assert record(client, other, doc, currency="EUR", status="proposed").status_code == 201
    assert categories(client, other) == {"insufficient_evidence"}
    assert client.get("/api/v1/claims/" + str(uuid4())).status_code == 404
    assert client.get("/api/v1/claims/invalid").status_code == 422
    assert client.get(base + "/claims?limit=0").status_code == 422


def test_pure_engine_empty_dataset():
    assert detect(str(uuid4()), [])[0]["category"] == "no_conflict_found"


@pytest.mark.parametrize(
    "field,value",
    [
        ("invoice_number", "SYNTHETIC-other"),
        ("supplier_name", "SYNTHETIC Supplier Ltd."),
        ("buyer_name", "SYNTHETIC other"),
        ("currency", "EUR"),
        ("total_amount", "120.00"),
    ],
)
def test_exact_identity_only(client, field, value):
    base, other = create_case(client), create_case(client)
    doc, _ = upload(client, base, "invoice", INVOICE)
    second, _ = upload(client, other, "invoice", {**INVOICE, field: value})
    record(client, base, doc)
    record(client, other, second, currency="EUR" if field == "currency" else "USD")
    assert "potential_competing_claims" not in categories(client, base)


def test_proposed_activation_and_wrong_document(client):
    base = create_case(client)
    doc, _ = upload(client, base, "invoice", INVOICE)
    claim = record(client, base, doc, status="proposed").json()
    assert categories(client, base) == {"insufficient_evidence"}
    assert (
        client.patch(
            "/api/v1/claims/" + claim["id"] + "/status", json={"status": "active"}
        ).status_code
        == 200
    )
    assert categories(client, base) == {"no_conflict_found"}
    from test_invoice_po_workflow import ORDER

    po, _ = upload(client, base, "purchase_order", ORDER)
    assert record(client, base, po).status_code == 422


def test_pure_conflicts_require_full_identity_and_provenance():
    from test_verification_engine import evidence

    first_doc = evidence("invoice", INVOICE)
    second_doc = evidence("invoice", {**INVOICE, "supplier_name": "  synthetic   supplier LTD "})

    def assertion(doc, lender):
        return {
            "id": str(uuid4()),
            "case_id": doc.case_id,
            "invoice_document_id": doc.document_id,
            "evidence_snapshot": doc.model_dump(),
            "lender": lender,
            "amount": "60.00",
            "currency": "USD",
            "status": "active",
        }

    first, second = assertion(first_doc, "SYNTHETIC A"), assertion(second_doc, "SYNTHETIC B")
    result = detect(first_doc.case_id, [first, second])
    assert {f["category"] for f in result} == {
        "potential_competing_claims",
        "aggregate_exceeds_invoice",
    }
    second["evidence_snapshot"]["provenance"] = []
    result = detect(first_doc.case_id, [first, second])
    assert "potential_competing_claims" not in {f["category"] for f in result}
    assert "insufficient_evidence" in {f["category"] for f in result}
