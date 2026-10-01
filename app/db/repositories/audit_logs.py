"""AuditLog repository."""

from datetime import datetime, timezone

from app.db.client import get_db


async def write(
    actor: str,
    action: str,
    *,
    profile_id: int | None = None,
    profile_name: str | None = None,
    app_name: str | None = None,
    detail: str | None = None,
) -> None:
    doc = {
        "actor": actor,
        "action": action,
        "profile_id": profile_id,
        "profile_name": profile_name,
        "app_name": app_name,
        "detail": detail,
        "created_at": datetime.now(timezone.utc),
    }
    await get_db().audit_logs.insert_one(doc)


async def list_recent(*, profile_id: int | None = None, limit: int = 20, skip: int = 0) -> list[dict]:
    query = {"profile_id": profile_id} if profile_id is not None else {}
    return (
        await get_db()
        .audit_logs.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(limit)
        .to_list(None)
    )
