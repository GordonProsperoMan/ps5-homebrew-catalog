"""Pull-request rules for community submissions."""

from __future__ import annotations

from dataclasses import dataclass

from .github import GitHub, GitHubError
from .records import RECORD_PATH, Record
from .report import Report

MAINTAINER_ASSOCIATIONS = {"OWNER", "MEMBER", "COLLABORATOR"}
REGULAR_FILE_MODE = "100644"


@dataclass(frozen=True)
class Change:
    status: str  # A (added), M (modified) or D (deleted)
    path: str
    mode: str | None = None  # git mode of the new blob, None when deleted


def is_maintainer(author_association: str) -> bool:
    return author_association in MAINTAINER_ASSOCIATIONS


def check_changes(changes: list[Change], maintainer: bool, report: Report) -> list[Change]:
    """Validate which files a PR touches; return the record changes to verify."""
    records = []
    for change in changes:
        if change.path.startswith("apps/"):
            if not RECORD_PATH.fullmatch(change.path):
                report.error(change.path, "only apps/<TITLEID>.json files may be added under apps/")
                continue
            if change.status != "D" and change.mode != REGULAR_FILE_MODE:
                report.error(change.path, "must be a regular, non-executable file")
                continue
            if change.status == "D" and not maintainer:
                report.error(change.path, "removing an app is done by maintainers; open a withdrawal issue")
                continue
            records.append(change)
        elif not maintainer:
            report.error(change.path, "community pull requests may change only apps/<TITLEID>.json; "
                                      "open an issue for other changes")
    if not maintainer and len([c for c in records if c.status != "D"]) > 1:
        report.error("apps", "submit one app per pull request")
    if not changes:
        report.error("pull request", "changes no files")
    return records


def check_publisher(author: str, maintainer: bool, old: Record | None, new: Record,
                    github: GitHub, report: Report) -> None:
    """Only the owner of source_repo (or a public member of that org) may list or update an app."""
    name = f"apps/{new.path.name}"
    if old and old.owner.casefold() != new.owner.casefold():
        if maintainer:
            report.warning(name, f"moves {new.titleid} from {old.owner} to {new.owner}")
        else:
            report.error(name, f"{new.titleid} is registered to {old.owner}; ownership transfers "
                               "require a maintainer")
            return
    if maintainer:
        return
    if author.casefold() == new.owner.casefold():
        return
    try:
        repo = github.repo(new.owner, new.repo)
        is_org = bool(repo) and repo.get("owner", {}).get("type") == "Organization"
        if is_org and github.is_public_member(new.owner, author):
            return
    except GitHubError as error:
        report.error(name, f"could not confirm the publisher: {error}")
        return
    report.error(name, f"@{author} does not own {new.owner}/{new.repo}; open the pull request from "
                       f"the {new.owner} account or make your membership of {new.owner} public")
