#!/bin/bash

# exit on error
set -e

echo "Professional Startup: Checking for database updates..."
# Run migrations to ensure DB is in sync BEFORE the app starts
alembic upgrade head

echo "Professional Startup: Starting Gunicorn server..."
# Start Gunicorn with Uvicorn workers for production performance
# We use the PORT environment variable provided by Render/Railway
PORT=${PORT:-8000}
exec gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:$PORT
