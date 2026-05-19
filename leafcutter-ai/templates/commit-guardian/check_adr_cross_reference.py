"""
Pre-commit hook: ADR cross-reference validator.

MODULE: check_adr_cross_reference
GOAL: For every staged ADR, verify that each component listed in its
      frontmatter's components: array has a back-link from its detail_ref doc
      (or components.json related_docs / body text) mentioning the ADR.
BUSINESS CONTEXT: ADRs and the component registry are currently disconnected —
      a reader looking at a component has no path to the ADRs that constrain it.
      This hook makes the back-link a commit-time requirement (warn-only by
      default; flip --strict to block after backfill is complete).
ARCHITECTURE: Not needed.

Logic:
    1. Collect staged ADR files (^docs/architecture/adrs/ADR-*.md) and
       staged detail_ref docs (any docs/ markdown file).
    2. For each staged ADR:
       a. Parse components: from frontmatter.
       b. For each component, look up detail_ref in docs/components.json.
       c. If no detail_ref: warn/block (component lacks back-link source).
       d. If detail_ref exists but the referenced doc does not mention the
          ADR filename (without extension): warn/block.
    3. For each staged detail_ref doc:
       a. Find all ADRs that list this component.
       b. Verify each such ADR is mentioned in the doc.
       c. This catches the reverse: someone removes an ADR mention from a doc.

Match strategy for "mentions ADR":
    - Search for the ADR basename (e.g. "ADR-007-features-complete-catalog")
      in both frontmatter related_docs/related_code values and body text.
    - Case-insensitive substring match is intentional — links may be relative
      or absolute, with or without ".md".

Exit codes:
    0 - All staged files pass (or --strict=False and only warnings exist)
    1 - Blocking violations found (only in --strict=True mode)

Usage:
    python scripts/commit_guardian/check_adr_cross_reference.py
    python scripts/commit_guardian/check_adr_cross_reference.py --strict

DOC_LINKS: None
DECISION HISTORY:
  - 2026-05-12 00:00 [Agent]: Created ADR cross-reference validator in warn-only
    mode (EPIC-ArchitectureDocs ticket 23). Starts warn-only (--strict=False) to
    surface existing drift; flip to --strict after backfill closes.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPONENTS_JSON_PATH = REPO_ROOT / "docs" / "components.json"
ADR_DIR_REL = "docs/architecture/adrs"
ADR_PATTERN = re.compile(r"^docs/architecture/adrs/ADR-\d+.*\.md$", re.IGNORECASE)

# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _get_staged_files() -> list[str]:
    """Return relative paths of all staged (non-deleted) files.

    Returns:
        List of staged file paths relative to repo root.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-status"],
        capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        return []
    files = []
    for line in result.stdout.strip().splitlines():
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2 and not parts[0].startswith("D"):
            files.append(parts[-1])
    return files


# ---------------------------------------------------------------------------
# Frontmatter helpers
# ---------------------------------------------------------------------------


def _extract_frontmatter(path: Path) -> dict:
    """Parse YAML frontmatter from a markdown file.

    Args:
        path: Absolute path to a markdown file.

    Returns:
        Parsed frontmatter dict; empty dict on error or missing frontmatter.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end == -1:
        return {}
    try:
        fm = yaml.safe_load(text[3:end])
        return fm if isinstance(fm, dict) else {}
    except yaml.YAMLError:
        return {}


def _get_file_content(path: Path) -> str:
    """Return the full text content of a file, empty string on error.

    Args:
        path: Absolute path to a file.

    Returns:
        File content string or empty string if the file cannot be read.
    """
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


# ---------------------------------------------------------------------------
# Component registry
# ---------------------------------------------------------------------------


def _load_components(components_json: Path) -> dict[str, dict]:
    """Load components dict from components.json.

    Args:
        components_json: Path to docs/components.json.

    Returns:
        Dict mapping component_id -> component data dict.
    """
    if not components_json.exists():
        return {}
    try:
        with open(components_json, encoding="utf-8") as fh:
            data = json.load(fh)
        value = data.get("components", {})
        if isinstance(value, dict):
            return value
        if isinstance(value, list):
            return {c["id"]: c for c in value if isinstance(c, dict) and "id" in c}
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return {}


# ---------------------------------------------------------------------------
# Cross-reference check
# ---------------------------------------------------------------------------


def _adr_basename(adr_path: str | Path) -> str:
    """Return the ADR filename without extension (e.g. ADR-007-features-complete-catalog).

    Args:
        adr_path: Path to or name of the ADR file.

    Returns:
        Filename stem string.
    """
    return Path(adr_path).stem


def _doc_mentions_adr(doc_path: Path, adr_stem: str) -> bool:
    """Return True if the doc file mentions the ADR by its stem anywhere.

    Checks frontmatter values (related_docs, related_code) and body text.
    Case-insensitive, substring match.

    Args:
        doc_path: Absolute path to the documentation file to search.
        adr_stem: ADR filename without extension (e.g. "ADR-007-features-catalog").

    Returns:
        True if the stem appears in the file content.
    """
    content = _get_file_content(doc_path)
    return adr_stem.lower() in content.lower()


def check_adr(
    adr_rel_path: str,
    components: dict[str, dict],
    strict: bool,
) -> list[tuple[str, str]]:
    """Check a single ADR's component back-link coverage.

    For each component in the ADR's frontmatter, verifies that:
    1. The component has a detail_ref in components.json.
    2. The detail_ref doc mentions this ADR.

    Args:
        adr_rel_path: Relative path to the ADR file (from repo root).
        components: Components registry dict from components.json.
        strict: If True findings are blocking; if False they are warnings.

    Returns:
        List of (severity, message) tuples.
        severity is "ERROR" (blocking) or "WARNING" (warn-only).
    """
    findings: list[tuple[str, str]] = []
    severity = "ERROR" if strict else "WARNING"

    adr_path = REPO_ROOT / adr_rel_path
    fm = _extract_frontmatter(adr_path)
    if not fm:
        return []  # No frontmatter — nothing to check

    adr_components = fm.get("components", [])
    if not adr_components:
        return []  # ADR has no components listed

    adr_stem = _adr_basename(adr_rel_path)

    for component_id in adr_components:
        if not isinstance(component_id, str):
            continue

        component_data = components.get(component_id)
        if component_data is None:
            # Component not in registry — let check_doc_frontmatter handle this
            continue

        detail_ref = component_data.get("detail_ref")
        if not detail_ref:
            findings.append((
                severity,
                f"{adr_rel_path}: component '{component_id}' has no detail_ref in "
                f"components.json — cannot verify ADR back-link.\n"
                f"  FIX: Add detail_ref to docs/components.json for '{component_id}' "
                f"and ensure that doc mentions '{adr_stem}'."
            ))
            continue

        detail_ref_path = REPO_ROOT / detail_ref
        if not detail_ref_path.exists():
            findings.append((
                severity,
                f"{adr_rel_path}: detail_ref '{detail_ref}' for component "
                f"'{component_id}' does not exist on disk.\n"
                f"  FIX: Create '{detail_ref}' or correct the path in "
                f"docs/components.json."
            ))
            continue

        if not _doc_mentions_adr(detail_ref_path, adr_stem):
            findings.append((
                severity,
                f"{adr_rel_path}: no back-link found in detail_ref doc "
                f"'{detail_ref}' for component '{component_id}'.\n"
                f"  FIX: Add '{adr_stem}' to the related_docs field or body of "
                f"'{detail_ref}'."
            ))

    return findings


def check_detail_ref_doc(
    doc_rel_path: str,
    all_adrs: dict[str, list[str]],
    strict: bool,
) -> list[tuple[str, str]]:
    """Check that a detail_ref doc still mentions all ADRs it should.

    This catches the case where an ADR mention is removed from a detail_ref doc.

    Args:
        doc_rel_path: Relative path to the doc file (from repo root).
        all_adrs: Dict mapping ADR path -> list of component IDs in that ADR.
        strict: If True findings are blocking; if False they are warnings.

    Returns:
        List of (severity, message) tuples.
    """
    findings: list[tuple[str, str]] = []
    severity = "ERROR" if strict else "WARNING"

    doc_path = REPO_ROOT / doc_rel_path

    for adr_rel_path, adr_component_ids in all_adrs.items():
        adr_path = REPO_ROOT / adr_rel_path
        fm = _extract_frontmatter(adr_path)
        if not fm:
            continue

        adr_components = fm.get("components", [])
        # Check if this doc is the detail_ref for any component listed in this ADR
        components = _load_components(COMPONENTS_JSON_PATH)
        for component_id in adr_components:
            if not isinstance(component_id, str):
                continue
            comp_data = components.get(component_id, {})
            detail_ref = comp_data.get("detail_ref", "")
            if not detail_ref:
                continue
            # Normalize paths for comparison
            if Path(detail_ref) == Path(doc_rel_path):
                adr_stem = _adr_basename(adr_rel_path)
                if not _doc_mentions_adr(doc_path, adr_stem):
                    findings.append((
                        severity,
                        f"{doc_rel_path}: removed mention of '{adr_stem}' "
                        f"(ADR requires back-link from component '{component_id}').\n"
                        f"  FIX: Add '{adr_stem}' back to the related_docs or body of "
                        f"'{doc_rel_path}'."
                    ))

    return findings


# ---------------------------------------------------------------------------
# ADR index builder
# ---------------------------------------------------------------------------


def _build_adr_index() -> dict[str, list[str]]:
    """Scan all existing ADRs and build an index of adr_path -> component_ids.

    Returns:
        Dict mapping ADR relative path -> list of component ID strings.
    """
    adr_dir = REPO_ROOT / ADR_DIR_REL
    index: dict[str, list[str]] = {}
    if not adr_dir.exists():
        return index
    for adr_file in adr_dir.glob("ADR-*.md"):
        rel = adr_file.relative_to(REPO_ROOT).as_posix()
        fm = _extract_frontmatter(adr_file)
        components_list = fm.get("components", [])
        if isinstance(components_list, list):
            index[rel] = [c for c in components_list if isinstance(c, str)]
    return index


# ---------------------------------------------------------------------------
# stdout helper
# ---------------------------------------------------------------------------


def _configure_stdout() -> None:
    """Ensure stdout uses UTF-8 on Windows.

    Returns:
        None.
    """
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except AttributeError:
            pass


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def _collect_findings(
    staged_adrs: list[str],
    staged_docs: list[str],
    components: dict[str, dict],
    adr_index: dict[str, list[str]],
    strict: bool,
) -> list[tuple[str, str]]:
    """Collect all cross-reference findings for staged files.

    Args:
        staged_adrs: List of staged ADR relative paths.
        staged_docs: List of staged docs/ relative paths (non-ADR).
        components: Components registry dict.
        adr_index: Dict mapping ADR path -> component IDs.
        strict: If True, findings use "ERROR" severity.

    Returns:
        List of (severity, message) tuples from all checks.
    """
    findings: list[tuple[str, str]] = []
    for adr_rel in staged_adrs:
        findings.extend(check_adr(adr_rel, components, strict))
    for doc_rel in staged_docs:
        findings.extend(check_detail_ref_doc(doc_rel, adr_index, strict))
    return findings


def _report_findings(
    findings: list[tuple[str, str]],
    strict: bool,
) -> int:
    """Print findings and return the appropriate exit code.

    Args:
        findings: List of (severity, message) tuples.
        strict: If True, errors cause a non-zero return code.

    Returns:
        0 if no errors (or warn-only mode), 1 if errors in strict mode.
    """
    if not findings:
        return 0

    errors = [f for f in findings if f[0] == "ERROR"]
    warnings = [f for f in findings if f[0] == "WARNING"]

    if warnings:
        print("\n⚠️  ADR Cross-Reference Warnings:\n", file=sys.stderr)
        for _, msg in warnings:
            print(f"  ⚠️  {msg}\n", file=sys.stderr)

    if errors:
        print("\n🔗 ADR Cross-Reference Check Failed\n", file=sys.stderr)
        for _, msg in errors:
            print(f"  ❌ {msg}\n", file=sys.stderr)
        return 1

    if warnings and not strict:
        print(
            "\n  [adr-cross-reference] Running in warn-only mode (--strict not set).\n"
            "  Warnings will become blocking after the ADR back-link backfill closes.",
            file=sys.stderr,
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    """Run the ADR cross-reference check against all staged files.

    Args:
        argv: Argument list (defaults to sys.argv[1:] when None).

    Returns:
        Exit code: 0 on success, 1 if --strict and blocking violations found.
    """
    _configure_stdout()

    parser = argparse.ArgumentParser(description="ADR cross-reference validator.")
    parser.add_argument(
        "--strict",
        action="store_true",
        default=False,
        help="Block commits on violations (default: warn-only).",
    )
    args = parser.parse_args(argv)
    strict: bool = args.strict

    staged = _get_staged_files()
    if not staged:
        return 0

    staged_adrs = [f for f in staged if ADR_PATTERN.match(f)]
    staged_docs = [
        f for f in staged
        if f.endswith(".md") and f.startswith("docs/") and not ADR_PATTERN.match(f)
    ]

    if not staged_adrs and not staged_docs:
        return 0

    components = _load_components(COMPONENTS_JSON_PATH)
    adr_index = _build_adr_index()
    findings = _collect_findings(staged_adrs, staged_docs, components, adr_index, strict)
    return _report_findings(findings, strict)


if __name__ == "__main__":
    sys.exit(main())
