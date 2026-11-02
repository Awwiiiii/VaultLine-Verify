"""Synthetic API → PostgreSQL workflows, isolated from all existing cases and files."""

import csv
from decimal import Decimal
from io import BytesIO, StringIO
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from vaultline_api.core.config import get_settings
from vaultline_api.db.base import Base
from vaultline_api.db.session import get_db_session, get_engine
from vaultline_api.main import app

INVOICE = {
    "invoice_number": "SYNTHETIC-INV-001",
    "invoice_date": "2026-10-02",
    "due_date": "2026-10-31",
    "supplier_name": "SYNTHETIC Supplier Ltd",
    "buyer_name": "SYNTHETIC Buyer Ltd",
    "currency": "USD",
    "purchase_order_reference": "SYNTHETIC-PO-001",
    "subtotal": "100.00",
    "tax": "10.00",
    "total_amount": "110.00",
}
ORDER = {
    "po_number": "SYNTHETIC-PO-001",
    "issue_date": "2026-10-01",
    "supplier_name": "SYNTHETIC Supplier Ltd",
    "buyer_name": "SYNTHETIC Buyer Ltd",
    "currency": "USD",
    "total_amount": "110.00",
}


def fingerprints(connection):
    # Return hashes only, never existing financial values or credentials in test output.
    return {
        table.name: tuple(
            connection.scalars(
                text(f'SELECT md5(row_to_json(t)::text) FROM "{table.name}" t ORDER BY id')
            )
        )
        for table in Base.metadata.sorted_tables
    }


@pytest.fixture(scope="module", autouse=True)
def existing_records_unchanged():
    """Scenario M: compare every existing application row before/after the entire suite."""
    with get_engine().connect() as connection:
        before = fingerprints(connection)
    yield
    with get_engine().connect() as connection:
        assert fingerprints(connection) == before, "Existing application records changed"


@pytest.fixture
def client(tmp_path, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "evidence_storage_dir", tmp_path)
    for name in (
        "verification_amount_tolerance",
        "verification_quantity_tolerance",
        "verification_price_tolerance",
    ):
        monkeypatch.setattr(settings, name, Decimal("0"))
    with get_engine().connect() as connection:
        transaction = connection.begin()
        schema = "synthetic_workflow_" + uuid4().hex
        try:
            connection.execute(text(f'CREATE SCHEMA "{schema}"'))
            # No public fallback: verification cannot see existing user evidence.
            connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            Base.metadata.create_all(connection)

            def sessions():
                with Session(
                    connection, join_transaction_mode="create_savepoint", expire_on_commit=False
                ) as session:
                    yield session

            app.dependency_overrides[get_db_session] = sessions
            with TestClient(app) as test_client:
                yield test_client
            assert set(
                connection.scalars(text("SELECT DISTINCT document_type FROM evidence_documents"))
            ) <= {"invoice", "purchase_order"}
        finally:
            app.dependency_overrides.clear()
            transaction.rollback()
        assert (
            connection.scalar(
                select(text("count(*)"))
                .select_from(text("pg_namespace"))
                .where(text("nspname = :schema")),
                {"schema": schema},
            )
            == 0
        )


def create_case(client):
    response = client.post("/api/v1/cases", json={"counterparty_name": "SYNTHETIC workflow"})
    assert response.status_code == 201
    return "/api/v1/cases/" + response.json()["id"]


def document_bytes(values, extension):
    if extension == "csv":
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["field", "value"])
        writer.writerows(values.items())
        return output.getvalue().encode()
    writer = PdfWriter()
    page = writer.add_blank_page(width=600, height=800)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    stream = DecodedStreamObject()
    stream.set_data(
        (
            "BT /F1 10 Tf 30 760 Td 12 TL "
            + " ".join(f"({key}: {value}) Tj T*" for key, value in values.items())
            + " ET"
        ).encode()
    )
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def upload(client, base, kind, values, extension="csv"):
    response = client.post(
        base + "/documents",
        data={"document_type": kind},
        files={
            "file": (
                f"SYNTHETIC.{extension}",
                document_bytes(values, extension),
                "text/csv" if extension == "csv" else "application/pdf",
            )
        },
    )
    assert response.status_code == 201
    document = response.json()
    assert document["document_type"] == kind
    assert document in client.get(base + "/documents").json()
    extraction = client.post(base + f"/documents/{document['id']}/extract")
    assert extraction.status_code == 200
    assert extraction.json() == client.get(base + f"/documents/{document['id']}/extraction").json()
    assert extraction.json()["result"]["document_type"] == kind
    return document, extraction.json()


def verify(client, base):
    response = client.post(base + "/verify")
    assert response.status_code == 201
    return response.json()


def findings(run, rule):
    return [finding for finding in run["findings"] if finding["rule_id"] == rule]


@pytest.mark.parametrize("extension", ["csv", "pdf"])
def test_a_matching_and_j_saved_history(client, extension):
    base = create_case(client)
    for kind, values in [("invoice", INVOICE), ("purchase_order", ORDER)]:
        document, extraction = upload(client, base, kind, values, extension)
        assert extraction["status"] == "extracted"
        assert extraction["result"]["findings"] == []
        assert extraction["result"]["fields"] == values
        for source in extraction["result"]["provenance"]:
            assert source["source_document_id"] == document["id"]
            assert source["original_value"] == (
                (" " if extension == "pdf" else "") + values[source["field_name"]]
            )
            assert source["source_location"] == (
                {"page": 1}
                if extension == "pdf"
                else {"row": list(values).index(source["field_name"]) + 2, "column": "value"}
            )
    first = verify(client, base)
    assert first["outcome"] == "passed"
    assert all(f["outcome"] == "passed" for f in first["findings"] if f["mandatory"])
    assert all(
        p["id"] for f in first["findings"] for o in f["source_evidence"] for p in o["provenance"]
    )
    second = verify(client, base)
    assert second["id"] != first["id"]
    assert second["findings"] == first["findings"]
    # New contradictory evidence changes only future runs.
    upload(client, base, "invoice", INVOICE)
    assert verify(client, base)["outcome"] == "discrepancy"
    assert client.get(base + f"/verifications/{first['id']}").json() == first
    assert client.get(base + "/verifications").json()["total"] == 3


def test_b_separate_cases_do_not_share_po(client):
    base, other = create_case(client), create_case(client)
    upload(client, base, "invoice", INVOICE)
    po, _ = upload(client, other, "purchase_order", ORDER)
    run = verify(client, base)
    assert run["outcome"] == "insufficient_evidence"
    assert all(po["id"] not in f["document_ids"] for f in run["findings"])
    assert findings(run, "po_reference")[0]["outcome"] == "insufficient_evidence"


def test_c_mislabeled_po_stays_invoice(client):
    base = create_case(client)
    upload(client, base, "invoice", INVOICE)
    document, extraction = upload(client, base, "invoice", ORDER)
    assert extraction["status"] == "needs_review"
    assert {
        f["field"] for f in extraction["result"]["findings"] if f["code"] == "unsupported_field"
    } == {"po_number", "issue_date"}
    assert "po_number" not in extraction["result"]["fields"]
    assert any(
        p["field_name"] == "po_number" and p["original_value"] == ORDER["po_number"]
        for p in extraction["result"]["provenance"]
    )
    run = verify(client, base)
    assert run["outcome"] == "insufficient_evidence"
    assert any(
        f["explanation"] == "No purchase_order document exists in this case."
        for f in findings(run, "required_evidence")
    )
    assert (
        next(d for d in client.get(base + "/documents").json() if d["id"] == document["id"])[
            "document_type"
        ]
        == "invoice"
    )


@pytest.mark.parametrize(
    "changes,rule",
    [
        ({"subtotal": "101.00", "total_amount": "111.00"}, "invoice_total"),
        ({"supplier_name": "SYNTHETIC Different supplier"}, "supplier_match"),
        ({"buyer_name": "SYNTHETIC Different buyer"}, "buyer_match"),
        ({"currency": "EUR"}, "currency_match"),
        ({"purchase_order_reference": "SYNTHETIC-OTHER"}, "po_reference"),
    ],
)
def test_d_through_h_discrepancies(client, changes, rule):
    base = create_case(client)
    upload(client, base, "invoice", {**INVOICE, **changes})
    upload(client, base, "purchase_order", ORDER)
    run = verify(client, base)
    assert run["outcome"] == "discrepancy"
    assert findings(run, rule)[0]["outcome"] == "discrepancy"


def test_i_missing_po(client):
    base = create_case(client)
    upload(client, base, "invoice", INVOICE)
    assert verify(client, base)["outcome"] == "insufficient_evidence"


def test_k_duplicates_across_cases_and_unresolved_dataset(client):
    base, other = create_case(client), create_case(client)
    upload(client, base, "invoice", INVOICE)
    upload(client, base, "purchase_order", ORDER)
    # A PO with the same identifier is not an invoice-number duplicate.
    upload(client, other, "purchase_order", {**ORDER, "po_number": INVOICE["invoice_number"]})
    assert verify(client, base)["outcome"] == "passed"
    unknown, _ = upload(client, other, "invoice", {"invoice_number": ""})
    run = verify(client, base)
    assert run["outcome"] == "passed"
    finding = findings(run, "duplicate_invoice_number")[0]
    assert finding["outcome"] == "insufficient_evidence"
    assert finding["mandatory"] is False
    assert unknown["id"] in finding["document_ids"]
    duplicate, _ = upload(client, other, "invoice", INVOICE)
    run = verify(client, base)
    assert run["outcome"] == "discrepancy"
    finding = findings(run, "duplicate_invoice_number")[0]
    assert finding["outcome"] == "discrepancy"
    assert duplicate["id"] in finding["document_ids"]
    assert any(o["case_id"] == other.rsplit("/", 1)[1] for o in finding["source_evidence"])


@pytest.mark.parametrize(
    "kind,field,value",
    [
        ("invoice", "invoice_number", ""),
        ("invoice", "invoice_date", "yesterday"),
        ("invoice", "total_amount", "NaN"),
        ("purchase_order", "po_number", ""),
        ("purchase_order", "issue_date", "2026-99-99"),
        ("purchase_order", "currency", "ZZZ"),
    ],
)
def test_l_missing_invalid_fields(client, kind, field, value):
    base = create_case(client)
    for document_type, values in [("invoice", INVOICE), ("purchase_order", ORDER)]:
        _, extraction = upload(
            client,
            base,
            document_type,
            {**values, field: value} if document_type == kind else values,
        )
        if document_type == kind:
            assert extraction["status"] == "needs_review"
            assert extraction["result"]["fields"][field] is None
    assert verify(client, base)["outcome"] == "insufficient_evidence"


@pytest.mark.parametrize("kind", [None, "po", "", "bank_statement"])
def test_upload_requires_supported_explicit_type(client, kind):
    base = create_case(client)
    response = client.post(
        base + "/documents",
        data={} if kind is None else {"document_type": kind},
        files={"file": ("SYNTHETIC.csv", document_bytes(ORDER, "csv"), "text/csv")},
    )
    assert response.status_code == 422
    assert client.get(base + "/documents").json() == []
