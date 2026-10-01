"""Create the Pyrogram bot client (no plugins= dict)."""

from pyrogram import Client, enums

from app.config import get_settings


def create_bot() -> Client:
    settings = get_settings()
    # FIX #12: Set parse_mode="html" globally so that every message.reply() and
    # send_message() call that uses <b>, <code>, <pre> etc. renders HTML markup
    # instead of showing the raw tags as literal text.
    return Client(
        "heroku_manager_bot",
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        bot_token=settings.bot_token,
        in_memory=True,
        parse_mode=enums.ParseMode.HTML,
    )
