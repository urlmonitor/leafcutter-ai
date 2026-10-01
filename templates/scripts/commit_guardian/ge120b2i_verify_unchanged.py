"""
MODULE: ge120b2i_verify_unchanged
GOAL: CLI that captures a per-check verdict baseline against the shared GE-120
    provoking fixture in a real deployed-only working copy, and later
    re-verifies that every check's verdict is unchanged, compared strictly by
    check id (never in aggregate).
BUSINESS CONTEXT: GE-120b-2-i's own criterion is "adopting the shared
    prerequisite-resolution facility (GE-120b-2) does not change what any
    check finds". That claim is only evidence if the baseline was captured by
    EXECUTION before GE-120b-2's first line landed — a baseline reconstructed
    from the check sources afterwards would agree with the change by
    construction, which this AC's own coverage note explicitly forbids.
ARCHITECTURE: Two subcommands, both delegating the actual isolated-copy
    mechanics to unit_tests.portability._deployed_check_harness.
    DeployedCheckHarness (GE-120c-1) — this module never builds its own
    ad-hoc before/after apparatus, per this AC's own it_requirements.

    capture --repo-root PATH --baseline-path PATH
        Builds one fresh deployed-only working copy at the CURRENT tree
        state via harness.create_second_copy(), stages the shared provoking
        fixture (unit_tests.portability._ge120_provoking_fixture.stage) into
        it, runs every hooks_manifest check from that copy's OWN deployed
        manifest against the DEPLOYED layout (never templates/, per ADR-001),
        and writes a JSON baseline keyed by check id.

    verify --repo-root PATH --baseline-path PATH
        Re-stages the SAME fixture into a FRESH deployed-only working copy of
        the CURRENT tree, re-runs every check, and prints the current sweep
        as a JSON object on stdout (so downstream tests can both grep check
        ids out of it and json.loads() it). Human-readable per-check
        agreement/disagreement detail goes to stderr. Exits 0 only when every
        check id present in the baseline has an unchanged status in the
        current run; exits 1 otherwise, or when --baseline-path does not
        exist (naming the missing path so the failure is legible).

    Both subcommands read the check-id set from the SECOND COPY's own
    deployed commit_guardian.json — the real manifest a commit in that copy
    would actually run — never a hard-coded list.

DECISION HISTORY
====================================================================
- 2026-09-08 [python-coder/GE-120b-2-i]: Initial implementation. GE-120b-2
  (the shared-resolution migration this AC measures) is still work_status:
  todo — see this module's own sign-off comment on the ticket for the honest
  residual list of checks the shared fixture does not yet provoke, and for
  why the four verdict-comparison tests in
  unit_tests/portability/test_ge_120b_2_i.py are correctly left RED (no
  post-sweep state exists yet to compare a baseline against).
====================================================================
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

_DEPLOYED_MANIFEST_REL = Path(".leafcutter") / "scripts" / "commit_guardian" / "commit_guardian.json"


def _import_harness_and_fixture(repo_root: Path):
    """Import the GE-120c-1 harness and the shared provoking fixture.

    Both modules live under `<repo_root>/unit_tests/portability/`, which is
    inserted onto `sys.path` so this script can import them regardless of
    whether it is itself running from `templates/` or a deployed
    `.leafcutter/scripts/commit_guardian/` copy.

    Args:
        repo_root: Root of the tree under test (the `--repo-root` argument).

    Returns:
        Tuple of (harness_module, fixture_module).
    """
    portability_dir = repo_root / "unit_tests" / "portability"
    sys.path.insert(0, str(portability_dir))
    import _deployed_check_harness as dch  # type: ignore[import]
    import _ge120_provoking_fixture as fixture  # type: ignore[import]

    return dch, fixture


def _git_rev_parse_head(repo_root: Path) -> str:
    """Return `git rev-parse HEAD` for `repo_root`.

    Args:
        repo_root: Repository root to resolve HEAD for.

    Returns:
        The current commit SHA as a string, or "UNKNOWN" when git fails.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("git rev-parse HEAD failed for %s: %s", repo_root, exc)
        return "UNKNOWN"
    if result.returncode != 0:
        return "UNKNOWN"
    return result.stdout.strip() or "UNKNOWN"


def _read_deployed_hooks(working_copy_dir: Path) -> list[dict]:
    """Read hooks_manifest.hooks[] from the working copy's DEPLOYED manifest.

    Reads `.leafcutter/scripts/commit_guardian/commit_guardian.json` inside
    `working_copy_dir` — the real deployed copy a commit there would run
    against — never a hard-coded set and never `templates/`.

    Args:
        working_copy_dir: Root of the deployed-only working copy.

    Returns:
        List of hook definition dicts as they appear in the manifest.
    """
    manifest_path = working_copy_dir / _DEPLOYED_MANIFEST_REL
    try:
        raw = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not read deployed manifest at %s: %s", manifest_path, exc)
        raise
    data = json.loads(raw)
    return list(data.get("hooks_manifest", {}).get("hooks", []))


def _staged_paths(working_copy_dir: Path) -> list[str]:
    """Return every path the fixture staged, via the real git index.

    Args:
        working_copy_dir: Root of the working copy to inspect.

    Returns:
        Sorted list of repo-relative staged path strings.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(working_copy_dir), "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        logger.warning("git diff --cached failed in %s: %s", working_copy_dir, exc)
        raise
    return sorted(p for p in result.stdout.splitlines() if p.strip())


def _args_for_hook(hook: dict, staged: list[str]) -> list[str]:
    """Compute the filename arguments a real commit would pass this hook.

    Mirrors pre-commit's own behaviour: only hooks with `pass_filenames:
    true` receive positional file arguments, and only staged paths matching
    the hook's own `files` regex (when present) are passed.

    Args:
        hook: One hook definition dict from the manifest.
        staged: Every path staged in the working copy.

    Returns:
        The filename arguments this hook should receive.
    """
    if not hook.get("pass_filenames", False):
        return []
    pattern = hook.get("files")
    if not pattern:
        return staged
    regex = re.compile(pattern)
    return [p for p in staged if regex.search(p)]


def _run_sweep(dch_module, fixture_module, repo_root: Path) -> dict:
    """Build a fresh deployed-only working copy, stage the fixture, and run
    every manifest check against it.

    Args:
        dch_module: The imported `_deployed_check_harness` module.
        fixture_module: The imported `_ge120_provoking_fixture` module.
        repo_root: Root of the tree under test.

    Returns:
        `{"captured_at_sha": str, "checks": {check_id: {"status", "output"}}}`.
    """
    harness = dch_module.DeployedCheckHarness(repo_root=repo_root)
    sha = _git_rev_parse_head(repo_root)

    with tempfile.TemporaryDirectory(prefix="ge120b2i_sweep_") as tmp:
        working_copy = Path(tmp) / "working_copy"
        harness.create_second_copy(working_copy)
        fixture_module.stage(working_copy)

        hooks = _read_deployed_hooks(working_copy)
        staged = _staged_paths(working_copy)

        checks: dict[str, dict] = {}
        for hook in hooks:
            check_id = hook.get("id")
            entry_template = hook.get("entry", "")
            args = _args_for_hook(hook, staged)
            outcome = harness.invoke_check(working_copy, entry_template, args)
            checks[check_id] = {"status": outcome.status, "output": outcome.output}

    return {"captured_at_sha": sha, "checks": checks}


def _capture(repo_root: Path, baseline_path: Path) -> int:
    """Run the `capture` subcommand: sweep once, write the baseline JSON.

    Args:
        repo_root: Root of the tree under test.
        baseline_path: Destination path for the baseline JSON artifact.

    Returns:
        Process exit code (0 on success).
    """
    dch, fixture = _import_harness_and_fixture(repo_root)
    baseline = _run_sweep(dch, fixture, repo_root)
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(json.dumps(baseline, indent=2) + "\n", encoding="utf-8")
    print(f"Captured baseline for {len(baseline['checks'])} checks to {baseline_path}")
    return 0


def _verify(repo_root: Path, baseline_path: Path) -> int:
    """Run the `verify` subcommand: sweep again, diff against the baseline.

    Args:
        repo_root: Root of the tree under test.
        baseline_path: Path to a previously captured baseline JSON artifact.

    Returns:
        Process exit code: 0 when every baseline check id is unchanged,
        1 when the baseline is missing or any check id's status differs.
    """
    if not baseline_path.exists():
        print(
            f"ge120b2i_verify_unchanged: baseline not found at {baseline_path} — "
            "run the 'capture' subcommand first.",
            file=sys.stderr,
        )
        return 1

    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    dch, fixture = _import_harness_and_fixture(repo_root)
    current = _run_sweep(dch, fixture, repo_root)

    print(json.dumps(current, indent=2))

    mismatches = []
    for check_id, recorded in baseline.get("checks", {}).items():
        after = current.get("checks", {}).get(check_id)
        if after is None:
            mismatches.append((check_id, recorded.get("status"), "MISSING"))
        elif after.get("status") != recorded.get("status"):
            mismatches.append((check_id, recorded.get("status"), after.get("status")))

    for check_id, before_status, after_status in mismatches:
        print(
            f"[ge120b2i_verify_unchanged] MISMATCH {check_id}: "
            f"baseline={before_status} current={after_status}",
            file=sys.stderr,
        )

    if mismatches:
        print(
            f"[ge120b2i_verify_unchanged] {len(mismatches)} check(s) disagree "
            "with the recorded baseline.",
            file=sys.stderr,
        )
        return 1
    return 0


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        Configured ArgumentParser with `capture` and `verify` subcommands.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("capture", "verify"):
        sub = subparsers.add_parser(name)
        sub.add_argument("--repo-root", required=True)
        sub.add_argument("--baseline-path", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Args:
        argv: Argument list; defaults to `sys.argv[1:]`.

    Returns:
        Process exit code.
    """
    args = _build_parser().parse_args(argv)
    repo_root = Path(args.repo_root)
    baseline_path = Path(args.baseline_path)

    if args.command == "capture":
        return _capture(repo_root, baseline_path)
    return _verify(repo_root, baseline_path)


if __name__ == "__main__":
    sys.exit(main())
