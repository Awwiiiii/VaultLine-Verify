"""Synthetic deterministic financial extraction fixtures and PostgreSQL persistence tests."""

from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from vaultline_api.extraction.contracts import SourceField
from vaultline_api.extraction.fields import extract_fields
from vaultline_api.extraction.normalization import normalize
from vaultline_api.extraction.parsing import parse_document

INVOICE = {
    "invoice_number": "SYNTHETIC-INV-001",
    "invoice_date": "2026-10-01",
    "due_date": "2026-10-31",
    "supplier_name": "SYNTHETIC supplier",
    "buyer_name": "SYNTHETIC buyer",
    "currency": "USD",
    "subtotal": "100.00",
    "tax": "10.00",
    "total_amount": "110.00",
    "payment_terms": "Net 30",
    "purchase_order_reference": "SYNTHETIC-PO-001",
    "line_items.1.description": "Synthetic goods",
    "line_items.1.quantity": "2",
    "line_items.1.unit_price": "50.00",
    "line_items.1.amount": "100.00",
}
PO = {
    "po_number": "SYNTHETIC-PO-001",
    "issue_date": "2026-10-01",
    "buyer_name": "SYNTHETIC buyer",
    "supplier_name": "SYNTHETIC supplier",
    "currency": "JPY",
    "total_amount": "100",
    "line_items.1.description": "Synthetic goods",
    "line_items.1.quantity": "2",
    "line_items.1.unit_price": "50",
    "line_items.1.amount": "100",
}


def sources(values):
    return [
        SourceField(k, v, {"row": i + 2, "column": "value"}, "csv_field_value_v1")
        for i, (k, v) in enumerate(values.items())
    ]


@pytest.mark.parametrize("kind,values", [("invoice", INVOICE), ("purchase_order", PO)])
def test_valid_normalization(kind, values):
    result = normalize(sources(values), kind, str(uuid4()))
    assert result.findings == []
    assert result.fields["total_amount"] == values["total_amount"]
    assert result.line_items[0]["quantity"] == "2"


@pytest.mark.parametrize(
    "change,code",
    [
        ({"invoice_date": "01/02/2026"}, "invalid_value"),
        ({"total_amount": "NaN"}, "invalid_value"),
        ({"total_amount": "-10.00"}, "invalid_value"),
        ({"total_amount": "109.00"}, "inconsistent_total"),
        ({"currency": "ZZZ"}, "invalid_value"),
        ({"total_amount": "110.005"}, "rounded"),
        ({"invoice_number": ""}, "required"),
        ({"total_amount": "1,000.00"}, "invalid_value"),
    ],
)
def test_validation_findings(change, code):
    result = normalize(sources({**INVOICE, **change}), "invoice", str(uuid4()))
    assert code in {f.code for f in result.findings}


def test_duplicate_fields():
    result = normalize(
        sources(INVOICE)
        + [
            SourceField("total_amount", "999", {"row": 99, "column": "value"}, "csv_field_value_v1")
        ],
        "invoice",
        str(uuid4()),
    )
    assert result.fields["total_amount"] is None
    assert len([p for p in result.provenance if p.field_name == "total_amount"]) == 2
    assert "duplicate" in {f.code for f in result.findings}


def csv_bytes(values):
    return ("field,value\n" + "\n".join(f"{k},{v}" for k, v in values.items())).encode()


def pdf_bytes():
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
            + " ".join(f"({k}: {v}) Tj T*" for k, v in INVOICE.items())
            + " ET"
        ).encode()
    )
    page[NameObject("/Contents")] = writer._add_object(stream)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_pdf_page_provenance(tmp_path):
    path = tmp_path / "synthetic.pdf"
    path.write_bytes(pdf_bytes())
    result = normalize(extract_fields(parse_document(path)), "invoice", str(uuid4()))
    assert result.findings == []
    assert all(p.source_location == {"page": 1} for p in result.provenance)


def upload(client, case, content, kind="invoice", extension="csv"):
    response = client.post(
        f"/api/v1/cases/{case['id']}/documents",
        data={"document_type": kind},
        files={
            "file": (
                f"synthetic.{extension}",
                content,
                "text/csv" if extension == "csv" else "application/pdf",
            )
        },
    )
    assert response.status_code == 201
    return response.json()["id"]


@pytest.mark.parametrize("kind,values", [("invoice", INVOICE), ("purchase_order", PO)])
def test_persistence_and_repeated_requests(client, case, kind, values):
    document_id = upload(client, case, csv_bytes(values), kind)
    base = f"/api/v1/cases/{case['id']}/documents/{document_id}"
    response = client.post(base + "/extract")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "extracted"
    assert data["result"]["fields"]["total_amount"] == values["total_amount"]
    provenance = data["result"]["provenance"][0]
    assert provenance["source_document_id"] == document_id
    assert provenance["source_location"] == {"row": 2, "column": "value"}
    assert provenance["original_value"] == next(iter(values.values()))
    assert client.get(base + "/extraction").json() == data
    assert client.post(base + "/extract").json() == data
    assert (
        client.get(f"/api/v1/cases/{case['id']}/documents").json()[0]["processing_status"]
        == "extracted"
    )


def test_pdf_api(client, case):
    document_id = upload(client, case, pdf_bytes(), extension="pdf")
    response = client.post(f"/api/v1/cases/{case['id']}/documents/{document_id}/extract")
    assert response.json()["status"] == "extracted"


def test_failure_recovery_preserves_evidence(client, case, tmp_path):
    document_id = upload(client, case, csv_bytes(INVOICE))
    path = next(tmp_path.iterdir())
    original = path.read_bytes()
    base = f"/api/v1/cases/{case['id']}/documents/{document_id}"
    with patch(
        "vaultline_api.services.extraction.parse_document",
        side_effect=ValueError("synthetic internal error"),
    ):
        response = client.post(base + "/extract").json()
        assert response["status"] == "failed"
        assert "synthetic internal error" not in response["error"]
    assert path.read_bytes() == original
    assert client.post(base + "/extract").json()["status"] == "extracted"


def test_needs_review_and_case_scope(client, case):
    document_id = upload(client, case, csv_bytes({"invoice_number": "SYNTHETIC"}))
    base = f"/api/v1/cases/{case['id']}/documents/{document_id}"
    assert client.get(base + "/extraction").status_code == 404
    response = client.post(base + "/extract").json()
    assert response["status"] == "needs_review"
    assert any(f["code"] == "required" for f in response["result"]["findings"])
    assert (
        client.get(f"/api/v1/cases/{uuid4()}/documents/{document_id}/extraction").status_code == 404
    )


def test_scanned_pdf_is_not_supported(client, case, tmp_path):
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    buffer = BytesIO()
    writer.write(buffer)
    document_id = upload(client, case, buffer.getvalue(), extension="pdf")
    original = next(tmp_path.iterdir()).read_bytes()
    response = client.post(f"/api/v1/cases/{case['id']}/documents/{document_id}/extract")
    assert response.json()["status"] == "failed"
    assert next(tmp_path.iterdir()).read_bytes() == original


def test_integrity_failure(client, case, tmp_path):
    document_id = upload(client, case, csv_bytes(INVOICE))
    path = next(tmp_path.iterdir())
    path.chmod(0o600)
    path.write_bytes(b"synthetic tampering")
    response = client.post(f"/api/v1/cases/{case['id']}/documents/{document_id}/extract")
    assert response.json()["status"] == "failed"
    assert response.json()["result"]["provenance"] == []
