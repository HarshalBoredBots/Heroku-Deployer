"""HealthSnapshot repository."""

from datetime import datetime, timezone

from app.db.client import get_db


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def upsert_snapshot(profile_id: int, process_type: str, states: str) -> dict:
    # FIX #5: The original replace_one() built a doc that always contained
    # "last_crash_alert_at": None, which reset the crash-alert cooldown timestamp
    # to None on every health-monitor poll.  This meant the 30-minute cooldown
    # was never respected and admins would be spammed with crash alerts.
    #
    # Fix: use update_one with $set so that only "states" and "polled_at" are
    # written; "last_crash_alert_at" is left untouched (or initialised to None
    # only on first insert via $setOnInsert, which is harmless because it has no
    # value yet).
    await get_db().health_snapshots.update_one(
        {"profile_id": profile_id, "process_type": process_type},
        {
            "$set": {
                "states": states,
                "polled_at": _now(),
            },
            "$setOnInsert": {
                "profile_id": profile_id,
                "process_type": process_type,
                "last_crash_alert_at": None,
            },
        },
        upsert=True,
    )
    # Return a minimal dict consistent with what callers expect.
    return {
        "profile_id": profile_id,
        "process_type": process_type,
        "states": states,
        "polled_at": _now(),
    }


async def get_snapshot(profile_id: int, process_type: str) -> dict | None:
    return await get_db().health_snapshots.find_one(
        {"profile_id": profile_id, "process_type": process_type}
    )


async def update_crash_alert_time(profile_id: int, process_type: str) -> None:
    await get_db().health_snapshots.update_one(
        {"profile_id": profile_id, "process_type": process_type},
        {"$set": {"last_crash_alert_at": _now()}},
    )


async def list_snapshots(profile_id: int) -> list[dict]:
    return await get_db().health_snapshots.find({"profile_id": profile_id}).to_list(None)
