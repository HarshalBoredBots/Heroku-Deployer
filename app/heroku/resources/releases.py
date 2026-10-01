from app.heroku.client import HerokuClient


class ReleasesResource:
    def __init__(self, client: HerokuClient) -> None:
        self._client = client

    async def list(self, app: str, limit: int = 10) -> list[dict]:
        # FIX #7: The Heroku Platform API does not accept a "limit" query
        # parameter on GET /apps/{app}/releases.  Pagination is controlled via
        # the "Range" request header (e.g. "Range: version ..; max=10; order=desc").
        # Passing params={"limit": limit} was silently ignored, causing the
        # endpoint to return all releases (potentially hundreds) every call.
        #
        # Fix: fetch all releases and slice client-side.  If the caller only
        # needs the most recent N entries the overhead is acceptable given that
        # Heroku already caps the response at 200 items by default.  For callers
        # that genuinely need pagination, the Range header approach should be
        # adopted; that is left as a future improvement because it would require
        # changing the public API of this method.
        releases = await self._client.get(f"/apps/{app}/releases")
        if not releases:
            return []
        # Heroku returns releases in ascending version order; reverse so index 0
        # is always the most recent, then honour the caller's limit.
        releases_desc = list(reversed(releases))
        return releases_desc[:limit]

    async def rollback(self, app: str, release_id: str) -> dict:
        return await self._client.post(
            f"/apps/{app}/releases", json={"release": release_id}
        )
