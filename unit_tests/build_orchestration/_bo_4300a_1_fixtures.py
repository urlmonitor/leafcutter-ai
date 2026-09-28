"""
MODULE: unit_tests/build_orchestration/_bo_4300a_1_fixtures.py
AC: BO-4300a-1 -- "Every route that asks gets the same kind of workspace from
    the same maker."
GOAL: Test-only REAL-git fixture helpers for test_bo_4300a_1.py. Builds a
    real bare hub, a real "test project" cloned from it, and a minimal stub
    build entry point that installs a REAL rejecting git hook -- so the
    maker's own `ensure` verb has something genuine to run and something
    genuine to prove rejects a bad commit.

NOT a test file itself (leading underscore -- mirrors the convention already
established by unit_tests/build_orchestration/_bo2400f13_fixtures.py and
unit_tests/portability/_deployed_check_harness.py). Nothing in here is
collected by pytest.

=== Why this module exists instead of reusing BO-4300f-4's fixture API ===
BO-4300a-1's own Implementation Notes name a shared fixture API
(`unit_tests/build_orchestration/_workspace_maker_fixtures.py`,
`deployed_maker_path()`, `make_project()`, `run_maker()`, `starting_points()`)
delivered by AC BO-4300f-4. As of this ticket's authoring, BO-4300f-4 is
ticket 58 of this same epic and has not been built -- there is no such module
on disk (confirmed: `find . -iname _workspace_maker_fixtures.py` -> no
hits). BO-4300a-1 is ticket 1 of the epic and cannot block on infrastructure
59 tickets away. This module is a narrower, self-contained stand-in scoped
ONLY to what BO-4300a-1's own test_spec needs; it deliberately does not try
to pre-empt BO-4300f-4's fuller contract (fault-injection override seam,
legacy-worktree helper, dev/consumer layout switch). When BO-4300f-4 lands,
these tests should be migrated onto its fixture module rather than this one
growing to match it feature-for-feature.

=== The "no new build.py spawn site" tension, and how this module resolves it ===
CLAUDE.md's "Tests must not spawn their own build.py" rule exists because 77
existing spawn sites each pay the ~60s full-package build cost with no
sharing. This ticket is different in kind, not degree: `templates/scripts/
worktree.py` and its resolver module do not exist in ANY already-built
deployed layout (there is nothing to share -- this ticket is what first adds
the deploy-manifest entries). Two of this ticket's own test_spec entries are
tagged `angle: deployed` for exactly this reason (BP-1100g-1's "deployed"
angle IS "runs build.py into a temporary target directory and exercises the
DEPLOYED copy"). This module therefore builds the deployed layout EXACTLY
ONCE per test-class run (via `DeployedMakerBuild`, intended for
`setUpClass`), and every other test in the file re-uses that one build --
never one spawn per test. This is the single new spawn site this ticket's
own Implementation Notes justify ("A test that must mutate the package and
build its own copy says so and justifies it in its ticket" -- see this
ticket's Implementation Notes and this module's DECISION HISTORY below).

DECISION HISTORY
====================================================================
- 2026-09-27 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01,
  BO-4300a-1]: Initial implementation, ahead of BO-4300f-4's fuller fixture
  API (see module docstring). Fixture "projects" carry their OWN minimal stub
  `scripts/build.py` (never the package's real `scripts/build.py`) so the
  maker's "run the install build inside the workspace" step has a fast,
  self-contained target: the stub writes an `INSTALLED_MARKER.txt` stamped
  with the source project's own content (proving the install ran "from its
  own contents", not a cached/generic template) and a real rejecting
  `.git/hooks/pre-commit` that fails any commit whose staged diff contains
  REJECT_SENTINEL.
====================================================================
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent

# The maker's provisional name and its resolver module's provisional name,
# per this ticket's own Implementation Notes ("templates/scripts/worktree.py
# (name provisional...)" and "e.g. workspace_root.py").
MAKER_NAME = "worktree.py"
RESOLVER_MODULE_NAME = "workspace_root.py"

# scripts/build.py's own default output_root (`config.get("output_root",
# ".leafcutter")`, scripts/build.py:1931) -- a fresh, non-self-hosted target
# directory (no --config-path override, as DeployedMakerBuild.build() below
# never passes one) always lands non-shimmed scripts under
# `<target_dir>/.leafcutter/scripts/`, never `<target_dir>/scripts/`. Mirrors
# the established precedent `_DEPLOYED_CG_REL` in
# unit_tests/portability/_deployed_check_harness.py.
_DEPLOYED_OUTPUT_ROOT = ".leafcutter"

REJECT_SENTINEL = "BO4300A1_REJECT_SENTINEL"

_GIT_USER_EMAIL = "bo-4300a-1-test-writer@example.com"
_GIT_USER_NAME = "BO-4300a-1 Test Writer"

# The five routes named in the AC's Given clause, mapped onto the six `--kind`
# values the CLI contract (this ticket's own "Delivers To" section) names --
# `ticket` is deliberately excluded: that kind is exercised together with
# `--ticket` by the sibling AC BO-4300a-1-ii, not by this one.
FIVE_ROUTES: list[dict[str, str]] = [
    {"route": "long-running build", "kind": "epic", "slug": "epic-longrun-alpha"},
    {"route": "quick fix", "kind": "feature", "slug": "feature-quickfix-beta"},
    {"route": "requirements-authoring session", "kind": "ac", "slug": "ac-reqsession-gamma"},
    {"route": "agent following the workspace skill", "kind": "fastlane", "slug": "fastlane-skill-delta"},
    {"route": "person at a terminal", "kind": "scratch", "slug": "scratch-terminal-epsilon"},
]


def run_git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command with cwd set to *cwd* (never `git -C` for anything
    that could be a commit -- see this ticket's own "GIT INVOCATION SPELLING"
    note and KI-CG-20260925-commit-delegation-hook-misses-git-dash-c)."""
    env = dict(os.environ)
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=check,
        env=env,
    )


def _configure_identity(repo: Path) -> None:
    run_git(["config", "user.email", _GIT_USER_EMAIL], repo)
    run_git(["config", "user.name", _GIT_USER_NAME], repo)
    run_git(["config", "commit.gpgsign", "false"], repo)


def _stub_build_py_source() -> str:
    """Source text for the fixture project's own tiny `scripts/build.py`.

    Never the package's real `scripts/build.py` (CLAUDE.md's "Tests must not
    spawn their own build.py"; this ticket's own note: "fixture projects
    carry a minimal stub build entry point"). Reads a BUILD_STAMP.txt that
    ships in the same clone, proving the install ran "from its own contents"
    (test_every_route_workspace_has_own_install_and_rejects_canary), and
    installs a REAL rejecting `.git/hooks/pre-commit`.
    """
    return f'''"""Stub build entry point for a BO-4300a-1 fixture project.

Never the real leafcutter scripts/build.py -- a fixture-only stand-in per
this ticket's own Implementation Notes ("fixture projects carry a minimal
stub build entry point that installs a real, rejecting hook").
"""
import argparse
import os
import stat
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-dir", required=True)
    parser.add_argument("--config-path", default=None)
    args = parser.parse_args()

    target = Path(args.target_dir)
    own_root = Path(__file__).resolve().parent.parent
    stamp = (own_root / "BUILD_STAMP.txt").read_text(encoding="utf-8").strip()

    (target / "INSTALLED_MARKER.txt").write_text(
        f"installed-from-stamp:{{stamp}}\\n", encoding="utf-8"
    )

    hooks_dir = target / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / "pre-commit"
    hook_path.write_text(
        "#!/usr/bin/env python\\n"
        "import subprocess, sys\\n"
        "diff = subprocess.run(['git', 'diff', '--cached'], capture_output=True, text=True).stdout\\n"
        "if {REJECT_SENTINEL!r} in diff:\\n"
        "    print('rejected by stub hook: {REJECT_SENTINEL}')\\n"
        "    sys.exit(1)\\n"
        "sys.exit(0)\\n",
        encoding="utf-8",
    )
    st = os.stat(hook_path)
    os.chmod(hook_path, st.st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    print("stub build complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
'''


def make_bare_hub(tmp: Path) -> Path:
    """Create a real bare hub repo at tmp/hub.git (the "shared project")."""
    hub = tmp / "hub.git"
    hub.mkdir(parents=True, exist_ok=True)
    run_git(["-c", "init.defaultBranch=main", "init", "--bare", "-q"], hub)
    return hub


def seed_hub(tmp: Path, hub: Path, stamp: str) -> str:
    """Create a real seed working copy, commit fixture content (a real
    .pre-commit-config.yaml, a real stub scripts/build.py, a minimal
    .claude/skills_config.json, and BUILD_STAMP.txt), and push it to *hub*
    as `main`. Returns the pushed commit SHA (commit S)."""
    seed = tmp / "seed"
    seed.mkdir(parents=True, exist_ok=True)
    run_git(["-c", "init.defaultBranch=main", "init", "-q"], seed)
    _configure_identity(seed)

    (seed / "README.md").write_text("BO-4300a-1 fixture project\n", encoding="utf-8")
    (seed / "BUILD_STAMP.txt").write_text(f"{stamp}\n", encoding="utf-8")
    (seed / ".pre-commit-config.yaml").write_text("repos: []\n", encoding="utf-8")
    (seed / ".claude").mkdir(parents=True, exist_ok=True)
    (seed / ".claude" / "skills_config.json").write_text(
        json.dumps({"docs_root": "docs/"}, indent=2) + "\n", encoding="utf-8"
    )
    scripts_dir = seed / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    (scripts_dir / "build.py").write_text(_stub_build_py_source(), encoding="utf-8")

    run_git(["add", "-A"], seed)
    run_git(["commit", "-q", "-m", "initial fixture content"], seed)
    run_git(["remote", "add", "origin", str(hub)], seed)
    run_git(["push", "-q", "-u", "origin", "main"], seed)
    sha = run_git(["rev-parse", "HEAD"], seed).stdout.strip()
    return sha


def advance_hub(tmp: Path, hub: Path, note: str) -> str:
    """Push a second, independent commit directly to *hub* -- simulating
    further work landing in the shared project AFTER a local checkout was
    made from it. Returns the new commit SHA. Uses a fresh throwaway clone
    (never the project fixture the tests operate on) so this never disturbs
    a caller's own working tree."""
    advancer = tmp / "hub_advancer"
    run_git(["clone", "-q", str(hub), str(advancer)], tmp)
    _configure_identity(advancer)
    (advancer / "ADVANCED.txt").write_text(f"{note}\n", encoding="utf-8")
    run_git(["add", "-A"], advancer)
    run_git(["commit", "-q", "-m", note], advancer)
    run_git(["push", "-q", "origin", "main"], advancer)
    sha = run_git(["rev-parse", "HEAD"], advancer).stdout.strip()
    return sha


def make_project(tmp: Path, hub: Path) -> Path:
    """Clone *hub* into tmp/project -- the "test project" the AC's Given
    clause names, the checkout every route's `ensure` call is anchored to."""
    project = tmp / "project"
    run_git(["clone", "-q", str(hub), str(project)], tmp)
    _configure_identity(project)
    return project


@dataclass
class DeployedMakerBuild:
    """Builds the shared package deployed layout EXACTLY ONCE (intended for
    `setUpClass`) and exposes the deployed maker / resolver module paths.

    This IS the "deployed" test angle for this AC's own two `angle: deployed`
    test_spec entries (BP-1100g-1's "deployed" angle: "Runs build.py into a
    temporary target directory and exercises the DEPLOYED copy"). Every other
    test in the file re-uses this SAME build rather than spawning its own --
    see this module's docstring "The no new build.py spawn site tension".
    """

    target_dir: Path
    build_stdout: str = ""
    build_returncode: int | None = None

    @classmethod
    def build(cls) -> "DeployedMakerBuild":
        target_dir = Path(tempfile.mkdtemp(prefix="bo4300a1-deployed-"))
        build_script = REPO_ROOT / "scripts" / "build.py"
        proc = subprocess.run(
            [sys.executable, str(build_script), "--target-dir", str(target_dir)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        return cls(
            target_dir=target_dir,
            build_stdout=(proc.stdout or "") + (proc.stderr or ""),
            build_returncode=proc.returncode,
        )

    @property
    def maker_path(self) -> Path:
        # scripts/build.py's own documented default (`config.get("output_root",
        # ".leafcutter")`, scripts/build.py:1931) writes every non-shimmed
        # script -- including the long-standing setup_ticket_worktree.py, not
        # just the maker -- to `<target_dir>/.leafcutter/scripts/<name>`, never
        # `<target_dir>/scripts/<name>`. This mirrors the established
        # precedent `_DEPLOYED_CG_REL = Path(".leafcutter") / "scripts" /
        # "commit_guardian"` in unit_tests/portability/_deployed_check_harness.py.
        # (test_drift fix -- see this ticket's 2026-09-27 23:57 python-coder
        # handoff comment; production was correct, this fixture's path
        # assumption was stale.)
        return self.target_dir / _DEPLOYED_OUTPUT_ROOT / "scripts" / MAKER_NAME

    @property
    def resolver_path(self) -> Path:
        return self.target_dir / _DEPLOYED_OUTPUT_ROOT / "scripts" / RESOLVER_MODULE_NAME

    def maker_present(self) -> bool:
        return self.maker_path.is_file()

    def resolver_present(self) -> bool:
        return self.resolver_path.is_file()


def run_maker(
    maker_path: Path,
    args: list[str],
    cwd: Path,
    timeout: int = 60,
) -> subprocess.CompletedProcess:
    """Invoke the DEPLOYED maker as a real separate process. Never imports
    the maker module -- CLAUDE.md "Gate / Workflow ACs -- Verify
    Behaviorally, Not by Grep" plus this ticket's own "no import of the
    maker module" constraint."""
    return subprocess.run(
        [sys.executable, str(maker_path), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def parse_json_stdout(proc: subprocess.CompletedProcess) -> dict[str, Any] | None:
    """Parse *proc*'s stdout as exactly one JSON object (the last JSON-shaped
    line, matching the established convention in
    unit_tests/build_orchestration/_bo2400f13_fixtures.py). Returns None
    (never raises) when nothing parses."""
    text = proc.stdout or ""
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            continue
    return None


def workspace_location(answer: dict) -> str | None:
    """The AC's answer names "the workspace's location" -- the decision memo
    adds `workspace_path` while keeping `worktree_path` as an alias. Accept
    either key name (both are the SAME contract field under two spellings),
    never a third, unnamed guess. Shared by both test_bo_4300a_1.py and
    test_bo_4300a_1_deployed.py (moved here, out of either test file, so
    neither test file needs to import from its sibling)."""
    return answer.get("workspace_path") or answer.get("worktree_path")


def marker_fields(verify_answer: dict) -> dict:
    """The marker's fields may be nested under a `marker` key or exposed at
    the top level of `verify`'s own answer -- either is an acceptable shape
    for this AC (which does not fix the marker's exact envelope), so long as
    kind/slug/branch/base_commit/state are all present somewhere in it."""
    if isinstance(verify_answer.get("marker"), dict):
        return verify_answer["marker"]
    return verify_answer


def attempt_reject_commit(workspace: Path) -> subprocess.CompletedProcess:
    """Stage a file containing REJECT_SENTINEL inside *workspace* and attempt
    a real `git commit` (cwd set to workspace, never `git -C`, per this
    ticket's own GIT INVOCATION SPELLING note). Returns the commit
    CompletedProcess (non-zero exit is the expected/desired outcome when a
    real rejecting hook is installed)."""
    bad_file = workspace / "known_bad_file.txt"
    bad_file.write_text(f"{REJECT_SENTINEL}\n", encoding="utf-8")
    run_git(["add", "-A"], workspace)
    return run_git(
        ["commit", "-q", "-m", "should be rejected by real hook"],
        workspace,
        check=False,
    )
