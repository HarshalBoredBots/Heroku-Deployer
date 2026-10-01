"""Input validators for profile fields."""

import re

_APP_NAME_RE = re.compile(r"^[a-z][a-z0-9-]{1,28}[a-z0-9]$")
_REPO_RE = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/?$")
_BRANCH_BAD_CHARS = re.compile(r"[\s~^:?*\[\]\\]")


def validate_app_name(name: str) -> str:
    name = name.strip().lower()
    if not _APP_NAME_RE.match(name):
        raise ValueError(
            "Invalid Heroku app name. Use 3-30 lowercase letters, digits and hyphens, "
            "starting with a letter and not ending with a hyphen."
        )
    return name


def validate_repo_url(url: str) -> str:
    url = url.strip().removesuffix(".git").rstrip("/")
    if not _REPO_RE.match(url):
        raise ValueError("Invalid repository URL. Expected https://github.com/user/repo")
    return url


def validate_branch(branch: str) -> str:
    branch = branch.strip()
    if not branch or len(branch) > 255 or _BRANCH_BAD_CHARS.search(branch):
        raise ValueError("Invalid branch name (no spaces or special characters).")
    return branch


def validate_start_command(cmd: str) -> str:
    cmd = cmd.strip()
    if not cmd or len(cmd) > 500:
        raise ValueError("Start command must be 1-500 characters.")
    return cmd


def validate_process_type(ptype: str) -> str:
    ptype = ptype.strip()
    if not ptype or len(ptype) > 128:
        raise ValueError("Process type must be 1-128 characters.")
    return ptype


def validate_dyno_count(text: str) -> int:
    try:
        count = int(text.strip())
    except ValueError:
        raise ValueError("Dyno count must be an integer between 0 and 100.") from None
    if not 0 <= count <= 100:
        raise ValueError("Dyno count must be between 0 and 100.")
    return count
