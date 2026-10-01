"""/settings — show non-secret bot configuration."""

from pyrogram import filters

from app.bot.auth import admin_only
from app.config import get_settings


def register(bot) -> None:
    @bot.on_message(filters.command("settings"))
    @admin_only
    async def _settings(client, message):
        s = get_settings()
        await message.reply(
            "⚙️ <b>Bot Settings</b>\n\n"
            f"Default region: <code>{s.default_region}</code>\n"
            f"Default dyno type: <code>{s.default_dyno_type}</code>\n"
            f"Admins: {len(s.admin_ids)}\n"
            f"MongoDB database: <code>{s.mongodb_database}</code>\n"
            f"Log level: <code>{s.log_level}</code>"
        )
