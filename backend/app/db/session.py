import asyncio
import socket
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text
from app.core.config import settings
from app.core.logging import logger

connect_args = {}
if "asyncpg" in settings.async_database_url:
    connect_args["timeout"] = 2.0

engine_kwargs = {
    "echo": False,
    "connect_args": connect_args,
}
if "sqlite" not in settings.async_database_url:
    engine_kwargs.update({
        "pool_size": 5,
        "max_overflow": 5,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
    })

async_engine = create_async_engine(
    settings.async_database_url,
    **engine_kwargs,
)

async_session_factory = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency that yields a managed database session."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_connection(timeout_seconds: float = 1.5) -> bool:
    """Verifies database connectivity without exposing connection secrets.
    
    Performs a fast socket pre-flight check so it returns False in milliseconds
    when the database is offline or socket access is blocked.
    """
    try:
        # Fast socket pre-flight check based on parsed engine URL (PostgreSQL only)
        db_url = async_engine.url
        if "sqlite" not in db_url.drivername:
            server = db_url.host or "127.0.0.1"
            port = db_url.port or 5432
            try:
                with socket.create_connection((server, port), timeout=0.3):
                    pass
            except OSError:
                return False

        async def _ping() -> bool:
            async with async_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True

        return await asyncio.wait_for(_ping(), timeout=timeout_seconds)
    except Exception as exc:
        logger.warning(f"Database health check failed: {exc.__class__.__name__}")
        return False
