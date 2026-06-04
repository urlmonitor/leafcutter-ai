"""
MODULE: check_v2_ac_store_alignment
GOAL: Pre-commit hook that verifies every inline AC store reference
    (implements/amends/introduces AC-XX-NNN) in a staged ticket body resolves
    to an active YAML file in docs/acceptance-criteria/.
BUSINESS CONTEXT: Enforces Option B (blocking) enforcement for the AC store
    cross-check. Tickets in the v2 pipeline reference specific AC IDs from the
    store. This hook ensures those references are valid at commit time —
    catching stale, missing, or deprecated AC links before they reach the
    repository. Completes the traceability triangle: ticket -> AC -> test.
ARCHITECTURE: Pure stdlib (re, pathlib, argparse, sys). No third-party
    dependencies. Accepts --ticket <path> for single-file invocation (used by
    ac-validator) and reads staged files from `git diff --cached` when no
    --ticket argument is given. AC store directory defaults to
    docs/acceptance-criteria/ relative to the repo root. Override via
    --ac-store for testing. Exits 1 with per-ID error lines when any
    referenced AC is missing or non-active; exits 0 silently when clean,
    no references found, or AC store absent.

Exit Codes:
    0 — All AC references resolve to active entries, or no references present,
        or the AC store does not exist.
    1 — One or more AC references are invalid (missing file or non-active status).
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Pattern: "implements AC-FIN-001", "amends AC-AUTH-007", "introduces AC-FIN-002"
# Captures only the ID portion (e.g. "FIN-001").
_AC_REF_REGEX = re.compile(
    r"(?:implements|amends|introduces)\s+AC-([A-Z]{2,6}-[0-9]{3,})"
)

# Minimal YAML field extractor — avoids a PyYAML dependency.
_STATUS_REGEX = re.compile(r"^\s*status:\s*(\S+)\s*$", re.MULTILINE)

# Default path segment, relative to the repo root.
_DEFAULT_AC_DIR = "docs/acceptance-criteria"


# ---------------------------------------------------------------------------
# Prefix map loader
# ---------------------------------------------------------------------------


def load_prefix_map(ac_dir: str) -> dict:
    """Build a mapping of {prefix: component_id} from index.yaml.

    Reads ``<ac_dir>/index.yaml`` and parses the ``components:`` list.  When
    the file is absent or the key is missing, returns an empty dict so callers
    can degrade gracefully.

    Args:
        ac_dir: Path to the acceptance-criteria root directory.

    Returns:
        Dict mapping uppercase prefix strings to component id strings,
        e.g. ``{"FIN": "finalize", "AUTH": "auth"}``.
    """
    index_path = Path(ac_dir) / "index.yaml"
    if not index_path.exists():
        return {}

    try:
        content = index_path.read_text(encoding="utf-8")
    except OSError:
        return {}

    prefix_map: dict = {}
    # Parse simple YAML list entries of the form:
    #   - id: finalize
    #     prefix: FIN
    # We walk the lines looking for "- id:" and "prefix:" pairs.
    current_id: str | None = None
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("- id:"):
            current_id = stripped.split(":", 1)[1].strip()
        elif stripped.startswith("prefix:") and current_id is not None:
            prefix = stripped.split(":", 1)[1].strip()
            prefix_map[prefix] = current_id
            current_id = None

    return prefix_map


# ---------------------------------------------------------------------------
# Reference extractor
# ---------------------------------------------------------------------------


def extract_ac_references(ticket_text: str) -> List[str]:
    """Return all AC IDs referenced in ticket_text.

    Scans for the pattern ``(implements|amends|introduces) AC-XX-NNN``
    and returns the ID portion (e.g. ``"FIN-001"``) for each match.
    Duplicate IDs are preserved in document order (deduplication is the
    caller's responsibility if desired).

    Args:
        ticket_text: Raw markdown text of the ticket body.

    Returns:
        List of AC ID strings in document order.
    """
    return _AC_REF_REGEX.findall(ticket_text)


# ---------------------------------------------------------------------------
# AC existence and status checker
# ---------------------------------------------------------------------------


def check_ac_exists_and_active(
    ac_dir: str,
    prefix_map: dict,
    ac_id: str,
) -> Tuple[bool, str]:
    """Check whether ac_id resolves to an active YAML file in ac_dir.

    Resolution steps:
    1. Split ac_id on the last '-' group to extract the prefix
       (e.g. ``"FIN"`` from ``"FIN-001"``).
    2. Look up the component directory from prefix_map.
    3. Check the file exists at ``<ac_dir>/<component>/<ac_id>.yaml``.
    4. Read the file and verify ``status: active``.

    Args:
        ac_dir: Path to the acceptance-criteria root directory.
        prefix_map: Mapping of ``{prefix: component_id}`` from load_prefix_map.
        ac_id: The AC identifier string (e.g. ``"FIN-001"``).

    Returns:
        Tuple ``(ok, error_message)`` where ``ok`` is True when the AC is
        active and exists, and ``error_message`` is an empty string on
        success or a descriptive ERROR line on failure.
    """
    # Extract the prefix — the uppercase letter part before the first digit run.
    # e.g. "FIN-001" -> prefix = "FIN", "AUTH-007" -> prefix = "AUTH"
    dash_idx = ac_id.rfind("-")
    if dash_idx == -1:
        return False, f"ERROR: AC {ac_id} has an unrecognised ID format"
    prefix = ac_id[:dash_idx]

    if prefix not in prefix_map:
        return (
            False,
            (
                f"ERROR: prefix {prefix} has no registered component "
                f"in docs/acceptance-criteria/index.yaml"
            ),
        )

    component = prefix_map[prefix]
    ac_file = Path(ac_dir) / component / f"{ac_id}.yaml"

    if not ac_file.exists():
        return (
            False,
            (
                f"ERROR: AC {ac_id} referenced in ticket but not found in "
                f"docs/acceptance-criteria/{component}/{ac_id}.yaml"
            ),
        )

    try:
        content = ac_file.read_text(encoding="utf-8")
    except OSError as exc:
        return (
            False,
            f"ERROR: AC {ac_id} — cannot read {ac_file}: {exc}",
        )

    status_match = _STATUS_REGEX.search(content)
    if not status_match:
        return (
            False,
            f"ERROR: AC {ac_id} has no 'status:' field in {ac_file}",
        )

    status = status_match.group(1).lower()
    if status != "active":
        return (
            False,
            (
                f"ERROR: AC {ac_id} referenced in ticket has status: {status} "
                f"(expected: active)"
            ),
        )

    return True, ""


# ---------------------------------------------------------------------------
# Staged file discovery
# ---------------------------------------------------------------------------


def _get_staged_ticket_files(repo_root: Path) -> List[str]:
    """Return a list of staged ticket file paths matching tickets/**/*.md.

    Runs ``git diff --cached --name-only`` and filters paths that start with
    ``tickets/`` and end with ``.md``.  Paths are returned relative to
    repo_root; callers must join with repo_root to get absolute paths.

    Args:
        repo_root: The repository root directory.

    Returns:
        List of relative path strings for staged ticket markdown files.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            cwd=str(repo_root),
        )
        if result.returncode != 0:
            return []
        lines = result.stdout.strip().splitlines()
        return [
            line for line in lines
            if line.startswith("tickets/") and line.endswith(".md")
        ]
    except FileNotFoundError:
        # git not found — graceful degradation
        return []


# ---------------------------------------------------------------------------
# Core check logic
# ---------------------------------------------------------------------------


def check_ticket(
    ticket_path: str,
    ac_dir: str,
) -> List[str]:
    """Check one ticket file and return a list of error lines.

    Returns an empty list when all references resolve, or when no references
    are present.  Returns one ERROR line per invalid reference on failure.

    Args:
        ticket_path: Absolute or relative path to the ticket markdown file.
        ac_dir: Path to the acceptance-criteria root directory.

    Returns:
        List of error strings.  Empty list means the ticket is clean.
    """
    ac_path = Path(ac_dir)

    # Graceful degradation: AC store absent -> no-op.
    if not ac_path.is_dir():
        return []

    try:
        text = Path(ticket_path).read_text(encoding="utf-8")
    except OSError as exc:
        return [f"ERROR: cannot read ticket file {ticket_path}: {exc}"]

    refs = extract_ac_references(text)
    if not refs:
        return []

    prefix_map = load_prefix_map(ac_dir)
    errors: List[str] = []
    for ac_id in refs:
        ok, error_msg = check_ac_exists_and_active(ac_dir, prefix_map, ac_id)
        if not ok:
            errors.append(error_msg)

    return errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    """Return a best-effort repo root path.

    Uses this script's location (templates/commit-guardian/) and ascends two
    levels to reach the repo root.  Falls back to the current working directory
    when the layout does not match.

    Returns:
        Absolute Path to the inferred repo root.
    """
    script_dir = Path(__file__).resolve().parent
    candidate = script_dir.parent.parent
    if (candidate / ".git").exists() or (candidate / "templates").is_dir():
        return candidate
    return Path(os.getcwd())


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        Configured ArgumentParser.
    """
    parser = argparse.ArgumentParser(
        prog="check_v2_ac_store_alignment",
        description=(
            "Pre-commit hook: verify that every implements/amends/introduces "
            "AC-XX-NNN reference in a staged ticket body resolves to an active "
            "YAML entry in docs/acceptance-criteria/."
        ),
    )
    parser.add_argument(
        "--ticket",
        default=None,
        metavar="PATH",
        help=(
            "Check a single ticket file instead of reading staged files from git. "
            "Used by ac-validator for per-ticket invocation."
        ),
    )
    parser.add_argument(
        "--ac-store",
        default=None,
        metavar="DIR",
        help=(
            "Override the acceptance-criteria directory path. "
            "Defaults to docs/acceptance-criteria/ relative to the repo root."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the pre-commit hook.

    Args:
        argv: CLI argument list.  When ``None``, uses ``sys.argv[1:]``.

    Returns:
        Exit code: 0 on clean, 1 on validation failures.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    repo_root = _repo_root()
    ac_dir = args.ac_store if args.ac_store else str(repo_root / _DEFAULT_AC_DIR)

    # Collect ticket files to check.
    if args.ticket:
        ticket_files = [args.ticket]
    else:
        relative_paths = _get_staged_ticket_files(repo_root)
        ticket_files = [str(repo_root / p) for p in relative_paths]

    if not ticket_files:
        return 0

    all_errors: List[str] = []
    for ticket_path in ticket_files:
        errors = check_ticket(ticket_path, ac_dir)
        all_errors.extend(errors)

    if all_errors:
        for err in all_errors:
            print(err)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-04 [TICKET-20260604-ACStoreInlineAlignmentHook]: Initial implementation.
  Pre-commit hook that extracts implements/amends/introduces AC-XX-NNN references
  from staged ticket bodies and verifies each resolves to an active YAML file in
  docs/acceptance-criteria/<component>/<id>.yaml. Prefix-to-directory resolution
  via docs/acceptance-criteria/index.yaml. Accepts --ticket for ac-validator
  invocation and --ac-store for test isolation. Gracefully degrades when AC store
  absent (exit 0). Exits 1 with per-ID ERROR lines on any invalid reference.
  Stdlib only (re, pathlib, argparse, subprocess). No third-party dependencies.
====================================================================
"""
