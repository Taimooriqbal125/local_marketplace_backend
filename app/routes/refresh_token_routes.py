"""Refresh Token Routes — API endpoints for refresh token lifecycle."""

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import settings
from app.core.rate_limiter import refresh_issue_rate_limit
from app.db.session import get_db
from app.models.user import User
from app.repositories import UserRepository
from app.services import RefreshTokenService


class RefreshTokenRequest(BaseModel):
	refresh_token: str = Field(..., min_length=16)


class TokenPairResponse(BaseModel):
	access_token: str
	refresh_token: str
	token_type: str = "bearer"


class MessageResponse(BaseModel):
	message: str


router = APIRouter(
	prefix="/refreshtokens",
	tags=["Refresh Tokens"],
)


REFRESH_TOKEN_COOKIE_NAME = "refresh_token"


def _resolve_refresh_token(
	payload: Optional[RefreshTokenRequest],
	refresh_token_cookie: Optional[str],
) -> str:
	"""Resolve refresh token from request body first, then cookie."""
	if payload and payload.refresh_token:
		return payload.refresh_token
	if refresh_token_cookie:
		return refresh_token_cookie
	raise HTTPException(
		status_code=status.HTTP_401_UNAUTHORIZED,
		detail="Refresh token not provided",
	)


def _set_refresh_token_cookie(response: Response, refresh_token: str) -> None:
	"""Persist refresh token in secure HttpOnly cookie."""
	response.set_cookie(
		key=REFRESH_TOKEN_COOKIE_NAME,
		value=refresh_token,
		httponly=True,
		secure=False,
		samesite="lax",
		max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
	)


@router.post(
	"/issue",
	response_model=TokenPairResponse,
	status_code=status.HTTP_201_CREATED,
	dependencies=[Depends(refresh_issue_rate_limit)],
)
def issue_refresh_token(
	response: Response,
	db: Session = Depends(get_db),
	current_user: User = Depends(security.get_current_user),
):
	"""Issue a fresh access token + refresh token pair for authenticated user."""
	service = RefreshTokenService(db)

	raw_refresh_token, _ = service.issue_token(current_user.id)

	access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
	access_token = security.create_access_token(
		data={"sub": str(current_user.id)},
		expires_delta=access_token_expires,
	)
	_set_refresh_token_cookie(response, raw_refresh_token)

	return {
		"access_token": access_token,
		"refresh_token": raw_refresh_token,
		"token_type": "bearer",
	}


@router.post("/rotate", response_model=TokenPairResponse)
def rotate_refresh_token(
	response: Response,
	payload: Optional[RefreshTokenRequest] = None,
	refresh_token_cookie: Optional[str] = Cookie(default=None, alias=REFRESH_TOKEN_COOKIE_NAME),
	db: Session = Depends(get_db),
):
	"""Rotate refresh token and return a new access token + refresh token pair."""
	service = RefreshTokenService(db)

	incoming_refresh_token = _resolve_refresh_token(payload, refresh_token_cookie)
	raw_refresh_token, db_token = service.rotate_token(incoming_refresh_token)

	user = UserRepository(db).get(db_token.user_id)
	if not user:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="User not found for this refresh token",
		)

	access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
	access_token = security.create_access_token(
		data={"sub": str(user.id)},
		expires_delta=access_token_expires,
	)
	_set_refresh_token_cookie(response, raw_refresh_token)

	return {
		"access_token": access_token,
		"refresh_token": raw_refresh_token,
		"token_type": "bearer",
	}


@router.post("/revoke", response_model=MessageResponse)
def revoke_refresh_token(
	response: Response,
	payload: Optional[RefreshTokenRequest] = None,
	refresh_token_cookie: Optional[str] = Cookie(default=None, alias=REFRESH_TOKEN_COOKIE_NAME),
	db: Session = Depends(get_db),
):
	"""Revoke a single refresh token using raw token value."""
	service = RefreshTokenService(db)
	incoming_refresh_token = _resolve_refresh_token(payload, refresh_token_cookie)
	revoked = service.revoke_token(incoming_refresh_token)

	if not revoked:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail="Refresh token not found",
		)

	response.delete_cookie(key=REFRESH_TOKEN_COOKIE_NAME)

	return {"message": "Refresh token revoked successfully"}


@router.post("/logout", response_model=MessageResponse)
def logout_user(
	response: Response,
	current_user: User = Depends(security.get_current_user),
	payload: Optional[RefreshTokenRequest] = None,
	refresh_token_cookie: Optional[str] = Cookie(default=None, alias=REFRESH_TOKEN_COOKIE_NAME),
	db: Session = Depends(get_db),
):
	"""Logout current user by revoking only their own refresh token."""
	service = RefreshTokenService(db)
	incoming_refresh_token = _resolve_refresh_token(payload, refresh_token_cookie)
	revoked = service.revoke_token_for_user(incoming_refresh_token, current_user.id)

	if not revoked:
		raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail="Refresh token not found",
		)

	response.delete_cookie(key=REFRESH_TOKEN_COOKIE_NAME)
	return {"message": "Logged out successfully"}


@router.post("/revoke-all", response_model=MessageResponse)
def revoke_all_user_tokens(
	response: Response,
	db: Session = Depends(get_db),
	current_user: User = Depends(security.get_current_user),
):
	"""Revoke all active refresh tokens for the current authenticated user."""
	service = RefreshTokenService(db)
	revoked_count = service.revoke_all_for_user(current_user.id)
	response.delete_cookie(key=REFRESH_TOKEN_COOKIE_NAME)
	return {"message": f"Revoked {revoked_count} refresh token(s)"}
