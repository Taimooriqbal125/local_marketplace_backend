"""
Background Tasks and Schedulers.
"""

from apscheduler.schedulers.background import BackgroundScheduler
from app.db.session import SessionLocal
from app.services.order_service import OrderService
from app.services.notification_service import NotificationService
from app.services.refresh_token_service import RefreshTokenService
from app.services.user_device_token_service import UserDeviceTokenService

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


def cleanup_refresh_tokens_job():
    """
    Background job to clean up stale refresh tokens.
    """
    db = SessionLocal()
    try:
        service = RefreshTokenService(db)
        result = service.cleanup_stale_tokens()
        print(f"[CLEANUP] Refresh token cleanup finished. Deleted {result['deleted_count']} token(s).")
    finally:
        db.close()


def cleanup_cancelled_orders_job():
    """
    Background job to remove cancelled orders after the retention window.
    """
    db = SessionLocal()
    try:
        service = OrderService(db)
        result = service.cleanup_cancelled_orders()
        print(f"[CLEANUP] Cancelled order cleanup finished. Deleted {result['deleted_count']} order(s).")
    finally:
        db.close()


def cleanup_inactive_device_tokens_job():
    """
    Background job to remove inactive device tokens after retention window.
    """
    db = SessionLocal()
    try:
        service = UserDeviceTokenService(db)
        result = service.cleanup_inactive_tokens()
        print(f"[CLEANUP] Inactive device token cleanup finished. Deleted {result['deleted_count']} token(s).")
    finally:
        db.close()

def start_scheduler():
    """
    Initialize and start the background scheduler.
    """
    scheduler = BackgroundScheduler()
    # Run cleanup daily at midnight
    scheduler.add_job(cleanup_notifications_job, 'cron', hour=0, minute=0)
    scheduler.add_job(cleanup_refresh_tokens_job, 'cron', hour=0, minute=15)
    scheduler.add_job(cleanup_cancelled_orders_job, 'cron', hour=0, minute=30)
    scheduler.add_job(cleanup_inactive_device_tokens_job, 'cron', hour=0, minute=45)
    
    # Optional: Run once on startup for immediate effect
    # scheduler.add_job(cleanup_notifications_job, 'date') 
    
    scheduler.start()
    print("[SCHEDULER] Background scheduler started.")
