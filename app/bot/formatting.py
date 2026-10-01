"""Message formatters for the bot UI."""

from app.db.repositories import profiles as profiles_repo

STAGE_ICONS = {
    "Checking Heroku app": "🔍",
    "Configuring environment": "⚙️",
    "Deploying source": "📦",
    "Building": "🔨",
    "Creating release": "📋",
    "Scaling dynos": "📈",
    "Starting dyno": "▶️",
    "Verifying": "🔎",
}


def render_profile_card(profile: dict, env_count: int | None = None) -> str:
    dot = "🟢" if profile.get("auto_deploy") else "🔴"
    lines = [
        f"{dot} <b>{profile['name']}</b>  (<code>{profile['app_name']}</code>)",
        f"Region: {profile['region']} | Dyno: {profile['dyno_type']} × {profile['dyno_count']}",
        f"Repo: <code>{profile['repository']}</code> ({profile['branch']})",
        f"Process: <code>{profile['process_type']}</code> — <code>{profile['start_command']}</code>",
    ]
    if env_count is not None:
        lines.append(f"Auto-deploy: {'✅' if profile.get('auto_deploy') else '❌'} | Env vars: {env_count}")
    return "\n".join(lines)


def render_progress(stages_done: list[str], current: str | None) -> str:
    lines = []
    for stage in stages_done:
        lines.append(f"✅ {stage}")
    if current:
        icon = STAGE_ICONS.get(current, "⏳")
        lines.append(f"{icon} {current}…")
    return "\n".join(lines)


def short_commit(commit: str | None) -> str:
    return commit[:7] if commit else "—"


async def profile_card_with_env_count(profile: dict) -> str:
    count = await profiles_repo.count_env_vars(profile["id"])
    return render_profile_card(profile, env_count=count)
