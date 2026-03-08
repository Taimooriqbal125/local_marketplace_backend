"""
Background Tasks and Schedulers.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from app.db.session import SessionLocal
from app.services.notification_service import NotificationService

def cleanup_notifications_job():
    """
    Background job to clean up expired notifications.
    """
    db = SessionLocal()
    try:
        service = NotificationService(db)
        result = service.cleanup_expired_notifications(read_days=60, unread_days=180)
        print(f"[CLEANUP] Scheduled cleanup finished. Deleted {result['deleted_count']} notifications.")
    finally:
        db.close()

def start_scheduler():
    """
    Initialize and start the background scheduler.
    """
    scheduler = BackgroundScheduler()
    # Run cleanup daily at midnight
    scheduler.add_job(cleanup_notifications_job, 'cron', hour=0, minute=0)
    
    # Optional: Run once on startup for immediate effect
    # scheduler.add_job(cleanup_notifications_job, 'date') 
    
    scheduler.start()
    print("[SCHEDULER] Background scheduler started.")
