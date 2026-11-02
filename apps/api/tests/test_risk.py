"""Synthetic deterministic indicators with real FastAPI/PostgreSQL, never a live provider."""

import json
from uuid import uuid4

import pytest
from test_claims import record
from test_invoice_po_workflow import INVOICE, ORDER, create_case, upload, verify
from test_invoice_po_workflow import client as workflow_client

from vaultline_api.risk.contracts import RiskInputs
from vaultline_api.risk.engine import assess

client = workflow_client


def assessment(client, base):
    response = client.get(base + "/risk-assessment")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    result = response.json()
    assert result["human_review_required"] is True
    assert "score" not in result and "probability" not in result
    inputs = RiskInputs.model_validate(result["input_snapshot"])
    assert assess(inputs).model_dump(mode="json") == {
        k: v for k, v in result.items() if k != "assessed_at"
    }
    refs = {s["id"] for s in result["sources"]}
    assert all(ref in refs for i in result["indicators"] for ref in i["source_refs"])
    assert any(i["category"] == "unknown_external_financing" for i in result["indicators"])
    return result


def pair(client, values=None):
    base = create_case(client)
    invoice, _ = upload(client, base, "invoice", values or INVOICE)
    upload(client, base, "purchase_order", ORDER)
    return base, invoice


def test_clean_current_and_history_unchanged(client):
    base, invoice = pair(client)
    run = verify(client, base)
    first = assessment(client, base)
    assert first["assessment_status"] == "no_recorded_discrepancy"
    assert first["input_snapshot"]["freshness"] == "current"
    assert first["input_snapshot"]["verification"]["id"] == run["id"]
    assert first["indicators"] == assessment(client, base)["indicators"]
    assert client.get(base + "/verifications/" + run["id"]).json() == run
    assert client.get(base + "/verifications").json()["total"] == 1
    assert client.get(base + "/investigations").json()["total"] == 0
    assert client.get(base + "/claims").json()["total"] == 0


@pytest.mark.parametrize(
    "changes,rule",
    [
        ({"subtotal": "101.00", "total_amount": "111.00"}, "invoice_total"),
        ({"supplier_name": "SYNTHETIC Different"}, "supplier_match"),
        ({"currency": "EUR"}, "currency_match"),
    ],
)
def test_discrepancy_references_exact_saved_finding(client, changes, rule):
    base, _ = pair(client, {**INVOICE, **changes})
    run = verify(client, base)
    result = assessment(client, base)
    assert result["assessment_status"] == "review_findings_present"
    indicator = next(
        i for i in result["indicators"] if i["title"] == "Recorded discrepancy: " + rule
    )
    source = next(s for s in result["sources"] if s["id"] == indicator["source_refs"][0])
    assert source["payload"] == next(f for f in run["findings"] if f["rule_id"] == rule)
    assert all(
        p["source_document_id"] == o["document_id"]
        for o in source["payload"]["source_evidence"]
        for p in o["provenance"]
    )


def test_missing_and_unresolved_fields_do_not_imply_fraud(client):
    base = create_case(client)
    result = assessment(client, base)
    assert result["assessment_status"] == "insufficient_evidence"
    assert result["input_snapshot"]["freshness"] == "missing"
    upload(client, base, "invoice", {"invoice_number": "SYNTHETIC-incomplete"})
    verify(client, base)
    result = assessment(client, base)
    assert result["assessment_status"] == "insufficient_evidence"
    assert "discrepancy" not in {i["category"] for i in result["indicators"]}


def test_stale_document_and_dataset_coverage(client):
    base, _ = pair(client)
    old = verify(client, base)
    # A new invoice elsewhere changes the dataset used by duplicate checking.
    other = create_case(client)
    upload(client, other, "invoice", {**INVOICE, "invoice_number": "SYNTHETIC-UNRELATED"})
    stale = assessment(client, base)
    assert stale["input_snapshot"]["freshness"] == "stale"
    assert stale["assessment_status"] == "insufficient_evidence"
    assert "SYNTHETIC-UNRELATED" not in json.dumps(stale)
    assert client.get(base + "/verifications/" + old["id"]).json() == old
    verify(client, base)
    assert assessment(client, base)["input_snapshot"]["freshness"] == "current"
    document, _ = upload(client, base, "purchase_order", {**ORDER, "po_number": "SYNTHETIC-NEW-PO"})
    assert assessment(client, base)["input_snapshot"]["freshness"] == "stale"


def test_claim_conflicts_and_released_claims(client):
    base, invoice = pair(client)
    other, other_invoice = pair(client)
    first = record(client, base, invoice, amount="70.00").json()
    second = record(
        client, other, other_invoice, amount="70.00", lender="SYNTHETIC other lender"
    ).json()
    verify(client, base)
    result = assessment(client, base)
    categories = {i["category"] for i in result["indicators"]}
    assert {"potential_claim_conflict", "aggregate_claim_excess"} <= categories
    refs = next(i for i in result["indicators"] if i["category"] == "potential_claim_conflict")[
        "source_refs"
    ]
    assert {"claim:" + first["id"], "claim:" + second["id"]} <= set(refs)
    client.patch("/api/v1/claims/" + second["id"] + "/status", json={"status": "released"})
    after = assessment(client, base)
    assert "potential_claim_conflict" not in {i["category"] for i in after["indicators"]}
    assert "aggregate_claim_excess" not in {i["category"] for i in after["indicators"]}
    # The previously returned snapshot remains reproducible after a status change.
    assert (
        assess(RiskInputs.model_validate(result["input_snapshot"])).model_dump(mode="json")[
            "indicators"
        ]
        == result["indicators"]
    )


def test_proposed_and_duplicate_assertions(client):
    base, invoice = pair(client)
    proposed = record(client, base, invoice, status="proposed", amount="10.00").json()
    verify(client, base)
    result = assessment(client, base)
    assert result["assessment_status"] == "insufficient_evidence"
    assert not any(i["category"] == "potential_claim_conflict" for i in result["indicators"])
    client.patch("/api/v1/claims/" + proposed["id"] + "/status", json={"status": "cancelled"})
    record(client, base, invoice, amount="10.00")
    record(client, base, invoice, amount="10.00")
    result = assessment(client, base)
    assert any(i["category"] == "duplicate_assertions" for i in result["indicators"])


def test_optional_gaps_and_case_isolation(client):
    base, _ = pair(client)
    other = create_case(client)
    # An unrelated unresolved invoice makes the duplicate comparison inconclusive.
    upload(client, other, "invoice", {"invoice_number": ""})
    run = verify(client, base)
    assert run["outcome"] == "passed"
    result = assessment(client, base)
    assert result["assessment_status"] == "insufficient_evidence"
    assert any(i["category"] == "unchecked_comparison" for i in result["indicators"])
    isolated = assessment(client, other)
    assert isolated["input_snapshot"]["verification"] is None
    assert client.get(f"/api/v1/cases/{uuid4()}/risk-assessment").status_code == 404
    assert client.get("/api/v1/cases/invalid/risk-assessment").status_code == 422


def test_replay_rejects_contradictory_case_and_freshness(client):
    base, _ = pair(client)
    verify(client, base)
    snapshot = assessment(client, base)["input_snapshot"]
    snapshot["case_id"] = str(uuid4())
    with pytest.raises(ValueError):
        RiskInputs.model_validate(snapshot)
    snapshot["case_id"] = snapshot["verification"]["case_id"]
    snapshot["freshness"] = "stale"
    with pytest.raises(ValueError):
        RiskInputs.model_validate(snapshot)


def test_pure_assessment_rejects_unsupported_claim_reference(client):
    base, invoice = pair(client)
    record(client, base, invoice, amount="10.00")
    record(client, base, invoice, amount="10.00")
    verify(client, base)
    inputs = RiskInputs.model_validate(assessment(client, base)["input_snapshot"])
    inputs.claims = []
    with pytest.raises(ValueError, match="unsupported evidence"):
        assess(inputs)


def test_extraction_changes_invalidate_old_coverage(client):
    from test_invoice_po_workflow import document_bytes

    base, _ = pair(client)
    # Upload an additional invoice but do not extract it yet.
    response = client.post(
        base + "/documents",
        data={"document_type": "invoice"},
        files={
            "file": (
                "SYNTHETIC-later.csv",
                document_bytes({**INVOICE, "invoice_number": "SYNTHETIC-LATER"}, "csv"),
                "text/csv",
            )
        },
    )
    identifier = response.json()["id"]
    old = verify(client, base)
    assert assessment(client, base)["input_snapshot"]["freshness"] == "current"
    assert client.post(base + f"/documents/{identifier}/extract").json()["status"] == "extracted"
    result = assessment(client, base)
    assert result["input_snapshot"]["freshness"] == "stale"
    assert result["assessment_status"] == "insufficient_evidence"
    assert client.get(base + "/verifications/" + old["id"]).json() == old


def test_get_preserves_existing_investigation_and_does_not_call_provider(client, monkeypatch):
    from vaultline_api.investigations.providers import MockAIProvider, get_provider
    from vaultline_api.main import app

    provider = MockAIProvider()
    app.dependency_overrides[get_provider] = lambda: provider
    base, _ = pair(client)
    verify(client, base)
    investigation = client.post(base + "/investigations").json()

    def forbidden(package):
        raise AssertionError("Assessment must not call any AI provider")

    monkeypatch.setattr(provider, "generate", forbidden)
    assessment(client, base)
    assert client.get(base + "/investigations/" + investigation["id"]).json() == investigation
