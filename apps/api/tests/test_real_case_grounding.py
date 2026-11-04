"""SYNTHETIC real-case-shaped grounding regressions; no live provider requests."""

import json

import httpx
import pytest
from test_invoice_po_workflow import INVOICE, ORDER, create_case, upload, verify
from test_invoice_po_workflow import client as workflow_client

from vaultline_api.investigations.baseten import BasetenAIProvider
from vaultline_api.investigations.contracts import (
    EvidencePackage,
    OutputValidationError,
    validate_output,
)
from vaultline_api.investigations.generation_schema import grounded_generation_schema
from vaultline_api.investigations.providers import MockAIProvider, ProviderError, get_provider
from vaultline_api.main import app

client = workflow_client


@pytest.fixture
def duplicated_case(client):
    base, other = create_case(client), create_case(client)
    upload(client, base, "invoice", INVOICE)
    upload(client, base, "purchase_order", ORDER)
    upload(client, other, "invoice", INVOICE)
    run = verify(client, base)
    assert run["outcome"] == "discrepancy"
    duplicate = next(f for f in run["findings"] if f["rule_id"] == "duplicate_invoice_number")
    assert duplicate["outcome"] == "discrepancy"
    assert any(f["outcome"] == "passed" for f in run["findings"])
    app.dependency_overrides[get_provider] = lambda: MockAIProvider()
    report = client.post(base + "/investigations").json()
    return base, run, report, EvidencePackage.model_validate(report["evidence_snapshot"])


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("paraphrase", "grounding_text"),
        ("kind", "grounding_kind"),
        ("two_sources", "grounding_sources"),
    ],
)
def test_exact_original_grounding_branches(duplicated_case, mutation, code):
    _, _, _, package = duplicated_case
    output = json.loads(MockAIProvider().generate(package))
    statement = output["key_findings"][0]
    assert statement["kind"] == "deterministic_finding"
    if mutation == "paraphrase":
        statement["text"] += " SYNTHETIC paraphrase"
    elif mutation == "kind":
        statement["kind"] = "observed_fact"
    else:
        statement["evidence_refs"].append(package.entries[0].id)
    with pytest.raises(OutputValidationError) as error:
        validate_output(json.dumps(output), package)
    assert error.value.code == code


def test_real_package_is_compact_complete_and_grounded(duplicated_case):
    _, run, report, package = duplicated_case
    assert package.prompt_version == "vaultline.investigation.v2"
    assert report["status"] == "completed"
    findings = [e for e in package.entries if e.id.startswith("verification:")]
    assert len(findings) == len(run["findings"])
    duplicate = next(e for e in findings if "duplicate_invoice_number:" in e.text)
    assert duplicate.id in package.required_finding_refs
    assert any(duplicate.text == s["text"] for s in report["output"]["key_findings"])
    observations = [e for e in package.entries if e.kind == "observed_fact"]
    assert observations and all(e.provenance for e in observations)
    fingerprints = [
        json.dumps(
            [e.kind, e.text, e.document_ids, e.claim_ids, e.case_ids, e.provenance], sort_keys=True
        )
        for e in observations
    ]
    assert len(fingerprints) == len(set(fingerprints))
    # Repeated source observations across checks are retained once, never distinct sources merged.
    raw = sum(len(f["source_evidence"]) for f in run["findings"])
    assert len(observations) < raw
    assert len({(e.document_ids[0], e.text) for e in observations}) == len(observations)
    validate_output(json.dumps(report["output"]), package)


def test_request_fact_branches_bind_kind_text_and_single_ref(duplicated_case):
    _, _, _, package = duplicated_case
    schema = grounded_generation_schema(package)
    branches = schema["$defs"]["Statement"]["anyOf"]
    for entry in package.entries:
        if entry.kind == "unknown":
            continue
        branch = next(
            b
            for b in branches
            if b["properties"]["text"]["enum"] == [entry.text]
            and b["properties"]["evidence_refs"]["items"]["enum"] == [entry.id]
        )
        assert branch["properties"]["kind"]["enum"] == [entry.kind]
        assert branch["properties"]["evidence_refs"]["maxItems"] == 1
        assert branch["additionalProperties"] is False
        assert set(branch["required"]) == {"kind", "text", "evidence_refs"}


def test_material_omission_rejected_even_if_cited_as_ai(duplicated_case):
    _, _, _, package = duplicated_case
    output = json.loads(MockAIProvider().generate(package))
    output["key_findings"] = []
    output["executive_summary"][0]["evidence_refs"] = package.required_finding_refs
    with pytest.raises(OutputValidationError, match="material_findings"):
        validate_output(json.dumps(output), package)


@pytest.mark.parametrize("mode", ["json_schema", "json_prompt"])
def test_baseten_real_package_failure_then_success_preserves_history(
    client, duplicated_case, monkeypatch, mode
):
    base, run, _, package = duplicated_case
    monkeypatch.setenv("BASETEN_API_KEY", "SYNTHETIC TEST KEY")
    monkeypatch.setenv("AI_EVIDENCE_SHARING_APPROVED", "true")
    calls = []
    bad = True

    def handler(request):
        calls.append(request)
        body = json.loads(request.content)
        current = EvidencePackage.model_validate_json(body["messages"][1]["content"])
        output = json.loads(MockAIProvider().generate(current))
        if bad:
            output["key_findings"][0]["text"] = "SYNTHETIC unsupported paraphrase"
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(output)}}]
            },
        )

    app.dependency_overrides[get_provider] = lambda: BasetenAIProvider(
        output_mode=mode, transport=httpx.MockTransport(handler)
    )
    failed = client.post(base + "/investigations").json()
    assert failed["error_code"] == "baseten_grounding_text" and failed["output"] is None
    bad = False
    passed = client.post(base + "/investigations").json()
    assert passed["status"] == "completed" and passed["provider"] == "baseten"
    assert passed["model"] == "meta-models/muse-spark-open"
    assert client.get(base + "/investigations/" + failed["id"]).json() == failed
    assert client.get(base + "/verifications/" + run["id"]).json() == run
    validate_output(
        json.dumps(passed["output"]), EvidencePackage.model_validate(passed["evidence_snapshot"])
    )
    assert len(calls) == 2  # two explicit API starts, no automatic retries


def test_conflicts_are_mandatory_and_provenance_survives(client):
    from test_claims import record

    base, other = create_case(client), create_case(client)
    invoice, _ = upload(client, base, "invoice", INVOICE)
    competing, _ = upload(client, other, "invoice", INVOICE)
    record(client, base, invoice)
    record(client, other, competing, lender="SYNTHETIC competitor")
    app.dependency_overrides[get_provider] = lambda: MockAIProvider()
    report = client.post(base + "/investigations").json()
    package = EvidencePackage.model_validate(report["evidence_snapshot"])
    conflicts = [e for e in package.entries if e.id.startswith("conflict:")]
    assert conflicts
    assert {e.id for e in conflicts} <= set(package.required_finding_refs)
    assert any(e.provenance and competing["id"] in e.document_ids for e in package.entries)
    validate_output(json.dumps(report["output"]), package)


def test_legacy_snapshots_still_validate_without_material_field(duplicated_case):
    _, _, _, package = duplicated_case
    old = package.model_dump()
    old.pop("required_finding_refs")
    old["prompt_version"] = "vaultline.investigation.v1"
    legacy = EvidencePackage.model_validate(old)
    assert not legacy.required_finding_refs
    validate_output(MockAIProvider().generate(legacy), legacy)


def test_large_generation_grammar_fails_before_transport(monkeypatch, duplicated_case):
    _, _, _, package = duplicated_case
    monkeypatch.setenv("BASETEN_API_KEY", "SYNTHETIC TEST KEY")
    monkeypatch.setenv("AI_EVIDENCE_SHARING_APPROVED", "true")
    expanded = package.model_copy(deep=True)
    expanded.entries = [
        expanded.entries[0].model_copy(update={"id": str(i), "text": "SYNTHETIC " + "x" * 2900})
        for i in range(100)
    ]

    def denied(request):
        raise AssertionError("No HTTP call allowed")

    with pytest.raises(ProviderError, match="evidence_too_large"):
        BasetenAIProvider(transport=httpx.MockTransport(denied)).generate(expanded)
