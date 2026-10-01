"""/deployhistory and /history — deployments and global audit log."""

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.auth import admin_only
from app.bot.formatting import short_commit
from app.db.repositories import audit_logs as audit_repo
from app.db.repositories import deployments as deployments_repo
from app.db.repositories import profiles as profiles_repo

_PAGE_SIZE = 20


def register(bot) -> None:
    @bot.on_message(filters.command("deployhistory"))
    @admin_only
    async def _deployhistory(client, message):
        args = message.text.split(maxsplit=1)[1].strip() if len(message.text.split()) > 1 else ""
        profile = None
        if args:
            profile = await profiles_repo.get_profile_by_name(args)
            if profile is None:
                await message.reply(f"Profile '<code>{args}</code>' not found.")
                return
        if profile is None:
            profiles = await profiles_repo.list_profiles()
            if len(profiles) == 1:
                profile = profiles[0]
            else:
                from app.bot.keyboards import profile_selector
                if not profiles:
                    await message.reply("No profiles yet.")
                    return
                await message.reply("Select a profile:",
                                    reply_markup=profile_selector(profiles, "history_select"))
                return
        deployments = await deployments_repo.list_deployments(profile["id"], limit=10)
        lines = [f"📜 <b>Deployment History: {profile['name']}</b>\n"]
        if not deployments:
            lines.append("No deployments yet.")
        for d in deployments:
            icon = {"success": "✅", "failed": "❌", "running": "⏳"}.get(d["status"], "⚪")
            ts = d["started_at"].strftime("%Y-%m-%d %H:%M")
            info = d["release_version"] or (d["error_message"] or "")[:40]
            lines.append(
                f"#{d['id']}  {icon} {d['status']}  <code>{short_commit(d.get('commit'))}</code>  {ts}  {info}"
            )
        await message.reply("\n".join(lines))

    @bot.on_callback_query(filters.regex(r"^history_select:"))
    @admin_only
    async def _history_select(client, query):
        value = query.data.split(":", 1)[1]
        await query.answer()
        if value == "cancel":
            await query.message.edit_text("❌ Cancelled.")
            return
        profile = await profiles_repo.get_profile_by_id(int(value))
        deployments = await deployments_repo.list_deployments(profile["id"], limit=10)
        lines = [f"📜 <b>Deployment History: {profile['name']}</b>\n"]
        for d in deployments:
            icon = {"success": "✅", "failed": "❌", "running": "⏳"}.get(d["status"], "⚪")
            ts = d["started_at"].strftime("%Y-%m-%d %H:%M")
            lines.append(f"#{d['id']}  {icon} {d['status']}  <code>{short_commit(d.get('commit'))}</code>  {ts}")
        await query.message.edit_text("\n".join(lines))

    @bot.on_message(filters.command("history"))
    @admin_only
    async def _history(client, message):
        await _send_audit_page(message, page=0, edit=False)

    @bot.on_callback_query(filters.regex(r"^history_page:"))
    @admin_only
    async def _history_page(client, query):
        page = int(query.data.split(":", 1)[1])
        await _send_audit_page(query.message, page=page, edit=True)
        await query.answer()


async def _send_audit_page(message, *, page: int, edit: bool) -> None:
    entries = await audit_repo.list_recent(limit=_PAGE_SIZE + 1, skip=page * _PAGE_SIZE)
    has_next = len(entries) > _PAGE_SIZE
    entries = entries[:_PAGE_SIZE]
    lines = [f"📋 <b>Audit Log</b> (page {page + 1})\n"]
    if not entries:
        lines.append("No entries.")
    for e in entries:
        ts = e["created_at"].strftime("%Y-%m-%d %H:%M")
        parts = [ts, e["actor"], e["action"]]
        if e.get("profile_name"):
            parts.append(e["profile_name"])
        if e.get("detail"):
            parts.append(str(e["detail"])[:40])
        lines.append("  ".join(parts))
    buttons = []
    row = []
    if page > 0:
        row.append(InlineKeyboardButton("← Prev", callback_data=f"history_page:{page - 1}"))
    if has_next:
        row.append(InlineKeyboardButton("Next →", callback_data=f"history_page:{page + 1}"))
    if row:
        buttons.append(row)
    markup = InlineKeyboardMarkup(buttons) if buttons else None
    if edit:
        await message.edit_text("\n".join(lines), reply_markup=markup)
    else:
        await message.reply("\n".join(lines), reply_markup=markup)
