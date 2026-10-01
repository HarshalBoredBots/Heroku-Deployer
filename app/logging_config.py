"""Structured JSON logging with sensitive-field redaction."""

import json
import logging
import sys

_SENSITIVE_KEYS = {
    "bot_token", "api_hash", "api_id", "database_url", "mongodb_uri",
    "heroku_api_key", "encryption_key", "github_webhook_secret",
    "webhook_secret", "config_vars", "env_vars", "env_value",
    "secret", "password", "token", "api_key", "api_key_encrypted",
    "put_url", "get_url",
}


def _redact(obj):
    if isinstance(obj, dict):
        return {k: ("[REDACTED]" if k.lower() in _SENSITIVE_KEYS else _redact(v)) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_redact(v) for v in obj]
    return obj


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in logging.LogRecord("", 0, "", 0, "", (), None).__dict__ and key not in (
                "message", "asctime", "taskName",
            ):
                payload[key] = _redact(value)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(log_level: str) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(log_level.upper())
    logging.getLogger("pyrogram").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
