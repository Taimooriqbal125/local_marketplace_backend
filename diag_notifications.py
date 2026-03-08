
import sys
import os
import uuid
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add the project root to sys.path
sys.path.append(os.getcwd())

from app.models.notification import Notification

# Simplistic DB connection for diagnostics
# Use the same logic as your app/db/session.py if possible
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost/marketplace")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def check_recent_notifications():
    db = SessionLocal()
    try:
        notifications = db.query(Notification).order_by(Notification.createdAt.desc()).limit(5).all()
        print(f"--- Recent Notifications ({len(notifications)}) ---")
        for n in notifications:
            print(f"ID: {n.id}")
            print(f"Recipient: {n.userId}")
            print(f"Type: {n.type}")
            print(f"Title: {n.title}")
            print(f"Body: {n.body}")
            print(f"Created: {n.createdAt}")
            print("-" * 20)
    finally:
        db.close()

if __name__ == "__main__":
    check_recent_notifications()
