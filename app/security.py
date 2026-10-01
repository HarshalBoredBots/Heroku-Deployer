"""Security helpers: error sanitization, rate limiting, env var validation."""

import re
import time


_URL_CRED_RE = re.compile(r"(https?://)[^/@\s:]+:[^/@\s]+@")
_KV_RE = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*=[^\s\"']+")
_QUOTED_RE = re.compile(r"(['\"])(?:(?!\1).){8,}?\1")
_ENV_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

MAX_ENV_VALUE_LENGTH = 32768


def sanitize_error(exc: BaseException | str) -> str:
    """Strip potential secrets from error text for safe display in Telegram."""
    text = str(exc)
    text = _URL_CRED_RE.sub(r"\1[REDACTED]@", text)
    text = _KV_RE.sub("[REDACTED]", text)
    text = _QUOTED_RE.sub("[REDACTED]", text)
    return text[:200]


class RateLimiter:
    """Per-user sliding-window rate limiter."""

    def __init__(self, max_calls: int = 20, window_seconds: int = 60) -> None:
        self.max_calls = max_calls
        self.window = window_seconds
        self._calls: dict[int, list[float]] = {}

    def allow(self, user_id: int) -> bool:
        now = time.monotonic()
        calls = self._calls.setdefault(user_id, [])
        cutoff = now - self.window
        while calls and calls[0] < cutoff:
            calls.pop(0)
        if len(calls) >= self.max_calls:
            return False
        calls.append(now)
        return True


rate_limiter = RateLimiter()


def validate_env_key(key: str) -> str:
    key = key.strip()
    if not key or len(key) > 255 or not _ENV_KEY_RE.match(key):
        raise ValueError(
            "Invalid env var key. Must start with a letter or underscore and "
            "contain only letters, digits and underscores (max 255 chars)."
        )
    return key


def validate_env_value(value: str) -> str:
    if len(value) > MAX_ENV_VALUE_LENGTH:
        raise ValueError(f"Env var value too long (max {MAX_ENV_VALUE_LENGTH} chars).")
    return value
