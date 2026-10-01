"""DeploymentProfile repository with encrypted env vars."""

from datetime import datetime, timezone

from app.crypto import decrypt_value, encrypt_value
from app.db.client import get_db, next_id
from app.security import validate_env_key, validate_env_value


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_profile(data: dict) -> dict:
    db = get_db()
    doc = {
        "id": await next_id("deployment_profiles"),
        "name": data["name"],
        "app_name": data["app_name"],
        "repository": data["repository"],
        "branch": data["branch"],
        "start_command": data["start_command"],
        "process_type": data.get("process_type", "worker"),
        "dyno_count": int(data.get("dyno_count", 1)),
        "dyno_type": data["dyno_type"],
        "region": data["region"],
        "auto_deploy": bool(data.get("auto_deploy", False)),
        "heroku_account_id": data["heroku_account_id"],
        "created_at": _now(),
        "updated_at": _now(),
    }
    await db.deployment_profiles.insert_one(doc)
    return doc


async def get_profile_by_id(profile_id: int) -> dict | None:
    return await get_db().deployment_profiles.find_one({"id": profile_id})


async def get_profile_by_name(name: str) -> dict | None:
    return await get_db().deployment_profiles.find_one({"name": name})


async def get_profile_by_app_name(app_name: str) -> dict | None:
    return await get_db().deployment_profiles.find_one({"app_name": app_name})


async def list_profiles() -> list[dict]:
    return await get_db().deployment_profiles.find().sort("id", 1).to_list(None)


async def find_auto_deploy_profiles(repository: str, branch: str) -> list[dict]:
    """Match auto_deploy profiles for a repo+branch (case-insensitive, .git stripped)."""
    repo_norm = repository.rstrip("/").removesuffix(".git").lower()
    profiles = await get_db().deployment_profiles.find({"auto_deploy": True}).to_list(None)
    return [
        p for p in profiles
        if p["repository"].rstrip("/").removesuffix(".git").lower() == repo_norm
        and p["branch"].lower() == branch.lower()
    ]


async def update_profile(profile_id: int, updates: dict) -> dict | None:
    updates["updated_at"] = _now()
    return await get_db().deployment_profiles.find_one_and_update(
        {"id": profile_id}, {"$set": updates}, return_document=True
    )


async def delete_profile(profile_id: int) -> bool:
    db = get_db()
    result = await db.deployment_profiles.delete_one({"id": profile_id})
    if result.deleted_count:
        await db.profile_env_vars.delete_many({"profile_id": profile_id})
        await db.deployments.delete_many({"profile_id": profile_id})
        await db.health_snapshots.delete_many({"profile_id": profile_id})
        # FIX #19: The original delete_profile() did not remove managed_apps
        # documents for the deleted profile.  Orphaned managed_apps entries
        # caused the health monitor to keep polling non-existent apps and could
        # trigger spurious errors on subsequent deploys.
        await db.managed_apps.delete_many({"profile_id": profile_id})
    return result.deleted_count > 0


async def save_env_vars(profile_id: int, env_vars: dict[str, str]) -> None:
    db = get_db()
    for key, value in env_vars.items():
        key = validate_env_key(key)
        value = validate_env_value(value)
        await db.profile_env_vars.update_one(
            {"profile_id": profile_id, "key": key},
            {
                "$set": {"encrypted_value": encrypt_value(value), "updated_at": _now()},
                "$setOnInsert": {"created_at": _now()},
            },
            upsert=True,
        )


async def get_env_vars_decrypted(profile_id: int) -> dict[str, str]:
    docs = await get_db().profile_env_vars.find({"profile_id": profile_id}).to_list(None)
    return {d["key"]: decrypt_value(d["encrypted_value"]) for d in docs}


async def get_env_var_keys(profile_id: int) -> list[str]:
    docs = (
        await get_db().profile_env_vars.find({"profile_id": profile_id}).sort("key", 1).to_list(None)
    )
    return [d["key"] for d in docs]


async def delete_env_var(profile_id: int, key: str) -> bool:
    result = await get_db().profile_env_vars.delete_one({"profile_id": profile_id, "key": key})
    return result.deleted_count > 0


async def count_env_vars(profile_id: int) -> int:
    return await get_db().profile_env_vars.count_documents({"profile_id": profile_id})
