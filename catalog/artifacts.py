"""Download artifacts and icons with hard limits.

Artifacts are only hashed; nothing downloaded here is opened, extracted or executed.
"""

from __future__ import annotations

import hashlib
import urllib.error
import urllib.request

from .github import USER_AGENT

MAX_ARTIFACT_BYTES = 2 << 30          # GitHub's per-asset limit
MAX_ICON_BYTES = 2 << 20
TIMEOUT = 60
CHUNK = 1 << 20


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


def hash_download(url: str, max_bytes: int = MAX_ARTIFACT_BYTES) -> tuple[int, str]:
    """Stream url without storing it, returning (byte count, sha256 hex)."""
    digest = hashlib.sha256()
    size = 0
    with _open(url) as response:
        declared = response.headers.get("Content-Length")
        if declared and declared.isdigit() and int(declared) > max_bytes:
            raise DownloadError(f"artifact is {int(declared)} bytes; the limit is {max_bytes}")
        while chunk := response.read(CHUNK):
            size += len(chunk)
            if size > max_bytes:
                raise DownloadError(f"artifact exceeds the {max_bytes}-byte limit")
            digest.update(chunk)
        if declared and declared.isdigit() and int(declared) != size:
            raise DownloadError(f"download was truncated ({size} of {declared} bytes)")
    return size, digest.hexdigest()


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
