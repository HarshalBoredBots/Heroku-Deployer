"""Catch-all callback router. MUST be registered last."""

import logging

from pyrogram import filters

from app.bot.auth import admin_only

logger = logging.getLogger(__name__)

# Namespaces handled by dedicated handlers elsewhere (listed for completeness).
_KNOWN_EXTERNAL = frozenset({
    "ct", "deploy_select", "deploy_confirm", "deploy_adopt", "deploy_force",
    "redeploy_select", "deployall_pick", "deployall_go", "deployall_cancel",
    "status_select", "logs_select", "logs_refresh",
    "start_select", "stop_select", "restart_select",
    "scale_select", "rollback_select", "rollback_do", "releases_select",
    "envs_select", "envs_add", "envs_edit", "envs_editkey", "envs_del",
    "envs_delkey", "envs_delcancel", "importenv_select",
    "deleteenv_select", "deleteenv_key", "deleteenv_confirm",
    "deleteapp_select", "delete_app_confirm",
    "acct", "history_select", "history_page",
    "autodeploy_select", "editenv", "editfield", "cancel",
})


def register(bot) -> None:
    @bot.on_callback_query()
    @admin_only
    async def _catch_all(client, query):
        namespace = query.data.split(":", 1)[0] if query.data else ""
        if namespace in _KNOWN_EXTERNAL:
            # A dedicated handler should have caught this; just stop the spinner.
            await query.answer()
            return
        logger.debug("unknown_callback", extra={"callback_data": query.data[:64]})
        try:
            await query.answer()
        except Exception:
            pass
