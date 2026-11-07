from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import logger
from app.core.exceptions import register_exception_handlers
from app.api.v1.api import api_router
from app.api.v1.endpoints.health import health_check


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(
        f"Starting {settings.PROJECT_NAME} API backend in {settings.ENVIRONMENT} mode..."
    )
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

    # Centralized exception handling
    register_exception_handlers(app)

    # Root health endpoint
    app.add_api_route("/health", health_check, methods=["GET"], tags=["Health"])

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
