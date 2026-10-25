"""Shared reader for frontend component `@ac` declaration blocks.

MODULE: _frontend_declaration_reader.py
GOAL: Parse the leading comment block of a frontend component file, record the
    acceptance-criterion ids it declares (via `@ac <id>[, <id>...]`) in authored
    order, and emit one stable record per file:
    {path, framework, role, declaration_block, declares, verdict}.
BUSINESS CONTEXT: GE-124a-1. One reader serves both the commit-tier check
    (GE-124c) and the CI-tier gate (GE-124e); two private parsers of one comment
    grammar drift, and the visible symptom is one tier accepting what the other
    rejects. Ids are opaque strings here: resolving them against the AC store is
    GE-124c-2's job, never this module's.
ARCHITECTURE: Pure text scan (no JS/TS AST). The commit tier reads the STAGED
    blob through the git index (`git show :<path>`), so an edit that is typed but
    not staged does not clear the check. Deployed alongside the other
    commit_guardian modules (the whole directory is copied by build.py).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

VERDICT_DECLARED = "declared"
VERDICT_MISSING = "missing"
VERDICT_UNREADABLE = "unreadable"

_FRAMEWORKS = {
    ".tsx": "react-tsx",
    ".jsx": "react-jsx",
    ".ts": "typescript",
    ".js": "javascript",
    ".vue": "vue",
    ".svelte": "svelte",
}
_BLOCK_COMMENT = re.compile(r"\s*(/\*.*?\*/)", re.DOTALL)
_LINE_COMMENTS = re.compile(r"(?:[ \t]*//[^\n]*\n?)+")
_AC_LINE = re.compile(r"@ac\b([^\n]*)")
_SEPARATORS = re.compile(r"[,\s]+")
_NOISE = ("*/", "-->")


def _framework_for(path: str) -> str:
    """Return the framework label for a path from its file extension."""
    return _FRAMEWORKS.get(Path(path).suffix.lower(), "unknown")


def _leading_comment(text: str) -> str:
    """Return the literal leading comment block of ``text`` ('' when none)."""
    stripped = text.lstrip("﻿")
    block = _BLOCK_COMMENT.match(stripped)
    if block:
        return block.group(1)
    start = len(stripped) - len(stripped.lstrip())
    lines = _LINE_COMMENTS.match(stripped, start)
    return lines.group(0).strip("\n") if lines else ""


def _ids_on_line(rest: str) -> list[str]:
    """Split the remainder of one `@ac` line into ids, preserving order."""
    cleaned = rest
    for noise in _NOISE:
        cleaned = cleaned.replace(noise, " ")
    cleaned = cleaned.rstrip("* \t")
    return [tok for tok in _SEPARATORS.split(cleaned.strip()) if tok]


def parse_declared_ids(block: str) -> list[str]:
    """Return every id declared by `@ac` lines in ``block``, in authored order."""
    ids: list[str] = []
    for match in _AC_LINE.finditer(block):
        ids.extend(_ids_on_line(match.group(1)))
    return ids


def read_declaration(path: str, text: str) -> dict:
    """Evaluate one file's text and return its declaration record."""
    block = _leading_comment(text)
    declares = parse_declared_ids(block)
    return {
        "path": path,
        "framework": _framework_for(path),
        "role": "component",
        "declaration_block": block,
        "declares": declares,
        "verdict": VERDICT_DECLARED if declares else VERDICT_MISSING,
    }


def _unreadable_record(path: str) -> dict:
    """Build the record for a path whose staged content could not be read."""
    record = read_declaration(path, "")
    record["verdict"] = VERDICT_UNREADABLE
    return record


def _staged_text(repo_root: str, path: str) -> str | None:
    """Return the staged (index) content of ``path`` or None when unreadable."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "show", f":{path}"],
            capture_output=True, check=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"[frontend-declaration-reader] cannot read staged {path}: {exc}", file=sys.stderr)
        return None
    return proc.stdout.decode("utf-8", errors="replace")


def read_staged_declarations(repo_root: str, paths: list[str]) -> list[dict]:
    """Return one record per path, read from the git index and never the working tree."""
    records = []
    for path in paths:
        text = _staged_text(repo_root, path)
        records.append(_unreadable_record(path) if text is None else read_declaration(path, text))
    return records


def main(argv: list[str] | None = None) -> int:
    """CLI: ``--staged <path>...`` prints a JSON list of records (cwd = repo root)."""
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] != "--staged":
        print("usage: _frontend_declaration_reader.py --staged <path>...", file=sys.stderr)
        return 2
    records = read_staged_declarations(str(Path.cwd()), args[1:])
    print(json.dumps(records))
    return 0


if __name__ == "__main__":
    sys.exit(main())

# DECISION HISTORY
# ================================================================================
# - 2026-10-23 17:00 [python-coder]: Created shared reader; separators are any run of commas/whitespace, order preserved, never sorted or de-duplicated; verdicts declared/missing/unreadable, resolution left to GE-124c-2. (#EPIC-EveryScreenSaysWhichRequirementItIs/01)
