"""ManagedApp repository."""

from datetime import datetime, timezone

from app.db.client import get_db


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def register_managed_app(
    profile_id: int, heroku_app_id: str, app_name: str, heroku_account_id: int
) -> dict:
    doc = {
        "heroku_app_id": heroku_app_id,
        "app_name": app_name,
        "profile_id": profile_id,
        "heroku_account_id": heroku_account_id,
        "created_at": _now(),
        "updated_at": _now(),
    }
    await get_db().managed_apps.update_one(
        {"profile_id": profile_id}, {"$set": doc}, upsert=True
    )
    return doc


async def get_by_profile(profile_id: int) -> dict | None:
    return await get_db().managed_apps.find_one({"profile_id": profile_id})


async def get_by_heroku_app_id(heroku_app_id: str) -> dict | None:
    return await get_db().managed_apps.find_one({"heroku_app_id": heroku_app_id})


async def delete_managed_app(profile_id: int) -> bool:
    result = await get_db().managed_apps.delete_one({"profile_id": profile_id})
    return result.deleted_count > 0


async def list_all() -> list[dict]:
    return await get_db().managed_apps.find().to_list(None)
