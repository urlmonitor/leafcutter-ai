"""
MODULE: scripts/commit_guardian/check_done_proof.py
GOAL: Enforce mechanical proof-of-done at two layers: a fast static pre-commit
    check (covers-tag PRESENCE only) and an authoritative CI check that runs
    the full verify_done_eligible oracle to confirm every done AC is backed by
    a passing test.
BUSINESS CONTEXT: BO-2500b mandates that no AC may reach work_status:done without
    a covers-tagged, passing test. Pre-commit (BO-2500b-1) is the fast developer
    loop — it checks only that a ``# covers: <ac_id>`` tag EXISTS somewhere in
    the test tree for every newly-done AC (static scan, no pytest). CI (BO-2500b-2)
    is the authoritative backstop: it calls verify_done_eligible for every done AC
    in the store and requires every linked test to PASS — so --no-verify commits
    and hook-config-less worktrees (BO-2500b-1-i) are still caught before merge.
ARCHITECTURE: Three public symbols consumed by tests and the CLI:
    check_staged_done_proofs(staged_yaml_paths, *, test_root) -> list[dict]
        STATIC pre-commit check. Scans test_root for covers tags; returns
        violation dicts for done ACs that have no tag. No subprocess calls.
    check_all_done_acs(*, ac_root, test_root) -> list[dict]
        CI-authoritative check. Calls verify_done_eligible (from done_proof)
        for every done AC under ac_root; returns violation dicts for ineligible
        ACs. Invokes pytest as a subprocess via the done_proof engine.
    main(argv) -> int
        CLI entry point. --mode precommit (default) or --mode ci.

    Root resolution: uses _resolve_root.find_project_root() for project-root
    defaults in main(); sibling-directory lookup (__file__ parent / ac_store)
    for the done_proof import — safe because the directory relationship is fixed
    in both source and deployed layouts.

    Error handling: all I/O wrapped per the Error Handling Policy (Rules 1-3).
    Pre-commit hook fail-open: the if __name__ == '__main__' guard exits 0 on
    unexpected errors so a crash never blocks a commit.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Resolve ac_store so done_proof is importable from commit_guardian context.
# Works in source layout (scripts/commit_guardian/ → parent/ac_store/) and
# deployed layout (.leafcutter/scripts/commit_guardian/ → parent/ac_store/).
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
_AC_STORE_PATH = _HERE.parent / "ac_store"
if str(_AC_STORE_PATH) not in sys.path:
    sys.path.insert(0, str(_AC_STORE_PATH))

from done_proof import verify_done_eligible  # noqa: E402
from _resolve_root import find_project_root  # noqa: E402

_COVERS_TAG_RE = re.compile(r"#\s*covers:\s*(\S+)")

# Default paths relative to the project root (used in main() when no explicit
# --ac-root / --test-root argument is supplied).
_DEFAULT_AC_ROOT = "docs/acceptance-criteria"
_DEFAULT_TEST_ROOT = "unit_tests"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _collect_all_covered_ids(test_root: Path) -> set[str]:
    """Scan *test_root* recursively and return all AC ids referenced in covers tags.

    Reads every ``*.py`` file under *test_root* and extracts the id from every
    ``# covers: <id>`` comment line.  Unreadable files are logged and skipped.

    Args:
        test_root: Root directory to search recursively for ``*.py`` files.

    Returns:
        Set of AC id strings found in ``# covers:`` comments.  Empty set when
        *test_root* does not exist or contains no readable Python files.
    """
    covered: set[str] = set()
    try:
        py_files = sorted(test_root.rglob("*.py"))
    except OSError as exc:
        print(
            f"WARNING: check_done_proof: cannot scan {test_root}: {exc}",
            file=sys.stderr,
        )
        return covered
    for py_file in py_files:
        try:
            text = py_file.read_text(encoding="utf-8")
        except OSError as exc:
            print(
                f"WARNING: check_done_proof: cannot read {py_file}: {exc}",
                file=sys.stderr,
            )
            continue
        for match in _COVERS_TAG_RE.finditer(text):
            covered.add(match.group(1))
    return covered


def _get_staged_ac_yaml_paths(project_root: Path) -> list[Path]:
    """Return absolute paths of staged AC YAML files via ``git diff --cached``.

    Only files within ``docs/acceptance-criteria/`` with a ``.yaml`` extension
    are returned.  Files that no longer exist on disk are skipped.

    Args:
        project_root: Absolute path to the project (git) root.

    Returns:
        List of absolute Paths for staged AC YAML files.  Returns an empty list
        when the git command fails or no matching files are staged.
    """
    try:
        proc = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(
            f"WARNING: check_done_proof: git diff failed: {exc}",
            file=sys.stderr,
        )
        return []
    result: list[Path] = []
    for line in proc.stdout.splitlines():
        rel = Path(line.strip())
        if rel.suffix != ".yaml":
            continue
        if "acceptance-criteria" not in rel.parts:
            continue
        abs_path = project_root / rel
        if abs_path.exists():
            result.append(abs_path)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def check_staged_done_proofs(
    staged_yaml_paths: list[Path],
    *,
    test_root: Path,
) -> list[dict]:
    """Fast static pre-commit check: covers-tag PRESENCE for newly-done ACs.

    For each AC YAML path in *staged_yaml_paths* whose ``work_status`` field
    is ``"done"``, checks whether at least one ``# covers: <ac_id>`` tag exists
    anywhere under *test_root*.  Does NOT invoke pytest — this is a pure
    filesystem scan designed to fit within the latency budget of a pre-commit
    hook.  Only ACs staged as ``done`` are evaluated (bounded blast radius);
    ACs in any other work_status are silently ignored.

    Args:
        staged_yaml_paths: Paths to staged AC YAML files to evaluate.  May
            include non-done ACs — they are skipped automatically.
        test_root: Root directory to search recursively for ``*.py`` files
            containing ``# covers:`` tags.

    Returns:
        List of violation dicts, each containing ``"ac_id"`` (str) and
        ``"reason"`` (str, non-empty).  An empty list means no violations.
    """
    all_covered_ids = _collect_all_covered_ids(test_root)
    violations: list[dict] = []
    for yaml_path in staged_yaml_paths:
        try:
            with open(yaml_path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except (yaml.YAMLError, OSError) as exc:
            print(
                f"WARNING: check_done_proof: cannot read {yaml_path}: {exc}",
                file=sys.stderr,
            )
            continue
        if not isinstance(data, dict):
            continue
        if data.get("work_status") != "done":
            continue
        ac_id = data.get("id")
        if not ac_id:
            continue
        ac_id_str = str(ac_id)
        if ac_id_str not in all_covered_ids:
            violations.append(
                {
                    "ac_id": ac_id_str,
                    "reason": (
                        f"no '# covers: {ac_id_str}' tag found anywhere under {test_root}"
                    ),
                }
            )
    return violations


def check_all_done_acs(
    *,
    ac_root: Path,
    test_root: Path,
) -> list[dict]:
    """CI-authoritative check: every done AC must pass verify_done_eligible.

    Scans *ac_root* recursively for all AC YAML files whose ``work_status`` is
    ``"done"``, then calls :func:`done_proof.verify_done_eligible` for each.
    ACs for which ``eligible`` is ``False`` are reported as violations.

    Unlike the pre-commit check, this function DOES run pytest (via
    verify_done_eligible → subprocess) so that a covers tag whose linked test
    is failing still produces a violation.  This is the authoritative backstop
    that catches commits made with ``--no-verify`` or from worktrees lacking
    hook config (BO-2500b-1-i).

    Args:
        ac_root: Root directory of the AC YAML store to scan recursively.
        test_root: Root directory to scan for ``*.py`` test files containing
            ``# covers:`` tags; passed to verify_done_eligible unchanged.

    Returns:
        List of violation dicts, each containing ``"ac_id"`` (str) and
        ``"reason"`` (str, non-empty).  An empty list means all done ACs are
        eligible.
    """
    violations: list[dict] = []
    try:
        yaml_files = sorted(ac_root.rglob("*.yaml"))
    except OSError as exc:
        print(
            f"WARNING: check_done_proof: cannot scan {ac_root}: {exc}",
            file=sys.stderr,
        )
        return violations
    for yaml_path in yaml_files:
        try:
            with open(yaml_path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except (yaml.YAMLError, OSError) as exc:
            print(
                f"WARNING: check_done_proof: cannot read {yaml_path}: {exc}",
                file=sys.stderr,
            )
            continue
        if not isinstance(data, dict):
            continue
        if data.get("work_status") != "done":
            continue
        ac_id = data.get("id")
        if not ac_id:
            continue
        ac_id_str = str(ac_id)
        verdict = verify_done_eligible(ac_id_str, ac_root=ac_root, test_root=test_root)
        if not verdict.get("eligible"):
            violations.append(
                {
                    "ac_id": ac_id_str,
                    "reason": verdict.get("reason", "coverage gate failed"),
                }
            )
    return violations


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the check_done_proof CLI.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Enforce mechanical proof-of-done (BO-2500b). "
            "pre-commit mode: static covers-tag presence check for staged done ACs. "
            "ci mode: full verify_done_eligible run over every done AC in the store."
        ),
    )
    parser.add_argument(
        "--mode",
        choices=["precommit", "ci"],
        default="precommit",
        help="Operating mode: 'precommit' (fast static, default) or 'ci' (full).",
    )
    parser.add_argument(
        "--ac-root",
        metavar="DIR",
        default=None,
        help=(
            "Root directory of the AC YAML store "
            "(default: <project-root>/docs/acceptance-criteria)."
        ),
    )
    parser.add_argument(
        "--test-root",
        metavar="DIR",
        default=None,
        help=(
            "Root directory to scan for covers-tagged tests "
            "(default: <project-root>/unit_tests)."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the proof-of-done gate.

    Dispatches to check_staged_done_proofs (pre-commit mode) or
    check_all_done_acs (ci mode) based on --mode, prints each violation's
    ac_id and reason, and exits 1 when violations are found.

    Args:
        argv: Argument list.  Defaults to ``sys.argv[1:]`` when ``None``.

    Returns:
        0 when no violations are found; 1 when at least one violation exists.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    project_root = find_project_root()
    ac_root = Path(args.ac_root) if args.ac_root else project_root / _DEFAULT_AC_ROOT
    test_root = (
        Path(args.test_root) if args.test_root else project_root / _DEFAULT_TEST_ROOT
    )

    if args.mode == "ci":
        try:
            violations = check_all_done_acs(ac_root=ac_root, test_root=test_root)
        except (OSError, ValueError, KeyError) as exc:
            print(
                f"[check-done-proof] CI checker error (fail-closed): {exc}",
                file=sys.stderr,
            )
            return 1
    else:
        staged_paths = _get_staged_ac_yaml_paths(project_root)
        violations = check_staged_done_proofs(staged_paths, test_root=test_root)

    if not violations:
        return 0

    for v in violations:
        print(f"[check-done-proof] {v['ac_id']}: {v['reason']}")
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as exc:
        print(f"[check-done-proof] unexpected error, skipping: {exc}", file=sys.stderr)
        sys.exit(0)
