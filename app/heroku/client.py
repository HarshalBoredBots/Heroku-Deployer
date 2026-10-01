"""Async Heroku HTTP client with retry policy."""

import asyncio
import logging

import httpx

from app.heroku.exceptions import (
    HerokuAPIError,
    HerokuAuthError,
    HerokuConflictError,
    HerokuNotFoundError,
    HerokuRateLimitError,
    HerokuServerError,
    HerokuValidationError,
)

logger = logging.getLogger(__name__)

BASE_URL = "https://api.heroku.com"
_IDEMPOTENT_METHODS = {"GET", "HEAD", "OPTIONS"}
_MAX_5XX_RETRIES = 5


class HerokuClient:
    def __init__(self, api_key: str) -> None:
        self._client = httpx.AsyncClient(
            base_url=BASE_URL,
            headers={
                "Accept": "application/vnd.heroku+json; version=3",
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            timeout=60.0,
            # FIX #18: Some Heroku API endpoints (e.g. source blob uploads and
            # certain OAuth flows) issue HTTP 3xx redirects.  Without
            # follow_redirects=True httpx raises a RedirectError, causing the
            # deploy pipeline to fail mid-flight.
            follow_redirects=True,
        )

    async def __aenter__(self) -> "HerokuClient":
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    def _raise_for_status(self, response: httpx.Response) -> None:
        code = response.status_code
        try:
            message = response.json().get("message", response.text[:200])
        except Exception:
            message = response.text[:200]
        if code == 401:
            raise HerokuAuthError(message, code)
        if code == 404:
            raise HerokuNotFoundError(message, code)
        if code == 409:
            raise HerokuConflictError(message, code)
        if code == 422:
            raise HerokuValidationError(message, code)
        if code == 429:
            raise HerokuRateLimitError(message, code)
        if code >= 500:
            raise HerokuServerError(message, code)
        if code >= 400:
            raise HerokuAPIError(message, code)

    async def request(self, method: str, path: str, **kwargs):
        method = method.upper()
        attempts = 0
        while True:
            attempts += 1
            try:
                response = await self._client.request(method, path, **kwargs)
            except httpx.TransportError as exc:
                if method in _IDEMPOTENT_METHODS and attempts < _MAX_5XX_RETRIES:
                    await asyncio.sleep(min(2 ** attempts, 30))
                    continue
                raise HerokuAPIError(f"Network error: {exc}") from exc

            if response.status_code == 429:
                retry_after = float(response.headers.get("Retry-After", 5))
                logger.warning("heroku_rate_limited", extra={"path": path, "retry_after": retry_after})
                await asyncio.sleep(retry_after)
                continue

            if response.status_code >= 500 and method in _IDEMPOTENT_METHODS and attempts < _MAX_5XX_RETRIES:
                await asyncio.sleep(min(2 ** attempts, 30))
                continue

            if response.status_code >= 400:
                self._raise_for_status(response)

            if response.status_code == 204 or not response.content:
                return None
            return response.json()

    async def get(self, path: str, **kwargs):
        return await self.request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs):
        return await self.request("POST", path, **kwargs)

    async def patch(self, path: str, **kwargs):
        return await self.request("PATCH", path, **kwargs)

    async def delete(self, path: str, **kwargs):
        return await self.request("DELETE", path, **kwargs)
