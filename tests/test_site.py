import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from catalog.report import Report
from catalog import site
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
            titleid="PPSA04321", name="Image Game", kind="game", version="2", sha256="b" * 64,
            artifact_url="https://github.com/example/example-app/releases/download/2/PPSA04321.ffpkg"))
        write_record(self.apps, reservation())

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, **options):
        report = Report()
        with mock.patch.dict("os.environ", {"CF_PAGES_COMMIT_SHA": "abc1234def"}):
            options.setdefault("fetch_icons", False)
            count = build_site(self.out, self.apps, report, **options)
        return count, report

    def test_builds_pages_feed_and_config(self):
        count, report = self.build()
        self.assertEqual((count, report.failed), (3, False))
        root = self.out
        for path in ("index.html", "app/PPSA01234/index.html", "app/PPSA04321/index.html",
                     "app/PPSA05555/index.html",
                     "catalog/v1.json", "favicon.svg", "404.html", "tv/index.html"):
            self.assertTrue((root / path).is_file(), path)
        for path in ("_headers", "_redirects", "404.html", "robots.txt"):
            self.assertTrue((self.out / path).is_file(), path)
        redirects = (self.out / "_redirects").read_text(encoding="utf-8")
        self.assertNotIn("/ / 302", redirects)
        self.assertIn("/list/ /?view=list 301", redirects)
        # Links from when the site lived under /ps5/ keep working.
        self.assertIn("/ps5/list/ /?view=list 301", redirects)
        self.assertIn("/ps5 / 301", redirects)
        self.assertIn("/ps5/* /:splat 301", redirects)
        self.assertFalse((root / "list").exists())

    def test_footer_shows_when_the_catalog_last_changed(self):
        with mock.patch.object(site, "source_commit_time", lambda commit: "2026-10-03T04:05:00Z"):
            self.build()
        page = (self.out / "index.html").read_text(encoding="utf-8")
        self.assertIn('abc1234</a> · last updated <time datetime="2026-10-03T04:05:00Z">3 Oct 2026, 04:05 UTC</time>.',
                      page)
        self.assertIn('Maintained by <a href="https://github.com/blackbearreloaded">BlackBearReloaded</a> · Built from', page)
        self.assertIn('<aside class="announce"', page)
        self.assertIn('href="https://github.com/blackbearreloaded/ProsperoStore"', page)
        tv = (self.out / "tv" / "index.html").read_text(encoding="utf-8")
        self.assertIn('<p class="tv-credit">Maintained by BlackBearReloaded · Built from abc1234 · last updated '
                      '<time datetime="2026-10-03T04:05:00Z">3 Oct 2026, 04:05 UTC</time></p>', tv)
        self.assertEqual(site._commit_time_html(None), "")

    def test_metadata_is_escaped(self):
        self.build()
        for page in (self.out / "index.html", self.out / "app" / "PPSA01234" / "index.html"):
            html = page.read_text(encoding="utf-8")
            self.assertNotIn("<script>alert", html)
            self.assertNotIn("<b>tags</b>", html)
            self.assertIn("&lt;script&gt;", html)

    def test_version_label(self):
        from catalog.site import version_label
        self.assertEqual(version_label("01.000.005"), "v01.000.005")
        self.assertEqual(version_label("vk-285-113"), "vk-285-113")
        self.assertEqual(version_label("v1.0"), "v1.0")

    def test_api(self):
        self.build()
        api = self.out / "api" / "v1"
        app = json.loads((api / "apps" / "PPSA01234.json").read_text(encoding="utf-8"))
        self.assertEqual((app["schema"], app["status"], app["format"], app["artifact_name"], app["tag"]),
                         (3, "available", "zip", "PPSA01234.zip", "01.000.000"))
        self.assertEqual(app["sha256"], "a" * 64)                      # every record field is there
        self.assertEqual(app["page"], "https://homebrew.page/app/PPSA01234/")
        self.assertEqual(app["release_url"], "https://github.com/example/example-app/releases/tag/01.000.000")
        # An offline build knows no release facts and has no icons; the fields are present and null.
        self.assertEqual([app[k] for k in ("size", "released", "prerelease", "content_version", "icon", "icon_small",
                                           "icon_hash")], [None] * 7)
        soon = json.loads((api / "apps" / "PPSA05555.json").read_text(encoding="utf-8"))
        self.assertEqual((soon["status"], soon["artifact_url"], soon["format"], soon["tag"]),
                         ("coming_soon", None, None, None))
        index = json.loads((api / "index.json").read_text(encoding="utf-8"))
        self.assertEqual((index["schema"], index["count"], index["commit"]), (3, 3, "abc1234def"))
        self.assertEqual([a["titleid"] for a in index["apps"]], ["PPSA01234", "PPSA04321", "PPSA05555"])
        self.assertNotIn("description", index["apps"][0])
        versions = json.loads((api / "versions.json").read_text(encoding="utf-8"))
        self.assertEqual(versions, {"schema": 3, "apps": {
            "PPSA01234": {"content_version": None, "version": "01.000.000"},
            "PPSA04321": {"content_version": None, "version": "2"}}})
        self.assertIn("/api/*\n  Access-Control-Allow-Origin: *", (self.out / "_headers").read_text(encoding="utf-8"))
        self.assertIn("/api/*/manifest.sig\n  Content-Type: application/octet-stream",
                      (self.out / "_headers").read_text(encoding="utf-8"))
        # The manifest names every JSON file of the API by its hash; the build itself never signs.
        import hashlib
        manifest = json.loads((api / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(sorted(manifest["files"]), ["apps/PPSA01234.json", "apps/PPSA04321.json", "apps/PPSA05555.json",
                                                     "index.json", "versions.json"])
        self.assertEqual(manifest["files"]["index.json"], hashlib.sha256((api / "index.json").read_bytes()).hexdigest())
        self.assertEqual((manifest["schema"], manifest["commit"]), (3, "abc1234def"))
        self.assertIsInstance(manifest["sequence"], int)
        self.assertFalse((api / "manifest.sig").exists())

    def test_api_release_facts_and_icons(self):
        from catalog import facts as facts_module
        known = facts_module.Facts(size=4096, released="2026-09-01T10:00:00Z", prerelease=False,
                                   content_version="01.000.000", param_path="sce_sys/param.json")
        png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR" + (512).to_bytes(4, "big") * 2
        with mock.patch.object(site, "_icon", lambda url, cache: (png, "png", png)), \
                mock.patch.object(site, "png_icons", lambda data: {512: b"large", 256: b"small"}), \
                mock.patch.object(facts_module, "cached", lambda record, github, cache, fetch=None:
                                  (facts_module.Facts(), None) if record.reserved else (known, None)):
            self.build(fetch_icons=True, github=object())
        api = self.out / "api" / "v1"
        app = json.loads((api / "apps" / "PPSA01234.json").read_text(encoding="utf-8"))
        self.assertEqual((app["size"], app["released"], app["prerelease"], app["content_version"]),
                         (4096, "2026-09-01T10:00:00Z", False, "01.000.000"))
        self.assertEqual(app["icon"], "https://homebrew.page/api/v1/icons/PPSA01234.png")
        self.assertEqual(app["icon_small"], "https://homebrew.page/api/v1/icons/PPSA01234-256.png")
        self.assertEqual((api / "icons" / "PPSA01234-256.png").read_bytes(), b"small")
        # The fingerprint is of the developer's image, so it changes only when that image does.
        import hashlib
        self.assertEqual(app["icon_hash"], hashlib.sha256(png).hexdigest()[:16])
        index = json.loads((api / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["apps"][0]["icon_hash"], app["icon_hash"])
        self.assertIsNone(index["apps"][2]["icon_hash"])               # the reservation has no icon
        versions = json.loads((api / "versions.json").read_text(encoding="utf-8"))
        self.assertEqual(versions["apps"]["PPSA01234"], {"content_version": "01.000.000", "version": "01.000.000"})

    def test_tv_mode(self):
        self.build()
        html = (self.out / "tv" / "index.html").read_text(encoding="utf-8")
        # The metadata is data for tv.js; no value can close the JSON <script> element.
        self.assertNotIn("<script>alert", html)
        self.assertNotIn("</script>alert", html)
        raw = html.split('<script type="application/json" id="tv-data">', 1)[1].split("</script>", 1)[0]
        data = json.loads(raw)
        by_id = {a["titleid"]: a for a in data["apps"]}
        self.assertEqual(by_id["PPSA01234"]["name"], "Evil <script>alert(1)</script>")
        self.assertEqual(by_id["PPSA01234"]["short_url"], "homebrew.page/app/PPSA01234/")
        self.assertTrue(by_id["PPSA01234"]["steps"][0].startswith("Download PPSA01234.zip"))
        self.assertTrue(by_id["PPSA05555"]["soon"])
        self.assertNotIn("sha256", by_id["PPSA05555"])
        self.assertIn('data-kind="soon"', html)
        self.assertIn('href="/tv/?layout=tv"', (self.out / "index.html").read_text(encoding="utf-8"))
        self.assertIn('href="/?layout=web"', html)

    def test_feed(self):
        self.build()
        feed = json.loads((self.out / "catalog" / "v1.json").read_text(encoding="utf-8"))
        self.assertEqual(feed["schema"], 1)
        self.assertEqual(feed["source"]["commit"], "abc1234def")
        self.assertEqual([a["titleid"] for a in feed["apps"]], ["PPSA01234", "PPSA04321"])
        self.assertEqual([a["format"] for a in feed["apps"]], ["zip", "ffpkg"])
        self.assertTrue(feed["apps"][0]["page"].endswith("homebrew.page/app/PPSA01234/"))
        self.assertEqual([a["titleid"] for a in feed["coming_soon"]], ["PPSA05555"])
        self.assertIsNone(feed["coming_soon"][0]["artifact_url"])
        self.assertIsNone(feed["coming_soon"][0]["source_repo"])

    def test_reservation_pages(self):
        self.build()
        root = self.out
        page = (root / "app" / "PPSA05555" / "index.html").read_text(encoding="utf-8")
        self.assertIn("Not released yet", page)
        self.assertNotIn("rel=\"nofollow\"", page)
        self.assertNotIn("None", page)
        html = (root / "index.html").read_text(encoding="utf-8")
        self.assertEqual(html.count('data-status="soon"'), 2)
        self.assertIn('data-status="available"', html)

    def test_catalog_page_holds_both_views_and_filters(self):
        self.build()
        html = (self.out / "index.html").read_text(encoding="utf-8")
        self.assertEqual(html.count('class="lrow '), 3)
        self.assertEqual(html.count('class="card-item"'), 3)
        self.assertEqual(html.count("data-grid"), 2)
        for hook in ("data-search", "data-status-filter", "data-format-filter", "data-sort",
                     'data-view-button="cards"', 'data-view-button="list"', 'data-base="/"'):
            self.assertIn(hook, html)

    def test_feed_is_minified(self):
        self.build()
        text = (self.out / "catalog" / "v1.json").read_text(encoding="utf-8")
        self.assertEqual(text.count("\n"), 1)

    def test_install_steps_follow_format(self):
        self.build()
        zip_page = (self.out / "app" / "PPSA01234" / "index.html").read_text(encoding="utf-8")
        image_page = (self.out / "app" / "PPSA04321" / "index.html").read_text(encoding="utf-8")
        self.assertIn("extract it", zip_page)
        self.assertIn("Copy the file as-is", image_page)

    def test_every_theme_builds(self):
        for theme in THEMES:
            with self.subTest(theme=theme):
                count, report = self.build(theme=theme)
                self.assertEqual(count, 3)
                html = (self.out / "index.html").read_text(encoding="utf-8")
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


class IconCacheTests(unittest.TestCase):
    PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\x0dIHDR" + (512).to_bytes(4, "big") * 2)

    def test_icons_are_fetched_once_and_pruned(self):
        from catalog import site
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            apps, cache = root / "apps", root / "cache"
            write_record(apps, record())
            fetches = []

            def fake_fetch(url, limit):
                fetches.append(url)
                return self.PNG

            with mock.patch.object(site.artifacts, "fetch_small", fake_fetch), \
                    mock.patch.object(site, "process_icon", lambda data: (data, "png")):
                for n in range(2):
                    site.build_site(root / f"out{n}", apps, Report(), icon_cache=cache)
                self.assertEqual(len(fetches), 1)
                self.assertEqual(len(list(cache.glob("*.img"))), 1)
                write_record(apps, record(icon_url="https://example.com/new.png"))
                site.build_site(root / "out3", apps, Report(), icon_cache=cache)
                self.assertEqual(len(fetches), 2)
                self.assertEqual(len(list(cache.glob("*.img"))), 1)


if __name__ == "__main__":
    unittest.main()
