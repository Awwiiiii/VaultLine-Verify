"""Normalize fields conservatively using Decimal; no financial verification claims."""

import re
from collections import Counter
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, localcontext

from vaultline_api.extraction.contracts import ExtractionResult, Finding, Provenance, SourceField
from vaultline_api.extraction.validation import validate_result

# Explicit supported currency subset; other codes require review, never guess minor units.
MINOR_UNITS = {"USD": 2, "EUR": 2, "GBP": 2, "INR": 2, "JPY": 0, "KWD": 3}
COMMON = {"supplier_name", "buyer_name", "currency", "total_amount"}
INVOICE = {
    "invoice_number",
    "invoice_date",
    "due_date",
    "purchase_order_reference",
    "subtotal",
    "tax",
    "payment_terms",
}
PO = {"po_number", "issue_date"}
LINE = re.compile(r"line_items\.([1-9][0-9]{0,3})\.(description|quantity|unit_price|amount)$")


def normalize(source: list[SourceField], document_type: str, document_id: str) -> ExtractionResult:
    result = ExtractionResult(document_type=document_type)

    def finding(field: str, code: str, message: str) -> None:
        result.findings.append(Finding(field=field, code=code, message=message))

    names = [s.name.strip().lower().replace(" ", "_") for s in source]
    counts = Counter(names)
    currency_values = [
        s.value.strip().upper() for s, n in zip(source, names, strict=True) if n == "currency"
    ]
    currency = currency_values[0] if len(currency_values) == 1 else None
    places = MINOR_UNITS.get(currency or "")
    allowed = COMMON | (INVOICE if document_type == "invoice" else PO)
    items: dict[int, dict[str, str | None]] = {}
    with localcontext() as context:
        context.prec = 80  # Covers products and sums of all bounded input decimals.
        for raw, name in zip(source, names, strict=True):
            match = LINE.fullmatch(name)
            value: str | None = raw.value.strip() or None
            status = "valid"
            if counts[name] > 1:
                value = None
                status = "ambiguous"
                finding(name, "duplicate", "Duplicate field; no value selected.")
            elif name not in allowed and not match:
                value = None
                status = "invalid"
                finding(name, "unsupported_field", "Field is outside the documented schema.")
            elif value is None:
                status = "invalid"
                finding(name, "missing_value", "Field has no value.")
            else:
                try:
                    leaf = match.group(2) if match else name
                    if name == "currency":
                        if value.upper() not in MINOR_UNITS:
                            raise ValueError("Unsupported currency code; review required.")
                        value = value.upper()
                    elif name.endswith("_date"):
                        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                            raise ValueError("Use an unambiguous ISO date (YYYY-MM-DD).")
                        value = date.fromisoformat(value).isoformat()
                    elif leaf in {
                        "total_amount",
                        "subtotal",
                        "tax",
                        "quantity",
                        "unit_price",
                        "amount",
                    }:
                        if not re.fullmatch(r"-?\d{1,18}(?:\.\d{1,8})?", value):
                            raise ValueError("Invalid decimal: use digits and a decimal point.")
                        amount = Decimal(value)
                        if amount < 0:
                            raise ValueError("Negative amounts require review.")
                        if leaf != "quantity":
                            if places is None:
                                raise ValueError("Monetary values require one supported currency.")
                            rounded = amount.quantize(
                                Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP
                            )
                            if rounded != amount:
                                status = "rounded"
                                finding(
                                    name,
                                    "rounded",
                                    "Rounded HALF_UP to currency minor units; review required.",
                                )
                            amount = rounded
                        value = format(amount, "f")
                except (ValueError, InvalidOperation) as exc:
                    value = None
                    status = "invalid"
                    finding(
                        name,
                        "invalid_value",
                        str(exc) if isinstance(exc, ValueError) else "Invalid decimal amount.",
                    )
            result.provenance.append(
                Provenance(
                    source_document_id=document_id,
                    field_name=name,
                    original_value=raw.value,
                    normalized_value=value,
                    source_location=raw.location,
                    extraction_method=raw.method,
                    validation_status=status,
                )
            )
            if match:
                items.setdefault(int(match.group(1)), {})[match.group(2)] = value
            elif name in allowed:
                result.fields[name] = value
        validate_result(result, document_type, items, places)
    return result
