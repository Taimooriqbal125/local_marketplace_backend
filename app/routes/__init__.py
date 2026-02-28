from fastapi import APIRouter
from .user_routes import router as user_router
from .post_routes import router as post_router
from .profile_routes import router as profile_router  
from .category_routes import router as category_router
from .cities_routes import router as cities_router  # Import cities routes

# Main API Router that aggregates all resource routers
api_router = APIRouter()

# Include resource routers
api_router.include_router(user_router)
api_router.include_router(post_router)
api_router.include_router(profile_router)  # Include profile routes
api_router.include_router(category_router)  # Include category routes
api_router.include_router(cities_router)  # Include cities routes