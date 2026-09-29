"""Fetch icons with hard limits, and inspect them. Artifacts are never downloaded."""

from __future__ import annotations

import urllib.error
import urllib.request

from .github import USER_AGENT

MAX_ARTIFACT_BYTES = 2 << 30          # GitHub's per-asset limit
MAX_ICON_BYTES = 2 << 20
TIMEOUT = 60


class DownloadError(RuntimeError):
    pass


def _open(url: str):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        response = urllib.request.urlopen(request, timeout=TIMEOUT)
    except urllib.error.HTTPError as error:
        raise DownloadError(f"HTTP {error.code} from {url}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise DownloadError(f"could not download {url}: {error}") from error
    if not response.geturl().startswith("https://"):
        response.close()
        raise DownloadError(f"{url} redirected to a non-HTTPS location")
    return response


def fetch_small(url: str, max_bytes: int) -> bytes:
    with _open(url) as response:
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise DownloadError(f"{url} is larger than {max_bytes} bytes")
    return data


def inspect_icon(data: bytes) -> tuple[str | None, list[str]]:
    """Return (format, warnings) for image bytes; format None means not an accepted image."""
    warnings = []
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width = int.from_bytes(data[16:20], "big")
        height = int.from_bytes(data[20:24], "big")
        if width != height:
            warnings.append(f"icon is {width}x{height}; a square image is recommended")
        elif width < 256:
            warnings.append(f"icon is {width}x{height}; at least 256x256 is recommended")
        return "png", warnings
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg", warnings
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp", warnings
    return None, warnings
