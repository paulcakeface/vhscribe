#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r"!?\[[^]]*]\(([^)]+)\)")
failures: list[str] = []

for markdown in sorted(ROOT.rglob("*.md")):
    if ".git" in markdown.parts or ".venv" in markdown.parts:
        continue
    text = markdown.read_text(encoding="utf-8")
    for raw_target in LINK.findall(text):
        target = raw_target.strip().strip("<>").split(maxsplit=1)[0]
        if not target or target.startswith(("#", "http://", "https://", "mailto:")):
            continue
        path_text = urllib.parse.unquote(target.split("#", 1)[0])
        candidate = (markdown.parent / path_text).resolve()
        try:
            candidate.relative_to(ROOT)
        except ValueError:
            failures.append(f"{markdown.relative_to(ROOT)}: link escapes repository: {target}")
            continue
        if not candidate.exists():
            failures.append(f"{markdown.relative_to(ROOT)}: missing link target: {target}")

if failures:
    print("\n".join(failures), file=sys.stderr)
    raise SystemExit(1)

print("All local Markdown link targets exist.")
