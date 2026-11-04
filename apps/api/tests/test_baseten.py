"""Synthetic Baseten HTTP mocks only; never real inference."""

import json
import runpy
import sys
from pathlib import Path

import httpx
import pytest
import test_investigations
from pydantic import ValidationError
from test_invoice_po_workflow import create_case

from vaultline_api.investigations.baseten import BasetenAIProvider, ProviderConfiguration
from vaultline_api.investigations.contracts import validate_output
from vaultline_api.investigations.providers import (
    MetaAIProvider,
    MockAIProvider,
    ProviderError,
    get_provider,
)
from vaultline_api.main import app


@pytest.fixture
def package():
    return test_investigations.package.__wrapped__()


@pytest.fixture(autouse=True)
def configuration(monkeypatch):
    monkeypatch.setenv("BASETEN_API_KEY", "SYNTHETIC-BASETEN-KEY")
    monkeypatch.setenv("AI_EVIDENCE_SHARING_APPROVED", "true")
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    monkeypatch.delenv("BASETEN_MAX_TOKENS", raising=False)
    monkeypatch.delenv("BASETEN_OUTPUT_MODE", raising=False)


def test_selection_and_configuration(monkeypatch):
    assert isinstance(get_provider(), MetaAIProvider)
    monkeypatch.setenv("AI_PROVIDER", "baseten")
    monkeypatch.setenv("BASETEN_MAX_TOKENS", "12000")
    assert isinstance(get_provider(), BasetenAIProvider)
    assert get_provider().max_tokens == 12000
    monkeypatch.setenv("AI_PROVIDER", "mock")
    with pytest.raises(ValidationError):
        get_provider()


@pytest.mark.parametrize(
    "name,value",
    [
        ("BASETEN_MAX_TOKENS", "0"),
        ("BASETEN_MAX_TOKENS", "32769"),
        ("BASETEN_MAX_TOKENS", "bad"),
        ("BASETEN_OUTPUT_MODE", "automatic"),
    ],
)
def test_invalid_configuration(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(ValidationError):
        ProviderConfiguration()


@pytest.mark.parametrize("mode", ["json_schema", "json_prompt"])
def test_payload_and_shared_contract(package, mode):
    calls = []

    def handler(request):
        calls.append(request)
        assert str(request.url) == "https://inference.baseten.co/v1/chat/completions"
        assert request.headers["authorization"] == "Bearer SYNTHETIC-BASETEN-KEY"
        body = json.loads(request.content)
        assert body["model"] == "meta-models/muse-spark-open"
        assert body["reasoning_effort"] == "low" and body["max_tokens"] == 8192
        assert body["stream"] is False
        assert json.loads(body["messages"][1]["content"]) == package.model_dump()
        assert "untrusted data" in body["messages"][0]["content"]
        if mode == "json_schema":
            assert body["response_format"]["json_schema"]["strict"] is True
        else:
            assert "response_format" not in body
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": MockAIProvider().generate(package),
                            "reasoning_content": "SYNTHETIC reasoning never persisted",
                        },
                    }
                ]
            },
        )

    result = BasetenAIProvider(output_mode=mode, transport=httpx.MockTransport(handler)).generate(
        package
    )
    assert validate_output(result, package)
    assert "reasoning never persisted" not in result
    assert len(calls) == 1


@pytest.mark.parametrize(
    "status,code",
    [
        (401, "baseten_invalid_credentials"),
        (403, "baseten_invalid_credentials"),
        (402, "baseten_billing_restricted"),
        (404, "baseten_unsupported_model"),
        (429, "baseten_rate_limited"),
        (400, "baseten_unsupported_request"),
        (422, "baseten_unsupported_request"),
        (500, "baseten_provider_error"),
        (302, "baseten_provider_error"),
    ],
)
def test_http_errors_no_retry(package, status, code):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, text="SYNTHETIC private error body")

    with pytest.raises(ProviderError) as error:
        BasetenAIProvider(transport=httpx.MockTransport(handler)).generate(package)
    assert error.value.code == code and "private" not in str(error.value)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "failure,code",
    [
        ("connect", "baseten_connect_timeout"),
        ("read", "baseten_read_timeout"),
        ("connection", "baseten_provider_error"),
        ("envelope", "baseten_envelope"),
        ("json", "baseten_invalid_json"),
        ("length", "baseten_output_budget"),
        ("reasoning", "baseten_no_content"),
        ("refusal", "baseten_refusal"),
        ("foreign", "baseten_references"),
        ("oversized", "baseten_response_limit"),
        ("tool", "baseten_tool_calls"),
    ],
)
def test_failures(package, failure, code):
    def handler(request):
        if failure in {"connect", "read", "connection"}:
            raise {
                "connect": httpx.ConnectTimeout,
                "read": httpx.ReadTimeout,
                "connection": httpx.ConnectError,
            }[failure]("SYNTHETIC private", request=request)
        if failure == "envelope":
            return httpx.Response(200, text="not JSON")
        if failure == "oversized":
            return httpx.Response(200, text="x" * 1000001)
        content = MockAIProvider().generate(package)
        if failure == "foreign":
            output = json.loads(content)
            output["supporting_evidence_references"] = ["FOREIGN"]
            content = json.dumps(output)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "length" if failure == "length" else "stop",
                        "message": {
                            "content": None
                            if failure == "reasoning"
                            else "not json"
                            if failure == "json"
                            else content,
                            "reasoning_content": "SYNTHETIC private",
                            "refusal": "no" if failure == "refusal" else None,
                            "tool_calls": [{}] if failure == "tool" else None,
                        },
                    }
                ]
            },
        )

    with pytest.raises(ProviderError) as error:
        BasetenAIProvider(transport=httpx.MockTransport(handler)).generate(package)
    assert error.value.code == code
    assert "private" not in str(error.value)


@pytest.mark.parametrize(
    "failure,code",
    [
        ("key", "baseten_missing_credentials"),
        ("sharing", "sharing_not_approved"),
        ("disabled", "baseten_live_disabled"),
    ],
)
def test_preconditions_no_transport(package, monkeypatch, failure, code):
    if failure == "key":
        monkeypatch.delenv("BASETEN_API_KEY")
    if failure == "sharing":
        monkeypatch.delenv("AI_EVIDENCE_SHARING_APPROVED")

    def denied(request):
        raise AssertionError("No request allowed")

    with pytest.raises(ProviderError) as error:
        BasetenAIProvider(
            allow_requests=failure != "disabled", transport=httpx.MockTransport(denied)
        ).generate(package)
    assert error.value.code == code


@pytest.mark.parametrize("bad", [False, True])
def test_history_persistence_and_no_fallback(client, bad):
    def handler(request):
        from vaultline_api.investigations.contracts import EvidencePackage

        package = EvidencePackage.model_validate_json(
            json.loads(request.content)["messages"][1]["content"]
        )
        if bad:
            return httpx.Response(400, text="Unsupported schema SYNTHETIC private")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": MockAIProvider().generate(package)},
                    }
                ]
            },
        )

    app.dependency_overrides[get_provider] = lambda: BasetenAIProvider(
        transport=httpx.MockTransport(handler)
    )
    base = create_case(client)
    result = client.post(base + "/investigations").json()
    assert result["provider"] == "baseten" and result["model"] == "meta-models/muse-spark-open"
    assert result["status"] == ("failed" if bad else "completed")
    if bad:
        assert result["output"] is None and result["error_code"] == "baseten_unsupported_request"
    saved = client.get(base + "/investigations/" + result["id"]).json()
    assert saved == result
    assert "SYNTHETIC private" not in json.dumps(result)


def test_diagnostics_no_call(client, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "baseten")
    result = client.get("/system/provider").json()
    assert result["provider"] == "baseten"
    assert result["configuration"] == "configured" and result["availability"] == "untested"
    assert (
        result["basic_inference"] == "owner_reported_success"
        and result["live_validation"] == "owner_reported_synthetic_success"
    )
    assert "SYNTHETIC-BASETEN-KEY" not in json.dumps(result)


def test_smoke_requires_authorization(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["baseten_smoke.py"])
    with pytest.raises(SystemExit) as error:
        runpy.run_path(
            str(Path(__file__).parents[1] / "scripts/baseten_smoke.py"), run_name="__main__"
        )
    assert error.value.code == 2


def test_smoke_one_mocked_call(monkeypatch, capsys):
    calls = []

    def generate(self, package):
        calls.append(package)
        return MockAIProvider().generate(package)

    monkeypatch.setattr(BasetenAIProvider, "generate", generate)
    monkeypatch.setattr(sys, "argv", ["baseten_smoke.py", "--authorize-live"])
    runpy.run_path(str(Path(__file__).parents[1] / "scripts/baseten_smoke.py"), run_name="__main__")
    assert len(calls) == 1 and "SYNTHETIC" in calls[0].entries[0].text
    assert "passed local schema" in capsys.readouterr().out


def test_response_model_mismatch_rejected(package):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "model": "SYNTHETIC-different-model",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": MockAIProvider().generate(package)},
                    }
                ],
            },
        )

    with pytest.raises(ProviderError, match="baseten_model_mismatch"):
        BasetenAIProvider(transport=httpx.MockTransport(handler)).generate(package)


@pytest.mark.parametrize(
    "payload", [None, [], {"choices": []}, {"choices": [{"finish_reason": "stop", "message": []}]}]
)
def test_malformed_envelope_types_are_sanitized(package, payload):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=json.dumps(payload))
    )
    with pytest.raises(ProviderError, match="baseten_envelope"):
        BasetenAIProvider(transport=transport).generate(package)


def test_configured_baseten_complete_synthetic_api_workflow(client, monkeypatch):
    """Actual factory + adapter + API persistence; HTTP is mocked, never live inference."""
    from test_invoice_po_workflow import INVOICE, ORDER, upload, verify

    from vaultline_api.investigations.contracts import EvidencePackage

    monkeypatch.setenv("AI_PROVIDER", "baseten")
    original_client = httpx.Client
    calls = []

    def handler(request):
        calls.append(request)
        package = EvidencePackage.model_validate_json(
            json.loads(request.content)["messages"][1]["content"]
        )
        assert package.verification_run_id
        assert any(e.kind == "observed_fact" and e.provenance for e in package.entries)
        return httpx.Response(
            200,
            json={
                "model": "meta-models/muse-spark-open",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {"content": MockAIProvider().generate(package)},
                    }
                ],
            },
        )

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: original_client(**{**kwargs, "transport": httpx.MockTransport(handler)}),
    )
    base = create_case(client)
    upload(client, base, "invoice", INVOICE)
    upload(client, base, "purchase_order", ORDER)
    run = verify(client, base)
    result = client.post(base + "/investigations").json()
    assert result["status"] == "completed"
    assert result["provider"] == "baseten" and result["model"] == "meta-models/muse-spark-open"
    assert result["evidence_snapshot"]["verification_run_id"] == run["id"]
    saved = client.get(base + "/investigations/" + result["id"]).json()
    assert saved == result
    assert client.get(base + "/investigations").json()["items"][0]["id"] == result["id"]
    validate_output(
        json.dumps(saved["output"]), EvidencePackage.model_validate(saved["evidence_snapshot"])
    )
    assert len(calls) == 1
