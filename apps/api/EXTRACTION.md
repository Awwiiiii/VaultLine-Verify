# Deterministic extraction v1

Extraction observes source content; it does not verify financial claims. No OCR or AI is used. Scanned/image-only PDFs are unsupported. Use synthetic documents while authentication and authorization are absent.

## Supported schemas

UTF-8 CSV (optional BOM) must have exactly the header `field,value`. Each subsequent logical CSV record contains one field and its value. Normal CSV quoting is supported. Sources refer to the logical record number (header is row 1) and value column. Do not export a conventional invoice table without converting it to this schema.

Machine-readable PDFs must contain extractable text with one `field: value` per text line. Human-readable labels with spaces are accepted (`Invoice Number` maps to `invoice_number`). No arbitrary table layout inference is attempted. PDFs retain page references, without invented bounding boxes or line coordinates. Other layouts may produce missing fields and needs_review. Image-only PDFs fail safely.

Common fields: `supplier_name`, `buyer_name`, `currency`, `total_amount`.
Invoice fields: `invoice_number`, `invoice_date`, `due_date`, `purchase_order_reference`, `subtotal`, `tax`, `payment_terms`.
PO fields: `po_number`, `issue_date`.
Line items: `line_items.1.description`, `line_items.1.quantity`, `line_items.1.unit_price`, `line_items.1.amount`; increment the index for more items. Original indices are preserved as source_index.

Required fields: common fields plus invoice_number/invoice_date for invoices, or po_number/issue_date for purchase orders. Optional absent fields are not fabricated. Empty required fields generate findings. Duplicate fields, including repeated PDF labels, remain unresolved; identical duplicates are also flagged. Unknown fields generate review findings and remain in provenance.

Synthetic invoice example:

```csv
field,value
invoice_number,SYNTHETIC-INV-001
invoice_date,2026-10-01
due_date,2026-10-31
supplier_name,SYNTHETIC Supplier
buyer_name,SYNTHETIC Buyer
currency,USD
subtotal,100.00
tax,10.00
total_amount,110.00
line_items.1.description,Synthetic goods
line_items.1.quantity,2
line_items.1.unit_price,50.00
line_items.1.amount,100.00
```

For PO CSV use po_number and issue_date instead of invoice fields, plus common fields and optional line items.

Select `purchase_order` explicitly when uploading a PO. The upload API requires either
`invoice` or `purchase_order`; it persists that type and extraction uses its corresponding
schema for both CSV and text PDFs. The UI requires an explicit selection. A PO uploaded as
`invoice` retains that type: `po_number` and `issue_date` produce unsupported-field findings,
and their original values remain in provenance. It cannot satisfy required PO evidence.
Upload correctly typed evidence in a clean case; earlier documents and runs remain unchanged.
For cross-document verification an invoice also needs `purchase_order_reference`, exactly
matching the PO's `po_number` in the same case. See [VERIFICATION.md](VERIFICATION.md) for the
isolated synthetic workflow command and demonstration instructions.

## Normalization and validation

Money and quantity use Decimal, never float. API and JSON persistence use decimal strings to preserve exactness across clients. Supported currencies: USD/EUR/GBP/INR (2 decimal places), JPY (0), KWD (3). Other codes require review and no monetary normalization is attempted. A unique supported currency is required; currency symbols and ambiguous separators are rejected. Decimal inputs are bounded to 18 integer digits and 8 fractional digits. Negative values require review; credit notes are outside this schema.

Dates must be ISO YYYY-MM-DD. Monetary rounding uses ROUND_HALF_UP at currency minor units and emits an explicit review finding whenever the value changes. Originals are always retained. Subtotal + tax is compared with total only when all three are present. Quantity × price is rounded to currency units before comparison with line amount. Complete line amounts are compared with stated subtotal (invoice) or total (PO); missing components are not inferred.

Each provenance row links to the normalized record and source document, with original/normalized value, source reference, method and validation status. The schema_version identifies the provider-independent record contract. JSON payload stores fields, line_items and findings; provenance rows store every observed field separately, including duplicates and invalid values.

## Lifecycle and API

POST `/api/v1/cases/{case_id}/documents/{document_id}/extract` runs synchronous extraction. GET the same prefix ending in `/extraction` returns the saved result, or 404 if none exists.

The document row is locked during processing. State transitions are uploaded → processing → extracted/needs_review/failed. Processing is within the transaction; other clients observe the last committed state until completion. A process/database failure rolls back the transaction. Concurrent requests serialize on the document lock. Repeated successful or needs_review requests return the same persisted result. Failed requests may retry; no background job or automatic retry exists.

Source checksums and size are checked before parsing. Evidence bytes are not rewritten or deleted. Internal parser errors and filesystem paths are not returned. Parsers are limited to 100 PDF pages, 200,000 extracted text characters per page and 10,000 fields. This is not a malware scanner or a complete sandbox against adversarial PDF decompression; use trusted synthetic documents locally.

Migration: `uv run alembic upgrade head`. Downgrade removes extraction/provenance data and restores document states to uploaded; original evidence remains intact. Do not downgrade a database containing valuable extraction data without a backup.
