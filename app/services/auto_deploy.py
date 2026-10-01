"""Auto-deploy service triggered by GitHub webhooks."""

import asyncio
import logging

from app.db.repositories import profiles as profiles_repo
from app.services import audit_actions as AA
from app.services.audit import audit
from app.services.deployment_engine import DeploymentEngine
from app.services.heroku_context import heroku_api_for_profile

logger = logging.getLogger(__name__)

_semaphore: asyncio.Semaphore | None = None  # created lazily on first use


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(3)  # max 3 concurrent builds
    return _semaphore


async def _deploy_one(profile: dict, commit: str) -> None:
    async with _get_semaphore():
        try:
            audit("system", AA.AUTO_DEPLOY_TRIGGERED,
                  profile_id=profile["id"], profile_name=profile["name"],
                  app_name=profile["app_name"], detail=commit[:7])
            async with heroku_api_for_profile(profile) as heroku:
                engine = DeploymentEngine(heroku)
                result = await engine.deploy(profile["name"])
            action = AA.AUTO_DEPLOY_SUCCEEDED if result.status == "success" else AA.AUTO_DEPLOY_FAILED
            audit("system", action,
                  profile_id=profile["id"], profile_name=profile["name"],
                  app_name=profile["app_name"], detail=result.error_message)
        except Exception:
            logger.exception("auto_deploy_failed", extra={"profile_id": profile["id"]})
            audit("system", AA.AUTO_DEPLOY_FAILED,
                  profile_id=profile["id"], profile_name=profile["name"],
                  app_name=profile["app_name"], detail="unexpected error")


async def schedule_auto_deployments(repository: str, branch: str, commit: str) -> None:
    """Deploy all auto_deploy profiles matching this repo+branch."""
    profiles = await profiles_repo.find_auto_deploy_profiles(repository, branch)
    for profile in profiles:
        asyncio.create_task(_deploy_one(profile, commit))
