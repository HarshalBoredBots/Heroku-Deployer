"""App controls: /status /logs /startbot /stopbot /restart /scale /releases /rollback."""

from datetime import datetime, timezone

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.auth import admin_only
from app.bot.conversations import conversation_manager as cm
from app.bot.keyboards import profile_selector
from app.db.repositories import managed_apps as managed_apps_repo
from app.db.repositories import profiles as profiles_repo
from app.security import sanitize_error
from app.services import audit_actions as AA
from app.services import validation as V
from app.services.audit import audit
from app.services.heroku_context import heroku_api_for_profile

_STATE_ICON = {"up": "🟢", "crashed": "🔴", "down": "⚪", "starting": "🟡", "idle": "⚪"}


async def _get_profile_or_selector(message, args: str, prefix: str):
    """Return profile if named, else show a selector keyboard. Returns None in selector case."""
    if args:
        profile = await profiles_repo.get_profile_by_name(args)
        if profile is None:
            await message.reply(f"Profile '<code>{args}</code>' not found.")
            return None
        return profile
    profiles = await profiles_repo.list_profiles()
    if not profiles:
        await message.reply("No profiles yet. Use /createenv first.")
        return None
    await message.reply("Select a profile:", reply_markup=profile_selector(profiles, prefix))
    return None


async def _cmd_status(message, profile) -> None:
    try:
        async with heroku_api_for_profile(profile) as heroku:
            dynos = await heroku.dynos.list(profile["app_name"])
    except Exception as exc:
        await message.reply(f"❌ {sanitize_error(exc)}")
        return
    lines = [f"📊 <b>Status: {profile['name']} ({profile['app_name']})</b>\n"]
    if not dynos:
        lines.append("No dynos running (scaled to 0).")
    for d in dynos:
        state = d.get("state", "unknown")
        icon = _STATE_ICON.get(state, "❔")
        updated = d.get("updated_at", "")[:16].replace("T", " ")
        lines.append(f"<code>{d['name']}</code>  {icon} {state}  ({updated} UTC)")
    await message.reply("\n".join(lines))


async def _cmd_logs(message, profile) -> None:
    try:
        async with heroku_api_for_profile(profile) as heroku:
            session = await heroku.log_sessions.create(profile["app_name"], lines=100)
            text = await heroku.log_sessions.fetch_lines(session["logplex_url"], lines=100)
    except Exception as exc:
        await message.reply(f"❌ {sanitize_error(exc)}")
        return
    markup = InlineKeyboardMarkup([[
        InlineKeyboardButton("🔄 Refresh", callback_data=f"logs_refresh:{profile['id']}")
    ]])
    header = f"📄 <b>Logs: {profile['name']}</b>\n"
    body = f"<pre>{text or '(no log lines)'}</pre>"
    if len(header) + len(body) <= 4096:
        await message.reply(header + body, reply_markup=markup)
    else:
        await message.reply(header, reply_markup=markup)
        chunk = ""
        for line in text.splitlines():
            if len(chunk) + len(line) + 20 > 4000:
                await message.reply(f"<pre>{chunk}</pre>")
                chunk = ""
            chunk += line + "\n"
        if chunk:
            await message.reply(f"<pre>{chunk}</pre>")


async def _cmd_scale_to(message, profile, quantity: int, action: str) -> None:
    try:
        async with heroku_api_for_profile(profile) as heroku:
            await heroku.formation.update(
                profile["app_name"], profile["process_type"], quantity, profile["dyno_type"]
            )
    except Exception as exc:
        await message.reply(f"❌ {sanitize_error(exc)}")
        return
    audit(str(message.from_user.id), action,
          profile_id=profile["id"], profile_name=profile["name"],
          app_name=profile["app_name"], detail=f"scaled to {quantity}")
    await message.reply(f"✅ <b>{profile['name']}</b> scaled to {quantity} dyno(s).")


async def _cmd_releases(message, profile) -> None:
    try:
        async with heroku_api_for_profile(profile) as heroku:
            releases = await heroku.releases.list(profile["app_name"], limit=10)
    except Exception as exc:
        await message.reply(f"❌ {sanitize_error(exc)}")
        return
    lines = [f"📋 <b>Releases: {profile['app_name']}</b>\n"]
    buttons = []
    for r in releases:
        ts = (r.get("created_at") or "")[:16].replace("T", " ")
        desc = (r.get("description") or "")[:40]
        lines.append(f"<b>v{r['version']}</b>  {ts}  {desc}")
        buttons.append([InlineKeyboardButton(
            f"↩️ Rollback to v{r['version']}",
            callback_data=f"rollback_do:{profile['id']}:{r['id']}"
        )])
    await message.reply("\n".join(lines),
                        reply_markup=InlineKeyboardMarkup(buttons) if buttons else None)


async def _cmd_rollback(message, profile) -> None:
    try:
        async with heroku_api_for_profile(profile) as heroku:
            releases = await heroku.releases.list(profile["app_name"], limit=10)
    except Exception as exc:
        await message.reply(f"❌ {sanitize_error(exc)}")
        return
    if not releases:
        await message.reply("No releases found.")
        return
    buttons = [
        [InlineKeyboardButton(f"v{r['version']} — {(r.get('description') or '')[:30]}",
                              callback_data=f"rollback_do:{profile['id']}:{r['id']}")]
        for r in releases
    ]
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="rollback_do:cancel:x")])
    await message.reply(f"↩️ Select a release to roll back <b>{profile['name']}</b> to:",
                        reply_markup=InlineKeyboardMarkup(buttons))


def register(bot) -> None:
    @bot.on_message(filters.command("status"))
    @admin_only
    async def _status(client, message):
        args = message.text.split(maxsplit=1)[1].strip() if len(message.text.split()) > 1 else ""
        profile = await _get_profile_or_selector(message, args, "status_select")
        if profile:
            await _cmd_status(message, profile)

    @bot.on_message(filters.command("logs"))
    @admin_only
    async def _logs(client, message):
        args = message.text.split(maxsplit=1)[1].strip() if len(message.text.split()) > 1 else ""
        profile = await _get_profile_or_selector(message, args, "logs_select")
        if profile:
            await _cmd_logs(message, profile)

    @bot.on_message(filters.command("startbot"))
    @admin_only
    async def _startbot(client, message):
        args = message.text.split(maxsplit=1)[1].strip() if len(message.text.split()) > 1 else ""
        profile = await _get_profile_or_selector(message, args, "start_select")
        if profile:
            await _cmd_scale_to(message, profile, profile["dyno_count"] or 1, AA.APP_STARTED)

    @bot.on_message(filters.command("stopbot"))
    @admin_only
    async def _stopbot(client, message):
        args = message.text.split(maxsplit=1)[1].strip() if len(message.text.split()) > 1 else ""
        profile = await _get_profile_or_selector(message, args, "stop_select")
        if profile:
            await _cmd_scale_to(message, profile, 0, AA.APP_STOPPED)

    @bot.on_message(filters.command("restart"))
    @admin_only
    async def _restart(client, message):
        args = message.text.split(maxsplit=1)[1].strip() if len(message.text.split()) > 1 else ""
        profile = await _get_profile_or_selector(message, args, "restart_select")
        if profile:
            try:
                async with heroku_api_for_profile(profile) as heroku:
                    await heroku.dynos.restart_all(profile["app_name"])
                audit(str(message.from_user.id), AA.APP_RESTARTED,
                      profile_id=profile["id"], profile_name=profile["name"],
                      app_name=profile["app_name"])
                await message.reply(f"✅ Restarted all dynos for <b>{profile['name']}</b>.")
            except Exception as exc:
                await message.reply(f"❌ {sanitize_error(exc)}")

    @bot.on_message(filters.command("scale"))
    @admin_only
    async def _scale(client, message):
        args = message.text.split(maxsplit=1)[1].strip() if len(message.text.split()) > 1 else ""
        profile = await _get_profile_or_selector(message, args, "scale_select")
        if profile:
            await cm.start(message.from_user.id, "scale", "count", profile_id=profile["id"])
            await message.reply(
                f"📈 Current dyno count for <b>{profile['name']}</b>: {profile['dyno_count']}\n"
                "Send the new count (0-100):"
            )

    @bot.on_message(filters.command("releases"))
    @admin_only
    async def _releases(client, message):
        args = message.text.split(maxsplit=1)[1].strip() if len(message.text.split()) > 1 else ""
        profile = await _get_profile_or_selector(message, args, "releases_select")
        if profile:
            await _cmd_releases(message, profile)

    @bot.on_message(filters.command("rollback"))
    @admin_only
    async def _rollback(client, message):
        args = message.text.split(maxsplit=1)[1].strip() if len(message.text.split()) > 1 else ""
        profile = await _get_profile_or_selector(message, args, "rollback_select")
        if profile:
            await _cmd_rollback(message, profile)

    # --- selector callbacks ---
    async def _dispatch(query, prefix: str, profile_id: int):
        profile = await profiles_repo.get_profile_by_id(profile_id)
        if profile is None:
            await query.answer("Profile not found.", show_alert=True)
            return
        message = query.message
        if prefix == "status":
            await _cmd_status(message, profile)
        elif prefix == "logs":
            await _cmd_logs(message, profile)
        elif prefix == "start":
            await _cmd_scale_to(message, profile, profile["dyno_count"] or 1, AA.APP_STARTED)
        elif prefix == "stop":
            await _cmd_scale_to(message, profile, 0, AA.APP_STOPPED)
        elif prefix == "restart":
            try:
                async with heroku_api_for_profile(profile) as heroku:
                    await heroku.dynos.restart_all(profile["app_name"])
                audit(str(query.from_user.id), AA.APP_RESTARTED,
                      profile_id=profile["id"], profile_name=profile["name"],
                      app_name=profile["app_name"])
                await message.reply(f"✅ Restarted all dynos for <b>{profile['name']}</b>.")
            except Exception as exc:
                await message.reply(f"❌ {sanitize_error(exc)}")
        elif prefix == "scale":
            await cm.start(query.from_user.id, "scale", "count", profile_id=profile["id"])
            await message.reply(f"Send the new dyno count for <b>{profile['name']}</b> (0-100):")
        elif prefix == "releases":
            await _cmd_releases(message, profile)
        elif prefix == "rollback":
            await _cmd_rollback(message, profile)

    for prefix in ("status", "logs", "start", "stop", "restart", "scale", "releases", "rollback"):
        @bot.on_callback_query(filters.regex(rf"^{prefix}_select:"))
        @admin_only
        async def _select(client, query, _prefix=prefix):
            value = query.data.split(":", 1)[1]
            await query.answer()
            if value == "cancel":
                await query.message.edit_text("❌ Cancelled.")
                return
            await _dispatch(query, _prefix, int(value))

    @bot.on_callback_query(filters.regex(r"^logs_refresh:"))
    @admin_only
    async def _logs_refresh(client, query):
        await query.answer("Refreshing…")
        profile = await profiles_repo.get_profile_by_id(int(query.data.split(":", 1)[1]))
        if profile:
            await _cmd_logs(query.message, profile)

    @bot.on_callback_query(filters.regex(r"^rollback_do:"))
    @admin_only
    async def _rollback_do(client, query):
        _, profile_id, release_id = query.data.split(":", 2)
        if profile_id == "cancel":
            await query.message.edit_text("❌ Cancelled.")
            await query.answer()
            return
        profile = await profiles_repo.get_profile_by_id(int(profile_id))
        if profile is None:
            await query.answer("Profile not found.", show_alert=True)
            return
        try:
            async with heroku_api_for_profile(profile) as heroku:
                release = await heroku.releases.rollback(profile["app_name"], release_id)
            audit(str(query.from_user.id), AA.APP_ROLLED_BACK,
                  profile_id=profile["id"], profile_name=profile["name"],
                  app_name=profile["app_name"], detail=f"v{release['version']}")
            await query.message.edit_text(
                f"✅ Rolled back <b>{profile['name']}</b> — new release v{release['version']}."
            )
        except Exception as exc:
            await query.message.edit_text(f"❌ {sanitize_error(exc)}")
        await query.answer()


async def handle_scale_text(message, state) -> None:
    user_id = message.from_user.id
    profile = await profiles_repo.get_profile_by_id(state.data["profile_id"])
    if profile is None:
        await cm.clear(user_id)
        await message.reply("Profile no longer exists.")
        return
    try:
        count = V.validate_dyno_count(message.text)
    except ValueError as exc:
        await message.reply(f"❌ {exc}\nTry again:")
        return
    await cm.clear(user_id)
    try:
        async with heroku_api_for_profile(profile) as heroku:
            await heroku.formation.update(
                profile["app_name"], profile["process_type"], count, profile["dyno_type"]
            )
        await profiles_repo.update_profile(profile["id"], {"dyno_count": count})
        audit(str(user_id), AA.APP_SCALED,
              profile_id=profile["id"], profile_name=profile["name"],
              app_name=profile["app_name"], detail=f"scaled to {count}")
        await message.reply(f"✅ <b>{profile['name']}</b> scaled to {count} dyno(s).")
    except Exception as exc:
        await message.reply(f"❌ {sanitize_error(exc)}")
