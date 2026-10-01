from app.heroku.client import HerokuClient


class RegionsResource:
    def __init__(self, client: HerokuClient) -> None:
        self._client = client

    async def list(self) -> list[dict]:
        return await self._client.get("/regions")
