"""/deleteenv — delete an env var key from a profile."""

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.auth import admin_only
from app.bot.keyboards import profile_selector
from app.db.repositories import profiles as profiles_repo
from app.services import audit_actions as AA
from app.services.audit import audit


def register(bot) -> None:
    @bot.on_message(filters.command("deleteenv"))
    @admin_only
    async def _deleteenv(client, message):
        args = message.text.split(maxsplit=1)[1].strip() if len(message.text.split()) > 1 else ""
        if args:
            profile = await profiles_repo.get_profile_by_name(args)
            if profile is None:
                await message.reply(f"Profile '<code>{args}</code>' not found.")
                return
            await _key_selector(message, profile)
        else:
            profiles = await profiles_repo.list_profiles()
            if not profiles:
                await message.reply("No profiles yet.")
                return
            await message.reply("Select a profile:",
                                reply_markup=profile_selector(profiles, "deleteenv_select"))

    async def _key_selector(message, profile):
        keys = await profiles_repo.get_env_var_keys(profile["id"])
        if not keys:
            await message.reply(f"No env vars on <b>{profile['name']}</b>.")
            return
        buttons = [
            [InlineKeyboardButton(k, callback_data=f"deleteenv_key:{profile['id']}:{k}")]
            for k in keys[:40]
        ]
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="deleteenv_key:cancel:x")])
        await message.reply(f"Select a key to delete from <b>{profile['name']}</b>:",
                            reply_markup=InlineKeyboardMarkup(buttons))

    @bot.on_callback_query(filters.regex(r"^deleteenv_select:"))
    @admin_only
    async def _select(client, query):
        value = query.data.split(":", 1)[1]
        await query.answer()
        if value == "cancel":
            await query.message.edit_text("❌ Cancelled.")
            return
        profile = await profiles_repo.get_profile_by_id(int(value))
        await _key_selector(query.message, profile)

    @bot.on_callback_query(filters.regex(r"^deleteenv_key:"))
    @admin_only
    async def _key(client, query):
        _, profile_id, key = query.data.split(":", 2)
        if profile_id == "cancel":
            await query.message.edit_text("❌ Cancelled.")
            await query.answer()
            return
        await query.message.edit_text(
            f"⚠️ Delete <code>{key}</code>?",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🗑️ Delete", callback_data=f"deleteenv_confirm:{profile_id}:{key}"),
                InlineKeyboardButton("❌ Cancel", callback_data="deleteenv_confirm:cancel:x"),
            ]]),
        )
        await query.answer()

    @bot.on_callback_query(filters.regex(r"^deleteenv_confirm:"))
    @admin_only
    async def _confirm(client, query):
        _, profile_id, key = query.data.split(":", 2)
        if profile_id == "cancel":
            await query.message.edit_text("❌ Cancelled.")
            await query.answer()
            return
        profile = await profiles_repo.get_profile_by_id(int(profile_id))
        await profiles_repo.delete_env_var(int(profile_id), key)
        if profile:
            audit(str(query.from_user.id), AA.PROFILE_EDITED,
                  profile_id=profile["id"], profile_name=profile["name"],
                  app_name=profile["app_name"], detail=f"deleted env key {key}")
        await query.message.edit_text(f"🗑️ Deleted <code>{key}</code>.")
        await query.answer()
