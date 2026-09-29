#!/usr/bin/env python3
"""Check the public catalog's small JSON records."""

import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
FIELDS = {
    "titleid", "name", "kind", "description", "license",
    "author", "version", "source_repo", "artifact_url",
}
TITLE_ID = re.compile(r"PPSA9900[1-9]\Z")
REPO_PART = re.compile(r"[A-Za-z0-9_.-]+\Z")


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def check(condition, message):
    if not condition:
        raise ValueError(message)


def validate(path):
    check(not path.is_symlink() and path.stat().st_size <= 8192, "unsafe or oversized JSON file")
    data = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_keys)
    check(isinstance(data, dict) and data.keys() == FIELDS, "expected exactly nine metadata fields")
    for field in FIELDS:
        value = data[field]
        check(isinstance(value, str) and 0 < len(value) <= 500 and value.strip() == value,
              f"invalid {field}")
    check(TITLE_ID.fullmatch(data["titleid"]) and path.stem == data["titleid"],
          "filename must match a title ID from PPSA99001 to PPSA99009")
    check(data["kind"] in {"app", "game", "tool"}, "invalid kind")

    source = urlsplit(data["source_repo"])
    parts = source.path.strip("/").split("/")
    check(source.scheme == "https" and source.netloc == "github.com"
          and len(parts) == 2 and all(REPO_PART.fullmatch(part) and part not in {".", ".."} for part in parts)
          and not source.query and not source.fragment, "invalid source_repo")

    artifact = urlsplit(data["artifact_url"])
    expected = data["source_repo"] + "/releases/download/"
    suffix = data["artifact_url"][len(expected):] if data["artifact_url"].startswith(expected) else ""
    check(artifact.scheme == "https" and artifact.netloc == "github.com"
          and re.fullmatch(r"[^/]+/[^/]+\.zip", suffix)
          and not artifact.query and not artifact.fragment, "invalid artifact_url")
    return data


def main():
    paths = sorted((ROOT / "apps").glob("*.json"))
    check(paths, "no JSON records")
    for path in paths:
        try:
            validate(path)
        except (ValueError, OSError) as error:
            print(f"{path.relative_to(ROOT)}: {error}", file=sys.stderr)
            return 1
    check(not list((ROOT / "apps").glob("*.yaml")), "legacy YAML records remain")
    print(f"Validated {len(paths)} title-ID JSON records.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
