from fastapi import APIRouter
from .user_routes import router as user_router
from .profile_routes import router as profile_router
from .category_routes import router as category_router
from .cities_routes import router as cities_router
from .service_listing_routes import router as service_listing_router
from .listing_media_routes import router as listing_media_router
from .order_routes import router as order_router
from .review_route import router as review_router
from .notification_routes import router as notification_router
from .websocket_routes import router as websocket_router
from .refresh_token_routes import router as refresh_token_router
from .otp_token_route import router as otp_token_router

# Main API Router that aggregates all resource routers
api_router = APIRouter()

# Include resource routers
api_router.include_router(user_router)
api_router.include_router(profile_router)
api_router.include_router(category_router)
api_router.include_router(cities_router)
api_router.include_router(service_listing_router)
api_router.include_router(listing_media_router)
api_router.include_router(order_router)
api_router.include_router(review_router)
api_router.include_router(notification_router)
api_router.include_router(websocket_router)
api_router.include_router(refresh_token_router)
api_router.include_router(otp_token_router)

