"""
MODULE: unit_tests/build_orchestration/test_bo_4300b_4.py
AC: BO-4300b-4 -- On Windows without permission to create links, the workspace is still fully ready
Two arms. Arm 1 (real Windows CI job without Developer Mode, .github/workflows/ci.yml) runs
test_windows_arm_no_injection on win32 only and is reported SKIPPED ("not run"), never passed,
elsewhere. Arm 2 denies os.symlink to the maker process via an injected sitecustomize on every platform.

DECISION HISTORY
====================================================================
- 2026-09-30 23:40 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05,
  BO-4300b-4]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05)
====================================================================
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

from unit_tests.build_orchestration.test_bo_4300c_1 import (
    SENT,
    STAGES,
    MakerTestCase,
    build_project,
    ensure,
    location,
)
from unit_tests.build_orchestration._workspace_maker_builders import _isolated_git_env

_SITECUSTOMIZE = (
    "import os\n"
    "def _deny(*a, **k):\n"
    "    raise OSError(1314, 'A required privilege is not held by the client (injected)')\n"
    "os.symlink = _deny\n"
)


def link_like(p: Path) -> bool:
    """True for a symlink or a Windows junction / reparse point."""
    if os.path.islink(p):
        return True
    attrs = getattr(os.lstat(p), "st_file_attributes", 0)
    return bool(attrs & 0x400)


def deny_env(tmp: Path) -> dict[str, str]:
    """Env that makes os.symlink raise in the maker and every child it spawns."""
    d = tmp / "deny-links"
    d.mkdir(parents=True, exist_ok=True)
    (d / "sitecustomize.py").write_text(_SITECUSTOMIZE, encoding="utf-8")
    existing = os.environ.get("PYTHONPATH")
    return {"PYTHONPATH": str(d) + (os.pathsep + existing if existing else "")}


def _tree(ws: Path) -> list[str]:
    out = []
    for root, dirs, files in os.walk(ws):
        rel = Path(root).relative_to(ws)
        if rel.parts[:1] == (".git",) and rel.parts[:2] != (".git", "hooks"):
            dirs[:] = []
            continue
        out.extend(str(rel / f).replace("\\", "/") for f in files)
    return sorted(out)


class TestNoLinks(MakerTestCase):
    def _denied_ensure(self, sub="a"):
        root = self.tmp / sub
        fx = build_project(root)
        env = deny_env(root)
        probe = subprocess.run(
            [sys.executable, "-c", "import os; os.symlink('x', 'y')"],
            cwd=str(root), env={**os.environ, **env}, capture_output=True, text=True,
        )
        self.assertNotEqual(probe.returncode, 0, "fixture failed to deny symlink creation")
        return fx, root, ensure(fx, "nolinks", extra_env=env)

    def test_ensure_is_ready_when_symlinks_are_denied(self):
        # covers: BO-4300b-4
        # angle: criterion
        """With os.symlink raising for the maker and its children, ensure is ok, exit 0."""
        _fx, _root, res = self._denied_ensure()
        self.assertEqual((res["answer"]["status"], res["exit_code"]), ("ok", 0), res["answer"])
        # fully ready means every protection fired, not just that the maker answered ok
        for key in ("hooks_pre_commit_fired", "hooks_commit_msg_fired", "hooks_post_merge_fired",
                    "hooks_canary_rejected", "build_ok", "tree_clean"):
            self.assertIs(res["answer"]["checks"].get(key), True, res["answer"]["checks"])

    def test_install_and_protection_paths_are_regular_files(self):
        # covers: BO-4300b-4
        # angle: real_artifact
        """No path under the install or hook set, nor .pre-commit-config.yaml, is a symlink or junction."""
        _fx, _root, res = self._denied_ensure()
        ws = Path(location(res["answer"]))
        seen = 0
        for top in (ws / ".leafcutter", ws / ".git" / "hooks"):
            for root, dirs, files in os.walk(top):
                for name in dirs + files:
                    seen += 1
                    self.assertFalse(link_like(Path(root) / name), f"{root}/{name} is a link")
        self.assertGreater(seen, 3)
        for stage in STAGES:
            self.assertTrue((ws / ".git" / "hooks" / stage).is_file(), f"no shim for {stage}")
        config = ws / ".pre-commit-config.yaml"
        self.assertTrue(config.is_file() and not link_like(config))

    def test_known_bad_commit_is_rejected_when_symlinks_are_denied(self):
        # covers: BO-4300b-4
        # angle: criterion
        """A commit of the known-bad file in that workspace is rejected by the installed hook."""
        _fx, _root, res = self._denied_ensure()
        ws = Path(location(res["answer"]))
        (ws / "known_bad.txt").write_text(SENT["pre-commit"] + "\n", encoding="utf-8")
        env = _isolated_git_env()
        subprocess.run(["git", "add", "known_bad.txt"], cwd=str(ws), env=env, check=True, capture_output=True)
        commit = subprocess.run(["git", "commit", "-q", "-m", "bad"], cwd=str(ws), env=env,
                                capture_output=True, text=True)
        self.assertNotEqual(commit.returncode, 0, commit.stdout + commit.stderr)

    def test_answers_with_and_without_link_permission_are_equivalent(self):
        # covers: BO-4300b-4
        # angle: boundary
        """Normalising paths, timestamps and shas, the denied and permitted answers and trees are equal."""
        _fx_a, root_a, denied = self._denied_ensure("denied")
        root_b = self.tmp / "permitted"
        fx_b = build_project(root_b)
        permitted = ensure(fx_b, "nolinks")
        self.assertEqual(denied["answer"]["status"], "ok", denied["answer"])
        self.assertIs(denied["answer"]["checks"].get("hooks_canary_rejected"), True, denied["answer"])
        self.assertEqual(permitted["answer"]["status"], "ok", permitted["answer"])

        def norm(value, root):
            if isinstance(value, dict):
                return {k: norm(v, root) for k, v in value.items()
                        if "created_at" not in k and "time" not in k}
            if isinstance(value, list):
                return [norm(v, root) for v in value]
            if isinstance(value, str):
                variants = {str(root), root.as_posix(), str(root.resolve()), root.resolve().as_posix()}
                variants |= {"/mnt/" + v[0].lower() + v[2:] for v in list(variants) if re.match(r"^[A-Za-z]:/", v)}
                for variant in sorted(variants, key=len, reverse=True):
                    value = value.replace(variant, "<ROOT>")
                return re.sub(r"\b[0-9a-f]{40}\b", "<SHA>", value)
            return value

        self.assertEqual(norm(denied["answer"], root_a), norm(permitted["answer"], root_b))
        self.assertEqual(_tree(Path(location(denied["answer"]))), _tree(Path(location(permitted["answer"]))))

    def test_windows_arm_no_injection(self):
        # manual-evidence = recorded proof CI cannot run (needs a real Windows runner
        # without Developer Mode); not a covers tag, so done-proof never reads its skip
        # as "not run" (KI-ACS-20261013; user decision 2026-10-21 "Re-mark non-CI tests").
        # manual-evidence: BO-4300b-4
        # angle: criterion
        """Arm 1: on a real Windows runner without Developer Mode, ensure is ready with no injection."""
        if sys.platform != "win32":
            self.skipTest("arm 1 not run: needs a real Windows runner without Developer Mode")
        fx = build_project(self.tmp)
        res = ensure(fx, "win-native")
        self.assertEqual((res["answer"]["status"], res["exit_code"]), ("ok", 0), res["answer"])
        ws = Path(location(res["answer"]))
        for root, dirs, files in os.walk(ws / ".leafcutter"):
            for name in dirs + files:
                self.assertFalse(link_like(Path(root) / name))


if __name__ == "__main__":
    unittest.main()
