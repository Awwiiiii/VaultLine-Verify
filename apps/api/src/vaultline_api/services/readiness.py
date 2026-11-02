"""Readiness checks for dependencies currently implemented by the application."""

from fastapi import HTTPException, status

from vaultline_api.db.health import check_database_connection


def get_readiness() -> dict[str, str]:
    """Report ready only when the configured database accepts a simple query."""
    if not check_database_connection():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"status": "not_ready", "dependency": "database"},
        )
    return {"status": "ready", "database": "reachable"}
