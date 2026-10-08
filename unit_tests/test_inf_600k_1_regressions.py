"""
MODULE: test_inf_600k_1_regressions
GOAL: Regression tests for AC INF-600k-1 (see unit_tests/test_inf_600k_1.py
    for the AC's own 8 test_spec tests, and
    unit_tests/_inf_600k_1_fixtures.py for the shared fixture helpers both
    files import). Split into its own file per check-file-size's flat
    400-content-line cap on new files -- a pure move, no test name, body,
    tag, or assertion changed from where these four tests originally lived
    in test_inf_600k_1.py.
BUSINESS CONTEXT: Three rounds of pr-reviewer findings against the in-flight
    INF-600k-1 implementation, discovered while python-coder was
    concurrently fixing production code in this same worktree. Each test's
    own docstring records the exact traceback / behavior observed against
    the in-flight code at test-authoring time; every assertion pins the
    DEFECT'S SYMPTOM, not any particular WIP intermediate state, so each
    stays a meaningful regression guard regardless of which exact line
    python-coder's eventual fix touches.

    Round 2 (two defects):
      1. Fresh clone, no build output: `scripts/commit_guardian/` is
         GITIGNORED build output, deployed by `build_commit_guardian()` from
         `templates/scripts/commit_guardian/`. On a fresh clone this
         directory does not exist on disk at all. If any module
         `registry_validator.py` imports at MODULE LEVEL resolved itself
         relative to that gitignored directory (a `sys.path.insert()` onto
         it followed by a bare import of a sibling module),
         `python scripts/build.py --validate-only` crashed with
         `ModuleNotFoundError` before `build.py`'s own `main()` even ran --
         and `check_agent_registry.py`'s pre-commit wrapper around the same
         import caught that `ModuleNotFoundError` via a broad
         `except ImportError`, silently SKIPPING registry validation
         entirely instead of failing loudly or degrading safely.
         `test_build_validate_only_does_not_crash_on_fresh_clone_with_no_build_output`
         covers this.
      2. Hook root independent of cwd:
         `check_agent_spawn_consistency.py`'s `is_recognized_external_caller(...)`
         call sites resolved the package root as `Path.cwd()` -- not via
         this same file's own `_get_repo_root()` helper (already used
         elsewhere in that file for the card<->registry mirror check's
         cards-directory resolution). A real package root must not depend
         on the hook process's current working directory.
         `test_hook_resolves_workflow_directory_independent_of_cwd` covers
         this.

    Round 3 (one defect): hooks/-nested caller derives the wrong
    workspace-parent root. `_resolve_root.candidate_manifest_roots(hook_file)`
    computed `deploy_root = hook_file.parents[2]`, assuming `hook_file` sits
    directly at `.../scripts/commit_guardian/<file>.py`.
    `check_agent_spawn_consistency.py` lives one level deeper, at
    `commit_guardian/hooks/`, so for THAT caller the arithmetic was off by
    one: the derived "workspace root" collapsed to the repo root itself
    instead of the repo's own parent -- the TRUE workspace-parent root,
    where an outer consumer project's `.build_manifest.json` sits as a
    SIBLING of the git repo (not nested inside it). See
    docs/known-issues/commit-guardian/open-high-ki-cg-20260831-manifest-
    shadowing.md and unit_tests/commit_guardian/test_ge_118b_drift_manifest_
    resolution.py for the sibling-manifest layout this mirrors, and
    unit_tests/commit_guardian/_ge_113c_1_vi_fixtures.py's `deploy_hook()`
    for the "deploy a real copy at its real relative depth, run it as a
    real subprocess" convention this file follows.
    `test_hooks_nested_caller_resolves_workspace_parent_manifest_like_top_level_caller`
    (direct resolution) and
    `test_deployed_hook_accepts_workflow_via_workspace_parent_manifest_end_to_end`
    (end-to-end subprocess) cover this.

DECISION HISTORY
- 2026-09-28 [test-writer/INF-600k-1]: Initial authoring of all four
    regression tests directly in test_inf_600k_1.py, across three rounds of
    pr-reviewer findings.
- 2026-09-28 [test-writer/INF-600k-1]: Split out to this file (check-file-
    size's flat 400-line cap on new files). Pure move: no test name, body,
    tag, or assertion changed.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from _inf_600k_1_fixtures import (
    _build_fresh_clone_fixture,
    _build_workspace_parent_fixture,
    _card_text,
    _copy_real_workflow,
    _init_git_repo,
    _make_agent,
    _run_hook,
    _run_resolve_root_probe,
    _stage_all,
    _write_registry,
)


def test_build_validate_only_does_not_crash_on_fresh_clone_with_no_build_output():
    # covers: INF-600k-1
    # angle: failure
    """pr-reviewer defect 1: on a fresh clone, `scripts/commit_guardian/`
    (gitignored build output, deployed by `build_commit_guardian()` from
    `templates/scripts/commit_guardian/`) does not exist on disk at all --
    `build.py` has never run. If any module `registry_validator.py` imports
    at MODULE LEVEL resolves itself relative to that gitignored directory
    (e.g. a `sys.path.insert()` onto `scripts/commit_guardian/` followed by
    a bare import of a sibling module), `python scripts/build.py
    --validate-only` crashes with `ModuleNotFoundError` before `build.py`'s
    own `main()` even runs -- and `scripts/commit_guardian/
    check_agent_registry.py`'s pre-commit wrapper around the same import
    catches that `ModuleNotFoundError` via a broad `except ImportError`,
    silently SKIPPING registry validation entirely instead of failing
    loudly or degrading safely.

    FIXTURE: see `_build_fresh_clone_fixture()` -- this repo's own HEAD
    tree via `git archive` (so no gitignored build output is present,
    exactly like a real fresh clone), with every tracked-but-modified
    file's CURRENT working-tree content overlaid on top, plus every
    untracked production-source file under `scripts/` or `templates/`
    overlaid on top too (the in-flight fix's new module(s) are untracked
    while python-coder is still working).

    Reproduced against the in-flight code at test-authoring time
    (2026-09-28, before python-coder's `commit_guardian_module_loader.py`
    fix landed): running this exact fixture-building + subprocess sequence
    produced
    ``Traceback ... File "scripts/registry_validator.py", line 37 ...
    ModuleNotFoundError: No module named 'agent_spawn_external_callers'``.
    python-coder may fix this before or after this test is read -- the
    assertion pins the DEFECT'S SYMPTOM (an import-time
    `ModuleNotFoundError` crashing `build.py --validate-only` outright), not
    any particular WIP intermediate state, so it remains a correct
    regression guard either way.
    """
    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp)
        overlay = _build_fresh_clone_fixture(dest)

        assert not (dest / "scripts" / "commit_guardian").exists(), (
            "fixture must reproduce a fresh clone: scripts/commit_guardian/ "
            "(gitignored build output) must be absent"
        )
        assert not (dest / ".leafcutter").exists(), (
            "fixture must reproduce a fresh clone: .leafcutter/ must be absent"
        )

        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run(
            [sys.executable, "scripts/build.py", "--validate-only"],
            cwd=str(dest),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=120,
        )
        combined = result.stdout + result.stderr

        assert "ModuleNotFoundError" not in combined, (
            f"build.py --validate-only must not crash on an import-time "
            f"ModuleNotFoundError on a fresh clone with no build output; "
            f"overlay={overlay} returncode={result.returncode} output:\n{combined}"
        )


def test_hook_resolves_workflow_directory_independent_of_cwd():
    # covers: INF-600k-1
    # angle: failure
    """pr-reviewer defect 2: `check_agent_spawn_consistency.py`'s
    `is_recognized_external_caller(...)` call sites currently resolve the
    package root as `Path.cwd()` -- NOT via this same file's own
    `_get_repo_root()` helper (already used elsewhere in this file for the
    card<->registry mirror check's cards-directory resolution). A real
    package root must not depend on the hook process's current working
    directory: this test runs the hook with `cwd` set to a REAL
    subdirectory of the fixture git repo (`<repo>/docs`) and asserts:

      1. A real workflow filename in `spawned_by` is still ACCEPTED (today
         it is wrongly REJECTED with `cwd=<repo>/docs`, because
         `<repo>/docs/templates/workflows-js/` does not exist, so the real
         workflow file cannot be found from that cwd even though the exact
         same fixture is accepted when cwd is the repo root -- see
         `test_real_workflow_filename_in_spawned_by_is_accepted_by_both_checks`
         in test_inf_600k_1.py, which is the identical fixture run from the
         repo root).
      2. A nonexistent workflow filename remains REJECTED regardless of
         cwd (the negative guarantee must not depend on cwd either).

    Reproduced against the in-flight code at test-authoring time: running
    part (1)'s exact fixture with `cwd` at the repo root passes (exit 0);
    running the IDENTICAL fixture with `cwd` at `<repo>/docs` fails (exit 1,
    stderr: "...registry entry shows fast-lane-ship.js spawns it, but the
    card does not show it") -- the only variable changed between the two
    runs is `cwd`.
    """
    card_no_edge = _card_text("spawner-agent")

    # -- Part 1: a real workflow filename must be accepted regardless of cwd.
    with tempfile.TemporaryDirectory() as tmp:
        repo = Path(tmp)
        _init_git_repo(repo)
        _write_registry(repo, [_make_agent("spawner-agent", spawned_by=["fast-lane-ship.js"])])
        _copy_real_workflow(repo / "templates" / "workflows-js", "fast-lane-ship.js")
        cards_dir = repo / "docs" / "agents" / "cards"
        cards_dir.mkdir(parents=True)
        (cards_dir / "spawner-agent.card.md").write_text(card_no_edge, encoding="utf-8")
        _stage_all(repo)

        subdir = repo / "docs"
        assert subdir.is_dir(), "fixture must have a real subdirectory to cd into"

        result = _run_hook(subdir)
        assert result.returncode == 0, (
            f"hook must accept a real workflow filename regardless of cwd; "
            f"cwd={subdir} exit={result.returncode} stderr={result.stderr!r}"
        )

    # -- Part 2: a nonexistent workflow filename must still be rejected.
    with tempfile.TemporaryDirectory() as tmp2:
        repo = Path(tmp2)
        _init_git_repo(repo)
        _write_registry(repo, [_make_agent("spawner-agent", spawned_by=["nonexistent-flow.js"])])
        (repo / "templates" / "workflows-js").mkdir(parents=True)
        cards_dir = repo / "docs" / "agents" / "cards"
        cards_dir.mkdir(parents=True)
        (cards_dir / "spawner-agent.card.md").write_text(card_no_edge, encoding="utf-8")
        _stage_all(repo)

        subdir = repo / "docs"
        result = _run_hook(subdir)
        assert result.returncode != 0, (
            f"hook must still reject a nonexistent workflow filename regardless of "
            f"cwd; cwd={subdir}"
        )
        assert "nonexistent-flow.js" in result.stderr


def test_hooks_nested_caller_resolves_workspace_parent_manifest_like_top_level_caller():
    # covers: INF-600k-1
    # angle: failure
    """pr-reviewer defect 3: `_resolve_root.candidate_manifest_roots(hook_file)`
    computes `deploy_root = hook_file.parents[2]`, assuming `hook_file` sits
    directly at `.../scripts/commit_guardian/<file>.py`. `check_agent_spawn_
    consistency.py` lives one level deeper, at `commit_guardian/hooks/`, so
    for THAT caller the derived `workspace_root` collapses to the repo root
    itself instead of the repo's own parent -- the true workspace-parent
    root where an outer consumer project's `.build_manifest.json` sits as a
    SIBLING of the git repo (not nested inside it). `check_agent_registry.py`
    (not nested under `hooks/`) derives the correct workspace root from the
    exact same real, deployed `_resolve_root.py` -- this test proves the two
    callers currently DISAGREE on a fixture where the manifest can only be
    found via the correct (non-collapsed) workspace root.

    FIXTURE: see `_build_workspace_parent_fixture()` -- a real workspace
    directory holding a real git repo (`consumer-project/`, where both hooks
    are deployed at their REAL relative depths and where `config/
    agent_registry.json` + the matching card are staged) and a REAL sibling
    package directory (`leafcutter-ai/`, holding the real
    `templates/workflows-js/fast-lane-ship.js`), tied together by a real
    `.build_manifest.json` at the workspace root
    (`{"package_root": "leafcutter-ai"}`) -- exactly the sibling-manifest
    shape `docs/known-issues/commit-guardian/open-high-ki-cg-20260831-
    manifest-shadowing.md` and `test_ge_118b_drift_manifest_resolution.py`
    document for this repo's real production layout. The git repo and the
    vendored package are deliberately DIFFERENT directories (not one nested
    in the other) so a fallback to bare `Path.cwd()` cannot accidentally
    find the real file and mask the resolution bug.

    Both `_resolve_root.candidate_manifest_roots()` calls below run the
    REAL, deployed `_resolve_root.py` (loaded by file path in a subprocess
    with cwd set to the fixture's git repo, so `find_project_root()`'s
    `git rev-parse --show-toplevel` resolves the FIXTURE repo, never this
    actual dev worktree) against each hook's own REAL deployed path.
    """
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp)
        fixture = _build_workspace_parent_fixture(workspace)
        resolved_package_dir = fixture["package_dir"].resolve()

        # Sanity: guard against a vacuous pass -- the manifest must genuinely
        # be absent from the location the BUGGY (collapsed) resolution would
        # search, or this test could not distinguish fixed from unfixed.
        collapsed_wrong_location = fixture["consumer"] / ".build_manifest.json"
        assert not collapsed_wrong_location.exists(), (
            "Test setup bug: the buggy collapsed-to-repo-root location must "
            "not coincidentally hold a manifest."
        )

        control = _run_resolve_root_probe(
            fixture["resolve_root_module"], fixture["registry_hook"], fixture["consumer"]
        )
        assert control["package_root"] == str(resolved_package_dir), (
            f"control (non-nested check_agent_registry.py) must resolve the real "
            f"package root via the workspace-parent manifest; got {control}"
        )

        nested = _run_resolve_root_probe(
            fixture["resolve_root_module"], fixture["hooks_hook"], fixture["consumer"]
        )
        assert str(workspace.resolve()) in nested["roots"], (
            f"hooks/-nested candidate_manifest_roots() must include the true "
            f"workspace root {workspace.resolve()}, exactly like the non-nested "
            f"caller's roots do; got {nested['roots']}"
        )
        assert nested["package_root"] == str(resolved_package_dir), (
            f"hooks/-nested resolve_package_root() must resolve the SAME package "
            f"root as the non-nested caller ({resolved_package_dir}); got {nested}"
        )


def test_deployed_hook_accepts_workflow_via_workspace_parent_manifest_end_to_end():
    # covers: INF-600k-1
    # angle: failure
    """End-to-end companion to the direct-resolution test above: the REAL
    deployed `check_agent_spawn_consistency.py`, run as a real subprocess at
    its genuine `commit_guardian/hooks/` depth with cwd at the fixture's git
    repo, must accept `fast-lane-ship.js` in `spawned_by` when the real file
    is only reachable through the workspace-parent manifest (see
    `_build_workspace_parent_fixture()` -- the git repo and the vendored
    package are different directories, so a `Path.cwd()` fallback cannot
    accidentally paper over the resolution bug).
    """
    with tempfile.TemporaryDirectory() as tmp:
        workspace = Path(tmp)
        fixture = _build_workspace_parent_fixture(workspace)

        result = _run_hook(fixture["consumer"], hook_path=fixture["hooks_hook"])
        assert result.returncode == 0, (
            f"the deployed hooks/-nested hook must accept a real workflow filename "
            f"reachable only via the workspace-parent manifest; "
            f"exit={result.returncode} stderr={result.stderr!r}"
        )
