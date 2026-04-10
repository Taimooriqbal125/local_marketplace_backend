from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.db.session import get_db
from app.schemas.otp_token import OTPVerify, OTPTokenResponse, OTPPurpose, OTPTokenBase
from app.schemas.user import ForgotPasswordRequest, ResetPasswordConfirm
from app.services.otp_token_service import OTPTokenService
from app.core.rate_limiter import forgot_password_rate_limit

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)

@router.post("/verify-otp", status_code=status.HTTP_200_OK)
def verify_otp(data: OTPVerify, db: Session = Depends(get_db)):
    """
    Verify an OTP code sent to the user's email.
    If valid, marks it as used and updates the user's verification status.
    """
    message = OTPTokenService(db).process_verify_otp(email=data.email, otp=data.otp, purpose=data.purpose)
    return {"message": message}

@router.post("/resend-otp", status_code=status.HTTP_200_OK)
def resend_otp(data: OTPTokenBase, db: Session = Depends(get_db)):
    """
    Generate and send a new OTP to the user's email.
    Invalidates any previous unused OTP for the same purpose.
    """
    message = OTPTokenService(db).process_resend_otp(email=data.email, purpose=data.purpose)
    return {"message": message}

@router.post(
    "/forgot-password",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(forgot_password_rate_limit)],
)
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """
    Initiate password reset by sending an OTP.
    """
    message = OTPTokenService(db).process_forgot_password(email=data.email)
    return {"message": message}

@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(data: ResetPasswordConfirm, db: Session = Depends(get_db)):
    """
    Reset password using a verified OTP.
    """
    message = OTPTokenService(db).process_reset_password(email=data.email, otp=data.otp, new_password=data.new_password)
    return {"message": message}