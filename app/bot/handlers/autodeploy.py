"""/autodeploy — toggle auto-deploy per profile."""

from pyrogram import filters

from app.bot.auth import admin_only
from app.bot.keyboards import profile_selector
from app.db.repositories import profiles as profiles_repo
from app.services import audit_actions as AA
from app.services.audit import audit


def register(bot) -> None:
    @bot.on_message(filters.command("autodeploy"))
    @admin_only
    async def _autodeploy(client, message):
        args = message.text.split(maxsplit=1)[1].strip() if len(message.text.split()) > 1 else ""
        if args:
            profile = await profiles_repo.get_profile_by_name(args)
            if profile is None:
                await message.reply(f"Profile '<code>{args}</code>' not found.")
                return
            await _toggle(message, profile, message.from_user.id)
        else:
            profiles = await profiles_repo.list_profiles()
            if not profiles:
                await message.reply("No profiles yet.")
                return
            await message.reply("Select a profile to toggle auto-deploy:",
                                reply_markup=profile_selector(profiles, "autodeploy_select"))

    @bot.on_callback_query(filters.regex(r"^autodeploy_select:"))
    @admin_only
    async def _select(client, query):
        value = query.data.split(":", 1)[1]
        await query.answer()
        if value == "cancel":
            await query.message.edit_text("❌ Cancelled.")
            return
        profile = await profiles_repo.get_profile_by_id(int(value))
        await _toggle(query.message, profile, query.from_user.id)


async def _toggle(message, profile, user_id: int) -> None:
    new_value = not profile.get("auto_deploy", False)
    await profiles_repo.update_profile(profile["id"], {"auto_deploy": new_value})
    audit(str(user_id), AA.PROFILE_EDITED,
          profile_id=profile["id"], profile_name=profile["name"],
          app_name=profile["app_name"],
          detail=f"auto_deploy {'on' if new_value else 'off'}")
    text = (f"🔁 Auto-deploy for <b>{profile['name']}</b>: "
            f"{'✅ OFF → ON' if new_value else '❌ ON → OFF'}")
    if new_value:
        text += (f"\n\nPushes to <code>{profile['branch']}</code> on "
                 f"<code>{profile['repository']}</code> will now trigger a deployment "
                 "via the GitHub webhook.")
    await message.reply(text)
