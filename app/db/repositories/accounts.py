"""HerokuAccount repository."""

from datetime import datetime, timezone

from app.crypto import encrypt_value
from app.config import get_settings
from app.db.client import get_db, next_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def ensure_default_account() -> None:
    db = get_db()
    count = await db.heroku_accounts.count_documents({})
    if count == 0:
        key_enc = encrypt_value(get_settings().heroku_api_key)
        await create_account("default", key_enc)
        default = await get_account_by_name("default")
        if default:
            await set_default_account(default["id"])


async def create_account(name: str, api_key_encrypted: str) -> dict:
    db = get_db()
    doc = {
        "id": await next_id("heroku_accounts"),
        "name": name,
        "api_key_encrypted": api_key_encrypted,
        "is_default": False,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.heroku_accounts.insert_one(doc)
    return doc


async def get_account_by_id(account_id: int) -> dict | None:
    return await get_db().heroku_accounts.find_one({"id": account_id})


async def get_account_by_name(name: str) -> dict | None:
    return await get_db().heroku_accounts.find_one({"name": name})


async def list_accounts() -> list[dict]:
    return await get_db().heroku_accounts.find().sort("id", 1).to_list(None)


async def remove_account(account_id: int) -> bool:
    result = await get_db().heroku_accounts.delete_one({"id": account_id})
    return result.deleted_count > 0


async def set_default_account(account_id: int) -> None:
    db = get_db()
    await db.heroku_accounts.update_many({}, {"$set": {"is_default": False}})
    await db.heroku_accounts.update_one(
        {"id": account_id}, {"$set": {"is_default": True, "updated_at": _now()}}
    )


async def get_default_account() -> dict | None:
    return await get_db().heroku_accounts.find_one({"is_default": True})
