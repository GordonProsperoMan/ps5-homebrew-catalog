"""Verify a record against GitHub and the bytes it points to."""

from __future__ import annotations

from . import artifacts
from .github import GitHub, GitHubError
from .records import Record
from .report import Report


def verify_record(record: Record, github: GitHub, report: Report, download: bool = True) -> None:
    name = f"apps/{record.path.name}"
    data = record.data
    if record.reserved:
        _verify_reservation(name, record, github, report)
        return
    try:
        repo = github.repo(record.owner, record.repo)
        if repo is None or repo.get("private"):
            report.error(name, f"source_repo {data['source_repo']} is not a public GitHub repository")
            return
        canonical = f"https://github.com/{repo['full_name']}"
        if canonical != data["source_repo"]:
            report.error(name, f"source_repo must use the canonical URL {canonical}")
            return
        if repo.get("archived"):
            report.warning(name, "source repository is archived")
        _check_license(name, data["license"], repo, report)

        release = github.release_by_tag(record.owner, record.repo, record.tag)
        if release is None or release.get("draft"):
            report.error(name, f"no published release is tagged {record.tag!r}")
            return
        asset = next((a for a in release.get("assets", []) if a.get("name") == record.asset_name), None)
        if asset is None:
            report.error(name, f"release {record.tag!r} has no asset named {record.asset_name!r}")
            return
        if asset.get("size", 0) > artifacts.MAX_ARTIFACT_BYTES:
            report.error(name, f"artifact is {asset['size']} bytes; the limit is {artifacts.MAX_ARTIFACT_BYTES}")
            return
        github_digest = asset.get("digest")
        if github_digest and github_digest != f"sha256:{data['sha256']}":
            report.error(name, f"sha256 does not match the release asset; GitHub reports {github_digest}")
            return
    except GitHubError as error:
        report.error(name, str(error))
        return

    if download:
        _verify_artifact(name, record, report)
    _verify_icon(name, data["icon_url"], report)


def _verify_reservation(name: str, record: Record, github: GitHub, report: Report) -> None:
    """Reservations have no release yet; the repository may still be private."""
    try:
        repo = github.repo(record.owner, record.repo)
        if github.account_type(record.owner) is None:
            report.error(name, f"GitHub account {record.owner} does not exist")
            return
    except GitHubError as error:
        report.error(name, str(error))
        return
    if repo is None:
        report.notice(name, "reservation: the source repository is private or not created yet")
    elif f"https://github.com/{repo['full_name']}" != record.data["source_repo"]:
        report.error(name, f"source_repo must use the canonical URL https://github.com/{repo['full_name']}")
        return
    else:
        report.notice(name, "reservation: release checks run when it becomes a release")
    if "icon_url" in record.data:
        _verify_icon(name, record.data["icon_url"], report)


def _check_license(name: str, license_value: str, repo: dict, report: Report) -> None:
    detected = (repo.get("license") or {}).get("spdx_id")
    if not detected or detected == "NOASSERTION":
        report.warning(name, "GitHub could not detect the repository license; confirm it manually")
    elif not any(token == detected or token.startswith(detected + "-") for token in license_value.split()):
        report.error(name, f"license {license_value!r} does not match the repository license {detected!r}")


def _verify_artifact(name: str, record: Record, report: Report) -> None:
    try:
        size, digest = artifacts.hash_download(record.data["artifact_url"])
    except (artifacts.DownloadError, OSError) as error:
        report.error(name, f"artifact download failed: {error}")
        return
    if digest != record.data["sha256"]:
        report.error(name, f"downloaded artifact has sha256 {digest}, not the recorded value")
        return
    report.notice(name, f"artifact matches sha256 ({size:,} bytes)")


def _verify_icon(name: str, url: str, report: Report) -> None:
    try:
        data = artifacts.fetch_small(url, artifacts.MAX_ICON_BYTES)
    except (artifacts.DownloadError, OSError) as error:
        report.error(name, f"icon_url could not be fetched: {error}")
        return
    image_format, warnings = artifacts.inspect_icon(data)
    if image_format is None:
        report.error(name, "icon_url does not return a PNG, JPEG or WebP image")
    for warning in warnings:
        report.warning(name, warning)


def newer_release(record: Record, github: GitHub) -> str | None:
    """Return the tag of the newest published release when it differs from the record."""
    if record.reserved:
        return None
    for release in github.releases(record.owner, record.repo):
        if not release.get("draft"):
            tag = release.get("tag_name")
            return tag if tag and tag != record.tag else None
    return None
