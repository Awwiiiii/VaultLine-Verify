"""Synthetic rule-level scenarios independent of API and database."""

from decimal import Decimal
from uuid import uuid4

import pytest

from vaultline_api.extraction.contracts import SourceField
from vaultline_api.extraction.normalization import normalize
from vaultline_api.verification.contracts import DocumentEvidence, Tolerances
from vaultline_api.verification.engine import verify

CASE_ID = str(uuid4())
INVOICE = {
    "invoice_number": "SYNTHETIC-INV-001",
    "purchase_order_reference": "SYNTHETIC-PO-001",
    "invoice_date": "2026-10-02",
    "supplier_name": "SYNTHETIC Supplier Ltd",
    "buyer_name": "SYNTHETIC Buyer Ltd",
    "currency": "USD",
    "total_amount": "100.00",
    "line_items.1.description": "SYNTHETIC widgets",
    "line_items.1.quantity": "2",
    "line_items.1.unit_price": "50.00",
    "line_items.1.amount": "100.00",
}
ORDER = {
    "po_number": "SYNTHETIC-PO-001",
    "issue_date": "2026-10-01",
    "supplier_name": "SYNTHETIC Supplier Ltd",
    "buyer_name": "SYNTHETIC Buyer Ltd",
    "currency": "USD",
    "total_amount": "100.00",
    "line_items.1.description": "SYNTHETIC widgets",
    "line_items.1.quantity": "2",
    "line_items.1.unit_price": "50.00",
    "line_items.1.amount": "100.00",
}


def evidence(kind, values, case_id=CASE_ID):
    identifier = str(uuid4())
    source = [
        SourceField(key, value, {"row": index + 2, "column": "value"}, "csv_field_value_v1")
        for index, (key, value) in enumerate(values.items())
    ]
    normalized = normalize(source, kind, identifier)
    return DocumentEvidence(
        document_id=identifier,
        case_id=case_id,
        document_type=kind,
        processing_status="needs_review" if normalized.findings else "extracted",
        checksum="0" * 64,
        fields=normalized.fields,
        line_items=normalized.line_items,
        provenance=[p.model_dump() for p in normalized.provenance],
        validation_findings=[f.model_dump() for f in normalized.findings],
    )


def run(values=None, order=None, tolerances=None):
    invoice = evidence("invoice", {**INVOICE, **(values or {})})
    po = evidence("purchase_order", {**ORDER, **(order or {})})
    return verify(CASE_ID, [invoice, po], [invoice], tolerances)


def rule(result, identifier):
    return [f for f in result.findings if f.rule_id == identifier]


def test_fully_matching():
    result = run()
    assert result.outcome == "passed"
    assert all(f.outcome == "passed" for f in result.findings)
    assert all(o.provenance for f in result.findings for o in f.source_evidence)


@pytest.mark.parametrize(
    "field,value,identifier",
    [
        ("total_amount", "100.01", "invoice_total"),
        ("supplier_name", "SYNTHETIC Supplier Limited", "supplier_match"),
        ("buyer_name", "Other SYNTHETIC buyer", "buyer_match"),
        ("currency", "EUR", "currency_match"),
        ("purchase_order_reference", "OTHER-PO", "po_reference"),
        ("invoice_date", "2026-09-30", "invoice_date"),
        ("line_items.1.quantity", "3", "line_quantity"),
        ("line_items.1.unit_price", "49.99", "line_unit_price"),
    ],
)
def test_discrepancies(field, value, identifier):
    result = run({field: value})
    assert result.outcome == "discrepancy"
    assert rule(result, identifier)[0].outcome == "discrepancy"


@pytest.mark.parametrize("kind", ["invoice", "purchase_order"])
def test_missing_document(kind):
    doc = evidence(kind, INVOICE if kind == "invoice" else ORDER)
    result = verify(CASE_ID, [doc], [doc] if kind == "invoice" else [])
    assert result.outcome == "insufficient_evidence"
    assert any(
        f.rule_id == "required_evidence" and f.outcome == "insufficient_evidence"
        for f in result.findings
    )


def test_conservative_identity():
    assert run({"supplier_name": "  synthetic   supplier LTD "}).outcome == "passed"
    assert (
        rule(run({"supplier_name": "SYNTHETIC Supplier Ltd."}), "supplier_match")[0].outcome
        == "discrepancy"
    )


def test_multiple_invoices_and_duplicates():
    invoice = evidence("invoice", INVOICE)
    second = evidence("invoice", {**INVOICE, "invoice_number": "SYNTHETIC-INV-002"})
    po = evidence("purchase_order", ORDER)
    assert verify(CASE_ID, [invoice, second, po], [invoice, second]).outcome == "passed"
    duplicate = evidence("invoice", INVOICE, case_id=str(uuid4()))
    result = verify(CASE_ID, [invoice, po], [invoice, duplicate])
    assert result.outcome == "discrepancy"
    finding = rule(result, "duplicate_invoice_number")[0]
    assert duplicate.document_id in finding.document_ids
    assert any(o.case_id == duplicate.case_id for o in finding.source_evidence)


def test_missing_provenance():
    invoice = evidence("invoice", INVOICE)
    invoice.provenance = []
    po = evidence("purchase_order", ORDER)
    result = verify(CASE_ID, [invoice, po], [invoice])
    assert result.outcome == "insufficient_evidence"
    assert all(f.outcome != "passed" for f in result.findings if f.rule_id != "required_evidence")


@pytest.mark.parametrize(
    "values", [{"currency": "ZZZ"}, {"total_amount": "1,000"}, {"invoice_date": "yesterday"}]
)
def test_unsupported_and_ambiguous(values):
    assert run(values).outcome == "insufficient_evidence"


def test_decimal_precision_and_tolerance():
    assert (
        rule(run({"total_amount": "0.30"}, {"total_amount": "0.30"}), "invoice_total")[0].outcome
        == "passed"
    )
    assert rule(run({"total_amount": "100.01"}), "invoice_total")[0].outcome == "discrepancy"
    assert (
        rule(
            run({"total_amount": "100.01"}, tolerances=Tolerances(amount=Decimal("0.01"))),
            "invoice_total",
        )[0].outcome
        == "passed"
    )
    with pytest.raises(ValueError):
        Tolerances(amount=Decimal("NaN"))


def test_ambiguous_po_and_line_mapping():
    invoice = evidence("invoice", INVOICE)
    po = evidence("purchase_order", ORDER)
    duplicate_po = evidence("purchase_order", ORDER)
    result = verify(CASE_ID, [invoice, po, duplicate_po], [invoice])
    assert result.outcome == "insufficient_evidence"
    assert rule(result, "po_reference")[0].outcome == "insufficient_evidence"
    po.line_items.append(dict(po.line_items[0]))
    result = verify(CASE_ID, [invoice, po], [invoice])
    assert rule(result, "line_quantity")[0].outcome == "insufficient_evidence"


def test_no_lines_are_not_claimed_as_matches():
    invoice = evidence(
        "invoice", {k: v for k, v in INVOICE.items() if not k.startswith("line_items.")}
    )
    po = evidence("purchase_order", ORDER)
    result = verify(CASE_ID, [invoice, po], [invoice])
    finding = rule(result, "line_quantity")[0]
    assert finding.outcome == "not_applicable"
    assert finding.mandatory is False


def test_unextracted_invoice_elsewhere_keeps_duplicate_uncertainty_optional():
    invoice = evidence("invoice", INVOICE)
    po = evidence("purchase_order", ORDER)
    unknown = DocumentEvidence(
        document_id=str(uuid4()),
        case_id=str(uuid4()),
        document_type="invoice",
        processing_status="uploaded",
        checksum="0" * 64,
    )
    result = verify(CASE_ID, [invoice, po], [invoice, unknown])
    assert result.outcome == "passed"
    finding = rule(result, "duplicate_invoice_number")[0]
    assert finding.outcome == "insufficient_evidence"
    assert finding.mandatory is False
    assert unknown.document_id in finding.document_ids


def test_duplicate_rule_ignores_purchase_orders_even_in_mixed_dataset():
    invoice = evidence("invoice", INVOICE)
    po = evidence("purchase_order", ORDER)
    result = verify(CASE_ID, [invoice, po], [invoice, po])
    assert result.outcome == "passed"
    assert rule(result, "duplicate_invoice_number")[0].document_ids == [invoice.document_id]


def test_rounded_amount_does_not_pass():
    result = run({"total_amount": "100.004"})
    assert result.outcome == "insufficient_evidence"
    assert rule(result, "invoice_total")[0].outcome == "insufficient_evidence"


def test_field_provenance_must_belong_to_document():
    invoice = evidence("invoice", INVOICE)
    po = evidence("purchase_order", ORDER)
    for source in invoice.provenance:
        source["source_document_id"] = str(uuid4())
    result = verify(CASE_ID, [invoice, po], [invoice])
    assert result.outcome == "insufficient_evidence"
    assert rule(result, "supplier_match")[0].outcome == "insufficient_evidence"
