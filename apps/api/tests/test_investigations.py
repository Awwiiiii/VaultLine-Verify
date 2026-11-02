"""Synthetic provider contracts and rollback-only PostgreSQL investigation workflows."""

import json
from uuid import uuid4

import httpx
import pytest
from test_invoice_po_workflow import (
    INVOICE,
    ORDER,
    create_case,
    upload,
    verify,
)
from test_invoice_po_workflow import (
    client as workflow_client,
)

from vaultline_api.investigations.contracts import (
    EvidenceEntry,
    EvidencePackage,
    validate_output,
)
from vaultline_api.investigations.providers import (
    MetaAIProvider,
    MockAIProvider,
    ProviderError,
    get_provider,
)
from vaultline_api.main import app

client = workflow_client


@pytest.fixture
def package():
    return EvidencePackage(
        case_id=str(uuid4()),
        captured_at="2026-11-03T00:00:00Z",
        verification_run_id=None,
        verification_created_at=None,
        entries=[
            EvidenceEntry(
                id="coverage",
                kind="unknown",
                text="No saved verification.",
                document_ids=[],
                claim_ids=[],
                case_ids=[],
                provenance=[],
            )
        ],
    )


@pytest.fixture
def mock_provider(client):
    provider = MockAIProvider()
    app.dependency_overrides[get_provider] = lambda: provider
    return provider


def test_valid_latest_evidence_and_history(client, mock_provider):
    base = create_case(client)
    invoice, _ = upload(client, base, "invoice", INVOICE)
    upload(client, base, "purchase_order", ORDER)
    old_run = verify(client, base)
    latest_run = verify(client, base)
    first = client.post(base + "/investigations")
    assert first.status_code == 201
    first = first.json()
    assert first["status"] == "completed"
    snapshot = first["evidence_snapshot"]
    assert snapshot["verification_run_id"] == latest_run["id"]
    assert snapshot["verification_run_id"] != old_run["id"]
    observed = [e for e in snapshot["entries"] if e["kind"] == "observed_fact"]
    assert observed and any(invoice["id"] in e["document_ids"] for e in observed)
    assert any(e["provenance"] for e in observed)
    assert "original_value" not in json.dumps(snapshot)
    second = client.post(base + "/investigations").json()
    assert second["id"] != first["id"]
    upload(client, base, "invoice", INVOICE)
    verify(client, base)
    assert client.get(base + "/investigations/" + first["id"]).json() == first
    history = client.get(base + "/investigations?limit=1").json()
    assert history["total"] == 2 and len(history["items"]) == 1
    other = create_case(client)
    assert client.get(other + "/investigations/" + first["id"]).status_code == 404
    assert client.get(other + "/investigations").json()["total"] == 0
    assert client.get(base + "/investigations?limit=0").status_code == 422
    assert client.post("/api/v1/cases/invalid/investigations").status_code == 422
    assert client.post(f"/api/v1/cases/{uuid4()}/investigations").status_code == 404


def test_insufficient_evidence_and_no_cross_case_leakage(client, mock_provider):
    base, unrelated = create_case(client), create_case(client)
    upload(
        client, unrelated, "invoice", {**INVOICE, "invoice_number": "SYNTHETIC-PRIVATE-UNRELATED"}
    )
    result = client.post(base + "/investigations").json()
    assert result["status"] == "completed"
    assert "SYNTHETIC-PRIVATE-UNRELATED" not in json.dumps(result)
    assert any(
        "insufficient" in s["text"].lower() for s in result["output"]["unresolved_questions"]
    )
    assert result["evidence_snapshot"]["verification_run_id"] is None


@pytest.mark.parametrize(
    "code", ["timeout", "rate_limited", "invalid_credentials", "provider_error"]
)
def test_provider_failures_persist_safe_errors(client, mock_provider, monkeypatch, code):
    def fail(package):
        raise ProviderError(code)

    monkeypatch.setattr(mock_provider, "generate", fail)
    base = create_case(client)
    result = client.post(base + "/investigations").json()
    assert result["status"] == "failed" and result["error_code"] == code
    assert result["output"] is None and result["error"]
    assert client.get(base + "/investigations/" + result["id"]).json() == result


def test_missing_credentials_and_approval_fail_closed(client, monkeypatch):
    monkeypatch.delenv("MODEL_API_KEY", raising=False)
    base = create_case(client)
    result = client.post(base + "/investigations").json()
    assert result["provider"] == "meta" and result["model"] == "muse-spark-1.3"
    assert result["error_code"] == "missing_credentials"
    monkeypatch.setenv("MODEL_API_KEY", "SYNTHETIC-TEST-KEY")
    monkeypatch.delenv("AI_EVIDENCE_SHARING_APPROVED", raising=False)
    assert client.post(base + "/investigations").json()["error_code"] == "sharing_not_approved"


@pytest.mark.parametrize("bad", ["not json", "{}", '{"executive_summary": "bad"}'])
def test_invalid_structured_output(client, mock_provider, monkeypatch, bad):
    monkeypatch.setattr(mock_provider, "generate", lambda p: bad)
    result = client.post(create_case(client) + "/investigations").json()
    assert result["status"] == "failed" and result["error_code"] == "invalid_output"
    assert result["output"] is None


@pytest.mark.parametrize(
    "mutation",
    [
        "foreign_ref",
        "false_fact",
        "decision",
        "extra_document",
        "missing_limit",
        "missing_uncertainty",
    ],
)
def test_strict_grounding_rejection(package, mutation):
    output = json.loads(MockAIProvider().generate(package))
    if mutation == "foreign_ref":
        output["executive_summary"][0]["evidence_refs"] = [str(uuid4())]
    elif mutation == "false_fact":
        output["executive_summary"][0].update(kind="observed_fact", text="Invoice total is 999.99")
    elif mutation == "decision":
        output["executive_summary"][0]["text"] = "Approve this loan; no external financing exists."
    elif mutation == "extra_document":
        output["executive_summary"][0]["document_id"] = str(uuid4())
    elif mutation == "missing_limit":
        output["limitations"] = []
    else:
        output["unresolved_questions"] = []
    with pytest.raises(ValueError):
        validate_output(json.dumps(output), package)


@pytest.mark.parametrize("provider_type", [MetaAIProvider, MockAIProvider])
def test_shared_provider_contract(package, monkeypatch, provider_type):
    expected = MockAIProvider().generate(package)

    def handler(request):
        assert request.url == "https://api.meta.ai/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer SYNTHETIC-TEST-KEY"
        body = json.loads(request.content)
        assert body["model"] == "muse-spark-1.3" and body["store"] is False
        assert body["response_format"]["json_schema"]["strict"] is True
        assert body["response_format"]["type"] == "json_schema"
        assert json.loads(body["messages"][1]["content"]) == package.model_dump()
        return httpx.Response(
            200, json={"choices": [{"finish_reason": "stop", "message": {"content": expected}}]}
        )

    monkeypatch.setenv("MODEL_API_KEY", "SYNTHETIC-TEST-KEY")
    monkeypatch.setenv("AI_EVIDENCE_SHARING_APPROVED", "true")
    provider = (
        provider_type(transport=httpx.MockTransport(handler))
        if provider_type is MetaAIProvider
        else provider_type()
    )
    assert validate_output(provider.generate(package), package)


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "invalid_credentials"),
        (403, "invalid_credentials"),
        (429, "rate_limited"),
        (500, "provider_error"),
        (400, "provider_error"),
        (302, "provider_error"),
    ],
)
def test_meta_http_errors(package, monkeypatch, status, code):
    monkeypatch.setenv("MODEL_API_KEY", "SYNTHETIC-TEST-KEY")
    monkeypatch.setenv("AI_EVIDENCE_SHARING_APPROVED", "true")
    provider = MetaAIProvider(
        transport=httpx.MockTransport(lambda r: httpx.Response(status, text="SECRET MUST NOT LEAK"))
    )
    with pytest.raises(ProviderError) as error:
        provider.generate(package)
    assert error.value.code == code and "SECRET" not in str(error.value)


@pytest.mark.parametrize(
    "failure", ["timeout", "invalid_json", "truncated", "refusal", "oversized"]
)
def test_meta_transport_and_invalid_envelopes(package, monkeypatch, failure):
    monkeypatch.setenv("MODEL_API_KEY", "SYNTHETIC-TEST-KEY")
    monkeypatch.setenv("AI_EVIDENCE_SHARING_APPROVED", "true")

    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("SECRET", request=request)
        if failure == "invalid_json":
            return httpx.Response(200, text="not json")
        if failure == "oversized":
            return httpx.Response(200, text="x" * 100001)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "length" if failure == "truncated" else "stop",
                        "message": {
                            "content": "{}",
                            "refusal": "No" if failure == "refusal" else None,
                        },
                    }
                ]
            },
        )

    with pytest.raises(ProviderError) as error:
        MetaAIProvider(transport=httpx.MockTransport(handler)).generate(package)
    assert error.value.code == ("timeout" if failure == "timeout" else "invalid_output")


def test_foreign_reference_rejected_before_persistence(client, mock_provider, monkeypatch):
    original = mock_provider.generate

    def generate(package):
        output = json.loads(original(package))
        output["supporting_evidence_references"] = ["claim:UNSUPPORTED"]
        return json.dumps(output)

    monkeypatch.setattr(mock_provider, "generate", generate)
    result = client.post(create_case(client) + "/investigations").json()
    assert result["error_code"] == "invalid_output" and result["output"] is None


def test_claim_conflict_evidence_is_minimized_and_traceable(client, mock_provider):
    from test_claims import record

    base, other = create_case(client), create_case(client)
    invoice, _ = upload(client, base, "invoice", INVOICE)
    competing, _ = upload(client, other, "invoice", INVOICE)
    first = record(
        client,
        base,
        invoice,
        notes="SYNTHETIC-NOTE-NOT-FOR-AI",
        external_reference="SYNTHETIC-EXTERNAL-NOT-FOR-AI",
    ).json()
    second = record(client, other, competing, lender="SYNTHETIC-private-lender").json()
    result = client.post(base + "/investigations").json()
    assert result["status"] == "completed"
    package_text = json.dumps(result["evidence_snapshot"])
    assert "SYNTHETIC-NOTE-NOT-FOR-AI" not in package_text
    assert "SYNTHETIC-EXTERNAL-NOT-FOR-AI" not in package_text
    assert "SYNTHETIC-private-lender" not in package_text
    entries = result["evidence_snapshot"]["entries"]
    conflict = next(e for e in entries if "potential_competing_claims" in e["text"])
    assert set(conflict["claim_ids"]) == {first["id"], second["id"]}
    assert set(conflict["document_ids"]) == {invoice["id"], competing["id"]}
    assert any(e["provenance"] and competing["id"] in e["document_ids"] for e in entries)
    assert "original_value" not in package_text


def test_unexpected_exception_is_sanitized(client, mock_provider, monkeypatch):
    def fail(package):
        raise RuntimeError("SYNTHETIC-SECRET-DO-NOT-PERSIST")

    monkeypatch.setattr(mock_provider, "generate", fail)
    result = client.post(create_case(client) + "/investigations").json()
    assert result["error_code"] == "provider_error"
    assert "SYNTHETIC-SECRET" not in json.dumps(result)


def test_evidence_size_limit_fails_before_provider(client, mock_provider, monkeypatch):
    def oversized(db, case_id):
        raise ProviderError("evidence_too_large")

    def no_call(package):
        raise AssertionError("Provider must not be called")

    monkeypatch.setattr("vaultline_api.services.investigations.build_evidence", oversized)
    monkeypatch.setattr(mock_provider, "generate", no_call)
    result = client.post(create_case(client) + "/investigations").json()
    assert result["status"] == "failed" and result["error_code"] == "evidence_too_large"
    assert result["output"] is None


def test_routine_tests_block_live_http():
    with pytest.raises(AssertionError, match="Live HTTP is disabled"):
        httpx.get("https://api.meta.ai/v1/status")
