"""Build the static store website and JSON feed from apps/.

Output (for the default base path /):

    dist/_headers, dist/_redirects, dist/404.html, dist/robots.txt
    dist/index.html                     the catalog, as cards or a list (?view=list)
    dist/app/<TITLEID>/index.html       one page per app
    dist/catalog/v1.json                machine-readable feed
    dist/assets/…                       content-hashed CSS, JS and icons

Each theme under site/themes/<name>/ provides base.html, index.html (the
catalog in both views), toolbar.html (its filters), card.html and row.html (one
app in each view, with -soon variants), app.html, app-soon.html, 404.html and
style.css. Templates use
string.Template placeholders; every metadata value is HTML-escaped before it is
substituted.

Icons are fetched and re-served from the site, resized to WebP when Pillow is
installed. With an icon cache directory, each icon URL is fetched only once
across builds (icon URLs are pinned to a tag or commit); entries no longer used
are pruned. A failed icon falls back to a placeholder instead of failing the
build.
"""

from __future__ import annotations

import hashlib
import html
import io
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from string import Template
from urllib.parse import quote, unquote

from . import artifacts
from .records import KINDS, Record, load_catalog
from .report import Report

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
REPO_URL = "https://github.com/blackbearreloaded/ps5-homebrew-catalog"
DEFAULT_SITE_URL = "https://homebrew.page"
DEFAULT_BASE = "/"
# Base paths the site used to be served under; their URLs redirect to the current base.
LEGACY_BASES = ("/ps5/",)
MARKER = ".catalog-site"
FEED_SCHEMA = 1
API_VERSION = "v1"         # path of the store API; a breaking change gets a new path
API_SCHEMA = 3             # raised when fields are added; clients ignore fields they don't know
API_ICON_SIZES = (512, 256)
ICON_SIZE = 512
FONT_URL = "https://fonts.googleapis.com/css2?{families}&display=swap"
THEMES = {
    # name: (Google Fonts families, browser theme-color)
    "holo": ("family=Unbounded:wght@500;700;800&family=DM+Sans:opsz,wght@9..40,400;9..40,500;9..40,700", "#0b0b10"),
}
DEFAULT_THEME = "holo"
FORMAT_LABELS = {"zip": "ZIP folder", "ffpkg": "FFPKG image", "ffpfsc": "FFPFSC image"}
KIND_LABELS = {"app": "App", "game": "Game", "tool": "Tool"}
KIND_PLURALS = {"app": "Apps", "game": "Games", "tool": "Tools"}


def e(value) -> str:
    return html.escape(str(value), quote=True)


def artifact_format(record: Record) -> str:
    return record.asset_name.rsplit(".", 1)[1].lower()


def source_sequence() -> int:
    """The catalog's sequence number: commits in the history of this build. It only ever grows on main,
    which lets a client refuse a signed catalog older than one it has already accepted. 0 when unknown."""
    if (_git("rev-parse", "--is-shallow-repository") or "").strip() == "true":
        _git("fetch", "--quiet", "--unshallow")
    count = (_git("rev-list", "--count", "HEAD") or "").strip()
    return int(count) if count.isdigit() else 0


def source_commit() -> str:
    for key in ("CF_PAGES_COMMIT_SHA", "GITHUB_SHA"):
        if os.environ.get(key):
            return os.environ[key]
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
                              capture_output=True, text=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _git(*args: str) -> str | None:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return None


def last_updated(apps_dir: Path) -> dict[str, str]:
    """Map record filename to the ISO commit date of the last commit that changed it.

    CI and Cloudflare may clone shallowly, which would date every record to the
    newest commit, so the history is deepened first when possible. Records
    outside the repository, or without history, are left out.
    """
    try:
        relative = apps_dir.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return {}
    if (_git("rev-parse", "--is-shallow-repository") or "").strip() == "true":
        _git("fetch", "--quiet", "--unshallow")
    output = _git("log", "--format=%x00%cI", "--name-only", "--no-renames", "--", relative)
    dates: dict[str, str] = {}
    date = None
    for line in (output or "").splitlines():
        if line.startswith("\0"):
            date = line[1:]
        elif line and date:
            dates.setdefault(Path(line).name, date)
    return dates


def display_date(iso: str) -> str:
    months = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
    year, month, day = iso[:10].split("-")
    return f"{months[int(month) - 1]} {int(day)}, {year}"


def version_label(version: str) -> str:
    """How a version is shown: "v1.2" for numeric versions, tags such as "vk-285-113" as they are."""
    return f"v{version}" if version[:1].isdigit() else version


def normalize_base(base: str) -> str:
    base = "/" + base.strip("/") + "/"
    return "/" if base == "//" else base


class Theme:
    def __init__(self, name: str):
        if name not in THEMES:
            raise ValueError(f"unknown theme {name!r}")
        self.name = name
        self.directory = SITE / "themes" / name
        self.fonts, self.color = THEMES[name]

    def template(self, name: str) -> Template | None:
        path = self.directory / name
        return Template(path.read_text(encoding="utf-8")) if path.is_file() else None

    def render(self, name: str, values: dict) -> str:
        template = self.template(name)
        return template.substitute(values) if template else ""


class Assets:
    """Writes content-hashed files under <base>/assets/ and remembers their URLs."""

    def __init__(self, directory: Path, url_prefix: str):
        self.directory = directory
        self.url_prefix = url_prefix
        directory.mkdir(parents=True, exist_ok=True)

    def add(self, stem: str, extension: str, content: bytes) -> str:
        name = f"{stem}.{hashlib.sha256(content).hexdigest()[:12]}.{extension}"
        (self.directory / name).write_bytes(content)
        return self.url_prefix + name


def process_icon(data: bytes) -> tuple[bytes, str]:
    image_format, _ = artifacts.inspect_icon(data)
    if image_format is None:
        raise ValueError("not a PNG, JPEG or WebP image")
    try:
        from PIL import Image
    except ImportError:
        return data, {"png": "png", "jpeg": "jpg", "webp": "webp"}[image_format]
    with Image.open(io.BytesIO(data)) as image:
        image = image.convert("RGBA")
        image.thumbnail((ICON_SIZE, ICON_SIZE))
        output = io.BytesIO()
        image.save(output, "WEBP", quality=82, method=6)
    return output.getvalue(), "webp"


def png_icons(data: bytes) -> dict[int, bytes]:
    """PNG copies for native clients, by longest side; they may not decode WebP. Needs Pillow to resize."""
    try:
        from PIL import Image
    except ImportError:
        return {API_ICON_SIZES[0]: data} if artifacts.inspect_icon(data)[0] == "png" else {}
    icons = {}
    with Image.open(io.BytesIO(data)) as image:
        image = image.convert("RGBA")
        for size in API_ICON_SIZES:
            copy = image.copy()
            copy.thumbnail((size, size))
            output = io.BytesIO()
            copy.save(output, "PNG", optimize=True)
            icons[size] = output.getvalue()
    return icons


def _icon(url: str, cache: Path | None) -> tuple[bytes, str, bytes]:
    """(site icon, its extension, original bytes) for url, using and filling the optional cache of originals."""
    entry = cache / (hashlib.sha256(url.encode()).hexdigest() + ".img") if cache else None
    if entry and entry.is_file():
        try:
            data = entry.read_bytes()
            return (*process_icon(data), data)
        except (OSError, ValueError):
            entry.unlink(missing_ok=True)
    data = artifacts.fetch_small(url, artifacts.MAX_ICON_BYTES)
    result = process_icon(data)
    if entry:
        cache.mkdir(parents=True, exist_ok=True)
        entry.write_bytes(data)
    return (*result, data)


def _prepare_output(out: Path) -> None:
    if out.exists():
        if not (out / MARKER).exists() and any(out.iterdir()):
            raise SystemExit(f"refusing to replace {out}: it is not empty and was not created by this build")
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / MARKER).write_text("Generated by python3 -m catalog build; safe to delete.\n", encoding="utf-8")


def _install_steps(record: Record) -> str:
    d = record.data
    name = f"<code>{e(unquote(record.asset_name))}</code>"
    loader = '<a href="https://github.com/drakmor/ShadowMountPlus">ShadowMountPlus</a>'
    if artifact_format(record) == "zip":
        steps = [
            f"Download {name} and extract it on your computer.",
            f"Copy the extracted <code>{e(d['titleid'])}/</code> folder to <code>/data/homebrew/</code> on your PS5, for example over FTP.",
            f"A loader such as {loader} picks it up. Launch {e(d['name'])} from the home screen.",
        ]
    else:
        steps = [
            f"Download {name}.",
            "Copy the file as-is to <code>/data/homebrew/</code> on your PS5, for example over FTP.",
            f"{loader} mounts the image. Launch {e(d['name'])} from the home screen.",
        ]
    return "\n".join(f"<li>{step}</li>" for step in steps)


def _install_steps_text(record: Record) -> list[str]:
    """The install steps as plain text, for TV mode."""
    return [html.unescape(re.sub(r"<[^>]+>", "", step)) for step in re.findall(r"<li>(.*?)</li>", _install_steps(record))]


def _utc(iso: str | None) -> str | None:
    """An ISO 8601 time as UTC with a Z suffix, the one form the API uses."""
    if not iso:
        return None
    from datetime import datetime, timezone
    return datetime.fromisoformat(iso).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")


def write_api(root: Path, url: str, records: list[Record], report: Report, *, updated: dict[str, str], page,
              icons: dict[str, dict[int, bytes]], icon_hashes: dict[str, str], commit: str, github=None,
              cache: Path | None = None) -> None:
    """The store API (docs/api.md): one file per app, a browse index and a version map, plus PNG icons.

    Per-app files and the version map hold nothing that changes between builds
    of the same catalog, so an unchanged app keeps its ETag and costs clients a
    304. Only the index carries the build's commit and time.
    """
    from . import facts as release_facts
    from datetime import datetime, timezone
    large, small = API_ICON_SIZES
    index, versions = [], {}
    for record in sorted(records, key=lambda r: r.titleid):
        d, titleid, name = record.data, record.titleid, f"apps/{record.path.name}"
        facts, problem = release_facts.cached(record, github, cache)
        if problem:
            report.warning(name, f"release facts not included in the API this time: {problem}")
        elif github is not None and not record.reserved and facts.content_version is None:
            report.notice(name, "no contentVersion found for this release; clients can't check it for updates")
        icon = {}
        for size, suffix in ((large, ""), (small, f"-{small}")):
            content = icons.get(titleid, {}).get(size)
            if content:
                (root / "icons").mkdir(parents=True, exist_ok=True)
                (root / "icons" / f"{titleid}{suffix}.png").write_bytes(content)
                icon[size] = f"{url}icons/{titleid}{suffix}.png"
        app = {
            "schema": API_SCHEMA,
            **d,
            "status": "coming_soon" if record.reserved else "available",
            "content_version": facts.content_version,
            "format": None if record.reserved else artifact_format(record),
            "artifact_name": None if record.reserved else unquote(record.asset_name),
            "size": facts.size,
            "tag": None if record.reserved else record.tag,
            "released": facts.released,
            "prerelease": facts.prerelease,
            "release_url": None if record.reserved else f"{d['source_repo']}/releases/tag/{quote(record.tag, safe='')}",
            "updated": _utc(updated.get(record.path.name)),
            "page": page(record),
            "icon": icon.get(large),
            "icon_small": icon.get(small) or icon.get(large),
            # Lets a client keep its copy of the icon until the developer's image changes.
            "icon_hash": icon_hashes.get(titleid) if icon else None,
        }
        _write_json(root / "apps" / f"{titleid}.json", app)
        index.append({key: app[key] for key in (
            "titleid", "status", "name", "kind", "author", "version", "content_version", "format", "size",
            "released", "updated", "icon_small", "icon_hash")})
        if not record.reserved:
            versions[titleid] = {"content_version": facts.content_version, "version": d["version"]}
    _write_json(root / "index.json", {
        "schema": API_SCHEMA, "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": commit, "count": len(index), "apps": index})
    _write_json(root / "versions.json", {"schema": API_SCHEMA, "apps": versions})
    # Hashes of everything above, for the deploy to sign (catalog/signing.py).
    from . import signing
    signing.write_manifest(root, API_SCHEMA, source_sequence(), commit)
    if github is not None:
        release_facts.prune(cache, records)


def build_site(out: Path, apps_dir: Path, report: Report, base: str = DEFAULT_BASE,
               site_url: str = DEFAULT_SITE_URL, fetch_icons: bool = True,
               theme: str = DEFAULT_THEME, icon_cache: Path | None = None, github=None) -> int:
    """Build the site. With `github`, release facts for the API are looked up (and kept in the cache)."""
    theme_obj = Theme(theme)
    records = load_catalog(apps_dir, report)
    if report.failed:
        return 0
    records.sort(key=lambda r: (r.data["name"].casefold(), r.titleid))
    base = normalize_base(base)
    site_url = site_url.rstrip("/")
    commit = source_commit()

    _prepare_output(out)
    root = out / base.strip("/") if base != "/" else out
    root.mkdir(parents=True, exist_ok=True)
    assets = Assets(root / "assets", base + "assets/")
    shared_dir = SITE / "shared"
    css = assets.add(f"{theme}", "css", (theme_obj.directory / "style.css").read_bytes())
    js = assets.add("app", "js", (shared_dir / "app.js").read_bytes())
    placeholder = assets.add("placeholder", "svg", (shared_dir / "placeholder.svg").read_bytes())
    shutil.copyfile(shared_dir / "favicon.svg", root / "favicon.svg")

    icons: dict[str, str] = {}
    api_icons: dict[str, dict[int, bytes]] = {}
    icon_hashes: dict[str, str] = {}
    for record in records:
        icons[record.titleid] = placeholder
        if not fetch_icons or record.data["icon_url"] is None:
            continue
        try:
            content, extension, original = _icon(record.data["icon_url"], icon_cache)
            api_icons[record.titleid] = png_icons(original)
            icon_hashes[record.titleid] = hashlib.sha256(original).hexdigest()[:16]
        except (artifacts.DownloadError, OSError, ValueError) as error:
            report.warning(f"apps/{record.path.name}", f"icon not included, using a placeholder: {error}")
            continue
        icons[record.titleid] = assets.add(f"icon-{record.titleid}", extension, content)
    if icon_cache and icon_cache.is_dir() and fetch_icons:
        wanted = {hashlib.sha256(r.data["icon_url"].encode()).hexdigest() + ".img"
                  for r in records if r.data["icon_url"]}
        for entry in icon_cache.glob("*.img"):
            if entry.name not in wanted:
                entry.unlink()

    kinds = {kind: [r for r in records if r.data["kind"] == kind] for kind in KINDS}
    total = len(records)
    updated = last_updated(apps_dir)

    def page_url(record: Record) -> str:
        return f"{base}app/{record.titleid}/"

    def app_values(record: Record, number: int) -> dict:
        d = record.data
        values = {k: "" if v is None else e(v) for k, v in d.items()}
        values.update(
            url=e(page_url(record)),
            icon=e(icons[record.titleid]),
            kind_label=e(KIND_LABELS[d["kind"]]),
            status="soon" if record.reserved else "available",
            format="",
        )
        if not record.reserved:
            fmt = artifact_format(record)
            values.update(
                source_short=e(f"{record.owner}/{record.repo}"),
                format=e(fmt),
                format_label=e(FORMAT_LABELS[fmt]),
                artifact_name=e(unquote(record.asset_name)),
                version_label=e(version_label(d["version"])),
                release_url=e(f"{d['source_repo']}/releases/tag/{d['artifact_url'].split('/releases/download/')[1].split('/')[0]}"),
                tag=e(record.tag),
            )
        values.update(
            number=f"{number:03d}",
            updated=e(display_date(updated[record.path.name])) if record.path.name in updated else "—",
            updated_iso=e(updated.get(record.path.name, "")),
            total=f"{total:03d}",
            search_text=e(" ".join((d["name"], d["author"], d["titleid"], d["description"], d["kind"]))),
        )
        return values

    numbered = {r.titleid: app_values(r, i) for i, r in enumerate(sorted(records, key=lambda r: r.titleid), 1)}

    def items(template: str, selection: list[Record]) -> str:
        """Render records with the data attributes the filter and sort script reads."""
        rendered = []
        for record in selection:
            values = dict(numbered[record.titleid])
            values["grid_attrs"] = (
                f' data-app data-app-kind="{values["kind"]}" data-status="{values["status"]}"'
                f' data-format="{values["format"]}"'
                f' data-name="{e(record.data["name"].casefold())}" data-titleid="{values["titleid"]}"'
                f' data-author="{e(record.data["author"].casefold())}"'
                f' data-updated="{values["updated_iso"]}" data-search-text="{values["search_text"]}"'
            )
            name = template.replace(".html", "-soon.html") if record.reserved else template
            rendered.append(theme_obj.render(name, values))
        return "\n".join(rendered)

    shared = {
        "base": base,
        "repo": REPO_URL,
        "submit_url": f"{REPO_URL}/blob/main/docs/submitting.md",
        "css": css,
        "js": js,
        "fonts": e(FONT_URL.format(families=theme_obj.fonts)),
        "theme_color": theme_obj.color,
        "commit": e(commit),
        "commit_short": e(commit[:7]),
        "app_count": total,
        "developer_count": len({r.data["author"].casefold() for r in records}),
        "game_count": len(kinds["game"]),
        "apps_only_count": len(kinds["app"]),
        "tool_count": len(kinds["tool"]),
        "soon_count": sum(1 for r in records if r.reserved),
        "feed_url": f"{base}catalog/v1.json",
    }
    base_tpl = theme_obj.template("base.html")

    def write_page(path: Path, *, title: str, description: str, canonical: str, body: str,
                   og_image: str | None = None, page_class: str = "") -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(base_tpl.substitute(
            shared, title=e(title), description=e(description), canonical=e(canonical),
            og_image=e(og_image or site_url + base + "favicon.svg"), body=body, page_class=page_class,
        ), encoding="utf-8")

    # Store front: the same catalog as cards (index) and as a list, sharing one toolbar.
    releases = [r for r in records if not r.reserved]
    chips = [f'<button type="button" class="chip" data-kind="all" aria-pressed="true">All <span>{total}</span></button>']
    chips += [f'<button type="button" class="chip" data-kind="{kind}" aria-pressed="false">{KIND_PLURALS[kind]} <span>{len(group)}</span></button>'
              for kind, group in kinds.items() if group]
    format_options = "".join(f'<option value="{fmt}">{e(FORMAT_LABELS[fmt])}</option>'
                             for fmt in sorted({artifact_format(r) for r in releases}))


    index_body = theme_obj.template("index.html").substitute(
        shared, cards=items("card.html", records), rows=items("row.html", records),
        toolbar=theme_obj.render("toolbar.html", dict(shared, chips="".join(chips), format_options=format_options)),
    )
    write_page(root / "index.html", title="PS5 Homebrew Store — community apps, games and tools",
               description=f"Browse {total} native PS5 homebrew apps, games and tools. Every download comes "
                           "from the developer's GitHub release and is pinned by SHA-256.",
               canonical=site_url + base, body=index_body, page_class="page-home")

    # App pages.
    for record in records:
        values = dict(shared, **numbered[record.titleid])
        if not record.reserved:
            values["steps"] = _install_steps(record)
        write_page(root / "app" / record.titleid / "index.html",
                   title=f"{record.data['name']} — PS5 Homebrew Store", description=record.data["description"],
                   canonical=site_url + page_url(record),
                   body=theme_obj.render("app-soon.html" if record.reserved else "app.html", values),
                   og_image=site_url + icons[record.titleid], page_class="page-app")

    # TV mode: a 10-foot interface for the PS5 browser, drawn by tv.js from data embedded in the page.
    tv_template = theme_obj.template("tv.html")
    if tv_template:
        host = site_url.split("://", 1)[-1]
        tv_apps = []
        for record in records:
            d = record.data
            item = {
                "titleid": d["titleid"], "name": d["name"], "kind": d["kind"], "kind_label": KIND_LABELS[d["kind"]],
                "description": d["description"], "author": d["author"], "version": d["version"] or "",
                "version_label": version_label(d["version"]) if d["version"] else "",
                "license": d["license"] or "", "soon": record.reserved, "icon": icons[record.titleid],
                "updated": display_date(updated[record.path.name]) if record.path.name in updated else "",
                "updated_iso": updated.get(record.path.name, ""), "short_url": host + page_url(record),
            }
            if not record.reserved:
                item.update(format_label=FORMAT_LABELS[artifact_format(record)], sha256=d["sha256"],
                            artifact_name=unquote(record.asset_name), source=f"{record.owner}/{record.repo}",
                            steps=_install_steps_text(record))
            tv_apps.append(item)
        available = [r for r in records if not r.reserved]
        rail = [("all", "All", total)] + [(kind, KIND_PLURALS[kind], sum(1 for r in available if r.data["kind"] == kind))
                                          for kind in KINDS]
        rail.append(("soon", "Coming soon", total - len(available)))
        rail_html = "\n".join(f'  <button type="button" class="tv-rail__item" data-kind="{kind}" tabindex="-1">'
                              f'{label}<span>{count}</span></button>' for kind, label, count in rail if count)
        data = json.dumps({"apps": tv_apps}, ensure_ascii=False, separators=(",", ":"))
        (root / "tv").mkdir()
        (root / "tv" / "index.html").write_text(tv_template.substitute(
            shared, canonical=e(site_url + base + "tv/"), rail=rail_html,
            tv_css=assets.add(f"{theme}-tv", "css", (theme_obj.directory / "tv.css").read_bytes()),
            tv_js=assets.add("tv", "js", (shared_dir / "tv.js").read_bytes()),
            # Inside <script type="application/json">, "<" is escaped so no value can close the element.
            data=data.replace("<", "\\u003c"),
        ), encoding="utf-8")

    # 404 page, served by Cloudflare Pages for unknown paths.
    for target in {out / "404.html", root / "404.html"}:
        write_page(target, title="Not found — PS5 Homebrew Store", description="Page not found.",
                   canonical=site_url + base, body=theme_obj.render("404.html", shared), page_class="page-404")

    # Feed for the console store and other clients.
    feed = {
        "schema": FEED_SCHEMA,
        "name": "PS5 Homebrew Catalog",
        "homepage": site_url + base,
        "source": {"repository": REPO_URL, "commit": commit},
        "apps": [
            {**r.data, "format": artifact_format(r), "updated": updated.get(r.path.name),
             "page": site_url + page_url(r), "icon": site_url + icons[r.titleid]}
            for r in sorted(releases, key=lambda r: r.titleid)
        ],
        "coming_soon": [
            {**r.data, "updated": updated.get(r.path.name),
             "page": site_url + page_url(r), "icon": site_url + icons[r.titleid]}
            for r in sorted((r for r in records if r.reserved), key=lambda r: r.titleid)
        ],
    }
    (root / "catalog").mkdir()
    (root / "catalog" / "v1.json").write_text(
        json.dumps(feed, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    write_api(root / "api" / API_VERSION, f"{site_url}{base}api/{API_VERSION}/", records, report,
              updated=updated, page=lambda r: site_url + page_url(r), icons=api_icons, icon_hashes=icon_hashes,
              commit=commit,
              github=github, cache=icon_cache)

    # Cloudflare Pages configuration.
    csp = ("default-src 'self'; img-src 'self' data:; style-src 'self' https://fonts.googleapis.com; "
           "font-src https://fonts.gstatic.com; script-src 'self'; connect-src 'self'; "
           "base-uri 'self'; form-action 'none'; frame-ancestors 'none'")
    (out / "_headers").write_text(f"""/*
  X-Content-Type-Options: nosniff
  Referrer-Policy: strict-origin-when-cross-origin
  X-Frame-Options: DENY
  Permissions-Policy: camera=(), microphone=(), geolocation=()
  Content-Security-Policy: {csp}

{base}assets/*
  Cache-Control: public, max-age=31536000, immutable

{base}catalog/*
  Access-Control-Allow-Origin: *
  Cache-Control: public, max-age=300, must-revalidate

{base}api/*
  Access-Control-Allow-Origin: *
  Cache-Control: public, max-age=300, must-revalidate
""", encoding="utf-8")
    redirects = [f"/ {base} 302", f"{base.rstrip('/')} {base} 301"] if base != "/" else []
    redirects += [f"{base}list {base}?view=list 301", f"{base}list/ {base}?view=list 301",
                  f"/favicon.ico {base}favicon.svg 301"]
    for old in LEGACY_BASES:
        if old != base:
            redirects += [f"{old}list {base}?view=list 301", f"{old}list/ {base}?view=list 301",
                          f"{old.rstrip('/')} {base} 301", f"{old}* {base}:splat 301"]
    (out / "_redirects").write_text("\n".join(redirects) + "\n", encoding="utf-8")
    (out / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
    return total
