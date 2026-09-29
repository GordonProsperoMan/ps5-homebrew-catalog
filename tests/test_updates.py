import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import catalog.__main__ as cli

from catalog.policy import check_publisher
from catalog.records import Record
from catalog.report import Report
from catalog.updates import find_update, is_release_bump, new_version, pick_asset

from helpers import record, reservation, write_record

OLD = record(
    titleid="PPSA01234", version="0.5.0",
    source_repo="https://github.com/example/example-app",
    artifact_url="https://github.com/example/example-app/releases/download/v0.5.0/example-0.5.0-PPSA01234.zip",
    icon_url="https://raw.githubusercontent.com/example/example-app/v0.5.0/sce_sys/icon0.png",
)


def asset(name, digest="sha256:" + "c" * 64):
    return {"name": name, "digest": digest, "size": 1000}


def release(tag, assets, prerelease=False, draft=False):
    return {"tag_name": tag, "assets": assets, "prerelease": prerelease, "draft": draft}


class FakeGitHub:
    def __init__(self, releases):
        self._releases = releases

    def releases(self, owner, name):
        return self._releases


class PickAssetTests(unittest.TestCase):
    def test_same_name_wins(self):
        chosen, how = pick_asset([asset("PPSA01234.zip"), asset("other.zip")], "PPSA01234.zip", "1", "1", "2")
        self.assertEqual((chosen["name"], how), ("PPSA01234.zip", "same file name"))

    def test_version_in_file_name(self):
        assets = [asset("example-0.6.0-PPSA01234.zip"), asset("sdk-0.6.0.zip")]
        chosen, how = pick_asset(assets, "example-0.5.0-PPSA01234.zip", "v0.5.0", "0.5.0", "v0.6.0")
        self.assertEqual(chosen["name"], "example-0.6.0-PPSA01234.zip")

    def test_only_file_of_that_type(self):
        chosen, how = pick_asset([asset("renamed.zip"), asset("notes.txt")], "old.zip", "1", "1", "2")
        self.assertEqual(chosen["name"], "renamed.zip")

    def test_ambiguous_or_missing(self):
        self.assertIsNone(pick_asset([asset("a.zip"), asset("b.zip")], "old.zip", "1", "1", "2")[0])
        self.assertIsNone(pick_asset([asset("a.ffpkg")], "old.zip", "1", "1", "2")[0])


class VersionTests(unittest.TestCase):
    def test_follows_the_tag_in_the_record_style(self):
        self.assertEqual(new_version("0.5.0", "v0.5.0", "v0.6.0"), "0.6.0")
        self.assertEqual(new_version("v0.5.0", "v0.5.0", "v0.6.0"), "v0.6.0")
        self.assertEqual(new_version("01.000.060", "01.000.060", "01.000.062"), "01.000.062")


class FindUpdateTests(unittest.TestCase):
    def find(self, releases, data=OLD, icon_exists=True):
        return find_update(Record(Path("PPSA01234.json"), data), FakeGitHub(releases),
                           icon_exists=lambda url: icon_exists)

    def test_proposes_the_newest_release_including_prereleases(self):
        update, reason = self.find([
            release("v0.7.0-beta", [asset("example-0.7.0-beta-PPSA01234.zip")], prerelease=True),
            release("v0.5.0", [asset("example-0.5.0-PPSA01234.zip")]),
        ])
        self.assertEqual(reason, "")
        self.assertTrue(update.prerelease)
        self.assertEqual(update.data["version"], "0.7.0-beta")
        self.assertEqual(update.data["sha256"], "c" * 64)
        self.assertTrue(update.data["artifact_url"].endswith("/v0.7.0-beta/example-0.7.0-beta-PPSA01234.zip"))
        self.assertIn("/v0.7.0-beta/", update.data["icon_url"])
        unchanged = {k for k in OLD if OLD[k] == update.data[k]}
        self.assertEqual(unchanged, set(OLD) - {"version", "artifact_url", "sha256", "icon_url"})

    def test_skips_drafts_and_up_to_date(self):
        update, reason = self.find([release("v0.9.0", [asset("x.zip")], draft=True),
                                    release("v0.5.0", [asset("example-0.5.0-PPSA01234.zip")])])
        self.assertEqual((update, reason), (None, "up to date"))

    def test_keeps_icon_when_missing_at_new_tag(self):
        update, _ = self.find([release("v0.6.0", [asset("example-0.6.0-PPSA01234.zip")])], icon_exists=False)
        self.assertEqual(update.data["icon_url"], OLD["icon_url"])
        self.assertTrue(any("icon kept" in note for note in update.notes))

    def test_needs_a_digest(self):
        update, reason = self.find([release("v0.6.0", [asset("example-0.6.0-PPSA01234.zip", digest=None)])])
        self.assertIsNone(update)
        self.assertIn("no digest", reason)

    def test_reservations_are_skipped(self):
        self.assertEqual(self.find([], data=reservation(titleid="PPSA01234")), (None, "reservation"))


class BumpPolicyTests(unittest.TestCase):
    def setUp(self):
        self.github = FakeGitHub([release("v0.6.0", [asset("example-0.6.0-PPSA01234.zip")])])
        self.old = Record(Path("PPSA01234.json"), OLD)
        update, _ = find_update(self.old, self.github, icon_exists=lambda url: True)
        self.new = Record(Path("PPSA01234.json"), update.data)

    def test_newest_release_bump_is_recognised(self):
        self.assertTrue(is_release_bump(self.old, self.new, self.github))

    def test_other_changes_are_not_a_bump(self):
        renamed = Record(self.new.path, dict(self.new.data, name="Other Name"))
        self.assertFalse(is_release_bump(self.old, renamed, self.github))
        older = FakeGitHub([release("v0.7.0", [])])
        self.assertFalse(is_release_bump(self.old, self.new, older))

    def test_bot_may_open_a_bump_but_not_other_changes(self):
        report = Report()
        check_publisher("catalog-bot[bot]", False, self.old, self.new, self.github, report)
        self.assertFalse(report.failed)
        report = Report()
        renamed = Record(self.new.path, dict(self.new.data, name="Other Name"))
        github = FakeGitHub(self.github._releases)
        github.account_type = lambda login: "User"
        check_publisher("catalog-bot[bot]", False, self.old, renamed, github, report)
        self.assertTrue(report.failed)


class OpenPullRequestTests(unittest.TestCase):
    def run_git(self, cwd, *args):
        return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout

    def test_opens_then_skips_an_identical_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            origin, clone = root / "origin", root / "clone"
            origin.mkdir()
            self.run_git(origin, "init", "-q", "-b", "main")
            self.run_git(origin, "config", "user.email", "t@example.com")
            self.run_git(origin, "config", "user.name", "T")
            self.run_git(origin, "config", "receive.denyCurrentBranch", "ignore")
            write_record(origin / "apps", OLD)
            self.run_git(origin, "add", ".")
            self.run_git(origin, "commit", "-q", "-m", "base")
            self.run_git(root, "clone", "-q", str(origin), str(clone))
            self.run_git(clone, "config", "user.email", "bot@example.com")
            self.run_git(clone, "config", "user.name", "Bot")

            old = Record(clone / "apps" / "PPSA01234.json", OLD)
            github = FakeGitHub([release("v0.6.0", [asset("example-0.6.0-PPSA01234.zip")])])
            update, _ = find_update(old, github, icon_exists=lambda url: True)
            created, open_pr = [], {}
            github.closed_pull_titles = lambda repo, branch: []
            github.open_pull = lambda repo, branch: open_pr.get(branch)
            github.create_pull = lambda repo, head, base, title, body: created.append((head, title)) or {"number": 7}
            github.update_pull = lambda *args: self.fail("identical update should not be refreshed")

            with mock.patch.object(cli, "ROOT", clone), mock.patch.object(cli, "APPS", clone / "apps"):
                report = Report()
                cli.open_update_pr(update, "example/catalog", github, report)
                self.assertEqual(created, [("catalog-update/PPSA01234", "Update Example App to 0.6.0")])
                pushed = self.run_git(origin, "show", "catalog-update/PPSA01234:apps/PPSA01234.json")
                self.assertEqual(json.loads(pushed)["version"], "0.6.0")
                self.assertEqual(json.loads((clone / "apps" / "PPSA01234.json").read_text())["version"], "0.5.0")

                open_pr["catalog-update/PPSA01234"] = {"number": 7}
                report = Report()
                cli.open_update_pr(update, "example/catalog", github, report)
                self.assertIn("already proposes", report.items[-1][2])


if __name__ == "__main__":
    unittest.main()
