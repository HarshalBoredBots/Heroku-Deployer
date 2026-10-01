"""/help — full command reference."""

from pyrogram import filters

from app.bot.auth import admin_only
from app.bot.handlers.start import WELCOME

HELP = WELCOME + """
<b>Notes</b>
• Env var values are always masked — never shown in chat.
• Auto-deploy requires a GitHub webhook pointing to /webhook/github.
• All actions are admin-only and rate-limited.
"""


def register(bot) -> None:
    @bot.on_message(filters.command("help"))
    @admin_only
    async def _help(client, message):
        await message.reply(HELP)
