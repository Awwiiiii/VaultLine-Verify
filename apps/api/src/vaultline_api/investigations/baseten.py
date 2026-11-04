"""Baseten-hosted Meta adapter: one bounded request, no retries or provider fallback."""

import json
import os
from typing import Literal

import httpx
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from vaultline_api.investigations.contracts import (
    EvidencePackage,
    InvestigationOutput,
    OutputValidationError,
    validate_output,
)
from vaultline_api.investigations.providers import ProviderError, investigation_instructions


class ProviderConfiguration(BaseSettings):
    """Nonsecret process configuration; invalid values fail closed, never choose a fallback."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore")
    ai_provider: Literal["meta", "baseten"] = "meta"
    baseten_max_tokens: int = Field(default=8192, ge=1024, le=32768)
    baseten_output_mode: Literal["json_schema", "json_prompt"] = "json_schema"


class BasetenAIProvider:
    name = "baseten"
    model = "meta-models/muse-spark-open"
    base_url = "https://inference.baseten.co/v1"

    def __init__(
        self,
        *,
        max_tokens: int = 8192,
        output_mode: Literal["json_schema", "json_prompt"] = "json_schema",
        transport: httpx.BaseTransport | None = None,
        allow_requests: bool = True,
    ):
        config = ProviderConfiguration(
            ai_provider="baseten", baseten_max_tokens=max_tokens, baseten_output_mode=output_mode
        )
        self.max_tokens = config.baseten_max_tokens
        self.output_mode = config.baseten_output_mode
        self.transport = transport
        self.allow_requests = allow_requests

    def generate(self, package: EvidencePackage) -> str:
        if not self.allow_requests:
            raise ProviderError("baseten_live_disabled")
        key = os.environ.get("BASETEN_API_KEY", "").strip()
        if not key:
            raise ProviderError("baseten_missing_credentials")
        if os.environ.get("AI_EVIDENCE_SHARING_APPROVED") != "true":
            raise ProviderError("sharing_not_approved")
        schema = InvestigationOutput.model_json_schema()
        body = {
            "model": self.model,
            "reasoning_effort": "low",
            "max_tokens": self.max_tokens,
            "stream": False,
            "messages": [
                {
                    "role": "system",
                    "content": investigation_instructions()
                    + " Return a JSON object only, without markdown. Use concise selections from "
                    "the allowed phrases; a human must review all evidence. "
                    "Copy allowed phrases verbatim, including punctuation. All six sections are "
                    "required. If entries contain only unknown evidence, key_findings must be [] "
                    "rather than relabeling unknown evidence as an observed fact. Include the "
                    "exact mandatory limitation in limitations with kind ai_interpretation. "
                    "Use only supplied entry IDs as evidence_refs, never case/document IDs. "
                    "JSON schema: " + json.dumps(schema),
                },
                {"role": "user", "content": package.model_dump_json()},
            ],
        }
        if self.output_mode == "json_schema":
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "VaultLineInvestigation", "strict": True, "schema": schema},
            }
        try:
            with httpx.Client(
                timeout=httpx.Timeout(120, connect=10),
                transport=self.transport,
                follow_redirects=False,
                trust_env=False,
            ) as client:
                with client.stream(
                    "POST",
                    self.base_url + "/chat/completions",
                    headers={"Authorization": "Bearer " + key},
                    json=body,
                ) as response:
                    codes = {
                        401: "baseten_invalid_credentials",
                        403: "baseten_invalid_credentials",
                        402: "baseten_billing_restricted",
                        404: "baseten_unsupported_model",
                        429: "baseten_rate_limited",
                        400: "baseten_unsupported_request",
                        422: "baseten_unsupported_request",
                    }
                    if response.status_code != 200:
                        raise ProviderError(
                            codes.get(response.status_code, "baseten_provider_error")
                        )
                    data = bytearray()
                    for chunk in response.iter_bytes():
                        data.extend(chunk)
                        # Bound the entire envelope, including reasoning that is never retained.
                        if len(data) > 1000000:
                            raise ProviderError("baseten_response_limit")
            try:
                payload = json.loads(data)
            except (ValueError, UnicodeError):
                raise ProviderError("baseten_envelope") from None
            if not isinstance(payload, dict):
                raise ProviderError("baseten_envelope")
            if "model" in payload and payload["model"] != self.model:
                raise ProviderError("baseten_model_mismatch")
            choices = payload.get("choices")
            if (
                not isinstance(choices, list)
                or len(choices) != 1
                or not isinstance(choices[0], dict)
            ):
                raise ProviderError("baseten_envelope")
            choice = choices[0]
            if choice.get("finish_reason") == "length":
                raise ProviderError("baseten_output_budget")
            if choice.get("finish_reason") != "stop":
                raise ProviderError("baseten_completion_state")
            message = choice.get("message")
            if not isinstance(message, dict):
                raise ProviderError("baseten_envelope")
            if message.get("refusal"):
                raise ProviderError("baseten_refusal")
            if message.get("tool_calls"):
                raise ProviderError("baseten_tool_calls")
            content = message.get("content")
            if content is None or content == "":
                raise ProviderError("baseten_no_content")
            if not isinstance(content, str):
                raise ProviderError("baseten_content_type")
            if len(content.encode()) > 100000:
                raise ProviderError("baseten_content_limit")
            validate_output(content, package)
            return content
        except OutputValidationError as exc:
            raise ProviderError("baseten_" + exc.code) from None
        except httpx.ConnectTimeout:
            raise ProviderError("baseten_connect_timeout") from None
        except httpx.TimeoutException:
            raise ProviderError("baseten_read_timeout") from None
        except httpx.HTTPError:
            raise ProviderError("baseten_provider_error") from None
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            raise ProviderError("baseten_envelope") from None
