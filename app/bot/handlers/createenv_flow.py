"""Flow dispatcher — routes plain text messages to the active conversation flow.

Shared by createenv, editenv, importenv, addaccount, scale and envs flows.
"""

import logging

from pyrogram import filters

from app.bot.auth import admin_only
from app.bot.conversations import conversation_manager as cm

logger = logging.getLogger(__name__)


def register(bot) -> None:
    @bot.on_message(filters.text & filters.private & ~filters.command(
        ["start", "help", "createenv", "editenv", "apps", "deploy", "redeploy",
         "deployall", "status", "logs", "startbot", "stopbot", "restart", "scale",
         "releases", "rollback", "envs", "env", "importenv", "deleteenv",
         "deleteapp", "accounts", "addaccount", "removeaccount", "useaccount",
         "autodeploy", "deployhistory", "history", "monitorstatus", "settings"]
    ))
    @admin_only
    async def _flow_text(client, message):
        state = await cm.get(message.from_user.id)
        if state is None:
            return

        if state.flow == "createenv":
            from app.bot.handlers import createenv
            await createenv.handle_step_text(message, state)
        elif state.flow == "editenv":
            from app.bot.handlers import editenv
            await editenv.handle_step_text(message, state)
        elif state.flow == "addaccount":
            from app.bot.handlers import accounts
            await accounts.handle_step_text(message, state)
        elif state.flow == "importenv":
            from app.bot.handlers import importenv
            await importenv.handle_step_text(message, state)
        elif state.flow == "scale":
            from app.bot.handlers import app_controls
            await app_controls.handle_scale_text(message, state)
        elif state.flow == "envset":
            from app.bot.handlers import envs
            await envs.handle_step_text(message, state)
        else:
            logger.debug("unknown_flow", extra={"flow": state.flow})
