"""
MODULE: test_inf_500d_4_ix
GOAL: Tests for AC INF-500d-4-ix (written first; the parity helper now implements them) -- every copy of the usable-stream / stale-root rule
    gives the canonical verdict on every declaration row, and a copy that drifts (or a copy
    that cannot be found or run) fails a check that names it.
AC: INF-500d-4-ix (source_ac); extends test_inf_500d_4_iv_usable_stream_parity.py, which pins
    only emit_event against sink_resolution.

THIS FILE holds the verdict-parity, vacuity, side-effect, count and entry-point tests. The drift, missing-copy and
stand-in tests live in test_inf_500d_4_ix_drift.py; the constants, helpers and the ``baseline_report`` fixture both
files share live in _inf_500d_4_ix_test_support.py.

THE SIX COPIES (all taken from the DEPLOYED shared reference layout, never the source tree):
    canonical              .leafcutter/scripts/knowledge/sink_resolution.py   (read_usable_stream + enduring_root_exists)
    emit_event             .leafcutter/skills/agent-telemetry/scripts/emit_event.py        (_declared_stream)
    inline_work_guard      .leafcutter/hooks/inline_work_guard.py                          (_resolve_audit_path)
    plan_feature_telemetry .leafcutter/workflows/plan-feature.js     (the command emitPtTelemetry dispatches)
    building_epics_probe   .leafcutter/skills/building-epics/SKILL.md  (section 1.0 ``# pre-drive-reachability-check``)
    epic_supervisor_probe  .leafcutter/agents/epic-supervisor.md        (check 7 ``# pre-drive-reachability-check``)
The three shell copies are EXECUTED with a real shell and read by what they do; nothing here greps their text.

CONTRACT THIS FILE FIXES (python-coder implements ``unit_tests/feedback/_usable_stream_parity_copies.py``
against exactly this -- imported below as ``parity``):

    COPY_NAMES                      the five names above, in that order (canonical is not a "copy").
    Verdict(usable, location=None, detail="")          frozen dataclass.
    build_rows() -> list[Row]       the 14 row recipes, in the order of ROW_NAMES below. ``Row.name`` is the row name;
                                    ``Row.materialize(base, layout_dir) -> InstalledRow`` builds that row's cheap
                                    install under ``base`` (no build.py): see InstalledRow.
    InstalledRow                    ``.name`` ``.tree`` (whole temp tree: project AND enduring dirs; snapshot target)
                                    ``.project`` (cwd of shell copies; a REAL ``git init`` repo with ``.leafcutter/``)
                                    ``.out_root`` (project/.leafcutter, carrying the DEPLOYED files from layout_dir at
                                    ``scripts/knowledge/``, ``skills/agent-telemetry/``, ``hooks/inline_work_guard.py``
                                    and ``config/knowledge_sink.json`` as the row declares it)
                                    ``.log_root`` / ``.enduring_root`` / ``.stream`` (absolute Paths or None: the
                                    declared operational_log_root, the directory that holds it, the declared
                                    telemetry stream).
    canonical_verdict(layout_dir, installed, filename=None) -> Verdict
                                    the DEPLOYED canonical rule (fresh process): usable iff read_usable_stream accepts
                                    the declared telemetry stream AND the enduring root is live. ``filename`` set
                                    (``"inline_work_guard.jsonl"``) evaluates that file placed directly under the
                                    declared root instead (option A for the inline-work guard).
    load_copy(layout_dir, name) / load_copies(layout_dir) -> callable / {name: callable(InstalledRow) -> Verdict}
                                    raise ``CopyNotFoundError`` (message names the copy) when the file is absent, the
                                    snippet is absent, or no command can be extracted.
    run_parity(layout_dir, rows, canonical=None, copies=None, only=None) -> ParityReport
                                    ``canonical(installed, filename=None) -> Verdict`` (None: canonical_verdict).
                                    ``only`` names the copies to run (None: all). A shell copy is usable only when it
                                    exits 0 AND the declared stream gained exactly one line AND nothing else changed;
                                    ``ok`` is also False on a LOCATION mismatch on a row the canonical rule finds
                                    usable and on a stray write. ``shell_verdict(installed, command, label)`` judges
                                    any bash command that way (for stand-in copies).
                                    ``copies`` None loads the five deployed copies; ``{}`` means zero copies. Every
                                    (copy, row) pair runs on a FRESH materialization. A missing copy is recorded in
                                    ``errors`` (never raised, never skipped silently); the guard is compared against
                                    ``canonical(installed, "inline_work_guard.jsonl")``, the others against
                                    ``canonical(installed)``.
    ParityReport                    ``.ok`` ``.copies_compared`` ``.rows_compared`` ``.disagreements`` (Disagreement:
                                    ``.copy`` ``.row`` ``.canonical`` ``.observed``) ``.errors`` (list[str]) ``.verdicts``
                                    / ``.canonical_verdicts`` ({(copy, row): Verdict}) ``.vacuous`` ``.summary()``
                                    (contains ``copies_compared=N rows_compared=M``) ``.message()``. A disagreement
                                    line reads ``<copy> disagrees on row <row>: canonical=<usable|unusable>
                                    copy=<usable|unusable>``. ``.ok`` is False on any disagreement, any error, zero
                                    copies, zero rows, or a vacuous table (the canonical verdicts for a compared copy
                                    are all usable or all unusable); a vacuous report says "vacuous".
    __main__                        ``python _usable_stream_parity_copies.py <layout_dir>`` prints the summary to
                                    stdout, the failure message to stderr; exit 0 iff ok.

REAL-ARTIFACT NOTE: copies come from the real shared layout; declarations are written by the real build helper or
    json.dumps (for the shapes it cannot produce); the shell copies are run with ``bash``; nothing is reloaded in-process.
"""
# @ac-tag: INF-500d-4-ix

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from unit_tests.feedback import _inf_500d_4_helpers as h
from unit_tests.feedback._inf_500d_4_ix_test_support import (
    _GUARD_FILE,
    COPIES,
    GUARD,
    GUARD_USABLE,
    ROW_NAMES,
    TELEMETRY_USABLE,
    VANISHED_ROWS,
    _expected_usable,
    _hook_payload,
    _parity,
    _private_layout,
    _remove_probe_block,
    _state,
    _tmpdir,
    baseline_report,  # noqa: F401  (fixture: pytest resolves it by name from this module)
)

_HELPER_SCRIPT = h.REPO_ROOT / "unit_tests" / "feedback" / "_usable_stream_parity_copies.py"


@pytest.mark.shared_layout_reader
def test_every_copy_gives_the_canonical_verdict_on_every_row(shared_reference_layout, baseline_report):  # noqa: F811
    # covers: INF-500d-4-ix
    # angle: deployed
    """AC-1/4/5/6/9/10: all five copies, from the deployed layout, agree with the canonical rule on all 14 rows;
    the shell copies are executed; usable rows are exactly the live-root rows; locations match.

    Must catch: a shell copy hard-coding the debugging/logs holder (wrong only on the flat vanished row), a shell
    copy that drops the holder check, an inline copy accepting a two-level stream, and the guard compared against
    the telemetry stream's verdict (it would be falsely "drifted" on the outside/nested/relative stream rows).
    """
    parity = _parity()
    rows = parity.build_rows()
    assert [row.name for row in rows] == list(ROW_NAMES), "the table must carry exactly the criteria's rows, in order"
    assert tuple(parity.COPY_NAMES) == COPIES

    report = baseline_report

    assert report.errors == [], f"a copy could not be found or run on the deployed layout: {report.errors}"
    assert report.disagreements == [], "a copy disagrees with the canonical rule:\n" + report.message()
    assert report.copies_compared == 5 and report.rows_compared == 14, report.summary()
    assert len(report.verdicts) == 5 * 14 and len(report.canonical_verdicts) == 5 * 14

    for copy in COPIES:
        usable = {row for (name, row), verdict in report.verdicts.items() if name == copy and verdict.usable}
        assert usable == _expected_usable(copy), f"{copy} is usable on {sorted(usable)}, expected {sorted(_expected_usable(copy))}"
        canonical_usable = {row for (name, row), v in report.canonical_verdicts.items() if name == copy and v.usable}
        assert canonical_usable == _expected_usable(copy), f"the canonical rule, as compared against {copy}, is usable on {sorted(canonical_usable)}"

    for (copy, row), verdict in report.verdicts.items():
        if not verdict.usable:
            continue
        canonical_location = report.canonical_verdicts[(copy, row)].location
        assert canonical_location is not None and Path(canonical_location).is_absolute(), (copy, row, canonical_location)
        if verdict.location is not None:
            assert Path(verdict.location) == Path(canonical_location), f"{copy} reports {verdict.location} on {row}, canonical {canonical_location}"
        if copy in ("emit_event", GUARD, "plan_feature_telemetry"):
            assert verdict.location is not None, f"{copy} must report the location it uses on the usable row {row}"
            assert Path(verdict.location).name == (_GUARD_FILE if copy == GUARD else "agent_telemetry.jsonl"), (copy, row, verdict.location)


@pytest.mark.shared_layout_reader
def test_parity_table_is_not_vacuous(shared_reference_layout, tmp_path):
    # covers: INF-500d-4-ix
    # angle: discrimination
    """AC-6: the canonical rule finds exactly the live-root valid rows usable; a stand-in that always answers
    unusable, and one that always answers usable, each FAIL the check; and a table on which the canonical rule and
    every copy agree on one answer for everything fails as vacuous instead of passing.

    Must catch: a table where everything is unusable for everyone, and one where everything is usable for everyone.
    """
    parity = _parity()
    layout = Path(str(shared_reference_layout))
    rows = parity.build_rows()

    telemetry_usable: set[str] = set()
    guard_usable: set[str] = set()
    for row in rows:
        installed = row.materialize(tmp_path / "canonical" / row.name, layout)
        if parity.canonical_verdict(layout, installed).usable:
            telemetry_usable.add(row.name)
        if parity.canonical_verdict(layout, installed, filename=_GUARD_FILE).usable:
            guard_usable.add(row.name)
    assert telemetry_usable == TELEMETRY_USABLE, f"the canonical rule must find exactly the live-root valid rows usable: {sorted(telemetry_usable)}"
    assert guard_usable == GUARD_USABLE, f"option A: the guard's own file is usable wherever the declared root is: {sorted(guard_usable)}"

    always_unusable = {name: (lambda installed: parity.Verdict(usable=False)) for name in COPIES}
    always_usable = {name: (lambda installed: parity.Verdict(usable=True, location=installed.stream)) for name in COPIES}
    for label, stand_ins, wrong_rows in (
        ("always-unusable", always_unusable, _expected_usable),
        ("always-usable", always_usable, lambda copy: frozenset(ROW_NAMES) - _expected_usable(copy)),
    ):
        report = parity.run_parity(layout, rows, copies=stand_ins)
        assert not report.ok, f"a {label} stand-in copy must fail the check"
        assert not report.vacuous, f"{label}: the canonical table is mixed, so the failure is the stand-in's, not vacuity (control)"
        for copy in COPIES:
            flagged = {d.row for d in report.disagreements if d.copy == copy}
            assert flagged == set(wrong_rows(copy)), f"{label} {copy}: flagged {sorted(flagged)}"

    # Everyone agrees on one answer for everything: the table proves nothing, so the check must not pass.
    for label, usable in (("all-unusable", False), ("all-usable", True)):
        flat = parity.run_parity(
            layout, rows,
            canonical=lambda installed, filename=None, _u=usable: parity.Verdict(usable=_u, location=installed.stream),
            copies={name: (lambda installed, _u=usable: parity.Verdict(usable=_u, location=installed.stream)) for name in COPIES},
        )
        assert flat.disagreements == [], f"{label}: the stand-ins agree with the stand-in canonical rule (precondition)"
        assert flat.vacuous and not flat.ok, f"{label}: agreement on a single answer for every row must fail the check"
        assert "vacuous" in flat.message().lower(), flat.message()


@pytest.mark.shared_layout_reader
def test_no_copy_creates_anything_on_an_unusable_row(shared_reference_layout, tmp_path):
    # covers: INF-500d-4-ix
    # angle: failure
    """AC-7: on every row a copy finds unusable, running it leaves the row's whole tree byte-identical -- no log
    directory, no enduring root, no new file, no appended line. The inline copies are run twice: as the loaded
    function (the parity verdict) and as the real emit_event.py / inline_work_guard.py programs.

    Must catch: a shell copy running ``mkdir -p`` before the holder check (recreating a vanished root), and an
    inline copy creating the log directory on an unusable declaration. Controls: the same programs DO write on a
    usable row, so their silence on the unusable rows is the declaration's doing.
    """
    parity = _parity()
    layout = Path(str(shared_reference_layout))
    rows = parity.build_rows()
    copies = parity.load_copies(layout)
    assert list(copies) == list(COPIES)
    tmpdir = _tmpdir(tmp_path)

    exercised = 0
    for row in rows:
        for copy, run in copies.items():
            if row.name in _expected_usable(copy):
                continue
            installed = row.materialize(tmp_path / copy / row.name, layout)
            before = _state(installed.tree)
            verdict = run(installed)
            assert not verdict.usable, f"{copy} must find {row.name} unusable"
            assert _state(installed.tree) == before, f"{copy} changed the tree of the unusable row {row.name}"
            if row.name in VANISHED_ROWS:
                assert not installed.log_root.exists() and not installed.enduring_root.exists(), f"{copy} recreated the vanished root of {row.name}"
            exercised += 1
    assert exercised == 4 * 11 + 1 * 7, f"every unusable (copy, row) pair must be exercised, got {exercised}"

    for row in rows:
        if row.name not in TELEMETRY_USABLE:
            emitted = row.materialize(tmp_path / "emit_cli" / row.name, layout)
            before = _state(emitted.tree)
            proc = h.run_py(emitted.out_root / "skills" / "agent-telemetry" / "scripts" / "emit_event.py", h.emit_args(), emitted.project, tmpdir)
            assert proc.returncode == 0, "telemetry stays non-fatal"
            assert _state(emitted.tree) == before, f"the real emit_event.py wrote something on the unusable row {row.name}"
        if row.name not in GUARD_USABLE:
            guarded = row.materialize(tmp_path / "guard_cli" / row.name, layout)
            (guarded.project / ".build-feature.lock").write_text("locked\n", encoding="utf-8")
            before = _state(guarded.tree)
            proc = h.run_py(guarded.out_root / "hooks" / "inline_work_guard.py", [], guarded.project, tmpdir,
                            stdin=_hook_payload(guarded.project), env_extra={"INLINE_WORK_GUARD_MODE": "warn"})
            assert proc.returncode == 0, proc.stderr
            assert _state(guarded.tree) == before, f"the real inline_work_guard.py wrote something on the unusable row {row.name}"

    live = next(r for r in rows if r.name == "valid_log_dir_missing_conventional")
    emitted = live.materialize(tmp_path / "emit_control", layout)
    proc = h.run_py(emitted.out_root / "skills" / "agent-telemetry" / "scripts" / "emit_event.py", h.emit_args(), emitted.project, tmpdir)
    assert proc.returncode == 0 and len(h.read_records(emitted.stream)) == 1, "control: the real emit_event.py writes on a usable row"
    guarded = live.materialize(tmp_path / "guard_control", layout)
    (guarded.project / ".build-feature.lock").write_text("locked\n", encoding="utf-8")
    proc = h.run_py(guarded.out_root / "hooks" / "inline_work_guard.py", [], guarded.project, tmpdir,
                    stdin=_hook_payload(guarded.project), env_extra={"INLINE_WORK_GUARD_MODE": "warn"})
    assert proc.returncode == 0 and len(h.read_records(guarded.log_root / _GUARD_FILE)) == 1, "control: the real guard writes on a usable row"


@pytest.mark.shared_layout_reader
def test_check_reports_how_many_copies_and_rows_it_compared(shared_reference_layout, baseline_report):  # noqa: F811
    # covers: INF-500d-4-ix
    # angle: criterion
    """AC-16: every run reports copies and rows compared (five and 14 on the deployed layout), and a run that compared
    zero copies or zero rows fails instead of reporting agreement.

    Must catch: a run that compared nothing and reports agreement.
    """
    parity = _parity()
    layout = Path(str(shared_reference_layout))
    rows = parity.build_rows()

    full = baseline_report
    assert full.ok, full.message()
    assert full.copies_compared == 5 and full.rows_compared == 14
    assert "copies_compared=5" in full.summary() and "rows_compared=14" in full.summary()

    no_rows = parity.run_parity(layout, [])
    assert no_rows.rows_compared == 0 and "rows_compared=0" in no_rows.summary()
    assert not no_rows.ok, "a run that compared no rows must not report agreement"

    no_copies = parity.run_parity(layout, rows, copies={})
    assert no_copies.copies_compared == 0 and "copies_compared=0" in no_copies.summary()
    assert no_copies.disagreements == [] and no_copies.errors == [], "nothing disagreed -- there was nothing to disagree"
    assert not no_copies.ok, "a run that compared no copies must not report agreement"


@pytest.mark.shared_layout_reader
def test_inf_500d_4_ix_reachable_from_entry_point(shared_reference_layout, tmp_path):
    # covers: INF-500d-4-ix
    # angle: reachability
    """The entry point is the parity check itself: the helper run as a program on the deployed layout reports five
    copies and 14 rows and exits 0; on a private layout missing one copy it exits non-zero and names it. Run as a
    subprocess -- importing run_parity does not satisfy this."""
    assert _HELPER_SCRIPT.is_file(), f"the parity check program does not exist: {_HELPER_SCRIPT}"
    tmpdir = _tmpdir(tmp_path)

    def run(layout: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-B", str(_HELPER_SCRIPT), str(layout)], capture_output=True, text=True,
                              cwd=str(h.REPO_ROOT), timeout=540, check=False, env=h.make_env(tmpdir))

    good = run(Path(str(shared_reference_layout)))
    assert good.returncode == 0, f"the check failed on the deployed layout:\n{good.stdout}\n{good.stderr}"
    assert "copies_compared=5" in good.stdout and "rows_compared=14" in good.stdout, good.stdout

    private = _private_layout(shared_reference_layout, tmp_path / "layout")
    _remove_probe_block(private, "building_epics")
    bad = run(private)
    assert bad.returncode != 0, "a missing copy must fail the check program"
    assert "building_epics_probe" in bad.stdout + bad.stderr, f"the failure must name the missing copy:\n{bad.stdout}\n{bad.stderr}"
    assert "copies_compared=4" in bad.stdout + bad.stderr, "every run reports how many copies it compared"
