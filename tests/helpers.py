"""Shared fixtures for the catalog tests."""

import json
import zipfile
from pathlib import Path

VALID = {
    "titleid": "PPSA01234",
    "name": "Example App",
    "kind": "app",
    "description": "One short sentence about the app.",
    "license": "GPL-3.0",
    "author": "Example Dev",
    "version": "01.000.000",
    "source_repo": "https://github.com/example/example-app",
    "artifact_url": "https://github.com/example/example-app/releases/download/01.000.000/PPSA01234.zip",
    "sha256": "a" * 64,
    "icon_url": "https://raw.githubusercontent.com/example/example-app/01.000.000/sce_sys/icon0.png",
}


def record(**changes):
    data = dict(VALID)
    data.update(changes)
    return data


def write_record(directory: Path, data: dict, filename: str | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (filename or f"{data.get('titleid', 'PPSA01234')}.json")
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def write_zip(path: Path, entries: dict, titleid: str = "PPSA01234") -> Path:
    """entries maps archive names to bytes (or None for a directory)."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            if content is None:
                archive.writestr(zipfile.ZipInfo(name), b"")
            else:
                archive.writestr(name, content)
    return path


def package_entries(titleid: str = "PPSA01234", param_titleid: str | None = None) -> dict:
    return {
        f"{titleid}/": None,
        f"{titleid}/eboot.bin": b"\x7fELF" + b"\x00" * 64,
        f"{titleid}/sce_sys/param.json": json.dumps(
            {"titleId": param_titleid or titleid, "contentVersion": "01.000.000"}).encode(),
        f"{titleid}/sce_sys/icon0.png": b"\x89PNG\r\n\x1a\n",
    }
