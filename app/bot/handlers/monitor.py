"""/monitorstatus — health snapshot for all profiles."""

from datetime import datetime, timezone

from pyrogram import filters

from app.bot.auth import admin_only
from app.db.repositories import health_snapshots as snapshots_repo
from app.db.repositories import profiles as profiles_repo


def _ago(ts) -> str:
    if ts is None:
        return "never"
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - ts
    minutes = int(delta.total_seconds() // 60)
    return f"{minutes}m ago" if minutes >= 1 else "just now"


def register(bot) -> None:
    @bot.on_message(filters.command("monitorstatus"))
    @admin_only
    async def _monitorstatus(client, message):
        profiles = await profiles_repo.list_profiles()
        lines = ["🏥 <b>Health Monitor Status</b>\n"]
        if not profiles:
            lines.append("No profiles yet.")
        for p in profiles:
            lines.append(f"<b>{p['name']}</b> (<code>{p['app_name']}</code>)")
            snapshots = await snapshots_repo.list_snapshots(p["id"])
            if not snapshots:
                lines.append("  No data yet")
                continue
            for s in snapshots:
                crashed = "crashed" in s["states"]
                icon = "🔴" if crashed else "🟢"
                line = f"  {s['process_type']}: {icon} {s['states']}  (polled {_ago(s['polled_at'])})"
                if s.get("last_crash_alert_at"):
                    line += f"  ⚠️ alert sent {_ago(s['last_crash_alert_at'])}"
                lines.append(line)
            lines.append("")
        await message.reply("\n".join(lines))
