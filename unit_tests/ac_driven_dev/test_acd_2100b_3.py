"""
MODULE: test_acd_2100b_3
GOAL: Behavioral tests for ACD-2100b-3 -- "An agent missing from the registry
    and an agent denied permission produce different reports" -- SCRIPT-LEVEL
    (classification) half.

    This file covers the test_spec entries whose behaviour is actually
    DECIDED by scripts/worktree/check_workspace_setup_permission.py's
    `_resolve_agent_outcome()` -- the three-state lookup (granted / absent /
    denied) this AC's criteria depend on. The companion WORKFLOW-level tests
    (driving templates/workflows-js/plan-feature.js through the E2 harness
    with a supplied verdict) live in unit_tests/workflows/test_acd_2100b_3.py.

SURFACE CHANGE: ACD-2100b-3's own test_spec (docs/acceptance-criteria/
    ac-driven-dev/ACD-2100-entry-point-unblocked/ACD-2100b-3.yaml) still names
    `unit_tests/workflows/` as the target_dir for all four of its entries --
    stale for the same reason as ACD-2100b-1's (see that AC's
    unit_tests/ac_driven_dev/test_acd_2100b_1.py module docstring): the
    lookup itself now happens entirely inside check_workspace_setup_permission.py.

CONTRACT THIS FILE PINS: `_resolve_agent_outcome()` maps a registry that
    lists the agent's entries collection but does not contain the target
    agent id to `outcome: "agent_not_found"`, and a registry that lists the
    target agent id with `permits_shell` not `True` to
    `outcome: "permission_denied"` -- two GENUINELY DIFFERENT enum values,
    not merely different message text, so the distinction this AC's criteria
    require survives even a caller that only inspects `.outcome`.

FIXTURE AUTHENTICITY (docs/reference/fixture-policy.md): both registries are
    produced by `json.dumps(..., indent=2)` -- the SAME serializer that would
    write a real agent_registry.json -- never a hand-typed literal.

NOTE ON AC-4 ("directs the reader at the permission setting to change"): the
    classification surface's verdict never carries free-text remediation
    prose at all (by design -- it is a machine-readable JSON object, not an
    operator message); that half of AC-4 is a REPORTING-surface concern and
    is tested (and found to have its own gap re: the literal `permits_shell`
    field name) in unit_tests/workflows/test_acd_2100b_3.py.

TICKET: 09_TICKET-20260826-ACD-2100b-3.md
AC: ACD-2100b-3
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

# A distinctive, low-collision probe id for the workspace-setup agent this
# check resolves -- proving the outcome is derived from the actual registry
# lookup rather than a hardcoded literal such as the real default
# "worktree-agent".
_PROBE_AGENT_ID = "zqm7_probe_worktree_agent_44xk"

_ABSENT_AGENT_REGISTRY_JSON = json.dumps(
    {"agents": [{"id": "unrelated-other-agent-9f2q", "permits_shell": True}]},
    indent=2,
)
_DENIED_AGENT_REGISTRY_JSON = json.dumps(
    {"agents": [{"id": _PROBE_AGENT_ID, "permits_shell": False}]},
    indent=2,
)
_GRANTED_AGENT_REGISTRY_JSON = json.dumps(
    {"agents": [{"id": _PROBE_AGENT_ID, "permits_shell": True}]},
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


class TestAbsentVsDeniedAgentClassification(unittest.TestCase):

    def test_absent_agent_outcome_is_agent_not_found(self):
        # covers: ACD-2100b-3
        # angle: criterion
        """AC-1: a registry that lists a real entries collection but does not
        contain the probe agent's id classifies as `outcome: "agent_not_found"`.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b3_script_absent_") as tmp:
            repo_dir = _make_repo_fixture(Path(tmp), registry_content=_ABSENT_AGENT_REGISTRY_JSON)
            verdict = _parse_stdout_json(_run_preflight(repo_dir))

            self.assertIs(verdict.get("permits"), False, f"verdict={verdict!r}")
            self.assertEqual(
                verdict.get("outcome"), "agent_not_found",
                f"Expected outcome='agent_not_found'. verdict={verdict!r}",
            )
            self.assertEqual(verdict.get("agent_id"), _PROBE_AGENT_ID)

    def test_denied_agent_outcome_is_permission_denied(self):
        # covers: ACD-2100b-3
        # angle: criterion
        """AC-2: a registry that lists the probe agent's id but withholds
        `permits_shell` classifies as `outcome: "permission_denied"`.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b3_script_denied_") as tmp:
            repo_dir = _make_repo_fixture(Path(tmp), registry_content=_DENIED_AGENT_REGISTRY_JSON)
            verdict = _parse_stdout_json(_run_preflight(repo_dir))

            self.assertIs(verdict.get("permits"), False, f"verdict={verdict!r}")
            self.assertEqual(
                verdict.get("outcome"), "permission_denied",
                f"Expected outcome='permission_denied'. verdict={verdict!r}",
            )
            self.assertEqual(verdict.get("agent_id"), _PROBE_AGENT_ID)

    def test_absent_and_denied_agents_classify_to_different_outcome_values(self):
        # covers: ACD-2100b-3
        # angle: boundary
        """AC-3: the absence outcome and the denial outcome are DIFFERENT
        `outcome` enum values -- the strongest form of "the two reports
        differ", since a caller that switches only on `.outcome` (as
        plan-feature.js now does) cannot accidentally collapse them.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b3_script_absent_cmp_") as tmp_absent:
            repo_absent = _make_repo_fixture(Path(tmp_absent), registry_content=_ABSENT_AGENT_REGISTRY_JSON)
            verdict_absent = _parse_stdout_json(_run_preflight(repo_absent))

        with tempfile.TemporaryDirectory(prefix="acd2100b3_script_denied_cmp_") as tmp_denied:
            repo_denied = _make_repo_fixture(Path(tmp_denied), registry_content=_DENIED_AGENT_REGISTRY_JSON)
            verdict_denied = _parse_stdout_json(_run_preflight(repo_denied))

        self.assertNotEqual(
            verdict_absent.get("outcome"), verdict_denied.get("outcome"),
            "The absent-agent and denied-agent verdicts must classify to "
            f"different outcome values. verdict_absent={verdict_absent!r} "
            f"verdict_denied={verdict_denied!r}",
        )

    def test_granted_registry_outcome_is_granted_not_denied_or_absent(self):
        # covers: ACD-2100b-3
        # angle: criterion
        """Regression guard: the same probe agent id, now genuinely permitted,
        classifies as `outcome: "granted"` -- never `agent_not_found` nor
        `permission_denied` -- so the three-state lookup's positive case
        isn't accidentally folded into either negative one.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b3_script_granted_") as tmp:
            repo_dir = _make_repo_fixture(Path(tmp), registry_content=_GRANTED_AGENT_REGISTRY_JSON)
            verdict = _parse_stdout_json(_run_preflight(repo_dir))

            self.assertIs(verdict.get("permits"), True, f"verdict={verdict!r}")
            self.assertEqual(verdict.get("outcome"), "granted", f"verdict={verdict!r}")


if __name__ == "__main__":
    unittest.main()
