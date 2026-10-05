"""Release notes: the text a developer wrote on the GitHub release of the listed version.

The notes are the developer's, not the catalog's: nobody reviews them, and they
are GitHub Markdown that may carry HTML, images and tables. So the catalog never
passes them on as written. They are read into a few kinds of blocks (headings,
paragraphs, list items), with everything else reduced to its text, and from
those blocks come the two things that are published: plain text for the store
API, and a small piece of HTML for the app's page. Images are dropped, links
keep only their text, and raw HTML keeps only what it encloses.

A release whose notes say nothing (empty, or only GitHub's generated "Full
Changelog" link) has no notes.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

MAX_SOURCE = 40000      # characters of a release body kept from GitHub
API_LIMIT = 4000        # characters of plain text in the store API
PAGE_LIMIT = 1800       # characters shown on an app's page

_COMMENT = re.compile(r"<!--.*?-->", re.S)
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)|<img\b[^>]*>", re.I)
_LINK = re.compile(r"\[([^\]]*)\]\((?:[^()]|\([^)]*\))*\)")
_AUTOLINK = re.compile(r"<(https?://[^>\s]+)>")
# HTML that GitHub renders or strips; anything else in angle brackets ("<PS5-IP>") is the developer's text.
_TAG = re.compile(r"</?(?:a|b|i|u|s|p|br|hr|div|span|details|summary|table|thead|tbody|tr|td|th|ul|ol|li|h[1-6]|strong|em|"
                  r"code|pre|kbd|sub|sup|center|picture|source|video|audio|blockquote|font|small|big|del|ins|script|"
                  r"style|iframe|svg|path)(?:\s[^>]*)?/?>", re.I)
_GENERATED = re.compile(r"^\**Full Changelog\**\s*:?\**\s*\S+$|^(?:#+\s*)?What's Changed$|^(?:#+\s*)?New Contributors$", re.I)
_HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*$")
_ITEM = re.compile(r"^\s*(?:[-*+]|\d{1,3}[.)])\s+(.*)$")
_RULE = re.compile(r"^\s*(?:[-*_]\s*){3,}$")
_TABLE_RULE = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_ALERT = re.compile(r"^\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\]\s*$", re.I)
_EMPHASIS = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
_ITALIC = re.compile(r"(?<![\w*])\*(?=\S)([^*\n]+?)(?<=\S)\*(?![\w*])")
_CODE = re.compile(r"`+([^`\n]+?)`+")


@dataclass(frozen=True)
class Block:
    kind: str       # "heading", "text" or "item"
    text: str       # one line; **bold** and `code` marks kept, everything else plain


def _inline(text: str) -> str:
    text = _IMAGE.sub("", text)
    text = _LINK.sub(lambda m: m.group(1), text)
    text = _AUTOLINK.sub(lambda m: m.group(1), text)
    text = _TAG.sub("", text)
    text = html.unescape(text)
    text = _ITALIC.sub(lambda m: m.group(1), text)
    return re.sub(r"\s+", " ", text).strip()


def parse(markdown: str | None) -> list[Block]:
    """The notes as blocks; an empty list when they say nothing."""
    if not markdown:
        return []
    text = _COMMENT.sub("", markdown[:MAX_SOURCE]).replace("\r\n", "\n").replace("\r", "\n")
    blocks: list[Block] = []
    paragraph: list[str] = []
    in_code = False

    def flush():
        if paragraph:
            joined = _inline(" ".join(paragraph))
            if joined:
                blocks.append(Block("text", joined))
            paragraph.clear()

    for raw in text.split("\n"):
        line = raw.rstrip()
        if line.lstrip().startswith(("```", "~~~")):
            flush()
            in_code = not in_code
            continue
        if in_code:
            if line.strip():
                blocks.append(Block("text", "`" + line.strip().replace("`", "'") + "`"))
            continue
        line = re.sub(r"^\s*(?:>\s?)+", "", line)          # quoted text reads as text
        stripped = line.strip()
        if not stripped or _RULE.match(stripped):
            flush()
            continue
        if _GENERATED.match(_inline(stripped)) or _TABLE_RULE.match(stripped) and "|" in stripped:
            flush()
            continue
        alert = _ALERT.match(stripped)
        if alert:
            flush()
            paragraph.append(f"**{alert.group(1).capitalize()}:**")
            continue
        heading = _HEADING.match(stripped)
        if heading:
            flush()
            title = _inline(heading.group(2)).replace("**", "")
            if title:
                blocks.append(Block("heading", title))
            continue
        item = _ITEM.match(line)
        if item:
            flush()
            content = _inline(item.group(1))
            if content:
                blocks.append(Block("item", content))
            continue
        if stripped.startswith("|") and stripped.endswith("|"):
            flush()
            cells = [c for c in (_inline(c) for c in stripped.strip("|").split("|")) if c]
            if cells:
                blocks.append(Block("item", " · ".join(cells)))
            continue
        if blocks and blocks[-1].kind == "item" and raw.startswith((" ", "\t")) and not paragraph:
            blocks[-1] = Block("item", (blocks[-1].text + " " + _inline(stripped)).strip())     # a wrapped list item
            continue
        paragraph.append(stripped)
    flush()
    # Notes that are only headings (or nothing) say nothing.
    return blocks if any(b.kind != "heading" for b in blocks) else []


def _plain(text: str) -> str:
    return _CODE.sub(lambda m: m.group(1), _EMPHASIS.sub(lambda m: m.group(2), text))


def _cut(blocks: list[Block], limit: int) -> tuple[list[Block], bool]:
    """(the leading blocks that fit in limit characters, whether any were left out)."""
    kept: list[Block] = []
    used, cut = 0, False
    for block in blocks:
        size = len(_plain(block.text)) + 3      # with its list mark or blank line, and the line end
        if used + size > limit:
            cut = True
            if not kept:        # one very long first block: keep its beginning
                kept.append(Block(block.kind, _plain(block.text)[:limit].rsplit(" ", 1)[0] + "…"))
            break
        kept.append(block)
        used += size
    while cut and len(kept) > 1 and kept[-1].kind == "heading":     # a heading with nothing under it
        kept.pop()
    return kept, cut


def as_text(markdown: str | None, limit: int = API_LIMIT) -> tuple[str | None, bool]:
    """(plain text, whether it was cut short) for the store API; (None, False) without notes."""
    blocks, cut = _cut(parse(markdown), limit)
    if not blocks:
        return None, False
    lines: list[str] = []
    for index, block in enumerate(blocks):
        text = _plain(block.text)
        if block.kind == "item":
            lines.append("- " + text)
            continue
        if index and not (block.kind == "text" and blocks[index - 1].kind == "heading"):
            lines.append("")
        lines.append(text)
    return "\n".join(lines).strip(), cut


def _rich(text: str) -> str:
    escaped = html.escape(text, quote=True)
    escaped = _EMPHASIS.sub(lambda m: f"<strong>{m.group(2)}</strong>", escaped)
    return _CODE.sub(lambda m: f"<code>{m.group(1)}</code>", escaped)


def as_html(markdown: str | None, limit: int = PAGE_LIMIT) -> tuple[str, bool]:
    """(HTML for the app's page, whether it was cut short); ("", False) without notes."""
    blocks, cut = _cut(parse(markdown), limit)
    out: list[str] = []
    in_list = False
    for block in blocks:
        if block.kind == "item":
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{_rich(block.text)}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        out.append(f"<h3>{_rich(block.text)}</h3>" if block.kind == "heading" else f"<p>{_rich(block.text)}</p>")
    if in_list:
        out.append("</ul>")
    return "\n".join(out), cut
