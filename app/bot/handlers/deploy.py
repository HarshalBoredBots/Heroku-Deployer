"""/deploy, /redeploy — run the deployment pipeline with live progress."""

import asyncio
import logging

from pyrogram import filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.bot.auth import admin_only
from app.bot.formatting import STAGE_ICONS, profile_card_with_env_count, short_commit
from app.bot.keyboards import profile_selector
from app.db.repositories import profiles as profiles_repo
from app.security import sanitize_error
from app.services import audit_actions as AA
from app.services.audit import audit
from app.services.deployment_engine import (
    AlreadyDeployedError,
    AppAdoptionRequiredError,
    DeploymentEngine,
)
from app.services.heroku_context import heroku_api_for_profile

logger = logging.getLogger(__name__)


async def _send_confirm(message, profile_id: int, prefix: str) -> None:
    profile = await profiles_repo.get_profile_by_id(profile_id)
    if profile is None:
        await message.reply("Profile not found.")
        return
    card = await profile_card_with_env_count(profile)
    await message.reply(
        f"🚀 <b>Deploy this profile?</b>\n\n{card}",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🚀 Deploy Now", callback_data=f"{prefix}_confirm:{profile_id}"),
            InlineKeyboardButton("❌ Cancel", callback_data=f"{prefix}_confirm:cancel"),
        ]]),
    )


async def _run_deploy(client, chat_id: int, user_id: int, profile_id: int,
                      *, force: bool = False, adopt_existing: bool = False) -> None:
    profile = await profiles_repo.get_profile_by_id(profile_id)
    if profile is None:
        await client.send_message(chat_id, "Profile not found.")
        return

    done_stages: list[str] = []
    current: list[str] = ["Starting"]
    progress_msg = await client.send_message(chat_id, f"⏳ Starting deploy of <b>{profile['name']}</b>…")

    async def _edit():
        lines = [f"🚀 Deploying <b>{profile['name']}</b>\n"]
        lines += [f"✅ {s}" for s in done_stages]
        if current[0]:
            lines.append(f"{STAGE_ICONS.get(current[0], '⏳')} {current[0]}…")
        try:
            await progress_msg.edit_text("\n".join(lines))
        except Exception:
            pass

    def on_progress(label: str, done: bool):
        async def _apply():
            if done:
                done_stages.append(label)
                if current[0] == label:
                    current[0] = ""
            else:
                current[0] = label
            await _edit()
        try:
            asyncio.get_running_loop().create_task(_apply())
        except Exception:
            pass

    audit(str(user_id), AA.DEPLOY_STARTED,
          profile_id=profile["id"], profile_name=profile["name"],
          app_name=profile["app_name"])

    try:
        async with heroku_api_for_profile(profile) as heroku:
            engine = DeploymentEngine(heroku, on_progress=on_progress)
            result = await engine.deploy(
                profile["name"], force=force, adopt_existing=adopt_existing
            )
    except AppAdoptionRequiredError as exc:
        await progress_msg.edit_text(
            f"⚠️ Heroku app <code>{exc.app_name}</code> already exists and is not managed by this bot.\n"
            "Adopt it and deploy anyway?",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Adopt", callback_data=f"deploy_adopt:{profile_id}"),
                InlineKeyboardButton("❌ Cancel", callback_data="deploy_adopt:cancel"),
            ]]),
        )
        return
    except AlreadyDeployedError as exc:
        await progress_msg.edit_text(
            f"ℹ️ Commit <code>{short_commit(exc.commit)}</code> is already deployed "
            f"(deployment #{exc.deployment_id}).",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔄 Force redeploy", callback_data=f"deploy_force:{profile_id}"),
                InlineKeyboardButton("❌ Cancel", callback_data="deploy_force:cancel"),
            ]]),
        )
        return

    if result.status == "success":
        audit(str(user_id), AA.DEPLOY_SUCCEEDED,
              profile_id=profile["id"], profile_name=profile["name"],
              app_name=profile["app_name"], detail=result.release_version)
        verified = "" if result.verified else "\n⚠️ Could not verify dyno is up — check /status."
        await progress_msg.edit_text(
            f"✅ Deployed <b>{profile['name']}</b> to {result.release_version or '?'} "
            f"(commit <code>{short_commit(result.commit)}</code>){verified}"
        )
    else:
        audit(str(user_id), AA.DEPLOY_FAILED,
              profile_id=profile["id"], profile_name=profile["name"],
              app_name=profile["app_name"], detail=result.error_message)
        stage, _, err = (result.error_message or "unknown").partition(": ")
        await progress_msg.edit_text(
            f"❌ Deployment failed at <b>{stage}</b>:\n<code>{sanitize_error(err)}</code>"
        )


async def _resolve_and_confirm(message, args: str, prefix: str) -> None:
    if args:
        profile = await profiles_repo.get_profile_by_name(args)
        if profile is None:
            await message.reply(f"Profile '<code>{args}</code>' not found.")
            return
        await _send_confirm(message, profile["id"], prefix)
    else:
        profiles = await profiles_repo.list_profiles()
        if not profiles:
            await message.reply("No profiles yet. Use /createenv first.")
            return
        await message.reply("Select a profile to deploy:",
                            reply_markup=profile_selector(profiles, f"{prefix}_select"))


def register(bot) -> None:
    @bot.on_message(filters.command("deploy"))
    @admin_only
    async def _deploy(client, message):
        args = message.text.split(maxsplit=1)[1].strip() if len(message.text.split()) > 1 else ""
        await _resolve_and_confirm(message, args, "deploy")

    @bot.on_message(filters.command("redeploy"))
    @admin_only
    async def _redeploy(client, message):
        args = message.text.split(maxsplit=1)[1].strip() if len(message.text.split()) > 1 else ""
        if args:
            profile = await profiles_repo.get_profile_by_name(args)
            if profile is None:
                await message.reply(f"Profile '<code>{args}</code>' not found.")
                return
            asyncio.create_task(_run_deploy(client, message.chat.id, message.from_user.id,
                                            profile["id"], force=True))
        else:
            profiles = await profiles_repo.list_profiles()
            if not profiles:
                await message.reply("No profiles yet.")
                return
            await message.reply("Select a profile to redeploy (force):",
                                reply_markup=profile_selector(profiles, "redeploy_select"))

    @bot.on_callback_query(filters.regex(r"^deploy_select:"))
    @admin_only
    async def _deploy_select(client, query):
        value = query.data.split(":", 1)[1]
        await query.answer()
        if value == "cancel":
            await query.message.edit_text("❌ Cancelled.")
            return
        profile = await profiles_repo.get_profile_by_id(int(value))
        card = await profile_card_with_env_count(profile)
        await query.message.edit_text(
            f"🚀 <b>Deploy this profile?</b>\n\n{card}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🚀 Deploy Now", callback_data=f"deploy_confirm:{profile['id']}"),
                InlineKeyboardButton("❌ Cancel", callback_data="deploy_confirm:cancel"),
            ]]),
        )

    @bot.on_callback_query(filters.regex(r"^redeploy_select:"))
    @admin_only
    async def _redeploy_select(client, query):
        value = query.data.split(":", 1)[1]
        await query.answer()
        if value == "cancel":
            await query.message.edit_text("❌ Cancelled.")
            return
        await query.message.edit_text("🚀 Redeploying (force)…")
        asyncio.create_task(_run_deploy(client, query.message.chat.id, query.from_user.id,
                                        int(value), force=True))

    @bot.on_callback_query(filters.regex(r"^deploy_confirm:"))
    @admin_only
    async def _deploy_confirm(client, query):
        value = query.data.split(":", 1)[1]
        await query.answer()
        if value == "cancel":
            await query.message.edit_text("❌ Deploy cancelled.")
            return
        await query.message.edit_text("🚀 Deploy queued…")
        asyncio.create_task(_run_deploy(client, query.message.chat.id, query.from_user.id,
                                        int(value)))

    @bot.on_callback_query(filters.regex(r"^deploy_adopt:"))
    @admin_only
    async def _deploy_adopt(client, query):
        value = query.data.split(":", 1)[1]
        await query.answer()
        if value == "cancel":
            await query.message.edit_text("❌ Cancelled.")
            return
        await query.message.edit_text("🚀 Adopting app and deploying…")
        asyncio.create_task(_run_deploy(client, query.message.chat.id, query.from_user.id,
                                        int(value), adopt_existing=True))

    @bot.on_callback_query(filters.regex(r"^deploy_force:"))
    @admin_only
    async def _deploy_force(client, query):
        value = query.data.split(":", 1)[1]
        await query.answer()
        if value == "cancel":
            await query.message.edit_text("❌ Cancelled.")
            return
        await query.message.edit_text("🔄 Force redeploying…")
        asyncio.create_task(_run_deploy(client, query.message.chat.id, query.from_user.id,
                                        int(value), force=True))
