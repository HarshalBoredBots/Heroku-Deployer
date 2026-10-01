"""Parse .env-format text into a key/value dict."""

from app.security import validate_env_key, validate_env_value


class EnvParseError(ValueError):
    pass


def parse_env_text(text: str) -> dict[str, str]:
    """Parse .env text. Supports comments (#), blank lines, optional quotes,
    and optional leading 'export '."""
    result: dict[str, str] = {}
    for lineno, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export "):].lstrip()
        if "=" not in line:
            raise EnvParseError(f"Line {lineno}: missing '=' — {line[:40]}")
        key, _, value = line.partition("=")
        key = validate_env_key(key)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        result[key] = validate_env_value(value)
    return result
