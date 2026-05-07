"""
Unit tests for Email Service.
Focuses on verifying integration logic with external providers (SendGrid) 
while mocking the actual network calls.
"""

import pytest
from unittest.mock import MagicMock, patch
from app.services.email_service import EmailService, EmailDeliveryError


@pytest.fixture
def mocked_email_service():
    """
    Fixture that provides an EmailService instance with a mocked SendGrid client.
    Uses patch to prevent real configuration from interfering.
    """
    with patch("app.services.email_service.SendGridAPIClient") as mock_client_class:
        # Mock settings to ensure consistency during tests
        with patch("app.services.email_service.settings") as mock_settings:
            mock_settings.SENDGRID_API_KEY = "test_api_key_123"
            mock_settings.SENDGRID_FROM_EMAIL = "noreply@marketplace.com"
            
            # Initialize service - this will use the mocked settings
            service = EmailService()
            
            # The instance of SendGridAPIClient created inside EmailService
            mock_sg_instance = mock_client_class.return_value
            
            yield service, mock_sg_instance, mock_settings


# ── SUCCESS Tests ─────────────────────────────────────────────────────────

def test_send_email_success(mocked_email_service):
    """Test successful email dispatch via SendGrid."""
    # Arrange
    service, mock_sg, _ = mocked_email_service
    mock_response = MagicMock()
    mock_response.status_code = 202
    mock_sg.send.return_value = mock_response

    to_email = "buyer@gmail.com"
    subject = "Order Confirmation"
    content = "<h1>Your order is confirmed!</h1>"

    # Act
    result = service.send_email(to_email, subject, content)

    # Assert
    assert result.status_code == 202
    mock_sg.send.assert_called_once()
    
    # Verify that the Mail object (first argument to send) contains our data
    # SendGrid's Mail object is complex, but we can verify it was called
    sent_message = mock_sg.send.call_args[0][0]
    assert hasattr(sent_message, "from_email")
    assert hasattr(sent_message, "subject")
    assert sent_message.subject.get() == subject


# ── CONFIGURATION Tests ───────────────────────────────────────────────────

def test_send_email_no_api_key():
    """Test that email dispatch is aborted gracefully if API key is missing."""
    # Arrange
    with patch("app.services.email_service.settings") as mock_settings:
        mock_settings.SENDGRID_API_KEY = None
        mock_settings.SENDGRID_FROM_EMAIL = "test@test.com"
        
        service = EmailService()
        
        # Act
        result = service.send_email("test@test.com", "Subject", "Body")
        
        # Assert
        assert result is None


# ── FAILURE Tests ─────────────────────────────────────────────────────────

def test_send_email_external_failure(mocked_email_service):
    """Test that external provider exceptions are caught and re-raised as EmailDeliveryError."""
    # Arrange
    service, mock_sg, _ = mocked_email_service
    mock_sg.send.side_effect = Exception("API Connection Timeout")

    # Act & Assert
    with pytest.raises(EmailDeliveryError) as exc_info:
        service.send_email("test@test.com", "Subject", "Body")
    
    assert "Failed to push message to Sendgrid" in str(exc_info.value.detail)
    assert "API Connection Timeout" in str(exc_info.value.detail)


def test_send_email_empty_recipient(mocked_email_service):
    """Test behavior with empty recipient (Mail class might raise error)."""
    # Arrange
    service, mock_sg, _ = mocked_email_service
    # If the Mail class or sg.send raises an error due to invalid params
    mock_sg.send.side_effect = Exception("Invalid to_email")

    # Act & Assert
    with pytest.raises(EmailDeliveryError):
        service.send_email("", "Subject", "Body")
