import httpx

from app.heroku.client import HerokuClient


class LogSessionsResource:
    def __init__(self, client: HerokuClient) -> None:
        self._client = client

    async def create(self, app: str, *, lines: int = 100, tail: bool = False) -> dict:
        return await self._client.post(
            f"/apps/{app}/log-sessions",
            json={"lines": lines, "tail": tail, "source": "app"},
        )

    async def fetch_lines(self, logplex_url: str, lines: int = 100) -> str:
        async with httpx.AsyncClient(timeout=30.0) as http:
            response = await http.get(logplex_url)
            response.raise_for_status()
            text = response.text
        return "\n".join(text.splitlines()[-lines:])
