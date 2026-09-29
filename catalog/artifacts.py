"""Download artifacts and icons with hard limits, and inspect package ZIPs.

Nothing downloaded here is ever executed or extracted to disk.
"""

from __future__ import annotations

import hashlib
import json
import re
import stat
import urllib.error
import urllib.request
import zipfile
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from .github import USER_AGENT

MAX_ARTIFACT_BYTES = 1 << 30          # 1 GiB compressed
MAX_UNPACKED_BYTES = 4 << 30          # 4 GiB after extraction
MAX_ENTRIES = 20_000
MAX_PATH_BYTES = 1024
MAX_COMPONENT_BYTES = 255
MAX_PARAM_JSON_BYTES = 64 << 10
MAX_ICON_BYTES = 2 << 20
TIMEOUT = 60
CHUNK = 1 << 20

REQUIRED_FILES = ("eboot.bin", "sce_sys/param.json")
DRIVE_PATH = re.compile(r"[A-Za-z]:")


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


def download(url: str, destination: Path, max_bytes: int = MAX_ARTIFACT_BYTES) -> tuple[int, str]:
    """Stream url to destination, returning (byte count, sha256 hex)."""
    digest = hashlib.sha256()
    size = 0
    with _open(url) as response, open(destination, "wb") as output:
        declared = response.headers.get("Content-Length")
        if declared and declared.isdigit() and int(declared) > max_bytes:
            raise DownloadError(f"artifact is {int(declared)} bytes; the limit is {max_bytes}")
        while chunk := response.read(CHUNK):
            size += len(chunk)
            if size > max_bytes:
                raise DownloadError(f"artifact exceeds the {max_bytes}-byte limit")
            digest.update(chunk)
            output.write(chunk)
        if declared and declared.isdigit() and int(declared) != size:
            raise DownloadError(f"download was truncated ({size} of {declared} bytes)")
    return size, digest.hexdigest()


def fetch_small(url: str, max_bytes: int) -> bytes:
    with _open(url) as response:
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise DownloadError(f"{url} is larger than {max_bytes} bytes")
    return data


@dataclass
class PackageResult:
    errors: list[str] = field(default_factory=list)
    param: dict | None = None
    files: int = 0
    unpacked_bytes: int = 0


def inspect_package(path: Path, titleid: str) -> PackageResult:
    """Check a ZIP against the homebrew-zip-v1 layout (docs/package-format.md)."""
    result = PackageResult()
    errors = result.errors
    try:
        archive = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as error:
        errors.append(f"artifact is not a valid ZIP archive: {error}")
        return result

    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_ENTRIES:
            errors.append(f"archive has {len(infos)} entries; the limit is {MAX_ENTRIES}")
            return result
        seen: dict[str, str] = {}
        files: dict[str, zipfile.ZipInfo] = {}
        declared_total = 0
        for info in infos:
            name = info.filename
            problem = _entry_problem(info, titleid)
            if problem:
                errors.append(f"archive entry {name!r} {problem}")
                continue
            key = name.rstrip("/")
            folded = key.casefold()
            if folded in seen:
                errors.append(f"archive entry {name!r} duplicates {seen[folded]!r}")
                continue
            seen[folded] = name
            if not info.is_dir():
                files[key] = info
                declared_total += info.file_size
        if len(errors) > 20:
            del errors[20:]
            errors.append("further archive problems omitted")
        for required in REQUIRED_FILES:
            if f"{titleid}/{required}" not in files:
                errors.append(f"archive is missing {titleid}/{required}")
        if declared_total > MAX_UNPACKED_BYTES:
            errors.append(f"archive unpacks to {declared_total} bytes; the limit is {MAX_UNPACKED_BYTES}")
        if errors:
            return result

        # Decompress every file once, bounded by actual output, so CRC errors and
        # lying headers are caught without extracting anything to disk.
        total = 0
        try:
            for key, info in files.items():
                entry_size = 0
                with archive.open(info) as member:
                    while chunk := member.read(CHUNK):
                        entry_size += len(chunk)
                        total += len(chunk)
                        if total > MAX_UNPACKED_BYTES:
                            errors.append(f"archive unpacks beyond the {MAX_UNPACKED_BYTES}-byte limit")
                            return result
                if entry_size != info.file_size:
                    errors.append(f"archive entry {key!r} size does not match its header")
        except (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError, OSError) as error:
            errors.append(f"archive is corrupt or uses an unsupported feature: {error}")
            return result
        result.files = len(files)
        result.unpacked_bytes = total

        param_info = files[f"{titleid}/sce_sys/param.json"]
        if param_info.file_size > MAX_PARAM_JSON_BYTES:
            errors.append("sce_sys/param.json is unreasonably large")
            return result
        try:
            param = json.loads(archive.read(param_info).decode("utf-8-sig"))
        except (UnicodeDecodeError, ValueError) as error:
            errors.append(f"sce_sys/param.json is not valid JSON: {error}")
            return result
        if not isinstance(param, dict):
            errors.append("sce_sys/param.json must contain a JSON object")
            return result
        if param.get("titleId") != titleid:
            errors.append(f"sce_sys/param.json titleId is {param.get('titleId')!r}, expected {titleid!r}")
        result.param = param
    return result


def _entry_problem(info: zipfile.ZipInfo, titleid: str) -> str | None:
    name = info.filename
    if info.flag_bits & 0x1:
        return "is encrypted"
    if "\\" in name or name.startswith("/") or DRIVE_PATH.match(name) or "\x00" in name:
        return "has an unsafe path"
    parts = name.rstrip("/").split("/")
    if any(part in ("", ".", "..") for part in parts):
        return "has an unsafe path"
    if len(name.encode()) > MAX_PATH_BYTES or any(len(p.encode()) > MAX_COMPONENT_BYTES for p in parts):
        return "has a path that is too long"
    if info.create_system == 3:  # Unix attributes are present
        kind = stat.S_IFMT(info.external_attr >> 16)
        if kind not in (0, stat.S_IFREG, stat.S_IFDIR):
            return "is a symbolic link or special file"
    if parts[0] != titleid:
        return f"is outside the single top-level {titleid}/ folder"
    return None


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
