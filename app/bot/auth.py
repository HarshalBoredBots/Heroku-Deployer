"""Admin-only decorator for Pyrogram handlers."""

import functools
import logging

from pyrogram.types import CallbackQuery, Message

from app.config import get_settings
from app.security import rate_limiter

logger = logging.getLogger(__name__)


def _user_id(event) -> int | None:
    user = getattr(event, "from_user", None)
    return user.id if user else None


def admin_only(func):
    """Silently ignore non-admins; apply the per-user rate limiter."""

    @functools.wraps(func)
    async def wrapper(client, event, *args, **kwargs):
        user_id = _user_id(event)
        if user_id is None or user_id not in get_settings().admin_ids:
            return
        if not rate_limiter.allow(user_id):
            if isinstance(event, CallbackQuery):
                try:
                    await event.answer("⏳ Slow down — rate limit reached.", show_alert=True)
                except Exception:
                    pass
            elif isinstance(event, Message):
                try:
                    await event.reply("⏳ Slow down — rate limit reached.")
                except Exception:
                    pass
            return
        return await func(client, event, *args, **kwargs)

    return wrapper
