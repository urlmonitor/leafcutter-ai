"""
MODULE: build_placeholder_detection
GOAL: Post-build scan that detects TODO/PLACEHOLDER markers in generated files
    and reports them so the onboard agent can surface them to the user.
BUSINESS CONTEXT: build.py writes files like docs/vision.md and docs/roadmap.json
    with placeholder content (e.g. "TODO: Replace with..."). Without detection,
    the onboard agent sees "file exists" and moves on, leaving stale placeholders
    that confuse downstream agents.
ARCHITECTURE: Single public function scan_for_placeholders() that walks a set of
    output paths and returns a list of PlaceholderHit dicts. Called by build.py as
    a post-build phase; results are passed to the onboard agent for user reporting.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_MARKER_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bTODO\s*:", re.IGNORECASE),
    re.compile(r"\bPLACEHOLDER\b", re.IGNORECASE),
    re.compile(r"\bReplace with\b", re.IGNORECASE),
    re.compile(r"<!--\s*QUESTION\b", re.IGNORECASE),
    re.compile(r"\bFIXME\s*:", re.IGNORECASE),
]

_SKIP_EXTENSIONS = frozenset({".pyc", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2"})


def scan_for_placeholders(
    target_root: Path,
    paths: list[Path] | None = None,
) -> list[dict[str, Any]]:
    """Scan output files for placeholder markers.

    Args:
        target_root: Absolute path to the target project root.
        paths: Specific paths to scan. If None, scans a default set of
            files known to contain placeholders after build.

    Returns:
        List of dicts with keys: path (str, relative to target_root),
        line (int), marker (str), context (str — the line content).
    """
    if paths is None:
        paths = _default_scan_paths(target_root)

    hits: list[dict[str, Any]] = []
    for path in paths:
        if not path.is_file():
            continue
        if path.suffix.lower() in _SKIP_EXTENSIONS:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            for pattern in _MARKER_PATTERNS:
                match = pattern.search(line)
                if match:
                    hits.append({
                        "path": str(path.relative_to(target_root)),
                        "line": lineno,
                        "marker": match.group(0),
                        "context": line.strip(),
                    })
                    break
    return hits


def _default_scan_paths(target_root: Path) -> list[Path]:
    """Return the default set of paths to scan for placeholders.

    Args:
        target_root: Absolute path to the target project root.

    Returns:
        List of Path objects to scan.
    """
    candidates = [
        target_root / "docs" / "vision.md",
        target_root / "docs" / "roadmap.json",
        target_root / "CLAUDE.md",
    ]
    return [p for p in candidates if p.exists()]


def format_placeholder_report(hits: list[dict[str, Any]]) -> str:
    """Format placeholder hits as a human-readable report.

    Args:
        hits: List of placeholder hit dicts from scan_for_placeholders().

    Returns:
        Markdown-formatted report string, or empty string if no hits.
    """
    if not hits:
        return ""
    by_file: dict[str, list[dict[str, Any]]] = {}
    for hit in hits:
        by_file.setdefault(hit["path"], []).append(hit)
    lines = ["## Placeholder Content Detected", ""]
    for path, file_hits in sorted(by_file.items()):
        lines.append(f"**{path}** ({len(file_hits)} marker{'s' if len(file_hits) != 1 else ''}):")
        for hit in file_hits:
            lines.append(f"  - Line {hit['line']}: `{hit['marker']}` — {hit['context']}")
        lines.append("")
    return "\n".join(lines)
