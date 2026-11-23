from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.source import NewsSource


async def get_source_by_domain(
    db: AsyncSession, domain: str
) -> Optional[NewsSource]:
    """Retrieves an existing source by clean domain."""
    stmt = select(NewsSource).where(NewsSource.domain == domain)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_or_create_source(
    db: AsyncSession,
    domain: str,
    name: Optional[str] = None,
    website_url: Optional[str] = None,
    country: Optional[str] = None,
    language: str = "en",
) -> NewsSource:
    """Finds an existing source by domain or creates a new one.
    
    If the source exists and has only a bare domain as name but we now have
    a proper publisher display name, update it.
    """
    clean_domain = domain.strip().lower()
    source = await get_source_by_domain(db, clean_domain)
    if source:
        # Upgrade name if we now have a better publisher display name
        if name and name.strip() and name.strip() != clean_domain:
            if source.name == clean_domain or source.name == clean_domain.capitalize():
                source.name = name.strip()
                await db.flush()
        return source

    display_name = (name.strip() if name and name.strip() else None) or clean_domain
    new_source = NewsSource(
        name=display_name,
        domain=clean_domain,
        website_url=website_url or f"https://{clean_domain}",
        country=country,
        language=language,
        is_active=True,
    )
    db.add(new_source)
    await db.flush()
    return new_source
