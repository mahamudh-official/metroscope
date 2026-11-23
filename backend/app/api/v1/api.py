from fastapi import APIRouter
from app.api.v1.endpoints import articles, categories, health, newsletter, photo_cards, social

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(articles.router, tags=["Articles"])
api_router.include_router(categories.router, tags=["Categories"])
api_router.include_router(newsletter.router, prefix="/newsletter", tags=["Newsletter"])
api_router.include_router(photo_cards.router, prefix="/photo-cards", tags=["Photo Cards"])
api_router.include_router(social.router, prefix="/social", tags=["Social Publishing"])
