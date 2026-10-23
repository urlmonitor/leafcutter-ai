"""
MODULE: unit_tests/build_orchestration/test_bo_4300c_1.py
AC: BO-4300c-1 -- Ready is only answered when every part of readiness holds on the
    workspace as it exists.
Real-subprocess proof against the DEPLOYED maker (real temp repos, real bare hub, no git mock).
Also the home of the shared fixture builders for this ticket's sibling modules
(test_bo_4300c_1_i/_ii/_iii, test_bo_4300b_4): the ticket's files_touched lists no separate
helper module, so the helpers live here and the siblings import the FUNCTIONS only.

FIXTURE CONTRACT the python-coder must implement against (the install's own declaration):
  * The workspace's stage set = union of `stages:` in its tracked .pre-commit-config.yaml
    (written here with yaml.safe_dump).
  * The install ships `<ws>/.leafcutter/scripts/commit_guardian/install_pre_commit_shims.py`
    (run with cwd = workspace, like the real CLI); it installs a shim per declared stage
    except pre-commit (the build installs that one), exactly like the real installer.
  * The install ships `<ws>/.leafcutter/scripts/commit_guardian/commit_guardian.json` whose
    `stage_canaries` key declares each stage's known-bad input:
      pre-commit: {"path", "content"}  commit-msg: {"message"}  post-merge: {"path", "content"}
    (for post-merge, the change the after-merge canary brings in on a disposable ref).
  * A post-merge hook cannot abort `git merge`; the stub post-merge hook exits 1 when
    `git diff ORIG_HEAD HEAD` holds its sentinel, so the maker must read the hook's own exit
    (e.g. `git hook run post-merge` after the canary merge), never git merge's exit.
  * Answers to refusals carry `checks` (the per-ingredient booleans) but never a workspace path.

DECISION HISTORY
====================================================================
- 2026-09-30 23:40 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05,
  BO-4300c-1]: Created the red baseline. BOOTSTRAP_FAILED is asserted with the status/exit
  pair ticket 03's table gives it (refused/2); the test_spec text says error/1 but ticket 03
  owns the table. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05)
====================================================================
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

from unit_tests.build_orchestration._workspace_maker_fixtures import (  # fixtures first: avoids the builders cycle
    make_project,
    run_maker,
)
from unit_tests.build_orchestration._workspace_maker_builders import (
    _isolated_git_env,
    _run_git,
)

STAGES = ("pre-commit", "commit-msg", "post-merge")
SENT = {
    "pre-commit": "BO4300C1_BAD_FILE_SENTINEL",
    "commit-msg": "BO4300C1_BAD_MESSAGE_SENTINEL",
    "post-merge": "BO4300C1_BAD_MERGE_SENTINEL",
}
TRACKED_DIR = "tracked"


def stage_key(stage: str) -> str:
    """Return the checks.* key for *stage*."""
    return "hooks_" + stage.replace("-", "_") + "_fired"


def _hook_source(stage: str, accept: bool) -> str:
    if accept:
        return "#!/usr/bin/env python\nimport sys\nsys.exit(0)\n"
    if stage == "pre-commit":
        probe = "out = subprocess.run(['git', 'diff', '--cached'], capture_output=True, text=True).stdout\n"
    elif stage == "commit-msg":
        probe = "out = open(sys.argv[1], encoding='utf-8').read()\n"
    else:
        probe = "out = subprocess.run(['git', 'diff', 'ORIG_HEAD', 'HEAD'], capture_output=True, text=True).stdout\n"
    return (
        "#!/usr/bin/env python\nimport subprocess, sys\n" + probe
        + f"if {SENT[stage]!r} in out:\n    print('PRECOMMIT_CANARY_REJECTED rejected by stub {stage} hook')\n    sys.exit(1)\nsys.exit(0)\n"
    )


_INSTALLER = """\
import json, os, stat, subprocess
from pathlib import Path
import yaml
root = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True).stdout.strip())
cfg = yaml.safe_load((root / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
stages = sorted({s for r in cfg.get("repos", []) for h in r.get("hooks", []) for s in h.get("stages", [])})
HOOKS = json.loads(__HOOKS__)
SKIP = __SKIP__
for st in stages:
    if st == "pre-commit" or st == SKIP:
        continue
    path = root / ".git" / "hooks" / st
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\\n") as fh:
        fh.write(HOOKS[st])
    os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    print("[installed] " + st)
"""

_BUILD = """\
import argparse, json, os, stat, subprocess, sys
from pathlib import Path
CFG = json.loads(__CFG__)
HOOKS = json.loads(__HOOKS__)
INSTALLER = __INSTALLER__
REWRITE = json.loads(__REWRITE__)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-dir", required=True)
    parser.add_argument("--config-path", default=None)
    target = Path(parser.parse_args().target_dir)
    (target / "INSTALLED_MARKER.txt").write_text("installed\\n", encoding="utf-8")
    cg = target / ".leafcutter" / "scripts" / "commit_guardian"
    cg.mkdir(parents=True, exist_ok=True)
    (cg / "commit_guardian.json").write_text(json.dumps({"stage_canaries": CFG["canaries"]}), encoding="utf-8")
    (cg / "install_pre_commit_shims.py").write_text(INSTALLER, encoding="utf-8")
    hooks = target / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    hook = hooks / "pre-commit"
    with open(hook, "w", encoding="utf-8", newline="\\n") as fh:
        fh.write(HOOKS["pre-commit"])
    os.chmod(hook, os.stat(hook).st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    for rel in REWRITE:
        (target / rel).write_bytes(b"REWRITTEN BY BUILD\\n")
__EXTRA__
    print("stub build complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""

_EXTRA = {
    "gitfile": (
        "moved = target.parent / (target.name + '.moved-gitdir')\n"
        "os.rename(target / '.git', moved)\n"
        "(target / '.git').write_text('gitdir: ' + str(moved) + '\\n', encoding='utf-8')\n"
    ),
    "main": "subprocess.run(['git', 'checkout', '-q', '-B', 'main', 'origin/main'], cwd=str(target), check=True)\n",
    "stale": "subprocess.run(['git', 'reset', '-q', '--hard', 'HEAD~1'], cwd=str(target), check=True)\n",
}

FAIL_LINE = "BUILD_FAILURE_DISTINCT_LINE_4300C1I: disk on fire"


def failing_build_source() -> str:
    """A stub build that writes part of its output, floods stderr, then exits 1."""
    return (
        "import argparse, sys\nfrom pathlib import Path\n"
        "p = argparse.ArgumentParser()\np.add_argument('--target-dir', required=True)\n"
        "p.add_argument('--config-path', default=None)\nt = Path(p.parse_args().target_dir)\n"
        "(t / 'INSTALLED_MARKER.txt').write_text('partial\\n', encoding='utf-8')\n"
        "(t / 'partial_output').mkdir(exist_ok=True)\n"
        "sys.stderr.write('filler line\\n' * 2000)\n"
        f"sys.stderr.write({FAIL_LINE!r} + '\\n')\nsys.exit(1)\n"
    )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def build_project(
    tmp,
    *,
    declared=STAGES,
    accept=None,
    skip_shim=None,
    rewrite_tracked=0,
    tip_commit=False,
    extra=None,
    build_source=None,
) -> dict:
    """Real bare hub + project whose tracked files declare *declared* stages.

    accept: stage whose stub hook accepts its canary (the one that "does not fire").
    skip_shim: stage the stub shim installer skips (declared, never installed).
    rewrite_tracked: N tracked files the stub build rewrites.
    extra: 'gitfile' | 'main' | 'stale' -- one more falsified ingredient, done by the build.
    build_source: replaces the stub build entirely (e.g. failing_build_source()).
    """
    hooks = {st: _hook_source(st, accept == st) for st in STAGES}
    canaries = {
        "pre-commit": {"path": "canary_bad_file.txt", "content": SENT["pre-commit"] + "\n"},
        "commit-msg": {"message": "canary message " + SENT["commit-msg"]},
        "post-merge": {"path": "canary_bad_merge.txt", "content": SENT["post-merge"] + "\n"},
    }
    rewrite = [f"{TRACKED_DIR}/f{i:02d}.txt" for i in range(rewrite_tracked)]
    installer = _INSTALLER.replace("__HOOKS__", repr(json.dumps(hooks))).replace("__SKIP__", repr(skip_shim))
    src = build_source or (
        _BUILD.replace("__CFG__", repr(json.dumps({"canaries": canaries})))
        .replace("__HOOKS__", repr(json.dumps(hooks)))
        .replace("__INSTALLER__", repr(installer))
        .replace("__REWRITE__", repr(json.dumps(rewrite)))
        .replace("__EXTRA__\n", textwrap.indent(_EXTRA.get(extra, ""), "    "))
    )
    fx = make_project(Path(tmp), stub_build=src)
    project = fx["project"]
    cfg = {"repos": [{"repo": "local", "hooks": [
        {"id": f"stub-{st}", "name": f"stub {st}", "entry": "stub", "language": "system", "stages": [st]}
        for st in declared]}]}
    _write(project / ".pre-commit-config.yaml", yaml.safe_dump(cfg))
    _write(project / ".gitignore", "INSTALLED_MARKER.txt\n.leafcutter/\n__pycache__/\npartial_output/\n")
    for rel in rewrite:
        _write(project / rel, f"committed content of {rel}\n")
    _run_git(["add", "-A"], project)
    _run_git(["commit", "-q", "-m", "declare stages and tracked fixture files"], project)
    if tip_commit:
        _write(project / "TIP_ONLY.txt", "tip only\n")
        _run_git(["add", "-A"], project)
        _run_git(["commit", "-q", "-m", "tip only"], project)
    _run_git(["push", "-q", "origin", "main"], project)
    fx["rewritten"] = rewrite
    return fx


def ensure(fx, slug, kind="feature", extra_env=None, cwd=None, extra_args=()):
    """Run the deployed maker's `ensure` as a real subprocess with isolated git identity."""
    env = dict(_isolated_git_env())
    env.update(extra_env or {})
    return run_maker(
        ["ensure", "--kind", kind, "--slug", slug, *extra_args],
        cwd=Path(cwd) if cwd else fx["project"],
        env=env,
        timeout=240,
    )


def workspaces_under(landing) -> list[Path]:
    """Every directory under *landing* that holds a .git (dir or gitfile)."""
    landing = Path(landing)
    return sorted(p.parent for p in landing.rglob(".git")) if landing.exists() else []


def location(answer: dict):
    """The answer's workspace location under either spelling, or None."""
    return answer.get("workspace_path") or answer.get("worktree_path")


def git_out(args, cwd) -> str:
    """Run an isolated git command in *cwd*; return stripped stdout."""
    return _run_git(args, Path(cwd)).stdout.strip()


def force_rmtree(path) -> None:
    """rmtree that clears read-only bits (git objects on Windows)."""
    def _chmod(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=_chmod)


class MakerTestCase(unittest.TestCase):
    """Base: a private temp dir per test, removed afterwards."""

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="bo4300c1-")
        self.addCleanup(force_rmtree, self._tmpdir)
        self.tmp = Path(self._tmpdir)

    def refused(self, res):
        """Assert *res* is a non-ok answer with no workspace location; return the answer."""
        ans = res["answer"]
        self.assertNotEqual(ans.get("status"), "ok", ans)
        self.assertNotEqual(res["exit_code"], 0)
        self.assertIsNone(location(ans), "a refusal never carries a workspace location")
        return ans


class TestReadinessConjunction(MakerTestCase):
    def test_all_five_ingredients_true_gives_ok(self):
        # covers: BO-4300c-1
        # angle: criterion
        """Sound fixture: ok, exit 0, every checks.* ingredient true, base read back from the hub."""
        fx = build_project(self.tmp)
        res = ensure(fx, "all-good")
        ans = res["answer"]
        self.assertEqual((ans["status"], res["exit_code"]), ("ok", 0), ans)
        expected = ["is_independent_repo", "not_main_checkout", "branch_matches", "not_protected_branch",
                    "base_is_fresh", "build_ok", "tree_clean", "precommit_config_present",
                    "hooks_pre_commit_fired", "hooks_commit_msg_fired", "hooks_post_merge_fired",
                    "hooks_canary_rejected"]
        for key in expected:
            with self.subTest(check=key):
                self.assertIs(ans["checks"].get(key), True, ans["checks"])
        self.assertEqual(ans["base_commit"], git_out(["rev-parse", "main"], fx["hub"]))

    def test_main_copy_instead_of_clone_is_refused_naming_it(self):
        # covers: BO-4300c-1
        # angle: failure
        """A workspace whose .git is a gitfile (not its own directory) is refused naming independence."""
        fx = build_project(self.tmp, extra="gitfile")
        ans = self.refused(ensure(fx, "gitfile"))
        self.assertIs(ans.get("checks", {}).get("is_independent_repo"), False, ans)
        text = json.dumps(ans)
        self.assertTrue("is_independent_repo" in text or "independent" in text.lower(), text)

    def test_line_of_work_equal_to_main_is_refused_naming_it(self):
        # covers: BO-4300c-1
        # angle: failure
        """A workspace that ends up on main is refused with ON_PROTECTED_BRANCH."""
        fx = build_project(self.tmp, extra="main")
        ans = self.refused(ensure(fx, "onmain"))
        self.assertEqual(ans["code"], "ON_PROTECTED_BRANCH", ans)
        self.assertIs(ans.get("checks", {}).get("not_protected_branch"), False, ans)

    def test_stale_base_is_refused_naming_it(self):
        # covers: BO-4300c-1
        # angle: failure
        """A branch tip that is not origin/main as read after the fetch is refused naming freshness."""
        fx = build_project(self.tmp, extra="stale", tip_commit=True)
        ans = self.refused(ensure(fx, "stale"))
        self.assertIs(ans.get("checks", {}).get("base_is_fresh"), False, ans)
        self.assertIn("fresh", json.dumps(ans).lower(), ans)

    def test_failed_install_build_is_refused_naming_it(self):
        # covers: BO-4300c-1
        # angle: failure
        """A build exiting non-zero gives BOOTSTRAP_FAILED (refused/2 per ticket 03's table), no path."""
        fx = build_project(self.tmp, build_source=failing_build_source())
        res = ensure(fx, "badbuild")
        ans = self.refused(res)
        self.assertEqual(ans["code"], "BOOTSTRAP_FAILED", ans)
        self.assertEqual(res["exit_code"], 2 if ans["status"] == "refused" else 1)

    def test_protections_that_do_not_fire_are_refused_naming_them(self):
        # covers: BO-4300c-1
        # angle: failure
        """Each stage in turn accepts its canary: HOOKS_INACTIVE names exactly that stage."""
        for stage in STAGES:
            with self.subTest(stage=stage):
                fx = build_project(self.tmp / stage, accept=stage)
                ans = self.refused(ensure(fx, f"inactive-{stage}"))
                self.assertEqual(ans["code"], "HOOKS_INACTIVE", ans)
                self.assertEqual(ans["inactive_stages"], [stage])
                self.assertIs(ans["checks"][stage_key(stage)], False)
                self.assertIs(ans["checks"]["hooks_canary_rejected"], False)


if __name__ == "__main__":
    unittest.main()
