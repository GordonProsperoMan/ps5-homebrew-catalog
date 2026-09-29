"""Summarize a wrangler log without revealing anything about the Cloudflare account.

Usage: python3 -m catalog.redact <wrangler.log>

The deploy job's logs are public, so only error lines are printed, and account
IDs, other long hex strings, emails, URLs and quoted values are masked.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

MAX_LINES = 12
ERROR_LINE = re.compile(r"✘|\bERROR\b|\[code: \d+\]|\berror\b", re.IGNORECASE)
ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
MASKS = (
    (re.compile(r"https?://\S+"), "<url>"),
    (re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+"), "<email>"),
    (re.compile(r"\b[0-9a-f]{16,}\b", re.IGNORECASE), "<id>"),
    (re.compile(r"/accounts/[^/\s]+"), "/accounts/<id>"),
    (re.compile(r"\"[^\"]*\"|'[^']*'|`[^`]*`"), "<value>"),
)


def summarize(text: str) -> list[str]:
    lines = []
    for raw in ANSI.sub("", text).splitlines():
        line = raw.strip()
        if not line or not ERROR_LINE.search(line):
            continue
        for pattern, replacement in MASKS:
            line = pattern.sub(replacement, line)
        if line not in lines:
            lines.append(line[:300])
    return lines[:MAX_LINES]


def main(argv: list[str]) -> int:
    lines = summarize(Path(argv[1]).read_text(encoding="utf-8", errors="replace")) if len(argv) > 1 else []
    for line in lines or ["(no error lines found in the wrangler output)"]:
        print(f"  {line}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
