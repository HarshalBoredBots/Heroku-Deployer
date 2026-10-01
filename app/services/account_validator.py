"""Validate a Heroku API key by calling /account."""

from app.heroku.api import HerokuAPI
from app.heroku.exceptions import HerokuAPIError


async def validate_heroku_api_key(api_key: str) -> dict:
    """Return account info on success, raise HerokuAPIError on failure."""
    async with HerokuAPI(api_key) as api:
        try:
            return await api.account.info()
        except HerokuAPIError:
            raise
