"""
MODULE: unit_tests/build_orchestration/test_tq500f3ii_gate_record_reuse.py
GOAL: RED tests for TQ-500f-3-ii's F2 (record and reuse) and F3 option A
    (``green_at_baseline`` halt classification) on the REAL heavy_lane_gate CLI.

AC: docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500f-3-ii.yaml

PINNED CONTRACT (extends test_tq500f3ii_heavy_lane_gate_subcommand.py; ticket 03):

    python fast_lane.py heavy_lane_gate --source-ac <ids> --test-root <dir> \\
        --ac-root <dir> --ticket <path>

* On ``gate_passed`` the wrapper (never the reader, never the test-writer)
  writes ONE column-0 frontmatter line into the ticket,
  ``red_baseline_gate: {"passed": true, "recorded_at", "head", "source_ac",
  "red": [{"file", "function"}]}`` and reports ``recorded: true``.
* A later run reuses the record WITHOUT running pytest (``reused: true``, an
  outcome naming ``recorded_at`` and ``head``) only when the record exists, its
  source_ac equals the ids now carried, and every recorded red (file, function)
  is still among the newly-added covers-tagged tests (subset check).
* Otherwise the reader runs and its verdict decides.
* A missing ticket never blocks: the pass stands with ``recorded: false`` and a
  non-empty ``record_error``. A relative ``--ticket`` resolves against
  ``--test-root``.
* ``all_new_tests_green_at_baseline`` additionally carries the wrapper keys
  ``halt_classification: "green_at_baseline"`` and ``remedy``.

PROOF THAT NO PYTEST RAN: every covered test appends its own name to a log file
outside the repo when it executes. A run that "reused" a record must leave no
log -- that is a fact about the filesystem, not about a mock.

REAL ARTIFACTS: the ticket is written with yaml.safe_dump; the guards run over
the written file are the real ticket_frontmatter_guard.validate and the real
check_doc_frontmatter.py script (from a temp repo whose path starts with
tickets/, as that checker only treats such paths as tickets).

TODAY (unmodified code): ``--ticket`` is not a recognised argument, so the CLI
exits 2 with no JSON on stdout; every test below fails by assertion.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

import unit_tests.build_orchestration._tq500f3i_fixtures as fx  # noqa: E402

AC_ID = "TQ-FIX-3II-REC"
TEST_A = "test_rec_value_is_two"
TEST_B = "test_rec_name_is_final"
TESTS_REL = "tests/test_rec_tests.py"
TICKET_REL = "tickets/01_todo/10_ticket.md"
_RECORD_PREFIX = "red_baseline_gate:"
_TEXT_ENC = "utf-8"


@dataclass
class Fixture:
    tmp: Path
    work: Path
    ac_root: Path
    ticket: Path
    log: Path
    head: str


def _tests_source(fixture_log: Path, work: Path, rename_a: str | None = None) -> str:
    """Source of the covered tests: each logs its own run, then asserts on prodmod."""
    name_a = rename_a or TEST_A
    return f"""\
    import sys

    sys.path.insert(0, {work.as_posix()!r})
    import prodmod


    def _log(name):
        with open({fixture_log.as_posix()!r}, "a", encoding="utf-8") as handle:
            handle.write(name + "\\n")


    def {name_a}():
        # covers: {AC_ID}
        _log("{name_a}")
        assert prodmod.value() == 2, "expected value() == 2"


    def {TEST_B}():
        # covers: {AC_ID}
        _log("{TEST_B}")
        assert prodmod.name() == "final", "expected name() == 'final'"
    """


def _write_ticket(path: Path, *, claim: bool = False, status_key: bool = True) -> None:
    """Write a ticket whose frontmatter comes from the real serializer (yaml.safe_dump)."""
    front = {
        "title": "gate record fixture ticket",
        "status": "todo",
        "components": ["build_orchestration"],
        "created": "2026-10-06",
        "depends_on": [],
        "source_ac": AC_ID,
        "agents": {"test-writer": "signed_off", "python-coder": "needed"},
        "files_touched": ["prodmod.py"],
        "requires_diagram": False,
        "requires_adr": False,
        "change_target": ["code"],
        "risk_surface": ["internal"],
    }
    if not status_key:
        del front["status"]
    body = "\n# Fixture ticket\n\n## Comments\n"
    if claim:
        body += (
            "\n### 2026-10-06 10:00 — test-writer (status: ok)\n"
            "red_baseline_verified: true\n"
        )
    text = "---\n" + yaml.safe_dump(front, sort_keys=False) + "---\n" + body
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode(_TEXT_ENC))


def _build(tmp: Path, *, claim: bool = False) -> Fixture:
    base = {
        "prodmod.py": "def value():\n    return 1\n\n\ndef name():\n    return 'draft'\n",
    }
    work, base_sha = fx.make_worktree(tmp, base)
    ac_root = work / "docs" / "acceptance-criteria"
    fx.write_ac_yaml(
        ac_root, AC_ID, [{"name": TEST_A}, {"name": TEST_B}]
    )
    log = tmp / "ran.log"
    fx.write(work / TESTS_REL, _tests_source(log, work))
    _write_ticket(work / TICKET_REL, claim=claim)
    components = {"components": {"build_orchestration": {"name": "BO", "description": "fixture"}}}
    (work / "docs" / "components.json").write_text(json.dumps(components), encoding=_TEXT_ENC)
    return Fixture(tmp, work, ac_root, work / TICKET_REL, log, base_sha)


def _code(fixture: Fixture) -> None:
    """Stand in for the coder's uncommitted work: production now satisfies the tests."""
    fx.write(
        fixture.work / "prodmod.py",
        "def value():\n    return 2\n\n\ndef name():\n    return 'final'\n",
    )
    # Same byte size as the draft and possibly the same whole second: a stale
    # .pyc from an earlier gate pass would pass Python's size+mtime freshness
    # check and keep the covered tests red. Drop every cached bytecode dir.
    for cache in fixture.work.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)


def _run_gate(
    fixture: Fixture,
    *,
    source_ac: str = AC_ID,
    ticket: str | Path | None = "default",
    cwd: Path | None = None,
) -> tuple[subprocess.CompletedProcess, dict]:
    argv = [
        sys.executable, str(fx.GATE_SCRIPT), "heavy_lane_gate",
        "--source-ac", source_ac,
        "--test-root", str(fixture.work),
        "--ac-root", str(fixture.ac_root),
    ]
    if ticket is not None:
        argv += ["--ticket", str(fixture.ticket if ticket == "default" else ticket)]
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.run(
        argv, capture_output=True, text=True, timeout=180, cwd=cwd, env=env
    )
    try:
        return proc, json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise AssertionError(
            "heavy_lane_gate --ticket must print one JSON object on stdout; "
            f"exit={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr[-400:]!r}"
        ) from None


def _record_lines(path: Path) -> list[str]:
    text = path.read_bytes().decode(_TEXT_ENC)
    return [ln for ln in text.splitlines() if ln.startswith(_RECORD_PREFIX)]


def _first_pass_recorded(fixture: Fixture) -> dict:
    """Run the gate before any coding; require the pass and the recorded line."""
    proc, verdict = _run_gate(fixture)
    assert verdict.get("gate_passed") is True and proc.returncode == 0, f"verdict={verdict!r}"
    lines = _record_lines(fixture.ticket)
    assert len(lines) == 1, f"a pass must record exactly one {_RECORD_PREFIX} line; lines={lines!r}"
    assert fixture.log.exists(), "the first (reader) run must have executed the covered tests"
    return verdict


def _load_guard():
    path = fx.REPO_ROOT / "templates" / "hooks" / "ticket_frontmatter_guard.py"
    spec = importlib.util.spec_from_file_location("tq500f3ii_ticket_guard", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _doc_check(fixture: Fixture, rel: str) -> subprocess.CompletedProcess:
    script = fx.REPO_ROOT / "scripts" / "commit_guardian" / "check_doc_frontmatter.py"
    return subprocess.run(
        [sys.executable, str(script), "--file", rel],
        cwd=fixture.work, capture_output=True, text=True, encoding=_TEXT_ENC, timeout=60,
    )


def test_gate_pass_writes_record_accepted_by_real_guards():
    # covers: TQ-500f-3-ii
    # angle: real_artifact
    """A pass writes exactly one red_baseline_gate line (passed, recorded_at, head,
    source_ac, red), touches no other byte, and the REAL guards accept the ticket."""
    with tempfile.TemporaryDirectory() as tmp:
        fixture = _build(Path(tmp))
        before = fixture.ticket.read_bytes()
        verdict = _first_pass_recorded(fixture)

        assert verdict.get("recorded") is True, f"verdict={verdict!r}"
        assert "halt_classification" not in verdict and "remedy" not in verdict, verdict
        after = fixture.ticket.read_bytes()
        record_line = _record_lines(fixture.ticket)[0]
        assert after.replace(record_line.encode(_TEXT_ENC) + b"\n", b"", 1) == before, (
            "the gate may add the red_baseline_gate line and change no other byte"
        )
        record = json.loads(record_line[len(_RECORD_PREFIX):])
        assert record["passed"] is True, record
        datetime.fromisoformat(record["recorded_at"].replace("Z", "+00:00"))
        assert record["head"] == fixture.head, f"head must be the fixture HEAD; {record!r}"
        assert record["source_ac"] == [AC_ID], record
        assert sorted(r["function"] for r in record["red"]) == sorted([TEST_A, TEST_B]), record
        assert all(r["file"] == TESTS_REL for r in record["red"]), record

        text = after.decode(_TEXT_ENC)
        guard = _load_guard()
        fm = guard.parse_frontmatter(text)
        assert fm is not None and fm.get("red_baseline_gate") == record, fm
        assert guard.validate(fm, fixture.ticket) == [], "ticket_frontmatter_guard must accept it"
        checked = _doc_check(fixture, TICKET_REL)
        assert checked.returncode == 0, f"check_doc_frontmatter: {checked.stdout}{checked.stderr}"
        _write_ticket(fixture.work / "tickets/01_todo/11_bad.md", status_key=False)
        control = _doc_check(fixture, "tickets/01_todo/11_bad.md")
        assert control.returncode != 0, "control: the checker must really inspect tickets/ files"


def test_rerun_after_coding_reuses_record_without_pytest():
    # covers: TQ-500f-3-ii
    # angle: criterion
    """After a recorded pass and 'coding', the gate reuses the record: passed, reused,
    an outcome naming recorded_at and head, no covered test executed, ticket untouched."""
    with tempfile.TemporaryDirectory() as tmp:
        fixture = _build(Path(tmp))
        _first_pass_recorded(fixture)
        record = json.loads(_record_lines(fixture.ticket)[0][len(_RECORD_PREFIX):])
        recorded_bytes = fixture.ticket.read_bytes()
        _code(fixture)
        fixture.log.unlink()

        proc, verdict = _run_gate(fixture)

        assert verdict.get("gate_passed") is True and proc.returncode == 0, f"verdict={verdict!r}"
        assert verdict.get("reused") is True, f"verdict={verdict!r}"
        outcome = str(verdict.get("outcome"))
        assert record["recorded_at"] in outcome and record["head"] in outcome, f"outcome={outcome!r}"
        assert not fixture.log.exists(), "reuse must not run pytest: a covered test executed"
        assert fixture.ticket.read_bytes() == recorded_bytes, "a reused pass writes nothing"


def test_renamed_recorded_red_test_runs_reader_and_fails():
    # covers: TQ-500f-3-ii
    # angle: failure
    """A recorded red test renamed after coding: no reuse, the reader runs and decides."""
    with tempfile.TemporaryDirectory() as tmp:
        fixture = _build(Path(tmp))
        _first_pass_recorded(fixture)
        recorded_bytes = fixture.ticket.read_bytes()
        _code(fixture)
        fixture.log.unlink()
        fx.write(fixture.work / TESTS_REL, _tests_source(fixture.log, fixture.work, TEST_A + "_x"))

        proc, verdict = _run_gate(fixture)

        assert verdict.get("gate_passed") is False and proc.returncode != 0, f"verdict={verdict!r}"
        assert verdict.get("reason") == "all_new_tests_green_at_baseline", f"verdict={verdict!r}"
        assert verdict.get("reused") is not True, f"verdict={verdict!r}"
        assert fixture.log.exists(), "the reader must have run the covered tests"
        assert "record" in str(verdict.get("remedy", "")).lower(), (
            "with a record that could not be reused, the remedy must say so: "
            f"{verdict.get('remedy')!r}"
        )
        assert fixture.ticket.read_bytes() == recorded_bytes, "a failed run writes nothing"


def test_different_source_ac_runs_reader():
    # covers: TQ-500f-3-ii
    # angle: boundary
    """A record made for [A] is not reused for --source-ac A,B; the reader decides."""
    other = "TQ-FIX-3II-OTHER"
    with tempfile.TemporaryDirectory() as tmp:
        fixture = _build(Path(tmp))
        fx.write_ac_yaml(fixture.ac_root, other, [{"name": "test_other_unused"}])
        _first_pass_recorded(fixture)
        _code(fixture)
        fixture.log.unlink()

        proc, verdict = _run_gate(fixture, source_ac=f"{AC_ID},{other}")

        assert verdict.get("reused") is not True, f"verdict={verdict!r}"
        assert verdict.get("gate_passed") is False and proc.returncode != 0, f"verdict={verdict!r}"
        assert verdict.get("reason") == "all_new_tests_green_at_baseline", f"verdict={verdict!r}"
        assert fixture.log.exists(), "the reader must have run the covered tests"


def test_tests_added_after_record_do_not_block_reuse():
    # covers: TQ-500f-3-ii
    # angle: boundary
    """The reuse check is a SUBSET check: a later test-writer handoff may add tests."""
    with tempfile.TemporaryDirectory() as tmp:
        fixture = _build(Path(tmp))
        _first_pass_recorded(fixture)
        _code(fixture)
        fixture.log.unlink()
        fx.write(
            fixture.work / "tests" / "test_rec_extra.py",
            f"""\
            def test_rec_added_later():
                # covers: {AC_ID}
                assert True
            """,
        )

        proc, verdict = _run_gate(fixture)

        assert verdict.get("gate_passed") is True and verdict.get("reused") is True, f"verdict={verdict!r}"
        assert not fixture.log.exists(), "reuse must not run pytest"


def test_test_writer_claim_without_record_runs_reader():
    # covers: TQ-500f-3-ii
    # angle: failure
    """A test-writer red_baseline_verified claim is not a record: the reader runs."""
    with tempfile.TemporaryDirectory() as tmp:
        fixture = _build(Path(tmp), claim=True)
        _code(fixture)
        before = fixture.ticket.read_bytes()

        proc, verdict = _run_gate(fixture)

        assert verdict.get("reused") is not True, f"verdict={verdict!r}"
        assert verdict.get("gate_passed") is False and proc.returncode != 0, f"verdict={verdict!r}"
        assert verdict.get("reason") == "all_new_tests_green_at_baseline", f"verdict={verdict!r}"
        assert fixture.log.exists(), "with no record the reader must run the covered tests"
        assert fixture.ticket.read_bytes() == before, "a failed run writes nothing"


def test_missing_ticket_passes_with_recorded_false():
    # covers: TQ-500f-3-ii
    # angle: boundary
    """A pass with --ticket naming a missing file stands, reports why, and writes no file."""
    with tempfile.TemporaryDirectory() as tmp:
        fixture = _build(Path(tmp))
        ghost = fixture.tmp / "ghost" / "nope.md"

        proc, verdict = _run_gate(fixture, ticket=ghost)

        assert verdict.get("gate_passed") is True and proc.returncode == 0, f"verdict={verdict!r}"
        assert verdict.get("recorded") is False, f"verdict={verdict!r}"
        assert str(verdict.get("record_error") or "").strip(), f"verdict={verdict!r}"
        assert not ghost.exists() and not ghost.parent.exists(), "no file may be created"


def test_relative_ticket_resolves_against_test_root():
    # covers: TQ-500f-3-ii
    # angle: boundary
    """build-ticket.js may pass the ticket path as given (relative): resolve it
    against --test-root, whatever the gate's own cwd is."""
    with tempfile.TemporaryDirectory() as tmp:
        fixture = _build(Path(tmp))

        proc, verdict = _run_gate(fixture, ticket=TICKET_REL, cwd=fixture.tmp)

        assert verdict.get("gate_passed") is True, f"verdict={verdict!r}"
        assert verdict.get("recorded") is True, f"verdict={verdict!r}"
        assert len(_record_lines(fixture.ticket)) == 1


def test_later_pass_replaces_the_record_not_duplicates_it():
    # covers: TQ-500f-3-ii
    # angle: boundary
    """A second pass for the same ticket replaces the line (the recorded test is renamed,
    still red, so the reader runs again and re-records)."""
    with tempfile.TemporaryDirectory() as tmp:
        fixture = _build(Path(tmp))
        _first_pass_recorded(fixture)
        fx.write(fixture.work / TESTS_REL, _tests_source(fixture.log, fixture.work, TEST_A + "_x"))

        proc, verdict = _run_gate(fixture)

        assert verdict.get("gate_passed") is True and verdict.get("reused") is not True, verdict
        lines = _record_lines(fixture.ticket)
        assert len(lines) == 1, f"exactly one record line must remain; lines={lines!r}"
        record = json.loads(lines[0][len(_RECORD_PREFIX):])
        assert TEST_A + "_x" in {r["function"] for r in record["red"]}, record


def test_green_at_baseline_verdict_carries_classification_and_remedy():
    # covers: TQ-500f-3-ii
    # angle: criterion
    """F3 option A: all-green tests with no record yield wrapper keys halt_classification
    and remedy listing every green test and advising coder phase not_needed."""
    with tempfile.TemporaryDirectory() as tmp:
        fixture = _build(Path(tmp))
        _code(fixture)

        proc, verdict = _run_gate(fixture)

        assert verdict.get("gate_passed") is False, f"verdict={verdict!r}"
        assert verdict.get("reason") == "all_new_tests_green_at_baseline", f"verdict={verdict!r}"
        assert verdict.get("halt_classification") == "green_at_baseline", f"verdict={verdict!r}"
        assert len(verdict.get("green_at_baseline") or []) == 2, "the reader's own list stays"
        remedy = str(verdict.get("remedy") or "")
        assert TEST_A in remedy and TEST_B in remedy, f"remedy must list both: {remedy!r}"
        assert "not_needed" in remedy and "commit" in remedy.lower(), f"remedy={remedy!r}"
