"""
MODULE: test_bo_4300c_3
GOAL: Red-first behavioural tests for BO-4300c-3 -- every workflow that needs a
    workspace stops on anything but a ready answer, quoting what it received,
    dispatching nothing after the workspace step and continuing nowhere.
PROOF SHAPE: the DEPLOYED workflows (shared reference layout, read-only; no
    build.py spawn) run under unit_tests/_workflow_engine_harness.py with the
    workspace step's reply scripted by label. Assertions are on the RECORDED
    dispatch list and the run's terminal payload, never on workflow source
    text -- except the parity/coverage checks, whose subject IS the deployed
    text between the WORKSPACE-ANSWER markers.
    The build inliner is exercised against a temporary templates tree through
    scripts/build_phases_workflows.py (never build.py as a subprocess).
SOURCE-BLOCK CONVENTION (declared here, one place): the single tracked source
    is templates/workflows-js/_shared/workspace-answer.js and its WHOLE file is
    the block; templates carry only an empty marker pair
    ``// WORKSPACE-ANSWER-START`` / ``// WORKSPACE-ANSWER-END``. One leading and
    one trailing newline around the block are not significant.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pytest

from . import _bo4300a1ia_support as S

_SCRIPTS = S.REPO_ROOT / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

START = "// WORKSPACE-ANSWER-START"
END = "// WORKSPACE-ANSWER-END"
SOURCE_REL = Path("workflows-js") / "_shared" / "workspace-answer.js"

SIX = ("build-epic.js", "build-ticket.js", "quick-fix.js", "plan-feature.js",
       "fast-lane-ship.js", "finalize-feature.js")

START_FOLDER = "/tmp/bo4300c3/start-folder"
MAIN_COPY = "/tmp/bo4300c3/main-copy"
UNGIVEN = "/tmp/bo4300c3/ungiven-location"
READY_PATH = "/tmp/bo4300c3/ws-ready"
HEAD = "ZZ-HEAD-MARKER-4300c3"
TAIL = "ZZ-TAIL-MARKER-4300c3"

ARGS = {
    "worktree_path": START_FOLDER,
    "caller_worktree_path": START_FOLDER,
    "cwd": START_FOLDER,
    "main_copy": MAIN_COPY,
}

HOSTILE = {
    "refusal": {"status": "refused", "reason": f"{HEAD}-refusal"},
    "error": {"status": "error", "message": f"{HEAD}-error"},
    "prose": HEAD + "-prose " + ("all is well, nothing to see here. " * 150) + TAIL,
    "neither": {"status": "pending", "note": f"{HEAD}-neither", "workspace_path": UNGIVEN},
    "none": None,
}

_BASELINE: dict | None = None


def tearDownModule():  # noqa: N802
    S.cleanup_world()


def _baseline() -> dict:
    global _BASELINE
    if _BASELINE is None:
        _BASELINE = S.collect_runs(S.deployed_workflow_dir())
    return _BASELINE


def _consumers() -> dict:
    return S.needing_workspace(_baseline())


def _run(name: str, reply, directory: Path | None = None):
    calls = _consumers().get(name)
    assert calls, f"{name} issues no workspace request (no workspace step to script)"
    label = calls[0].label
    run = S.run_workflow((directory or S.deployed_workflow_dir()) / name,
                         label_responses={label: reply}, args=ARGS)
    idx = next(i for i, c in enumerate(run.agent_calls) if c.label == label)
    return run, idx


def _status(run):
    return run.result.get("status") if isinstance(run.result, dict) else None


def _between(text: str) -> str | None:
    if START not in text or END not in text:
        return None
    return text.split(START, 1)[1].split(END, 1)[0]


def _norm(block: str) -> str:
    return block.strip("\n")


def _source_block() -> str:
    return _norm((S.REPO_ROOT / "templates" / SOURCE_REL).read_text(encoding="utf-8"))


def consumers_without_block(directory: Path) -> tuple[list[str], list[str]]:
    """(workflows consuming a workspace, subset lacking an identical block)."""
    block = _source_block()
    consuming, bad = [], []
    for path in S.workflow_paths(directory):
        text = path.read_text(encoding="utf-8")
        if not re.search(r"\bargs\.workspace\b", text) and path.name not in _consumers():
            continue
        consuming.append(path.name)
        inner = _between(text)
        if inner is None or _norm(inner) != block:
            bad.append(path.name)
    return consuming, bad


@pytest.mark.shared_layout_reader
class TestBo4300c3(unittest.TestCase):
    def test_each_workflow_ends_in_failure_on_each_non_ready_answer(self):
        # covers: BO-4300c-3
        # angle: failure
        """AC-1: 6 workflows x 5 hostile answers -> every run ends with status error."""
        consumers = _consumers()
        self.assertTrue(set(SIX) <= set(consumers),
                        f"workflows without a workspace step: {sorted(set(SIX) - set(consumers))}")
        for name in SIX:
            for kind, reply in HOSTILE.items():
                with self.subTest(workflow=name, answer=kind):
                    run, _ = _run(name, reply)
                    self.assertEqual(_status(run), "error", (run.result, run.stderr[-400:]))

    def test_failure_quotes_what_was_received(self):
        # covers: BO-4300c-3
        # angle: criterion
        """AC-1: the failure message contains the received answer, bounded to 2 KB."""
        for name in SIX:
            for kind, reply in HOSTILE.items():
                with self.subTest(workflow=name, answer=kind):
                    run, _ = _run(name, reply)
                    text = json.dumps(run.result)
                    if kind == "none":
                        self.assertRegex(text, r"(?i)no answer|nothing|empty|null|none|undefined")
                        continue
                    self.assertIn(HEAD, text, "received answer is not quoted")
                    if kind == "prose":
                        self.assertNotIn(TAIL, text, "quote is not bounded to 2 KB")
                        self.assertLess(len(text), 2048 + 1500)

    def test_no_authoring_phase_commit_or_delivery_step_is_dispatched_after_the_workspace_step(self):
        # covers: BO-4300c-3
        # angle: criterion
        """AC-2: in every run the recorded dispatch list ends at the workspace step."""
        for name in SIX:
            for kind, reply in HOSTILE.items():
                with self.subTest(workflow=name, answer=kind):
                    run, idx = _run(name, reply)
                    self.assertEqual([c.label for c in run.agent_calls[idx + 1:]], [])

    def test_no_run_continues_in_main_copy_epic_folder_start_folder_or_any_ungiven_location(self):
        # covers: BO-4300c-3
        # angle: boundary
        """AC-3: no dispatch after a hostile answer names a location not given by an ok
        answer; the control row (ok answer) proves the later dispatches carry the given one."""
        for name in SIX:
            with self.subTest(workflow=name, answer="ok-control"):
                run, idx = _run(name, {"status": "ok", "workspace_path": READY_PATH,
                                       "worktree_path": READY_PATH})
                later = [str(c.prompt) for c in run.agent_calls[idx + 1:]]
                self.assertTrue(later, "nothing dispatched after an ok answer")
                self.assertTrue(any(READY_PATH in p for p in later))
            for kind, reply in HOSTILE.items():
                with self.subTest(workflow=name, answer=kind):
                    run, idx = _run(name, reply)
                    later = [str(c.prompt) for c in run.agent_calls[idx + 1:]]
                    self.assertEqual(later, [])
                    if isinstance(run.result, dict):
                        for key in ("workspace_path", "worktree_path", "cwd"):
                            self.assertNotIn(run.result.get(key), (UNGIVEN, START_FOLDER, MAIN_COPY))
                            self.assertNotIn(run.result.get(key), (S.GENERIC_ARGS["epic_path"],))

    def test_workspace_answer_block_is_byte_identical_in_every_deployed_consumer(self):
        # covers: BO-4300c-3
        # angle: deployed
        """Deployed text between the markers equals the single source block; a difference
        names the workflow."""
        self.assertTrue((S.REPO_ROOT / "templates" / SOURCE_REL).is_file(), "single source block missing")
        self.assertFalse((S.deployed_workflow_dir() / "workspace-answer.js").exists(),
                         "the shared source must not deploy as a workflow")
        block = _source_block()
        self.assertTrue(block)
        carriers = 0
        for path in S.workflow_paths(S.deployed_workflow_dir()):
            inner = _between(path.read_text(encoding="utf-8"))
            if inner is None:
                continue
            carriers += 1
            with self.subTest(workflow=path.name):
                self.assertEqual(_norm(inner), block, f"block differs in {path.name}")
        self.assertGreaterEqual(carriers, len(SIX))

    def test_every_workspace_consuming_workflow_carries_the_block(self):
        # covers: BO-4300c-3
        # angle: failure
        """Every deployed workflow consuming a workspace carries the block; a fixture
        consumer without it is reported by name."""
        consuming, bad = consumers_without_block(S.deployed_workflow_dir())
        self.assertTrue(set(SIX) <= set(consuming))
        self.assertEqual(bad, [])
        holder = S.copy_with_extra_workflow(
            S.deployed_workflow_dir(), "zz-consumer.js",
            "const w = args.workspace;\nreturn { status: 'ok', w };\n")
        self.addCleanup(holder.cleanup)
        _, bad_fixture = consumers_without_block(Path(holder.name) / "workflows")
        self.assertEqual(bad_fixture, ["zz-consumer.js"])

    def test_bo_4300c_3_reachable_from_entry_point(self):
        # covers: BO-4300c-3
        # angle: reachability
        """Entry point: each consuming deployed workflow dispatched under the E2 harness.
        A refusal ends the run at the workspace step; an ok answer is consumed (later
        dispatches carry its path) -- the answer decides control flow."""
        consumers = _consumers()
        self.assertTrue(consumers)
        for name in consumers:
            with self.subTest(workflow=name):
                bad, bad_idx = _run(name, HOSTILE["refusal"])
                self.assertEqual(_status(bad), "error")
                self.assertEqual(len(bad.agent_calls), bad_idx + 1)
                good, good_idx = _run(name, {"status": "ok", "workspace_path": READY_PATH})
                self.assertTrue(any(READY_PATH in str(c.prompt) for c in good.agent_calls[good_idx + 1:]))


class TestBo4300c3BuildInliner(unittest.TestCase):
    """Seam: the real build phase against a temporary templates tree."""

    BLOCK = "function acceptWorkspaceAnswer(raw) { return { accepted: false, reason: 'x' }; }\n"

    def _tree(self, template_body: str):
        holder = tempfile.TemporaryDirectory(prefix="bo4300c3_tpl_")
        self.addCleanup(holder.cleanup)
        templates = Path(holder.name) / "templates"
        (templates / "workflows-js" / "_shared").mkdir(parents=True)
        (templates / SOURCE_REL).write_text(self.BLOCK, encoding="utf-8")
        (templates / "workflows-js" / "demo.js").write_text(template_body, encoding="utf-8")
        return templates, Path(holder.name) / "target"

    def _build(self, templates: Path, target: Path) -> int:
        import build_phases as bp
        from build_phases_workflows import build_workflow_scripts
        with mock.patch.object(bp, "TEMPLATES_DIR", templates), \
                mock.patch.dict(os.environ, {"CLAUDE_CODE_VERSION": "2.1.200"}):
            return build_workflow_scripts(target, {"workflows": {"enabled": True}},
                                          dry_run=False, force=False)

    def test_build_fails_on_a_hand_filled_block_and_is_idempotent(self):
        # covers: BO-4300c-3
        # angle: seam
        """Fills an empty marker pair from the source, refuses a pair already holding
        text, a second run writes nothing, and the shared source is not deployed."""
        templates, target = self._tree(f"{START}\n{END}\nreturn 1;\n")
        self._build(templates, target)
        deployed = target / "workflows" / "demo.js"
        self.assertTrue(deployed.is_file())
        inner = _between(deployed.read_text(encoding="utf-8"))
        self.assertIsNotNone(inner)
        self.assertEqual(_norm(inner), _norm(self.BLOCK))
        self.assertFalse((target / "workflows" / "workspace-answer.js").exists())
        digest = hashlib.sha256(deployed.read_bytes()).hexdigest()
        mtime = deployed.stat().st_mtime_ns
        self.assertEqual(self._build(templates, target), 0, "second run wrote files")
        self.assertEqual(hashlib.sha256(deployed.read_bytes()).hexdigest(), digest)
        self.assertEqual(deployed.stat().st_mtime_ns, mtime)

        hand, target2 = self._tree(f"{START}\n// hand copy\n{END}\nreturn 1;\n")
        with self.assertRaises(Exception):  # noqa: B017 -- any refusal that fails the build
            self._build(hand, target2)
        self.assertFalse((target2 / "workflows" / "demo.js").exists(),
                         "a hand-filled template was deployed")

        missing, target3 = self._tree(f"{START}\n{END}\nreturn 1;\n")
        (missing / SOURCE_REL).unlink()
        with self.assertRaises(Exception):  # noqa: B017
            self._build(missing, target3)
        self.assertFalse((target3 / "workflows" / "demo.js").exists())


if __name__ == "__main__":
    unittest.main()
