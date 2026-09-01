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

Merge scoping (AC GE-120e-1, superseding GE-120e-3-ii):
    When ``MERGE_HEAD`` is present, ``get_staged_md_files`` narrows its result
    to ``.md`` paths differing from BOTH merge parents — i.e. content the
    merge author's own resolution introduced or changed — via the SHARED
    ``_authored_change.get_authored_change()`` derivation, the same one
    ``check_contract_shrinking.py`` consumes, so both checks answer "what did
    the author change" identically. A merge stages the entire incoming
    branch, so an unscoped ``git diff --cached`` also names every ``.md``
    file the OTHER side ever touched, which the merge author neither wrote
    nor can fix. Outside a merge, the full staged set is used unchanged — the
    stricter, pre-existing behaviour. When the derivation cannot be computed
    at all (e.g. a git failure resolving the merge-parent side),
    ``get_staged_md_files`` returns ``None`` — a could-not-check outcome —
    rather than falling back to the unscoped staged set.

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

from _resolve_root import find_project_root


def _resolve_worktree_root() -> Path:
    """Return the git working-tree top-level for the current process cwd.

    Preferred over ``find_project_root()`` (which is ``__file__``-relative) for
    determining the base directory against which staged file paths are resolved.
    During a pre-commit run, the process cwd is always set to the git
    working-tree root by git itself.  Inside a linked git worktree that root
    differs from the primary checkout, so ``git rev-parse --show-toplevel``
    (cwd-relative) is the only reliable anchor.

    ``find_project_root()`` is still imported and used as the fallback for three
    conditions:

    * ``git`` is not on PATH — ``OSError`` raised by ``subprocess.run``.
    * The invocation exits non-zero — not inside a git repository, e.g. a
      manual ``--all`` scan from an arbitrary directory.
    * ``git rev-parse`` returns empty output (degenerate edge case).

    In all three cases, ``find_project_root()`` is returned so that non-git
    usage continues to work exactly as before (AC GE-115 criterion 3).

    Returns:
        Path: Absolute path to the git working-tree root (from
        ``git rev-parse --show-toplevel``) on success; ``find_project_root()``
        on any failure.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, OSError):
        return find_project_root()

    top_level = result.stdout.strip()
    if not top_level:
        return find_project_root()
    return Path(top_level)


project_root = _resolve_worktree_root()

from config import (
    DOC_FM_COMPONENTS_REGISTRY,
    DOC_FM_DOCS_DIR,
    TICKET_FM_TICKETS_DIR,
)

from frontmatter_validators import (
    validate_doc_file,
    validate_ticket_file,
)

try:
    from check_outcome import (  # type: ignore[import]
        OUTCOME_COULD_NOT_CHECK,
        OUTCOME_NOTHING_TO_INSPECT,
        emit_result,
    )
except ImportError:
    # check_outcome.py is deployed alongside this file in every real layout
    # (build.py copies the whole templates/scripts/commit_guardian/ tree), so
    # this fallback exists only for a working copy that exposes this check
    # script in isolation (e.g. a test fixture) -- same pattern as
    # check_ac_parent_covered_by.py / check_contract_shrinking.py. The values
    # here MUST stay in sync with check_outcome.py.
    OUTCOME_NOTHING_TO_INSPECT = "nothing_to_inspect"
    OUTCOME_COULD_NOT_CHECK = "could_not_check"

try:
    from _authored_change import get_authored_change  # type: ignore[import]
except ImportError:
    # _authored_change.py is deployed alongside this file in every real
    # layout (build.py copies the whole templates/scripts/commit_guardian/
    # tree). This fallback exists only for a working copy that exposes this
    # check script in isolation (e.g. a test fixture that predates GE-120e-1).
    get_authored_change = None  # type: ignore[assignment]

    def emit_result(outcome: str) -> None:
        """Fallback RESULT-line emitter used when check_outcome is absent."""
        print(f"RESULT: {outcome}", file=sys.stdout)

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


def _get_shared_authored_change():
    """Call the shared ``get_authored_change()``, degrading a broken import to ``None``.

    Mirrors ``check_contract_shrinking.py``'s helper of the same name: the
    shared module is a dependency this check does not control, and GE-120e-1's
    AC-5 requires that if it is broken (raises unexpectedly, as opposed to the
    ordinary git-failure path it already reports via ``could_not_check``),
    every consumer degrades to could-not-check identically rather than
    crashing the whole pre-commit process or silently passing on bad data.

    Returns:
        The ``AuthoredChange``, or ``None`` (shared module unavailable, or it
        raised unexpectedly — an ordinary derivation failure is instead
        reported IN BAND via the returned ``AuthoredChange.could_not_check``).
    """
    if get_authored_change is None:
        return None
    try:
        return get_authored_change()
    except Exception as exc:  # noqa: BLE001 - shared dependency may raise unpredictably; must degrade to could-not-check, never crash or widen (GE-120e-1 AC-5).
        print(f"WARNING: shared change-set derivation raised: {exc}", file=sys.stderr)
        return None


def get_staged_md_files() -> dict[str, str] | None:
    """Get all staged .md files with their git status.

    During a merge (``MERGE_HEAD`` present), the result is narrowed — via the
    shared ``_authored_change.get_authored_change()`` derivation (GE-120e-1,
    see the module docstring's "Merge scoping" section) — to paths not
    carried in verbatim from the incoming branch. Outside a merge, every
    staged ``.md`` file is returned unchanged.

    Returns:
        dict[str, str] | None: Mapping of filepath to git status code, or
        ``None`` when the shared derivation could not be computed at all —
        a could-not-check outcome the caller must NOT treat as "nothing
        staged" (which would silently skip validation) nor widen to the
        unscoped staged set.
    """
    if get_authored_change is None:
        # Shared module unavailable in this working copy (isolated test
        # fixture predating GE-120e-1) -- fall back to a plain, unscoped
        # git diff --cached --name-status so this file keeps working there.
        try:
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-status"],
                capture_output=True, text=True, check=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            print(f"WARNING: git diff --cached --name-status failed: {exc}", file=sys.stderr)
            return None
        name_status = {}
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) >= 2:
                name_status[parts[-1]] = parts[0]
    else:
        authored = _get_shared_authored_change()
        if authored is None or authored.could_not_check:
            return None
        name_status = dict(authored.name_status)

    return {
        filepath: status
        for filepath, status in name_status.items()
        if filepath.lower().endswith(".md") and not status.startswith("D")
    }


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
    roadmap_path = project_root / "docs" / "roadmap.json"
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


def get_files_to_check(args: argparse.Namespace, project_root: Path) -> dict[str, str] | None:
    """Determine which files to check based on CLI arguments.

    Args:
        args: Parsed command-line arguments.
        project_root: Absolute path to the project root.

    Returns:
        dict[str, str] | None: Mapping of relative file paths to their git
        status, or ``None`` — only possible on the default (no ``--file`` /
        ``--all`` / positional filenames) path — when
        ``get_staged_md_files()`` could not compute the authored change set
        at all (could-not-check; see that function's docstring).
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


def _report_if_nothing_to_inspect(args: argparse.Namespace) -> None:
    """Emit GE-120e-1-i's outcome when the merge author authored no .md content.

    GE-120e-1-i: an empty authored (merge-scoped) change set is a value to
    report, never a signal to widen the scan back to the whole staged tree —
    that anti-pattern is already avoided by construction in
    ``get_staged_md_files`` (an empty scoped intersection from the shared
    ``_authored_change.get_authored_change()`` derivation narrows the staged
    set to ``{}``, not a fallback to the unscoped diff). This function only
    decides whether to ANNOUNCE that empty state on the shared,
    machine-readable RESULT line, distinguishing "nothing of the author's to
    inspect" from GE-120a-1's OUTCOME_COULD_NOT_CHECK ("a check that never
    looked"). Only meaningful for the default (no ``--file`` / ``--all`` /
    positional filenames) invocation, where the staged set actually goes
    through merge scoping; a manual file selection is never "merge-derived",
    so it is skipped here. Called only from the non-blocking (pass) path in
    ``main()`` — empty is a PASS, not a skip; a could-not-check outcome is
    handled separately in ``main()`` before this function is ever reached.

    Args:
        args: Parsed command-line arguments.
    """
    if args.file or args.all or args.filenames:
        return
    authored = _get_shared_authored_change()
    if (
        authored is not None
        and not authored.could_not_check
        and len(authored.states) > 1
        and not authored.paths
    ):
        emit_result(OUTCOME_NOTHING_TO_INSPECT)


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

    if files_to_check is None:
        # GE-120e-1: the shared change-set derivation could not be computed
        # (e.g. a git failure resolving the merge-parent side). Report
        # could-not-check and skip validation for THIS commit rather than
        # widening the scan to the unscoped staged set.
        print(
            "WARNING: could not derive the authored (merge-scoped) change "
            "set for this commit — skipping frontmatter validation rather "
            "than falling back to the whole staged set.",
            file=sys.stderr,
        )
        emit_result(OUTCOME_COULD_NOT_CHECK)
        return 0

    if not files_to_check:
        _report_if_nothing_to_inspect(args)
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
- 2026-08-31 [python-coder/GE-120e-1, pr-reviewer remediation]: The shared
  module imported below was renamed from _resolve_change_set.py/
  get_change_set() to _authored_change.py/get_authored_change(), to honour
  the contract unit_tests/portability/test_ge_120e_4_i.py (ticket 36) had
  already established for it. get_staged_md_files() and
  _report_if_nothing_to_inspect() were updated to read the renamed module's
  in-band could_not_check/states fields instead of a None sentinel/head_ref.
  (#EPIC-TrustThatAGreenCheckActuallyChecked/28)
- 2026-08-31 [python-coder/GE-120e-1]: get_staged_md_files() now derives its
  scoped set from the SHARED templates/scripts/commit_guardian/
  _authored_change.get_authored_change() (also consumed by
  check_contract_shrinking.py) instead of the private
  frontmatter_validators.merge_scoped_md_paths(), which is removed. It
  returns None on a could-not-check outcome instead of falling back to the
  unscoped staged set; main() and _report_if_nothing_to_inspect() were
  updated to handle that None distinctly from "nothing staged".
  (#EPIC-TrustThatAGreenCheckActuallyChecked/28)
- 2026-08-25 [python-coder/GE-120e-1-i]: Added _report_if_nothing_to_inspect(),
  called from main()'s empty-files_to_check pass path. Emits the shared
  check_outcome.OUTCOME_NOTHING_TO_INSPECT RESULT line when
  frontmatter_validators.merge_scoped_md_paths() finds the merge author's
  own resolution touched no .md content -- an explicit, non-widening empty
  result, distinguishable from GE-120a-1's OUTCOME_COULD_NOT_CHECK. No
  change to the pass/block decision itself (the merge-scoped narrowing that
  makes AC-1/AC-2 true here was already in place via GE-120e-3-ii, below).
  (#EPIC-TrustThatAGreenCheckActuallyChecked/29)
- 2026-08-25 [python-coder/GE-120e-3-ii]: get_staged_md_files() now applies
  frontmatter_validators.merge_scoped_md_paths() to narrow the staged .md
  set to paths differing from BOTH merge parents whenever MERGE_HEAD is
  present, mirroring check_contract_shrinking.py's _merge_scoped_paths
  idiom. Fixes two false-positive shapes: naming carried-in .md content
  the merge author never touched, and blocking a merge whose invalid
  frontmatter arrived unchanged from a parent with no author resolution.
  The new helpers live in frontmatter_validators.py, not here, to keep
  this file under the 400-line limit. (AC GE-120e-3-ii)
- 2026-05-19 11:30 [EPIC-RoadmapStewardship/03]: Added roadmap_staleness check. (#EPIC-RoadmapStewardship/03)
  Adds check_roadmap_staleness() and _load_roadmap_staleness_threshold() to
  fire a warn-only stderr warning when docs/roadmap.json.last_updated exceeds
  the configured threshold (default 30 days, key roadmap_staleness_threshold_days
  in commit_guardian.json). Always exits 0. Missing or unparseable last_updated
  prints a soft warning and skips the age check. Warning text suggests /po-review.
  Implements the pre-commit nag (advisory warning, never blocking).
- 2026-05-17 00:00 [python-coder]: Added is_terminal_or_done_subfolder() helper
  that returns True for tickets/99_done/**, tickets/99_rejected/**,
  tickets/01_todo/EPIC-*/done/**, and tickets/00_inbox/epics/EPIC-*/done/**.
  Wired into main() so matched files are skipped before validate_ticket_file is
  called (same pattern as is_ticket_readme). Eliminates ~118 pre-schema legacy
  violations that blocked commits touching those paths. Mirror updated in
  lockstep. (TICKET-20260515-Legacy_Tickets_Frontmatter_Backfill_Or_Validator_Scope)
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
- 2026-07-08 [python-coder/GE-115]: Fixed false "Could not read file" violation
  inside linked git worktrees. Replaced module-level
  ``project_root = find_project_root()`` (``__file__``-relative, resolves to
  the leafcutter-ai source root regardless of cwd) with
  ``project_root = _resolve_worktree_root()``. The new helper runs
  ``git rev-parse --show-toplevel`` via subprocess — a cwd-relative command
  that always returns the worktree root during a pre-commit run — and falls back
  to ``find_project_root()`` when git is absent or the process is not inside a
  repo. Eliminates the need for SKIP=check-doc-frontmatter in worktree-based
  drives. (AC GE-115)
====================================================================
"""
