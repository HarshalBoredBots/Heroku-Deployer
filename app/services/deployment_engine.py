"""DeploymentEngine — the full Heroku deploy pipeline."""

import asyncio
import logging
from dataclasses import dataclass

from app.db.repositories import deployments as deployments_repo
from app.db.repositories import managed_apps as managed_apps_repo
from app.db.repositories import profiles as profiles_repo
from app.heroku.api import HerokuAPI
from app.heroku.exceptions import HerokuNotFoundError
from app.services.github_client import GitHubClient
from app.services.source_builder import inject_procfile

logger = logging.getLogger(__name__)


class AppAdoptionRequiredError(Exception):
    def __init__(self, app_name: str, heroku_app_id: str) -> None:
        super().__init__(f"Heroku app '{app_name}' exists but is not managed by this bot.")
        self.app_name = app_name
        self.heroku_app_id = heroku_app_id


class AlreadyDeployedError(Exception):
    def __init__(self, commit: str, deployment_id: int) -> None:
        super().__init__(f"Commit {commit[:7]} already deployed (deployment #{deployment_id}).")
        self.commit = commit
        self.deployment_id = deployment_id


@dataclass
class DeploymentResult:
    deployment_id: int
    status: str  # "success" | "failed"
    app_name: str
    commit: str | None
    release_version: str | None
    verified: bool
    error_message: str | None = None


class DeploymentEngine:
    def __init__(self, heroku: HerokuAPI, *, on_progress=None) -> None:
        self._heroku = heroku
        self._on_progress = on_progress

    async def _progress(self, label: str, done: bool) -> None:
        """Fire-and-forget progress callback; exceptions are swallowed."""
        if self._on_progress is None:
            return
        try:
            result = self._on_progress(label, done)
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            pass

    async def deploy(
        self, profile_name: str, *, force: bool = False, adopt_existing: bool = False
    ) -> DeploymentResult:
        profile = await profiles_repo.get_profile_by_name(profile_name)
        if profile is None:
            raise ValueError(f"Profile '{profile_name}' not found.")

        # --- VALIDATING ---
        stage = "validating"
        deployment = await deployments_repo.create_deployment(
            profile["id"], profile["branch"], profile["repository"]
        )
        dep_id = deployment["id"]
        release_version = None
        # FIX #6: Initialise commit to None here so the except block can always
        # reference it.  Once the commit is resolved it is reassigned; if the
        # exception fires before that point commit stays None (correct), if it
        # fires after, we pass the already-resolved value into DeploymentResult.
        commit: str | None = None

        try:
            await deployments_repo.update_deployment_stage(dep_id, stage)
            for field in ("app_name", "repository", "branch", "start_command",
                          "process_type", "dyno_type", "region"):
                if not profile.get(field) and profile.get(field) != 0:
                    raise ValueError(f"Profile is missing required field: {field}")

            # Resolve commit + idempotency
            async with GitHubClient() as gh:
                commit = await gh.resolve_commit(profile["repository"], profile["branch"])
            await deployments_repo.set_commit(dep_id, commit)

            existing = await deployments_repo.get_last_successful_deployment(
                profile["id"], commit
            )
            if existing and not force:
                await deployments_repo.finish_deployment(dep_id, status="cancelled")
                raise AlreadyDeployedError(commit, existing["id"])

            # --- CREATING_APP ---
            stage = "creating_app"
            await deployments_repo.update_deployment_stage(dep_id, stage)
            await self._progress("Checking Heroku app", done=False)

            managed = await managed_apps_repo.get_by_profile(profile["id"])
            heroku_app = None
            if managed:
                try:
                    heroku_app = await self._heroku.apps.get(managed["heroku_app_id"])
                except HerokuNotFoundError:
                    await managed_apps_repo.delete_managed_app(profile["id"])
                    managed = None

            if heroku_app is None:
                try:
                    heroku_app = await self._heroku.apps.get(profile["app_name"])
                    # App exists on Heroku but we don't manage it
                    if not adopt_existing:
                        raise AppAdoptionRequiredError(
                            profile["app_name"], heroku_app["id"]
                        )
                except HerokuNotFoundError:
                    heroku_app = await self._heroku.apps.create(
                        profile["app_name"], profile["region"]
                    )

            heroku_app_id = heroku_app["id"]
            await deployments_repo.update_heroku_app_id(dep_id, heroku_app_id)
            await managed_apps_repo.register_managed_app(
                profile["id"], heroku_app_id, heroku_app["name"],
                profile["heroku_account_id"],
            )
            await self._progress("Checking Heroku app", done=True)

            # --- CONFIGURING ---
            stage = "configuring"
            await deployments_repo.update_deployment_stage(dep_id, stage)
            await self._progress("Configuring environment", done=False)
            env_vars = await profiles_repo.get_env_vars_decrypted(profile["id"])
            if env_vars:
                await self._heroku.config_vars.update(profile["app_name"], env_vars)
            await self._progress("Configuring environment", done=True)

            # --- UPLOADING ---
            stage = "uploading"
            await deployments_repo.update_deployment_stage(dep_id, stage)
            await self._progress("Deploying source", done=False)
            async with GitHubClient() as gh:
                tarball_url = await gh.get_tarball_url(profile["repository"], commit)
                tarball = await gh.download_tarball(tarball_url)
            tarball = inject_procfile(
                tarball, profile["process_type"], profile["start_command"]
            )
            source = await self._heroku.sources.create(profile["app_name"])
            source_blob = source["source_blob"]
            await self._heroku.sources.upload(source_blob["put_url"], tarball)
            await self._progress("Deploying source", done=True)

            # --- BUILDING ---
            stage = "building"
            await deployments_repo.update_deployment_stage(dep_id, stage)
            await self._progress("Building", done=False)
            build = await self._heroku.builds.create(
                profile["app_name"],
                {"url": source_blob["get_url"], "checksum": None},
            )
            await self._heroku.builds.poll_until_complete(profile["app_name"], build["id"])
            await self._progress("Building", done=True)

            # --- RELEASING ---
            stage = "releasing"
            await deployments_repo.update_deployment_stage(dep_id, stage)
            await self._progress("Creating release", done=False)
            release_version = await self._wait_for_release(profile["app_name"])
            await self._progress("Creating release", done=True)

            # --- SCALING ---
            stage = "scaling"
            await deployments_repo.update_deployment_stage(dep_id, stage)
            await self._progress("Scaling dynos", done=False)
            await self._heroku.formation.update(
                profile["app_name"], profile["process_type"],
                profile["dyno_count"], profile["dyno_type"],
            )
            await self._progress("Scaling dynos", done=True)

            # --- STARTING ---
            stage = "starting"
            await deployments_repo.update_deployment_stage(dep_id, stage)
            await self._progress("Starting dyno", done=False)
            if profile["dyno_count"] > 0:
                await self._heroku.dynos.restart_all(profile["app_name"])
            await self._progress("Starting dyno", done=True)

            # --- VERIFYING ---
            stage = "verifying"
            await deployments_repo.update_deployment_stage(dep_id, stage)
            await self._progress("Verifying", done=False)
            verified = await self._verify(profile["app_name"])
            await self._progress("Verifying", done=True)

            await deployments_repo.finish_deployment(
                dep_id, status="success", release_version=release_version
            )
            return DeploymentResult(
                deployment_id=dep_id, status="success",
                app_name=profile["app_name"], commit=commit,
                release_version=release_version, verified=verified,
            )

        except (AppAdoptionRequiredError, AlreadyDeployedError):
            raise
        except Exception as exc:
            logger.exception("deployment_failed", extra={"deployment_id": dep_id, "stage": stage})
            await deployments_repo.finish_deployment(
                dep_id, status="failed", error_message=str(exc)[:500]
            )
            # FIX #6: Pass the already-resolved `commit` value (which may still
            # be None if the failure occurred before the GitHub call, but is the
            # real SHA if it happened later).  The original code always passed
            # commit=None, discarding the commit even when it was known.
            return DeploymentResult(
                deployment_id=dep_id, status="failed",
                app_name=profile["app_name"], commit=commit,
                release_version=release_version, verified=False,
                error_message=f"{stage}: {exc}",
            )

    async def _wait_for_release(self, app: str, timeout: int = 120) -> str | None:
        elapsed = 0
        while elapsed < timeout:
            releases = await self._heroku.releases.list(app, limit=1)
            if releases and releases[0].get("current"):
                return releases[0].get("version") and f"v{releases[0]['version']}"
            await asyncio.sleep(5)
            elapsed += 5
        releases = await self._heroku.releases.list(app, limit=1)
        if releases:
            return f"v{releases[0]['version']}"
        return None

    async def _verify(self, app: str) -> bool:
        for _ in range(5):
            dynos = await self._heroku.dynos.list(app)
            if any(d.get("state") == "up" for d in dynos):
                return True
            await asyncio.sleep(3)
        return False
