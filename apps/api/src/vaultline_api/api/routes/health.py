"""Health and readiness endpoints."""

import os
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from vaultline_api.investigations.baseten import BasetenAIProvider
from vaultline_api.investigations.providers import AIProvider, MetaAIProvider, get_provider
from vaultline_api.services.readiness import get_readiness

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Confirm the API process is responding."""
    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict[str, str]:
    """Report readiness based on implemented dependencies."""
    return get_readiness()


class ProviderStatus(BaseModel):
    provider: str
    model: str
    configuration: Literal["configured", "unavailable", "test_only"]
    availability: Literal["unavailable", "untested", "test_only"]
    basic_inference: Literal["owner_reported_success", "untested"] = "untested"
    live_validation: Literal[
        "untested", "owner_reported_synthetic_success", "owner_reported_application_success"
    ] = "untested"


@router.get("/system/provider", response_model=ProviderStatus)
def provider_status(provider: Annotated[AIProvider, Depends(get_provider)]) -> ProviderStatus:
    """Report local configuration only; never probe a provider or expose credentials."""
    if not isinstance(provider, (MetaAIProvider, BasetenAIProvider)):
        return ProviderStatus(
            provider=provider.name,
            model=provider.model,
            configuration="test_only",
            availability="test_only",
        )
    key_name = "BASETEN_API_KEY" if isinstance(provider, BasetenAIProvider) else "MODEL_API_KEY"
    configured = bool(os.environ.get(key_name, "").strip())
    permitted = provider.allow_requests and os.environ.get("AI_EVIDENCE_SHARING_APPROVED") == "true"
    return ProviderStatus(
        provider=provider.name,
        model=provider.model,
        basic_inference="owner_reported_success"
        if isinstance(provider, BasetenAIProvider)
        else "untested",
        live_validation="owner_reported_application_success"
        if isinstance(provider, BasetenAIProvider)
        else "untested",
        configuration="configured" if configured else "unavailable",
        availability="untested" if configured and permitted else "unavailable",
    )
