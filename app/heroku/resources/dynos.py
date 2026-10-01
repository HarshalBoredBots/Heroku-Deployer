from app.heroku.client import HerokuClient


class DynosResource:
    def __init__(self, client: HerokuClient) -> None:
        self._client = client

    async def list(self, app: str) -> list[dict]:
        return await self._client.get(f"/apps/{app}/dynos")

    async def restart_all(self, app: str) -> None:
        await self._client.delete(f"/apps/{app}/dynos")
