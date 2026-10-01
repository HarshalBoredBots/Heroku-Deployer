"""/deployall — multi-select profiles and deploy up to 3 concurrently."""

import asyncio

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.auth import admin_only
from app.bot.handlers.deploy import _run_deploy
from app.db.repositories import profiles as profiles_repo

# user_id -> set of selected profile ids (in-memory selection state)
_selections: dict[int, set[int]] = {}


async def _render_keyboard(user_id: int) -> InlineKeyboardMarkup:
    profiles = await profiles_repo.list_profiles()
    selected = _selections.get(user_id, set())
    buttons = []
    for p in profiles:
        mark = "✅" if p["id"] in selected else "⬜"
        buttons.append([InlineKeyboardButton(
            f"{mark} {p['name']}", callback_data=f"deployall_pick:{p['id']}"
        )])
    buttons.append([
        InlineKeyboardButton(f"🚀 Deploy Selected ({len(selected)})",
                             callback_data="deployall_go"),
        InlineKeyboardButton("❌ Cancel", callback_data="deployall_cancel"),
    ])
    return InlineKeyboardMarkup(buttons)


def register(bot) -> None:
    @bot.on_message(filters.command("deployall"))
    @admin_only
    async def _deployall(client, message):
        profiles = await profiles_repo.list_profiles()
        if not profiles:
            await message.reply("No profiles yet. Use /createenv first.")
            return
        _selections[message.from_user.id] = set()
        await message.reply("Select profiles to deploy:",
                            reply_markup=await _render_keyboard(message.from_user.id))

    @bot.on_callback_query(filters.regex(r"^deployall_pick:"))
    @admin_only
    async def _pick(client, query):
        user_id = query.from_user.id
        profile_id = int(query.data.split(":", 1)[1])
        selected = _selections.setdefault(user_id, set())
        if profile_id in selected:
            selected.discard(profile_id)
        else:
            selected.add(profile_id)
        await query.message.edit_reply_markup(await _render_keyboard(user_id))
        await query.answer()

    @bot.on_callback_query(filters.regex(r"^deployall_cancel$"))
    @admin_only
    async def _cancel(client, query):
        _selections.pop(query.from_user.id, None)
        await query.message.edit_text("❌ Cancelled.")
        await query.answer()

    @bot.on_callback_query(filters.regex(r"^deployall_go$"))
    @admin_only
    async def _go(client, query):
        user_id = query.from_user.id
        selected = list(_selections.pop(user_id, set()))
        await query.answer()
        if not selected:
            await query.message.edit_text("No profiles selected.")
            return
        await query.message.edit_text(f"🚀 Deploying {len(selected)} profile(s)…")
        chat_id = query.message.chat.id

        semaphore = asyncio.Semaphore(3)

        async def _one(pid: int):
            async with semaphore:
                await _run_deploy(client, chat_id, user_id, pid)

        await asyncio.gather(*[_one(pid) for pid in selected])
        await client.send_message(chat_id, "✅ Bulk deploy finished.")
