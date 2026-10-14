"""
MODULE: test_bo_4300c_2
GOAL: Red-first behavioural tests for BO-4300c-2 -- the workspace maker's answer
    is one readable answer (one JSON object on stdout) and nothing else.
PROOF SHAPE: the DEPLOYED maker (shared reference layout, read-only; never the
    templates/ source copy, never a build.py spawn) runs as a separate process
    against real temporary git repositories and a real bare hub, once per
    outcome: ready, OCCUPIED, FETCH_FAILED (hub unreachable), BOOTSTRAP_FAILED.
    No mock of git, no import of the maker, no grep of its source.
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

from scripts.suite_performance._shared_layout_producer import get_or_produce_shared_layout

from ._bo4300a1_helpers import build_world, find_marker, git_ok

_WORLDS: list = []
_RUNS: dict = {}

# What the maker's own child tools print; none may reach stdout.
GIT_NOISE = ("HEAD is now at", "set up to track", "Cloning into", "Switched to")
STUB_NOISE = "stub build ok"
FAILING_STUB = (
    "import sys\n"
    "print('failing stub build: progress line on stdout')\n"
    "print('failing stub build: error line', file=sys.stderr)\n"
    "sys.exit(5)\n"
)
STATUS_EXIT = {"ok": 0, "refused": 2, "error": 1}


def _scripts_dir() -> Path:
    return Path(get_or_produce_shared_layout()) / ".leafcutter" / "scripts"


def _new_world():
    world = build_world(_scripts_dir())
    _WORLDS.append(world)
    return world


def tearDownModule():  # noqa: N802
    for world in _WORLDS:
        world.holder.cleanup()


def _raw(world, argv, cwd=None) -> subprocess.CompletedProcess:
    maker = world.maker
    assert maker.is_file(), f"deployed maker missing: {maker}"
    return subprocess.run(  # noqa: S603
        [sys.executable, str(maker), *argv], cwd=str(cwd or world.elsewhere),
        env=world.env, stdin=subprocess.DEVNULL, capture_output=True, text=True,
        timeout=300, check=False,
    )


def _request(world, slug):
    return ["ensure", "--kind", "feature", "--slug", slug, "--repo-root", str(world.project)]


def _run_ready():
    world = _new_world()
    return _raw(world, _request(world, "bo4300c2-ready")), world


def _run_occupied():
    world = _new_world()
    first = _raw(world, _request(world, "bo4300c2-occ"))
    assert first.returncode == 0, f"fixture: first ensure failed: {first.stderr[-1500:]}"
    workspace = Path(json.loads(first.stdout)["workspace_path"])
    marker_path, _ = find_marker(workspace)
    marker_path.unlink()  # the location now holds something that is not a workspace
    return _raw(world, _request(world, "bo4300c2-occ")), world


def _run_unreachable_hub():
    world = _new_world()
    world.hub.rename(world.hub.with_name("hub-gone.git"))
    return _raw(world, _request(world, "bo4300c2-nohub")), world


def _run_bootstrap_failed():
    world = _new_world()
    seed = world.base / "seed"
    for build in (seed / "scripts" / "build.py", world.project / "scripts" / "build.py"):
        build.write_text(FAILING_STUB, encoding="utf-8")
    git_ok(seed, world.env, "add", "-A")
    git_ok(seed, world.env, "commit", "-m", "break the build")
    git_ok(seed, world.env, "push", "origin", "HEAD:main")
    return _raw(world, _request(world, "bo4300c2-boot")), world


_BUILDERS = {
    "ready": _run_ready,
    "OCCUPIED": _run_occupied,
    "FETCH_FAILED": _run_unreachable_hub,
    "BOOTSTRAP_FAILED": _run_bootstrap_failed,
}


def _outcome(name):
    if name not in _RUNS:
        _RUNS[name] = _BUILDERS[name]()
    return _RUNS[name]


def _answer(name) -> dict:
    done, _world = _outcome(name)
    try:
        payload = json.loads(done.stdout)
    except ValueError:
        self_msg = f"{name}: stdout is not exactly one JSON object: {done.stdout!r}"
        raise AssertionError(self_msg + f" stderr={done.stderr[-800:]!r}") from None
    assert isinstance(payload, dict), f"{name}: stdout JSON is not an object"
    return payload


class TestMakerAnswerChannel(unittest.TestCase):
    def test_stdout_holds_exactly_one_json_object_in_each_outcome(self):
        # covers: BO-4300c-2
        # angle: criterion
        """AC-1: stdout is exactly one JSON object, in each of the four outcomes."""
        for name in _BUILDERS:
            with self.subTest(outcome=name):
                done, _ = _outcome(name)
                bom = chr(0xFEFF)
                self.assertFalse(done.stdout.startswith(bom), "BOM on stdout")
                self.assertFalse(done.stdout.startswith("﻿"), "BOM on stdout")
                body = done.stdout[:-1] if done.stdout.endswith("\n") else done.stdout
                self.assertNotIn("\n", body, f"more than one line on stdout: {done.stdout!r}")
                self.assertIsInstance(_answer(name), dict)

    def test_outcomes_are_the_four_the_ac_names(self):
        # covers: BO-4300c-2
        # angle: discrimination
        """AC-1: each scenario really produced its named outcome (no vacuous fixtures)."""
        self.assertEqual(_answer("ready").get("status"), "ok", _outcome("ready")[0].stderr[-1500:])
        self.assertEqual(_answer("OCCUPIED").get("code"), "OCCUPIED")
        self.assertEqual(_answer("FETCH_FAILED").get("code"), "FETCH_FAILED")
        self.assertEqual(_answer("BOOTSTRAP_FAILED").get("code"), "BOOTSTRAP_FAILED")

    def test_every_answer_states_its_status(self):
        # covers: BO-4300c-2
        # angle: criterion
        """AC-2: each answer has status in {ok, refused, error}, a code and a schema_version."""
        expected_code = {"ready": "OK", "OCCUPIED": "OCCUPIED",
                         "FETCH_FAILED": "FETCH_FAILED", "BOOTSTRAP_FAILED": "BOOTSTRAP_FAILED"}
        for name in _BUILDERS:
            with self.subTest(outcome=name):
                answer = _answer(name)
                self.assertIn(answer.get("status"), set(STATUS_EXIT))
                self.assertEqual(answer.get("code"), expected_code[name])
                self.assertIsInstance(answer.get("schema_version"), int)
                self.assertIsInstance(answer.get("message"), str)

    def test_git_progress_messages_appear_on_stderr_not_stdout(self):
        # covers: BO-4300c-2
        # angle: seam
        """AC-3: child tool output is forwarded to stderr and never appears in the answer."""
        done, _ = _outcome("ready")
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        self.assertIn(STUB_NOISE, done.stderr, "the build's own output is not available on stderr")
        self.assertTrue(any(m in done.stderr for m in GIT_NOISE),
                        f"no git progress line forwarded to stderr: {done.stderr[-800:]!r}")
        for name in _BUILDERS:
            with self.subTest(outcome=name):
                stdout = _outcome(name)[0].stdout
                for marker in (*GIT_NOISE, STUB_NOISE, "failing stub build"):
                    self.assertNotIn(marker, stdout)
        boot = _outcome("BOOTSTRAP_FAILED")[0]
        self.assertIn("failing stub build: progress line on stdout", boot.stderr,
                      "a failing child's stdout must be forwarded to stderr")

    def test_exit_code_matches_stated_status(self):
        # covers: BO-4300c-2
        # angle: criterion
        """AC-4: exit code is 0/2/1 for ok/refused/error in each outcome."""
        for name in _BUILDERS:
            with self.subTest(outcome=name):
                done, _ = _outcome(name)
                self.assertEqual(done.returncode, STATUS_EXIT[_answer(name)["status"]])
        self.assertEqual(_answer("ready")["status"], "ok")
        self.assertEqual(_answer("OCCUPIED")["status"], "refused")
        self.assertEqual(_answer("FETCH_FAILED")["status"], "error")
        self.assertEqual(_answer("BOOTSTRAP_FAILED")["status"], "error")

    def test_usage_error_still_emits_one_json_object(self):
        # covers: BO-4300c-2
        # angle: boundary
        """AC-1/AC-4: an unknown verb exits 64 with one JSON object (error, USAGE)."""
        world = _new_world()
        done = _raw(world, ["frobnicate"])
        self.assertEqual(done.returncode, 64, done.stderr[-800:])
        payload = json.loads(done.stdout)
        self.assertEqual(payload.get("status"), "error")
        self.assertEqual(payload.get("code"), "USAGE")

    def test_bo_4300c_2_reachable_from_entry_point(self):
        # covers: BO-4300c-2
        # angle: reachability
        """The deployed worktree.py CLI, run as a subprocess, produces an answer a caller consumes."""
        done, world = _outcome("ready")
        answer = _answer("ready")
        self.assertEqual(done.returncode, 0, done.stderr[-1500:])
        self.assertEqual(answer.get("status"), "ok")
        self.assertEqual(answer.get("code"), "OK")
        self.assertIsInstance(answer.get("schema_version"), int)
        self.assertIn(STUB_NOISE, done.stderr)
        located = _raw(world, ["locate", "--path", answer["workspace_path"],
                               "--repo-root", str(world.project)])
        self.assertEqual(located.returncode, 0, located.stderr[-800:])
        self.assertEqual(json.loads(located.stdout).get("code"), "OK")


if __name__ == "__main__":
    unittest.main()
