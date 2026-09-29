"""Command-line entry point: python3 -m catalog <command>."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from .github import GitHub, GitHubError
from .policy import Change, check_changes, check_publisher, is_maintainer
from .records import MAX_FILE_BYTES, RECORD_PATH, Record, load_catalog, load_record, repo_parts
from .report import Report
from .verify import newer_release, verify_record

ROOT = Path(__file__).resolve().parents[1]
APPS = ROOT / "apps"
ZERO_SHA = "0" * 40


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def git_bytes(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True).stdout


def diff_changes(base: str, head: str) -> list[Change]:
    fields = git("diff", "--name-status", "--no-renames", "-z", base, head).split("\0")
    changes = []
    for status, path in zip(fields[0::2], fields[1::2]):
        mode = None
        if status != "D":
            listing = git("ls-tree", "-z", head, "--", path).split("\0")[0]
            mode = listing.split(" ", 1)[0] if listing else None
        changes.append(Change(status[0], path, mode))
    return changes


def cmd_check(args) -> int:
    report = Report()
    records = load_catalog(Path(args.apps_dir), report)
    return report.emit("Catalog check", f"{len(records)} record(s) are valid.")


def cmd_verify(args) -> int:
    report = Report()
    records = load_catalog(APPS, report)
    wanted = {t.upper() for t in args.titleids}
    unknown = wanted - {r.titleid for r in records}
    for titleid in sorted(unknown):
        report.error(f"apps/{titleid}.json", "no valid record with this title ID")
    selected = [r for r in records if not wanted or r.titleid in wanted]
    github = GitHub()
    for record in selected:
        verify_record(record, github, report, download=not args.no_download)
    return report.emit("Catalog verification", f"{len(selected)} record(s) verified.")


def cmd_health(args) -> int:
    from datetime import datetime, timedelta, timezone
    from .records import RESERVATION_STALE_DAYS
    from .site import last_updated

    report = Report()
    records = load_catalog(APPS, report)
    github = GitHub()
    updated = last_updated(APPS)
    cutoff = datetime.now(timezone.utc) - timedelta(days=RESERVATION_STALE_DAYS)
    for record in records:
        verify_record(record, github, report)
        changed = updated.get(record.path.name)
        if record.reserved and changed and datetime.fromisoformat(changed) < cutoff:
            report.warning(f"apps/{record.path.name}", f"reservation unchanged for over "
                           f"{RESERVATION_STALE_DAYS} days (last update {changed[:10]}); it may be released")
        try:
            tag = newer_release(record, github)
        except GitHubError as error:
            report.warning(f"apps/{record.path.name}", f"could not list releases: {error}")
            continue
        if tag:
            report.notice(f"apps/{record.path.name}", f"a newer release is published: {tag}")
    return report.emit("Catalog health", f"All {len(records)} listed downloads are intact.")


def cmd_push(args) -> int:
    report = Report()
    records = load_catalog(APPS, report)
    if not args.before or args.before == ZERO_SHA:
        selected = records
    else:
        changed = {Path(c.path).name for c in diff_changes(args.before, args.after)
                   if c.status != "D" and RECORD_PATH.fullmatch(c.path)}
        selected = [r for r in records if r.path.name in changed]
    github = GitHub()
    for record in selected:
        verify_record(record, github, report)
    return report.emit("Catalog push check", f"{len(records)} record(s) valid; {len(selected)} verified.")


def reservation_holder(record_path: str, github: GitHub) -> str | None:
    """Login of the account whose commit added a reservation file (the latest addition)."""
    sha = git("log", "--diff-filter=A", "--format=%H", "-1", "--", record_path).strip()
    repository = os.environ.get("GITHUB_REPOSITORY")
    if not sha or not repository:
        return None
    try:
        return github.commit_author(repository, sha)
    except GitHubError:
        return None


def cmd_pr(args) -> int:
    """Validate a pull request using this (base-branch) code; PR files are read only as data."""
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
    pull = event["pull_request"]
    author = pull["user"]["login"]
    maintainer = is_maintainer(pull["author_association"])
    report = Report()
    if maintainer:
        report.notice("pull request", f"@{author} is a maintainer; community-only rules are relaxed")

    head = "refs/catalog/pr-head"
    git("fetch", "--no-tags", "--quiet", "origin", f"+refs/pull/{pull['number']}/head:{head}")
    base = git("merge-base", "HEAD", head).strip()
    record_changes = check_changes(diff_changes(base, head), maintainer, report)

    github = GitHub()
    with tempfile.TemporaryDirectory(prefix="catalog-pr-") as tmp:
        candidate = Path(tmp) / "apps"
        shutil.copytree(APPS, candidate)
        for change in record_changes:
            target = candidate / Path(change.path).name
            target.unlink(missing_ok=True)
            if change.status == "D":
                continue
            if int(git("cat-file", "-s", f"{head}:{change.path}")) > MAX_FILE_BYTES:
                report.error(change.path, f"is larger than {MAX_FILE_BYTES} bytes")
                continue
            target.write_bytes(git_bytes("show", f"{head}:{change.path}"))

        records = {r.path.name: r for r in load_catalog(candidate, report)}
        holders: dict[str, str | None] = {}

        def holder_of(filename: str) -> str | None:
            if filename not in holders:
                holders[filename] = reservation_holder(f"apps/{filename}", github)
            return holders[filename]

        if any(r.reserved for r in records.values()):
            base_reserved = [r for r in load_catalog(APPS, Report()) if r.reserved]
        else:
            base_reserved = []
        for change in record_changes:
            new = records.get(Path(change.path).name)
            if change.status == "D" or new is None:
                continue
            old_path = ROOT / change.path
            old = load_record(old_path, Report()) if old_path.is_file() else None
            before = report.count("error")
            held = sum(1 for r in base_reserved if r.path.name != new.path.name
                       and (holder_of(r.path.name) or "").casefold() == author.casefold())
            check_publisher(author, maintainer, old, new, github, report,
                            holder=holder_of(new.path.name) if old and old.reserved else None, held=held)
            if report.count("error") == before:
                verify_record(new, github, report)
    return report.emit("Pull request check", "The submission meets every automated requirement; "
                                             "a maintainer will review it.")


def cmd_build(args) -> int:
    from .site import build_site
    report = Report()
    count = build_site(Path(args.out), APPS, report, base=args.base, site_url=args.site_url,
                       fetch_icons=not args.no_icons, theme=args.theme)
    return report.emit("Site build", f"Built {count} app page(s) into {args.out}.")


def cmd_digest(args) -> int:
    """Print the sha256 GitHub reports for a release asset URL."""
    marker = "/releases/download/"
    if marker not in args.artifact_url:
        print("expected a https://github.com/<owner>/<repo>/releases/download/<tag>/<asset> URL", file=sys.stderr)
        return 2
    source_repo, suffix = args.artifact_url.split(marker, 1)
    probe = Record(Path("probe.json"), {"source_repo": source_repo, "artifact_url": args.artifact_url})
    try:
        owner, repo = repo_parts(source_repo)
        tag, asset_name = probe.tag, probe.asset_name
        release = GitHub().release_by_tag(owner, repo, tag)
    except (ValueError, GitHubError) as error:
        print(f"could not look up the release: {error}", file=sys.stderr)
        return 1
    asset = next((a for a in (release or {}).get("assets", []) if a.get("name") == asset_name), None)
    if not asset:
        print("release or asset not found", file=sys.stderr)
        return 1
    digest = asset.get("digest") or ""
    if not digest.startswith("sha256:"):
        print("GitHub has no digest for this asset; run sha256sum on the downloaded file", file=sys.stderr)
        return 1
    print(digest.removeprefix("sha256:"))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m catalog", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    check = commands.add_parser("check", help="offline validation of every record (no network)")
    check.add_argument("--apps-dir", default=str(APPS))
    check.set_defaults(func=cmd_check)

    verify = commands.add_parser("verify", help="check records against GitHub and their downloads")
    verify.add_argument("titleids", nargs="*", help="title IDs to verify (default: all)")
    verify.add_argument("--no-download", action="store_true", help="skip downloading artifacts to check sha256")
    verify.set_defaults(func=cmd_verify)

    digest = commands.add_parser("digest", help="print the sha256 of a GitHub release asset URL")
    digest.add_argument("artifact_url")
    digest.set_defaults(func=cmd_digest)

    from .site import DEFAULT_BASE, DEFAULT_SITE_URL, DEFAULT_THEME, THEMES
    build = commands.add_parser("build", help="build the static website and JSON feed")
    build.add_argument("--out", default=str(ROOT / "dist"))
    build.add_argument("--base", default=DEFAULT_BASE, help="URL path the site is served under")
    build.add_argument("--site-url", default=DEFAULT_SITE_URL, help="origin used for absolute URLs")
    build.add_argument("--theme", default=DEFAULT_THEME, choices=sorted(THEMES))
    build.add_argument("--no-icons", action="store_true", help="skip fetching icons (placeholders)")
    build.set_defaults(func=cmd_build)

    pr = commands.add_parser("pr", help="CI: validate the pull request in GITHUB_EVENT_PATH")
    pr.set_defaults(func=cmd_pr)

    push = commands.add_parser("push", help="CI: validate records changed by a push")
    push.add_argument("--before", default="")
    push.add_argument("--after", default="HEAD")
    push.set_defaults(func=cmd_push)

    health = commands.add_parser("health", help="CI: re-verify every listed download")
    health.set_defaults(func=cmd_health)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
