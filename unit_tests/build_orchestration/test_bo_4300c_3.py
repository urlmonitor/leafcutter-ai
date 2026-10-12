"""
MODULE: unit_tests/build_orchestration/test_bo_4300c_3.py
AC: BO-4300c-3 -- "Every caller stops on anything but a ready answer"
    (ticket 10). Tests: five hostile answers x every workspace-consuming
    deployed workflow; the build-inlined WORKSPACE-ANSWER block's parity,
    coverage and build behaviour.

The consuming set is DERIVED (see _bo_4300c_3_fixtures.consuming_workflows),
with REQUIRED_CONSUMERS (the six workflows the AC names) as a floor so an
empty set cannot pass vacuously. Replies are scripted exactly as the engine
would deliver them; assertions read the RECORDED dispatch list and terminal
payload of the DEPLOYED workflows, never source text (except block parity).

RED BASELINE (2026-10-12): all red -- no workflow carries the block or
dispatches the workspace step; templates/workflows-js/_shared/ is absent.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from unit_tests.build_orchestration._bo_4300c_3_fixtures import (
    END_MARKER,
    FIVE_HOSTILE,
    REQUIRED_CONSUMERS,
    SENTINEL_MAIN_COPY,
    SHARED_SOURCE,
    START_MARKER,
    WORKSPACE_LABEL,
    consuming_workflows,
    deployed_workflow_names,
    deployed_workflows_dir,
    extract_between_markers,
    hostile_reply,
    reads_args_workspace,
    run_scenario,
    shared_source_block,
    terminal,
    terminal_text,
    workspace_calls,
)


def _consumers() -> tuple[str, ...]:
    found = consuming_workflows()
    assert set(REQUIRED_CONSUMERS) <= set(found), f"consuming workflows {found}; required {REQUIRED_CONSUMERS}"
    return found


def workflows_missing_block(directory: Path, consumers: set[str] | None = None) -> list[str]:
    """Workflows in `directory` that read args.workspace (or are in
    `consumers`) but carry no marker pair."""
    out = []
    for p in sorted(directory.glob("*.js")):
        src = p.read_text(encoding="utf-8")
        wants = reads_args_workspace(src) or bool(consumers and p.name in consumers)
        if wants and extract_between_markers(src) is None:
            out.append(p.name)
    return out


class TestBO4300c3EveryCallerStops(unittest.TestCase):
    def test_each_workflow_ends_in_failure_on_each_non_ready_answer(self):
        # covers: BO-4300c-3
        # angle: failure
        """6 workflows x 5 hostile answers: every run ends with status error."""
        failures = []
        for name in _consumers():
            for kind in FIVE_HOSTILE:
                result = run_scenario(name, hostile_reply(kind))
                if terminal(result).get("status") != "error":
                    failures.append(f"{name}/{kind}: {terminal_text(result)[:160]}")
        self.assertEqual(failures, [], msg="\n".join(failures))

    def test_failure_quotes_what_was_received(self):
        # covers: BO-4300c-3
        # angle: criterion
        """Each failure quotes the received answer, bounded to 2 KB."""
        failures = []
        for name in _consumers():
            for kind in FIVE_HOSTILE:
                text = terminal_text(run_scenario(name, hostile_reply(kind)))
                if kind == "none":
                    ok = "no valid answer" in text.lower() or "no answer" in text.lower()
                else:
                    ok = f"TOKEN-{kind}" in text
                if not ok:
                    failures.append(f"{name}/{kind}: {text[:160]}")
            long_text = terminal_text(run_scenario(name, "TOKEN-long " + "x" * 6000))
            if "TOKEN-long" not in long_text or "x" * 2100 in long_text:
                failures.append(f"{name}/long: quote missing or not bounded to 2 KB (len {len(long_text)})")
        self.assertEqual(failures, [], msg="\n".join(failures))

    def test_no_authoring_phase_commit_or_delivery_step_is_dispatched_after_the_workspace_step(self):
        # covers: BO-4300c-3
        # angle: criterion
        """Exactly one workspace dispatch and it is the last recorded one."""
        failures = []
        for name in _consumers():
            for kind in FIVE_HOSTILE:
                result = run_scenario(name, hostile_reply(kind))
                if len(workspace_calls(result)) != 1 or result.agent_calls[-1].label != WORKSPACE_LABEL:
                    failures.append(f"{name}/{kind}: {[c.label for c in result.agent_calls]}")
        self.assertEqual(failures, [], msg="\n".join(failures))

    def test_no_run_continues_in_main_copy_epic_folder_start_folder_or_any_ungiven_location(self):
        # covers: BO-4300c-3
        # angle: boundary
        """Hostile runs dispatch nothing after the workspace step and no
        recorded dispatch names the sentinel main-copy/start location handed
        in via args. Control: with a ready answer the run continues past the
        workspace step and no later dispatch uses the sentinel."""
        extra = {"worktree_path": SENTINEL_MAIN_COPY, "epicPath": SENTINEL_MAIN_COPY, "started_from": SENTINEL_MAIN_COPY}
        failures = []
        for name in _consumers():
            for kind in FIVE_HOSTILE:
                result = run_scenario(name, hostile_reply(kind), args_extra=extra)
                idx = [i for i, c in enumerate(result.agent_calls) if c.label == WORKSPACE_LABEL]
                if len(idx) != 1 or idx[0] != len(result.agent_calls) - 1:
                    failures.append(f"{name}/{kind}: dispatches {[c.label for c in result.agent_calls]}")
                blob = json.dumps([[c.prompt, c.opts] for c in result.agent_calls], default=str)
                if SENTINEL_MAIN_COPY in blob:
                    failures.append(f"{name}/{kind}: a dispatch names the ungiven location")
            ok = run_scenario(name, hostile_reply("ok"), args_extra=extra)
            idx = [i for i, c in enumerate(ok.agent_calls) if c.label == WORKSPACE_LABEL]
            if len(idx) != 1 or idx[0] == len(ok.agent_calls) - 1:
                failures.append(f"{name}/ready: control run did not continue past the workspace step")
            else:
                later = json.dumps([[c.prompt, c.opts] for c in ok.agent_calls[idx[0] + 1:]], default=str)
                if SENTINEL_MAIN_COPY in later:
                    failures.append(f"{name}/ready: a later dispatch uses the ungiven location")
        self.assertEqual(failures, [], msg="\n".join(failures))

    def test_workspace_answer_block_is_byte_identical_in_every_deployed_consumer(self):
        # covers: BO-4300c-3
        # angle: deployed
        """The text between the markers in every DEPLOYED workflow equals the
        single source block; a difference names the workflow."""
        self.assertTrue(SHARED_SOURCE.is_file(), msg=f"missing single source {SHARED_SOURCE}")
        source = shared_source_block()
        self.assertTrue(source.strip(), "the single source block is empty")
        carriers, diffs = [], []
        for name in deployed_workflow_names():
            block = extract_between_markers((deployed_workflows_dir() / name).read_text(encoding="utf-8"))
            if block is None:
                continue
            carriers.append(name)
            if block != source:
                diffs.append(name)
        self.assertEqual(diffs, [], msg=f"block differs from the source in: {diffs}")
        self.assertTrue(set(REQUIRED_CONSUMERS) <= set(carriers), msg=f"carriers: {carriers}")

    def test_every_workspace_consuming_workflow_carries_the_block(self):
        # covers: BO-4300c-3
        # angle: failure
        """A fixture workflow consuming a workspace without the block is named
        by the check; every real deployed consumer carries the block."""
        with tempfile.TemporaryDirectory(prefix="bo4300c3-fixture-wf-") as tmp:
            Path(tmp, "uses-workspace.js").write_text("const w = args.workspace;\nreturn w;\n", encoding="utf-8")
            Path(tmp, "has-block.js").write_text(
                f"{START_MARKER}\nconst x = 1;\n{END_MARKER}\nconst w = args.workspace;\n", encoding="utf-8")
            Path(tmp, "unrelated.js").write_text("return args.workspace_setup_permission;\n", encoding="utf-8")
            self.assertEqual(workflows_missing_block(Path(tmp)), ["uses-workspace.js"])
        missing = workflows_missing_block(deployed_workflows_dir(), set(_consumers()))
        self.assertEqual(missing, [], msg=f"workspace-consuming workflows without the block: {missing}")

    def test_build_fails_on_a_hand_filled_block_and_is_idempotent(self):
        # covers: BO-4300c-3
        # angle: seam
        """Against a temporary templates tree: an empty marker pair is filled
        from the source (before placeholder injection), a second run writes
        nothing, a hand-filled pair or a missing source fails the build."""
        import build_phases

        block = "function workspaceProbe() { return '{{config.output_root}}/x'; }"
        with tempfile.TemporaryDirectory(prefix="bo4300c3-build-") as tmp:
            wf = Path(tmp) / "templates" / "workflows-js"
            (wf / "_shared").mkdir(parents=True)
            (wf / "_shared" / "workspace-answer.js").write_text(block + "\n", encoding="utf-8")
            (wf / "consumer.js").write_text(f"{START_MARKER}\n{END_MARKER}\nreturn 1;\n", encoding="utf-8")
            (wf / "plain.js").write_text("return 2;\n", encoding="utf-8")
            target = Path(tmp) / "target"
            cfg = {"workflows": {"enabled": True}, "output_root": ".custom-root"}
            with mock.patch.object(build_phases, "TEMPLATES_DIR", Path(tmp) / "templates"), \
                    mock.patch.dict(os.environ, {"CLAUDE_CODE_VERSION": "2.1.154"}):
                build_phases.build_workflow_scripts(target, cfg, dry_run=False, force=True)
                out = (target / "workflows" / "consumer.js").read_text(encoding="utf-8")
                self.assertEqual(extract_between_markers(out), block.replace("{{config.output_root}}", ".custom-root"))
                self.assertEqual((target / "workflows" / "plain.js").read_text(encoding="utf-8"), "return 2;\n")
                mtimes = {p.name: p.stat().st_mtime_ns for p in (target / "workflows").glob("*.js")}
                self.assertEqual(build_phases.build_workflow_scripts(target, cfg, dry_run=False, force=True), 0,
                                 "a second build must write nothing")
                self.assertEqual(mtimes, {p.name: p.stat().st_mtime_ns for p in (target / "workflows").glob("*.js")})
                (wf / "consumer.js").write_text(f"{START_MARKER}\nhand copy\n{END_MARKER}\n", encoding="utf-8")
                with self.assertRaises((Exception, SystemExit)) as ctx:
                    build_phases.build_workflow_scripts(Path(tmp) / "t2", cfg, dry_run=False, force=True)
                self.assertIn("consumer.js", str(ctx.exception))
                self.assertFalse((Path(tmp) / "t2" / "workflows" / "consumer.js").exists())
                (wf / "consumer.js").write_text(f"{START_MARKER}\n{END_MARKER}\n", encoding="utf-8")
                (wf / "_shared" / "workspace-answer.js").unlink()
                with self.assertRaises((Exception, SystemExit)):
                    build_phases.build_workflow_scripts(Path(tmp) / "t3", cfg, dry_run=False, force=True)


if __name__ == "__main__":
    unittest.main()
