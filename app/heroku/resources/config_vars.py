from app.heroku.client import HerokuClient


class ConfigVarsResource:
    def __init__(self, client: HerokuClient) -> None:
        self._client = client

    async def update(self, app: str, vars: dict) -> dict:
        """Set config vars; a value of None deletes the key."""
        return await self._client.patch(f"/apps/{app}/config-vars", json=vars)

    async def list(self, app: str) -> dict:
        return await self._client.get(f"/apps/{app}/config-vars")
