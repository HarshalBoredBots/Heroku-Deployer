from app.heroku.client import HerokuClient


class AppsResource:
    def __init__(self, client: HerokuClient) -> None:
        self._client = client

    async def create(self, name: str, region: str) -> dict:
        return await self._client.post("/apps", json={"name": name, "region": region})

    async def get(self, app_id_or_name: str) -> dict:
        return await self._client.get(f"/apps/{app_id_or_name}")

    async def delete(self, app_id_or_name: str) -> None:
        await self._client.delete(f"/apps/{app_id_or_name}")

    async def list(self) -> list[dict]:
        return await self._client.get("/apps")
