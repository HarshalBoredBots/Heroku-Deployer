from app.heroku.client import HerokuClient


class FormationResource:
    def __init__(self, client: HerokuClient) -> None:
        self._client = client

    async def update(self, app: str, process_type: str, quantity: int, size: str) -> dict:
        return await self._client.patch(
            f"/apps/{app}/formation/{process_type}",
            json={"quantity": quantity, "size": size},
        )

    async def list(self, app: str) -> list[dict]:
        return await self._client.get(f"/apps/{app}/formation")
