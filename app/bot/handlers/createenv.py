"""/createenv — 11-step guided profile creation flow."""

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.auth import admin_only
from app.bot.conversations import conversation_manager as cm
from app.bot.formatting import render_profile_card
from app.bot.keyboards import cancel_button, skip_button, yes_no
from app.config import get_settings
from app.db.repositories import profiles as profiles_repo
from app.services import audit_actions as AA
from app.services.audit import audit
from app.services.heroku_context import heroku_api_for_user
from app.services.profile_creation import save_profile

FLOW = "createenv"


def _summary_text(data: dict, env_count: int) -> str:
    fake_profile = {
        "name": data["name"], "app_name": data["app_name"],
        "repository": data["repository"], "branch": data["branch"],
        "start_command": data["start_command"], "process_type": data["process_type"],
        "dyno_count": data["dyno_count"], "dyno_type": data["dyno_type"],
        "region": data["region"], "auto_deploy": data.get("auto_deploy", False),
    }
    card = render_profile_card(fake_profile)
    return f"📋 <b>Confirm new profile</b>\n\n{card}\nEnv vars to import: {env_count}"


async def _prompt_dyno_types(message, user_id: int) -> None:
    async with heroku_api_for_user(user_id) as heroku:
        sizes = await heroku.dyno_sizes.list()
    buttons = []
    default = get_settings().default_dyno_type
    for s in sizes[:20]:
        cost = s.get("cost", {})
        price = f"${cost.get('cents', 0) // 100}/mo" if cost else ""
        label = f"{s['name']} {price}".strip()
        buttons.append([InlineKeyboardButton(label, callback_data=f"ct:dtype:{s['name']}")])
    markup = InlineKeyboardMarkup(buttons) if buttons else None
    hint = f"(default: {default})" if default else ""
    await message.reply(f"8️⃣ <b>Dyno type</b> {hint}", reply_markup=markup)


async def _prompt_regions(message, user_id: int) -> None:
    async with heroku_api_for_user(user_id) as heroku:
        regions = await heroku.regions.list()
    buttons = [
        [InlineKeyboardButton(f"{r['name']} — {r.get('description', '')}",
                              callback_data=f"ct:region:{r['name']}")]
        for r in regions[:20]
    ]
    markup = InlineKeyboardMarkup(buttons) if buttons else None
    await message.reply("9️⃣ <b>Region</b>", reply_markup=markup)


def register(bot) -> None:
    @bot.on_message(filters.command("createenv"))
    @admin_only
    async def _createenv(client, message):
        user_id = message.from_user.id
        await cm.start(user_id, FLOW, "name")
        await message.reply(
            "1️⃣ <b>Profile name</b> — e.g. <code>ENV A</code> (1-64 chars, unique)",
            reply_markup=cancel_button("ct:cancel"),
        )

    @bot.on_callback_query(filters.regex(r"^ct:"))
    @admin_only
    async def _ct_callback(client, query):
        user_id = query.from_user.id
        parts = query.data.split(":", 2)
        action = parts[1]
        value = parts[2] if len(parts) > 2 else ""

        state = await cm.get(user_id)
        if state is None or state.flow != FLOW:
            await query.answer("No active /createenv flow.")
            return

        if action == "cancel":
            await cm.clear(user_id)
            await query.message.edit_text("❌ Profile creation cancelled.")
            await query.answer()
            return

        if action == "ptype" and state.step == "process_type":
            await cm.update_data(user_id, process_type=value)
            await cm.set_step(user_id, "dyno_count")
            await query.message.edit_text(
                "7️⃣ <b>Dyno count</b> — integer 0-100"
            )
        elif action == "dtype" and state.step == "dyno_type":
            await cm.update_data(user_id, dyno_type=value)
            await cm.set_step(user_id, "region")
            await query.message.edit_text("✅ Dyno type selected.")
            await _prompt_regions(query.message, user_id)
        elif action == "region" and state.step == "region":
            await cm.update_data(user_id, region=value)
            await cm.set_step(user_id, "auto_deploy")
            await query.message.edit_text(
                "🔟 <b>Auto-deploy on git push?</b>",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ Yes", callback_data="ct:auto:yes"),
                    InlineKeyboardButton("❌ No", callback_data="ct:auto:no"),
                ]]),
            )
        elif action == "auto" and state.step == "auto_deploy":
            await cm.update_data(user_id, auto_deploy=(value == "yes"))
            await cm.set_step(user_id, "env_vars")
            await query.message.edit_text(
                "1️⃣1️⃣ <b>Environment variables</b> (optional)\n"
                "Paste <code>.env</code>-format text, or skip.",
                reply_markup=skip_button("ct:envskip"),
            )
        elif action == "envskip" and state.step == "env_vars":
            await cm.update_data(user_id, env_vars={})
            await cm.set_step(user_id, "confirm")
            text = _summary_text((await cm.get(user_id)).data, 0)
            await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💾 Save", callback_data="ct:save"),
                InlineKeyboardButton("❌ Cancel", callback_data="ct:cancel"),
            ]]))
        elif action == "save" and state.step == "confirm":
            data = state.data
            env_vars = data.get("env_vars", {})
            from app.db.repositories import accounts as accounts_repo
            default_acct = await accounts_repo.get_default_account()
            # FIX #4 (createenv): get_default_account() can return None when no
            # Heroku accounts have been configured yet.  Accessing default_acct["id"]
            # on None crashes with a TypeError.  Fall back to 0 (sentinel) so the
            # profile can still be saved; the user can reassign the account later.
            heroku_account_id = default_acct["id"] if default_acct is not None else 0
            profile = await save_profile(
                {
                    "name": data["name"], "app_name": data["app_name"],
                    "repository": data["repository"], "branch": data["branch"],
                    "start_command": data["start_command"],
                    "process_type": data["process_type"],
                    "dyno_count": data["dyno_count"], "dyno_type": data["dyno_type"],
                    "region": data["region"], "auto_deploy": data.get("auto_deploy", False),
                    "heroku_account_id": heroku_account_id,
                },
                env_vars,
            )
            await cm.clear(user_id)
            audit(str(user_id), AA.PROFILE_CREATED,
                  profile_id=profile["id"], profile_name=profile["name"],
                  app_name=profile["app_name"])
            await query.message.edit_text(
                f"✅ Profile <b>{profile['name']}</b> saved with {len(env_vars)} env var(s)."
            )
        else:
            await query.answer()
            return
        await query.answer()


async def handle_step_text(message, state) -> None:
    """Process a text input for the current /createenv step. Called by the flow dispatcher."""
    user_id = message.from_user.id
    text = message.text.strip()
    from app.services import validation as V
    from app.services.env_parser import EnvParseError, parse_env_text

    try:
        if state.step == "name":
            if not 1 <= len(text) <= 64:
                raise ValueError("Profile name must be 1-64 characters.")
            if await profiles_repo.get_profile_by_name(text):
                raise ValueError("That profile name is already taken.")
            await cm.update_data(user_id, name=text)
            await cm.set_step(user_id, "app_name")
            await message.reply("2️⃣ <b>Heroku app name</b> — lowercase, 3-30 chars, letters/digits/hyphens")

        elif state.step == "app_name":
            app_name = V.validate_app_name(text)
            if await profiles_repo.get_profile_by_app_name(app_name):
                raise ValueError("That app name is already used by another profile.")
            await cm.update_data(user_id, app_name=app_name)
            await cm.set_step(user_id, "repository")
            await message.reply("3️⃣ <b>Repository</b> — HTTPS GitHub URL (https://github.com/user/repo)")

        elif state.step == "repository":
            await cm.update_data(user_id, repository=V.validate_repo_url(text))
            await cm.set_step(user_id, "branch")
            await message.reply("4️⃣ <b>Branch</b> — e.g. <code>main</code>")

        elif state.step == "branch":
            await cm.update_data(user_id, branch=V.validate_branch(text))
            await cm.set_step(user_id, "start_command")
            await message.reply("5️⃣ <b>Start command</b> — e.g. <code>python bot.py</code>")

        elif state.step == "start_command":
            await cm.update_data(user_id, start_command=V.validate_start_command(text))
            await cm.set_step(user_id, "process_type")
            await message.reply(
                "6️⃣ <b>Process type</b> — send text or use the default",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("worker (default)", callback_data="ct:ptype:worker")
                ]]),
            )

        elif state.step == "process_type":
            await cm.update_data(user_id, process_type=V.validate_process_type(text))
            await cm.set_step(user_id, "dyno_count")
            await message.reply("7️⃣ <b>Dyno count</b> — integer 0-100")

        elif state.step == "dyno_count":
            await cm.update_data(user_id, dyno_count=V.validate_dyno_count(text))
            await cm.set_step(user_id, "dyno_type")
            await _prompt_dyno_types(message, user_id)

        elif state.step == "env_vars":
            env_vars = parse_env_text(text)
            await cm.update_data(user_id, env_vars=env_vars)
            await cm.set_step(user_id, "confirm")
            summary = _summary_text((await cm.get(user_id)).data, len(env_vars))
            await message.reply(summary, reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💾 Save", callback_data="ct:save"),
                InlineKeyboardButton("❌ Cancel", callback_data="ct:cancel"),
            ]]))
        else:
            await message.reply("Please use the buttons for this step.")

    except (ValueError, EnvParseError) as exc:
        await message.reply(f"❌ {exc}\nTry again:")
