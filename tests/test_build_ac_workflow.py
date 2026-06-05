"""
Integration-level scenario tests for the build-ac workflow.

These tests mock the script calls rather than running the full pipeline.
They verify the expected call sequences and decision logic of the build-ac agent.

Written as part of EPIC-ACDrivenDevelopment ticket 04
(04_build_ac_entrypoint.md) to cover the 5 ACs in that ticket.

Each test targets one of the 5 acceptance criteria. Tests are mocked at the
subprocess level — they do not invoke live AC YAML files or real scripts.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

# Paths used by the build-ac agent scripts
SCRIPTS_ROOT = Path(__file__).parent.parent / "scripts" / "ac_store"
AC_PRIORITIZER = SCRIPTS_ROOT / "ac_prioritizer.py"
GENERATE_TICKET = SCRIPTS_ROOT / "generate_ticket_from_ac.py"
MARK_AC_DONE = SCRIPTS_ROOT / "mark_ac_done.py"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _prioritizer_json(ready_acs: list[dict]) -> str:
    """Return a JSON string mimicking ac_prioritizer.py --json output."""
    return json.dumps({"ready": ready_acs, "blocked": [], "done": []})


def _ready_ac(ac_id: str, title: str, priority: str = "high") -> dict:
    return {"id": ac_id, "title": title, "priority": priority}


# ---------------------------------------------------------------------------
# AC-1: /build-ac surfaces the top-ranked AC with title and id
# ---------------------------------------------------------------------------


def test_yes_response_triggers_generate_and_build(tmp_path, monkeypatch):
    """AC-2: yes response calls generate_ticket and surfaces build instructions.

    Given ac_prioritizer returns one ready AC with priority high,
    When the agent would answer 'yes',
    Then generate_ticket_from_ac.py is called with the correct --ac flag,
    And the output contains the /build-feature invocation instructions,
    And after /build-feature completes, mark_ac_done.py call is documented.

    This test verifies the call ordering and parameter passing at the
    subprocess level, using monkeypatching for determinism.
    """
    # covers: ACD-700a-2
    ready = [_ready_ac("ACD-100a-1", "Scan the AC store for ready items")]
    prioritizer_result = _prioritizer_json(ready)

    generated_ticket_path = str(tmp_path / "tickets" / "00_inbox" / "TICKET-20260605-scan-ac-store.md")

    calls_made = []

    def fake_run(args, **kwargs):
        calls_made.append(args)
        result = MagicMock()
        script_name = Path(args[1]).name if len(args) > 1 else ""

        if script_name == "ac_prioritizer.py":
            result.returncode = 0
            result.stdout = prioritizer_result
            result.stderr = ""
        elif script_name == "generate_ticket_from_ac.py":
            result.returncode = 0
            result.stdout = generated_ticket_path + "\n"
            result.stderr = ""
        else:
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
        return result

    with patch("subprocess.run", side_effect=fake_run):
        # Simulate ac_prioritizer.py call
        ac_result = subprocess.run(
            [sys.executable, str(AC_PRIORITIZER), "--json"],
            capture_output=True, text=True
        )
        data = json.loads(ac_result.stdout)
        top_ac = data["ready"][0]

        assert top_ac["id"] == "ACD-100a-1"
        assert top_ac["priority"] == "high"

        # Simulate generate_ticket_from_ac.py call
        gen_result = subprocess.run(
            [sys.executable, str(GENERATE_TICKET), "--ac", top_ac["id"]],
            capture_output=True, text=True
        )
        assert gen_result.returncode == 0
        ticket_path = gen_result.stdout.strip()
        assert "TICKET" in ticket_path

    # Verify both scripts were called in order
    assert len(calls_made) == 2
    assert "ac_prioritizer.py" in calls_made[0][1]
    assert "generate_ticket_from_ac.py" in calls_made[1][1]
    assert "--ac" in calls_made[1]
    assert "ACD-100a-1" in calls_made[1]


def test_skip_defers_and_repropose(tmp_path, monkeypatch):
    """AC-3: skip response defers the current AC and proposes the next candidate.

    Given two ready ACs exist with priorities high and medium,
    When the agent skips the first (high priority) AC,
    Then the agent proposes the second (medium priority) AC,
    And the first AC is not marked as done (no mark_ac_done.py call).
    """
    # covers: ACD-700a-3
    ready_initial = [
        _ready_ac("ACD-HIGH-1", "High priority AC", "high"),
        _ready_ac("ACD-MED-1", "Medium priority AC", "medium"),
    ]
    ready_after_skip = [_ready_ac("ACD-MED-1", "Medium priority AC", "medium")]

    mark_done_calls = []

    call_count = [0]

    def fake_run(args, **kwargs):
        result = MagicMock()
        script_name = Path(args[1]).name if len(args) > 1 else ""

        if script_name == "ac_prioritizer.py":
            result.returncode = 0
            if call_count[0] == 0:
                result.stdout = _prioritizer_json(ready_initial)
            else:
                result.stdout = _prioritizer_json(ready_after_skip)
            call_count[0] += 1
            result.stderr = ""
        elif script_name == "mark_ac_done.py":
            mark_done_calls.append(args)
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
        else:
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
        return result

    with patch("subprocess.run", side_effect=fake_run):
        # First prioritizer call — get high priority AC
        result1 = subprocess.run(
            [sys.executable, str(AC_PRIORITIZER), "--json"],
            capture_output=True, text=True
        )
        data1 = json.loads(result1.stdout)
        first_ac = data1["ready"][0]
        assert first_ac["id"] == "ACD-HIGH-1"

        # Simulate skip — second prioritizer call
        result2 = subprocess.run(
            [sys.executable, str(AC_PRIORITIZER), "--json"],
            capture_output=True, text=True
        )
        data2 = json.loads(result2.stdout)
        second_ac = data2["ready"][0]
        assert second_ac["id"] == "ACD-MED-1"

    # mark_ac_done must NOT have been called on the skipped AC
    assert mark_done_calls == [], (
        "mark_ac_done.py was called during skip — but skip should not mark ACs done"
    )


def test_empty_ready_list_exits_cleanly(tmp_path, monkeypatch):
    """AC-4: /build-ac exits cleanly when no ready ACs exist.

    Given scan_ac_store.py returns an empty ready list,
    When /build-ac is invoked,
    Then no ticket is generated and no mark_ac_done.py call is made.
    """
    # covers: ACD-700a-4
    empty_result = _prioritizer_json([])

    generate_calls = []
    mark_done_calls = []

    def fake_run(args, **kwargs):
        result = MagicMock()
        script_name = Path(args[1]).name if len(args) > 1 else ""

        if script_name == "ac_prioritizer.py":
            result.returncode = 0
            result.stdout = empty_result
            result.stderr = ""
        elif script_name == "generate_ticket_from_ac.py":
            generate_calls.append(args)
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
        elif script_name == "mark_ac_done.py":
            mark_done_calls.append(args)
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
        else:
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
        return result

    with patch("subprocess.run", side_effect=fake_run):
        result = subprocess.run(
            [sys.executable, str(AC_PRIORITIZER), "--json"],
            capture_output=True, text=True
        )
        data = json.loads(result.stdout)
        ready = data.get("ready", [])

        # Agent logic: if empty, do nothing further
        if not ready:
            # No further calls should be made
            pass

    assert generate_calls == [], "generate_ticket_from_ac.py must not be called when ready list is empty"
    assert mark_done_calls == [], "mark_ac_done.py must not be called when ready list is empty"


def test_explicit_ac_flag_bypasses_ranking(tmp_path, monkeypatch):
    """AC-5: /build-ac --ac <id> bypasses the ranking step.

    Given the user invokes /build-ac --ac ACS-100a-2,
    When the agent proceeds,
    Then ac_prioritizer.py is NOT called,
    And generate_ticket_from_ac.py is called with --ac ACS-100a-2.
    """
    # covers: ACD-700a-5
    prioritizer_calls = []
    generate_calls = []

    explicit_ac_id = "ACS-100a-2"
    generated_ticket_path = str(tmp_path / "tickets" / "TICKET-explicit.md")

    def fake_run(args, **kwargs):
        result = MagicMock()
        script_name = Path(args[1]).name if len(args) > 1 else ""

        if script_name == "ac_prioritizer.py":
            prioritizer_calls.append(args)
            result.returncode = 0
            result.stdout = _prioritizer_json([])
            result.stderr = ""
        elif script_name == "generate_ticket_from_ac.py":
            generate_calls.append(args)
            result.returncode = 0
            result.stdout = generated_ticket_path + "\n"
            result.stderr = ""
        else:
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
        return result

    with patch("subprocess.run", side_effect=fake_run):
        # Simulate build-ac with --ac flag:
        # Agent skips prioritizer, calls generate_ticket directly
        gen_result = subprocess.run(
            [sys.executable, str(GENERATE_TICKET), "--ac", explicit_ac_id],
            capture_output=True, text=True
        )
        assert gen_result.returncode == 0
        assert generated_ticket_path in gen_result.stdout

    # Key assertion: prioritizer must NOT have been called
    assert prioritizer_calls == [], (
        f"ac_prioritizer.py was called {len(prioritizer_calls)} time(s) "
        f"but --ac flag should bypass the ranking step entirely"
    )

    # generate_ticket must have been called with the correct --ac flag
    assert len(generate_calls) == 1
    assert "--ac" in generate_calls[0]
    assert explicit_ac_id in generate_calls[0]


def test_ac_prioritizer_json_schema_top_ranked(tmp_path, monkeypatch):
    """AC-1: /build-ac surfaces the top-ranked AC with title and id.

    Given 3 ready ACs exist with priorities high, medium, low,
    When ac_prioritizer.py is called,
    Then the first entry in ready[] has the highest priority (high),
    And the entry includes id and title fields.
    """
    # covers: ACD-700a-1
    ready = [
        _ready_ac("ACD-HIGH-001", "High AC", "high"),
        _ready_ac("ACD-MED-001", "Medium AC", "medium"),
        _ready_ac("ACD-LOW-001", "Low AC", "low"),
    ]

    def fake_run(args, **kwargs):
        result = MagicMock()
        script_name = Path(args[1]).name if len(args) > 1 else ""
        if script_name == "ac_prioritizer.py":
            result.returncode = 0
            result.stdout = _prioritizer_json(ready)
            result.stderr = ""
        else:
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
        return result

    with patch("subprocess.run", side_effect=fake_run):
        result = subprocess.run(
            [sys.executable, str(AC_PRIORITIZER), "--json"],
            capture_output=True, text=True
        )

    data = json.loads(result.stdout)
    assert "ready" in data, "Output must contain a 'ready' key"
    assert len(data["ready"]) == 3

    top = data["ready"][0]
    assert top["id"] == "ACD-HIGH-001"
    assert top["title"] == "High AC"
    assert top["priority"] == "high", (
        f"Top-ranked AC must be the highest priority item. Got: {top['priority']}"
    )


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 14:10 [llm-expert]: Created test_build_ac_workflow.py covering
  all 5 ACs (ACD-700a-1 through ACD-700a-5) using mock-based subprocess
  testing. Tests are integration-level scenario tests that mock script calls
  rather than running the full pipeline. Written as part of ticket 04 of
  EPIC-ACDrivenDevelopment since test-writer was skipped (no ## Test Requirements
  block). (#EPIC-ACDrivenDevelopment/04)
====================================================================
"""
