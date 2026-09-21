"""
epic_cli.py — Argument parser and --ids mode dispatch for goal_to_epic.

MODULE: epic_cli
GOAL: Define the goal_to_epic command-line surface — the two mutually exclusive
      modes (--ac / --ids), the path overrides, and the readiness-gate flags —
      and run the --ids mode end to end, mapping every failure onto exit code 1.
BUSINESS CONTEXT: The CLI is a contract, not an implementation detail: five
      test files invoke scripts/goal_to_epic.py as a subprocess and assert on
      its flags and exit codes, and templates/agents/build-ac.md plus
      templates/skills/build-ac/SKILL.md instruct agents to shell out to it.
      Extracted from goal_to_epic.py so that file can meet the 400-line
      check_file_size limit; no flag, help string or exit code changed.
ARCHITECTURE: main() itself stays in goal_to_epic.py — tests patch
      goal_to_epic.run and goal_to_epic._find_worktree_root and then call
      goal_to_epic.main(), which only works while main resolves both names as
      globals of that module. What lives here is everything main() can
      delegate without breaking that: the parser, and the --ids branch (which
      calls build_epic_from_ids, a function no test patches). Imports
      epic_errors, epic_pipeline and epic_runtime. Deployed flat beside
      goal_to_epic.py (see AC_STORE_DEPLOY_MAP in scripts/build_phases.py).

AC coverage owned by this module:
    ACD-1200b-4: --yes and --approved-only are declared here and forwarded to
                 the readiness gate.
    BO-2600a-5:  --ac and --ids form a required mutually exclusive group; --ids
                 parses a comma-separated list and prints the epic folder path
                 as the last stdout line before exiting 0.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from epic_errors import CyclicDependencyError, ZeroLeafError
from epic_pipeline import build_epic_from_ids
from epic_runtime import _DEFAULT_INBOX_DIR, _DEFAULT_STORE_ROOT

# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser.

    Supports two mutually exclusive modes (exactly one must be supplied):

    - ``--ac <ac_id>``          Tree-traversal mode: walks the AC subtree beneath
                                *ac_id* and generates one ticket per leaf.
    - ``--ids <id1,id2,...>``   Explicit id-list mode (BO-2600a-5): takes the
                                comma-separated id list as authoritative; no subtree
                                re-derivation; cross-tree prerequisites are preserved.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Walk the AC tree from a goal AC (--ac), or assemble from an explicit "
            "leaf AC id list (--ids), generating one ticket per AC and assembling "
            "the results into a numbered EPIC folder."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--ac",
        dest="ac_id",
        default=None,
        help="Goal or L1 AC id to start tree traversal from (--ac mode).",
    )
    mode_group.add_argument(
        "--ids",
        dest="ids",
        default=None,
        help=(
            "Comma-separated list of leaf AC ids to include in the epic (--ids mode, "
            "BO-2600a-5). The id set is taken as authoritative — no subtree traversal "
            "is performed. Cross-tree ids in the list are preserved. "
            "Example: --ids ACD-050a-1,ACD-050b-1"
        ),
    )
    parser.add_argument(
        "--store-root",
        dest="store_root",
        default=None,
        help=f"Root directory of the AC YAML store (default: {_DEFAULT_STORE_ROOT} relative to worktree).",
    )
    parser.add_argument(
        "--inbox-dir",
        dest="inbox_dir",
        default=None,
        help=f"Tickets inbox root directory (default: {_DEFAULT_INBOX_DIR} relative to worktree).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Print the plan without writing any files.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        dest="yes",
        default=False,
        help=(
            "Proceed past the readiness gate without prompting, using only the "
            "already-approved leaf ACs (equivalent to choosing 'yes' at the "
            "interactive prompt). Required when stdin has no controlling TTY "
            "and some ACs are unapproved. (ACD-1200b-4)"
        ),
    )
    parser.add_argument(
        "--approved-only",
        action="store_true",
        dest="approved_only",
        default=False,
        help=(
            "Filter to only already-approved leaf ACs and skip unapproved ones "
            "without presenting any interactive prompt. Clears the readiness gate "
            "in non-interactive (no-TTY) runs. (ACD-1200b-4)"
        ),
    )
    return parser


# ---------------------------------------------------------------------------
# --ids mode (BO-2600a-5)
# ---------------------------------------------------------------------------


def _run_ids_mode(raw_ids: str, ac_store_root: Path, inbox_dir: Path) -> int:
    """Run --ids mode: parse the id list, build the epic, print its path.

    Every failure mode maps onto exit code 1 with an ``ERROR:`` line on stderr;
    on success the epic folder path is the last line on stdout, which is what
    the build-ac agent reads.

    Args:
        raw_ids: The raw comma-separated value of the ``--ids`` flag.
        ac_store_root: Root directory of the AC YAML store.
        inbox_dir: Absolute path to the tickets inbox root.

    Returns:
        int: 0 on success, 1 on any error.
    """
    ids = [i.strip() for i in raw_ids.split(",") if i.strip()]
    if not ids:
        print("ERROR: --ids requires at least one AC id.", file=sys.stderr)
        return 1
    try:
        epic_folder = build_epic_from_ids(ids, store_root=ac_store_root, inbox_dir=inbox_dir)
    except (ZeroLeafError, CyclicDependencyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: ticket generation failed: {exc}", file=sys.stderr)
        return 1
    except (OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(str(epic_folder))
    return 0


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 12:00 [goal-to-epic-decompose]: Extracted from
  scripts/goal_to_epic.py, which exceeded the 400-line check_file_size limit.
  _build_parser moved verbatim — every flag, dest, default and help string is
  byte-identical, because five test files drive this parser through a real
  subprocess and two agent templates document the flags. _run_ids_mode is
  main()'s --ids branch lifted out unchanged: the same four except clauses in
  the same order, the same ERROR text, the same exit codes, and the epic folder
  path still printed as the last stdout line.

  main() deliberately did NOT move here. Three test files patch
  goal_to_epic.run and goal_to_epic._find_worktree_root with patch.object and
  then call goal_to_epic.main(); that only works while main() resolves those
  names as globals of the goal_to_epic module itself. Moving main() would have
  left those patches rebinding names nothing calls — the stub silently never
  reached. The --ids branch was safe to move by the same test: no test patches
  build_epic_from_ids.

  Pre-split history lives in goal_to_epic.py's DECISION HISTORY block (the
  2026-07-20 ACD-1200b-4 and 2026-08-12 BO-2600a-5 entries).
  (#TICKETLESS reason=file-size-decomposition-refactor)
====================================================================
"""
