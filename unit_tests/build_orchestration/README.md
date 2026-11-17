# unit_tests/build_orchestration/ — shared workspace-maker test support

This directory holds the proof suite for the ADR-018 Amendment 1 "one workspace
maker" (`templates/scripts/worktree.py`) and its related build-orchestration
scripts. This README documents the shared test-support modules ticket 02
(`02_TICKET-20260928-BO-4300-deployed-maker-test-support.md`, AC `BO-4300f-4`
/ `BO-4300f-4-i`) delivers so later ticket authors do not re-derive the same
fixtures.

## The locator: never test a tracked source copy

`_workspace_maker_fixtures.py` resolves the **DEPLOYED** maker — the copy a
real install produces via `python scripts/build.py --target-dir <dir>` — and
refuses to resolve a tracked source copy under this repository's own
`scripts/` or `templates/scripts/` (`TrackedSourceCopyError`). This exists
because a tracked stray copy once became "the thing under test" by accident
(known issue `KI-TQ-20260831`, the mutation probe that landed in the wrong copy).

```python
from unit_tests.build_orchestration._workspace_maker_fixtures import (
    DeployedMakerNotFoundError,
    TrackedSourceCopyError,
    deployed_maker_path,
    ensure_deployed_layout,
    legacy_worktree,
    make_project,
    run_maker,
    starting_points,
)

maker_path = deployed_maker_path()          # raises, never skips, never falls back to templates/
made = make_project(tmp_path, layout="dev")  # {"project": ..., "hub": ..., "landing_place": ...}
result = run_maker(["ensure", "--kind", "scratch", "--slug", "x"], cwd=made["project"])
# result == {"answer": {...}, "exit_code": 0, "stdout": "...", "stderr": "..."}
```

`ensure_deployed_layout()` builds the shared deployed layout **exactly once
per interpreter session** (a module-level cache) — this is the ONE new
`scripts/build.py` spawn site this ticket's own Implementation Notes justify.
Every later BO-4300 maker proof, and `_bo_4300a_1_fixtures.DeployedMakerBuild`
(BO-4300a-1's own fixture module), reuse this same cached layout instead of
spawning their own. **Do not add a second spawn site** — import
`ensure_deployed_layout` instead.

The override seam (`deployed_maker_path(override=...)` / `run_maker(...,
maker_path=...)`) exists **only** for the meta-test that proves a fault in
the deployed copy actually fails a proof — never use it to skip the locator
in an ordinary test.

## Builders (`_workspace_maker_builders.py`, re-exported from
`_workspace_maker_fixtures`)

- `make_project(tmp, layout="dev"|"consumer", stub_build=None, hook="reject"|"accept")`
  builds a real bare hub plus a real project clone with a stub
  `scripts/build.py` that installs a real (never mocked) accept/reject git
  pre-commit hook in well under a second — never the package's own
  `scripts/build.py` (CLAUDE.md "Tests must not spawn their own build.py").
- `starting_points(project)` returns the six BO-4300b-1 starting-point cwds
  (`project_top`, `three_levels_down`, `parent_above`, `sibling_beside`,
  `inside_w1`, `inside_new_workspace`) as real, existing directories —
  building its own two scratch workspaces so `inside_w1` /
  `inside_new_workspace` are always real at call time, independent of
  whatever kind/slug the calling test uses afterwards. **Known limitation**:
  from `parent_above` / `sibling_beside` / `inside_w1`, the maker's `ensure`
  needs `--repo-root` or BO-4300b-1's own child/sibling/marker search (ticket
  04) to resolve the project — `templates/scripts/workspace_root.py` today
  implements only `argument` and `git-common-dir` resolution (BO-4300a-1's
  own documented scope). A caller that spawns the maker from these three cwds
  with no `--repo-root` will get `NO_REPO` until ticket 04 lands.
- `legacy_worktree(project, name, unsent=False, at=None)` is the **one**
  test-side creator of a real, linked `git worktree` — BO-4300f-2's census
  exempts only this helper. Places the worktree at the pre-Q5 legacy location
  (`<parent of project>/worktrees/<name>`) by default, outside the Q5 landing
  root, so later tickets can prove an old workspace is never twinned with a
  maker-made one.

## The developer-repo guard (ADR-051)

`_developer_repo_guard.py` + `conftest.py` implement AC `BO-4300f-4-i`: a
session-scoped, autouse pytest fixture snapshots the developer repository's
`git worktree list --porcelain`, `git for-each-ref`, and
`git config --local --list` before the whole suite in this directory runs,
and compares after — **any difference fails the session**. Per
[ADR-051](../../docs/architecture/adrs/ADR-051-developer-repo-guard-session-exclusivity.md),
the guard holds a real OS advisory lock (`msvcrt`/`fcntl`) on
`<git-common-dir>/bo4300-proof-suite.lock` for the whole snapshot-to-compare
window, so a second concurrent suite invocation blocks rather than races the
comparison. A lock timeout raises `DeveloperRepoLockTimeoutError`, distinct
from `DeveloperRepoChangedError` (a real leak).

**Every later BO-4300 proof ticket inherits this guard automatically through
this directory's `conftest.py`. Do not add your own guard or your own
developer-repo snapshot** — wire new fixtures through the existing
`_workspace_maker_fixtures`/`_workspace_maker_builders` modules instead.

Override the guarded repository (for an isolated test of the guard itself)
via the `BO4300_DEVELOPER_REPO_ROOT` environment variable — never by editing
`conftest.py`.

## Re-pointed legacy fixtures

`_bo2400f13_fixtures.py`'s `DEPLOYED_SCRIPT` (used by the BO-2400f-13 family)
and `_bo_4300a_1_fixtures.py`'s `DeployedMakerBuild.build()` (used by
BO-4300a-1's deployed-maker tests) both now resolve through
`ensure_deployed_layout()` instead of spawning their own
`scripts/build.py` — one shared spawn site for the whole directory.
