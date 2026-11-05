"""
MODULE: unit_tests/build_orchestration/test_bo_4300c_2_contract_codes.py
AC: BO-4300c-2 -- the maker answers in the contract's exact shape: no git text in message, a ``step`` field
    naming a failed child-process step, the ensure ok-answer fields, and only the contract's codes (A2).
TICKET: tickets/00_inbox/epics/EPIC-WorkspaceMakerHardening/
    05_TICKET-20261022-ensure-clones-main-checkout-contract-shape.md

Runs the DEPLOYED maker (shared locator); never spawns scripts/build.py itself. The code list is parsed
from BO-4300c-2.yaml's python-coder delivers_to contract; the deployed worktree_answer is loaded in a fresh
subprocess.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from unit_tests.build_orchestration._workspace_maker_fixtures import (  # fixtures first: builders cycle
    deployed_maker_path,
    make_project,
)
from unit_tests.build_orchestration._bo_4300a_1_ii_fixtures import git, maker  # noqa: I001

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AC_YAML = (REPO_ROOT / "docs" / "acceptance-criteria" / "build-orchestration" / "BO-4300-one-way-workspaces"
           / "BO-4300c-2.yaml")


def contract_codes() -> list[str]:
    """The code list of BO-4300c-2's python-coder delivers_to contract (`code (A | B | ...)`)."""
    doc = yaml.safe_load(AC_YAML.read_text(encoding="utf-8"))
    contract = next(d["contract"] for d in doc["delivers_to"] if d.get("agent") == "python-coder")
    match = re.search(r"\bcode \(([^)]*)\)", contract)
    assert match, "no `code (...)` list in the BO-4300c-2 contract"
    return [c.strip() for c in match.group(1).split("|") if c.strip()]


def deployed_code_sets() -> dict[str, list[str]]:
    """ALL_CODES and REFUSED_CODES of the DEPLOYED worktree_answer, read in a fresh interpreter."""
    scripts = deployed_maker_path().parent
    code = ("import json,sys; sys.path.insert(0, sys.argv[1]); import worktree_answer as wa; "
            "print(json.dumps({'all': sorted(wa.ALL_CODES), 'refused': sorted(wa.REFUSED_CODES)}))")
    proc = subprocess.run([sys.executable, "-I", "-c", code, str(scripts)], capture_output=True, text=True,
                          timeout=60, check=False)
    assert proc.returncode == 0, proc.stderr
    data = json.loads(proc.stdout)
    return {"all": data["all"], "refused": data["refused"]}


class _World(unittest.TestCase):
    def new_world(self) -> dict[str, Path]:
        tmp = Path(tempfile.mkdtemp(prefix="bo4300c2cc_")).resolve()
        self.addCleanup(shutil.rmtree, str(tmp), True)
        self.tmp = tmp
        return make_project(tmp / "world")

    def assert_no_git_text(self, res: dict) -> None:
        """No non-empty stderr line (and no 'fatal:') appears in message or step; git's text is on stderr."""
        ans = res["answer"]
        shown = f"{ans.get('message', '')}\n{ans.get('step', '')}"
        self.assertNotIn("fatal:", shown, ans)
        stderr_lines = [ln.strip() for ln in res["stderr"].splitlines() if ln.strip()]
        self.assertTrue(any("fatal:" in ln for ln in stderr_lines),
                        f"control: git's own text must still travel on stderr: {res['stderr']!r}")
        for line in stderr_lines:
            self.assertNotIn(line, shown, f"stderr line leaked into the answer: {line!r}")


class TestNoGitText(_World):
    def test_fetch_failure_message_carries_no_git_text(self):
        # covers: BO-4300c-2
        # angle: deployed
        """The project's origin is repointed at a missing path: ensure answers FETCH_FAILED with a step
        field, and neither message nor step holds any stderr line or 'fatal:'.
        WRONG VERSION: step added but git's stderr still pasted into message."""
        fx = self.new_world()
        git(["remote", "set-url", "origin", str(self.tmp / "no-such-hub.git")], fx["project"])
        res = maker(["ensure", "--kind", "feature", "--slug", "x"], fx["project"])
        ans = res["answer"]
        self.assertEqual((ans.get("status"), ans.get("code")), ("refused", "FETCH_FAILED"), ans)
        self.assertTrue(isinstance(ans.get("step"), str) and ans["step"].strip(), f"no step field: {ans}")
        self.assertTrue(ans.get("message", "").strip(), ans)
        self.assert_no_git_text(res)

    def test_resume_fetch_failure_carries_a_step_and_no_git_text(self):
        # covers: BO-4300c-2
        # angle: failure
        """A ready workspace asked for again after the hub became unreachable: FETCH_FAILED with a step,
        and no git text in message/step (the ready-path fetch site)."""
        fx = self.new_world()
        first = maker(["ensure", "--kind", "feature", "--slug", "x"], fx["project"])
        self.assertEqual(first["answer"].get("status"), "ok", first["answer"])
        moved = self.tmp / "hub-moved.git"
        fx["hub"].rename(moved)
        res = maker(["ensure", "--kind", "feature", "--slug", "x"], fx["project"])
        ans = res["answer"]
        self.assertEqual(ans.get("code"), "FETCH_FAILED", ans)
        self.assertTrue(isinstance(ans.get("step"), str) and ans["step"].strip(), f"no step field: {ans}")
        self.assert_no_git_text(res)


class TestOkAnswerFields(_World):
    def test_ensure_ok_answer_carries_every_contract_field(self):
        # covers: BO-4300c-2
        # angle: deployed
        """A project holding a .env: ensure answers base_ref, origin_main_commit (the hub's main tip),
        base_matches_origin_main true, fetch ok, created true, bootstrap.config_path and
        bootstrap.env_copied listing .env (and not the absent .mcp.json); a second ensure says created false."""
        fx = self.new_world()
        project, hub = fx["project"], fx["hub"]
        (project / ".env").write_text("SECRET=1\n", encoding="utf-8")
        hub_tip = git(["rev-parse", "main"], hub)
        res = maker(["ensure", "--kind", "feature", "--slug", "x"], project)
        ans = res["answer"]
        self.assertEqual((ans.get("status"), res["exit_code"]), ("ok", 0), f"{ans} {res['stderr'][-500:]!r}")
        self.assertEqual(ans.get("base_ref"), "origin/main", ans)
        self.assertEqual(ans.get("origin_main_commit"), hub_tip, ans)
        self.assertIs(ans.get("base_matches_origin_main"), True, ans)
        self.assertEqual(ans.get("fetch"), "ok", ans)
        self.assertIs(ans.get("created"), True, ans)
        boot = ans.get("bootstrap") or {}
        self.assertTrue(isinstance(boot.get("config_path"), str) and boot["config_path"], boot)
        self.assertIn(".env", boot.get("env_copied") or [], boot)
        self.assertNotIn(".mcp.json", boot.get("env_copied") or [], boot)
        again = maker(["ensure", "--kind", "feature", "--slug", "x"], project)["answer"]
        self.assertEqual(again.get("status"), "ok", again)
        self.assertIs(again.get("created"), False, again)


class TestCodes(_World):
    def test_answer_codes_are_the_contract_codes(self):
        # covers: BO-4300c-2
        # angle: criterion
        """The deployed worktree_answer.ALL_CODES is a subset of BO-4300c-2's code list and REFUSED (never a
        contract code, nothing emits it) is in neither ALL_CODES nor REFUSED_CODES."""
        listed = contract_codes()
        self.assertIn("BUILT_FOR_OTHER_TICKET", listed, "parse sanity: the amended contract list")
        sets = deployed_code_sets()
        self.assertEqual(sorted(set(sets["all"]) - set(listed)), [], "codes outside the contract list")
        self.assertNotIn("REFUSED", sets["all"])
        self.assertNotIn("REFUSED", sets["refused"])
        self.assertIn("BUILT_FOR_OTHER_TICKET", sets["refused"])

    def test_non_ok_answers_use_contract_codes(self):
        # covers: BO-4300c-2
        # angle: boundary
        """Real non-ok answers (USAGE, FETCH_FAILED, NOT_FOUND) each carry a code from the contract list."""
        listed = set(contract_codes())
        fx = self.new_world()
        project = fx["project"]
        usage = maker(["ensure", "--kind", "bogus", "--slug", "x"], project)["answer"]
        absent = maker(["verify", "--path", str(self.tmp / "nowhere")], project)["answer"]
        git(["remote", "set-url", "origin", str(self.tmp / "no-such-hub.git")], project)
        fetch = maker(["ensure", "--kind", "feature", "--slug", "x"], project)["answer"]
        self.assertEqual([usage.get("code"), fetch.get("code")], ["USAGE", "FETCH_FAILED"], (usage, fetch))
        for ans in (usage, absent, fetch):
            self.assertNotEqual(ans.get("status"), "ok", ans)
            self.assertIn(ans.get("code"), listed, ans)


if __name__ == "__main__":
    unittest.main()
