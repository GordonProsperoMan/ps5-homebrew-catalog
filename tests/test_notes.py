import unittest

from catalog import notes

SAMPLE = """<!-- license header -->
# v1.2 — Faster menus
> [!WARNING]
> **Pre-release.** Needs a [loader](https://example.com/loader) on port 9021.

![badge](https://img.shields.io/badge/x) **Menus are faster.** Run `make` to build.

### Added
- One <b>thing</b>
  on two lines
- ![](https://img.shields.io/badge/new) **NEW** Two <script>alert(1)</script>
1. Numbered

| Mode | FPS |
| --- | --- |
| 4K | 120 |

```
make all
```
<details><summary>More</summary>hidden text</details>

**Full Changelog**: https://github.com/a/b/compare/1...2
"""


class NotesTests(unittest.TestCase):
    def test_plain_text_for_the_api(self):
        text, cut = notes.as_text(SAMPLE)
        self.assertFalse(cut)
        self.assertEqual(text.split("\n"), [
            "v1.2 — Faster menus",
            "Warning: Pre-release. Needs a loader on port 9021.",
            "",
            "Menus are faster. Run make to build.",
            "",
            "Added",
            "- One thing on two lines",
            "- NEW Two alert(1)",
            "- Numbered",
            "- Mode · FPS",
            "- 4K · 120",
            "",
            "make all",
            "",
            "Morehidden text",
        ])
        for unwanted in ("<", "](", "![", "Full Changelog", "license header", "**", "`"):
            self.assertNotIn(unwanted, text)

    def test_html_for_the_page_holds_only_the_catalogs_own_tags(self):
        body, cut = notes.as_html(SAMPLE)
        self.assertFalse(cut)
        self.assertIn("<h3>v1.2 — Faster menus</h3>", body)
        self.assertIn("<p><strong>Menus are faster.</strong> Run <code>make</code> to build.</p>", body)
        self.assertIn("<li><strong>NEW</strong> Two alert(1)</li>", body)
        self.assertEqual(body.count("<ul>"), body.count("</ul>"))
        for unwanted in ("<script", "<img", "<a ", "<b>", "<details", "http"):
            self.assertNotIn(unwanted, body)
        # Text that looks like markup after the tags are gone is escaped, not passed on.
        self.assertEqual(notes.as_html("a &lt;script&gt; b")[0], "<p>a &lt;script&gt; b</p>")

    def test_notes_that_say_nothing_are_no_notes(self):
        for empty in (None, "", "  \n", "**Full Changelog**: https://github.com/a/b/compare/1...2",
                      "## What's Changed\n\n**Full Changelog**: https://x/y", "# Only a title", "<!-- x -->"):
            self.assertEqual(notes.as_text(empty), (None, False), empty)
            self.assertEqual(notes.as_html(empty), ("", False), empty)

    def test_long_notes_are_cut_at_a_block(self):
        long = "## Changes\n" + "\n".join(f"- change number {n} " + "x" * 40 for n in range(200)) + "\n## Install\n"
        text, cut = notes.as_text(long)
        self.assertTrue(cut)
        self.assertLessEqual(len(text), notes.API_LIMIT)
        self.assertTrue(text.splitlines()[-1].startswith("- change number"))
        body, cut = notes.as_html(long)
        self.assertTrue(cut)
        self.assertTrue(body.endswith("</ul>"))
        one, cut = notes.as_text("word " * 3000)
        self.assertTrue(cut)
        self.assertLessEqual(len(one), notes.API_LIMIT + 1)
        self.assertTrue(one.endswith("…"))


if __name__ == "__main__":
    unittest.main()
