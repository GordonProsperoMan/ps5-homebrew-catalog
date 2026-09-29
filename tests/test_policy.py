import unittest
from pathlib import Path

from catalog.policy import Change, check_changes, check_publisher, is_maintainer
from catalog.records import Record
from catalog.report import Report

from helpers import record


class FakeGitHub:
    def __init__(self, owner_type="User", public_members=()):
        self.owner_type = owner_type
        self.public_members = set(public_members)

    def account_type(self, login):
        return self.owner_type

    def is_public_member(self, org, user):
        return user in self.public_members


def make_record(owner="example"):
    data = record(source_repo=f"https://github.com/{owner}/example-app",
                  artifact_url=f"https://github.com/{owner}/example-app/releases/download/1/PPSA01234.zip")
    return Record(Path("PPSA01234.json"), data)


def errors(report):
    return [m for level, _, m in report.items if level == "error"]


class ChangeTests(unittest.TestCase):
    def test_community_may_add_one_record(self):
        report = Report()
        result = check_changes([Change("A", "apps/PPSA01234.json", "100644")], False, report)
        self.assertEqual(errors(report), [])
        self.assertEqual(len(result), 1)

    def test_community_cannot_touch_other_files(self):
        report = Report()
        check_changes([Change("A", "apps/PPSA01234.json", "100644"),
                       Change("M", "catalog/records.py", "100644")], False, report)
        self.assertTrue(any("may change only" in e for e in errors(report)))

    def test_community_limits(self):
        report = Report()
        check_changes([Change("A", "apps/PPSA01234.json", "100644"),
                       Change("A", "apps/PPSA04321.json", "100644")], False, report)
        self.assertTrue(any("one app per pull request" in e for e in errors(report)))

        report = Report()
        check_changes([Change("D", "apps/PPSA01234.json")], False, report)
        self.assertTrue(any("withdrawal" in e for e in errors(report)))

    def test_file_rules_apply_to_everyone(self):
        for change in (Change("A", "apps/PPSA01234.json", "120000"),
                       Change("A", "apps/PPSA01234.json", "100755"),
                       Change("A", "apps/readme.md", "100644")):
            with self.subTest(change=change):
                report = Report()
                check_changes([change], True, report)
                self.assertTrue(errors(report))

    def test_maintainer_may_change_anything(self):
        report = Report()
        check_changes([Change("D", "apps/PPSA01234.json"), Change("M", "README.md", "100644"),
                       Change("A", "apps/PPSA04321.json", "100644"),
                       Change("A", "apps/PPSA05555.json", "100644")], True, report)
        self.assertEqual(errors(report), [])

    def test_maintainer_associations(self):
        self.assertTrue(is_maintainer("OWNER"))
        self.assertFalse(is_maintainer("CONTRIBUTOR"))
        self.assertFalse(is_maintainer("FIRST_TIME_CONTRIBUTOR"))


class PublisherTests(unittest.TestCase):
    def check(self, author, old=None, new=None, maintainer=False, github=None):
        report = Report()
        check_publisher(author, maintainer, old, new or make_record(), github or FakeGitHub(), report)
        return errors(report)

    def test_repository_owner_may_publish(self):
        self.assertEqual(self.check("Example"), [])

    def test_stranger_rejected(self):
        self.assertTrue(any("does not own" in e for e in self.check("mallory")))

    def test_public_org_member_accepted(self):
        github = FakeGitHub("Organization", {"alice"})
        self.assertEqual(self.check("alice", github=github), [])
        self.assertTrue(self.check("bob", github=github))

    def test_title_id_cannot_change_owner(self):
        old, new = make_record("example"), make_record("mallory")
        self.assertTrue(any("registered to example" in e for e in self.check("mallory", old, new)))
        self.assertEqual(self.check("owner", old, new, maintainer=True), [])


if __name__ == "__main__":
    unittest.main()
