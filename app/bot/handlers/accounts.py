"""Heroku account management: /accounts /addaccount /removeaccount /useaccount."""

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.auth import admin_only
from app.bot.conversations import conversation_manager as cm
from app.crypto import encrypt_value
from app.db.repositories import accounts as accounts_repo
from app.db.repositories import profiles as profiles_repo
from app.security import sanitize_error
from app.services import audit_actions as AA
from app.services.account_validator import validate_heroku_api_key
from app.services.audit import audit
from app.services.heroku_context import (
    get_active_account_id,
    set_active_account_id,
)


def _accounts_keyboard(accounts: list[dict]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(a["name"], callback_data=f"acct:view:{a['id']}")]
        for a in accounts
    ]
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="acct:close")])
    return InlineKeyboardMarkup(buttons)


def register(bot) -> None:
    @bot.on_message(filters.command("accounts"))
    @admin_only
    async def _accounts(client, message):
        accounts = await accounts_repo.list_accounts()
        if not accounts:
            await message.reply("No Heroku accounts configured. Use /addaccount.")
            return
        active_id = get_active_account_id(message.from_user.id)
        lines = ["🏦 <b>Heroku Accounts</b>\n"]
        for a in accounts:
            marks = []
            if a.get("is_default"):
                marks.append("⭐ default")
            if a["id"] == active_id:
                marks.append("✅ session")
            lines.append(f"• <b>{a['name']}</b> {' '.join(marks)}")
        await message.reply("\n".join(lines),
                            reply_markup=_accounts_keyboard(accounts))

    @bot.on_callback_query(filters.regex(r"^acct:"))
    @admin_only
    async def _acct(client, query):
        parts = query.data.split(":")
        action = parts[1]
        user_id = query.from_user.id

        if action == "close":
            await query.message.edit_text("Closed.")
        elif action == "view":
            account = await accounts_repo.get_account_by_id(int(parts[2]))
            if account is None:
                await query.answer("Account not found.", show_alert=True)
                return
            await query.message.edit_text(
                f"🏦 <b>{account['name']}</b>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⭐ Set as default",
                                          callback_data=f"acct:default:{account['id']}")],
                    [InlineKeyboardButton("✅ Use for session",
                                          callback_data=f"acct:use:{account['id']}")],
                    [InlineKeyboardButton("🗑️ Remove",
                                          callback_data=f"acct:remove:{account['id']}")],
                    [InlineKeyboardButton("← Back", callback_data="acct:back")],
                ]),
            )
        elif action == "back":
            accounts = await accounts_repo.list_accounts()
            await query.message.edit_text("🏦 <b>Heroku Accounts</b>",
                                          reply_markup=_accounts_keyboard(accounts))
        elif action == "default":
            await accounts_repo.set_default_account(int(parts[2]))
            await query.message.edit_text("⭐ Default account updated.")
        elif action == "use":
            account_id = int(parts[2])
            account = await accounts_repo.get_account_by_id(account_id)
            set_active_account_id(user_id, account_id)
            await query.message.edit_text(
                f"✅ Session now uses account <b>{account['name']}</b> "
                "(resets when the bot restarts)."
            )
        elif action == "remove":
            account_id = int(parts[2])
            account = await accounts_repo.get_account_by_id(account_id)
            profiles = await profiles_repo.list_profiles()
            used_by = [p["name"] for p in profiles if p["heroku_account_id"] == account_id]
            if used_by:
                await query.answer(
                    f"Cannot remove — used by: {', '.join(used_by)}", show_alert=True
                )
                return
            await accounts_repo.remove_account(account_id)
            audit(str(user_id), AA.ACCOUNT_REMOVED,
                  detail=account["name"] if account else str(account_id))
            await query.message.edit_text(f"🗑️ Removed account <b>{account['name']}</b>.")
        await query.answer()

    @bot.on_message(filters.command("addaccount"))
    @admin_only
    async def _addaccount(client, message):
        await cm.start(message.from_user.id, "addaccount", "name")
        await message.reply("1️⃣ Send a name for the new Heroku account (1-64 chars, unique):")

    @bot.on_message(filters.command("removeaccount"))
    @admin_only
    async def _removeaccount(client, message):
        accounts = await accounts_repo.list_accounts()
        buttons = [
            [InlineKeyboardButton(a["name"], callback_data=f"acct:remove:{a['id']}")]
            for a in accounts
        ]
        await message.reply("Select an account to remove:",
                            reply_markup=InlineKeyboardMarkup(buttons))

    @bot.on_message(filters.command("useaccount"))
    @admin_only
    async def _useaccount(client, message):
        accounts = await accounts_repo.list_accounts()
        buttons = [
            [InlineKeyboardButton(a["name"], callback_data=f"acct:use:{a['id']}")]
            for a in accounts
        ]
        await message.reply("Select an account for this session:",
                            reply_markup=InlineKeyboardMarkup(buttons))


async def handle_step_text(message, state) -> None:
    user_id = message.from_user.id
    text = message.text.strip()
    if state.step == "name":
        if not 1 <= len(text) <= 64:
            await message.reply("❌ Name must be 1-64 characters. Try again:")
            return
        if await accounts_repo.get_account_by_name(text):
            await message.reply("❌ That account name is taken. Try again:")
            return
        await cm.update_data(user_id, name=text)
        await cm.set_step(user_id, "api_key")
        await message.reply("2️⃣ Send the Heroku API key (your message will be deleted immediately):")
    elif state.step == "api_key":
        # Reduce exposure: delete the user's message ASAP.
        try:
            await message.delete()
        except Exception:
            pass
        try:
            info = await validate_heroku_api_key(text)
        except Exception:
            await cm.clear(user_id)
            await message.reply("❌ Invalid Heroku API key.")
            return
        account = await accounts_repo.create_account(state.data["name"], encrypt_value(text))
        audit(str(user_id), AA.ACCOUNT_ADDED, detail=account["name"])
        email = info.get("email", "unknown")
        await message.reply(
            f"✅ Account <b>{account['name']}</b> added (verified: {email})."
        )
        await cm.clear(user_id)
