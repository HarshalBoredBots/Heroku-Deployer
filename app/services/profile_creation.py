"""Save a deployment profile with encrypted env vars."""

from app.db.repositories import profiles as profiles_repo


async def save_profile(data: dict, env_vars: dict[str, str]) -> dict:
    """Create the profile document, then encrypt + store env vars."""
    profile = await profiles_repo.create_profile(data)
    if env_vars:
        await profiles_repo.save_env_vars(profile["id"], env_vars)
    return profile
