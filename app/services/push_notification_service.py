"""
Push Notification Service — handles sending push notifications via Expo Push API.
"""

from __future__ import annotations

import asyncio
import anyio
import uuid
from typing import Any, Dict, Optional
import structlog
import httpx

from sqlalchemy.orm import Session
from app.repositories.user_device_token_repo import UserDeviceTokenRepository

logger = structlog.get_logger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
EXPO_RECEIPT_URL = "https://exp.host/--/api/v2/push/getReceipts"

class PushNotificationService:
    """Service layer for sending push notifications using Expo."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.token_repo = UserDeviceTokenRepository(db)

    async def send_push_to_user(
        self, 
        user_id: uuid.UUID, 
        title: str, 
        body: str, 
        data: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Send a push notification to all active Expo devices of a specific user.
        Returns the number of notifications successfully sent.
        Automatically schedules receipt checking after ~5 seconds.
        """
        # Offload synchronous DB call to threadpool to avoid blocking the event loop
        tokens = await anyio.to_thread.run_sync(self.token_repo.get_all_by_user, user_id, True)
        if not tokens:
            logger.info("No active Expo device tokens found for user", user_id=str(user_id))
            return 0
        success_count = 0
        ticket_ids: list[str] = []

        # Reuse a single AsyncClient and send concurrently with bounded concurrency
        sem = asyncio.Semaphore(10)

        async with httpx.AsyncClient() as client:
            async def _send_record(token_record):
                nonlocal success_count
                try:
                    async with sem:
                        success, ticket_id = await self.send_to_token(
                            expo_push_token=token_record.expo_push_token,
                            title=title,
                            body=body,
                            data=data,
                            client=client,
                        )
                except Exception as e:
                    logger.error("Error sending push to token", error=str(e))
                    return

                if success:
                    # update counters and collect ticket ids
                    success_count += 1
                    if ticket_id:
                        ticket_ids.append(ticket_id)
                    # Persist last used timestamp off the event loop
                    await anyio.to_thread.run_sync(self.token_repo.update_last_used, token_record.expo_push_token)
                    logger.info("Push ticket created", ticket_id=ticket_id, token=token_record.expo_push_token[:15])
                else:
                    logger.warning("Failed to send push to token", token=token_record.expo_push_token[:15])

            tasks = [asyncio.create_task(_send_record(t)) for t in tokens]
            if tasks:
                await asyncio.gather(*tasks)

        # Schedule receipt checking in the background (after ~5 seconds)
        if ticket_ids:
            asyncio.create_task(self._check_receipts_delayed(ticket_ids, delay_seconds=5))

        return success_count

    async def send_to_token(
        self, 
        expo_push_token: str, 
        title: str, 
        body: str, 
        data: Optional[Dict[str, Any]] = None
        , client: Optional[httpx.AsyncClient] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Send a push notification to a single Expo device token using httpx.
        Returns (success: bool, ticket_id: Optional[str]).
        """
        expo_push_token = expo_push_token.strip()

        if not expo_push_token.startswith("ExponentPushToken["):
            logger.error("Invalid Expo push token format", token=expo_push_token)
            return False, None

        payload = {
            "to": expo_push_token,
            "title": title,
            "body": body,
            "sound": "default"
        }
        if data:
            payload["data"] = data

        try:
            # Reuse client when provided (avoid creating one per token)
            if client is None:
                async with httpx.AsyncClient() as _client:
                    response = await _client.post(
                        EXPO_PUSH_URL,
                        json=payload,
                        headers={"Accept": "application/json", "Content-Type": "application/json"},
                    )
                    response.raise_for_status()
                    result = response.json()
            else:
                response = await client.post(
                    EXPO_PUSH_URL,
                    json=payload,
                    headers={"Accept": "application/json", "Content-Type": "application/json"},
                )
                response.raise_for_status()
                result = response.json()

            ticket = result.get("data") if isinstance(result, dict) else None

            if isinstance(ticket, dict):
                ticket_id = ticket.get("id")
                if ticket.get("status") == "ok":
                    logger.info("Push notification sent successfully", ticket_id=ticket_id, token=expo_push_token)
                    return True, ticket_id

                error_msg = ticket.get("message", "Unknown error")
                logger.error(
                    "Expo push notification failed",
                    error=error_msg,
                    details=ticket.get("details"),
                    token=expo_push_token,
                )
                return False, None

            if isinstance(ticket, list) and ticket:
                first_ticket = ticket[0]
                if isinstance(first_ticket, dict):
                    ticket_id = first_ticket.get("id")
                    if first_ticket.get("status") == "ok":
                        logger.info("Push notification sent successfully", ticket_id=ticket_id, token=expo_push_token)
                        return True, ticket_id

                    error_msg = first_ticket.get("message", "Unknown error")
                    logger.error(
                        "Expo push notification failed",
                        error=error_msg,
                        details=first_ticket.get("details"),
                        token=expo_push_token,
                    )
                    return False, None

            if isinstance(result, dict) and result.get("errors"):
                logger.error(
                    "Expo push notification request failed",
                    errors=result["errors"],
                    token=expo_push_token,
                )
                return False, None

            return False, None

        except httpx.HTTPStatusError as e:
            logger.error("HTTP error sending push notification", status_code=e.response.status_code, error=str(e))
            return False, None
        except ValueError as e:
            logger.error(
                "Failed to parse Expo push response",
                error=str(e),
                response_text=getattr(response, "text", None),
                token=expo_push_token,
            )
            return False, None
        except Exception as e:
            logger.error("Unexpected error sending push notification", error=str(e), token=expo_push_token)
            return False, None

    async def get_push_receipt(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch the push receipt from Expo for a given ticket ID.
        Returns the receipt data or None if not available yet.
        
        Receipt status can be:
        - 'ok': Delivered to FCM/APNs
        - 'error': Failed (check details.error for reason like DeviceNotRegistered)
        """
        if not ticket_id:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    EXPO_RECEIPT_URL,
                    json={"ids": [ticket_id]},
                    headers={"Accept": "application/json", "Content-Type": "application/json"}
                )
                response.raise_for_status()

                result = response.json()
                receipts = result.get("data", {})

                if isinstance(receipts, dict) and ticket_id in receipts:
                    receipt = receipts[ticket_id]
                    status = receipt.get("status")
                    
                    if status == "ok":
                        logger.info("Push receipt: delivery successful", ticket_id=ticket_id)
                        return receipt
                    elif status == "error":
                        error_msg = receipt.get("message", "Unknown error")
                        error_code = receipt.get("details", {}).get("error", "Unknown")
                        logger.error(
                            "Push receipt: delivery failed",
                            ticket_id=ticket_id,
                            error=error_msg,
                            error_code=error_code,
                            details=receipt.get("details")
                        )
                        return receipt
                    else:
                        logger.info("Push receipt: not available yet", ticket_id=ticket_id, status=status)
                        return receipt
                else:
                    logger.info("Push receipt: not ready yet", ticket_id=ticket_id)
                    return None

        except httpx.HTTPStatusError as e:
            logger.error("HTTP error getting push receipt", status_code=e.response.status_code, ticket_id=ticket_id)
            return None
        except Exception as e:
            logger.error("Unexpected error getting push receipt", error=str(e), ticket_id=ticket_id)
            return None

    async def get_push_receipts_batch(self, ticket_ids: list[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Fetch push receipts for multiple ticket IDs in one request.
        Returns a dict mapping ticket_id -> receipt data.
        """
        if not ticket_ids:
            return {}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    EXPO_RECEIPT_URL,
                    json={"ids": ticket_ids},
                    headers={"Accept": "application/json", "Content-Type": "application/json"}
                )
                response.raise_for_status()

                result = response.json()
                receipts = result.get("data", {})

                summary = {}
                for ticket_id in ticket_ids:
                    if ticket_id in receipts:
                        receipt = receipts[ticket_id]
                        status = receipt.get("status")
                        summary[ticket_id] = receipt
                        
                        if status == "ok":
                            logger.info("Push receipt: delivery successful", ticket_id=ticket_id)
                        elif status == "error":
                            error_code = receipt.get("details", {}).get("error", "Unknown")
                            logger.error(
                                "Push receipt: delivery failed",
                                ticket_id=ticket_id,
                                error=receipt.get("message"),
                                error_code=error_code
                            )
                    else:
                        summary[ticket_id] = None
                        logger.info("Push receipt: not ready yet", ticket_id=ticket_id)

                return summary

        except httpx.HTTPStatusError as e:
            logger.error("HTTP error getting push receipts batch", status_code=e.response.status_code)
            return {}
        except Exception as e:
            logger.error("Unexpected error getting push receipts batch", error=str(e))
            return {}

    async def _check_receipts_delayed(self, ticket_ids: list[str], delay_seconds: int = 5) -> None:
        """
        Background task: Wait for a delay, then check push receipts and log results.
        This helps diagnose delivery failures without blocking the main request.
        """
        try:
            await asyncio.sleep(delay_seconds)
            logger.info("Checking push receipts", ticket_count=len(ticket_ids))
            
            results = await self.get_push_receipts_batch(ticket_ids)
            
            ok_count = 0
            error_count = 0
            
            for ticket_id, receipt in results.items():
                if receipt is None:
                    logger.info("Push receipt: still not available", ticket_id=ticket_id)
                    continue
                    
                status = receipt.get("status")
                if status == "ok":
                    ok_count += 1
                    logger.info("✅ Push receipt OK: notification delivered to FCM/APNs", ticket_id=ticket_id)
                elif status == "error":
                    error_count += 1
                    error_code = receipt.get("details", {}).get("error", "Unknown")
                    error_msg = receipt.get("message", "Unknown error")
                    
                    if error_code == "DeviceNotRegistered":
                        logger.warning(
                            "❌ Push receipt FAILED: Device no longer registered (may have uninstalled app or revoked permissions)",
                            ticket_id=ticket_id,
                            error=error_code
                        )
                    elif error_code == "InvalidCredentials":
                        logger.error(
                            "❌ Push receipt FAILED: Invalid FCM/APNs credentials in your Expo project",
                            ticket_id=ticket_id,
                            error=error_code,
                            message=error_msg
                        )
                    elif error_code == "MessageTooBig":
                        logger.error(
                            "❌ Push receipt FAILED: Notification payload too large (max 4096 bytes)",
                            ticket_id=ticket_id,
                            error=error_code
                        )
                    elif error_code == "MessageRateExceeded":
                        logger.warning(
                            "❌ Push receipt FAILED: Sending too fast to this device (rate limited)",
                            ticket_id=ticket_id,
                            error=error_code
                        )
                    else:
                        logger.error(
                            "❌ Push receipt FAILED: Delivery error",
                            ticket_id=ticket_id,
                            error=error_code,
                            message=error_msg
                        )
            
            logger.info(
                "Push receipt check complete",
                ticket_count=len(ticket_ids),
                ok_count=ok_count,
                error_count=error_count,
                not_ready_count=len(ticket_ids) - ok_count - error_count
            )
            
        except Exception as e:
            logger.error("Error in delayed receipt check", error=str(e))
