"""Stage diagnostics contain only fixed codes; all fixtures are SYNTHETIC."""

import json
import runpy
import sys
from pathlib import Path

import httpx
import pytest
import test_investigations
from test_invoice_po_workflow import create_case

from vaultline_api.investigations.baseten import BasetenAIProvider
from vaultline_api.investigations.contracts import (
    InvestigationOutput,
    OutputValidationError,
    validate_output,
)
from vaultline_api.investigations.diagnostics import BASETEN_DIAGNOSTICS, error_stage
from vaultline_api.investigations.providers import MockAIProvider, ProviderError, get_provider
from vaultline_api.main import app


@pytest.fixture
def package():
    return test_investigations.package.__wrapped__()


def altered(package, failure):
    output = json.loads(MockAIProvider().generate(package))
    if failure == "schema":
        output["executive_summary"][0]["extra"] = "SYNTHETIC PRIVATE"
    elif failure == "kind":
        output["executive_summary"][0]["kind"] = "SYNTHETIC PRIVATE"
    elif failure == "missing_section":
        del output["key_findings"]
    elif failure == "missing_limit":
        del output["limitations"]
    elif failure == "empty_limit":
        output["limitations"] = []
    elif failure == "wrong_limit":
        output["limitations"] = output["executive_summary"]
    elif failure == "ref":
        output["executive_summary"][0]["evidence_refs"] = ["SYNTHETIC PRIVATE"]
    elif failure == "fact":
        output["executive_summary"][0].update(kind="observed_fact", text="SYNTHETIC PRIVATE")
    elif failure == "vocabulary":
        output["executive_summary"][0]["text"] = "SYNTHETIC PRIVATE approve financing"
    elif failure == "index":
        package = package.model_copy(deep=True)
        other = package.entries[0].model_copy(update={"id": "second"})
        package.entries.append(other)
        output["supporting_evidence_references"].append("second")
    elif failure == "uncertainty":
        output["unresolved_questions"] = output["unresolved_questions"][:1]
    elif failure == "insufficient":
        output["unresolved_questions"] = output["unresolved_questions"][1:]
    return json.dumps(output), package


@pytest.mark.parametrize(
    "failure,code",
    [
        ("schema", "output_schema"),
        ("kind", "statement_kind"),
        ("missing_section", "output_schema"),
        ("missing_limit", "limitation"),
        ("empty_limit", "limitation"),
        ("wrong_limit", "limitation"),
        ("ref", "references"),
        ("fact", "grounding_kind"),
        ("vocabulary", "vocabulary"),
        ("index", "evidence_index"),
        ("uncertainty", "uncertainty"),
        ("insufficient", "uncertainty"),
    ],
)
@pytest.mark.parametrize("mode", ["json_schema", "json_prompt"])
def test_semantic_failures_are_staged_without_leaking(package, monkeypatch, failure, code, mode):
    raw, package = altered(package, failure)
    with pytest.raises(OutputValidationError) as error:
        validate_output(raw, package)
    assert error.value.code == code and "PRIVATE" not in str(error.value)
    monkeypatch.setenv("BASETEN_API_KEY", "SYNTHETIC KEY")
    monkeypatch.setenv("AI_EVIDENCE_SHARING_APPROVED", "true")
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(
            200, json={"choices": [{"finish_reason": "stop", "message": {"content": raw}}]}
        )

    with pytest.raises(ProviderError) as provider_error:
        BasetenAIProvider(output_mode=mode, transport=httpx.MockTransport(handler)).generate(
            package
        )
    assert provider_error.value.code == "baseten_" + code
    assert error_stage(provider_error.value.code)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "payload,code",
    [
        ({"choices": [{"finish_reason": "SYNTHETIC PRIVATE"}]}, "baseten_completion_state"),
        (
            {"choices": [{"finish_reason": "stop", "message": {"content": []}}]},
            "baseten_content_type",
        ),
        (
            {"choices": [{"finish_reason": "stop", "message": {"content": "x" * 100001}}]},
            "baseten_content_limit",
        ),
        ({"choices": [{"finish_reason": "stop", "message": {}}]}, "baseten_no_content"),
    ],
)
def test_more_envelope_stages(package, monkeypatch, payload, code):
    monkeypatch.setenv("BASETEN_API_KEY", "SYNTHETIC KEY")
    monkeypatch.setenv("AI_EVIDENCE_SHARING_APPROVED", "true")
    with pytest.raises(ProviderError) as error:
        BasetenAIProvider(
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload))
        ).generate(package)
    assert error.value.code == code


def test_schema_shape_has_no_optional_or_open_objects():
    schema = InvestigationOutput.model_json_schema()
    assert set(schema["required"]) == set(schema["properties"])
    assert len(schema["properties"]) == 6
    statement = schema["$defs"]["Statement"]
    assert set(statement["required"]) == {"kind", "text", "evidence_refs"}
    assert statement["additionalProperties"] is False
    assert schema["additionalProperties"] is False
    assert statement["properties"]["kind"]["enum"] == [
        "observed_fact",
        "deterministic_finding",
        "ai_interpretation",
        "unknown",
    ]
    for name in (
        "executive_summary",
        "key_findings",
        "unresolved_questions",
        "recommended_next_verification_steps",
        "limitations",
    ):
        assert schema["properties"][name]["items"] == {"$ref": "#/$defs/Statement"}
    # Standard schema enforces structure, not the exact vocabulary or evidence semantics.
    assert "enum" not in statement["properties"]["text"]


def test_staged_failure_persisted_without_rewriting_history(client, monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", "SYNTHETIC KEY")
    monkeypatch.setenv("AI_EVIDENCE_SHARING_APPROVED", "true")
    base = create_case(client)
    app.dependency_overrides[get_provider] = lambda: MockAIProvider()
    old = client.post(base + "/investigations").json()

    def handler(request):
        return httpx.Response(
            200, json={"choices": [{"finish_reason": "stop", "message": {"content": "{}"}}]}
        )

    app.dependency_overrides[get_provider] = lambda: BasetenAIProvider(
        transport=httpx.MockTransport(handler)
    )
    failed = client.post(base + "/investigations").json()
    assert failed["error_code"] == "baseten_limitation"
    assert failed["error_stage"] == "mandatory_limitation"
    assert failed["output"] is None
    assert client.get(base + "/investigations/" + old["id"]).json() == old
    assert client.get(base + "/investigations/" + failed["id"]).json() == failed


def test_smoke_sanitizes_stage_and_never_retries(monkeypatch, capsys):
    calls = []

    def generate(self, package):
        calls.append(package)
        raise ProviderError("baseten_statement_kind")

    monkeypatch.setattr(BasetenAIProvider, "generate", generate)
    monkeypatch.setattr(sys, "argv", ["baseten_smoke.py", "--authorize-live"])
    with pytest.raises(SystemExit) as error:
        runpy.run_path(
            str(Path(__file__).parents[1] / "scripts/baseten_smoke.py"), run_name="__main__"
        )
    assert error.value.code == 1 and len(calls) == 1
    assert (
        capsys.readouterr().out
        == "Smoke test failed: baseten_statement_kind stage=schema_validation\n"
    )


def test_diagnostic_codes_fit_history_column():
    assert all(len(code) <= 40 for code in BASETEN_DIAGNOSTICS)
