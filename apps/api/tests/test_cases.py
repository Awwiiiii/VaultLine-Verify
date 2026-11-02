"""Synthetic evidence integration tests against the configured PostgreSQL database."""

import hashlib
from io import BytesIO
from unittest.mock import patch
from uuid import uuid4

import pytest
from pypdf import PdfWriter


def test_case_crud(client, case):
    assert client.get(f"/api/v1/cases/{case['id']}").json() == case
    assert case in client.get("/api/v1/cases?limit=100").json()["items"]
    assert client.get("/api/v1/cases/not-a-uuid").status_code == 422
    assert client.get(f"/api/v1/cases/{uuid4()}").status_code == 404
    assert client.post("/api/v1/cases", json={"counterparty_name": " "}).status_code == 422


@pytest.mark.parametrize("kind", ["pdf", "csv"])
def test_upload_and_checksum(client, case, tmp_path, kind):
    if kind == "pdf":
        stream = BytesIO()
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.write(stream)
        content = stream.getvalue()
    else:
        content = b"synthetic_id,amount\r\nDEMO,10.00\r\n"
    response = client.post(
        f"/api/v1/cases/{case['id']}/documents",
        data={"document_type": "invoice"},
        files={
            "file": (
                f"../../synthetic.{kind}",
                content,
                "application/pdf" if kind == "pdf" else "text/csv",
            )
        },
    )
    assert response.status_code == 201
    metadata = response.json()
    assert metadata["sha256_checksum"] == hashlib.sha256(content).hexdigest()
    assert metadata["processing_status"] == "uploaded"
    assert "storage_reference" not in metadata
    assert next(tmp_path.iterdir()).read_bytes() == content
    assert client.get(f"/api/v1/cases/{case['id']}/documents").json() == [metadata]


@pytest.mark.parametrize(
    "name,content,mime,status",
    [
        ("empty.csv", b"", "text/csv", 422),
        ("big.csv", b"a" * 4097, "text/csv", 413),
        ("x.exe", b"data", "application/octet-stream", 415),
        ("bad.pdf", b"%PDF-garbage", "application/pdf", 422),
        ("bad.csv", b"a,b\n1,2,3", "text/csv", 422),
    ],
)
def test_failed_upload_leaves_no_evidence(client, case, tmp_path, name, content, mime, status):
    response = client.post(
        f"/api/v1/cases/{case['id']}/documents",
        data={"document_type": "invoice"},
        files={"file": (name, content, mime)},
    )
    assert response.status_code == status
    assert client.get(f"/api/v1/cases/{case['id']}/documents").json() == []
    assert list(tmp_path.iterdir()) == []


def test_database_failure_removes_file(client, case, tmp_path):
    with patch(
        "vaultline_api.api.routes.cases.Session.flush",
        side_effect=RuntimeError("synthetic failure"),
    ):
        with pytest.raises(RuntimeError):
            client.post(
                f"/api/v1/cases/{case['id']}/documents",
                data={"document_type": "invoice"},
                files={"file": ("synthetic.csv", b"a,b\n1,2", "text/csv")},
            )
    assert list(tmp_path.iterdir()) == []
    assert client.get(f"/api/v1/cases/{case['id']}/documents").json() == []


@pytest.mark.parametrize("identifier,status", [("not-a-uuid", 422), (str(uuid4()), 404)])
def test_upload_rejects_invalid_case(client, tmp_path, identifier, status):
    response = client.post(
        f"/api/v1/cases/{identifier}/documents",
        data={"document_type": "invoice"},
        files={"file": ("synthetic.csv", b"a,b\n1,2", "text/csv")},
    )
    assert response.status_code == status
    assert list(tmp_path.iterdir()) == []
