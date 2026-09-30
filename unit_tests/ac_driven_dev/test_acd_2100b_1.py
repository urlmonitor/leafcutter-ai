"""
MODULE: test_acd_2100b_1
GOAL: Behavioral tests for ACD-2100b-1 -- "A registry the startup check cannot
    read is reported as unreadable and names what it tried to read" --
    SCRIPT-LEVEL (classification) half.

    This file covers the test_spec entries whose behaviour is actually DECIDED
    by scripts/worktree/check_workspace_setup_permission.py's `build_verdict()`
    -- the classification of "unreadable" itself. The companion WORKFLOW-level
    tests (driving templates/workflows-js/plan-feature.js through the E2
    harness with a supplied verdict) live in
    unit_tests/workflows/test_acd_2100b_1.py.

SURFACE CHANGE (read before touching this file or its workflow-level sibling):
    ACD-2100b-1's own test_spec (docs/acceptance-criteria/ac-driven-dev/
    ACD-2100-entry-point-unblocked/ACD-2100b-1.yaml) still names
    `unit_tests/workflows/` as the target_dir for all four of its entries --
    that pointer is now STALE. ACD-2100b-5 moved the workspace-setup
    permission check itself out of templates/workflows-js/plan-feature.js's
    sandboxed body (which has no filesystem primitive under the E2 engine,
    ADR-030) and into scripts/worktree/check_workspace_setup_permission.py, a
    real script the plan-feature skill invokes BEFORE the workflow runs. The
    workflow now ONLY consumes a pre-computed verdict passed through
    `args.workspace_setup_permission` and renders one of a small set of canned
    messages keyed by `verdict.outcome` -- it no longer reads
    config/agent_registry.json itself, dispatches no agent to do so, and
    computes no read-vs-parse-vs-lookup distinction of its own. The actual
    "is this registry unreadable" DECISION -- the thing this AC's criteria
    are about -- is now made entirely inside `build_verdict()`. This file
    proves that decision directly, against the real script, in a real
    subprocess.

    Report to it-po: every one of ACD-2100b-1.yaml's four test_spec entries
    should be re-targeted the way ACD-2100b-5.yaml's test_spec already was --
    split across `unit_tests/ac_driven_dev/` (the classification decision)
    and `unit_tests/workflows/` (the halt + rendered report) -- rather than
    left pointing at `unit_tests/workflows/` for all four.

CONTRACT THIS FILE PINS: scripts/worktree/check_workspace_setup_permission.py's
    `build_verdict()`, run as a real subprocess (`python3
    check_workspace_setup_permission.py --agent-id <id>`) against a real,
    on-disk, repository-anchored `.leafcutter/config/agent_registry.json` (or
    its deliberate absence). Output: exactly one JSON object on stdout, exit 0,
    with at least `permits` (bool) and `outcome` (str). For BOTH Given
    conditions this AC's criteria name -- "the location holds no file" and
    "the process is refused permission to open it" -- `outcome` is
    "read_failure" and `location` names the exact path that was tried.

A GAP THAT WAS CLOSED -- ASSERTION KEPT AS THE REGRESSION GUARD:
    ACD-2100b-1's own criteria require the run's report to state "the reason
    the read failed" in a way that DISTINGUISHES "no file at that location"
    from "permission refused" (two different remedies). This was a real,
    unresolved gap when this file was first authored: `build_verdict()`
    mapped BOTH Given conditions to the exact same `outcome` value
    ("read_failure"), with the only differing field being the incidental
    `location` string (which differed only because the two fixtures live in
    different temporary repositories, not because the verdict encoded
    anything about the failure cause). The distinguishing OS-level detail
    (`[Errno 2] No such file or directory` vs. `[Errno 13] Permission
    denied`) was real and WAS produced by `_load_registry()` -- but at the
    time only as a `logger.warning()` argument on the script's own stderr,
    never crossing into `args.workspace_setup_permission`.

    This gap was closed by ACD-2100b-5's port: `build_verdict()` now attaches
    a `reason`/`detail` field to the returned verdict that carries the
    distinguishing cause forward, so an absent registry and a
    permission-denied registry produce verdicts that differ in a field
    other than the incidental `location` string. Both this script's stdout
    and templates/workflows-js/plan-feature.js's rendered report (see
    unit_tests/workflows/test_acd_2100b_1.py) can now state a reason that
    tells the two causes apart.
    `test_absent_and_permission_denied_registries_are_distinguishable_beyond_location`
    below asserts exactly what AC-2 requires (a distinguishing reason) and
    now PASSES against the current check_workspace_setup_permission.py. The
    assertion is left in its full, unweakened form -- unchanged from when it
    was authored to expose the gap -- so it stands as the guard against this
    collapse reappearing.

TICKET: 07_TICKET-20260826-ACD-2100b-1.md
AC: ACD-2100b-1
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PREFLIGHT_SCRIPT = (
    _WORKTREE_ROOT / "scripts" / "worktree" / "check_workspace_setup_permission.py"
)

_TIMEOUT = 20  # seconds; real git I/O only, no network, no dispatch.
_DEFAULT_AGENT_ID = "worktree-agent"


def _is_root() -> bool:
    try:
        return os.geteuid() == 0
    except AttributeError:
        return False


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, check=True, capture_output=True, text=True
    )


def _make_repo_fixture(
    tmp_path: Path,
    *,
    registry_present: bool,
    registry_permission_denied: bool = False,
) -> Path:
    """Build the Given: a REAL git repository ("the project") in which the
    agent registry the pre-flight resolves to either does not exist at all,
    or exists but cannot be opened for reading.

    Layout:
        tmp_path/project/                                    <- real git repo
          .leafcutter/config/agent_registry.json              <- present iff
                                                                   registry_present
    """
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
        registry_path.write_text(
            json.dumps({"agents": [{"id": _DEFAULT_AGENT_ID, "permits_shell": True}]}),
            encoding="utf-8",
        )
        if registry_permission_denied:
            registry_path.chmod(0o000)

    return repo_dir


def _resolved_registry_location(repo_dir: Path) -> str:
    return str(repo_dir / ".leafcutter" / "config" / "agent_registry.json")


def _run_preflight(cwd: Path, agent_id: str = _DEFAULT_AGENT_ID) -> subprocess.CompletedProcess:
    """Invoke the real pre-flight script as a fresh subprocess -- no agent
    dispatch, no network, no mocking -- against `cwd`.
    """
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
            "Pre-flight script produced no stdout at all.\n"
            f"returncode={proc.returncode}\nstderr={proc.stderr[:2000]!r}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f"Pre-flight script produced non-JSON stdout: {exc}\n"
            f"stdout={proc.stdout[:2000]!r}\nstderr={proc.stderr[:2000]!r}"
        ) from exc


class TestUnreadableRegistryClassification(unittest.TestCase):

    def test_absent_registry_outcome_is_read_failure_naming_the_location(self):
        # covers: ACD-2100b-1
        # angle: criterion
        """AC-1/AC-2: no file at the resolved registry location. The
        pre-flight, run as a real subprocess against a real repository,
        classifies this as `outcome: "read_failure"` and names the exact
        location it tried in its returned verdict -- the fact this AC's
        report must ultimately be built from.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b1_script_absent_") as tmp:
            repo_dir = _make_repo_fixture(Path(tmp), registry_present=False)
            proc = _run_preflight(repo_dir)

            self.assertEqual(
                proc.returncode, 0,
                f"Pre-flight exited non-zero for a well-formed invocation. "
                f"stdout={proc.stdout!r} stderr={proc.stderr!r}",
            )
            verdict = _parse_stdout_json(proc)

            self.assertIs(
                verdict.get("permits"), False,
                f"Expected permits=False for an absent registry. verdict={verdict!r}",
            )
            self.assertEqual(
                verdict.get("outcome"), "read_failure",
                f"Expected outcome='read_failure' for an absent registry. verdict={verdict!r}",
            )
            self.assertEqual(
                verdict.get("location"), _resolved_registry_location(repo_dir),
                "The verdict does not name the exact location that was tried. "
                f"verdict={verdict!r}",
            )

    def test_permission_denied_registry_outcome_is_read_failure_naming_the_location(self):
        # covers: ACD-2100b-1
        # angle: criterion
        """AC-1/AC-2: a registry file present on disk but with read
        permission withheld from the process. The pre-flight classifies this
        the same way as an absent file -- `outcome: "read_failure"` -- and
        still names the exact location it tried.
        """
        if _is_root():
            self.skipTest(
                "Running as root -- file permission bits do not deny reads, "
                "so this boundary cannot be constructed."
            )

        with tempfile.TemporaryDirectory(prefix="acd2100b1_script_denied_") as tmp:
            repo_dir = _make_repo_fixture(
                Path(tmp), registry_present=True, registry_permission_denied=True
            )
            try:
                proc = _run_preflight(repo_dir)
            finally:
                registry_path = Path(_resolved_registry_location(repo_dir))
                registry_path.chmod(0o644)

            self.assertEqual(
                proc.returncode, 0,
                f"Pre-flight exited non-zero for a well-formed invocation. "
                f"stdout={proc.stdout!r} stderr={proc.stderr!r}",
            )
            verdict = _parse_stdout_json(proc)

            self.assertIs(
                verdict.get("permits"), False,
                f"Expected permits=False for a permission-refused registry. verdict={verdict!r}",
            )
            self.assertEqual(
                verdict.get("outcome"), "read_failure",
                f"Expected outcome='read_failure' for a permission-refused registry. verdict={verdict!r}",
            )
            self.assertEqual(
                verdict.get("location"), _resolved_registry_location(repo_dir),
                "The verdict does not name the exact location that was tried. "
                f"verdict={verdict!r}",
            )

    def test_absent_and_permission_denied_registries_are_distinguishable_beyond_location(self):
        # covers: ACD-2100b-1
        # angle: boundary
        """AC-2 (see module docstring): the criteria require the reason the
        read failed to distinguish "no file at that location" from
        "permission refused" -- two different remedies. This test builds
        both real, on-disk fixtures and runs the real pre-flight against
        each, then asserts the two verdicts carry SOME field other than the
        incidental `location` string that differs between them -- the
        guarantee this test protects.

        This was a real gap when first authored -- `_load_registry()` mapped
        both `FileNotFoundError` and `PermissionError` to the identical
        `outcome: "read_failure"` with no other distinguishing field, the
        OS-level distinction (`[Errno 2] ...` vs. `[Errno 13] ...`) reaching
        only the script's own stderr via `logger.warning()`, never the
        returned verdict. It was closed by ACD-2100b-5's port, which attached
        a distinguishing reason to the verdict; the assertion remains here,
        unweakened, as the guard against it returning.
        """
        if _is_root():
            self.skipTest(
                "Running as root -- file permission bits do not deny reads, "
                "so this boundary cannot be constructed."
            )

        with tempfile.TemporaryDirectory(prefix="acd2100b1_script_absent_cmp_") as tmp_absent:
            repo_absent = _make_repo_fixture(Path(tmp_absent), registry_present=False)
            verdict_absent = _parse_stdout_json(_run_preflight(repo_absent))

        with tempfile.TemporaryDirectory(prefix="acd2100b1_script_denied_cmp_") as tmp_denied:
            repo_denied = _make_repo_fixture(
                Path(tmp_denied), registry_present=True, registry_permission_denied=True
            )
            try:
                verdict_denied = _parse_stdout_json(_run_preflight(repo_denied))
            finally:
                Path(_resolved_registry_location(repo_denied)).chmod(0o644)

        self.assertEqual(
            verdict_absent.get("outcome"), "read_failure",
            f"Test construction error: absent-registry verdict={verdict_absent!r}",
        )
        self.assertEqual(
            verdict_denied.get("outcome"), "read_failure",
            f"Test construction error: permission-denied verdict={verdict_denied!r}",
        )

        fields_other_than_location = set(verdict_absent) | set(verdict_denied)
        fields_other_than_location.discard("location")
        fields_other_than_location.discard("agent_id")

        differing_fields = {
            field
            for field in fields_other_than_location
            if verdict_absent.get(field) != verdict_denied.get(field)
        }
        self.assertTrue(
            differing_fields,
            "AC-2 requires the pre-flight's verdict to distinguish 'no file "
            "at that location' from 'permission refused' by a reason other "
            "than the incidental location string -- but the two verdicts "
            "differ in NO field besides 'location'. This is a real, "
            "unresolved gap in check_workspace_setup_permission.py's "
            "build_verdict(): both OSError causes collapse into the same "
            f"outcome='read_failure' with no distinguishing reason field. "
            f"verdict_absent={verdict_absent!r} verdict_denied={verdict_denied!r}",
        )


if __name__ == "__main__":
    unittest.main()
