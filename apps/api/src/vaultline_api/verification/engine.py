"""Conservative document comparisons. Outcomes never establish legal identity or rights."""

import re
from datetime import date
from decimal import Decimal, localcontext

from vaultline_api.extraction.normalization import MINOR_UNITS
from vaultline_api.verification.contracts import (
    DocumentEvidence,
    Finding,
    Observation,
    Outcome,
    Tolerances,
    VerificationResult,
)


def conservative_text(value: str) -> str:
    """Case and whitespace only; retain punctuation, suffixes and all substantive characters."""
    return " ".join(value.split()).casefold()


def observe(document: DocumentEvidence, field: str, value: str | None = None) -> Observation:
    if value is None:
        value = document.fields.get(field)
    return Observation(
        document_id=document.document_id,
        case_id=document.case_id,
        field_name=field,
        value=value,
        provenance=[
            p
            for p in document.provenance
            if p.get("field_name") == field and p.get("source_document_id") == document.document_id
        ],
    )


def usable(observation: Observation) -> bool:
    return (
        isinstance(observation.value, str)
        and bool(observation.value.strip())
        and len(observation.provenance) == 1
        and observation.provenance[0].get("validation_status") == "valid"
        and observation.provenance[0].get("normalized_value") == observation.value
    )


def number(observation: Observation) -> Decimal | None:
    value = observation.value
    if not usable(observation) or not re.fullmatch(r"\d{1,18}(?:\.\d{1,8})?", value or ""):
        return None
    return Decimal(value)


def iso_date(observation: Observation) -> date | None:
    if not usable(observation) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", observation.value or ""):
        return None
    try:
        return date.fromisoformat(observation.value)
    except ValueError:
        return None


def overall(findings: list[Finding]) -> Outcome:
    if any(f.outcome == "discrepancy" for f in findings):
        return "discrepancy"
    if any(
        f.mandatory and f.outcome in {"insufficient_evidence", "not_applicable"} for f in findings
    ):
        return "insufficient_evidence"
    return "passed" if any(f.outcome == "passed" for f in findings) else "insufficient_evidence"


def verify(
    case_id: str,
    documents: list[DocumentEvidence],
    dataset_invoices: list[DocumentEvidence],
    tolerances: Tolerances | None = None,
) -> VerificationResult:
    tolerances = tolerances or Tolerances()
    findings: list[Finding] = []

    def add(
        rule: str,
        outcome: Outcome,
        actual: list[Observation],
        expected: list[Observation],
        explanation: str,
        mandatory: bool = True,
        document_ids: list[str] | None = None,
    ) -> None:
        observations = actual + expected
        findings.append(
            Finding(
                case_id=case_id,
                rule_id=rule,
                outcome=outcome,
                mandatory=mandatory,
                document_ids=sorted(
                    set((document_ids or []) + [o.document_id for o in observations])
                ),
                compared_fields=sorted({o.field_name for o in observations}),
                actual_values={f"{o.document_id}:{o.field_name}": o.value for o in actual},
                expected_values={f"{o.document_id}:{o.field_name}": o.value for o in expected},
                source_evidence=observations,
                explanation=explanation,
            )
        )

    invoices = [d for d in documents if d.document_type == "invoice"]
    orders = [d for d in documents if d.document_type == "purchase_order"]
    for kind, group in [("invoice", invoices), ("purchase_order", orders)]:
        if not group:
            add(
                "required_evidence",
                "insufficient_evidence",
                [],
                [],
                f"No {kind} document exists in this case.",
            )
    for document in documents:
        required = {"supplier_name", "buyer_name", "currency", "total_amount"} | (
            {"invoice_number", "invoice_date", "purchase_order_reference"}
            if document.document_type == "invoice"
            else {"po_number", "issue_date"}
        )
        observations = [observe(document, name) for name in sorted(set(document.fields) | required)]
        unresolved = sorted(key for key in required if not usable(observe(document, key)))
        extraction_issues = sorted(
            {
                f"{f.get('field', 'unknown')}:{f.get('code', 'review')}"
                for f in document.validation_findings
            }
        )
        complete = (
            document.processing_status == "extracted"
            and not document.validation_findings
            and all(usable(observe(document, key)) for key in required)
        )
        add(
            "required_evidence",
            "passed" if complete else "insufficient_evidence",
            observations,
            [],
            "Required extracted fields have valid provenance."
            if complete
            else (
                f"Extraction state: {document.processing_status}. "
                f"Unresolved required fields: {', '.join(unresolved) or 'none'}. "
                f"Extraction findings: {', '.join(extraction_issues) or 'none'}."
            ),
            document_ids=[document.document_id],
        )
    for invoice in invoices:
        reference = observe(invoice, "purchase_order_reference")
        po_numbers = [observe(order, "po_number") for order in orders]
        matches = [
            order
            for order in orders
            if usable(reference)
            and usable(observe(order, "po_number"))
            and reference.value.strip() == order.fields["po_number"].strip()
        ]
        po = matches[0] if len(matches) == 1 else None
        if po:
            add(
                "po_reference",
                "passed",
                [reference],
                [observe(po, "po_number")],
                "Invoice reference exactly matches one extracted PO number.",
            )
        else:
            outcome = (
                "discrepancy"
                if usable(reference)
                and po_numbers
                and all(usable(o) for o in po_numbers)
                and not matches
                else "insufficient_evidence"
            )
            add(
                "po_reference",
                outcome,
                [reference],
                po_numbers,
                "No unique referenced PO can be established; no alternative PO was assumed.",
            )
        for field, rule in [
            ("supplier_name", "supplier_match"),
            ("buyer_name", "buyer_match"),
            ("currency", "currency_match"),
        ]:
            actual = observe(invoice, field)
            expected = observe(po, field) if po else None
            valid = expected is not None and usable(actual) and usable(expected)
            if field == "currency":
                valid = valid and actual.value in MINOR_UNITS and expected.value in MINOR_UNITS
            result: Outcome = "insufficient_evidence"
            if valid:
                same = (
                    conservative_text(actual.value) == conservative_text(expected.value)
                    if field != "currency"
                    else actual.value == expected.value
                )
                result = "passed" if same else "discrepancy"
            add(
                rule,
                result,
                [actual],
                [expected] if expected else [],
                "Case/whitespace-normalized text equality only; no legal-entity inference."
                if field != "currency"
                else "Compare supported currency codes exactly; no conversion.",
            )
        total = observe(invoice, "total_amount")
        po_total = observe(po, "total_amount") if po else None
        currency = observe(invoice, "currency")
        po_currency = observe(po, "currency") if po else None
        same_currency = (
            po_currency is not None
            and usable(currency)
            and usable(po_currency)
            and currency.value == po_currency.value
            and currency.value in MINOR_UNITS
        )
        actual_amount = number(total)
        expected_amount = number(po_total) if po_total else None
        with localcontext() as context:
            context.prec = 80
            result = "insufficient_evidence"
            if same_currency and actual_amount is not None and expected_amount is not None:
                result = (
                    "passed"
                    if actual_amount <= expected_amount + tolerances.amount
                    else "discrepancy"
                )
            add(
                "invoice_total",
                result,
                [total, currency],
                [po_total, po_currency] if po_total else [],
                f"Invoice <= PO + {tolerances.amount}. A matching supported currency is required.",
            )
            invoice_date = observe(invoice, "invoice_date")
            po_date = observe(po, "issue_date") if po else None
            actual_date = iso_date(invoice_date)
            expected_date = iso_date(po_date) if po_date else None
            result = (
                "insufficient_evidence"
                if actual_date is None or expected_date is None
                else "passed"
                if actual_date >= expected_date
                else "discrepancy"
            )
            add(
                "invoice_date",
                result,
                [invoice_date],
                [po_date] if po_date else [],
                "Invoice date must be on or after PO issue date. No upper bound is assumed.",
            )
            if not invoice.line_items:
                for rule in ("line_quantity", "line_unit_price"):
                    add(
                        rule,
                        "not_applicable",
                        [],
                        [],
                        "No extracted invoice line items; line comparison was not performed.",
                        mandatory=False,
                        document_ids=[invoice.document_id] + ([po.document_id] if po else []),
                    )
            else:
                descriptions = [
                    conservative_text(item.get("description") or "") for item in invoice.line_items
                ]
                for item in invoice.line_items:
                    index = item.get("source_index")
                    description = observe(
                        invoice, f"line_items.{index}.description", item.get("description")
                    )
                    candidates = (
                        [
                            line
                            for line in po.line_items
                            if usable(description)
                            and conservative_text(line.get("description") or "")
                            == conservative_text(description.value)
                        ]
                        if po
                        else []
                    )
                    unique = (
                        descriptions.count(conservative_text(description.value or "")) == 1
                        and len(candidates) == 1
                    )
                    supported = candidates[0] if unique else None
                    expected_description = (
                        observe(
                            po,
                            f"line_items.{supported.get('source_index')}.description",
                            supported.get("description"),
                        )
                        if supported
                        else None
                    )
                    mapping_valid = (
                        usable(description)
                        and expected_description is not None
                        and usable(expected_description)
                    )
                    for leaf, rule, tolerance in [
                        ("quantity", "line_quantity", tolerances.quantity),
                        ("unit_price", "line_unit_price", tolerances.unit_price),
                    ]:
                        actual = observe(invoice, f"line_items.{index}.{leaf}", item.get(leaf))
                        expected = (
                            observe(
                                po,
                                f"line_items.{supported.get('source_index')}.{leaf}",
                                supported.get(leaf),
                            )
                            if supported
                            else None
                        )
                        left, right = number(actual), number(expected) if expected else None
                        result = "insufficient_evidence"
                        if (
                            mapping_valid
                            and left is not None
                            and right is not None
                            and (leaf == "quantity" or same_currency)
                        ):
                            matches_value = (
                                left <= right + tolerance
                                if leaf == "quantity"
                                else abs(left - right) <= tolerance
                            )
                            result = "passed" if matches_value else "discrepancy"
                        add(
                            rule,
                            result,
                            [description, actual],
                            ([expected_description, expected] if supported else []),
                            (
                                "Unique descriptions required; invoice quantity <= PO quantity; "
                                if leaf == "quantity"
                                else "Unique descriptions/currency; equal unit prices; "
                            )
                            + f"absolute tolerance {tolerance}. No line-index matching.",
                        )
        number_observation = observe(invoice, "invoice_number")
        known = [
            observe(d, "invoice_number")
            for d in dataset_invoices
            if d.document_type == "invoice" and d.document_id != invoice.document_id
        ]
        duplicates = [
            o
            for o in known
            if usable(number_observation)
            and usable(o)
            and o.value.strip() == number_observation.value.strip()
            and o.document_id != invoice.document_id
        ]
        result = (
            "discrepancy"
            if duplicates
            else "passed"
            if usable(number_observation) and all(usable(o) for o in known)
            else "insufficient_evidence"
        )
        add(
            "duplicate_invoice_number",
            result,
            [number_observation],
            duplicates or known,
            "Exact number duplicates are investigation flags. "
            "Only invoice documents are compared. Missing/unproven numbers prevent a clean "
            "dataset-wide duplicate check; unrelated unresolved invoices do not block "
            "this case's mandatory evidence checks. Inspect this finding even if the case passes.",
            # Uncertainty elsewhere must remain visible, without becoming missing case evidence.
            # Known duplicates still produce an overall discrepancy, even on an optional check.
            mandatory=bool(duplicates)
            or not usable(number_observation)
            or all(usable(o) for o in known),
        )
    return VerificationResult(outcome=overall(findings), findings=findings)
