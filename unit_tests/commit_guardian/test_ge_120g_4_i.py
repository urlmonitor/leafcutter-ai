"""
Tests for templates/scripts/commit_guardian/check_negative_control_liveness.py

GE-120g-4-i: re-observing the SAME verdict on a later day must leave the stored
`currently` record and the manifest file alone; only a CHANGED verdict is
written. "Same verdict" = equal `state`, equal evidence count, and per-position
equal `command` and `exit_code` (output text and `observed` are not compared).
`observed` now means the date the current verdict was first observed.

Every test builds a throwaway directory holding `probe.py`, `outcomes.json` and
a `commit_guardian.json` serialised with indent=4 (NOT the writer's indent=2),
so ANY rewrite of the file changes its bytes. The commands stay textually
constant; only `outcomes.json` varies between runs. The stored `observed` is a
fixed past date (2026-10-11), so no clock mocking is needed; "today" is asserted
against `date.today()`.

The tests invoke the TEMPLATE source copy of the check
(templates/scripts/commit_guardian/check_negative_control_liveness.py) as a
subprocess, the same copy and harness test_ge_120g_4.py uses.
"""
from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

STORED_DATE = "2026-10-11"
HOOK_ID = "probe-hook"
TEXT_BAD = "bad probe: rejected input"
TEXT_ACCEPT = "accept probe: accepted input"

_PROBE_SOURCE = """\
import json
import sys

role = sys.argv[1]
with open("outcomes.json", encoding="utf-8") as handle:
    outcome = json.load(handle)[role]
sys.stdout.write(outcome["text"])
sys.exit(outcome["exit"])
"""


def _script_path() -> Path:
    """Template source copy of the liveness check (match test_ge_120g_4.py)."""
    repo_root = Path(__file__).resolve().parents[2]
    return (
        repo_root / "templates" / "scripts" / "commit_guardian"
        / "check_negative_control_liveness.py"
    )


def _py() -> str:
    return shlex.quote(sys.executable)


def _bad_command() -> str:
    return f"{_py()} probe.py bad"


def _accept_command() -> str:
    return f"{_py()} probe.py accept"


def _outcomes(bad_exit: int, bad_text: str, accept_exit: int, accept_text: str) -> dict:
    return {
        "bad": {"exit": bad_exit, "text": bad_text},
        "accept": {"exit": accept_exit, "text": accept_text},
    }


def _write_fixture(
    root: Path, stored: dict, outcomes: dict, *, with_accept_command: bool = True,
) -> Path:
    """Write probe.py, outcomes.json and the indent=4 manifest into *root*."""
    (root / "probe.py").write_text(_PROBE_SOURCE, encoding="utf-8")
    (root / "outcomes.json").write_text(json.dumps(outcomes), encoding="utf-8")
    hook: dict = {
        "id": HOOK_ID,
        "entry": f"{_py()} probe.py",
        "negative_control": {"command": _bad_command(), "currently": stored},
    }
    if with_accept_command:
        hook["command"] = _accept_command()
    manifest = root / "commit_guardian.json"
    document = {"hooks_manifest": {"hooks": [hook]}}
    manifest.write_text(json.dumps(document, indent=4) + "\n", encoding="utf-8")
    return manifest


def _evidence(bad_exit, bad_text, accept_exit, accept_text) -> list[dict]:
    return [
        {"command": _bad_command(), "output": bad_text, "exit_code": bad_exit},
        {"command": _accept_command(), "output": accept_text, "exit_code": accept_exit},
    ]


def _stored(state: str, evidence: list[dict]) -> dict:
    return {"state": state, "observed": STORED_DATE, "evidence": evidence}


def _run_check(root: Path, manifest: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(_script_path()), "--manifest", str(manifest)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(root),
        check=False,
    )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _currently(manifest: Path) -> dict:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    return data["hooks_manifest"]["hooks"][0]["negative_control"]["currently"]


class TestLivenessSameVerdictIsNotNews(unittest.TestCase):
    """GE-120g-4-i: only a changed verdict is recorded."""

    def test_same_verdict_on_a_later_day_leaves_manifest_bytes_identical(self) -> None:
        # covers: GE-120g-4-i
        # angle: criterion
        """Same exit codes seen again on a later day: file bytes unchanged."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stored = _stored("passing", _evidence(1, TEXT_BAD, 0, TEXT_ACCEPT))
            manifest = _write_fixture(root, stored, _outcomes(1, TEXT_BAD, 0, TEXT_ACCEPT))
            before = _digest(manifest)

            result = _run_check(root, manifest)

            self.assertEqual(
                before,
                _digest(manifest),
                msg=(
                    "manifest bytes changed on a re-observation of the same "
                    f"verdict; stored record now: {_currently(manifest)!r}\n"
                    f"exit={result.returncode} stdout={result.stdout!r} "
                    f"stderr={result.stderr!r}"
                ),
            )

    def test_reworded_output_with_same_exit_codes_keeps_stored_record(self) -> None:
        # covers: GE-120g-4-i
        # angle: criterion
        """Reworded probe text, same exit codes: keep old text and old date."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stored = _stored("passing", _evidence(1, TEXT_BAD, 0, TEXT_ACCEPT))
            reworded = "bad probe: message reworded after a linter upgrade"
            manifest = _write_fixture(root, stored, _outcomes(1, reworded, 0, TEXT_ACCEPT))
            before = _digest(manifest)

            result = _run_check(root, manifest)

            record = _currently(manifest)
            self.assertEqual(before, _digest(manifest), msg=f"bytes changed: {record!r}")
            self.assertEqual(STORED_DATE, record["observed"], msg=f"record: {record!r}")
            self.assertEqual(TEXT_BAD, record["evidence"][0]["output"], msg=f"{record!r}")
            self.assertEqual(0, result.returncode, msg=result.stderr)

    def test_passing_to_failing_is_recorded_with_new_date_and_evidence(self) -> None:
        # covers: GE-120g-4-i
        # angle: criterion
        """Bad probe now exits 0: the changed verdict is written, dated today."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stored = _stored("passing", _evidence(1, TEXT_BAD, 0, TEXT_ACCEPT))
            new_bad_text = "bad probe: accepted the bad input"
            manifest = _write_fixture(root, stored, _outcomes(0, new_bad_text, 0, TEXT_ACCEPT))
            before = _digest(manifest)

            _run_check(root, manifest)

            record = _currently(manifest)
            self.assertEqual("failing", record["state"])
            self.assertEqual(date.today().isoformat(), record["observed"])
            self.assertEqual(_evidence(0, new_bad_text, 0, TEXT_ACCEPT), record["evidence"])
            self.assertNotEqual(before, _digest(manifest), msg="file was not rewritten")

    def test_every_direction_of_state_change_is_recorded(self) -> None:
        # covers: GE-120g-4-i
        # angle: criterion
        """passing<->failing and unverified->passing/failing are all recorded."""
        unverified_entry = [
            {"command": _bad_command(), "output": "not examined this run -- never attempted"},
        ]
        # (label, stored state, stored evidence, bad exit, accept exit, new state)
        rows = [
            ("passing->failing", "passing", _evidence(1, TEXT_BAD, 0, TEXT_ACCEPT), 0, 0, "failing"),
            ("failing->passing", "failing", _evidence(0, TEXT_BAD, 0, TEXT_ACCEPT), 1, 0, "passing"),
            ("unverified->passing", "unverified", unverified_entry, 1, 0, "passing"),
            ("unverified->failing", "unverified", unverified_entry, 0, 0, "failing"),
        ]
        for label, old_state, old_evidence, bad_exit, accept_exit, new_state in rows:
            with self.subTest(row=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                outcomes = _outcomes(bad_exit, TEXT_BAD, accept_exit, TEXT_ACCEPT)
                manifest = _write_fixture(root, _stored(old_state, old_evidence), outcomes)

                _run_check(root, manifest)

                record = _currently(manifest)
                self.assertEqual(new_state, record["state"])
                self.assertEqual(date.today().isoformat(), record["observed"])
                self.assertEqual(
                    _evidence(bad_exit, TEXT_BAD, accept_exit, TEXT_ACCEPT), record["evidence"],
                )

    def test_same_state_different_exit_code_is_recorded(self) -> None:
        # covers: GE-120g-4-i
        # angle: criterion
        """State stays failing but the accept exit code moves 1 -> 2: recorded."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stored = _stored("failing", _evidence(1, TEXT_BAD, 1, TEXT_ACCEPT))
            manifest = _write_fixture(root, stored, _outcomes(1, TEXT_BAD, 2, TEXT_ACCEPT))

            _run_check(root, manifest)

            record = _currently(manifest)
            self.assertEqual("failing", record["state"])
            self.assertEqual(2, record["evidence"][1]["exit_code"], msg=f"record: {record!r}")
            self.assertEqual(date.today().isoformat(), record["observed"])

    def test_blocked_record_reobserved_unchanged_is_kept(self) -> None:
        # covers: GE-120g-4-i
        # angle: criterion
        """Declaration-level blocked (no accept command), re-observed: untouched.

        The stored evidence carries no exit_code and DIFFERENT output text; a
        missing exit_code on both sides is equal, so the stored block is kept.
        """
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stored = _stored(
                "blocked",
                [{"command": _bad_command(), "output": "older blocked wording"}],
            )
            outcomes = _outcomes(1, TEXT_BAD, 0, TEXT_ACCEPT)
            manifest = _write_fixture(root, stored, outcomes, with_accept_command=False)
            before = _digest(manifest)

            result = _run_check(root, manifest)

            self.assertEqual(
                before,
                _digest(manifest),
                msg=(
                    f"blocked record rewritten: {_currently(manifest)!r}\n"
                    f"stdout={result.stdout!r} stderr={result.stderr!r}"
                ),
            )

    def test_printed_lines_and_exit_code_match_the_observed_verdict(self) -> None:
        # covers: GE-120g-4-i
        # angle: criterion
        """Scope fence: printed result line and exit code follow the verdict."""
        command = _bad_command()
        cases = [
            ("same verdict", 1, "passing", "discriminates", 0),
            ("passing->failing", 0, "failing", "n/a", 1),
        ]
        for label, bad_exit, state, discrimination, exit_code in cases:
            with self.subTest(case=label), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                stored = _stored("passing", _evidence(1, TEXT_BAD, 0, TEXT_ACCEPT))
                outcomes = _outcomes(bad_exit, TEXT_BAD, 0, TEXT_ACCEPT)
                manifest = _write_fixture(root, stored, outcomes)

                result = _run_check(root, manifest)

                expected = (
                    f"NEGATIVE_CONTROL_RESULT check_id={HOOK_ID} state={state} "
                    f"entry_point=probe demonstration=entry_point "
                    f"discrimination={discrimination} command={command}"
                )
                self.assertEqual(exit_code, result.returncode, msg=result.stderr)
                self.assertEqual([expected], result.stdout.splitlines())


if __name__ == "__main__":
    unittest.main()
