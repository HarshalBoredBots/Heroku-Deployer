"""Background health monitor: polls dyno states, alerts on crashes."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from app.config import get_settings
from app.db.repositories import accounts as accounts_repo
from app.db.repositories import health_snapshots as snapshots_repo
from app.db.repositories import managed_apps as managed_apps_repo
from app.db.repositories import profiles as profiles_repo
from app.services import audit_actions as AA
from app.services.audit import audit
from app.services.heroku_context import account_heroku_api

logger = logging.getLogger(__name__)

POLL_INTERVAL = 60
ALERT_COOLDOWN = timedelta(minutes=30)

_bot = None


def set_telegram_bot_for_monitor(bot) -> None:
    global _bot
    _bot = bot


async def _alert_admins(text: str) -> None:
    if _bot is None:
        return
    for admin_id in get_settings().admin_ids:
        try:
            await _bot.send_message(admin_id, text)
        except Exception:
            logger.exception("crash_alert_send_failed", extra={"admin_id": admin_id})


async def _check_profile(profile: dict, managed: dict) -> None:
    account = await accounts_repo.get_account_by_id(managed["heroku_account_id"])
    if account is None:
        return
    async with account_heroku_api(account) as heroku:
        dynos = await heroku.dynos.list(managed["app_name"])

    # Group states by process type
    by_process: dict[str, list[str]] = {}
    for d in dynos:
        ptype = d.get("type", "unknown")
        by_process.setdefault(ptype, []).append(d.get("state", "unknown"))

    for ptype, states in by_process.items():
        states_str = ",".join(states)
        await snapshots_repo.upsert_snapshot(profile["id"], ptype, states_str)

        if "crashed" in states:
            snapshot = await snapshots_repo.get_snapshot(profile["id"], ptype)
            last_alert = snapshot.get("last_crash_alert_at") if snapshot else None
            now = datetime.now(timezone.utc)
            if last_alert:
                if last_alert.tzinfo is None:
                    last_alert = last_alert.replace(tzinfo=timezone.utc)
                if now - last_alert < ALERT_COOLDOWN:
                    continue
            await snapshots_repo.update_crash_alert_time(profile["id"], ptype)
            await _alert_admins(
                f"🚨 <b>Dyno crashed</b>\n"
                f"Profile: {profile['name']} (<code>{managed['app_name']}</code>)\n"
                f"Process: <code>{ptype}</code> — states: {states_str}\n"
                f"(No automatic restart will be attempted.)"
            )
            audit("system", AA.DYNO_CRASH_DETECTED,
                  profile_id=profile["id"], profile_name=profile["name"],
                  app_name=managed["app_name"], detail=f"{ptype}: {states_str}")


async def _tick() -> None:
    profiles = {p["id"]: p for p in await profiles_repo.list_profiles()}
    managed_list = await managed_apps_repo.list_all()
    for managed in managed_list:
        profile = profiles.get(managed["profile_id"])
        if profile is None:
            continue
        try:
            await _check_profile(profile, managed)
        except Exception:
            # A single Heroku API error never kills the monitor
            logger.exception("health_check_failed", extra={"profile_id": profile["id"]})


async def run_health_monitor() -> None:
    logger.info("health_monitor_started")
    while True:
        try:
            await _tick()
        except Exception:
            logger.exception("health_monitor_tick_failed")
        await asyncio.sleep(POLL_INTERVAL)
