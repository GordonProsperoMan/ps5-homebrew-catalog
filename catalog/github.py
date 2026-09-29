"""Minimal read-only GitHub REST client built on the standard library."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from urllib.parse import quote

API = "https://api.github.com"
USER_AGENT = "ps5-homebrew-catalog-verifier"
TIMEOUT = 30


class GitHubError(RuntimeError):
    pass


class GitHub:
    def __init__(self, token: str | None = None):
        self.token = token if token is not None else os.environ.get("GITHUB_TOKEN")

    def _get(self, path: str):
        """Return decoded JSON, or None for 404. Other failures raise GitHubError."""
        request = urllib.request.Request(API + path, headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": USER_AGENT,
        })
        if self.token:
            request.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
                body = response.read()
                return json.loads(body) if body else {}
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            if error.code in (403, 429) and error.headers.get("x-ratelimit-remaining") == "0":
                raise GitHubError("GitHub API rate limit reached; set GITHUB_TOKEN") from error
            raise GitHubError(f"GitHub API returned HTTP {error.code} for {path}") from error
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            raise GitHubError(f"GitHub API request failed for {path}: {error}") from error

    def repo(self, owner: str, name: str) -> dict | None:
        return self._get(f"/repos/{quote(owner)}/{quote(name)}")

    def release_by_tag(self, owner: str, name: str, tag: str) -> dict | None:
        return self._get(f"/repos/{quote(owner)}/{quote(name)}/releases/tags/{quote(tag, safe='')}")

    def releases(self, owner: str, name: str) -> list[dict]:
        return self._get(f"/repos/{quote(owner)}/{quote(name)}/releases?per_page=20") or []

    def is_public_member(self, org: str, user: str) -> bool:
        """True when user publicly belongs to org (GitHub answers 204 or 404)."""
        return self._get(f"/orgs/{quote(org)}/public_members/{quote(user)}") is not None
