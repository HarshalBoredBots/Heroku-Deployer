from app.heroku.client import HerokuClient


class AccountResource:
    def __init__(self, client: HerokuClient) -> None:
        self._client = client

    async def info(self) -> dict:
        return await self._client.get("/account")
