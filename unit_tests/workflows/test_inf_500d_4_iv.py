"""
MODULE: test_inf_500d_4_iv (workflow side)
GOAL: RED test for AC INF-500d-4-iv's plan-feature.js half -- the product-truth
    telemetry line the /plan-feature workflow dispatches is appended to the
    DECLARED operational telemetry stream, obtained through INF-500d-4-iii's
    location query in the dispatched instruction, never to a path the workflow
    composes from the (disposable) authoring worktree.
AC: INF-500d-4-iv (source_ac); depends on INF-500d-4-iii (--print-location).

WHY THIS DRIVES BEHAVIOUR, NOT A GREP: the real plan-feature.js top-level body
    runs in the E2 stub harness (``run_workflow_under_e2``: the actual JS in a
    sandboxed Node vm). The store-absent branch of the product-truth phase calls
    the REAL ``emitPtTelemetry`` with the REAL ``authoringWorktreePath`` the
    configured ``worktree-setup`` reply names, and the test inspects the prompt
    the workflow's own control flow assembled for the ``pt-telemetry`` dispatch.

CONTRACT THIS FILE FIXES: the dispatched instruction (a) still carries the
    event line, (b) obtains the append path by running the deployed
    ``sink_resolution.py --print-location telemetry``, and (c) contains no
    ``debugging/logs`` path composed by the workflow. The dispatch stays
    best-effort (one ``pt-telemetry`` call; the workflow does not halt).
"""
# @ac-tag: INF-500d-4-iv

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))
if str(_UNIT_TESTS_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR.parent))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402
from unit_tests.feedback import _inf_500d_4_helpers as h  # noqa: E402
from unit_tests.feedback import _inf_500d_4_vi_helpers as vh  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"
_TIMEOUT = 30
_FAKE_AUTHORING_WORKTREE = "/tmp/inf-500d-4-iv-fake-authoring-worktree"


def _label_responses() -> dict:
    """Reach the store-absent self-skip: a real authoring worktree, a PT outcome, and an ABSENT store."""
    return {
        "stage-0-triage": {
            "route": "strategic",
            "existing_acs": [],
            "parent_l1_id": None,
            "rationale": "test fixture -- route straight past the covered-route gate",
        },
        "worktree-setup": {
            "output": json.dumps(
                {
                    "worktree_path": _FAKE_AUTHORING_WORKTREE,
                    "ac_store_path": _FAKE_AUTHORING_WORKTREE + "/docs/acceptance-criteria",
                }
            ),
            "exit_code": 0,
        },
        "pt-classify": {
            "outcome": "mock-data-only",
            "component": "test-comp",
            "dispatch": ["mock-data-author"],
        },
        "pt-store-check": {"output": "absent", "exit_code": 0},
        "pt-telemetry": {"exit_code": 0},
    }


def test_plan_feature_pt_telemetry_targets_the_declared_stream():
    # covers: INF-500d-4-iv
    # angle: seam
    """The pt-telemetry dispatch asks the location query for the stream; it composes no worktree-prefixed log path."""
    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=_label_responses(),
        args={"run_id": "test-inf-500d-4-iv"},
    )
    assert result.error == "", f"Harness error: {result.error}"

    labels = [call.label for call in result.agent_calls]
    calls = [call for call in result.agent_calls if call.label == "pt-telemetry"]
    assert len(calls) == 1, f"the store-absent skip must dispatch exactly one pt-telemetry line; labels: {labels}"
    prompt = calls[0].prompt
    assert isinstance(prompt, str)

    # The logged line must still carry this event as its "event" field (key and value together, not the bare name).
    assert re.search(r'event\W+pt_phase_skipped_store_absent', prompt), f"the event line is no longer carried:\n{prompt}"
    assert "debugging/logs" not in prompt, (
        "the instruction still names a path the workflow composed itself (the worktree-prefixed "
        f"debugging/logs/agent_telemetry.jsonl append path):\n{prompt}"
    )
    assert _FAKE_AUTHORING_WORKTREE + "/debugging" not in prompt
    assert re.search(r"sink_resolution\.py\s+--print-location\s+telemetry", prompt), (
        f"the instruction must obtain the stream through the location query:\n{prompt}"
    )


def _composed_command() -> str:
    """The shell command the workflow's own control flow composed for the ``pt-telemetry`` dispatch (its ``Run:`` line)."""
    result = run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=_label_responses(),
        args={"run_id": "test-inf-500d-4-iv"},
    )
    assert result.error == "", f"Harness error: {result.error}"
    calls = [call for call in result.agent_calls if call.label == "pt-telemetry"]
    assert len(calls) == 1, [call.label for call in result.agent_calls]
    match = re.search(r"^Run: (.+)$", calls[0].prompt, re.MULTILINE)
    assert match, f"the dispatched instruction carries no 'Run:' command:\n{calls[0].prompt}"
    return match.group(1)


def _git_project(base: Path, name: str, *, declared: bool) -> tuple[Path, Path, Path]:
    """A real git repository carrying a deployed install; returns ``(project, nested cwd, declared stream)``.

    The composed command ends in ``>> "$STREAM"`` with NO mkdir, so a declared project gets its log directory
    here -- the shape of an install whose first write has already happened.
    """
    project = base / name
    project.mkdir()
    subprocess.run(["git", "init", "-q", str(project)], check=True, capture_output=True)
    out_root = h.deploy_install(project, git=False)
    stream = project / "debugging" / "logs" / "agent_telemetry.jsonl"
    if declared:
        h.declare(out_root)  # ordinary build: <project>/debugging/logs
        stream.parent.mkdir(parents=True)
    cwd = project / "work"
    cwd.mkdir()
    return project, cwd, stream


def test_the_composed_pt_telemetry_command_appends_to_the_declared_stream(tmp_path):
    # covers: INF-500d-4-iv
    # angle: reachability
    """The ``Run:`` command plan-feature composes for pt-telemetry, executed verbatim with ``bash -c`` from a nested
    directory of a declared project, appends exactly one well-formed event to the DECLARED stream; against an
    undeclared install it exits non-zero and writes nothing (so the append is the declaration's doing).

    The prompt-text test above only reads the dispatched words. This one runs what they say.
    """
    command = _composed_command()
    tmpdir = tmp_path / "tmpdir"
    tmpdir.mkdir()

    project, cwd, stream = _git_project(tmp_path, "declared", declared=True)
    before = h.snapshot(project)
    proc = vh._shell(command, cwd, tmpdir)

    assert proc.returncode == 0, f"the composed command failed in a declared install: {proc.stderr!r}\n{command}"
    records = h.read_records(stream)
    assert len(records) == 1, f"exactly one event must be appended to the declared stream {stream}: {records}"
    assert records[0]["source"] == "plan-feature" and records[0]["event"] == "pt_phase_skipped_store_absent", records[0]
    assert records[0]["detail"]["run_id"] == "test-inf-500d-4-iv", records[0]
    assert h.snapshot(project) - before == {str(stream)}, (
        "the append may create the declared stream and nothing else: " f"{sorted(h.snapshot(project) - before)}")
    assert not (cwd / "debugging").exists(), "a workspace-relative log was created beside the caller"

    bare_project, bare_cwd, _bare_stream = _git_project(tmp_path, "undeclared", declared=False)
    bare_before = h.snapshot(bare_project)
    refused = vh._shell(command, bare_cwd, tmpdir)
    assert refused.returncode != 0, f"with no declaration the command must refuse, not guess a path: {refused.stdout!r}"
    assert h.snapshot(bare_project) == bare_before, "an undeclared install must get no log written anywhere"
