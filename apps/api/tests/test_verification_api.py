"""Synthetic PostgreSQL integration: case scoping, append-only runs, stored snapshots."""

from uuid import uuid4

from test_verification_engine import INVOICE, ORDER


def add_document(client, case, kind, values):
    content = ("field,value\n" + "\n".join(f"{k},{v}" for k, v in values.items())).encode()
    response = client.post(
        f"/api/v1/cases/{case['id']}/documents",
        data={"document_type": kind},
        files={"file": ("synthetic.csv", content, "text/csv")},
    )
    assert response.status_code == 201
    identifier = response.json()["id"]
    response = client.post(f"/api/v1/cases/{case['id']}/documents/{identifier}/extract")
    assert response.json()["status"] == "extracted"
    return identifier


def test_repeated_runs_and_history(client, case):
    values = {**INVOICE, "invoice_number": f"SYNTHETIC-{uuid4().hex}"}
    invoice_id = add_document(client, case, "invoice", values)
    po_id = add_document(client, case, "purchase_order", ORDER)
    base = f"/api/v1/cases/{case['id']}"
    first = client.post(base + "/verify")
    assert first.status_code == 201
    first = first.json()
    assert first["rule_set_version"] == "vaultline.cross-document.v1.1"
    assert first["tolerances"] == {"amount": "0", "quantity": "0", "unit_price": "0"}
    assert (
        next(f for f in first["findings"] if f["rule_id"] == "po_reference")["outcome"] == "passed"
    )
    compared = next(f for f in first["findings"] if f["rule_id"] == "invoice_total")
    assert set(compared["document_ids"]) == {invoice_id, po_id}
    assert all(
        p["id"] for observation in compared["source_evidence"] for p in observation["provenance"]
    )
    repeated = client.post(base + "/verify").json()
    assert repeated["id"] != first["id"]
    assert repeated["findings"] == first["findings"]
    add_document(client, case, "invoice", values)
    latest = client.post(base + "/verify").json()
    assert latest["outcome"] == "discrepancy"
    assert any(
        f["rule_id"] == "duplicate_invoice_number" and f["outcome"] == "discrepancy"
        for f in latest["findings"]
    )
    assert client.get(base + f"/verifications/{first['id']}").json() == first
    history = client.get(base + "/verifications?limit=2").json()
    assert history["total"] == 3
    assert len(history["items"]) == 2
    assert len(client.get(base + "/verifications?limit=2&offset=2").json()["items"]) == 1
    other = client.post("/api/v1/cases", json={"counterparty_name": "SYNTHETIC other case"}).json()
    assert client.get(f"/api/v1/cases/{other['id']}/verifications/{first['id']}").status_code == 404


def test_empty_case_and_invalid_scoping(client, case):
    response = client.post(f"/api/v1/cases/{case['id']}/verify")
    assert response.json()["outcome"] == "insufficient_evidence"
    assert client.post(f"/api/v1/cases/{uuid4()}/verify").status_code == 404
    assert client.post("/api/v1/cases/not-a-uuid/verify").status_code == 422
    assert client.get(f"/api/v1/cases/{case['id']}/verifications/{uuid4()}").status_code == 404
