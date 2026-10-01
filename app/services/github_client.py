"""Async GitHub API client for commit resolution and tarball downloads."""

import httpx

from app.services.validation import validate_repo_url


class GitHubError(Exception):
    pass


def _owner_repo(repo_url: str) -> tuple[str, str]:
    url = validate_repo_url(repo_url)
    parts = url.removeprefix("https://github.com/").split("/")
    return parts[0], parts[1]


class GitHubClient:
    def __init__(self, token: str | None = None) -> None:
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._client = httpx.AsyncClient(
            base_url="https://api.github.com", headers=headers, timeout=60.0
        )

    async def __aenter__(self) -> "GitHubClient":
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def resolve_commit(self, repo_url: str, branch: str) -> str:
        """Return the HEAD commit SHA for branch."""
        owner, repo = _owner_repo(repo_url)
        response = await self._client.get(f"/repos/{owner}/{repo}/commits/{branch}")
        if response.status_code != 200:
            raise GitHubError(f"Could not resolve branch '{branch}' (HTTP {response.status_code})")
        return response.json()["sha"]

    async def get_tarball_url(self, repo_url: str, commit: str) -> str:
        owner, repo = _owner_repo(repo_url)
        return f"https://api.github.com/repos/{owner}/{repo}/tarball/{commit}"

    async def download_tarball(self, url: str) -> bytes:
        response = await self._client.get(url, follow_redirects=True, timeout=300.0)
        if response.status_code != 200:
            raise GitHubError(f"Tarball download failed (HTTP {response.status_code})")
        return response.content
