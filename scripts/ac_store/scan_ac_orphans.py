#!/usr/bin/env python3
"""
MODULE: scan_ac_orphans
GOAL: Two related AC-store integrity scans:

  1. Parent-child link scan: detect child AC YAML files whose parent's
     covered_by field does not include them (original purpose — ACS-100i-4).

  2. Draft-orphan scan (AC BO-1500b-3): detect uncommitted AC YAML files left
     over from a prior crashed /create-ac session inside the dedicated authoring
     worktree.  This scan is the partial-run recovery pre-flight referenced in
     templates/skills/create-ac/SKILL.md §PRR.2.

BUSINESS CONTEXT: The AC store enforces a bidirectional parent-child link: when
    a child AC exists on disk, the parent's covered_by field must list that child.
    Pre-commit hooks (check_ac_parent_covered_by.py) enforce this at commit time,
    but they only catch freshly staged files. This scan catches existing orphans
    that pre-date the hook or slipped through during manual edits. Running it as
    part of a CI gate or an ad-hoc operator command closes the gap. The scan
    reuses derive_parent_id() from ac_parent_id.py so the parent-derivation
    logic is never duplicated.

    The draft-orphan scan (mode: draft-orphans) supports the partial-run
    recovery pre-flight in the /create-ac workflow (AC BO-1500b-3).  It uses
    `git status --porcelain` scoped to the authoring worktree so only
    uncommitted working-tree changes are reported; AC files already committed
    on the authoring branch are naturally excluded because committed files do
    not appear in `git status` output.  The scan qualifies candidates by
    origin_agent and readiness: draft to avoid false positives from unrelated
    YAML files.

ARCHITECTURE: Pure-stdlib with optional PyYAML. Walks docs/acceptance-criteria/
    recursively, loads all .yaml files, builds an in-memory id→record index, then
    for every non-root AC checks whether its structural parent's covered_by list
    includes it. Reports grouped by parent. Exits 0 when no orphans are found,
    exits 1 when one or more orphans are found, exits 2 on a YAML load error.

    For draft-orphan mode: runs `git -C <worktree> status --porcelain` on the
    authoring worktree, qualifies each YAML file, then emits a JSON array of
    orphaned draft AC descriptors to stdout.

DOC_LINKS:
  - docs/reference/ac-schema.md
  - docs/architecture/adrs/ADR-008-ac-store-schema-id-format-enforcement.md
  - templates/skills/create-ac/SKILL.md

DECISION HISTORY:
  - 2026-06-24 [llm-expert/BO-1500b-3]: Added draft-orphan scan mode.
    New public function scan_draft_orphans_in_worktree() implements the
    partial-run recovery pre-flight detection described in §PRR.2 of
    templates/skills/create-ac/SKILL.md. Uses `git -C <worktree> status
    --porcelain` scoped to the AC store directory so only uncommitted
    working-tree files are reported; already-committed AC files on the
    authoring branch are excluded naturally by git status semantics.
    Qualifies candidates by origin_agent in {product-owner,
    business-analyst, it-po} and readiness == "draft".  New CLI
    subcommand `draft-orphans --worktree <path> [--ac-root <rel-path>]`
    emits a JSON array of {file_path, ac_id} objects to stdout.
    (#EPIC-SafeAcAuthoring/08)
  - 2026-06-08 [python-coder/ACS-100i-4]: Created scan_ac_orphans.py.
    Implements ACS-100i-4: store-wide scan that detects and reports orphaned
    child ACs (children whose parent covered_by omits them). Reuses
    derive_parent_id() from ac_parent_id.py. Exits 0 (clean), 1 (orphans found),
    or 2 (YAML load error). Groups orphans by parent in human-readable output.
    (#EPIC-AcParentChildLinkEnforcement/04)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore[import]
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_AC_ROOT = "docs/acceptance-criteria"

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------

AcRecord = dict[str, Any]


# ---------------------------------------------------------------------------
# Worktree root detection
# ---------------------------------------------------------------------------


def _find_worktree_root(start: Path) -> Path:
    """Walk up from *start* until a directory containing a .git file/dir is found.

    Args:
        start: Starting path for the upward search.

    Returns:
        The worktree root path.

    Raises:
        FileNotFoundError: When no .git marker is found before the filesystem root.
    """
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    raise FileNotFoundError(  # noqa: TRY003
        f"Could not locate worktree root from {start}"
    )


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------


def _load_ac(path: Path) -> AcRecord | None:
    """Load and return a single AC YAML file.

    Args:
        path: Absolute path to the YAML file.

    Returns:
        Parsed AC dict on success, None on parse or I/O failure (error to stderr).
    """
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"ERROR: {path}: could not read file: {exc}", file=sys.stderr)
        return None

    if _YAML_AVAILABLE:
        try:
            data = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            print(f"ERROR: {path}: YAML parse error: {exc}", file=sys.stderr)
            return None
        if not isinstance(data, dict):
            print(
                f"ERROR: {path}: expected a YAML mapping, got {type(data).__name__}",
                file=sys.stderr,
            )
            return None
    else:
        # Minimal fallback: parse top-level scalars only.
        data = {}
        for raw_line in content.splitlines():
            line = raw_line.rstrip()
            if not line or line.startswith("#") or line[:1] in (" ", "\t"):
                continue
            if ":" in line:
                key, _, value = line.partition(":")
                data[key.strip()] = value.strip()

    data["_path"] = str(path)
    return data


def _extract_covered_by(data: AcRecord) -> list[str]:
    """Extract the covered_by list from a parsed AC YAML dict.

    Handles PyYAML list, empty list, and the minimal-fallback string form.

    Args:
        data: Parsed YAML dict from an AC file.

    Returns:
        List of child AC ID strings. Empty list when covered_by is absent or empty.
    """
    raw = data.get("covered_by")
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if item is not None and str(item).strip()]
    if isinstance(raw, str):
        stripped = raw.strip()
        if stripped in ("[]", ""):
            return []
        stripped = stripped.strip("[]")
        return [item.strip() for item in stripped.split(",") if item.strip()]
    return []


# ---------------------------------------------------------------------------
# derive_parent_id import (graceful fallback)
# ---------------------------------------------------------------------------


def _get_derive_parent_id():
    """Import and return the derive_parent_id function.

    Attempts three strategies:
    1. Standard package import.
    2. Locate ac_parent_id.py relative to this script's location.
    3. Locate ac_parent_id.py relative to the project root.

    Returns:
        The derive_parent_id callable.

    Raises:
        ImportError: When the module cannot be found by any strategy.
    """
    try:
        from scripts.ac_store.ac_parent_id import derive_parent_id  # type: ignore[import]
    except ImportError:
        pass
    else:
        return derive_parent_id

    import importlib.util

    def _load_from_path(module_path: Path):
        """Load derive_parent_id from an explicit path.

        Args:
            module_path: Absolute path to ac_parent_id.py.

        Returns:
            The derive_parent_id callable, or None on failure.
        """
        spec = importlib.util.spec_from_file_location("ac_parent_id", str(module_path))
        if spec is None or spec.loader is None:
            return None
        try:
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)  # type: ignore[union-attr]
        except (ImportError, AttributeError, OSError) as exc:
            print(
                f"[scan_ac_orphans] WARNING: could not load ac_parent_id from {module_path}: {exc}",
                file=sys.stderr,
            )
            return None
        else:
            return mod.derive_parent_id

    # Strategy 2: relative to this script.
    script_dir = Path(__file__).resolve().parent
    candidate = script_dir / "ac_parent_id.py"
    if candidate.exists():
        fn = _load_from_path(candidate)
        if fn is not None:
            return fn

    # Strategy 3: project root walk.
    for ancestor in [Path.cwd(), *Path.cwd().parents]:
        if (ancestor / ".git").exists() or (ancestor / "CLAUDE.md").exists():
            candidate3 = ancestor / "scripts" / "ac_store" / "ac_parent_id.py"
            if candidate3.exists():
                fn = _load_from_path(candidate3)
                if fn is not None:
                    return fn
            break

    msg = "ac_parent_id.py not found via package import, script-relative, or project-root walk."
    raise ImportError(msg)


# ---------------------------------------------------------------------------
# Orphan detection
# ---------------------------------------------------------------------------


def _build_id_index(records: list[AcRecord]) -> dict[str, AcRecord]:
    """Build a mapping from AC id to record dict.

    Args:
        records: All successfully loaded AC records.

    Returns:
        Dict mapping id → AcRecord.
    """
    index: dict[str, AcRecord] = {}
    for rec in records:
        ac_id = rec.get("id")
        if isinstance(ac_id, str) and ac_id.strip():
            index[ac_id.strip()] = rec
    return index


def find_orphaned_children(
    id_index: dict[str, AcRecord],
    derive_parent_id,
) -> dict[str, list[dict[str, str]]]:
    """Find all child ACs whose immediate parent's covered_by omits them.

    For every AC in *id_index* that has a parent (i.e. derive_parent_id
    returns a non-None value), check whether the parent record's covered_by
    list contains the child's ID. If not, the child is an orphan.

    Args:
        id_index: Full id-to-record mapping built from the AC store.
        derive_parent_id: The derive_parent_id callable from ac_parent_id module.

    Returns:
        Dict mapping parent_id → list of orphan dicts, where each orphan dict
        contains keys: child_id, parent_id, parent_file.
        Returns an empty dict when no orphans are found.
    """
    orphans: dict[str, list[dict[str, str]]] = {}

    for child_id, child_rec in id_index.items():
        parent_id = derive_parent_id(child_id)
        if parent_id is None:
            # Root-level AC — no parent to check.
            continue

        parent_rec = id_index.get(parent_id)
        if parent_rec is None:
            # Parent not found in the store — structural issue, but not
            # the responsibility of this scan (a missing-parent scan is
            # a separate concern).
            continue

        covered_by = _extract_covered_by(parent_rec)
        if child_id not in covered_by:
            entry = {
                "child_id": child_id,
                "parent_id": parent_id,
                "parent_file": parent_rec.get("_path", "(unknown)"),
            }
            if parent_id not in orphans:
                orphans[parent_id] = []
            orphans[parent_id].append(entry)

    return orphans


# ---------------------------------------------------------------------------
# Draft-orphan scan (AC BO-1500b-3): partial-run recovery pre-flight
# ---------------------------------------------------------------------------

#: AC authoring agents whose files can be orphaned by a crashed /create-ac run.
_AUTHORING_AGENTS = frozenset(
    {"product-owner", "business-analyst", "it-po"}
)


def scan_draft_orphans_in_worktree(
    worktree_path: Path,
    ac_store_rel: str = "docs/acceptance-criteria",
) -> list[dict[str, str]]:
    """Detect uncommitted AC YAML draft files left over from a prior crashed session.

    Runs ``git -C <worktree_path> status --porcelain --untracked-files=all``
    scoped to *ac_store_rel* (relative path inside the worktree).  Only
    working-tree changes are reported by ``git status``; AC files that are
    already committed on the authoring branch are naturally excluded because
    committed files do not appear in git status output.  This guarantees that
    the scan never produces false orphan reports for AC YAML files that were
    successfully committed in a prior (partial) session.

    Each candidate file is then qualified as an orphaned draft iff:

    - The file path ends in ``.yaml`` or ``.yml``.
    - The YAML ``origin_agent`` field is one of: ``product-owner``,
      ``business-analyst``, ``it-po``.
    - The YAML ``readiness`` field is ``"draft"``.

    This implements the detection algorithm described in
    ``templates/skills/create-ac/SKILL.md`` §PRR.2 (AC BO-1500b-3).

    Args:
        worktree_path: Absolute path to the dedicated AC-authoring worktree.
            All git operations use ``git -C <worktree_path>`` so they never
            affect the original checkout (AC BO-1500a-2).
        ac_store_rel: Path to the AC store directory **relative** to the
            worktree root.  Defaults to ``docs/acceptance-criteria``.

    Returns:
        List of dicts with keys ``file_path`` (absolute path string) and
        ``ac_id`` (the ``id`` field from the YAML, or the filename stem when
        ``id`` is absent).  The list is sorted by ``file_path``.  Returns an
        empty list when no qualifying orphans are found or when ``git status``
        exits non-zero (warn-and-proceed semantics per §PRR.2 error handling).

    Raises:
        Nothing — all errors are printed to stderr and the function returns an
        empty list (non-blocking).  This matches the ``git status`` error
        handling policy in §PRR.2: ``"Proceeding without orphan detection."``
    """
    worktree_path = Path(worktree_path).resolve()
    ac_store_path = worktree_path / ac_store_rel

    # Run git status --porcelain inside the authoring worktree.
    # Committed files are not shown by git status — false orphan reports from
    # already-committed AC files are excluded by git semantics (AC BO-1500b-3).
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(worktree_path),
                "status",
                "--porcelain",
                "--untracked-files=all",
                "--",
                str(ac_store_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        print(
            f"Warning: could not check for uncommitted AC files (git error: {exc}). "
            "Proceeding without orphan detection.",
            file=sys.stderr,
        )
        return []

    if result.returncode != 0:
        print(
            f"Warning: could not check for uncommitted AC files "
            f"(git error: {result.stderr.strip()}). "
            "Proceeding without orphan detection.",
            file=sys.stderr,
        )
        return []

    orphans: list[dict[str, str]] = []
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]

    for line in lines:
        if len(line) < 4:
            continue
        xy_status = line[:2]
        file_path_str = line[3:].strip()

        # Only consider YAML files.
        if not (file_path_str.endswith(".yaml") or file_path_str.endswith(".yml")):
            continue

        # Only include files with relevant status codes (modified, added, untracked).
        index_status = xy_status[0]
        worktree_status = xy_status[1]
        is_relevant = (
            index_status in ("M", "A")
            or worktree_status in ("M", "A")
            or xy_status == "??"
        )
        if not is_relevant:
            continue

        # Resolve to an absolute path inside the worktree.
        candidate = worktree_path / file_path_str
        record = _load_ac(candidate)
        if record is None:
            # Parse or read error already logged by _load_ac — skip.
            continue

        # Qualify by origin_agent and readiness.
        origin_agent = record.get("origin_agent")
        if isinstance(origin_agent, str):
            origin_agent = origin_agent.strip()
        if origin_agent not in _AUTHORING_AGENTS:
            continue

        readiness = record.get("readiness")
        if isinstance(readiness, str):
            readiness = readiness.strip()
        if readiness != "draft":
            continue

        # Derive AC ID from the id field or filename stem.
        ac_id = record.get("id")
        if isinstance(ac_id, str) and ac_id.strip():
            ac_id = ac_id.strip()
        else:
            ac_id = Path(file_path_str).stem

        orphans.append({"file_path": str(candidate), "ac_id": ac_id})

    return sorted(orphans, key=lambda o: o["file_path"])


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _print_orphan_report(orphans: dict[str, list[dict[str, str]]]) -> None:
    """Print the orphan report grouped by parent to stdout.

    Args:
        orphans: Dict mapping parent_id → list of orphan entries.
    """
    total = sum(len(v) for v in orphans.values())
    print(f"ORPHANED CHILDREN ({total} found, grouped by parent):")
    print()
    for parent_id in sorted(orphans):
        entries = orphans[parent_id]
        # Use the parent file path from the first entry.
        parent_file = entries[0]["parent_file"] if entries else "(unknown)"
        print(f"  Parent: {parent_id}")
        print(f"  Parent file: {parent_file}")
        print(f"  Orphaned children ({len(entries)}):")
        for entry in sorted(entries, key=lambda e: e["child_id"]):
            print(f"    - {entry['child_id']}")
        print()


def _print_clean_report(total_checked: int) -> None:
    """Print the all-clean summary to stdout.

    Args:
        total_checked: Total number of child ACs examined.
    """
    print(f"OK — {total_checked} child ACs checked, no orphans found.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser.

    Returns:
        Configured ArgumentParser instance with two subcommands:
        ``parent-links`` (original behaviour) and ``draft-orphans``
        (partial-run recovery pre-flight, AC BO-1500b-3).
    """
    parser = argparse.ArgumentParser(
        description=(
            "AC store orphan scanner.\n\n"
            "Subcommands:\n"
            "  parent-links  — detect child ACs omitted from parent covered_by (default).\n"
            "  draft-orphans — detect uncommitted draft AC files in an authoring worktree."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    # --- parent-links subcommand (original behaviour) ---
    parent_links_parser = subparsers.add_parser(
        "parent-links",
        help="Detect child ACs omitted from parent covered_by (original scan).",
    )
    parent_links_parser.add_argument(
        "--ac-root",
        dest="ac_root",
        default=None,
        help=(
            f"Root directory of the AC store (default: {_DEFAULT_AC_ROOT} "
            "relative to the worktree root)."
        ),
    )

    # --- draft-orphans subcommand (AC BO-1500b-3) ---
    draft_parser = subparsers.add_parser(
        "draft-orphans",
        help=(
            "Detect uncommitted AC YAML draft files from a prior crashed "
            "/create-ac session inside the dedicated authoring worktree. "
            "Implements the partial-run recovery pre-flight (§PRR.2). "
            "Emits a JSON array of {file_path, ac_id} objects to stdout. "
            "Already-committed AC files on the authoring branch are excluded "
            "by git status semantics (AC BO-1500b-3)."
        ),
    )
    draft_parser.add_argument(
        "--worktree",
        required=True,
        help="Absolute path to the dedicated AC-authoring worktree.",
    )
    draft_parser.add_argument(
        "--ac-root-rel",
        dest="ac_root_rel",
        default="docs/acceptance-criteria",
        help=(
            "AC store path relative to the worktree root "
            "(default: docs/acceptance-criteria)."
        ),
    )

    # Legacy: if no subcommand is given, treat as parent-links for backward compat.
    parser.add_argument(
        "--ac-root",
        dest="ac_root_legacy",
        default=None,
        help=argparse.SUPPRESS,
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for scan_ac_orphans.py.

    Args:
        argv: Command-line arguments (default: sys.argv[1:]).

    Returns:
        For ``parent-links`` (or legacy no-subcommand):
            0 when no orphans found, 1 when orphans found, 2 on YAML load errors.
        For ``draft-orphans``:
            0 always (results emitted as JSON to stdout; errors to stderr).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    # -----------------------------------------------------------------------
    # draft-orphans subcommand (AC BO-1500b-3)
    # -----------------------------------------------------------------------
    if args.subcommand == "draft-orphans":
        worktree = Path(args.worktree)
        if not worktree.is_dir():
            print(
                f"ERROR: worktree path does not exist or is not a directory: {worktree}",
                file=sys.stderr,
            )
            return 2

        orphans = scan_draft_orphans_in_worktree(worktree, args.ac_root_rel)
        print(json.dumps(orphans, indent=2))
        return 0

    # -----------------------------------------------------------------------
    # parent-links subcommand (original behaviour, also used for legacy calls)
    # -----------------------------------------------------------------------

    # Resolve ac_root — may come from the subcommand or the legacy flag.
    ac_root_raw = None
    if args.subcommand == "parent-links":
        ac_root_raw = args.ac_root
    else:
        # No subcommand given: legacy invocation — use --ac-root legacy flag.
        ac_root_raw = args.ac_root_legacy

    if ac_root_raw:
        ac_root = Path(ac_root_raw)
    else:
        try:
            worktree = _find_worktree_root(Path(__file__))
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        ac_root = worktree / _DEFAULT_AC_ROOT

    if not ac_root.exists():
        print(f"ERROR: AC root directory not found: {ac_root}", file=sys.stderr)
        return 2

    # Load derive_parent_id.
    try:
        derive_parent_id = _get_derive_parent_id()
    except ImportError as exc:
        print(f"ERROR: cannot import derive_parent_id: {exc}", file=sys.stderr)
        return 2

    # Load all YAML files.
    yaml_paths = sorted(ac_root.rglob("*.yaml"))
    all_records: list[AcRecord] = []
    load_errors = 0

    for path in yaml_paths:
        record = _load_ac(path)
        if record is None:
            load_errors += 1
        else:
            all_records.append(record)

    if load_errors:
        print(
            f"ERROR: {load_errors} AC YAML file(s) could not be loaded. "
            "Fix parse errors before running the orphan scan.",
            file=sys.stderr,
        )
        return 2

    # Build id index.
    id_index = _build_id_index(all_records)

    # Find orphans.
    orphans = find_orphaned_children(id_index, derive_parent_id)

    # Count child ACs checked (those with a derivable parent in the index).
    children_checked = sum(
        1 for ac_id in id_index if derive_parent_id(ac_id) in id_index
    )

    if orphans:
        _print_orphan_report(orphans)
        return 1

    _print_clean_report(children_checked)
    return 0


if __name__ == "__main__":
    sys.exit(main())
