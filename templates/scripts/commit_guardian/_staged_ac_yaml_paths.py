"""
MODULE: _staged_ac_yaml_paths
GOAL: Resolve the set of staged AC YAML paths the done-proof pre-commit gate
    should evaluate.
BUSINESS CONTEXT: check_staged_done_proofs (BO-2500b-1) is the fast static
    pre-commit check: it needs the list of AC YAML files staged in the
    current commit, filtered to real store entries (never bundled fixture/
    demo copies) and, for a merge commit, narrowed to files whose staged
    result actually differs from BOTH parents (a merge stages the entire
    incoming branch, and blocking on inherited-unchanged content would make
    merging impossible without weakening the phantom-done guarantee — see
    :func:`_get_staged_ac_yaml_paths`'s own docstring).
ARCHITECTURE: A sibling module inside templates/scripts/commit_guardian/ --
    build_commit_guardian (scripts/build_phases_lifecycle.py) copies every
    file in that directory verbatim (via `cg_dir.rglob("*")`) to
    <target_root>/scripts/commit_guardian/, so this file needs no entry of
    its own in any hardcoded deploy_map; it deploys purely by being a sibling
    of check_done_proof.py, the same way `_resolve_root.py` already does.
    Relocated out of check_done_proof.py (BP-100n-4-ii-ii) to buy back
    file-size-ratchet headroom after the BO-2500a-1-ii conjunction carve-out
    pushed that file over its baseline -- pure move, no behaviour change.
    check_done_proof.py re-exports both symbols at its own top level, so
    every existing consumer (``from check_done_proof import _is_gated_ac_yaml``,
    ``check_done_proof._get_staged_ac_yaml_paths(...)``) is unaffected; its
    own ``_get_changed_ac_yaml_paths`` (which stayed behind) calls
    :func:`_is_gated_ac_yaml` via that same re-exported name.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


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

    staged_lines = proc.stdout.splitlines()

    # Merge commits: a merge stages the ENTIRE incoming branch, so this
    # PRE-COMMIT presence check would demand a covers tag for every done AC the
    # other side carries — including ones already marked done there without a
    # discoverable tag. The merge inherits those byte-for-byte and can neither
    # improve nor worsen them, so blocking here only makes merging impossible.
    # Narrow to files whose result differs from BOTH parents.
    #
    # This does NOT weaken the phantom-done guarantee. This function feeds only
    # check_staged_done_proofs (the fast, static, staged-only tag-presence
    # check). The authoritative whole-store sweep is check_all_done_acs, which
    # walks ac_root recursively for EVERY done AC and runs verify_done_eligible
    # on each; it never consults the staged set and is untouched by this scope.
    # Same fix as check_ac_limits / check_ac_parent_covered_by / check_ac_schema.
    try:
        merge_probe = subprocess.run(
            ["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        in_merge = merge_probe.returncode == 0
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(
            f"WARNING: check_done_proof: MERGE_HEAD probe failed: {exc}",
            file=sys.stderr,
        )
        in_merge = False

    if in_merge:
        try:
            other = subprocess.run(
                [
                    "git", "diff", "--cached", "--name-only",
                    "--diff-filter=ACM", "MERGE_HEAD",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(
                f"WARNING: check_done_proof: MERGE_HEAD diff failed: {exc}",
                file=sys.stderr,
            )
        else:
            if other.returncode == 0:
                vs_other = {
                    ln.strip() for ln in other.stdout.splitlines() if ln.strip()
                }
                staged_lines = [ln for ln in staged_lines if ln.strip() in vs_other]

    result: list[Path] = []
    for line in staged_lines:
        rel = Path(line.strip())
        if not _is_gated_ac_yaml(rel):
            continue
        abs_path = project_root / rel
        if abs_path.exists():
            result.append(abs_path)
    return result
