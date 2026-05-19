"""
Pre-commit hook to validate YAML frontmatter on docs/ and tickets/ markdown files.

MODULE: check_doc_frontmatter
GOAL: Enforce the FRONTMATTER.md specification on all staged docs/*.md files
    and the ticket frontmatter rules on all staged tickets/**/*.md files
    (excluding tickets/**/README.md).
BUSINESS CONTEXT: Ensures both documentation and tickets are machine-parseable
    and maintain consistent metadata for traceability, search, and automated
    quality checks.
ARCHITECTURE: Not needed.

Doc checks:
    1. Presence of YAML frontmatter delimited by ``---``.
    2. All required fields present — per-glob dict: docs/architecture/** also requires
       ``flight_level``; docs/** requires the base 6 fields.
    3. ``type`` matches the allowed enum values.
    4. ``status`` matches the allowed enum values.
    5. ``flight_level`` value is valid when present (4 values).
    6. ``diagram_type`` value is valid when present (8 values + ``none``).
    7. ``components`` entries exist in ``docs/components.json``.
    8. ``related_docs``, ``related_code``, ``architecture_diagrams`` paths exist (blocking).
    9. (warn-only) Body content changed but ``last_updated`` is stale.

Ticket checks:
    1. Presence of YAML frontmatter delimited by ``---``.
    2. Required fields: title, status, components, created, depends_on.
    3. ``status`` matches the allowed ticket enum values.
    4. ``type`` (optional) matches the allowed ticket type enum.
    5. ``components`` entries exist in ``docs/components.json``.
    6. Each ``depends_on`` entry resolves to a sibling ticket file (or to a
       sibling ``done/`` subfolder, or — when the ticket itself lives in
       ``done/`` — to the parent of ``done/``).

Exit Codes:
    0 - All files pass validation (warnings are printed but do not block)
    1 - One or more files have blocking violations

Usage:
    poetry run python scripts/commit_guardian/check_doc_frontmatter.py
    poetry run python scripts/commit_guardian/check_doc_frontmatter.py --file docs/some_file.md
    poetry run python scripts/commit_guardian/check_doc_frontmatter.py --all
"""

import argparse
import glob
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

# Fix import path when running from root
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.commit_guardian.config import (
    DOC_FM_COMPONENTS_REGISTRY,
    DOC_FM_DOCS_DIR,
    TICKET_FM_TICKETS_DIR,
)

from scripts.commit_guardian.frontmatter_validators import (
    validate_doc_file,
    validate_ticket_file,
)

# ---------------------------------------------------------------------------
# File processing
# ---------------------------------------------------------------------------


def load_components_registry(project_root_path: Path) -> set[str]:
    """Load valid component IDs from the components.json registry.

    Supports two on-disk formats:

    - Dict-keyed (current): ``{"components": {"id1": {...}, "id2": {...}}}``
      → keys are the component IDs.
    - Legacy list-of-dicts: ``{"components": [{"id": "id1", ...}, ...]}``
      → each entry's ``"id"`` field is the component ID.

    Documented ``aliases`` arrays on each entry are also added to the returned
    set, because docs/FRONTMATTER.md treats aliases as legitimate identifiers.

    Args:
        project_root_path: Absolute path to the project root.

    Returns:
        set[str]: Set of valid component ID strings (canonical IDs plus any
        configured aliases). Empty set if the file is missing, malformed, or
        in an unexpected shape.
    """
    registry_path = project_root_path / DOC_FM_COMPONENTS_REGISTRY
    if not registry_path.exists():
        return set()

    try:
        with open(registry_path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return set()

    components = data.get("components")
    valid: set[str] = set()

    if isinstance(components, dict):
        valid.update(components.keys())
        entries = list(components.values())
    elif isinstance(components, list):
        entries = [c for c in components if isinstance(c, dict) and "id" in c]
        valid.update(entry["id"] for entry in entries)
    else:
        return set()

    for entry in entries:
        if isinstance(entry, dict):
            aliases = entry.get("aliases")
            if isinstance(aliases, list):
                valid.update(a for a in aliases if isinstance(a, str))

    return valid


def is_in_docs_dir(filepath: str) -> bool:
    """Check if a file is inside the docs/ directory.

    Args:
        filepath: Relative file path within the repo.

    Returns:
        bool: True if the file is in docs/ or a subdirectory of it.
    """
    parts = Path(filepath).parts
    return len(parts) >= 2 and parts[0] == DOC_FM_DOCS_DIR


def is_in_adr_dir(filepath: str) -> bool:
    """Check if a file is inside the adr/ directory.

    Args:
        filepath: Relative file path within the repo.

    Returns:
        bool: True if the file path begins with ``adr/``.
    """
    parts = Path(filepath).parts
    return len(parts) >= 2 and parts[0] == "adr"


def is_in_tickets_dir(filepath: str) -> bool:
    """Check if a file is inside the tickets/ directory.

    Args:
        filepath: Relative file path within the repo.

    Returns:
        bool: True if the file path begins with ``tickets/``.
    """
    parts = Path(filepath).parts
    return len(parts) >= 2 and parts[0] == TICKET_FM_TICKETS_DIR


def is_ticket_readme(filepath: str) -> bool:
    """Check if a file is a README inside the tickets/ tree.

    These are explicitly excluded from the ticket frontmatter check because
    they are folder-level navigational documents, not ticket records.

    Args:
        filepath: Relative file path within the repo.

    Returns:
        bool: True for any ``README.md`` whose path is inside ``tickets/``.
    """
    if not is_in_tickets_dir(filepath):
        return False
    return Path(filepath).name == "README.md"


def is_terminal_or_done_subfolder(filepath: str) -> bool:
    """Check if a ticket file is in a terminal or done-subfolder path.

    Terminal and done-subfolder tickets are pre-schema legacy files that
    are intentionally excluded from frontmatter validation to avoid blocking
    commits that happen to stage these files alongside active work.

    Skipped paths:
    - ``tickets/99_done/**``            — archived epics and singles
    - ``tickets/99_rejected/**``        — rejected work
    - ``tickets/01_todo/EPIC-*/done/**`` — completed sub-tickets in active epics
    - ``tickets/00_inbox/epics/EPIC-*/done/**`` — completed sub-tickets in proposed epics

    Args:
        filepath: Relative file path within the repo (forward slashes).

    Returns:
        bool: True if the file is in a terminal or done subfolder and should
        be skipped by the frontmatter validator.
    """
    parts = Path(filepath).parts
    if len(parts) < 2 or parts[0] != TICKET_FM_TICKETS_DIR:
        return False

    # tickets/99_done/** and tickets/99_rejected/**
    if parts[1] in ("99_done", "99_rejected"):
        return True

    # tickets/01_todo/EPIC-*/done/**
    if (
        len(parts) >= 4
        and parts[1] == "01_todo"
        and parts[2].startswith("EPIC-")
        and parts[3] == "done"
    ):
        return True

    # tickets/00_inbox/epics/EPIC-*/done/**
    if (
        len(parts) >= 5
        and parts[1] == "00_inbox"
        and parts[2] == "epics"
        and parts[3].startswith("EPIC-")
        and parts[4] == "done"
    ):
        return True

    return False


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def get_staged_md_files() -> dict[str, str]:
    """Get all staged .md files with their git status.

    Returns:
        dict[str, str]: Mapping of filepath to git status code.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-status"],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError:
        return {}

    staged = {}
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            status = parts[0]
            filepath = parts[-1]
            if filepath.lower().endswith(".md") and not status.startswith("D"):
                staged[filepath] = status

    return staged


# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------


def configure_stdout() -> None:
    """Ensure output works on Windows with UTF-8."""
    if sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def _load_roadmap_staleness_threshold(project_root: Path) -> int:
    """Load the roadmap staleness threshold from commit_guardian.json.

    Args:
        project_root: Absolute path to the project root.

    Returns:
        int: Threshold in days. Defaults to 30 when the key is absent or the
        file cannot be read.
    """
    config_path = (
        project_root
        / "portable-dev-workflow"
        / "scripts"
        / "commit_guardian"
        / "commit_guardian.json"
    )
    if not config_path.exists():
        return 30
    try:
        with open(config_path, encoding="utf-8") as fh:
            cfg = json.load(fh)
        return int(cfg.get("roadmap_staleness_threshold_days", 30))
    except Exception:  # noqa: BLE001
        return 30


def check_roadmap_staleness(project_root: Path) -> None:
    """Warn when docs/roadmap.json has not been updated recently.

    Reads the ``last_updated`` field from ``docs/roadmap.json`` and computes
    the age in days relative to today. Prints a warning to stderr when the age
    exceeds the configured threshold. Always exits 0 (warn-only; never blocks
    a commit).

    A missing ``docs/roadmap.json`` or a missing / unparseable ``last_updated``
    field is treated as a soft-warning (printed to stderr) rather than an error.

    Args:
        project_root: Absolute path to the project root.
    """
    from scripts.commit_guardian.config import DOC_FM_DOCS_DIR
    roadmap_path = project_root / DOC_FM_DOCS_DIR / "roadmap.json"
    threshold = _load_roadmap_staleness_threshold(project_root)

    if not roadmap_path.exists():
        return  # No roadmap.json — nothing to check.

    try:
        data = json.loads(roadmap_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        print(
            "WARNING: roadmap.json — could not parse docs/roadmap.json; skipping staleness check.",
            file=sys.stderr,
        )
        return

    last_updated_raw = data.get("last_updated")
    if not last_updated_raw:
        print(
            "WARNING: roadmap.json — last_updated field is missing; "
            "consider running /po-review to update the roadmap.",
            file=sys.stderr,
        )
        return

    try:
        last_updated_date = date.fromisoformat(str(last_updated_raw)[:10])
    except ValueError:
        print(
            f"WARNING: roadmap.json — last_updated value '{last_updated_raw}' is not a "
            "recognised date; skipping staleness check.",
            file=sys.stderr,
        )
        return

    age_days = (date.today() - last_updated_date).days
    if age_days > threshold:
        print(
            f"WARNING: roadmap.json has not been updated in {age_days} days "
            f"(threshold: {threshold} days) — consider running /po-review",
            file=sys.stderr,
        )


def get_files_to_check(args: argparse.Namespace, project_root: Path) -> dict[str, str]:
    """Determine which files to check based on CLI arguments.

    Args:
        args: Parsed command-line arguments.
        project_root: Absolute path to the project root.

    Returns:
        dict[str, str]: Mapping of relative file paths to their git status.
    """
    if args.file:
        try:
            filepath = Path(args.file).resolve().relative_to(project_root).as_posix()
        except ValueError:
            filepath = Path(args.file).as_posix()
        return {filepath: "M"}
    
    if args.all:
        docs_glob = str(project_root / DOC_FM_DOCS_DIR / "**" / "*.md")
        files = {}
        for md_file in glob.glob(docs_glob, recursive=True):
            try:
                rel = Path(md_file).resolve().relative_to(project_root).as_posix()
                files[rel] = "M"
            except ValueError:
                pass
        return files

    if args.filenames:
        files = {}
        for f in args.filenames:
            try:
                rel = Path(f).resolve().relative_to(project_root).as_posix()
            except ValueError:
                rel = Path(f).as_posix()
            files[rel] = "M"
        return files

    return get_staged_md_files()


def print_results(all_errors: list[str], all_warnings: list[str], passed_count: int) -> int:
    """Print results and return exit code.

    Args:
        all_errors: List of blocking error messages.
        all_warnings: List of non-blocking warning messages.
        passed_count: Number of files that passed validation successfully.

    Returns:
        int: Exit code (1 if there are errors, 0 otherwise).
    """
    if all_warnings:
        print("\n⚠️  Documentation Frontmatter Warnings:\n")
        for w in all_warnings:
            print(w)
        print()

    if all_errors:
        print("\n📚 Documentation Frontmatter Check Failed\n")
        for err in all_errors:
            print(err)
            print()
        print("   FIX: Add or correct YAML frontmatter per docs/FRONTMATTER.md spec.")
        print("   📖 Spec: docs/FRONTMATTER.md\n")
        return 1

    if passed_count > 0:
        print(f"✅ PASSED: {passed_count} doc(s) passed frontmatter validation")

    return 0


def _should_skip(filepath: str) -> bool:
    """Return True if this file should be skipped by all validators.

    Args:
        filepath: Relative file path within the repo.

    Returns:
        bool: True if the file is outside the three validated trees, is a
        ticket README, or is a terminal/done-subfolder ticket.
    """
    in_docs = is_in_docs_dir(filepath)
    in_tickets = is_in_tickets_dir(filepath)
    in_adr = is_in_adr_dir(filepath)
    if not in_docs and not in_tickets and not in_adr:
        return True
    if in_tickets and is_ticket_readme(filepath):
        return True
    if in_tickets and is_terminal_or_done_subfolder(filepath):
        return True
    return False


def _validate_one(
    filepath: str,
    valid_components: set[str],
) -> tuple[list[str], list[str]]:
    """Dispatch validation for a single file to the appropriate validator.

    Args:
        filepath: Relative file path within the repo.
        valid_components: Set of valid component ID strings.

    Returns:
        tuple[list[str], list[str]]: (blocking_errors, warnings).
    """
    if is_in_docs_dir(filepath) or is_in_adr_dir(filepath):
        return validate_doc_file(filepath, valid_components, project_root)
    return validate_ticket_file(filepath, valid_components, project_root)


def main() -> int:
    """Entry point for the doc frontmatter pre-commit hook.

    Returns:
        int: Exit code (0 success, 1 violations found).
    """
    parser = argparse.ArgumentParser(description="Validate YAML frontmatter on docs/*.md files.")
    parser.add_argument("--file", help="Specific file to check (bypasses git staged files).")
    parser.add_argument("--all", action="store_true", help="Scan all .md files in docs/.")
    parser.add_argument("filenames", nargs="*", help="Files to check (passed by pre-commit)")
    args = parser.parse_args()

    configure_stdout()
    check_roadmap_staleness(project_root)

    valid_components = load_components_registry(project_root)
    files_to_check = get_files_to_check(args, project_root)

    if not files_to_check:
        return 0

    all_errors: list[str] = []
    all_warnings: list[str] = []
    passed_count = 0

    for filepath in files_to_check:
        if _should_skip(filepath):
            continue

        errors, warnings = _validate_one(filepath, valid_components)

        if errors:
            all_errors.append(
                f"❌ FRONTMATTER VIOLATION: '{filepath}'\n"
                + "\n".join(f"   {e}" for e in errors)
            )
        if warnings:
            all_warnings.extend(f"   {filepath}: {w}" for w in warnings)

        if not errors:
            passed_count += 1

    return print_results(all_errors, all_warnings, passed_count)


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-19 11:30 [EPIC-RoadmapStewardship/03]: Added roadmap_staleness check. (#EPIC-RoadmapStewardship/03)
  Adds check_roadmap_staleness() and _load_roadmap_staleness_threshold() to
  fire a warn-only stderr warning when docs/roadmap.json.last_updated exceeds
  the configured threshold (default 30 days, key roadmap_staleness_threshold_days
  in commit_guardian.json). Always exits 0. Missing or unparseable last_updated
  prints a soft warning and skips the age check. Warning text suggests /po-review.
  Implements ADR-038 Option A (pre-commit nag).
- 2026-05-17 00:00 [python-coder]: Added is_terminal_or_done_subfolder() helper. (#TICKETLESS reason=legacy-scope-fix-pre-schema-violations)
  Skips tickets/99_done/**, tickets/99_rejected/**, tickets/01_todo/EPIC-*/done/**,
  and tickets/00_inbox/epics/EPIC-*/done/** before validate_ticket_file is called.
- 2026-05-12 10:45 [Agent]: Extended hook to validate adr/*.md files through
  the same validate_doc_file path as docs/ files. Added is_in_adr_dir() helper
  and updated main() dispatcher. Pre-commit files pattern also extended to
  include adr/ (ticket 16 EPIC-DocTraceability).
- 2026-05-05 12:00 [AI]: Extended hook to validate ticket frontmatter on
  tickets/**/*.md (excluding tickets/**/README.md). Added is_in_tickets_dir,
  is_ticket_readme, and a path-based dispatcher in main(). Renamed
  validate_file -> validate_doc_file (now lives in frontmatter_validators.py
  alongside the new validate_ticket_file). Fixed load_components_registry to
  support the dict-keyed components.json shape in addition to the legacy
  list-of-dicts, and to also accept ``aliases`` so existing alias references
  in docs/FRONTMATTER.md continue to validate. (EPIC-DocTraceability #15)
- 2026-05-04 18:58 [AI/Antigravity]: Fixed NoneType crash in validate_last_updated
  when git show returns empty content for files that previously had no frontmatter.
  Added None guard and try/except for read_text.
- 2026-05-11 00:00 [Agent]: Added validate_flight_level and validate_diagram_type
  calls. Updated validate_required_fields call to pass filepath for per-glob
  resolution. Fixed load_components_registry to handle dict-format components.json.
  Updated module docstring (ticket 02).
- 2026-05-03 14:24 [AI/Antigravity]: Initial implementation. Validates YAML
  frontmatter on docs/*.md files per docs/FRONTMATTER.md specification.
  Blocks on missing/invalid required fields and broken paths; warns on stale
  last_updated dates. Follows existing commit guardian patterns.
====================================================================
"""
