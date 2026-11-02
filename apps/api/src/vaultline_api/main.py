"""FastAPI application factory and shared HTTP handling."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from vaultline_api.api.routes.cases import router as cases_router
from vaultline_api.api.routes.claims import router as claims_router
from vaultline_api.api.routes.health import router as health_router
from vaultline_api.api.routes.investigations import router as investigations_router
from vaultline_api.core.config import get_settings


def create_app() -> FastAPI:
    """Build the API application using validated runtime settings."""
    settings = get_settings()
    app = FastAPI(title=settings.app_name)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.exception_handler(SQLAlchemyError)
    async def handle_database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": "Database operation unavailable"})

    @app.exception_handler(Exception)
    async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
        """Return a stable error shape without exposing internal exception details."""
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_server_error",
                    "message": "An unexpected error occurred.",
                }
            },
        )

    app.include_router(health_router)
    app.include_router(cases_router)
    app.include_router(claims_router)
    app.include_router(investigations_router)
    return app


app = create_app()
