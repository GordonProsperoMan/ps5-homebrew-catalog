import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from catalog.report import Report
from catalog.site import THEMES, build_site

from helpers import record, reservation, write_record


class SiteBuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.apps = root / "apps"
        self.out = root / "dist"
        write_record(self.apps, record(name="Evil <script>alert(1)</script>",
                                       description='Quote " and <b>tags</b> & ampersands.'))
        write_record(self.apps, record(
            titleid="PPSA04321", name="Image Game", kind="game", sha256="b" * 64,
            artifact_url="https://github.com/example/example-app/releases/download/2/PPSA04321.ffpkg"))
        write_record(self.apps, reservation())

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, **options):
        report = Report()
        with mock.patch.dict("os.environ", {"CF_PAGES_COMMIT_SHA": "abc1234def"}):
            count = build_site(self.out, self.apps, report, fetch_icons=False, **options)
        return count, report

    def test_builds_pages_feed_and_config(self):
        count, report = self.build()
        self.assertEqual((count, report.failed), (3, False))
        root = self.out / "ps5"
        for path in ("index.html", "list/index.html", "app/PPSA01234/index.html", "app/PPSA04321/index.html",
                     "app/PPSA05555/index.html",
                     "catalog/v1.json", "favicon.svg", "404.html"):
            self.assertTrue((root / path).is_file(), path)
        for path in ("_headers", "_redirects", "404.html", "robots.txt"):
            self.assertTrue((self.out / path).is_file(), path)
        self.assertIn("/ /ps5/ 302", (self.out / "_redirects").read_text(encoding="utf-8"))

    def test_metadata_is_escaped(self):
        self.build()
        for page in (self.out / "ps5" / "index.html", self.out / "ps5" / "list" / "index.html",
                     self.out / "ps5" / "app" / "PPSA01234" / "index.html"):
            html = page.read_text(encoding="utf-8")
            self.assertNotIn("<script>alert", html)
            self.assertNotIn("<b>tags</b>", html)
            self.assertIn("&lt;script&gt;", html)

    def test_feed(self):
        self.build()
        feed = json.loads((self.out / "ps5" / "catalog" / "v1.json").read_text(encoding="utf-8"))
        self.assertEqual(feed["schema"], 1)
        self.assertEqual(feed["source"]["commit"], "abc1234def")
        self.assertEqual([a["titleid"] for a in feed["apps"]], ["PPSA01234", "PPSA04321"])
        self.assertEqual([a["format"] for a in feed["apps"]], ["zip", "ffpkg"])
        self.assertTrue(feed["apps"][0]["page"].endswith("/ps5/app/PPSA01234/"))
        self.assertEqual([a["titleid"] for a in feed["coming_soon"]], ["PPSA05555"])
        self.assertNotIn("artifact_url", feed["coming_soon"][0])

    def test_reservation_pages(self):
        self.build()
        root = self.out / "ps5"
        page = (root / "app" / "PPSA05555" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Not released yet", page)
        self.assertNotIn("rel=\"nofollow\"", page)
        for listing in ("index.html", "list/index.html"):
            html = (root / listing).read_text(encoding="utf-8")
            self.assertIn('data-status="soon"', html)
            self.assertIn('data-status="available"', html)

    def test_list_page_has_rows_and_filters(self):
        self.build()
        html = (self.out / "ps5" / "list" / "index.html").read_text(encoding="utf-8")
        self.assertEqual(html.count('class="lrow '), 3)
        for hook in ("data-search", "data-status-filter", "data-format-filter", "data-sort", 'data-view-link'):
            self.assertIn(hook, html)
        self.assertIn('aria-current="page"', html)

    def test_install_steps_follow_format(self):
        self.build()
        zip_page = (self.out / "ps5" / "app" / "PPSA01234" / "index.html").read_text(encoding="utf-8")
        image_page = (self.out / "ps5" / "app" / "PPSA04321" / "index.html").read_text(encoding="utf-8")
        self.assertIn("extract it", zip_page)
        self.assertIn("Copy the file as-is", image_page)

    def test_every_theme_builds(self):
        for theme in THEMES:
            with self.subTest(theme=theme):
                count, report = self.build(theme=theme)
                self.assertEqual(count, 3)
                html = (self.out / "ps5" / "index.html").read_text(encoding="utf-8")
                self.assertNotIn("$", html.replace("$ ", ""))

    def test_invalid_catalog_builds_nothing(self):
        write_record(self.apps, record(titleid="PPSA05555", name="Broken", sha256="nope"))
        count, report = self.build()
        self.assertTrue(report.failed)
        self.assertFalse(self.out.exists())

    def test_refuses_to_replace_foreign_directory(self):
        self.out.mkdir()
        (self.out / "keep.txt").write_text("mine", encoding="utf-8")
        with self.assertRaises(SystemExit):
            self.build()
        self.assertTrue((self.out / "keep.txt").exists())


if __name__ == "__main__":
    unittest.main()
