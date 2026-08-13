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
ARCHITECTURE: Four public symbols consumed by tests and the CLI:
    check_staged_done_proofs(staged_yaml_paths, *, test_root) -> list[dict]
        STATIC pre-commit check. Scans test_root for covers tags; returns
        violation dicts for done ACs that have no tag. No subprocess calls.
    check_all_done_acs(*, ac_root, test_root) -> list[dict]
        CI-authoritative check. Calls verify_done_eligible (from done_proof)
        for every done AC under ac_root; returns violation dicts for ineligible
        ACs. ACs with ``test_required: false`` are silently exempted — they do
        not require a covers-tagged test (documentation/prompt-convention ACs).
        Invokes pytest as a subprocess via the done_proof engine.
    check_changed_done_acs(changed_yaml_paths, *, ac_root, test_root) -> list[dict]
        PR-scoped CI check. Calls verify_done_eligible only for done ACs in the
        provided changed_yaml_paths list; never scans the full store. ACs with
        ``test_required: false`` are silently exempted from the covers-tag
        mandate. Makes it safe to promote to a required gate without failing on
        legacy done ACs that predate the covers-tag mandate (BO-2500b-3).
    main(argv) -> int
        CLI entry point. --mode precommit (default), --mode ci, or
        --mode ci-changed (with --base <ref>, default origin/main).

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

from _resolve_root import find_project_root  # noqa: E402

# ---------------------------------------------------------------------------
# Fail-safe top-level import so ``verify_done_eligible`` is a module-level
# attribute that unittest.mock.patch can replace.  Falls back to None when
# ``done_proof`` is not importable (e.g. the templates/ source layout whose
# sibling ac_store/ contains only .gitkeep).  The _load_verify_done_eligible()
# helper below is kept as the None-fallback path.
# ---------------------------------------------------------------------------
try:
    _ac_store = _HERE.parent / "ac_store"
    if str(_ac_store) not in sys.path:
        sys.path.insert(0, str(_ac_store))
    from done_proof import verify_done_eligible
    # Import the shared covers-tag seam (BO-2500e-1) — handles both
    # Python "# covers:" and JavaScript/TypeScript "// covers:".
    from test_enforcement import COVERS_TAG_RE
except (ImportError, ModuleNotFoundError):
    # Fallback: define the unified regex locally when test_enforcement is absent
    # (e.g. in a templates/ source layout with no deployed ac_store neighbour).
    COVERS_TAG_RE = re.compile(r"(?:#|//)\s*covers:\s*(\S+)")

    def verify_done_eligible(*args, **kwargs):
        """Lazy shim used when done_proof is not importable at module load.

        Keeps ``verify_done_eligible`` a real, patchable module-level attribute
        (so unittest.mock.patch("check_done_proof.verify_done_eligible") always
        takes effect) while deferring the real import until first call, resolved
        via the sibling ac_store in the deployed layout.
        """
        return _load_verify_done_eligible()(*args, **kwargs)


def _load_verify_done_eligible():
    """Import ``done_proof.verify_done_eligible`` from the sibling ac_store.

    Serves as the None-fallback when the top-level import failed (e.g. in the
    templates/ source layout where ``scripts/ac_store/done_proof.py`` is
    absent) or when the module attribute is None.  Call sites read the module
    global ``verify_done_eligible`` first and only invoke this helper when it
    is None, so that ``unittest.mock.patch("check_done_proof.verify_done_eligible",
    ...)`` takes effect without requiring done_proof to be importable at test
    collection time.

    Returns:
        The ``verify_done_eligible`` callable from the ac_store ``done_proof`` module.
    """
    ac_store = _HERE.parent / "ac_store"
    if str(ac_store) not in sys.path:
        sys.path.insert(0, str(ac_store))
    from done_proof import verify_done_eligible

    return verify_done_eligible

# Directory names excluded from all test-file scanning (both .py and .ts/.tsx).
# Prevents traversal into node_modules and other non-test subtrees.
_EXCLUDED_SCAN_DIRS: frozenset[str] = frozenset(
    {
        "node_modules",
        ".next",
        "dist",
        "coverage",
        ".git",
        "__pycache__",
        ".venv",
    }
)

# Default paths relative to the project root (used in main() when no explicit
# --ac-root / --test-root argument is supplied).
_DEFAULT_AC_ROOT = "docs/acceptance-criteria"
_DEFAULT_TEST_ROOT = "unit_tests"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _collect_all_covered_ids(test_root: Path) -> set[str]:
    """Scan *test_root* recursively and return all AC ids referenced in covers tags.

    Reads every ``*.py``, ``*.ts``, and ``*.tsx`` file under *test_root``, extracting
    the id from every ``# covers: <id>`` (Python) or ``// covers: <id>``
    (TypeScript/JavaScript) comment line.  Uses the shared :data:`COVERS_TAG_RE`
    seam (BO-2500e-1) so both syntax forms are recognised.

    Directories named ``node_modules``, ``.next``, ``dist``, ``coverage``,
    ``.git``, ``__pycache__``, and ``.venv`` are excluded from traversal.

    This is a STATIC presence-only scan — no tests are run.  Unreadable files
    are logged to stderr and skipped.

    Args:
        test_root: Root directory to search recursively for test files.

    Returns:
        Set of AC id strings found in ``covers:`` comments.  Empty set when
        *test_root* does not exist or contains no readable test files.
    """
    covered: set[str] = set()
    try:
        py_files = sorted(test_root.rglob("*.py"))
        ts_files = sorted(test_root.rglob("*.ts"))
        tsx_files = sorted(test_root.rglob("*.tsx"))
    except OSError as exc:
        print(
            f"WARNING: check_done_proof: cannot scan {test_root}: {exc}",
            file=sys.stderr,
        )
        return covered

    all_test_files = (
        [f for f in py_files if not any(p in _EXCLUDED_SCAN_DIRS for p in f.parts)]
        + [f for f in ts_files if not any(p in _EXCLUDED_SCAN_DIRS for p in f.parts)]
        + [f for f in tsx_files if not any(p in _EXCLUDED_SCAN_DIRS for p in f.parts)]
    )

    for test_file in all_test_files:
        try:
            text = test_file.read_text(encoding="utf-8")
        except OSError as exc:
            print(
                f"WARNING: check_done_proof: cannot read {test_file}: {exc}",
                file=sys.stderr,
            )
            continue
        for match in COVERS_TAG_RE.finditer(text):
            covered.add(match.group(1))
    return covered


def _is_gated_ac_yaml(rel: Path) -> bool:
    """True when a repo-relative path is a real AC YAML the done-proof gate
    should evaluate.

    Excludes non-YAML files, paths outside an ``acceptance-criteria`` tree, and
    bundled fixture/demo copies (e.g. under
    ``leafcutter-web/fixtures/docs/acceptance-criteria/**``) — those are canned
    data for the Atlas to render in mock mode, not real store entries, so the
    gate must never evaluate them.
    """
    if rel.suffix != ".yaml":
        return False
    if "acceptance-criteria" not in rel.parts:
        return False
    if "fixtures" in rel.parts:
        return False
    return True


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
        if not _is_gated_ac_yaml(rel):
            continue
        abs_path = project_root / rel
        if abs_path.exists():
            result.append(abs_path)
    return result


def _get_changed_ac_yaml_paths(base_ref: str, project_root: Path) -> list[Path]:
    """Return absolute paths of AC YAML files changed since *base_ref* via git diff.

    Runs ``git diff --name-only <base_ref>...HEAD`` and filters for files under
    ``docs/acceptance-criteria/`` with a ``.yaml`` extension.  Git errors are
    logged and an empty list is returned (fail-open for the diff step).

    Args:
        base_ref: Git reference to diff against (e.g., ``"origin/main"``).
        project_root: Absolute path to the project (git) root.

    Returns:
        List of absolute Paths for changed AC YAML files.  Returns an empty list
        when the git command fails or no matching files were changed.
    """
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
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
        if not _is_gated_ac_yaml(rel):
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
                        f"no '# covers: {ac_id_str}' or '// covers: {ac_id_str}' "
                        f"tag found anywhere under {test_root}"
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

    ACs with ``test_required: false`` (the Python boolean ``False``, not the
    string ``"false"``) are silently exempted and never passed to
    verify_done_eligible.  This covers documentation ACs and prompt-convention
    ACs where a covers-tagged test is structurally impossible.  An absent or
    ``True`` value for ``test_required`` is always enforced.

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
        if data.get("test_required") is False:
            continue
        verdict = verify_done_eligible(ac_id_str, ac_root=ac_root, test_root=test_root)
        if not verdict.get("eligible"):
            violations.append(
                {
                    "ac_id": ac_id_str,
                    "reason": verdict.get("reason", "coverage gate failed"),
                }
            )
    return violations


def check_changed_done_acs(
    changed_yaml_paths: list[Path],
    *,
    ac_root: Path,
    test_root: Path,
) -> list[dict]:
    """PR-scoped CI check: done-proof evaluated only for changed AC yaml paths.

    For each AC YAML path in *changed_yaml_paths* whose ``work_status`` is
    ``"done"``, calls :func:`done_proof.verify_done_eligible` to confirm the
    AC has a covers-tagged, passing test.  ACs NOT in *changed_yaml_paths* are
    never evaluated — this scoping invariant makes it safe to promote this mode
    to a required CI gate without failing on pre-existing done ACs that predate
    the covers-tag mandate (BO-2500b-3).

    ACs with ``test_required: false`` (the Python boolean ``False``, not the
    string ``"false"``) are silently exempted and never passed to
    verify_done_eligible.  This covers documentation ACs and prompt-convention
    ACs where a covers-tagged test is structurally impossible.  An absent or
    ``True`` value for ``test_required`` is always enforced.

    Args:
        changed_yaml_paths: AC YAML paths changed in the current PR (e.g. from
            ``git diff --name-only <base>...HEAD``).  Only these paths are
            evaluated.  Pre-existing done ACs not in this list are silently
            ignored.
        ac_root: Root directory of the AC YAML store; passed to
            :func:`done_proof.verify_done_eligible`.
        test_root: Root directory to scan for covers-tagged tests; passed to
            :func:`done_proof.verify_done_eligible`.

    Returns:
        List of violation dicts, each containing ``"ac_id"`` (str) and
        ``"reason"`` (str, non-empty).  An empty list means no violations among
        the changed done ACs.
    """
    violations: list[dict] = []
    for yaml_path in changed_yaml_paths:
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
        if data.get("test_required") is False:
            continue
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
        choices=["precommit", "ci", "ci-changed"],
        default="precommit",
        help=(
            "Operating mode: 'precommit' (fast static, default), 'ci' (full store), "
            "or 'ci-changed' (PR-scoped; only changed AC yamls are evaluated)."
        ),
    )
    parser.add_argument(
        "--base",
        metavar="REF",
        default="origin/main",
        help=(
            "Git base ref for diff in ci-changed mode "
            "(default: origin/main). Ignored in precommit and ci modes."
        ),
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

    Dispatches to check_staged_done_proofs (precommit mode),
    check_all_done_acs (ci mode), or check_changed_done_acs (ci-changed mode)
    based on --mode.  Prints each violation's ac_id and reason; exits 1 when
    violations are found, 0 otherwise.

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
    elif args.mode == "ci-changed":
        changed_paths = _get_changed_ac_yaml_paths(args.base, project_root)
        try:
            violations = check_changed_done_acs(
                changed_paths, ac_root=ac_root, test_root=test_root
            )
        except (OSError, ValueError, KeyError) as exc:
            print(
                f"[check-done-proof] CI-changed checker error (fail-closed): {exc}",
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
