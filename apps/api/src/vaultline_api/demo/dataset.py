"""Reproducible, conspicuously synthetic files shared by demo and integration tests."""

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[5] / "demo" / "synthetic"


def seed(client) -> dict:
    """Use real API routes; caller must supply an isolated demo/test client."""
    manifest = json.loads((DATA_DIR / "manifest.json").read_text())
    records = {}
    for scenario in manifest["scenarios"]:
        response = client.post("/api/v1/cases", json={"counterparty_name": scenario["name"]})
        response.raise_for_status()
        case = response.json()
        base = f"/api/v1/cases/{case['id']}"
        documents = []
        for source in scenario["documents"]:
            path = DATA_DIR / source["file"]
            response = client.post(
                base + "/documents",
                data={"document_type": source["type"]},
                files={"file": (path.name, path.read_bytes(), "text/csv")},
            )
            response.raise_for_status()
            document = response.json()
            extraction = client.post(base + f"/documents/{document['id']}/extract")
            extraction.raise_for_status()
            if extraction.json()["status"] != "extracted":
                raise RuntimeError("Synthetic fixture extraction failed")
            documents.append(document)
        claim = None
        if scenario["claim"]:
            response = client.post(
                base + "/claims",
                json={**scenario["claim"], "invoice_document_id": documents[0]["id"]},
            )
            response.raise_for_status()
            claim = response.json()
        records[scenario["key"]] = {
            "case": case,
            "documents": documents,
            "claim": claim,
            "expected_outcome": scenario["expected_outcome"],
        }
    # Run after all uploads so duplicate checks see both synthetic conflict cases.
    for record in records.values():
        response = client.post(f"/api/v1/cases/{record['case']['id']}/verify")
        response.raise_for_status()
        record["verification"] = response.json()
        if response.json()["outcome"] != record["expected_outcome"]:
            raise RuntimeError("Synthetic demo outcome differed from the manifest")
    return records
