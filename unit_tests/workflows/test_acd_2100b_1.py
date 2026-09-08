"""
MODULE: test_acd_2100b_1
GOAL: Behavioral tests for ACD-2100b-1 -- "A registry the startup check cannot
    read is reported as unreadable and names what it tried to read" --
    WORKFLOW-LEVEL (reporting) half.

    This file covers the halt-and-render behaviour of templates/workflows-js/
    plan-feature.js's Pre-Stage-0 Workspace-Setup Dispatch Permission Gate.
    The companion SCRIPT-level tests (the classification decision itself,
    including the confirmed AC-2 gap) live in
    unit_tests/ac_driven_dev/test_acd_2100b_1.py -- read that file's module
    docstring before this one.

SURFACE CHANGE: ACD-2100b-5 moved the registry read out of this workflow's
    sandboxed body (no filesystem primitive under the E2 engine, ADR-030) and
    into scripts/worktree/check_workspace_setup_permission.py, invoked by the
    plan-feature skill BEFORE the workflow runs. The workflow now reads
    `args.workspace_setup_permission` -- a pre-computed verdict -- and, when
    `.permits !== true`, renders one of a small, fixed set of canned messages
    keyed SOLELY by `.outcome` (see plan-feature.js's `outcomeMessages` map,
    ~line 2253). It makes NO agent() dispatch on the check's own behalf at
    all (confirmed: no call carries the old
    "resolve-workspace-setup-permission" label under this design). This
    file's tests therefore supply the verdict directly via `args` and observe
    the workflow's own halt and rendered report -- never a live registry read
    inside the workflow, which no longer happens.

WHY THE TESTS BELOW NO LONGER ASSERT A `resolve-workspace-setup-permission`
    DISPATCH: the PRIOR version of this file drove a real, on-disk registry
    through a self-contained Node-subprocess harness and asserted that label's
    presence as proof "the check executed at all". That dispatch has been
    REMOVED BY DESIGN (ACD-2100b-5, work_status: done) -- asserting its
    presence today would be asserting a fact this workflow no longer makes
    true, on a design its own sibling AC deliberately retired. Reachability
    is proven here instead by observing that the workflow's OWN CONSUMED,
    RETURNED result reflects the halt and that no step AFTER the check
    (`resolve-worktree-setup-script-path` / `worktree-setup`) is ever
    dispatched -- the correct evidence for "the args-supplied verdict was
    consumed in control flow" under the new design.

A GAP CARRIED FORWARD FROM THE CLASSIFICATION SURFACE -- NOW CLOSED, ASSERTION
    KEPT AS THE REGRESSION GUARD: when this file was first authored,
    check_workspace_setup_permission.py's `build_verdict()` mapped BOTH "no
    file" and "permission refused" to the identical `outcome: "read_failure"`
    (see unit_tests/ac_driven_dev/test_acd_2100b_1.py's module docstring),
    and this workflow rendered its message SOLELY from `.outcome`, so the two
    Given conditions this AC names produced a byte-IDENTICAL rendered report
    here too. That gap was closed by ACD-2100b-5's port: the verdict now
    carries a distinguishing `reason`/`detail`, and plan-feature.js's
    `outcomeMessages` now interpolates it, so the two Given conditions render
    genuinely different reports.
    `test_permission_refused_and_absent_verdicts_render_different_reports`
    below asserts what AC-2 requires (the two reports differ) and now PASSES
    against the current plan-feature.js -- the assertion is unchanged from
    when it was authored to expose the gap, and remains as the honest,
    direct-to-the-operator guard against this collapse reappearing.

TICKET: 07_TICKET-20260826-ACD-2100b-1.md
AC: ACD-2100b-1
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"
_PREFLIGHT_SCRIPT = (
    _WORKTREE_ROOT / "scripts" / "worktree" / "check_workspace_setup_permission.py"
)

_TIMEOUT = 20
_SETUP_RELATED_LABELS = ("resolve-worktree-setup-script-path", "worktree-setup")

# Vocabulary this report must never contain -- a statement about agent
# permission, or a pointer at a permission setting (AC-3/AC-4).
_FORBIDDEN_PERMISSION_VERDICT_MARKERS = ("permit", "permits_shell")

_UNREADABLE_PHRASES = ("could not be read", "could not read", "cannot be read", "unreadable")


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, check=True, capture_output=True, text=True
    )


def _make_repo_fixture(tmp_path: Path, *, registry_present: bool) -> Path:
    repo_dir = tmp_path / "project"
    repo_dir.mkdir(parents=True)
    _run(["git", "init", "-b", "main", str(repo_dir)])
    _run(["git", "-C", str(repo_dir), "config", "user.email", "test@example.com"])
    _run(["git", "-C", str(repo_dir), "config", "user.name", "Test"])
    (repo_dir / "README.md").write_text("seed\n", encoding="utf-8")
    _run(["git", "-C", str(repo_dir), "add", "README.md"])
    _run(["git", "-C", str(repo_dir), "commit", "-m", "seed"])
    if registry_present:
        registry_path = repo_dir / ".leafcutter" / "config" / "agent_registry.json"
        registry_path.parent.mkdir(parents=True)
        registry_path.write_text(json.dumps({"agents": []}), encoding="utf-8")
    return repo_dir


def _real_preflight_verdict(repo_dir: Path, agent_id: str = "worktree-agent") -> dict:
    """Run the REAL pre-flight script (not a hand-typed stand-in for its
    output shape) against `repo_dir` and return its parsed verdict -- the
    seam this file feeds into the REAL workflow consumer via `args`.
    """
    proc = subprocess.run(
        [sys.executable, str(_PREFLIGHT_SCRIPT), "--agent-id", agent_id],
        cwd=str(repo_dir),
        capture_output=True,
        text=True,
        timeout=_TIMEOUT,
    )
    if not proc.stdout.strip():
        raise AssertionError(
            f"Pre-flight script produced no stdout. returncode={proc.returncode} "
            f"stderr={proc.stderr[:2000]!r}"
        )
    return json.loads(proc.stdout)


def _setup_calls(result) -> list:
    return [c for c in result.agent_calls if c.label in _SETUP_RELATED_LABELS]


def _report_text(result) -> str:
    parts = []
    if isinstance(result.result, dict):
        parts.append(json.dumps(result.result))
    parts.append(result.error or "")
    parts.append(result.stderr or "")
    return "\n".join(parts)


class TestUnreadableRegistryReport(unittest.TestCase):

    def test_absent_registry_is_reported_as_unreadable(self):
        # covers: ACD-2100b-1
        # angle: criterion
        """AC-1/AC-2 (report half): a real `read_failure` verdict -- sourced
        by actually running the real pre-flight script against a repository
        with no registry file at all (the seam: real producer -> real
        consumer) -- makes the workflow halt and state the registry could not
        be read. The specific location-naming half of AC-1 is proven on the
        classification surface (unit_tests/ac_driven_dev/test_acd_2100b_1.py),
        where the location is actually computed.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b1_wf_absent_") as tmp:
            repo_dir = _make_repo_fixture(Path(tmp), registry_present=False)
            verdict = _real_preflight_verdict(repo_dir)

        self.assertEqual(
            verdict.get("outcome"), "read_failure",
            f"Test construction error: expected outcome='read_failure'. verdict={verdict!r}",
        )

        result = run_workflow_under_e2(
            _PLAN_FEATURE_JS,
            timeout=_TIMEOUT,
            args={"workspace_setup_permission": verdict},
        )
        self.assertEqual(result.error, "", f"Harness error: {result.error}")

        self.assertFalse(
            _setup_calls(result),
            f"A step after the permission check ran, but the run must halt "
            f"at the check. calls={[c.label for c in result.agent_calls]}",
        )
        self.assertIsInstance(
            result.result, dict,
            f"Expected a structured, CONSUMED halt result. result={result.result!r}",
        )
        self.assertNotEqual(
            result.result.get("status"), "ok",
            f"The run did not stop for an unreadable registry. result={result.result!r}",
        )

        report = _report_text(result).lower()
        self.assertTrue(
            any(phrase in report for phrase in _UNREADABLE_PHRASES),
            f"The report does not state the registry could not be read. report={report!r}",
        )

    def test_unreadable_registry_report_contains_no_permission_verdict(self):
        # covers: ACD-2100b-1
        # angle: criterion
        """AC-3/AC-4: the read_failure report contains no statement about any
        agent being permitted or not permitted to run repository commands,
        and does not name a permission setting.
        """
        verdict = {
            "permits": False,
            "outcome": "read_failure",
            "agent_id": "worktree-agent",
            "location": "/example/repo/.leafcutter/config/agent_registry.json",
        }
        result = run_workflow_under_e2(
            _PLAN_FEATURE_JS,
            timeout=_TIMEOUT,
            args={"workspace_setup_permission": verdict},
        )
        self.assertEqual(result.error, "", f"Harness error: {result.error}")

        report = _report_text(result).lower()
        for marker in _FORBIDDEN_PERMISSION_VERDICT_MARKERS:
            self.assertNotIn(
                marker, report,
                f"The report on an unreadable registry contains a "
                f"permission-verdict marker ({marker!r}). report={report!r}",
            )

    def test_permission_refused_and_absent_verdicts_render_different_reports(self):
        # covers: ACD-2100b-1
        # angle: boundary
        """AC-2 (see module docstring): the criteria require the report to
        distinguish "no file" from "permission refused". Feeding two real
        `read_failure` verdicts -- one sourced from an absent-registry
        repository, one from a permission-refused registry -- through the
        REAL workflow renders reports that differ, which is the guarantee
        this test protects.

        This was a real gap when first authored -- `outcomeMessages.read_failure`
        was a single static string that did not reference the verdict's
        `location` (or any other field), so any two `read_failure` verdicts
        rendered byte-identical reports regardless of why the read failed.
        This was the same gap unit_tests/ac_driven_dev/test_acd_2100b_1.py
        documented at the classification layer. It was closed by
        ACD-2100b-5's port, which threaded the verdict's distinguishing
        reason into `outcomeMessages`; the assertion remains here, unweakened,
        as the guard against it returning.
        """
        import os
        import stat as _stat

        def _is_root() -> bool:
            try:
                return os.geteuid() == 0
            except AttributeError:
                return False

        if _is_root():
            self.skipTest(
                "Running as root -- file permission bits do not deny reads."
            )

        with tempfile.TemporaryDirectory(prefix="acd2100b1_wf_absent_cmp_") as tmp_absent:
            repo_absent = _make_repo_fixture(Path(tmp_absent), registry_present=False)
            verdict_absent = _real_preflight_verdict(repo_absent)

        with tempfile.TemporaryDirectory(prefix="acd2100b1_wf_denied_cmp_") as tmp_denied:
            repo_denied = Path(tmp_denied) / "project"
            repo_denied.mkdir(parents=True)
            _run(["git", "init", "-b", "main", str(repo_denied)])
            _run(["git", "-C", str(repo_denied), "config", "user.email", "test@example.com"])
            _run(["git", "-C", str(repo_denied), "config", "user.name", "Test"])
            (repo_denied / "README.md").write_text("seed\n", encoding="utf-8")
            _run(["git", "-C", str(repo_denied), "add", "README.md"])
            _run(["git", "-C", str(repo_denied), "commit", "-m", "seed"])
            registry_path = repo_denied / ".leafcutter" / "config" / "agent_registry.json"
            registry_path.parent.mkdir(parents=True)
            registry_path.write_text(json.dumps({"agents": []}), encoding="utf-8")
            registry_path.chmod(0o000)
            try:
                verdict_denied = _real_preflight_verdict(repo_denied)
            finally:
                registry_path.chmod(_stat.S_IRUSR | _stat.S_IWUSR)

        self.assertEqual(verdict_absent.get("outcome"), "read_failure")
        self.assertEqual(verdict_denied.get("outcome"), "read_failure")

        result_absent = run_workflow_under_e2(
            _PLAN_FEATURE_JS, timeout=_TIMEOUT,
            args={"workspace_setup_permission": verdict_absent},
        )
        result_denied = run_workflow_under_e2(
            _PLAN_FEATURE_JS, timeout=_TIMEOUT,
            args={"workspace_setup_permission": verdict_denied},
        )
        self.assertEqual(result_absent.error, "")
        self.assertEqual(result_denied.error, "")

        self.assertNotEqual(
            json.dumps(result_absent.result, sort_keys=True),
            json.dumps(result_denied.result, sort_keys=True),
            "AC-2 requires the absent-registry report and the "
            "permission-refused report to differ, but plan-feature.js's "
            "outcomeMessages.read_failure renders the identical static "
            "string for both, regardless of the verdict's other fields. "
            f"result_absent={result_absent.result!r} "
            f"result_denied={result_denied.result!r}",
        )

    def test_unreadable_registry_halts_the_run_at_the_check(self):
        # covers: ACD-2100b-1
        # angle: reachability
        """Driving the REAL workflow entry point (via run_workflow_under_e2,
        never by importing a helper function) with a read_failure verdict
        supplied through args stops the run before the step after the check
        -- and the halt is what the caller observes in the workflow's own
        CONSUMED, returned result, not merely a value computed and discarded.
        """
        verdict = {
            "permits": False,
            "outcome": "read_failure",
            "agent_id": "worktree-agent",
            "location": "/example/repo/.leafcutter/config/agent_registry.json",
        }
        result = run_workflow_under_e2(
            _PLAN_FEATURE_JS,
            timeout=_TIMEOUT,
            args={"workspace_setup_permission": verdict},
        )
        self.assertEqual(result.error, "", f"Harness error: {result.error}")

        self.assertFalse(
            _setup_calls(result),
            "A step after the unreadable-registry check ran, but the run "
            f"must stop at the check. calls={[c.label for c in result.agent_calls]}",
        )

        self.assertIsInstance(
            result.result, dict,
            f"The caller observes no structured halt result at all "
            f"(result={result.result!r}) -- the halt must be CONSUMED in "
            "control flow (returned), not merely computed and discarded.",
        )
        self.assertNotEqual(
            result.result.get("status"), "ok",
            f"The run's own observable result does not reflect a halt. result={result.result!r}",
        )
        result_text = json.dumps(result.result).lower()
        self.assertTrue(
            any(phrase in result_text for phrase in _UNREADABLE_PHRASES),
            f"The halted run's own observable result does not state the "
            f"registry could not be read. result={result.result!r}",
        )
        for marker in _FORBIDDEN_PERMISSION_VERDICT_MARKERS:
            self.assertNotIn(
                marker, result_text,
                f"The halted run's own observable result contains a "
                f"permission-verdict marker ({marker!r}). result={result.result!r}",
            )


if __name__ == "__main__":
    unittest.main()
