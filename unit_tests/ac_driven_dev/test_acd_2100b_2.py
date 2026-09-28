"""
MODULE: test_acd_2100b_2
GOAL: Behavioral tests for ACD-2100b-2 -- "A registry whose contents cannot be
    understood is reported as unusable and not as a permission verdict" --
    SCRIPT-LEVEL (classification) half.

    This file covers the test_spec entries whose behaviour is actually
    DECIDED by scripts/worktree/check_workspace_setup_permission.py's
    `build_verdict()` (via `_load_registry()`'s `json.loads()` call) -- the
    classification of "uninterpretable" itself. The companion WORKFLOW-level
    tests (driving templates/workflows-js/plan-feature.js through the E2
    harness with a supplied verdict) live in
    unit_tests/workflows/test_acd_2100b_2.py.

SURFACE CHANGE: ACD-2100b-2's own test_spec (docs/acceptance-criteria/
    ac-driven-dev/ACD-2100-entry-point-unblocked/ACD-2100b-2.yaml) still names
    `unit_tests/workflows/` as the target_dir for all four of its entries --
    that pointer is stale for the same reason as ACD-2100b-1's (see that AC's
    unit_tests/ac_driven_dev/test_acd_2100b_1.py module docstring): the
    interpretation decision now happens entirely inside
    check_workspace_setup_permission.py's `_load_registry()`, not inside the
    sandboxed workflow body.

CONTRACT THIS FILE PINS: for a registry file that IS readable but whose
    contents raise `json.JSONDecodeError`, `build_verdict()` returns
    `outcome: "parse_failure"`, `permits: False`, and names the location that
    was read -- distinct from `outcome: "read_failure"` (ACD-2100b-1, the
    file could not be opened at all) and from `outcome: "granted"` (a valid,
    permitting registry).

FIXTURE AUTHENTICITY (docs/reference/fixture-policy.md): the malformed
    registry content is produced by `json.dumps(..., indent=2)` -- the SAME
    serializer that would write a real agent_registry.json -- then sliced
    with plain Python string slicing to simulate a partial write / interrupted
    build-time copy. Never a hand-typed broken literal.

A GAP THAT WAS CLOSED -- ASSERTION KEPT AS THE REGRESSION GUARD:
    ACD-2100b-2's AC-4 requires the report to name a POSITION within the
    contents that corresponds to where the real serializer's output was
    actually cut. This was a real, unresolved gap when this file was first
    authored: `build_verdict()`'s `parse_failure` verdict carried only
    `permits`, `outcome`, `agent_id`, and `location` -- no offset, line
    number, or trailing-fragment field of any kind. `_load_registry()` did
    capture the real `json.JSONDecodeError` (which carries
    `.pos`/`.lineno`/`.colno`) but only passed it to `logger.warning()`,
    never attaching it to the returned verdict.

    This gap was closed by ACD-2100b-5's port: the verdict now carries
    `position`/`line`/`column` fields sourced from the real
    `json.JSONDecodeError`, so both this script's stdout and
    plan-feature.js's rendered report (see
    unit_tests/workflows/test_acd_2100b_2.py) can state where interpretation
    failed.
    `test_parse_failure_verdict_states_where_interpretation_failed` below
    asserts exactly what AC-4 requires and now PASSES against the current
    check_workspace_setup_permission.py. The assertion is left in its full,
    unweakened form -- unchanged from when it was authored to expose the gap
    -- so it stands as the guard against this gap reappearing.

TICKET: 08_TICKET-20260826-ACD-2100b-2.md
AC: ACD-2100b-2
"""

from __future__ import annotations

import json
import re
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
_DEFAULT_AGENT_ID = "worktree-agent"

# The REAL serializer's output for a two-agent registry -- built with the
# same json.dumps() a real agent_registry.json write would use, never a
# hand-typed literal. Two distinct, deliberately mid-token truncation offsets
# are cut from this SAME content so the position-tracking test can prove (or,
# per the documented gap above, fail to prove) the reported position tracks
# the real cut point rather than a hardcoded canned value.
_FULL_REGISTRY_JSON = json.dumps(
    {
        "agents": [
            {"id": _DEFAULT_AGENT_ID, "permits_shell": True},
            {"id": "xk7q_distinctive_probe_marker_93fz", "permits_shell": False},
        ]
    },
    indent=2,
)
_CUT_A = 118
_CUT_B = 132


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=str(cwd) if cwd else None, check=True, capture_output=True, text=True
    )


def _make_repo_fixture(tmp_path: Path, *, registry_content: str | None) -> Path:
    """Build the Given: a REAL git repository whose agent registry either does
    not exist (`registry_content is None`) or holds `registry_content`
    verbatim (a truncated, real-serializer-produced JSON string).
    """
    repo_dir = tmp_path / "project"
    repo_dir.mkdir(parents=True)
    _run(["git", "init", "-b", "main", str(repo_dir)])
    _run(["git", "-C", str(repo_dir), "config", "user.email", "test@example.com"])
    _run(["git", "-C", str(repo_dir), "config", "user.name", "Test"])
    (repo_dir / "README.md").write_text("seed\n", encoding="utf-8")
    _run(["git", "-C", str(repo_dir), "add", "README.md"])
    _run(["git", "-C", str(repo_dir), "commit", "-m", "seed"])

    if registry_content is not None:
        registry_path = repo_dir / ".leafcutter" / "config" / "agent_registry.json"
        registry_path.parent.mkdir(parents=True)
        registry_path.write_text(registry_content, encoding="utf-8")

    return repo_dir


def _run_preflight(cwd: Path, agent_id: str = _DEFAULT_AGENT_ID) -> subprocess.CompletedProcess:
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


_OFFSET_PATTERN = re.compile(
    r"(?:position|offset|character|char|index|byte|col(?:umn)?)\D{0,15}(\d{1,6})",
    re.IGNORECASE,
)
_LINE_PATTERN = re.compile(r"line\D{0,10}(\d{1,4})", re.IGNORECASE)


def _position_stated_correctly(text: str, content: str, cut: int) -> bool:
    truncated = content[:cut]
    expected_line = truncated.count("\n") + 1

    for match in _OFFSET_PATTERN.finditer(text):
        if abs(int(match.group(1)) - cut) <= 5:
            return True
    for match in _LINE_PATTERN.finditer(text):
        if int(match.group(1)) == expected_line:
            return True
    for frag_len in (10, 15, 20):
        if len(truncated) >= frag_len:
            fragment = truncated[-frag_len:].strip()
            if fragment and fragment in text:
                return True
    return False


class TestUninterpretableRegistryClassification(unittest.TestCase):

    def test_truncated_registry_outcome_is_parse_failure(self):
        # covers: ACD-2100b-2
        # angle: criterion
        """AC-1: a registry produced by truncating the real serializer's
        output part-way through is read successfully (the file exists and is
        readable) but its contents cannot be interpreted. The pre-flight, run
        as a real subprocess, classifies this as `outcome: "parse_failure"`.
        """
        for cut in (_CUT_A, _CUT_B):
            with self.subTest(cut=cut):
                with tempfile.TemporaryDirectory(prefix="acd2100b2_script_trunc_") as tmp:
                    repo_dir = _make_repo_fixture(
                        Path(tmp), registry_content=_FULL_REGISTRY_JSON[:cut]
                    )
                    proc = _run_preflight(repo_dir)

                    self.assertEqual(
                        proc.returncode, 0,
                        f"Pre-flight exited non-zero. stdout={proc.stdout!r} stderr={proc.stderr!r}",
                    )
                    verdict = _parse_stdout_json(proc)

                    self.assertIs(
                        verdict.get("permits"), False,
                        f"Expected permits=False for a truncated registry. verdict={verdict!r}",
                    )
                    self.assertEqual(
                        verdict.get("outcome"), "parse_failure",
                        f"Expected outcome='parse_failure' for a truncated registry. verdict={verdict!r}",
                    )
                    self.assertEqual(
                        verdict.get("location"),
                        str(repo_dir / ".leafcutter" / "config" / "agent_registry.json"),
                        f"The verdict does not name the location that was read. verdict={verdict!r}",
                    )

    def test_absent_and_truncated_registries_produce_different_outcomes(self):
        # covers: ACD-2100b-2
        # angle: criterion
        """AC-2/AC-3: an absent registry (ACD-2100b-1's outcome) and a
        truncated-but-present registry (this AC's outcome) are classified
        with genuinely DIFFERENT `outcome` enum values -- not merely
        different message text -- so the two causes cannot silently collapse
        into each other.
        """
        with tempfile.TemporaryDirectory(prefix="acd2100b2_script_absent_") as tmp_absent:
            repo_absent = _make_repo_fixture(Path(tmp_absent), registry_content=None)
            verdict_absent = _parse_stdout_json(_run_preflight(repo_absent))

        with tempfile.TemporaryDirectory(prefix="acd2100b2_script_trunc2_") as tmp_trunc:
            repo_trunc = _make_repo_fixture(
                Path(tmp_trunc), registry_content=_FULL_REGISTRY_JSON[:_CUT_A]
            )
            verdict_trunc = _parse_stdout_json(_run_preflight(repo_trunc))

        self.assertEqual(verdict_absent.get("outcome"), "read_failure")
        self.assertEqual(verdict_trunc.get("outcome"), "parse_failure")
        self.assertNotEqual(
            verdict_absent.get("outcome"), verdict_trunc.get("outcome"),
            "An absent registry and a truncated-but-present registry must "
            f"classify to different outcomes. verdict_absent={verdict_absent!r} "
            f"verdict_trunc={verdict_trunc!r}",
        )

    def test_parse_failure_verdict_states_where_interpretation_failed(self):
        # covers: ACD-2100b-2
        # angle: real_artifact
        """AC-4 (see module docstring): the verdict names a position within
        the contents that corresponds to where the REAL serializer's output
        was cut -- proved by truncating the same real JSON at two different,
        independently-computed offsets and requiring each run's reported
        position to track its own cut point. This is the guarantee this test
        protects.

        This was a real gap when first authored -- `_load_registry()` caught
        `json.JSONDecodeError` (which carries `.pos`/`.lineno`/`.colno`) but
        only logged it via `logger.warning()`, attaching none of that detail
        to the returned verdict. It was closed by ACD-2100b-5's port, which
        attached `position`/`line`/`column` fields to the verdict; the
        assertion remains here, unweakened, as the guard against it
        returning.
        """
        for cut in (_CUT_A, _CUT_B):
            with self.subTest(cut=cut):
                with tempfile.TemporaryDirectory(prefix="acd2100b2_script_pos_") as tmp:
                    repo_dir = _make_repo_fixture(
                        Path(tmp), registry_content=_FULL_REGISTRY_JSON[:cut]
                    )
                    verdict = _parse_stdout_json(_run_preflight(repo_dir))
                    verdict_text = json.dumps(verdict)

                    self.assertTrue(
                        _position_stated_correctly(verdict_text, _FULL_REGISTRY_JSON, cut),
                        "The verdict does not name a position (offset, line, "
                        "or trailing fragment) corresponding to where the "
                        f"real serializer's output was actually cut (cut={cut}). "
                        f"verdict={verdict!r}",
                    )


if __name__ == "__main__":
    unittest.main()
