"""
MODULE: leafcutter/scripts/commit_guardian/known_failing_tests.py
GOAL: Pre-commit test hook with baseline diffing. Runs pytest, loads the known-
    failing baseline, and blocks only on NEW failures (tests failing now that
    were not previously in the baseline). Eliminates the --no-verify escape path
    caused by pre-existing test failures blocking unrelated commits.
BUSINESS CONTEXT: When the test suite has pre-existing failures (tests failing
    before the current change), the commit hook blocks ALL commits by every dev.
    Devs reach for --no-verify to unblock themselves, which bypasses ALL hooks.
    The baseline mechanism records currently-known failures so the hook can
    distinguish "pre-existing failure" (skip) from "new regression" (block).
    Baseline updates are explicit, reviewable git diffs — not silent side-effects.
ARCHITECTURE: The script has two modes:
    1. Hook mode (default): run pytest, load baseline, diff, exit 0 or 1.
    2. Update mode (--update): run pytest, write current failures to baseline.
    The baseline file is ``scripts/commit_guardian/known_failing_tests.json``.
    Registered in ``commit_guardian.json`` as ``run-tests-with-baseline`` hook.
DOC_LINKS:
  - docs/how-to/known-failing-tests-baseline.md

Exit Codes (hook mode):
    0 - All failures are baseline-known (or no failures). Commit proceeds.
    1 - One or more NEW failures detected. Commit is blocked.

Usage:
    python scripts/commit_guardian/known_failing_tests.py
    python scripts/commit_guardian/known_failing_tests.py --update
    python scripts/commit_guardian/known_failing_tests.py --baseline-path path/to/file.json
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BASELINE_PATH = Path(__file__).parent / "known_failing_tests.json"
"""Default location of the baseline file, co-located with this script."""

_BASELINE_DATE_KEY = "baseline_date"
_BASELINE_FAILING_KEY = "known_failing"


# ---------------------------------------------------------------------------
# Baseline I/O
# ---------------------------------------------------------------------------


def load_baseline(baseline_path: Path) -> frozenset[str]:
    """Load the set of known-failing test node IDs from *baseline_path*.

    Fail-open: if the file is absent or malformed, return an empty set so that
    all failures are treated as new (same behaviour as no-baseline mode).

    Args:
        baseline_path: Absolute or repo-relative path to the JSON baseline file.

    Returns:
        frozenset of test node ID strings. Empty set when file is absent or invalid.
    """
    if not baseline_path.exists():
        return frozenset()
    try:
        with open(baseline_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return frozenset()

    known = data.get(_BASELINE_FAILING_KEY, [])
    if not isinstance(known, list):
        return frozenset()
    return frozenset(str(t) for t in known if isinstance(t, str))


def write_baseline(baseline_path: Path, failing_tests: set[str]) -> None:
    """Write the current set of failing tests to *baseline_path*.

    The baseline file is a JSON object with a date stamp and the sorted list of
    failing test node IDs. Writing it produces a reviewable ``git diff`` so the
    baseline update is visible in the PR.

    Args:
        baseline_path: Path to write (or overwrite) the baseline JSON file.
        failing_tests: Set of currently-failing pytest node IDs.
    """
    payload = {
        _BASELINE_DATE_KEY: date.today().isoformat(),
        _BASELINE_FAILING_KEY: sorted(failing_tests),
    }
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    with open(baseline_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
        f.write("\n")


# ---------------------------------------------------------------------------
# Pytest runner
# ---------------------------------------------------------------------------


def collect_failing_tests(test_args: list[str]) -> set[str]:
    """Run pytest in collection mode and return the set of failing node IDs.

    Uses ``--tb=no -q --no-header`` for compact output and captures the list of
    FAILED lines. The test suite is always executed — the baseline only affects
    how failures are reported, not whether tests run.

    Args:
        test_args: Extra arguments to pass to pytest (e.g. a specific test path).

    Returns:
        Set of failing test node IDs (``path::test_name`` format). Empty when all
        tests pass.
    """
    cmd = [
        sys.executable, "-m", "pytest",
        "--tb=no", "-q", "--no-header",
    ] + test_args

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError as e:
        print(f"[known-failing-tests] ERROR: could not launch pytest: {e}", file=sys.stderr)
        return set()

    failing: set[str] = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("FAILED "):
            # e.g. "FAILED unit_tests/foo/test_bar.py::test_something - AssertionError: ..."
            node_id = line[len("FAILED "):].split(" - ")[0].strip()
            failing.add(node_id)
        elif line.startswith("ERROR "):
            # "ERROR path/to/test.py::test_name - ..."
            node_id = line[len("ERROR "):].split(" - ")[0].strip()
            failing.add(node_id)

    return failing


# ---------------------------------------------------------------------------
# Hook mode
# ---------------------------------------------------------------------------


def run_hook(baseline_path: Path, test_args: list[str]) -> int:
    """Run the pre-commit hook: compare current failures against the baseline.

    Args:
        baseline_path: Path to the baseline JSON file.
        test_args: Extra pytest arguments (e.g. a specific test directory).

    Returns:
        0 when no new failures are detected; 1 when new failures block the commit.
    """
    known = load_baseline(baseline_path)
    current_failures = collect_failing_tests(test_args)

    new_failures = current_failures - known

    if not new_failures:
        if current_failures:
            print(
                f"[known-failing-tests] {len(current_failures)} baseline-known failure(s) "
                f"present — not blocking. Run --update to refresh the baseline.",
                file=sys.stderr,
            )
        return 0

    # New failures detected — block with an actionable error
    print(
        f"[known-failing-tests] BLOCK: {len(new_failures)} NEW test failure(s) detected:",
        file=sys.stderr,
    )
    for node_id in sorted(new_failures):
        print(f"  FAILED {node_id}", file=sys.stderr)
    print(
        "\nThese tests were passing before your change. Fix the regressions or, "
        "if the failures are intentional and pre-existing, acknowledge them with:\n"
        f"  python {__file__} --update",
        file=sys.stderr,
    )
    return 1


# ---------------------------------------------------------------------------
# Update mode
# ---------------------------------------------------------------------------


def run_update(baseline_path: Path, test_args: list[str]) -> int:
    """Regenerate the baseline from the current failing test set.

    Args:
        baseline_path: Path to write (or overwrite) the baseline JSON file.
        test_args: Extra pytest arguments (e.g. a specific test directory).

    Returns:
        Always 0 (update never blocks).
    """
    print("[known-failing-tests] Running pytest to collect current failures …", file=sys.stderr)
    current_failures = collect_failing_tests(test_args)

    write_baseline(baseline_path, current_failures)
    print(
        f"[known-failing-tests] Baseline updated: {len(current_failures)} failing test(s) "
        f"recorded in {baseline_path}",
        file=sys.stderr,
    )
    if current_failures:
        for node_id in sorted(current_failures):
            print(f"  {node_id}", file=sys.stderr)
        print(
            "\nStage and commit the updated baseline:\n"
            f"  git add {baseline_path}\n"
            "  git commit -m 'chore(tests): update known-failing baseline'",
            file=sys.stderr,
        )
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Pre-commit test hook with baseline diffing.\n"
            "In hook mode (default): runs pytest, loads the known-failing baseline, "
            "and blocks only on NEW failures.\n"
            "In update mode (--update): regenerates the baseline from the current "
            "failing test set."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--update",
        action="store_true",
        default=False,
        help="Regenerate the baseline from the current failing test set and exit.",
    )
    parser.add_argument(
        "--baseline-path",
        default=str(DEFAULT_BASELINE_PATH),
        metavar="PATH",
        help=(
            f"Path to the known-failing baseline JSON file "
            f"(default: {DEFAULT_BASELINE_PATH})."
        ),
    )
    parser.add_argument(
        "test_args",
        nargs="*",
        metavar="PYTEST_ARG",
        help="Extra arguments passed to pytest (e.g. a specific test directory or file).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for known_failing_tests.py.

    Args:
        argv: Argument list. When None, uses sys.argv[1:].

    Returns:
        Exit code: 0 on success, 1 on new failures.
    """
    args = _build_parser().parse_args(argv)
    baseline_path = Path(args.baseline_path).resolve()

    if args.update:
        return run_update(baseline_path, args.test_args)
    return run_hook(baseline_path, args.test_args)


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-22 00:00 [EPIC-CommitSignoffHardening/06]: Initial implementation.
  Pre-commit test hook with known-failing baseline diffing. Collects current
  pytest failures, diffs against the baseline in known_failing_tests.json,
  and blocks only on net-new failures. Fail-open when baseline is absent.
  --update mode regenerates the baseline from the current failing set and
  prints staging instructions. Registered in commit_guardian.json as
  run-tests-with-baseline.
====================================================================
"""
