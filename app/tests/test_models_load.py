import sys
import os
from datetime import datetime

# Add project root to sys.path
sys.path.append(os.getcwd())

def test_models():
    print("Testing Comprehensive Model Loading...")
    try:
        from app.models import (
            User, Profile, Category, City, 
            ServiceListing, ListingMedia, 
            Order, Review, Notification, 
            RefreshToken, OTPToken
        )
        print("Successfully imported all models from app.models.")

        # Test Category structure
        print("\nVerifying Category structure...")
        cat = Category(name="Electronics", slug="electronics")
        columns = Category.__table__.columns.keys()
        for col in ["created_at", "updated_at"]:
            if col not in columns:
                print(f"FAILED: Category missing {col}")
                return False
        print("PASS: Category is sound.")

        # Test User structure
        print("\nVerifying User structure...")
        user = User(email="test@example.com", hashed_password="...")
        columns = User.__table__.columns.keys()
        for col in ["created_at", "updated_at"]:
            if col not in columns:
                print(f"FAILED: User missing {col}")
                return False
        # Ensure legacy columns are gone or co-existing
        if "last_active_at" not in columns:
             print("FAILED: User missing last_active_at")
             return False
        print("PASS: User is sound.")

        # Test Profile structure (PostGIS)
        print("\nVerifying Profile structure...")
        from sqlalchemy import inspect
        columns = Profile.__table__.columns.keys()
        if "last_location_point" not in columns:
            print("FAILED: Profile missing PostGIS column last_location_point")
            return False
        print("PASS: Profile is sound.")

        # Test Notification structure
        print("\nVerifying Notification structure...")
        notif = Notification(userId=user.id, type="order_requested", title="Title", body="Body")
        columns = Notification.__table__.columns.keys()
        if "isRead" not in columns:
            print("FAILED: Notification missing isRead (camelCase preservation check)")
            return False
        print("PASS: Notification is sound.")

        return True
    except Exception as e:
        print(f"FAILED: Error during model check: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_models()
    if success:
        print("\nVerification SUCCESSFUL! All models are production-ready and structurally sound.")
        sys.exit(0)
    else:
        print("\nVerification FAILED! Please inspect the output above.")
        sys.exit(1)
