"""Shared InlineKeyboardMarkup builders."""

from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def profile_selector(profiles: list[dict], prefix: str) -> InlineKeyboardMarkup:
    """One button per profile: callback_data = f'{prefix}:{profile_id}'."""
    buttons = [
        [InlineKeyboardButton(p["name"], callback_data=f"{prefix}:{p['id']}")]
        for p in profiles
    ]
    buttons.append([InlineKeyboardButton("❌ Cancel", callback_data=f"{prefix}:cancel")])
    return InlineKeyboardMarkup(buttons)


def confirm_cancel(confirm_data: str, cancel_data: str = "cancel",
                   confirm_label: str = "✅ Confirm") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(confirm_label, callback_data=confirm_data),
        InlineKeyboardButton("❌ Cancel", callback_data=cancel_data),
    ]])


def yes_no(prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Yes", callback_data=f"{prefix}:yes"),
        InlineKeyboardButton("❌ No", callback_data=f"{prefix}:no"),
    ]])


def cancel_button(data: str = "cancel") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=data)]])


def skip_button(data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⏭ Skip", callback_data=data)]])
