"""
MODULE: unit_tests/build_orchestration/test_bo_4300_docs.py
AC: BO-4300a-3, BO-4300a-4, BO-4300a-5, BO-4300c-5, BO-4300d-5, BO-4300e-5 (ticket 13).
GOAL: Prove the six workspace docs exist as the ACs describe, are reachable from
    docs/INDEX.md, and that every maker command the two how-tos publish RUNS against the
    DEPLOYED maker (real subprocess, real bare hub, real project) with the documented outcome.
BUSINESS CONTEXT: A doc whose published command does not run is a phantom-done doc. Commands
    are extracted from the page's own fenced blocks (any line naming worktree.py), the
    script token is replaced by the deployed maker, and <placeholders> are filled from a
    real fixture; an unfillable placeholder fails the test (the page must publish
    commands a reader can fill in).
ARCHITECTURE: unittest; fixtures from _workspace_maker_fixtures / _workspace_maker_builders
    (the one shared build spawn site); no mocks of git or of the maker.

DECISION HISTORY
====================================================================
- 2026-10-13 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/13,
  BO-4300a-3]: Created the red baseline. Diagram numbers are c3-030 / c3-031 (the
  numbers the ACs' doc_links record; c3-009..c3-011 are taken).
====================================================================
"""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml

from unit_tests.build_orchestration._workspace_maker_fixtures import deployed_maker_path, make_project
from unit_tests.build_orchestration._workspace_maker_builders import _isolated_git_env, _run_git

REPO = Path(__file__).resolve().parents[2]
GET_DOC = REPO / "docs/how-to/get-a-workspace.md"
CLEAR_DOC = REPO / "docs/how-to/clear-a-workspace.md"
REF_DOC = REPO / "docs/reference/workspace-maker-answer.md"
COMPONENT_DOC = REPO / "docs/architecture/components/worktree-manager.md"
SEQ_DOC = REPO / "docs/architecture/diagrams/c3-030-workspace-request-halt-sequence.md"
STATE_DOC = REPO / "docs/architecture/diagrams/c3-031-workspace-request-states.md"
INDEX = REPO / "docs/INDEX.md"
AC_DIR = REPO / "docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces"
RETIRED = ("setup_ticket_worktree",)


def _force_rmtree(path: Path) -> None:
    def _chmod(func, target, _exc):
        os.chmod(target, stat.S_IWRITE)
        func(target)

    shutil.rmtree(path, onerror=_chmod)


def read(path: Path) -> str:
    assert path.is_file(), f"{path.relative_to(REPO)} does not exist"
    return path.read_text(encoding="utf-8")


def frontmatter(path: Path) -> dict[str, Any]:
    text = read(path)
    m = re.match(r"---\r?\n(.*?)\r?\n---\r?\n", text, re.S)
    assert m, f"{path.name}: no frontmatter block"
    data = yaml.safe_load(m.group(1))
    assert isinstance(data, dict), f"{path.name}: frontmatter is not a mapping"
    return data


def assert_doc_frontmatter(tc: unittest.TestCase, path: Path) -> dict[str, Any]:
    fm = frontmatter(path)
    for key in ("title", "description", "type", "status", "created", "last_updated"):
        tc.assertTrue(fm.get(key), f"{path.name}: frontmatter lacks {key}")
    tc.assertTrue({"worktree_manager", "build_orchestration"} <= set(fm.get("components") or []), fm)
    return fm


def assert_in_index(tc: unittest.TestCase, path: Path) -> None:
    rel = path.relative_to(REPO / "docs").as_posix()
    tc.assertIn(rel, read(INDEX), f"{rel} is not reachable from docs/INDEX.md")


def mermaid_blocks(path: Path) -> list[str]:
    return re.findall(r"```mermaid\r?\n(.*?)```", read(path), re.S)


def fenced_text(path: Path) -> str:
    return "\n".join(re.findall(r"```[a-z]*\r?\n(.*?)```", read(path), re.S))


def published_commands(path: Path) -> list[str]:
    """Every command line in a fenced block that names worktree.py (continuations joined)."""
    cmds: list[str] = []
    for block in re.findall(r"```[a-z]*\r?\n(.*?)```", read(path), re.S):
        joined = re.sub(r"\\\r?\n\s*", " ", block)
        cmds += [ln.strip() for ln in joined.splitlines() if "worktree.py" in ln]
    return cmds


def deployed_codes() -> set[str]:
    """The DEPLOYED maker's answer-table codes, read in a fresh subprocess."""
    scripts = deployed_maker_path().parent
    out = subprocess.run(
        [sys.executable, "-c", "import json,worktree_answer as a;print(json.dumps(sorted(a.ALL_CODES)))"],
        cwd=str(scripts), capture_output=True, text=True, timeout=60, check=False)
    assert out.returncode == 0, out.stderr
    return set(json.loads(out.stdout))


class DocMakerCase(unittest.TestCase):
    """Real project + hub; runs a doc's published commands against the deployed maker."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="bo4300doc-")).resolve()
        self.addCleanup(_force_rmtree, self.tmp)
        self.home = self.tmp / "home"
        self.home.mkdir()
        shutil.copyfile(_isolated_git_env()["GIT_CONFIG_GLOBAL"], self.home / ".gitconfig")
        self.fx = make_project(self.tmp / "world")
        self.project: Path = self.fx["project"]
        self.maker = deployed_maker_path()
        self.values = {"kind": "scratch", "slug": "doc-proof", "repo": str(self.project),
                       "project": str(self.project), "maker": str(self.maker)}

    def env(self) -> dict[str, str]:
        env = _isolated_git_env()
        env.update(HOME=str(self.home), USERPROFILE=str(self.home),
                   GIT_CONFIG_GLOBAL=str(self.home / ".gitconfig"))
        return env

    def fill(self, command: str) -> list[str]:
        """Substitute <placeholders> and the maker path; fail on anything unfillable."""
        def sub(m: re.Match) -> str:
            name = m.group(1).lower().replace("-", "_")
            for hint, key in (("token", "token"), ("path", "path"), ("location", "path"),
                              ("kind", "kind"), ("slug", "slug"), ("repo", "repo"),
                              ("project", "project"), ("work", "slug")):
                if hint in name and key in self.values:
                    return self.values[key]
            self.fail(f"unfillable placeholder {m.group(0)!r} in published command: {command}")
        text = re.sub(r"<([^<>]+)>", sub, command)
        argv = shlex.split(text, posix=True)
        idx = next((i for i, a in enumerate(argv) if a.endswith("worktree.py")), None)
        self.assertIsNotNone(idx, command)
        self.assertNotIn("$", text, f"unexpanded shell variable in: {command}")
        return [sys.executable, str(self.maker), *argv[idx + 1:]]

    def run_cmd(self, command: str) -> tuple[dict[str, Any], int]:
        proc = subprocess.run(self.fill(command), cwd=str(self.project), capture_output=True,
                              text=True, timeout=120, env=self.env(), check=False)
        objs = []
        for ln in proc.stdout.splitlines():
            try:
                objs.append(json.loads(ln))
            except ValueError:
                continue
        self.assertEqual(len(objs), 1, f"{command}: stdout not one JSON object: {proc.stdout!r} {proc.stderr!r}")
        return objs[0], proc.returncode

    @staticmethod
    def verb(command: str) -> str:
        after = command.split("worktree.py", 1)[1].split()
        return after[0] if after else ""


class TestGetAWorkspaceHowTo(DocMakerCase):
    def test_get_a_workspace_how_to_publishes_a_maker_command_that_runs(self):
        # covers: BO-4300a-3
        # angle: real_artifact
        """docs/how-to/get-a-workspace.md exists, is indexed, and each published command answers ok."""
        assert_doc_frontmatter(self, GET_DOC)
        assert_in_index(self, GET_DOC)
        cmds = published_commands(GET_DOC)
        runnable = [c for c in cmds if self.verb(c) in ("ensure", "locate", "list", "verify", "where")]
        verbs = {self.verb(c) for c in runnable}
        self.assertIn("ensure", verbs, f"page must publish the ensure request: {cmds}")
        self.assertIn("locate", verbs, f"page must publish how to read the location back: {cmds}")
        for cmd in sorted(runnable, key=lambda c: self.verb(c) != "ensure"):  # ensure first
            answer, code = self.run_cmd(cmd)
            self.assertEqual((answer.get("status"), code), ("ok", 0), f"{cmd} -> {answer}")
            if self.verb(cmd) == "ensure":
                self.values["path"] = answer["workspace_path"]
        text = read(GET_DOC)
        self.assertIn("workspace_path", text)
        self.assertRegex(text, r"(?i)ask(ing)? again[^.]*safe|safe[^.]*ask(ing)? again|always safe")
        self.assertIn("clear-a-workspace.md", text)
        self.assertIn("workspace-maker-answer.md", text)
        banned = ("git worktree add", "git clone", "ln -s", "mklink", "cp -r", "symlink(")
        block_text = fenced_text(GET_DOC)
        for needle in banned:
            self.assertNotIn(needle, block_text, f"hand-made recipe in fenced block: {needle}")
        for name in RETIRED:
            self.assertNotIn(name, text)

    def test_ticket_13_reachable_from_entry_point(self):
        # covers: BO-4300a-3
        # angle: reachability
        """The published ensure command, run as a real CLI from three starting points, answers ok."""
        cmds = [c for c in published_commands(GET_DOC) if self.verb(c) == "ensure"]
        self.assertTrue(cmds, "get-a-workspace.md publishes no ensure command")
        paths = set()
        parent = self.project.parent
        for cwd in (self.project, parent):
            proc = subprocess.run(self.fill(cmds[0]), cwd=str(cwd), capture_output=True, text=True,
                                  timeout=120, env=self.env(), check=False)
            answer = json.loads(proc.stdout.strip().splitlines()[-1])
            self.assertEqual((answer["status"], proc.returncode), ("ok", 0), (cwd, answer))
            self.assertTrue(Path(answer["workspace_path"]).is_dir())
            paths.add(answer["workspace_path"])
        self.assertEqual(len(paths), 1, "asking again from another folder must reach the same workspace")


class TestClearAWorkspaceHowTo(DocMakerCase):
    def test_clear_a_workspace_how_to_publishes_a_remove_command_that_runs(self):
        # covers: BO-4300e-5
        # angle: real_artifact
        """remove on unsent work is refused with a discard_token; the documented repeat clears it."""
        assert_doc_frontmatter(self, CLEAR_DOC)
        assert_in_index(self, CLEAR_DOC)
        cmds = published_commands(CLEAR_DOC)
        plain = [c for c in cmds if self.verb(c) == "remove" and "--discard-token" not in c]
        token = [c for c in cmds if self.verb(c) == "remove" and "--discard-token" in c]
        locate = [c for c in cmds if self.verb(c) == "locate"]
        self.assertTrue(plain and token and locate, f"need locate, remove and remove --discard-token: {cmds}")
        # A real workspace holding one unpushed commit.
        made = subprocess.run([sys.executable, str(self.maker), "ensure", "--kind", "scratch",
                               "--slug", "doc-proof"], cwd=str(self.project), capture_output=True,
                              text=True, timeout=120, env=self.env(), check=False)
        ws = Path(json.loads(made.stdout.strip().splitlines()[-1])["workspace_path"])
        self.values["path"] = str(ws)
        (ws / "UNSENT.txt").write_text("unsent\n", encoding="utf-8", newline="\n")
        _run_git(["add", "UNSENT.txt"], ws)
        _run_git(["commit", "-q", "-m", "unsent work"], ws)
        answer, code = self.run_cmd(locate[0])
        self.assertEqual((answer["status"], code), ("ok", 0), answer)
        refusal, code = self.run_cmd(plain[0])
        self.assertEqual((refusal.get("code"), code), ("UNSENT_WORK", 2), refusal)
        self.assertTrue(refusal.get("discard_token"), refusal)
        self.assertTrue(ws.is_dir(), "a refused remove must leave the workspace as it was")
        self.values["token"] = refusal["discard_token"]
        cleared, code = self.run_cmd(token[0])
        self.assertEqual((cleared["status"], code), ("ok", 0), cleared)
        self.assertFalse(ws.exists(), "the documented discard repeat must clear the workspace")
        text = read(CLEAR_DOC)
        self.assertIn("get-a-workspace.md", text)
        self.assertRegex(text, r"(?i)unpushed commit")
        self.assertRegex(text, r"(?i)uncommitted")
        block_text = fenced_text(CLEAR_DOC)
        for needle in ("rm -rf", "rmdir", "git worktree remove", "rmtree", "Remove-Item"):
            self.assertNotIn(needle, block_text, f"manual deletion bypasses the maker: {needle}")


class TestAnswerReference(unittest.TestCase):
    def test_answer_reference_points_at_the_contract_record(self):
        # covers: BO-4300a-5
        # angle: real_artifact
        """Reference lists every deployed code, discard_token, and the caller rules."""
        assert_doc_frontmatter(self, REF_DOC)
        assert_in_index(self, REF_DOC)
        text = read(REF_DOC)
        self.assertIn("BO-4300c-2", text)
        missing = [c for c in sorted(deployed_codes()) if not re.search(rf"\b{c}\b", text)]
        self.assertEqual(missing, [], f"codes missing from the reference: {missing}")
        for needle in ("AMBIGUOUS_LINE", "discard_token", "--discard-token", "schema_version", "lines"):
            self.assertIn(needle, text)
        self.assertRegex(text, r"(?i)anything (other|but)[^.]*\bok\b[^.]*stop|stop[^.]*anything (other|but)")
        self.assertRegex(text, r"(?i)workspace_path[^.]*(only|never)")
        self.assertRegex(text, r"(?i)same form|same shape|same answer")


class TestComponentDiagram(unittest.TestCase):
    def test_component_diagram_names_the_one_maker_and_every_caller(self):
        # covers: BO-4300a-4
        # angle: real_artifact
        """worktree-manager.md carries a valid-typed mermaid component diagram of maker + callers."""
        fm = frontmatter(COMPONENT_DOC)
        types = json.loads(read(REPO / "config/diagram_types.json"))["diagram_types"]
        self.assertIn(fm.get("diagram_type"), types)
        blocks = mermaid_blocks(COMPONENT_DOC)
        self.assertTrue(blocks, "no mermaid block")
        diagram = "\n".join(blocks)
        self.assertRegex(diagram, r"^\s*C4Component|^\s*(flowchart|graph)", )
        for needle in ("worktree.py", "workspace_root.py", "shell-runner", "skill", "workflow",
                       "Person", "agent", "Landing place", "Main copy", "Hub"):
            self.assertRegex(diagram, rf"(?i){re.escape(needle)}", f"diagram lacks {needle}")
        for name in RETIRED:
            self.assertNotIn(name, diagram)
        for rel in ("c3-030-workspace-request-halt-sequence.md", "c3-031-workspace-request-states.md"):
            self.assertIn(rel, read(COMPONENT_DOC))


class TestSequenceDiagram(unittest.TestCase):
    def test_halt_sequence_diagram_exists_and_shows_the_halt_path(self):
        # covers: BO-4300c-5
        # angle: real_artifact
        """The sequence diagram shows ready and a halt per non-ready class; the AC points at it."""
        self.assertEqual(frontmatter(SEQ_DOC).get("diagram_type"), "sequence")
        diagram = "\n".join(mermaid_blocks(SEQ_DOC))
        self.assertIn("sequenceDiagram", diagram)
        for needle in ("Caller", "worktree.py", "Hub", "workspace_path"):
            self.assertIn(needle, diagram)
        branches = re.findall(r"^\s*(?:alt|else)\s+(.*)$", diagram, re.M)
        halts = [b for b in branches if re.search(r"(?i)refus|error|prose|decline|no answer", b)]
        self.assertGreaterEqual(len(halts), 4, branches)
        self.assertEqual(len(re.findall(r"nothing dispatched", diagram)), len(branches) - 1,
                         "every non-ready branch must end the run before any working step")
        ac = yaml.safe_load(read(AC_DIR / "BO-4300c-5.yaml"))
        paths = {d["path"]: d["status"] for d in ac.get("doc_links", [])}
        self.assertEqual(paths.get(SEQ_DOC.relative_to(REPO).as_posix()), "exists")


class TestStateDiagram(unittest.TestCase):
    def test_state_diagram_exists_and_names_every_request_state(self):
        # covers: BO-4300d-5
        # angle: real_artifact
        """The state diagram names the four states, codes on refused edges, no edge leaving occupied."""
        self.assertEqual(frontmatter(STATE_DOC).get("diagram_type"), "state")
        diagram = "\n".join(mermaid_blocks(STATE_DOC))
        self.assertIn("stateDiagram", diagram)
        for needle in ("Absent", "HalfMade", "Ready", "Occupied"):
            self.assertIn(needle, diagram)
        edges = re.findall(r"^\s*(\w+)\s*-->\s*(\w+)\s*:?\s*(.*)$", diagram, re.M)
        self.assertEqual([e for e in edges if e[0] == "Occupied" and e[1] != "Occupied"], [])
        self.assertTrue(any(e[0] == "Occupied" for e in edges))
        for src, dst, label in edges:
            if "refused" in label:
                self.assertRegex(label, r"[A-Z]{2,}_[A-Z_]+", f"refused edge {src}->{dst} names no code")
        ac = yaml.safe_load(read(AC_DIR / "BO-4300d-5.yaml"))
        paths = {d["path"]: d["status"] for d in ac.get("doc_links", [])}
        self.assertEqual(paths.get(STATE_DOC.relative_to(REPO).as_posix()), "exists")


if __name__ == "__main__":
    unittest.main()
