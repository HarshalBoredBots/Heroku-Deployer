import asyncio

from app.heroku.client import HerokuClient
from app.heroku.exceptions import HerokuAPIError


class BuildsResource:
    def __init__(self, client: HerokuClient) -> None:
        self._client = client

    async def create(self, app: str, source_blob: dict) -> dict:
        return await self._client.post(
            f"/apps/{app}/builds", json={"source_blob": source_blob}
        )

    async def get(self, app: str, build_id: str) -> dict:
        return await self._client.get(f"/apps/{app}/builds/{build_id}")

    async def poll_until_complete(
        self, app: str, build_id: str, *, timeout: int = 600, interval: int = 5
    ) -> dict:
        elapsed = 0
        while elapsed < timeout:
            build = await self.get(app, build_id)
            status = build.get("status")
            if status == "succeeded":
                return build
            if status == "failed":
                raise HerokuAPIError(
                    f"Build failed: {build.get('failure_reason') or 'unknown reason'}"
                )
            await asyncio.sleep(interval)
            elapsed += interval
        raise HerokuAPIError(f"Build timed out after {timeout}s")
