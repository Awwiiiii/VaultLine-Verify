"""Parse file structure only; field semantics live in fields.py."""

import csv
from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader


@dataclass(frozen=True)
class ParsedDocument:
    format: str
    rows: list[list[str]]
    pages: list[str]


def parse_document(path: Path) -> ParsedDocument:
    if path.suffix.lower() == ".csv":
        rows: list[list[str]] = []
        with path.open(encoding="utf-8-sig", newline="") as source:
            for row in csv.reader(source, strict=True):
                rows.append(row)
                if len(rows) > 10001:
                    raise ValueError("Row limit")
        return ParsedDocument("csv", rows, [])
    if path.suffix.lower() == ".pdf":
        reader = PdfReader(path, strict=True)
        if reader.is_encrypted or len(reader.pages) > 100:
            raise ValueError("Unsupported PDF")
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if len(text) > 200000:
                raise ValueError("Page text limit")
            pages.append(text)
        if not any(text.strip() for text in pages):
            raise ValueError("No extractable text; OCR unsupported")
        return ParsedDocument("pdf", [], pages)
    raise ValueError("Unsupported format")
