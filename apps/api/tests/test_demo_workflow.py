"""Complete shared synthetic demo against real endpoints in rollback-only PostgreSQL."""

import json

from fastapi.testclient import TestClient

from vaultline_api.demo.dataset import seed
from vaultline_api.demo.harness import isolated_demo
from vaultline_api.investigations.contracts import EvidencePackage, validate_output
from vaultline_api.investigations.providers import MetaAIProvider, MockAIProvider, get_provider


def test_complete_demo_preserves_evidence_and_history():
    assert isinstance(get_provider(), MetaAIProvider)
    with isolated_demo() as app:
        # Mock injection is explicit and confined to this test application.
        app.dependency_overrides[get_provider] = lambda: MockAIProvider()
        with TestClient(app) as client:
            records = seed(client)
            for key, record in records.items():
                base = f"/api/v1/cases/{record['case']['id']}"
                run = record["verification"]
                assert run["outcome"] == record["expected_outcome"]
                for doc in record["documents"]:
                    extraction = client.get(base + f"/documents/{doc['id']}/extraction").json()
                    assert extraction["status"] == "extracted"
                    for source in extraction["result"]["provenance"]:
                        assert source["source_document_id"] == doc["id"]
                        assert source["source_location"]["column"] == "value"
                        assert source["validation_status"] == "valid"
                if key == "matching":
                    assert all(f["outcome"] == "passed" for f in run["findings"])
                if key == "mismatch":
                    assert any(
                        f["rule_id"] == "invoice_total" and f["outcome"] == "discrepancy"
                        for f in run["findings"]
                    )
                if key.startswith("conflict"):
                    conflicts = client.get(base + "/claim-conflicts").json()["findings"]
                    competing = next(
                        f for f in conflicts if f["category"] == "potential_competing_claims"
                    )
                    assert set(competing["claim_ids"]) == {
                        records[k]["claim"]["id"] for k in ("conflict_a", "conflict_b")
                    }
                    assert len(competing["case_ids"]) == 2
                    assert all(d["provenance"] for d in competing["source_evidence"])
                    assert any(f["category"] == "aggregate_exceeds_invoice" for f in conflicts)
                assessment = client.get(base + "/risk-assessment").json()
                assert assessment["human_review_required"] is True
                expected_risk = (
                    "no_recorded_discrepancy"
                    if key == "matching"
                    else "insufficient_evidence"
                    if key == "missing"
                    else "review_findings_present"
                )
                assert assessment["assessment_status"] == expected_risk
                report = client.post(base + "/investigations").json()
                assert report["status"] == "completed" and report["provider"] == "mock"
                package = EvidencePackage.model_validate(report["evidence_snapshot"])
                validate_output(json.dumps(report["output"]), package)
                saved = client.get(base + "/investigations/" + report["id"]).json()
                assert saved == report
                assert client.post(base + "/verify").json()["id"] != run["id"]
                assert client.get(base + "/verifications/" + run["id"]).json() == run
                assert client.get(base + "/investigations/" + report["id"]).json() == report
    # The runtime factory was never changed to a mock.
    assert isinstance(get_provider(), MetaAIProvider)


def test_interactive_demo_disables_live_ai_even_with_environment_key(monkeypatch):
    monkeypatch.setenv("MODEL_API_KEY", "SYNTHETIC-KEY-NEVER-USED")
    monkeypatch.setenv("AI_EVIDENCE_SHARING_APPROVED", "true")
    with isolated_demo() as app, TestClient(app) as client:
        case = client.post("/api/v1/cases", json={"counterparty_name": "SYNTHETIC offline"}).json()
        result = client.post(f"/api/v1/cases/{case['id']}/investigations").json()
        assert result["provider"] == "meta" and result["status"] == "failed"
        assert result["error_code"] == "live_disabled"
        assert result["output"] is None


def test_recording_intake_pair_matches_without_colliding_with_seeded_demo():
    """A live upload during recording must not duplicate the already-seeded clean invoice."""
    from vaultline_api.demo.dataset import DATA_DIR

    with isolated_demo() as app, TestClient(app) as client:
        seed(client)
        response = client.post(
            "/api/v1/cases", json={"counterparty_name": "SYNTHETIC Recording intake"}
        )
        assert response.status_code == 201
        base = "/api/v1/cases/" + response.json()["id"]
        for kind in ("invoice", "purchase_order"):
            path = DATA_DIR / f"SYNTHETIC-recording-{kind}.csv"
            response = client.post(
                base + "/documents",
                data={"document_type": kind},
                files={"file": (path.name, path.read_bytes(), "text/csv")},
            )
            assert response.status_code == 201
            identifier = response.json()["id"]
            extraction = client.post(base + f"/documents/{identifier}/extract").json()
            assert extraction["status"] == "extracted"
            assert all(
                p["source_document_id"] == identifier for p in extraction["result"]["provenance"]
            )
        verification = client.post(base + "/verify").json()
        assert verification["outcome"] == "passed"
        assert all(f["outcome"] == "passed" for f in verification["findings"])
        risk = client.get(base + "/risk-assessment").json()
        assert risk["assessment_status"] == "no_recorded_discrepancy"
        assert risk["human_review_required"] is True
