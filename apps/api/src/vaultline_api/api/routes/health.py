"""Health and readiness endpoints."""

from fastapi import APIRouter

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
