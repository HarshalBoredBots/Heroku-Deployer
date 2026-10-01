"""/envs — list env var keys (masked), add/edit/delete."""

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.auth import admin_only
from app.bot.conversations import conversation_manager as cm
from app.bot.keyboards import profile_selector
from app.db.repositories import profiles as profiles_repo
from app.security import validate_env_key, validate_env_value
from app.services import audit_actions as AA
from app.services.audit import audit


def _envs_markup(profile_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("➕ Add", callback_data=f"envs_add:{profile_id}"),
        InlineKeyboardButton("✏️ Edit", callback_data=f"envs_edit:{profile_id}"),
        InlineKeyboardButton("🗑️ Delete", callback_data=f"envs_del:{profile_id}"),
    ]])


async def _send_envs_list(message, profile) -> None:
    keys = await profiles_repo.get_env_var_keys(profile["id"])
    lines = [f"🔑 <b>{profile['name']} — Environment Variables ({len(keys)})</b>\n"]
    lines += [f"• <code>{k}</code>  = ***" for k in keys]
    await message.reply("\n".join(lines), reply_markup=_envs_markup(profile["id"]))


def register(bot) -> None:
    @bot.on_message(filters.command("envs"))
    @admin_only
    async def _envs(client, message):
        args = message.text.split(maxsplit=1)[1].strip() if len(message.text.split()) > 1 else ""
        if args:
            profile = await profiles_repo.get_profile_by_name(args)
            if profile is None:
                await message.reply(f"Profile '<code>{args}</code>' not found.")
                return
            await _send_envs_list(message, profile)
        else:
            profiles = await profiles_repo.list_profiles()
            if not profiles:
                await message.reply("No profiles yet. Use /createenv first.")
                return
            await message.reply("Select a profile:",
                                reply_markup=profile_selector(profiles, "envs_select"))

    @bot.on_callback_query(filters.regex(r"^envs_select:"))
    @admin_only
    async def _select(client, query):
        value = query.data.split(":", 1)[1]
        await query.answer()
        if value == "cancel":
            await query.message.edit_text("❌ Cancelled.")
            return
        profile = await profiles_repo.get_profile_by_id(int(value))
        await _send_envs_list(query.message, profile)

    @bot.on_callback_query(filters.regex(r"^envs_add:"))
    @admin_only
    async def _add(client, query):
        profile_id = int(query.data.split(":", 1)[1])
        await cm.start(query.from_user.id, "envset", "add_key", profile_id=profile_id)
        await query.message.reply("Send the new variable as <code>KEY=value</code>:")
        await query.answer()

    @bot.on_callback_query(filters.regex(r"^envs_edit:"))
    @admin_only
    async def _edit(client, query):
        profile_id = int(query.data.split(":", 1)[1])
        keys = await profiles_repo.get_env_var_keys(profile_id)
        if not keys:
            await query.answer("No env vars to edit.", show_alert=True)
            return
        buttons = [
            [InlineKeyboardButton(k, callback_data=f"envs_editkey:{profile_id}:{k}")]
            for k in keys[:40]
        ]
        await query.message.reply("Select a key to edit:",
                                  reply_markup=InlineKeyboardMarkup(buttons))
        await query.answer()

    @bot.on_callback_query(filters.regex(r"^envs_editkey:"))
    @admin_only
    async def _editkey(client, query):
        _, profile_id, key = query.data.split(":", 2)
        await cm.start(query.from_user.id, "envset", "edit_value",
                       profile_id=int(profile_id), key=key)
        await query.message.reply(f"Send the new value for <code>{key}</code>:")
        await query.answer()

    @bot.on_callback_query(filters.regex(r"^envs_del:"))
    @admin_only
    async def _del(client, query):
        profile_id = int(query.data.split(":", 1)[1])
        keys = await profiles_repo.get_env_var_keys(profile_id)
        if not keys:
            await query.answer("No env vars to delete.", show_alert=True)
            return
        buttons = [
            [InlineKeyboardButton(k, callback_data=f"envs_delkey:{profile_id}:{k}")]
            for k in keys[:40]
        ]
        buttons.append([InlineKeyboardButton("❌ Cancel", callback_data="envs_delcancel")])
        await query.message.reply("Select a key to delete:",
                                  reply_markup=InlineKeyboardMarkup(buttons))
        await query.answer()

    @bot.on_callback_query(filters.regex(r"^envs_delkey:"))
    @admin_only
    async def _delkey(client, query):
        _, profile_id, key = query.data.split(":", 2)
        profile = await profiles_repo.get_profile_by_id(int(profile_id))
        await profiles_repo.delete_env_var(int(profile_id), key)
        if profile:
            audit(str(query.from_user.id), AA.PROFILE_EDITED,
                  profile_id=profile["id"], profile_name=profile["name"],
                  app_name=profile["app_name"], detail=f"deleted env key {key}")
        await query.message.edit_text(f"🗑️ Deleted <code>{key}</code>.")
        await query.answer()

    @bot.on_callback_query(filters.regex(r"^envs_delcancel$"))
    @admin_only
    async def _delcancel(client, query):
        await query.message.edit_text("❌ Cancelled.")
        await query.answer()


async def handle_step_text(message, state) -> None:
    user_id = message.from_user.id
    profile_id = state.data["profile_id"]
    profile = await profiles_repo.get_profile_by_id(profile_id)
    if profile is None:
        await cm.clear(user_id)
        await message.reply("Profile no longer exists.")
        return
    try:
        if state.step == "add_key":
            key, sep, value = message.text.partition("=")
            if not sep:
                raise ValueError("Use the format KEY=value.")
            key = validate_env_key(key)
            value = validate_env_value(value.strip())
        else:  # edit_value
            key = state.data["key"]
            value = validate_env_value(message.text.strip())
        await profiles_repo.save_env_vars(profile_id, {key: value})
        audit(str(user_id), AA.PROFILE_EDITED,
              profile_id=profile["id"], profile_name=profile["name"],
              app_name=profile["app_name"], detail=f"set env key {key}")
        await message.reply(f"✅ Saved <code>{key}</code> = *** for <b>{profile['name']}</b>.")
    except ValueError as exc:
        await message.reply(f"❌ {exc}\nTry again:")
        return
    await cm.clear(user_id)
