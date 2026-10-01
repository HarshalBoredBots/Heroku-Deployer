"""/importenv — paste a .env block to merge into a profile's env vars."""

from pyrogram import filters

from app.bot.auth import admin_only
from app.bot.conversations import conversation_manager as cm
from app.bot.keyboards import profile_selector
from app.db.repositories import profiles as profiles_repo
from app.services import audit_actions as AA
from app.services.audit import audit
from app.services.env_parser import EnvParseError, parse_env_text


def register(bot) -> None:
    @bot.on_message(filters.command("importenv"))
    @admin_only
    async def _importenv(client, message):
        args = message.text.split(maxsplit=1)[1].strip() if len(message.text.split()) > 1 else ""
        if args:
            profile = await profiles_repo.get_profile_by_name(args)
            if profile is None:
                await message.reply(f"Profile '<code>{args}</code>' not found.")
                return
            await cm.start(message.from_user.id, "importenv", "paste",
                           profile_id=profile["id"])
            await message.reply(
                f"Paste <code>.env</code>-format text for <b>{profile['name']}</b> "
                "(existing keys are overwritten):"
            )
        else:
            profiles = await profiles_repo.list_profiles()
            if not profiles:
                await message.reply("No profiles yet. Use /createenv first.")
                return
            await message.reply("Select a profile to import env vars into:",
                                reply_markup=profile_selector(profiles, "importenv_select"))

    @bot.on_callback_query(filters.regex(r"^importenv_select:"))
    @admin_only
    async def _select(client, query):
        value = query.data.split(":", 1)[1]
        await query.answer()
        if value == "cancel":
            await query.message.edit_text("❌ Cancelled.")
            return
        profile = await profiles_repo.get_profile_by_id(int(value))
        await cm.start(query.from_user.id, "importenv", "paste", profile_id=profile["id"])
        await query.message.edit_text(
            f"Paste <code>.env</code>-format text for <b>{profile['name']}</b>:"
        )


async def handle_step_text(message, state) -> None:
    user_id = message.from_user.id
    profile = await profiles_repo.get_profile_by_id(state.data["profile_id"])
    if profile is None:
        await cm.clear(user_id)
        await message.reply("Profile no longer exists.")
        return
    try:
        env_vars = parse_env_text(message.text)
    except EnvParseError as exc:
        await message.reply(f"❌ {exc}\nTry again:")
        return
    if not env_vars:
        await message.reply("Nothing to import (no KEY=value lines found).")
        await cm.clear(user_id)
        return
    existing = set(await profiles_repo.get_env_var_keys(profile["id"]))
    updated = sum(1 for k in env_vars if k in existing)
    new = len(env_vars) - updated
    await profiles_repo.save_env_vars(profile["id"], env_vars)
    audit(str(user_id), AA.PROFILE_EDITED,
          profile_id=profile["id"], profile_name=profile["name"],
          app_name=profile["app_name"], detail=f"imported {len(env_vars)} env keys")
    await message.reply(f"✅ Imported {len(env_vars)} keys ({updated} updated, {new} new).")
    await cm.clear(user_id)
