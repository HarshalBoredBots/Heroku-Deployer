"""/deleteapp — destroy the Heroku app and the profile."""

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.auth import admin_only
from app.bot.keyboards import profile_selector
from app.db.repositories import managed_apps as managed_apps_repo
from app.db.repositories import profiles as profiles_repo
from app.security import sanitize_error
from app.services import audit_actions as AA
from app.services.audit import audit
from app.services.heroku_context import heroku_api_for_profile


def register(bot) -> None:
    @bot.on_message(filters.command("deleteapp"))
    @admin_only
    async def _deleteapp(client, message):
        profiles = await profiles_repo.list_profiles()
        if not profiles:
            await message.reply("No profiles yet.")
            return
        args = message.text.split(maxsplit=1)[1].strip() if len(message.text.split()) > 1 else ""
        if args:
            profile = await profiles_repo.get_profile_by_name(args)
            if profile is None:
                await message.reply(f"Profile '<code>{args}</code>' not found.")
                return
            await _confirm_prompt(message, profile)
        else:
            await message.reply("Select a profile to delete:",
                                reply_markup=profile_selector(profiles, "deleteapp_select"))

    async def _confirm_prompt(message, profile):
        await message.reply(
            f"⚠️ This will permanently delete <b>{profile['name']}</b> and the Heroku app "
            f"<code>{profile['app_name']}</code>. This cannot be undone.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_app_confirm:{profile['id']}"),
                InlineKeyboardButton("❌ Cancel", callback_data="delete_app_confirm:cancel"),
            ]]),
        )

    @bot.on_callback_query(filters.regex(r"^deleteapp_select:"))
    @admin_only
    async def _select(client, query):
        value = query.data.split(":", 1)[1]
        await query.answer()
        if value == "cancel":
            await query.message.edit_text("❌ Cancelled.")
            return
        profile = await profiles_repo.get_profile_by_id(int(value))
        await query.message.edit_text(
            f"⚠️ This will permanently delete <b>{profile['name']}</b> and the Heroku app "
            f"<code>{profile['app_name']}</code>. This cannot be undone.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🗑️ Delete", callback_data=f"delete_app_confirm:{profile['id']}"),
                InlineKeyboardButton("❌ Cancel", callback_data="delete_app_confirm:cancel"),
            ]]),
        )

    @bot.on_callback_query(filters.regex(r"^delete_app_confirm:"))
    @admin_only
    async def _confirm(client, query):
        value = query.data.split(":", 1)[1]
        if value == "cancel":
            await query.message.edit_text("❌ Cancelled.")
            await query.answer()
            return
        profile = await profiles_repo.get_profile_by_id(int(value))
        if profile is None:
            await query.message.edit_text("Profile not found.")
            await query.answer()
            return
        errors = []
        managed = await managed_apps_repo.get_by_profile(profile["id"])
        if managed:
            try:
                async with heroku_api_for_profile(profile) as heroku:
                    await heroku.apps.delete(managed["app_name"])
            except Exception as exc:
                errors.append(sanitize_error(exc))
            await managed_apps_repo.delete_managed_app(profile["id"])
        await profiles_repo.delete_profile(profile["id"])
        audit(str(query.from_user.id), AA.APP_DELETED,
              profile_id=profile["id"], profile_name=profile["name"],
              app_name=profile["app_name"])
        text = f"🗑️ Deleted <b>{profile['name']}</b> and its Heroku app."
        if errors:
            text += f"\n⚠️ Heroku deletion reported: <code>{errors[0]}</code>"
        await query.message.edit_text(text)
        await query.answer()
