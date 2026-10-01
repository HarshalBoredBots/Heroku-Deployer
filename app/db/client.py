"""Motor client lifecycle and index creation."""

import logging

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING

from app.config import get_settings

logger = logging.getLogger(__name__)

_client: AsyncIOMotorClient | None = None
_db: AsyncIOMotorDatabase | None = None


async def init_db() -> None:
    """Connect to MongoDB, verify with ping, create all indexes."""
    global _client, _db
    settings = get_settings()
    _client = AsyncIOMotorClient(settings.mongodb_uri)
    await _client.admin.command("ping")
    _db = _client[settings.mongodb_database]
    await _create_indexes(_db)
    logger.info("mongodb_connected", extra={"database": settings.mongodb_database})


async def _create_indexes(db: AsyncIOMotorDatabase) -> None:
    await db.heroku_accounts.create_index([("name", ASCENDING)], unique=True)
    await db.heroku_accounts.create_index([("is_default", ASCENDING)])

    await db.deployment_profiles.create_index([("name", ASCENDING)], unique=True)
    await db.deployment_profiles.create_index([("app_name", ASCENDING)], unique=True)
    await db.deployment_profiles.create_index([("heroku_account_id", ASCENDING)])

    await db.profile_env_vars.create_index(
        [("profile_id", ASCENDING), ("key", ASCENDING)], unique=True
    )

    await db.deployments.create_index([("profile_id", ASCENDING)])
    await db.deployments.create_index([("status", ASCENDING)])
    await db.deployments.create_index([("commit", ASCENDING)])
    await db.deployments.create_index([("started_at", DESCENDING)])

    await db.managed_apps.create_index([("heroku_app_id", ASCENDING)], unique=True)
    await db.managed_apps.create_index([("app_name", ASCENDING)], unique=True)
    await db.managed_apps.create_index([("profile_id", ASCENDING)], unique=True)

    await db.audit_logs.create_index([("actor", ASCENDING)])
    await db.audit_logs.create_index([("action", ASCENDING)])
    await db.audit_logs.create_index([("profile_id", ASCENDING)])
    await db.audit_logs.create_index([("created_at", DESCENDING)])

    await db.health_snapshots.create_index(
        [("profile_id", ASCENDING), ("process_type", ASCENDING)], unique=True
    )

    await db.webhook_deliveries.create_index([("delivery_id", ASCENDING)], unique=True)
    await db.webhook_deliveries.create_index(
        [("received_at", ASCENDING)], expireAfterSeconds=30 * 24 * 3600
    )


async def close_db() -> None:
    global _client, _db
    if _client is not None:
        _client.close()
    _client = None
    _db = None


def get_db() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db


async def next_id(counter_name: str) -> int:
    """Auto-incrementing readable integer ID from the counters collection."""
    doc = await get_db().counters.find_one_and_update(
        {"_id": counter_name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    return int(doc["seq"])
