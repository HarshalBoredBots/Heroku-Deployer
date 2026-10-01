"""Deployment repository."""

from datetime import datetime, timezone

from app.db.client import get_db, next_id


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def create_deployment(profile_id: int, branch: str, source: str) -> dict:
    doc = {
        "id": await next_id("deployments"),
        "profile_id": profile_id,
        "heroku_app_id": None,
        "commit": None,
        "branch": branch,
        "source": source,
        "status": "running",
        "stage": "pending",
        "release_version": None,
        "started_at": _now(),
        "finished_at": None,
        "error_message": None,
    }
    await get_db().deployments.insert_one(doc)
    return doc


async def get_deployment_by_id(deployment_id: int) -> dict | None:
    return await get_db().deployments.find_one({"id": deployment_id})


async def update_deployment_stage(deployment_id: int, stage: str) -> None:
    await get_db().deployments.update_one(
        {"id": deployment_id}, {"$set": {"stage": stage}}
    )


async def finish_deployment(
    deployment_id: int,
    *,
    status: str,
    release_version: str | None = None,
    error_message: str | None = None,
) -> None:
    await get_db().deployments.update_one(
        {"id": deployment_id},
        {"$set": {
            "status": status,
            "release_version": release_version,
            "error_message": error_message,
            "finished_at": _now(),
        }},
    )


async def get_last_successful_deployment(profile_id: int, commit: str) -> dict | None:
    return await get_db().deployments.find_one(
        {"profile_id": profile_id, "commit": commit, "status": "success"}
    )


async def list_deployments(profile_id: int, limit: int = 10) -> list[dict]:
    return (
        await get_db()
        .deployments.find({"profile_id": profile_id})
        .sort("id", -1)
        .limit(limit)
        .to_list(None)
    )


async def update_heroku_app_id(deployment_id: int, heroku_app_id: str) -> None:
    await get_db().deployments.update_one(
        {"id": deployment_id}, {"$set": {"heroku_app_id": heroku_app_id}}
    )


async def set_commit(deployment_id: int, commit: str) -> None:
    await get_db().deployments.update_one(
        {"id": deployment_id}, {"$set": {"commit": commit}}
    )
