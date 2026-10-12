"""
MODULE: unit_tests/build_orchestration/test_bo_4300c_6_real_install.py
AC: BO-4300c-6 (scenario 5: the canaries as an install delivers them are inert on ordinary work,
    reject the reserved inputs, and a reject-everything canary fails the inert proof)
"""
from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

import yaml

from unit_tests.build_orchestration._bo_4300c_6_fixtures import (
    MARKER, assert_inert, declared, deployed_canary, init_repo, merge_branch, observe, run_canary,
    write,
)
from unit_tests.build_orchestration._workspace_maker_builders import _run_git
from unit_tests.build_orchestration._workspace_maker_fixtures import ensure_deployed_layout

STAGES = ("pre-commit", "commit-msg", "post-merge")

_MUTANT_PATCH = """\
import json as _j, subprocess as _sp
_real_run = _sp.run


def _mut_run(cmd, *a, **k):
    done = _real_run(cmd, *a, **k)
    if cmd and cmd[0] == "git" and "--name-only" in cmd and done.returncode == 0 and done.stdout:
        decl = _j.loads(_DECLARATION.read_text(encoding="utf-8"))["stage_canaries"]
        extra = decl["pre-commit"]["path"] + chr(0) + decl["post-merge"]["path"] + chr(0)
        done.stdout = done.stdout + (extra.encode() if isinstance(done.stdout, bytes) else extra)
    return done


_sp.run = _mut_run

"""


def registered_args() -> dict[str, list[str]]:
    """Arguments after the script for each stage, read from the deployed generated config."""
    cfg = yaml.safe_load((ensure_deployed_layout() / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    out: dict[str, list[str]] = {}
    for repo in cfg["repos"]:
        for hook in repo["hooks"]:
            entry = str(hook.get("entry", ""))
            parts = entry.split()
            for stage in STAGES:
                if "precommit_canary.py" in entry and f"--stage {stage}" in entry \
                        and stage in (hook.get("stages") or []):
                    idx = next(i for i, p in enumerate(parts) if p.endswith("precommit_canary.py"))
                    out[stage] = parts[idx + 1:]
    missing = [s for s in STAGES if s not in out]
    if missing:
        raise AssertionError(f"no registered canary entry for {missing}")
    return out


class TestRealInstallCanaries(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory(prefix="bo4300c6-ri-")
        self.addCleanup(self._td.cleanup)
        self.tmp = Path(self._td.name)

    def test_registered_canaries_are_inert_for_ordinary_commit_and_merge_in_a_real_repo(self):
        # covers: BO-4300c-6
        # angle: deployed
        """AC-9: the registered entries, run in a real repo with a real staged file and a real
        --no-ff merge, exit 0 with no marker and no git-failure report."""
        assert_inert(observe(deployed_canary(), registered_args(), self.tmp))

    def test_registered_canaries_reject_reserved_inputs_in_the_same_repo(self):
        # covers: BO-4300c-6
        # angle: criterion
        """AC-10: reserved pre-commit path staged -> exit 1 + marker; merge adding the reserved
        post-merge path -> exit 1 + marker."""
        args = registered_args()
        repo = observe(deployed_canary(), args, self.tmp)["repo"]
        reserved = declared("pre-commit")["path"]
        write(repo, reserved)
        _run_git(["add", reserved], repo)
        done = run_canary(args["pre-commit"], repo)
        self.assertEqual(done.returncode, 1, done.out + done.err)
        self.assertIn(MARKER, done.out)
        merge_branch(repo, "reserved-branch", declared("post-merge")["path"])
        done = run_canary(args["post-merge"], repo)
        self.assertEqual(done.returncode, 1, done.out + done.err)
        self.assertIn(MARKER, done.out)

    def test_reject_everything_canary_fails_the_inert_proof(self):
        # covers: BO-4300c-6
        # angle: discrimination
        """AC-11: a copy of the canary that counts every listed path as reserved is shown to
        reject ordinary input, and then the shared inert proof raises AssertionError for it."""
        mutant_dir = self.tmp / "mutant"
        mutant_dir.mkdir()
        src = deployed_canary()
        shutil.copy2(src.parent / "commit_guardian.json", mutant_dir / "commit_guardian.json")
        text = src.read_text(encoding="utf-8")
        guard = 'if __name__ == "__main__":'
        self.assertIn(guard, text)
        mutant = mutant_dir / "precommit_canary.py"
        mutant.write_text(text.replace(guard, _MUTANT_PATCH + guard, 1), encoding="utf-8")
        obs = observe(mutant, registered_args(), self.tmp)
        for stage in ("pre-commit", "post-merge"):
            with self.subTest(stage=stage):
                self.assertEqual(obs[stage].returncode, 1, obs[stage].out + obs[stage].err)
                self.assertIn(MARKER, obs[stage].out)
                with self.assertRaises(AssertionError):
                    assert_inert(obs, stages=(stage,))


if __name__ == "__main__":
    unittest.main()
