from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.core.config import settings
from app.core.logging import logger
from app.core.exceptions import register_exception_handlers
from app.api.v1.api import api_router
from app.api.v1.endpoints.health import (
    health_check,
    liveness_check,
    readiness_check,
    metrics_check,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        f"Starting {settings.PROJECT_NAME} API backend in {settings.ENVIRONMENT} mode..."
    )
    # Validate production configuration and log diagnostics
    issues = settings.validate_production_configuration()
    for issue in issues:
        if issue.startswith("CRITICAL"):
            logger.error(f"[CONFIG AUDIT] {issue}")
        else:
            logger.warning(f"[CONFIG AUDIT] {issue}")
    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME} API backend...")


def create_app() -> FastAPI:
    """Application factory for MetroScope FastAPI application."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="0.1.0",
        description="Automated US & Global News Discovery Platform API",
        openapi_url=f"{settings.API_V1_STR}/openapi.json" if settings.DEBUG else None,
        docs_url=f"{settings.API_V1_STR}/docs" if settings.DEBUG else None,
        redoc_url=f"{settings.API_V1_STR}/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # CORS configuration
    if settings.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Host header validation for HTTP Host Header Poisoning mitigation
    if settings.ALLOWED_HOSTS:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.ALLOWED_HOSTS,
        )

    # Centralized Security Headers Middleware
    @app.middleware("http")
    async def add_security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "SAMEORIGIN"
        return response

    # Centralized exception handling
    register_exception_handlers(app)

    # Root health and probe endpoints
    app.add_api_route("/health", health_check, methods=["GET"], tags=["Health"])
    app.add_api_route("/health/live", liveness_check, methods=["GET"], tags=["Health"])
    app.add_api_route("/health/ready", readiness_check, methods=["GET"], tags=["Health"])
    app.add_api_route("/health/metrics", metrics_check, methods=["GET"], tags=["Health"])

    # Include API v1 router
    app.include_router(api_router, prefix=settings.API_V1_STR)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=settings.DEBUG,
    )
