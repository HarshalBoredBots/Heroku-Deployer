"""/start — welcome message."""

from pyrogram import filters

from app.bot.auth import admin_only

WELCOME = """👋 <b>Heroku Manager Bot</b>

Manage your Heroku apps right from this chat.

<b>Profiles</b>
/createenv — create a deployment profile
/editenv — edit a profile
/apps — list all profiles
/deleteapp — delete profile + Heroku app

<b>Deploy</b>
/deploy, /redeploy, /deployall
/deployhistory — past deployments
/autodeploy — toggle git-push auto-deploy

<b>Controls</b>
/status, /logs, /startbot, /stopbot, /restart, /scale
/releases, /rollback

<b>Environment</b>
/envs, /env, /importenv, /deleteenv

<b>Accounts & system</b>
/accounts, /addaccount, /removeaccount, /useaccount
/history, /monitorstatus, /settings, /help
"""


def register(bot) -> None:
    @bot.on_message(filters.command("start"))
    @admin_only
    async def _start(client, message):
        await message.reply(WELCOME)
