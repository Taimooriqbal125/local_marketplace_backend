"""
FastAPI Application Entry Point.

This is where everything comes together:
  1. Create the FastAPI app
  2. Create database tables on startup
  3. Register all route groups (routers)

Run with:  uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.init_db import init_db
from app.routes import api_router
from app.core.logging import logger
from app.core.rate_limiter import init_rate_limiter
from app.core.redis import close_redis_connection, test_redis_connection

# ---------- Create the app ----------
app = FastAPI(
    title="Local Marketplace API",
    description="Backend API for the Local Marketplace application, supporting service listings, orders, and reviews.",
    version="1.0.0",
)

# ---------- CORS Configuration ----------
# Professional Tip: For production, replace ["*"] with your actual frontend URL
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from app.core import tasks

# ---------- Startup event ----------
@app.on_event("startup")
async def on_startup():
    """Runs once when the server starts — creates DB tables if they don't exist."""
    init_db()

    redis_ok = await test_redis_connection()
    if not redis_ok:
        logger.error("Redis startup health check failed")

    await init_rate_limiter()

    # Start background scheduler
    try:
        tasks.start_scheduler()
    except Exception as e:
        logger.error("Failed to start scheduler", error=str(e))


@app.on_event("shutdown")
async def on_shutdown():
    """Runs once on shutdown to close external resources cleanly."""
    await close_redis_connection()


# ---------- Register routers ----------
app.include_router(api_router)


# ---------- Health check ----------
@app.get("/", tags=["Health"])
def root():
    """Quick check that the server is running."""
    return {"message": "FastAPI is running 🚀"}
