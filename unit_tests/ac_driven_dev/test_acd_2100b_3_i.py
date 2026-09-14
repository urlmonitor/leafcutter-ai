"""
MODULE: test_acd_2100b_3_i
GOAL: Behavioral tests for ACD-2100b-3-i -- "A registry that holds no agent
    entries is reported as unusable rather than as a missing agent" --
    SCRIPT-LEVEL (classification) half.

    This file covers the test_spec entries whose behaviour is actually
    DECIDED by scripts/worktree/check_workspace_setup_permission.py's
    `_resolve_agent_outcome()` -- specifically its FOURTH, representable
    state (`no_entries_collection`, when `registry_json["agents"]` is not a
    list at all). The companion WORKFLOW-level tests live in
    unit_tests/workflows/test_acd_2100b_3_i.py.

SURFACE CHANGE: ACD-2100b-3-i's own test_spec (docs/acceptance-criteria/
    ac-driven-dev/ACD-2100-entry-point-unblocked/ACD-2100b-3-i.yaml) still
    names `unit_tests/workflows/` as the target_dir for all four of its
    entries -- stale for the same reason as ACD-2100b-1's (see that AC's
    unit_tests/ac_driven_dev/test_acd_2100b_1.py module docstring): the
    lookup itself now happens entirely inside
    check_workspace_setup_permission.py's `_resolve_agent_outcome()`, whose
    docstring already names this exact fourth state explicitly:

        "no_entries_collection" registry_json["agents"] is not a list at
                                 all (missing key, wrong type) -- a distinct
                                 fact from "agent_not_found", never folded
                                 into it (ACD-2100b-3-i).

CONTRACT THIS FILE PINS: a registry that parses cleanly as JSON but holds a
    non-list value where the `agents` collection belongs classifies as
    `outcome: "no_entries_collection"` -- a THIRD, genuinely distinct enum
    value from both `agent_not_found` (a real, empty-or-non-matching list)
    and `permission_denied` (a real list containing the agent, denied).

FIXTURE AUTHENTICITY (docs/reference/fixture-policy.md): the registry is
    produced by `json.dumps(..., indent=2)` -- the SAME serializer that would
    write a real agent_registry.json -- never a hand-typed literal.

A GAP THAT WAS CLOSED -- ASSERTION KEPT AS THE REGRESSION GUARD:
    AC-1 requires the report to name WHAT was found where the agent entries
    collection was expected (the malformed value or its type), "so an
    operator can tell a wrong file from a structurally changed one". This
    was a real, unresolved gap when this file was first authored:
    `_resolve_agent_outcome()` computed the `no_entries_collection` outcome
    purely from `isinstance(agents, list)` and never returned the malformed
    value (or its type) to its caller -- `build_verdict()`'s returned dict
    for this outcome carried only `permits`, `outcome`, `agent_id`, and
    `location`.

    This gap was closed by ACD-2100b-5's port: the verdict now carries
    `agents_type`/`agents_value` fields, so both this script's stdout and
    plan-feature.js's rendered report (see
    unit_tests/workflows/test_acd_2100b_3_i.py) can state what was actually
    found in the malformed `agents` field's place.
    `test_no_entries_collection_verdict_states_what_was_found` below asserts
    exactly what AC-1 requires and now PASSES against the current
    check_workspace_setup_permission.py. The assertion is left in its full,
    unweakened form -- unchanged from when it was authored to expose the gap
    -- so it stands as the guard against this gap reappearing.

TICKET: 10_TICKET-20260826-ACD-2100b-3-i.md
AC: ACD-2100b-3-i
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PREFLIGHT_SCRIPT = (
    _WORKTREE_ROOT / "scripts" / "worktree" / "check_workspace_setup_permission.py"
)

_TIMEOUT = 20

_PROBE_AGENT_ID = "zqm7_probe_worktree_agent_44xk"

# A distinctive numeric value standing where the `agents` LIST belongs.
_MALFORMED_AGENTS_VALUE = 42891
_NO_ENTRIES_COLLECTION_REGISTRY_JSON = json.dumps(
    {"agents": _MALFORMED_AGENTS_VALUE}, indent=2
)
_ABSENT_AGENT_REGISTRY_JSON = json.dumps(
    {"agents": [{"id": "unrelated-other-agent-8h2z", "permits_shell": True}]},
    indent=2,
)
_DENIED_AGENT_REGISTRY_JSON = json.dumps(
    {"agents": [{"id": _PROBE_AGENT_ID, "permits_shell": False}]},
    indent=2,
)


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, check=True, capture_output=True, text=True
    )


def _make_repo_fixture(tmp_path: Path, *, registry_content: str) -> Path:
    repo_dir = tmp_path / "project"
    repo_dir.mkdir(parents=True)
    _run(["git", "init", "-b", "main", str(repo_dir)])
    _run(["git", "-C", str(repo_dir), "config", "user.email", "test@example.com"])
    _run(["git", "-C", str(repo_dir), "config", "user.name", "Test"])
    (repo_dir / "README.md").write_text("seed\n", encoding="utf-8")
    _run(["git", "-C", str(repo_dir), "add", "README.md"])
    _run(["git", "-C", str(repo_dir), "commit", "-m", "seed"])

    registry_path = repo_dir / ".leafcutter" / "config" / "agent_registry.json"
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(registry_content, encoding="utf-8")
    return repo_dir


def _run_preflight(cwd: Path, agent_id: str = _PROBE_AGENT_ID) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_PREFLIGHT_SCRIPT), "--agent-id", agent_id],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
    )


def _parse_stdout_json(proc: subprocess.CompletedProcess) -> dict:
    if not proc.stdout.strip():
        raise AssertionError(
            f"Pre-flight script produced no stdout. returncode={proc.returncode} "
            f"stderr={proc.stderr[:2000]!r}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"Pre-flight script produced non-JSON stdout: {exc}\n"
            f"stdout={proc.stdout[:2000]!r}\nstderr={proc.stderr[:2000]!r}"
        ) from exc


class TestNoEntriesCollectionClassification(unittest.TestCase):

    def test_no_entries_collection_outcome_is_its_own_value(self):
        # covers: ACD-2100b-3-i
        # angle: criterion
        """AC-1: a registry that parses cleanly as JSON but holds a
        non-list value where `agents` belongs classifies as
        `outcome: "no_entries_collection"`.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b3i_script_") as tmp:
            repo_dir = _make_repo_fixture(
                Path(tmp), registry_content=_NO_ENTRIES_COLLECTION_REGISTRY_JSON
            )
            verdict = _parse_stdout_json(_run_preflight(repo_dir))

            self.assertIs(verdict.get("permits"), False, f"verdict={verdict!r}")
            self.assertEqual(
                verdict.get("outcome"), "no_entries_collection",
                f"Expected outcome='no_entries_collection'. verdict={verdict!r}",
            )

    def test_no_entries_collection_is_distinct_from_agent_not_found_and_permission_denied(self):
        # covers: ACD-2100b-3-i
        # angle: boundary
        """AC-2/AC-3: the no-entries-collection outcome is NEVER worded (or,
        here, classified) as either the absence outcome or the denial
        outcome -- proved as three genuinely different enum values from
        three fixtures that share the same probe agent id, differing only in
        the shape of the registry's `agents` field.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b3i_script_malformed_") as tmp_malformed:
            repo_malformed = _make_repo_fixture(
                Path(tmp_malformed), registry_content=_NO_ENTRIES_COLLECTION_REGISTRY_JSON
            )
            verdict_malformed = _parse_stdout_json(_run_preflight(repo_malformed))

        with tempfile.TemporaryDirectory(prefix="acd2100b3i_script_absent_") as tmp_absent:
            repo_absent = _make_repo_fixture(Path(tmp_absent), registry_content=_ABSENT_AGENT_REGISTRY_JSON)
            verdict_absent = _parse_stdout_json(_run_preflight(repo_absent))

        with tempfile.TemporaryDirectory(prefix="acd2100b3i_script_denied_") as tmp_denied:
            repo_denied = _make_repo_fixture(Path(tmp_denied), registry_content=_DENIED_AGENT_REGISTRY_JSON)
            verdict_denied = _parse_stdout_json(_run_preflight(repo_denied))

        outcomes = {
            verdict_malformed.get("outcome"),
            verdict_absent.get("outcome"),
            verdict_denied.get("outcome"),
        }
        self.assertEqual(
            outcomes,
            {"no_entries_collection", "agent_not_found", "permission_denied"},
            "The three Given conditions must classify to three genuinely "
            f"different outcome values, got: "
            f"malformed={verdict_malformed.get('outcome')!r} "
            f"absent={verdict_absent.get('outcome')!r} "
            f"denied={verdict_denied.get('outcome')!r}",
        )

    def test_no_entries_collection_verdict_states_what_was_found(self):
        # covers: ACD-2100b-3-i
        # angle: real_artifact
        """AC-1 (see module docstring): the verdict names what was actually
        found where the agent entries collection was expected -- the
        malformed value or its type -- so an operator can tell a wrong file
        from a structurally changed one. This is the guarantee this test
        protects.

        This was a real gap when first authored -- `_resolve_agent_outcome()`
        discarded the malformed value entirely once it determined
        `isinstance(agents, list)` was False, so nothing in
        `build_verdict()`'s returned dict carried the value 42891 or the
        word "number". It was closed by ACD-2100b-5's port, which attached
        `agents_type`/`agents_value` fields to the verdict; the assertion
        remains here, unweakened, as the guard against it returning.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b3i_script_found_") as tmp:
            repo_dir = _make_repo_fixture(
                Path(tmp), registry_content=_NO_ENTRIES_COLLECTION_REGISTRY_JSON
            )
            verdict = _parse_stdout_json(_run_preflight(repo_dir))
            verdict_text = json.dumps(verdict)

            found_markers = (str(_MALFORMED_AGENTS_VALUE), "number")
            self.assertTrue(
                any(marker in verdict_text for marker in found_markers),
                "The verdict does not name what was found where the agent "
                f"entries collection was expected (expected {_MALFORMED_AGENTS_VALUE!r} "
                f"or 'number' to appear). verdict={verdict!r}",
            )


if __name__ == "__main__":
    unittest.main()
