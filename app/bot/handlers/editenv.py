"""/editenv — edit an existing profile's fields."""

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.auth import admin_only
from app.bot.conversations import conversation_manager as cm
from app.bot.keyboards import profile_selector
from app.db.repositories import profiles as profiles_repo
from app.services import audit_actions as AA
from app.services import validation as V
from app.services.audit import audit
from app.services.env_parser import parse_env_text

FLOW = "editenv"

_EDITABLE_FIELDS = [
    ("name", "Profile name"), ("app_name", "App name"), ("repository", "Repository"),
    ("branch", "Branch"), ("start_command", "Start command"),
    ("process_type", "Process type"), ("dyno_count", "Dyno count"),
    ("dyno_type", "Dyno type"), ("region", "Region"),
    ("auto_deploy", "Auto-deploy (yes/no)"), ("env_vars", "Environment variables"),
]

_VALIDATORS = {
    "app_name": V.validate_app_name,
    "repository": V.validate_repo_url,
    "branch": V.validate_branch,
    "start_command": V.validate_start_command,
    "process_type": V.validate_process_type,
    "dyno_count": V.validate_dyno_count,
}


def register(bot) -> None:
    @bot.on_message(filters.command("editenv"))
    @admin_only
    async def _editenv(client, message):
        profiles = await profiles_repo.list_profiles()
        if not profiles:
            await message.reply("No profiles to edit. Use /createenv first.")
            return
        await message.reply("Select a profile to edit:",
                            reply_markup=profile_selector(profiles, "editenv"))

    @bot.on_callback_query(filters.regex(r"^editenv:"))
    @admin_only
    async def _select(client, query):
        value = query.data.split(":", 1)[1]
        if value == "cancel":
            await query.message.edit_text("❌ Cancelled.")
            await query.answer()
            return
        profile = await profiles_repo.get_profile_by_id(int(value))
        if profile is None:
            await query.answer("Profile not found.", show_alert=True)
            return
        await cm.start(query.from_user.id, FLOW, "pick_field", profile_id=profile["id"])
        buttons = [
            [InlineKeyboardButton(label, callback_data=f"editfield:{field}")]
            for field, label in _EDITABLE_FIELDS
        ]
        buttons.append([InlineKeyboardButton("❌ Done", callback_data="editfield:done")])
        await query.message.edit_text(
            f"✏️ Editing <b>{profile['name']}</b> — pick a field:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        await query.answer()

    @bot.on_callback_query(filters.regex(r"^editfield:"))
    @admin_only
    async def _field(client, query):
        state = await cm.get(query.from_user.id)
        if state is None or state.flow != FLOW:
            await query.answer("No active edit session.")
            return
        field = query.data.split(":", 1)[1]
        if field == "done":
            await cm.clear(query.from_user.id)
            await query.message.edit_text("✅ Done editing.")
            await query.answer()
            return
        await cm.update_data(query.from_user.id, edit_field=field)
        await cm.set_step(query.from_user.id, "new_value")
        prompt = "Paste new value"
        if field == "env_vars":
            prompt = "Paste .env-format text (merged — last value wins on duplicates)"
        elif field == "auto_deploy":
            prompt = "Send <code>yes</code> or <code>no</code>"
        await query.message.edit_text(f"✏️ <b>{field}</b>: {prompt}:")
        await query.answer()


async def handle_step_text(message, state) -> None:
    user_id = message.from_user.id
    text = message.text.strip()
    profile_id = state.data["profile_id"]
    field = state.data.get("edit_field")

    profile = await profiles_repo.get_profile_by_id(profile_id)
    if profile is None:
        await cm.clear(user_id)
        await message.reply("Profile no longer exists.")
        return

    try:
        if field == "env_vars":
            env_vars = parse_env_text(text)
            await profiles_repo.save_env_vars(profile_id, env_vars)
            await message.reply(f"✅ Saved {len(env_vars)} env var(s) for <b>{profile['name']}</b> (values encrypted).")
        elif field == "auto_deploy":
            value = text.lower() in ("yes", "y", "true", "1", "on")
            await profiles_repo.update_profile(profile_id, {"auto_deploy": value})
            await message.reply(f"✅ Auto-deploy {'enabled' if value else 'disabled'} for <b>{profile['name']}</b>.")
        else:
            validator = _VALIDATORS.get(field)
            value = validator(text) if validator else text
            if field == "name" and not 1 <= len(value) <= 64:
                raise ValueError("Profile name must be 1-64 characters.")
            await profiles_repo.update_profile(profile_id, {field: value})
            await message.reply(f"✅ Updated <b>{field}</b> for <b>{profile['name']}</b>.")
        audit(str(user_id), AA.PROFILE_EDITED,
              profile_id=profile_id, profile_name=profile["name"],
              app_name=profile["app_name"], detail=field)
    except ValueError as exc:
        await message.reply(f"❌ {exc}\nTry again:")
        return

    await cm.set_step(user_id, "pick_field")
