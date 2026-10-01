"""Webhook delivery idempotency."""

from datetime import datetime, timezone

from pymongo.errors import DuplicateKeyError

from app.db.client import get_db


async def check_and_record(delivery_id: str, event_type: str, repository: str, ref: str) -> bool:
    """Atomically insert the delivery. Returns True if NEW, False if duplicate."""
    try:
        await get_db().webhook_deliveries.insert_one({
            "delivery_id": delivery_id,
            "event_type": event_type,
            "repository": repository,
            "ref": ref,
            "received_at": datetime.now(timezone.utc),
        })
        return True
    except DuplicateKeyError:
        return False
