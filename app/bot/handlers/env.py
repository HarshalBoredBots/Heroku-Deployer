"""/env [profile] KEY — view a single env var (masked; reveals length only)."""

from pyrogram import filters

from app.bot.auth import admin_only
from app.db.repositories import profiles as profiles_repo


def register(bot) -> None:
    @bot.on_message(filters.command("env"))
    @admin_only
    async def _env(client, message):
        parts = message.text.split()
        if len(parts) < 3:
            await message.reply("Usage: <code>/env PROFILE_NAME KEY</code>")
            return
        profile_name, key = parts[1], parts[2]
        profile = await profiles_repo.get_profile_by_name(profile_name)
        if profile is None:
            await message.reply(f"Profile '<code>{profile_name}</code>' not found.")
            return
        env_vars = await profiles_repo.get_env_vars_decrypted(profile["id"])
        if key not in env_vars:
            await message.reply(f"Key <code>{key}</code> not found in <b>{profile['name']}</b>.")
            return
        # Never show the value — only key name and length.
        await message.reply(
            f"🔑 <code>{key}</code> = ***\nValue length: {len(env_vars[key])} characters"
        )
