"""Bounded streaming storage and syntactic validation of untrusted evidence."""

import csv
import hashlib
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile
from pypdf import PdfReader

from vaultline_api.core.config import get_settings

ALLOWED = {
    ".pdf": {"application/pdf"},
    ".csv": {"text/csv", "application/csv", "application/vnd.ms-excel"},
}


def store_upload(upload: UploadFile) -> tuple[Path, str, int, str]:
    settings = get_settings()
    name = (upload.filename or "").replace("\\", "/").split("/")[-1]
    extension = Path(name).suffix.lower()
    if not name or len(name) > 255 or any(ord(c) < 32 for c in name):
        raise HTTPException(422, "Invalid filename")
    if extension not in ALLOWED or upload.content_type not in ALLOWED[extension]:
        raise HTTPException(415, "Only PDF and CSV with matching content types are supported")
    root = settings.evidence_storage_dir.resolve()
    # Never permit configured storage inside the publicly served frontend.
    web = Path(__file__).resolve().parents[4] / "web"
    if root == web or web in root.parents:
        raise HTTPException(500, "Invalid evidence storage configuration")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    key = uuid4().hex + extension
    path = root / key
    created = False
    size = 0
    digest = hashlib.sha256()
    try:
        with path.open("xb") as target:
            created = True
            path.chmod(0o600)
            while chunk := upload.file.read(64 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(413, "File exceeds upload size limit")
                target.write(chunk)
                digest.update(chunk)
        if size == 0:
            raise HTTPException(422, "Empty uploads are not accepted")
        try:
            if extension == ".pdf":
                with path.open("rb") as source:
                    if source.read(5) != b"%PDF-":
                        raise ValueError("Missing PDF signature")
                    source.seek(0)
                    reader = PdfReader(source, strict=True)
                    if reader.is_encrypted or len(reader.pages) == 0:
                        raise ValueError("Encrypted or empty PDF")
            else:
                with path.open(encoding="utf-8-sig", newline="") as source:
                    rows = csv.reader(source, strict=True)
                    width = None
                    count = 0
                    for row in rows:
                        if any("\x00" in cell for cell in row):
                            raise ValueError("Binary CSV")
                        if not row or not any(cell.strip() for cell in row):
                            continue
                        width = width or len(row)
                        if len(row) != width:
                            raise ValueError("Inconsistent CSV rows")
                        count += 1
                    if count == 0:
                        raise ValueError("Empty CSV")
        except Exception as exc:
            raise HTTPException(422, "Malformed, encrypted, or unsupported document") from exc
        path.chmod(0o400)
        return path, name, size, digest.hexdigest()
    except BaseException:
        if created:
            path.unlink(missing_ok=True)
        raise
