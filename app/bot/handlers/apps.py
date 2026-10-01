"""/apps — list all deployment profiles."""

from pyrogram import filters

from app.bot.auth import admin_only
from app.db.repositories import profiles as profiles_repo


def register(bot) -> None:
    @bot.on_message(filters.command("apps"))
    @admin_only
    async def _apps(client, message):
        profiles = await profiles_repo.list_profiles()
        if not profiles:
            await message.reply("No profiles yet. Use /createenv to create one.")
            return
        cards = []
        for p in profiles:
            count = await profiles_repo.count_env_vars(p["id"])
            dot = "🟢" if p.get("auto_deploy") else "🔴"
            cards.append(
                f"{dot} <b>{p['name']}</b>  (<code>{p['app_name']}</code>)\n"
                f"Region: {p['region']} | Dyno: {p['dyno_type']} × {p['dyno_count']}\n"
                f"Auto-deploy: {'✅' if p.get('auto_deploy') else '❌'} | Env vars: {count}"
            )
        await message.reply("\n\n".join(cards))
