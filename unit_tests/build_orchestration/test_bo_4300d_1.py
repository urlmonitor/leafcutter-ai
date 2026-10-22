"""
MODULE: unit_tests/build_orchestration/test_bo_4300d_1.py
AC: BO-4300d-1 -- Asking again for a healthy workspace hands it back re-readied, with the work
    in it untouched.
Real-subprocess proof against the DEPLOYED maker (real temp repos, real bare hub, no git mock).
Also the home of the shared helpers of this ticket's sibling modules (test_bo_4300d_1_i/_ii,
test_bo_4300d_2/_i/_ii/_iii): the ticket's files_touched lists no separate helper module, so the
helpers live here and the siblings import the FUNCTIONS only (the ticket-05 precedent).

TEST SEAMS the python-coder must honour (documented here, the only env contract the proofs use):
  * LEAFCUTTER_WORKSPACE_ABORT_AT=<stage> -- the maker aborts (non-zero exit, no ok answer) at
    exactly that stage and does NOTHING else: after_clone | after_branch | after_install |
    during_marker. It can never skip a step or yield ok.
  * BO4300D_FAIL_BUILD=1 / BO4300D_BUILD_SLEEP=<s> / BO4300D_FLAG=<file> -- read only by the
    fixture's OWN stub scripts/build.py (not the maker): fail early, hold the build open, and
    write the build's pid to <file> when it starts.
Observable stand-ins the stub install provides: <ws>/.leafcutter/build_count.txt (incremented by
every build run) and <ws>/.git/canary_log.txt (one line per canary rejection by a stub hook).

DECISION HISTORY
====================================================================
- 2026-10-10 18:10 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/07,
  BO-4300d-1]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/07)
====================================================================
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
import time
import unittest
from pathlib import Path

from unit_tests.build_orchestration._workspace_maker_fixtures import deployed_maker_path
from unit_tests.build_orchestration._workspace_maker_builders import _isolated_git_env
from unit_tests.build_orchestration.test_bo_4300c_1 import (
    _BUILD,
    _INSTALLER,
    SENT,
    STAGES,
    MakerTestCase,
    _hook_source,
    build_project,
    ensure,
    git_out,
    location,
    workspaces_under,
)

ABORT_ENV = "LEAFCUTTER_WORKSPACE_ABORT_AT"
ABORT_STAGES = ("after_clone", "after_branch", "after_install", "during_marker")
CHECK_KEYS = ("is_independent_repo", "not_main_checkout", "branch_matches", "not_protected_branch",
              "base_is_fresh", "build_ok", "tree_clean", "precommit_config_present",
              "hooks_pre_commit_fired", "hooks_commit_msg_fired", "hooks_post_merge_fired",
              "hooks_canary_rejected")
FAIL_ENV = {"BO4300D_FAIL_BUILD": "1"}
KIND, SLUG = "feature", "alpha"

_COUNT_AND_HOLD = (
    "cnt = target / '.leafcutter' / 'build_count.txt'\n"
    "cnt.parent.mkdir(parents=True, exist_ok=True)\n"
    "prev = int(cnt.read_text(encoding='utf-8').strip() or 0) if cnt.exists() else 0\n"
    "cnt.write_bytes((str(prev + 1) + '\\n').encode('utf-8'))\n"
    "if os.environ.get('BO4300D_FLAG'):\n"
    "    Path(os.environ['BO4300D_FLAG']).write_text(str(os.getpid()), encoding='utf-8')\n"
    "__import__('time').sleep(float(os.environ.get('BO4300D_BUILD_SLEEP', '0')))\n"
)
_TARGET_LINE = "    target = Path(parser.parse_args().target_dir)\n"
_FAIL_EARLY = (
    "    if os.environ.get('BO4300D_FAIL_BUILD'):\n"
    "        sys.stderr.write('BUILD_FAILURE_4300D: disk on fire\\n')\n"
    "        return 1\n"
)


def _logging_hook(stage: str) -> str:
    """The stage's rejecting stub hook, also appending one line to <git-dir>/canary_log.txt."""
    src = _hook_source(stage, False).replace("import subprocess, sys\n", "import os, subprocess, sys\n", 1)
    log = (
        "    _gd = subprocess.run(['git', 'rev-parse', '--absolute-git-dir'], capture_output=True, text=True).stdout.strip()\n"
        f"    open(os.path.join(_gd, 'canary_log.txt'), 'a').write({stage!r} + '\\n')\n"
    )
    return src.replace("    print('PRECOMMIT_CANARY_REJECTED", log + "    print('PRECOMMIT_CANARY_REJECTED", 1)


def stub_build_source(rewrite_tracked: int = 0) -> str:
    """The ticket-05 stub build plus: a build counter, a canary log, an early-fail switch, a hold."""
    hooks = {st: _logging_hook(st) for st in STAGES}
    canaries = {
        "pre-commit": {"path": "canary_bad_file.txt", "content": SENT["pre-commit"] + "\n"},
        "commit-msg": {"message": "canary message " + SENT["commit-msg"]},
        "post-merge": {"path": "canary_bad_merge.txt", "content": SENT["post-merge"] + "\n"},
    }
    rewrite = [f"tracked/f{i:02d}.txt" for i in range(rewrite_tracked)]
    installer = _INSTALLER.replace("__HOOKS__", repr(json.dumps(hooks))).replace("__SKIP__", repr(None))
    src = (
        _BUILD.replace("__CFG__", repr(json.dumps({"canaries": canaries})))
        .replace("__HOOKS__", repr(json.dumps(hooks)))
        .replace("__INSTALLER__", repr(installer))
        .replace("__REWRITE__", repr(json.dumps(rewrite)))
        .replace("__EXTRA__\n", textwrap.indent(_COUNT_AND_HOLD, "    "))
    )
    assert _TARGET_LINE in src, "the ticket-05 stub build template drifted"
    return src.replace(_TARGET_LINE, _TARGET_LINE + _FAIL_EARLY, 1)


def project(tmp, rewrite_tracked: int = 0) -> dict:
    """A real hub + project whose stub build counts runs and logs canary rejections."""
    return build_project(tmp, rewrite_tracked=rewrite_tracked, build_source=stub_build_source(rewrite_tracked))


def where(fx, kind: str = KIND, slug: str = SLUG) -> Path:
    """The one location the work's workspace must occupy."""
    return Path(fx["landing_place"]) / kind / slug


def build_count(ws) -> int:
    """How many times the stub build has run in *ws* (0 when never)."""
    f = Path(ws) / ".leafcutter" / "build_count.txt"
    return int(f.read_text(encoding="utf-8").strip()) if f.exists() else 0


def canary_log(ws) -> list[str]:
    """One entry per canary rejection recorded by a stub hook in *ws*."""
    f = Path(ws) / ".git" / "canary_log.txt"
    return f.read_text(encoding="utf-8").split() if f.exists() else []


def raw_env(extra: dict | None = None) -> dict:
    """The environment a maker process is started with (isolated git identity + *extra*)."""
    return {**os.environ, **_isolated_git_env(), **(extra or {})}


def start_maker(args: list[str], cwd, extra_env: dict | None = None) -> subprocess.Popen:
    """Start the DEPLOYED maker as a real, separate process (not waited for)."""
    return subprocess.Popen([sys.executable, str(deployed_maker_path()), *args], cwd=str(cwd), text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=raw_env(extra_env))


def finish(proc: subprocess.Popen, timeout: int = 240) -> dict:
    """Wait for *proc*; return {answer: dict|None, exit_code, stdout, stderr}."""
    out, err = proc.communicate(timeout=timeout)
    answer = None
    for line in out.splitlines():
        try:
            parsed = json.loads(line)
        except ValueError:
            continue
        if isinstance(parsed, dict):
            answer = parsed
    return {"answer": answer, "exit_code": proc.returncode, "stdout": out, "stderr": err}


def raw_maker(args: list[str], cwd, extra_env: dict | None = None, timeout: int = 240) -> dict:
    """Run the deployed maker to completion; tolerate an abort that prints no answer."""
    return finish(start_maker(args, cwd, extra_env), timeout)


def ensure_args(slug: str = SLUG, kind: str = KIND) -> list[str]:
    return ["ensure", "--kind", kind, "--slug", slug]


def kill_tree(pids: list[int]) -> None:
    """Kill every process in *pids* and their children, ignoring ones already gone."""
    for pid in pids:
        if sys.platform == "win32":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True)
        else:
            try:
                os.kill(pid, 9)
            except OSError:
                pass


def wait_for(path: Path, seconds: int = 90) -> bool:
    """Poll until *path* exists; False on timeout."""
    end = time.time() + seconds
    while time.time() < end:
        if Path(path).exists():
            return True
        time.sleep(0.1)
    return False


def interrupt(fx, stage: str, slug: str = SLUG) -> dict:
    """Really interrupt the deployed maker at *stage* via the documented abort seam."""
    return raw_maker(ensure_args(slug), fx["project"], {ABORT_ENV: stage})


class TestReReady(MakerTestCase):
    def ready_with_work(self) -> dict:
        """Ready workspace for alpha holding two local commits, a tracked edit and an untracked file."""
        fx = project(self.tmp)
        first = ensure(fx, SLUG)["answer"]
        self.assertEqual(first.get("status"), "ok", first)
        ws = Path(location(first))
        git_out(["config", "user.email", "work@example.com"], ws)
        git_out(["config", "user.name", "Work"], ws)
        for i in (1, 2):
            (ws / f"work{i}.txt").write_text(f"work {i}\n", encoding="utf-8", newline="\n")
            git_out(["add", "-A"], ws)
            git_out(["commit", "-q", "-m", f"work {i}"], ws)
        (ws / "README.md").write_bytes(b"UNCOMMITTED EDIT BY THE WORK\n")
        (ws / "new_file.txt").write_bytes(b"NEW FILE NOT UNDER VERSION CONTROL\n")
        fx["ws"], fx["first"] = ws, first
        fx["shas"] = git_out(["rev-list", "HEAD"], ws)
        return fx

    def test_rerequest_of_ready_workspace_answers_ok_same_location_re_readied(self):
        # covers: BO-4300d-1
        # angle: criterion
        """Second request: ok, same workspace_path, workspace_action 're-readied' (not 'reused')."""
        fx = self.ready_with_work()
        res = ensure(fx, SLUG)
        ans = res["answer"]
        self.assertEqual((ans.get("status"), res["exit_code"]), ("ok", 0), ans)
        self.assertEqual(Path(location(ans)).resolve(), fx["ws"].resolve(), ans)
        self.assertEqual(ans.get("workspace_action"), "re-readied", ans)

    def test_rerequest_rebuilds_install_and_reproves_protections(self):
        # covers: BO-4300d-1
        # angle: real_artifact
        """The stub build's counter increments and a FRESH canary rejection is recorded in the request."""
        fx = self.ready_with_work()
        builds, canaries = build_count(fx["ws"]), len(canary_log(fx["ws"]))
        self.assertEqual(builds, 1)
        self.assertGreaterEqual(canaries, 1, "the first request proved the protections")
        ans = ensure(fx, SLUG)["answer"]
        self.assertEqual(ans.get("status"), "ok", ans)
        self.assertEqual(build_count(fx["ws"]), builds + 1, "the tools were not rebuilt during the request")
        self.assertGreater(len(canary_log(fx["ws"])), canaries, "no fresh canary rejection during the request")
        for key in CHECK_KEYS:
            with self.subTest(check=key):
                self.assertIs(ans["checks"].get(key), True, ans["checks"])

    def test_commits_uncommitted_change_and_untracked_file_survive(self):
        # covers: BO-4300d-1
        # angle: boundary
        """Both commit shas, the uncommitted change and the untracked file are byte-identical afterwards."""
        fx = self.ready_with_work()
        ws = fx["ws"]
        self.assertEqual(len(fx["shas"].split()), 4, "the fixture's two commits plus the work's two")
        ans = ensure(fx, SLUG)["answer"]
        self.assertEqual(ans.get("status"), "ok", ans)
        self.assertEqual(git_out(["rev-list", "HEAD"], ws), fx["shas"])
        self.assertEqual((ws / "README.md").read_bytes(), b"UNCOMMITTED EDIT BY THE WORK\n")
        self.assertEqual((ws / "new_file.txt").read_bytes(), b"NEW FILE NOT UNDER VERSION CONTROL\n")
        status = sorted(line.strip() for line in git_out(["status", "--porcelain"], ws).splitlines())
        self.assertEqual(status, ["?? new_file.txt", "M README.md"], status)
        self.assertEqual(build_count(ws), 2, "the success path must really have rebuilt")

    def test_exactly_one_workspace_exists_after_rerequest(self):
        # covers: BO-4300d-1
        # angle: criterion
        """The landing place holds exactly one workspace for alpha, at the original location."""
        fx = self.ready_with_work()
        ans = ensure(fx, SLUG)["answer"]
        self.assertEqual(ans.get("status"), "ok", ans)
        self.assertEqual(ans.get("workspace_action"), "re-readied", ans)
        self.assertEqual([p.resolve() for p in workspaces_under(fx["landing_place"])], [fx["ws"].resolve()])


if __name__ == "__main__":
    unittest.main()
