from fastapi import APIRouter
from .user_routes import router as user_router
from .post_routes import router as post_router

# Main API Router that aggregates all resource routers
api_router = APIRouter()

# Include resource routers
api_router.include_router(user_router)
api_router.include_router(post_router)
