"""
FastAPI Application Entry Point.

This is where everything comes together:
  1. Create the FastAPI app
  2. Create database tables on startup
  3. Register all route groups (routers)

Run with:  uvicorn app.main:app --reload
"""

from fastapi import FastAPI
from app.db.init_db import init_db
from app.routes import api_router

# ---------- Create the app ----------
app = FastAPI(
    title="FastAPI Example",
    description="A clean FastAPI boilerplate with a User CRUD API",
    version="1.0.0",
)


from app.core import tasks

# ---------- Startup event ----------
@app.on_event("startup")
def on_startup():
    """Runs once when the server starts — creates DB tables if they don't exist."""
    init_db()
    # Start background scheduler
    try:
        tasks.start_scheduler()
    except Exception as e:
        print(f"[ERROR] Failed to start scheduler: {e}")


# ---------- Register routers ----------
app.include_router(api_router)


# ---------- Health check ----------
@app.get("/", tags=["Health"])
def root():
    """Quick check that the server is running."""
    return {"message": "FastAPI is running 🚀"}
