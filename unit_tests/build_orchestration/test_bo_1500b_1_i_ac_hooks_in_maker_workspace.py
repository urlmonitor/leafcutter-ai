"""
MODULE: unit_tests/build_orchestration/test_bo_1500b_1_i_ac_hooks_in_maker_workspace.py
AC: BO-1500b-1-i -- the fresh authoring workspace is set up so the AC hooks run and gate the
    first stage commit instead of being silently skipped.
GOAL: Re-prove BO-1500b-1-i against the one workspace maker after BO-4300f-2 removed the
    setup script (and tests/test_setup_ticket_worktree.py) that used to prove it. /plan-feature
    now gets its authoring workspace from `worktree.py ensure --kind ac` (BO-4300a-1), so the
    workspace the first stage commit lands in is the one this test asks the maker for.
ARCHITECTURE: Real producer, real consumer. The `.leafcutter/` install comes verbatim from a real
    scripts/build.py run (the shared deployed layout, via the build stub of
    test_bo_4300c_1_real_install), and every hook in the `.pre-commit-config.yaml` that stub
    writes into the workspace is the real generated registration, unedited. As in a real
    project, the hook config and the install are build output, gitignored and never tracked, so
    a fresh checkout of the hub has neither (the AC's Given, asserted on a plain clone). The fixture project
    declares only the hooks this AC is about -- the AC store hooks (check-ac-*) -- plus the stage
    canaries and the self-healing hook the maker's readiness needs, and turns fail_fast off so
    every AC hook reports. (The full generated set also runs project-wide hooks, e.g.
    check-identifier-uniqueness, that refuse any fixture lacking a real project's ticket and
    decision stores.) The deployed maker is run as a subprocess; the commit is a real `git`
    commit through the hooks the maker installed. No git mock, no PRE_COMMIT_ALLOW_NO_CONFIG.
    The negative control commits the same file in a plain clone the maker never set up.

DECISION HISTORY
====================================================================
- 2026-10-21 [smart-bug-resolver/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/18,
  BO-1500b-1-i]: Created under the user's decision "re-prove, else retire" (2026-10-21).
  (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/18)
- 2026-10-21 [smart-bug-resolver/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/18,
  BO-1500b-1-i]: Review M-2: the hook config is now build output (gitignored, untracked) as in
  a real project, and the AC's Given (no hook config, no .leafcutter in a fresh checkout) is
  asserted on a plain clone of the same hub. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/18)
====================================================================
"""
from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

import yaml

from unit_tests.build_orchestration._workspace_maker_fixtures import make_project  # noqa: F401  fixtures first: avoids the builders cycle
from unit_tests.build_orchestration._workspace_maker_builders import (
    _configure_identity,
    _isolated_git_env,
    _run_git,
)
from unit_tests.build_orchestration.test_bo_4300c_1 import MakerTestCase, ensure, location
from unit_tests.build_orchestration._workspace_maker_fixtures import ensure_deployed_layout
from unit_tests.build_orchestration.test_bo_4300c_1_real_install import _BUILD, _real_config_text

# Schema-invalid on purpose: no component, no status, no criteria.
_BAD_AC_REL = "docs/acceptance-criteria/zz-fixture/ZZ-100.yaml"
_BAD_AC_TEXT = "id: ZZ-100\ntitle: A schema-invalid AC staged as an authoring stage's output\n"
_SCHEMA_HOOK = "Check AC Store Schema"
_PARENT_HOOK = "Check AC Parent covered_by Back-Link"
_AC_HOOK_PREFIX = "Check AC "
_KEPT_HOOKS = ("precommit-canary", "ensure-precommit-config", "check-ac-")


def _ac_hooks_config_text() -> str:
    """The real generated config, narrowed to the AC hooks (+ canaries, self-heal), fail_fast off."""
    cfg = yaml.safe_load(_real_config_text())
    for repo in cfg["repos"]:
        repo["hooks"] = [h for h in repo["hooks"] if str(h.get("id", "")).startswith(_KEPT_HOOKS)]
    cfg["repos"] = [repo for repo in cfg["repos"] if repo["hooks"]]
    cfg["fail_fast"] = False
    ids = [h["id"] for repo in cfg["repos"] for h in repo["hooks"]]
    if "check-ac-schema" not in ids or "check-ac-parent-covered-by" not in ids:
        msg = f"the generated config no longer registers the AC hooks: {ids}"
        raise AssertionError(msg)
    return yaml.safe_dump(cfg, sort_keys=False)


def _project_with_untracked_hook_config(tmp: Path) -> dict:
    """A real hub + project whose build writes the AC-hook config, which no commit ever tracks."""
    config_line = "    (target / '.pre-commit-config.yaml').write_text(CONFIG_TEXT, encoding='utf-8')\n"
    anchor = "    env = dict(os.environ)\n"
    stub = _BUILD.replace("__DEPLOYED__", repr(str(ensure_deployed_layout())))
    if stub.count(anchor) != 1:
        msg = "the real-install build stub changed shape; the config write has no anchor"
        raise AssertionError(msg)
    src = "CONFIG_TEXT = " + repr(_ac_hooks_config_text()) + "\n" + stub.replace(anchor, config_line + anchor)
    fx = make_project(Path(tmp), stub_build=src)
    project = fx["project"]
    with open(project / ".gitignore", "w", encoding="utf-8", newline="\n") as fh:
        fh.write("INSTALLED_MARKER.txt\n.leafcutter/\n.pre-commit-config.yaml\n__pycache__/\n")
    _run_git(["rm", "-q", "--cached", ".pre-commit-config.yaml"], project)
    _run_git(["add", "-A"], project)
    _run_git(["commit", "-q", "-m", "hook config is build output"], project)
    _run_git(["push", "-q", "origin", "main"], project)
    return fx


def _plain_clone(fx: dict, tmp: Path, name: str) -> Path:
    """A plain clone of the fixture hub: a fresh checkout nobody has set up."""
    checkout = tmp / name
    _run_git(["clone", "-q", str(fx["hub"]), str(checkout)], tmp)
    _configure_identity(checkout)
    return checkout


def _hook_setup_present(checkout: Path) -> dict[str, bool]:
    return {
        ".pre-commit-config.yaml": (checkout / ".pre-commit-config.yaml").exists(),
        ".leafcutter": (checkout / ".leafcutter").exists(),
        ".git/hooks/pre-commit": (checkout / ".git" / "hooks" / "pre-commit").exists(),
    }


_NOTHING_SET_UP = {".pre-commit-config.yaml": False, ".leafcutter": False, ".git/hooks/pre-commit": False}


def _commit_env() -> dict[str, str]:
    """The fixture git identity, with the no-config skip switch explicitly absent."""
    env = dict(_isolated_git_env())
    env.pop("PRE_COMMIT_ALLOW_NO_CONFIG", None)
    return env


def _stage_and_commit(checkout: Path) -> subprocess.CompletedProcess:
    """Write the bad AC under *checkout*, stage it, and attempt the stage commit."""
    target = checkout / _BAD_AC_REL
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(_BAD_AC_TEXT)
    _run_git(["add", _BAD_AC_REL], checkout)
    return subprocess.run(
        ["git", "commit", "-m", "feat(ac): product-owner stage output"],
        cwd=str(checkout), env=_commit_env(), capture_output=True, text=True, timeout=600, check=False,
    )


def _hook_line(output: str, hook_name: str) -> str:
    """The pre-commit result line for *hook_name*, or '' when the hook did not report."""
    return next((line for line in output.splitlines() if line.startswith(hook_name)), "")


def _head(checkout: Path) -> str:
    return _run_git(["rev-parse", "HEAD"], checkout).stdout.strip()


class TestAcHooksGateTheFirstStageCommit(MakerTestCase):
    def test_ac_hooks_run_and_block_a_bad_stage_commit_in_a_fresh_authoring_workspace(self):
        # covers: BO-1500b-1-i
        # angle: real_artifact
        """Given a fresh checkout of the hub has no hook config, no .leafcutter and no hook
        (asserted on a plain clone, the control, since the maker makes its clone itself), a
        fresh `--kind ac` workspace has its pre-commit configuration in place before any
        commit; committing a schema-invalid AC there runs the AC schema and parent-link hooks
        against it, the schema hook fails, only AC hooks fail, the commit exits non-zero and
        HEAD does not move."""
        fx = _project_with_untracked_hook_config(self.tmp)
        control = _plain_clone(fx, self.tmp, "fresh-checkout-control")
        self.assertEqual(_hook_setup_present(control), _NOTHING_SET_UP, "the Given does not hold")
        res = ensure(fx, "authoring", kind="ac")
        ans = res["answer"]
        self.assertEqual((ans.get("status"), res["exit_code"]), ("ok", 0), ans)
        ws = Path(location(ans))
        self.assertIs(ans["checks"]["precommit_config_present"], True, ans["checks"])
        self.assertTrue((ws / ".pre-commit-config.yaml").is_file())
        self.assertTrue((ws / ".git" / "hooks" / "pre-commit").is_file())
        before = _head(ws)
        done = _stage_and_commit(ws)
        out = done.stdout + done.stderr
        self.assertNotEqual(done.returncode, 0, f"the bad stage commit landed:\n{out[-3000:]}")
        self.assertEqual(_head(ws), before, "HEAD moved: the bad stage commit landed unchecked")
        schema = _hook_line(out, _SCHEMA_HOOK)
        parent = _hook_line(out, _PARENT_HOOK)
        self.assertTrue(schema.endswith("Failed"), f"AC schema hook did not fail the commit: {schema!r}\n{out[-3000:]}")
        self.assertRegex(parent, r"(Passed|Failed)$", f"AC parent-link hook did not run: {parent!r}\n{out[-3000:]}")
        failed = [line for line in out.splitlines() if line.endswith("Failed")]
        self.assertEqual([line for line in failed if not line.startswith(_AC_HOOK_PREFIX)], [], out[-3000:])

    def test_same_bad_commit_lands_in_a_checkout_the_maker_never_set_up(self):
        # covers: BO-1500b-1-i
        # angle: discrimination
        """Negative control: a plain clone of the same project, without the maker's set-up,
        takes the same schema-invalid commit -- so the block above is the set-up's doing."""
        fx = _project_with_untracked_hook_config(self.tmp)
        plain = _plain_clone(fx, self.tmp, "plain-clone")
        self.assertEqual(_hook_setup_present(plain), _NOTHING_SET_UP)
        before = _head(plain)
        done = _stage_and_commit(plain)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertNotEqual(_head(plain), before)
        self.assertEqual(_hook_line(done.stdout + done.stderr, _SCHEMA_HOOK), "")


if __name__ == "__main__":
    unittest.main()
