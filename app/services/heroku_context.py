"""Resolve which Heroku account / API key to use for an operation."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from app.config import get_settings
from app.crypto import decrypt_value
from app.db.repositories import accounts as accounts_repo
from app.heroku.api import HerokuAPI

# In-memory: user_id -> active account_id (resets on restart)
_active_accounts: dict[int, int] = {}


def get_active_account_id(user_id: int) -> int | None:
    return _active_accounts.get(user_id)


def set_active_account_id(user_id: int, account_id: int) -> None:
    _active_accounts[user_id] = account_id


def clear_active_account_id(user_id: int) -> None:
    _active_accounts.pop(user_id, None)


@asynccontextmanager
async def default_heroku_api() -> AsyncGenerator[HerokuAPI, None]:
    """Uses the default account's API key (falls back to env HEROKU_API_KEY)."""
    account = await accounts_repo.get_default_account()
    if account:
        api_key = decrypt_value(account["api_key_encrypted"])
    else:
        api_key = get_settings().heroku_api_key
    async with HerokuAPI(api_key) as api:
        yield api


@asynccontextmanager
async def heroku_api_for_user(user_id: int) -> AsyncGenerator[HerokuAPI, None]:
    """Uses the user's session-selected account, falling back to default."""
    account_id = get_active_account_id(user_id)
    account = await accounts_repo.get_account_by_id(account_id) if account_id else None
    if account:
        async with account_heroku_api(account) as api:
            yield api
    else:
        async with default_heroku_api() as api:
            yield api


@asynccontextmanager
async def account_heroku_api(account: dict) -> AsyncGenerator[HerokuAPI, None]:
    """Uses a specific account document's encrypted key."""
    api_key = decrypt_value(account["api_key_encrypted"])
    async with HerokuAPI(api_key) as api:
        yield api


@asynccontextmanager
async def heroku_api_for_profile(profile: dict) -> AsyncGenerator[HerokuAPI, None]:
    """Uses the account attached to a deployment profile."""
    account = await accounts_repo.get_account_by_id(profile["heroku_account_id"])
    if account:
        async with account_heroku_api(account) as api:
            yield api
    else:
        async with default_heroku_api() as api:
            yield api
