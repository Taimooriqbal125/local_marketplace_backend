"""
Email Service — acts as a broker to external emailing providers (SendGrid).
"""

import logging
from fastapi import HTTPException, status
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from typing import Optional, Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailDeliveryError(HTTPException):
    """Raised when the email provider fails to dispatch a message."""
    def __init__(self, detail: str = "External email provider failure."):
        super().__init__(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=detail)


class EmailService:
    """Service class for handling email dispatching."""
    
    def __init__(self) -> None:
        self.api_key = settings.SENDGRID_API_KEY
        self.from_email = settings.SENDGRID_FROM_EMAIL
        # Only initialize the client if the key is present to prevent startup crashes in dev
        self.sg = SendGridAPIClient(self.api_key) if self.api_key else None

    def send_email(self, to_email: str, subject: str, html_content: str) -> Optional[Any]:
        """
        Dispatches an email via SendGrid API.
        Fails safely if API keys are misconfigured or external APIs reject the payload.
        """
        if not self.sg:
            logger.warning("SENDGRID_API_KEY not configured. Email dispatch aborted.")
            return None

        message = Mail(
            from_email=self.from_email,
            to_emails=to_email,
            subject=subject,
            html_content=html_content
        )
        
        try:
            response = self.sg.send(message)
            logger.info(f"Email sent to {to_email}. Status Code: {response.status_code}")
            return response
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {str(e)}")
            raise EmailDeliveryError(detail=f"Failed to push message to Sendgrid: {str(e)}")


# Create a unified singleton instance to be imported across modules
email_service = EmailService()
