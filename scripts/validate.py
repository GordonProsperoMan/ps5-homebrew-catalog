#!/usr/bin/env python3
"""Validate the human-edited catalog records without downloading release assets."""

from pathlib import Path
import re
import sys
from urllib.parse import urlparse

import yaml

ROOT = Path(__file__).resolve().parents[1]
ID = re.compile(r"[a-z0-9]+(?:[.-][a-z0-9]+)*\Z")
TITLE_ID = re.compile(r"PPSA[0-9]{5}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
PNG = b"\x89PNG\r\n\x1a\n"


class UniqueKeyLoader(yaml.SafeLoader):
    pass


def unique_mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if key in result:
            raise ValueError(f"duplicate YAML key: {key}")
        result[key] = loader.construct_object(value_node)
    return result


UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, unique_mapping
)


def check(condition, message):
    if not condition:
        raise ValueError(message)


def nonempty(value, maximum):
    return isinstance(value, str) and 0 < len(value) <= maximum and value.strip() == value


def validate(path):
    check(not path.is_symlink() and path.stat().st_size <= 32768, "unsafe or oversized YAML file")
    data = yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)
    check(isinstance(data, dict), "record must be a mapping")
    required = {"id", "title", "kind", "author", "summary", "description", "source_url", "license", "categories"}
    optional = {"title_id", "icon", "release", "release_page", "installation_verified"}
    check(required <= data.keys() and data.keys() <= required | optional, "missing or unknown fields")
    check(nonempty(data["id"], 100) and ID.fullmatch(data["id"]), "invalid id")
    check(path.stem == data["id"].split(".", 1)[-1], "filename must match id suffix")
    for field, limit in (("title", 100), ("author", 100), ("summary", 180), ("description", 1000), ("license", 80)):
        check(nonempty(data[field], limit), f"invalid {field}")
    check(data["kind"] in {"app", "game", "tool", "research", "runtime"}, "invalid kind")
    check(isinstance(data["categories"], list) and 0 < len(data["categories"]) <= 5
          and all(nonempty(item, 40) for item in data["categories"]), "invalid categories")
    source = data["source_url"]
    parsed = urlparse(source) if isinstance(source, str) else None
    check(parsed and parsed.scheme == "https" and parsed.netloc == "github.com"
          and len(parsed.path.strip("/").split("/")) == 2 and not parsed.query
          and not parsed.fragment, "invalid source_url")
    if "release_page" in data:
        check(data["release_page"].startswith(source + "/releases/tag/"), "invalid release_page")

    if data["kind"] in {"app", "game"}:
        check({"title_id", "icon", "release", "installation_verified"} <= data.keys(),
              "app is missing installation metadata")
        check(TITLE_ID.fullmatch(str(data["title_id"])), "invalid title_id")
        check(type(data["installation_verified"]) is bool, "installation_verified must be boolean")
        icon = Path(data["icon"])
        check(icon.parts[:2] == ("assets", "icons") and ".." not in icon.parts, "invalid icon path")
        icon_file = ROOT / icon
        check(icon_file.is_file() and not icon_file.is_symlink()
              and icon_file.stat().st_size <= 2_000_000
              and icon_file.read_bytes()[:8] == PNG, "missing or invalid PNG icon")
        release = data["release"]
        fields = {"version", "sequence", "channel", "page_url", "url", "sha256",
                  "download_bytes", "installed_bytes", "archive_root"}
        check(isinstance(release, dict) and release.keys() == fields, "invalid release fields")
        check(nonempty(release["version"], 60) and type(release["sequence"]) is int
              and release["sequence"] > 0, "invalid release version or sequence")
        check(release["channel"] in {"stable", "alpha"}, "invalid release channel")
        check(release["page_url"].startswith(source + "/releases/tag/"), "invalid release page")
        check(release["url"].startswith(source + "/releases/download/")
              and release["url"].endswith(".zip"), "invalid artifact URL")
        check(SHA256.fullmatch(str(release["sha256"])), "invalid SHA-256")
        for field in ("download_bytes", "installed_bytes"):
            check(type(release[field]) is int and 0 < release[field] < 2_147_483_648,
                  f"invalid {field}")
        check(release["archive_root"] == data["title_id"], "archive root must match title ID")
        check(not data["installation_verified"],
              "installation_verified requires the later hardware and compatibility contract")
    else:
        check(not ({"title_id", "icon", "release", "installation_verified"} & data.keys()),
              "non-app record has app installation fields")
    return data


def main():
    seen_ids = set()
    seen_title_ids = set()
    paths = sorted((ROOT / "apps").glob("*.yaml"))
    check(paths, "no app records")
    for path in paths:
        try:
            data = validate(path)
            check(data["id"] not in seen_ids, "duplicate id")
            seen_ids.add(data["id"])
            if "title_id" in data:
                check(data["title_id"] not in seen_title_ids, "duplicate title ID")
                seen_title_ids.add(data["title_id"])
        except (ValueError, TypeError, KeyError, AttributeError, yaml.YAMLError, OSError) as error:
            print(f"{path.relative_to(ROOT)}: {error}", file=sys.stderr)
            return 1
    print(f"Validated {len(paths)} catalog records ({len(seen_title_ids)} titled apps).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
