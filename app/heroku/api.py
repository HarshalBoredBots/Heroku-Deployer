"""HerokuAPI facade grouping all resources."""

from app.heroku.client import HerokuClient
from app.heroku.resources import (
    AccountResource,
    AppsResource,
    BuildsResource,
    ConfigVarsResource,
    DynosResource,
    DynoSizesResource,
    FormationResource,
    LogSessionsResource,
    RegionsResource,
    ReleasesResource,
    SourcesResource,
)


class HerokuAPI:
    def __init__(self, api_key: str) -> None:
        self._client = HerokuClient(api_key)
        self.account = AccountResource(self._client)
        self.apps = AppsResource(self._client)
        self.regions = RegionsResource(self._client)
        self.config_vars = ConfigVarsResource(self._client)
        self.builds = BuildsResource(self._client)
        self.formation = FormationResource(self._client)
        self.dynos = DynosResource(self._client)
        self.dyno_sizes = DynoSizesResource(self._client)
        self.releases = ReleasesResource(self._client)
        self.log_sessions = LogSessionsResource(self._client)
        self.sources = SourcesResource(self._client)

    async def __aenter__(self) -> "HerokuAPI":
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self._client.aclose()
