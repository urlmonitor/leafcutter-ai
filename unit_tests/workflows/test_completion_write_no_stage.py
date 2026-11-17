"""The completion write dispatches set_ticket_status.py with --no-stage.

Drives a ticket to completion through the real driver harness for both twin
drivers and reads the ticket-completion-write dispatch's prompt by label.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "prompt_assembly"))
sys.path.insert(0, str(_HERE.parent))
sys.path.insert(0, str(_HERE))

import _driver_harness  # noqa: E402

H = _driver_harness
TWINS = list(H.TWIN_DRIVERS)

pytestmark = pytest.mark.skipif(not H.node_available(), reason="node is not on PATH")


@pytest.fixture
def worktree():
    path = tempfile.mkdtemp(prefix="completion-no-stage-")
    yield path
    shutil.rmtree(path, ignore_errors=True)


@pytest.mark.parametrize("driver", TWINS)
def test_completion_write_passes_no_stage(driver, worktree):
    # covers: UNKNOWN
    # angle: seam
    # must_catch: only one twin updated, or --no-stage dropped while "no additional flags" stays
    phases = ["python-coder", "pr-reviewer"]
    path = H.write_ticket_record(
        worktree, "01_ticket.md", phases,
        extra_frontmatter={"component": "build-orchestration"},
    )
    scenario = H.single_ticket_scenario(
        worktree, path,
        {"title": "completion", "phases": phases, "has_test_requirements": True},
    )
    obs = H.run_driver(H.TWIN_DRIVERS[driver], scenario)
    assert obs["error"] is None, obs["error"]
    writes = [w for w in (obs.get("writes") or []) if w.get("label") == "ticket-completion-write"]
    assert len(writes) == 1, writes
    prompt = writes[0].get("prompt") or ""
    assert "set_ticket_status.py --ticket" in prompt, prompt
    assert "--status done --no-stage" in prompt, prompt
    assert "no additional flags" in prompt, prompt
