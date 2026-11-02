"""Extract observed fields from supported document structures without inference."""

from vaultline_api.extraction.contracts import SourceField
from vaultline_api.extraction.parsing import ParsedDocument


def extract_fields(document: ParsedDocument) -> list[SourceField]:
    fields: list[SourceField] = []
    if document.format == "csv":
        if not document.rows or document.rows[0] != ["field", "value"]:
            raise ValueError("Unsupported CSV schema")
        for row_number, row in enumerate(document.rows[1:], start=2):
            if len(row) != 2:
                raise ValueError("Invalid field/value row")
            fields.append(
                SourceField(
                    row[0], row[1], {"row": row_number, "column": "value"}, "csv_field_value_v1"
                )
            )
    else:
        for page_number, text in enumerate(document.pages, start=1):
            for line in text.splitlines():
                if ":" in line:
                    name, value = line.split(":", 1)
                    fields.append(
                        SourceField(name, value, {"page": page_number}, "pdf_label_value_v1")
                    )
                if len(fields) > 10000:
                    raise ValueError("Field limit")
    if any(len(field.name) > 200 for field in fields):
        raise ValueError("Field name limit")
    return fields
