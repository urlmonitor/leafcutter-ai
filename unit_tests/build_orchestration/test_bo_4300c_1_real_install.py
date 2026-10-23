"""
MODULE: unit_tests/build_orchestration/test_bo_4300c_1_real_install.py
AC: BO-4300c-1-ii (per-stage protections must fire) / BO-4300c-1 (ready only when protections fire)
GOAL: Prove the REAL deployed install registers one canary-rejecting hook per declared git
    stage (pr-reviewer H-1, decided 2026-10-09), so a real `ensure` answers ok instead of
    refusing HOOKS_INACTIVE, and that removing one stage's registration is refused naming it.
ARCHITECTURE: The fixtures here are NOT hand-typed stubs. The `.pre-commit-config.yaml` and the
    `.leafcutter/` tree come verbatim from the shared deployed layout (ticket 02's locator,
    ensure_deployed_layout(): a real scripts/build.py run); the stub build only copies that real
    install into the new workspace and runs the install's own shim installer plus
    `pre-commit install`. The maker is run as a subprocess; no git mock.

DECISION HISTORY
====================================================================
- 2026-10-09 10:00 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05,
  BO-4300c-1-ii]: Added the real-install red tests for the per-stage canary hook registration
  (H-1). (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05)
====================================================================
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml

from unit_tests.build_orchestration._workspace_maker_fixtures import (
    ensure_deployed_layout,
    make_project,
)
from unit_tests.build_orchestration._workspace_maker_builders import _run_git
from unit_tests.build_orchestration.test_bo_4300c_1 import (
    STAGES,
    MakerTestCase,
    ensure,
    location,
    stage_key,
)

_BUILD = """\
import argparse, os, shutil, subprocess, sys
from pathlib import Path
DEPLOYED = Path(__DEPLOYED__)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target-dir", required=True)
    parser.add_argument("--config-path", default=None)
    target = Path(parser.parse_args().target_dir)
    shutil.copytree(DEPLOYED / ".leafcutter", target / ".leafcutter", dirs_exist_ok=True)
    (target / "INSTALLED_MARKER.txt").write_text("installed\\n", encoding="utf-8")
    env = dict(os.environ)
    for cmd in (
        [sys.executable, "-m", "pre_commit", "install", "--hook-type", "pre-commit"],
        [sys.executable, ".leafcutter/scripts/commit_guardian/install_pre_commit_shims.py"],
    ):
        done = subprocess.run(cmd, cwd=str(target), env=env, capture_output=True, text=True)
        sys.stderr.write(done.stdout + done.stderr)
        if done.returncode != 0:
            return done.returncode
    print("real-install stub build complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""


def _canary_hook(hook: dict, stage: str) -> bool:
    """True when *hook* is a registration of precommit_canary.py --stage <stage> at that stage."""
    entry = str(hook.get("entry", ""))
    return (
        "precommit_canary.py" in entry
        and f"--stage {stage}" in entry
        and stage in (hook.get("stages") or [])
    )


def _real_config_text() -> str:
    return (ensure_deployed_layout() / ".pre-commit-config.yaml").read_text(encoding="utf-8")


def _without_canary(text: str, stage: str) -> str:
    cfg = yaml.safe_load(text)
    for repo in cfg["repos"]:
        repo["hooks"] = [h for h in repo["hooks"] if not _canary_hook(h, stage)]
    return yaml.safe_dump(cfg, sort_keys=False)


def real_install_project(tmp, config_text: str) -> dict:
    """A real bare hub + project whose build copies the REAL deployed install and whose tracked
    `.pre-commit-config.yaml` is *config_text* (derived from the real generated config)."""
    src = _BUILD.replace("__DEPLOYED__", repr(str(ensure_deployed_layout())))
    fx = make_project(Path(tmp), stub_build=src)
    project = fx["project"]
    with open(project / ".pre-commit-config.yaml", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(config_text)
    with open(project / ".gitignore", "w", encoding="utf-8", newline="\n") as fh:
        fh.write("INSTALLED_MARKER.txt\n.leafcutter/\n__pycache__/\n")
    _run_git(["add", "-A"], project)
    _run_git(["commit", "-q", "-m", "real generated hook config"], project)
    _run_git(["push", "-q", "origin", "main"], project)
    return fx


class TestRealInstallStageRegistration(unittest.TestCase):
    def test_real_install_registers_a_canary_hook_per_stage(self):
        # covers: BO-4300c-1-ii
        # angle: real_artifact
        """The generated .pre-commit-config.yaml of a real build runs
        `precommit_canary.py --stage <stage>` at each of pre-commit, commit-msg and post-merge."""
        cfg = yaml.safe_load(_real_config_text())
        hooks = [h for repo in cfg["repos"] for h in repo["hooks"]]
        for stage in STAGES:
            with self.subTest(stage=stage):
                self.assertTrue(
                    any(_canary_hook(h, stage) for h in hooks),
                    f"no hook registration runs precommit_canary.py --stage {stage}",
                )


class TestRealInstallEnsure(MakerTestCase):
    def test_real_install_ensure_answers_ok_with_every_stage_fired(self):
        # covers: BO-4300c-1
        # angle: seam
        """Real producer (generated config + deployed install) into the real maker: ok, every
        declared stage reported fired, a shim per stage in the clone's own .git/hooks."""
        fx = real_install_project(self.tmp, _real_config_text())
        res = ensure(fx, "real-install")
        ans = res["answer"]
        self.assertEqual((ans["status"], res["exit_code"]), ("ok", 0), ans)
        for stage in STAGES:
            with self.subTest(stage=stage):
                self.assertIn(stage, ans["hooks_stages_declared"])
                self.assertIs(ans["checks"][stage_key(stage)], True, ans["checks"])
                self.assertTrue((Path(location(ans)) / ".git" / "hooks" / stage).is_file())
        self.assertIs(ans["checks"]["hooks_canary_rejected"], True)

    def test_removing_one_stage_registration_is_refused_naming_that_stage(self):
        # covers: BO-4300c-1-ii
        # angle: discrimination
        """With the post-merge canary registration removed (the stage stays declared by the
        install's check-ac-done-on-merge hook, which always exits 0) ensure refuses
        HOOKS_INACTIVE naming exactly that stage. Only post-merge is parametrised: at
        pre-commit and commit-msg the install's other real hooks also reject the canary
        input, so removing the canary registration there is not decisive."""
        for stage in ("post-merge",):
            with self.subTest(stage=stage):
                fx = real_install_project(self.tmp / stage, _without_canary(_real_config_text(), stage))
                res = ensure(fx, f"real-no-{stage}")
                ans = res["answer"]
                self.assertNotEqual(ans.get("status"), "ok", ans)
                self.assertIsNone(location(ans))
                self.assertEqual(ans.get("code"), "HOOKS_INACTIVE", ans)
                self.assertEqual(ans.get("inactive_stages"), [stage], ans)
                self.assertIn(stage, json.dumps(ans))


if __name__ == "__main__":
    unittest.main()
