from fastapi import APIRouter
from app.core.config import settings
from app.db.session import check_db_connection
from app.schemas.health import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="API Health Status",
    description="Returns current application operational status and database connection state.",
)
async def health_check() -> HealthResponse:
    db_ok = await check_db_connection()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        environment=settings.ENVIRONMENT,
        database_connected=db_ok,
        version="0.1.0",
    )
