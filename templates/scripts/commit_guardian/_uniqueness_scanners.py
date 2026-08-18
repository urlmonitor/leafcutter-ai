"""
Per-namespace directory walks for the whole-collection uniqueness pass.

MODULE: _uniqueness_scanners
GOAL: Walk each of the three fixed namespaces (acceptance-criteria,
    decisions, diagrams) and produce a NamespaceVerdict naming every number
    claimed by two or more artifacts. Split out of check_identifier_uniqueness.py
    to keep both files under the project's 400-line-per-new-file limit.
BUSINESS CONTEXT: See check_identifier_uniqueness.py's module docstring for
    the full GE-122 rationale. This module owns the actual filesystem I/O:
    every *.yaml / *.md file encountered increments inspected_count during
    the walk itself, before any attempt to parse it, so the count reflects
    what was actually inspected rather than what happened to parse cleanly.
ARCHITECTURE: Two walk shapes, both non-git, pure filesystem:
      - acceptance-criteria: recursive walk of docs/acceptance-criteria/**/*.yaml,
        keyed on each record's top-level ``id`` field (PyYAML with a minimal
        fallback parser when PyYAML is unavailable).
      - decisions / diagrams: flat (non-recursive) walk of *.md files, keyed
        on a number captured from the filename via a compiled regex.
    Each per-file read failure (unreadable, unparsable, non-matching
    filename) is fail-open at the file level: it still counts toward
    inspected_count but contributes no claim, since a file whose number
    cannot be determined cannot be said to have claimed one.

DOC_LINKS:
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122a-1.yaml

DECISION HISTORY:
  - 2026-08-18 [python-coder/GE-122a-1]: Extracted from check_identifier_uniqueness.py
    to keep both that module and this one under the 400-line new-file limit
    (check-file-size pre-commit hook).
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable
from pathlib import Path

from _uniqueness_types import Finding, NamespaceVerdict  # type: ignore[import]

try:
    import yaml  # type: ignore[import]

    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


_HOOK_PREFIX = "[check_identifier_uniqueness]"

_ADR_FILENAME_RE = re.compile(r"^ADR-(\d+)-.*\.md$", re.IGNORECASE)
_DIAGRAM_FILENAME_RE = re.compile(r"^c(\d+)-(\d+)-.*\.md$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# YAML loading (soft dependency on PyYAML; minimal fallback for id-only reads)
# ---------------------------------------------------------------------------


def _parse_yaml_minimal(content: str) -> dict | None:
    """Parse only top-level scalar ``key: value`` lines from a YAML string.

    Used when PyYAML is unavailable. Sufficient for extracting a record's
    top-level ``id`` field, which is all this pass needs from an AC file.

    Args:
        content: Raw YAML text.

    Returns:
        A dict of top-level scalar fields, or None if none were found.
    """
    result: dict = {}
    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith("#") or line[0:1] in (" ", "\t"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip().strip("'\"")
    return result or None


def _parse_yaml_dict(content: str, source_label: Path) -> dict | None:
    """Parse a YAML string into a dict, preferring PyYAML with a minimal fallback.

    Args:
        content: Raw YAML text read from source_label.
        source_label: Path used in warning messages on parse failure.

    Returns:
        The parsed dict, or None on parse failure or non-dict content.
    """
    if not _YAML_AVAILABLE:
        return _parse_yaml_minimal(content)
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: YAML parse error in {source_label}: {exc}",
            file=sys.stderr,
        )
        return None
    return data if isinstance(data, dict) else None


def _read_yaml_id(yaml_path: Path) -> str | None:
    """Read one AC YAML file from disk and return its top-level ``id`` field.

    Fails open per file: an unreadable or unparsable file contributes to the
    namespace's inspected_count (tracked by the caller during the walk) but
    makes no claim, since a file whose id cannot be determined cannot be said
    to have claimed a number.

    Args:
        yaml_path: Path to the .yaml file to read.

    Returns:
        The non-empty ``id`` field value as a string, or None.
    """
    try:
        content = yaml_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: cannot read {yaml_path}: {exc}",
            file=sys.stderr,
        )
        return None

    data = _parse_yaml_dict(content, yaml_path)
    if data is None:
        return None
    record_id = str(data.get("id", "")).strip()
    return record_id or None


# ---------------------------------------------------------------------------
# Namespace verdict assembly
# ---------------------------------------------------------------------------


def _build_namespace_verdict(
    claims: dict[str, list[Path]],
    inspected_count: int,
) -> NamespaceVerdict:
    """Turn a number->claimant-paths map into a NamespaceVerdict.

    A number is only reported when two or more artifacts claim it -- grouping
    by contested number (not by claimant file) is what keeps the finding
    count at "one per collision" rather than "one per file in a collision".

    Args:
        claims: Mapping of claimed number to the list of paths that claim it.
        inspected_count: Total artifacts walked in this namespace.

    Returns:
        The assembled NamespaceVerdict.
    """
    findings = [
        Finding(number=number, paths=[str(p) for p in paths])
        for number, paths in sorted(claims.items())
        if len(paths) > 1
    ]
    return NamespaceVerdict(
        passed=not findings,
        inspected_count=inspected_count,
        findings=findings,
    )


# ---------------------------------------------------------------------------
# Per-namespace directory walks
# ---------------------------------------------------------------------------


def scan_acceptance_criteria(ac_root: Path) -> NamespaceVerdict:
    """Walk the acceptance-criteria namespace and detect id collisions.

    Recursively walks every *.yaml file under ac_root, mirroring the real
    store's component/goal-folder shape. Every file encountered counts
    toward inspected_count regardless of whether it parses.

    Args:
        ac_root: Path to the docs/acceptance-criteria/ directory.

    Returns:
        The NamespaceVerdict for the acceptance-criteria namespace.
    """
    if not ac_root.is_dir():
        return NamespaceVerdict(passed=True, inspected_count=0, findings=[])

    claims: dict[str, list[Path]] = {}
    inspected_count = 0
    for yaml_path in sorted(ac_root.rglob("*.yaml")):
        inspected_count += 1
        record_id = _read_yaml_id(yaml_path)
        if record_id is None:
            continue
        claims.setdefault(record_id, []).append(yaml_path)

    return _build_namespace_verdict(claims, inspected_count)


def _scan_filename_numbered(
    directory: Path,
    pattern: re.Pattern[str],
    number_of: Callable[[re.Match[str]], str],
) -> NamespaceVerdict:
    """Scan a flat directory of *.md files whose filenames encode a number.

    Non-recursive by design: both docs/architecture/adrs/ and
    docs/architecture/diagrams/ are flat namespaces in this store. Every
    *.md file counts toward inspected_count regardless of whether its
    filename matches pattern.

    Args:
        directory: Directory to scan for *.md files.
        pattern: Compiled regex matched against each filename.
        number_of: Callable taking a regex Match and returning the
            contested-number string for that filename.

    Returns:
        The NamespaceVerdict for the namespace rooted at directory.
    """
    if not directory.is_dir():
        return NamespaceVerdict(passed=True, inspected_count=0, findings=[])

    claims: dict[str, list[Path]] = {}
    inspected_count = 0
    for md_path in sorted(directory.glob("*.md")):
        inspected_count += 1
        match = pattern.match(md_path.name)
        if match is None:
            continue
        claims.setdefault(number_of(match), []).append(md_path)

    return _build_namespace_verdict(claims, inspected_count)


def scan_decisions(adr_root: Path) -> NamespaceVerdict:
    """Walk the decisions namespace and detect ADR integer collisions.

    Args:
        adr_root: Path to the docs/architecture/adrs/ directory.

    Returns:
        The NamespaceVerdict for the decisions namespace.
    """
    return _scan_filename_numbered(adr_root, _ADR_FILENAME_RE, lambda m: m.group(1))


def scan_diagrams(diagram_root: Path) -> NamespaceVerdict:
    """Walk the diagrams namespace and detect level-and-sequence collisions.

    Args:
        diagram_root: Path to the docs/architecture/diagrams/ directory.

    Returns:
        The NamespaceVerdict for the diagrams namespace.
    """
    return _scan_filename_numbered(
        diagram_root,
        _DIAGRAM_FILENAME_RE,
        lambda m: f"c{m.group(1)}-{m.group(2)}",
    )
