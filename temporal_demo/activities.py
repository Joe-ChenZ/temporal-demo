import asyncio
import logging

from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn
async def send_email(user_id: str) -> str:
    logger.info("sending email to %s", user_id)
    await asyncio.sleep(3)
    logger.info("email sent to %s", user_id)
    return f"email:{user_id}"


@activity.defn
async def send_fcm(user_id: str) -> str:
    attempt = activity.info().attempt
    logger.info("sending FCM to %s (attempt %d)", user_id, attempt)

    if attempt < 3:
        raise Exception("FCM service unavailable")

    await asyncio.sleep(3)
    logger.info("FCM sent to %s", user_id)
    return f"fcm:{user_id}"


@activity.defn
async def send_socketio(user_id: str) -> str:
    logger.info("sending SIO push to %s", user_id)
    await asyncio.sleep(2)
    logger.info("SIO sent to %s", user_id)
    return f"sio:{user_id}"
