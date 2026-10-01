import httpx

from app.heroku.client import HerokuClient


class SourcesResource:
    def __init__(self, client: HerokuClient) -> None:
        self._client = client

    async def create(self, app: str) -> dict:
        return await self._client.post(f"/apps/{app}/sources")

    async def upload(self, put_url: str, tarball_bytes: bytes) -> None:
        async with httpx.AsyncClient(timeout=300.0) as http:
            response = await http.put(
                put_url,
                content=tarball_bytes,
                headers={"Content-Type": "application/octet-stream"},
            )
            response.raise_for_status()
