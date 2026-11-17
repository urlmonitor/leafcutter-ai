"""
MODULE: unit_tests/build_orchestration/test_bo_4300e_3.py
AC: BO-4300e-3 -- Loss of unsent work happens only when authorised up front.

Given a workspace holding one unpushed commit and one uncommitted change, and a request to clear it
that was refused listing that commit and that file and returning a one-time token bound to that
workspace and exactly that unsent work, when clearing is requested again with that token in the
request itself, then the workspace is gone completely without any question, the answer lists what
was discarded (commit by identifier, file by path), and the shared project's line of work and main
line are identical before and after.

Q8 (decided 2026-09-28): the token is the refusal's `discard_token`, given as `--discard-token`;
never read from env, config, stdin or a file; nothing is stored between invocations.

Real-subprocess proof against the DEPLOYED maker; real temp repos and bare hub; helpers from
test_bo_4300e_2.py.

DECISION HISTORY
====================================================================
- 2026-10-12 16:30 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/08,
  BO-4300e-3]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/08)
====================================================================
"""
from __future__ import annotations

import ast
import json
import unittest

from unit_tests.build_orchestration._workspace_maker_fixtures import deployed_maker_path
from unit_tests.build_orchestration.test_bo_4300e_2 import WorkspaceCase, names_file, shas_name

TOKEN_ENV_NAMES = (
    "LEAFCUTTER_DISCARD_TOKEN", "DISCARD_TOKEN", "WORKTREE_DISCARD_TOKEN",
    "LEAFCUTTER_WORKSPACE_DISCARD_TOKEN", "LEAFCUTTER_WORKTREE_DISCARD_TOKEN",
)


class TestAuthorisedLoss(WorkspaceCase):
    def test_authorised_remove_deletes_without_any_question(self):
        # covers: BO-4300e-3
        # angle: criterion
        """AC-7: with the discard_token from the preceding UNSENT_WORK refusal given as
        --discard-token and stdin an open pipe nobody writes to, the folder is gone and the answer
        is ok."""
        ws, _sha = self.make_unsent("beta", "b")
        token = self.refuse(ws)["discard_token"]
        res = self.remove(ws, token, stdin="open", timeout=40)
        self.assertEqual(res["answer"].get("status"), "ok", msg=f"{res}")
        self.assertEqual(res["exit_code"], 0)
        self.assertFalse(ws.exists(), msg="authorised remove left the workspace behind")

    def test_refusal_returns_a_discard_token_with_the_unsent_lists(self):
        # covers: BO-4300e-3
        # angle: criterion
        """AC-7: remove without a token is refused UNSENT_WORK (exit 2) listing the unpushed sha and
        the uncommitted path, carries a non-empty discard_token, and leaves the workspace
        byte-identical."""
        ws, sha = self.make_unsent("beta", "b")
        before, heads = self.snap(ws), self.refs(ws)
        res = self.remove(ws)
        answer = res["answer"]
        self.assertEqual((answer.get("code"), res["exit_code"]), ("UNSENT_WORK", 2), msg=f"{res}")
        self.assertTrue(shas_name(answer["unsent"]["commits"], sha), msg=f"{answer}")
        self.assertTrue(names_file(answer["unsent"]["files"], "dirty-b.txt"), msg=f"{answer}")
        self.assertTrue(isinstance(answer.get("discard_token"), str) and answer["discard_token"], msg=f"{answer}")
        self.assertEqual(self.snap(ws), before)
        self.assertEqual(self.refs(ws), heads)

    def test_token_is_not_taken_from_the_environment_or_config(self):
        # covers: BO-4300e-3
        # angle: seam
        """AC-7: with the valid token placed in environment variables and in the project's config,
        remove WITHOUT --discard-token is refused UNSENT_WORK and the workspace is byte-identical.
        Control: the very same token given as --discard-token does authorise (so the token was valid
        and only its channel decided the outcome)."""
        ws, _sha = self.make_unsent("beta", "b")
        token = self.refuse(ws)["discard_token"]
        config = self.project / ".claude" / "skills_config.json"
        data = json.loads(config.read_text(encoding="utf-8"))
        data.update(discard_token=token, worktree={"discard_token": token}, workspace={"discard_token": token})
        config.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8", newline="\n")
        before, heads = self.snap(ws), self.refs(ws)
        res = self.remove(ws, extra_env={name: token for name in TOKEN_ENV_NAMES})
        self.assertEqual(res["answer"].get("code"), "UNSENT_WORK", msg=f"{res}")
        self.assertEqual(self.snap(ws), before)
        self.assertEqual(self.refs(ws), heads)
        self.assertEqual(self.remove(ws, token)["answer"].get("status"), "ok")

    def test_token_is_not_persisted_anywhere(self):
        # covers: BO-4300e-3
        # angle: seam
        """AC-7: after the refusal the token string appears in no file under the test's temp
        directory (project, hub, landing root, workspace, isolated HOME) and not on stderr; it is on
        stdout (the refusal's answer), where it belongs."""
        ws, _sha = self.make_unsent("beta", "b")
        res = self.remove(ws)
        token = res["answer"]["discard_token"]
        self.assertGreaterEqual(len(token), 8, msg="a trivially short token proves nothing")
        self.assertIn(token, res["stdout"])
        self.assertNotIn(token, res["stderr"])
        needle = token.encode("utf-8")
        files = [p for p in self.tmp.rglob("*") if p.is_file()]
        self.assertGreater(len(files), 20, msg="fixture tree looks empty")
        leaks = [str(p) for p in files if needle in p.read_bytes()]
        self.assertEqual(leaks, [], msg=f"the token was written to disk: {leaks}")

    def test_answer_lists_discarded_commit_and_file(self):
        # covers: BO-4300e-3
        # angle: criterion
        """AC-7: discarded.commits holds exactly the unpushed sha and discarded.files exactly the
        uncommitted path."""
        ws, sha = self.make_unsent("beta", "b")
        token = self.refuse(ws)["discard_token"]
        answer = self.remove(ws, token)["answer"]
        self.assertEqual(answer.get("status"), "ok", msg=f"{answer}")
        discarded = answer.get("discarded") or {}
        self.assertEqual(len(discarded.get("commits", [])), 1, msg=f"{answer}")
        self.assertTrue(shas_name(discarded["commits"], sha), msg=f"{discarded}")
        self.assertEqual(len(discarded.get("files", [])), 1, msg=f"{answer}")
        self.assertTrue(names_file(discarded["files"], "dirty-b.txt"), msg=f"{discarded}")

    def test_hub_line_and_main_unchanged_by_authorised_remove(self):
        # covers: BO-4300e-3
        # angle: boundary
        """AC-7: the hub's refs (its branch line and main) and the main checkout's refs and status
        are identical before and after an authorised remove; the hub never gains or loses the
        workspace's branch (no --delete-remote-branch given)."""
        ws, _sha = self.make_unsent("beta", "b")
        token = self.refuse(ws)["discard_token"]
        hub_before = self.refs(self.hub)
        project_before = (self.refs(self.project), self.git(["status", "--porcelain"], self.project))
        self.assertIn("refs/heads/main", hub_before)
        self.assertEqual(self.remove(ws, token)["answer"].get("status"), "ok")
        self.assertFalse(ws.exists())
        self.assertEqual(self.refs(self.hub), hub_before)
        self.assertEqual((self.refs(self.project), self.git(["status", "--porcelain"], self.project)), project_before)


MAKER_FILES = ("worktree_remove.py", "worktree_ensure_state.py")


def _own_nodes(func: ast.AST):
    """Every node of *func*'s body, without descending into nested function definitions."""
    stack = list(ast.iter_child_nodes(func))
    while stack:
        node = stack.pop()
        yield node
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            stack.extend(ast.iter_child_nodes(node))


def _calls_rmtree(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    fn = node.func
    return (isinstance(fn, ast.Attribute) and fn.attr == "rmtree") or (isinstance(fn, ast.Name) and fn.id == "rmtree")


class TestOneDeleteHelper(unittest.TestCase):
    def test_one_delete_helper_and_no_dead_locate(self):
        # covers: BO-4300e-2
        # angle: deployed
        """M17: in the DEPLOYED worktree_remove.py and worktree_ensure_state.py exactly one function
        calls shutil.rmtree, and no locate_ready_only is defined. Must be implemented: the one
        whole-folder delete helper lives in worktree_remove.py and the dead locate_ready_only is
        deleted. Control: the scan really finds the helper (so zero is not a blind scan)."""
        scripts = deployed_maker_path().parent
        callers: list[str] = []
        defined: list[str] = []
        for name in MAKER_FILES:
            path = scripts / name
            self.assertTrue(path.is_file(), msg=f"{path} is not deployed")
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name == "locate_ready_only":
                        defined.append(f"{name}:{node.name}")
                    if any(_calls_rmtree(n) for n in _own_nodes(node)):
                        callers.append(f"{name}:{node.name}")
        self.assertEqual(len(callers), 1, msg=f"functions calling rmtree: {callers}")
        self.assertEqual(defined, [], msg=f"dead code still defined: {defined}")


if __name__ == "__main__":
    unittest.main()
