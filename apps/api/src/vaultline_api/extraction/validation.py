"""Cross-field validation of normalized financial observations."""

from decimal import ROUND_HALF_UP, Decimal

from vaultline_api.extraction.contracts import ExtractionResult, Finding


def validate_result(
    result: ExtractionResult,
    document_type: str,
    items: dict[int, dict[str, str | None]],
    places: int | None,
) -> None:
    def finding(field: str, code: str, message: str) -> None:
        result.findings.append(Finding(field=field, code=code, message=message))

    required = {"supplier_name", "buyer_name", "currency", "total_amount"} | (
        {"invoice_number", "invoice_date"}
        if document_type == "invoice"
        else {"po_number", "issue_date"}
    )
    for name in sorted(required):
        if not result.fields.get(name):
            finding(name, "required", "Required field is missing or unresolved.")

    # Validate arithmetic only when all operands were explicitly extracted.
    def amount(name: str) -> Decimal | None:
        value = result.fields.get(name)
        return Decimal(value) if value is not None else None

    subtotal, tax, total = amount("subtotal"), amount("tax"), amount("total_amount")
    if subtotal is not None and tax is not None and total is not None and subtotal + tax != total:
        finding("total_amount", "inconsistent_total", "Subtotal plus tax does not equal total.")
    for index, item in sorted(items.items()):
        if any(item.get(key) is None for key in ("quantity", "unit_price", "amount")):
            finding(
                f"line_items.{index}",
                "incomplete_line",
                "Line arithmetic cannot be checked: quantity, unit price or amount is missing.",
            )
        if (
            all(item.get(k) is not None for k in ("quantity", "unit_price", "amount"))
            and places is not None
        ):
            expected = (Decimal(item["quantity"]) * Decimal(item["unit_price"])).quantize(
                Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP
            )
            if expected != Decimal(item["amount"]):
                finding(
                    f"line_items.{index}.amount",
                    "inconsistent_line",
                    "Quantity times unit price differs from line amount.",
                )
        result.line_items.append({"source_index": str(index), **item})
    if items and all(item.get("amount") is not None for item in items.values()):
        line_sum = sum((Decimal(item["amount"]) for item in items.values()), Decimal(0))
        target = subtotal if document_type == "invoice" else total
        if target is not None and line_sum != target:
            finding(
                "line_items",
                "inconsistent_lines",
                "Line amounts do not equal the stated subtotal or PO total.",
            )
    if (
        result.fields.get("invoice_date")
        and result.fields.get("due_date")
        and result.fields["due_date"] < result.fields["invoice_date"]
    ):
        finding("due_date", "date_order", "Due date precedes invoice date.")
