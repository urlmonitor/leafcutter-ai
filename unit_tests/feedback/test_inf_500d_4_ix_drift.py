"""
MODULE: test_inf_500d_4_ix_drift
GOAL: Drift half of the AC INF-500d-4-ix tests -- a canonical rule that flips, a copy that drifts, a copy that cannot be
    found or run, and stand-in copies that write or report wrongly, each fail a check that names the copy and the row.
AC: INF-500d-4-ix (source_ac). The contract is described in the docstring of test_inf_500d_4_ix.py; the shared
    constants, helpers and stand-in factories live in _inf_500d_4_ix_test_support.py.
"""
# @ac-tag: INF-500d-4-ix

from __future__ import annotations

import re
from pathlib import Path

import pytest

from unit_tests.feedback._inf_500d_4_ix_test_support import (
    _DRIFTS,
    _LAYOUT_FILES,
    _MISSING_COPIES,
    _STAND_IN_ROWS,
    _STAND_INS,
    COPIES,
    TELEMETRY_COPIES,
    _edit,
    _parity,
    _private_layout,
    _stand_in_writer,
    _tree_digest,
)


@pytest.mark.shared_layout_reader
@pytest.mark.parametrize(
    ("case", "row_name", "flipped_usable"),
    [("stream_two_levels_becomes_usable", "stream_two_levels_under_root", True),
     ("missing_log_dir_treated_as_stale", "valid_log_dir_missing_conventional", False)],
)
def test_check_names_copy_row_and_verdicts_when_the_canonical_rule_flips(shared_reference_layout, case, row_name, flipped_usable):
    # covers: INF-500d-4-ix
    # angle: discrimination
    """AC-12/13/14: flip the canonical verdict on ONE row (in-process, the shared layout is untouched) and leave every
    copy as deployed: the check fails, and each disagreeing copy is named with the row and both verdicts.

    Must catch: a check comparing copies only to each other (it would pass here), and a failure that says
    "mismatch" without the copy, the row and the two verdicts.
    """
    parity = _parity()
    layout = Path(str(shared_reference_layout))
    rows = parity.build_rows()
    digest_before = _tree_digest(layout)

    def flipped(installed, filename=None):
        real = parity.canonical_verdict(layout, installed, filename)
        if filename is None and installed.name == row_name:
            return parity.Verdict(usable=flipped_usable, location=installed.stream)
        return real

    report = parity.run_parity(layout, rows, canonical=flipped)

    assert not report.ok, f"{case}: a changed canonical rule with unchanged copies must fail the check"
    assert report.errors == [], report.errors
    # Only the telemetry copies are compared against the telemetry verdict; the guard answers for its own file.
    assert {(d.copy, d.row) for d in report.disagreements} == {(copy, row_name) for copy in TELEMETRY_COPIES}, report.message()
    canonical_word, copy_word = ("usable", "unusable") if flipped_usable else ("unusable", "usable")
    message = report.message()
    for copy in TELEMETRY_COPIES:
        pattern = rf"{copy} disagrees on row {row_name}: canonical={canonical_word}\s+copy={copy_word}"
        assert re.search(pattern, message), f"the failure must name copy, row and both verdicts ({pattern}):\n{message}"
    assert _tree_digest(layout) == digest_before, "the shared layout must be byte-identical after the check"


@pytest.mark.shared_layout_reader
@pytest.mark.parametrize("case", sorted(_DRIFTS))
def test_a_drifted_copy_fails_the_check_naming_it_and_the_row(shared_reference_layout, tmp_path, case):
    # covers: INF-500d-4-ix
    # angle: discrimination
    """AC-12/13/14, on REAL drifted text in a private layout: each wrong version of one copy is caught on exactly the
    rows it gets wrong, naming that copy; no other copy is flagged. The last case changes the deployed canonical rule
    itself: the shell copies ask that same rule, so only the standalone inline copy disagrees.

    Must catch: a shell copy verified by grepping its text (a grep cannot name the row), and a holder computation
    hard-coded to the conventional layout (right on every conventional row).
    """
    parity = _parity()
    key, old, new, drifted, expected_rows = _DRIFTS[case]
    private = _private_layout(shared_reference_layout, tmp_path / "layout")
    _edit(private, key, old, new)

    report = parity.run_parity(private, parity.build_rows())

    assert not report.ok and report.errors == [], report.message()
    assert report.copies_compared == 5 and report.rows_compared == 14, report.summary()
    flagged = {(d.copy, d.row) for d in report.disagreements}
    assert flagged == {(drifted, row) for row in expected_rows}, f"{case}: flagged {sorted(flagged)}\n{report.message()}"
    assert drifted in report.message() and all(row in report.message() for row in expected_rows)


@pytest.mark.shared_layout_reader
def test_a_harmless_rewording_of_a_probe_still_passes(shared_reference_layout, tmp_path):
    # covers: INF-500d-4-ix
    # angle: discrimination
    """Control for the drift cases above: renaming a probe's scratch variable changes its text and not what it does,
    so the check must still pass. (A check that looks for expected fragments fails here; one that runs the probe
    does not.)"""
    parity = _parity()
    private = _private_layout(shared_reference_layout, tmp_path / "layout")
    path = private / _LAYOUT_FILES["epic_supervisor"]
    text = path.read_text(encoding="utf-8")
    assert "WRITE_AT" in text, "fixture: the probe uses WRITE_AT"
    path.write_text(text.replace("WRITE_AT", "PROBE_DIR"), encoding="utf-8")

    report = parity.run_parity(private, parity.build_rows())

    assert report.ok, report.message()
    assert report.copies_compared == 5 and report.rows_compared == 14


@pytest.mark.shared_layout_reader
@pytest.mark.parametrize("copy", COPIES)
def test_check_fails_and_names_a_copy_it_cannot_find_or_run(shared_reference_layout, tmp_path, copy):
    # covers: INF-500d-4-ix
    # angle: failure
    """AC-15: with one copy absent (file removed, command unextractable, or snippet removed) from a PRIVATE layout, the
    check fails and names that copy; it is not compared, not skipped silently, and the other four still agree.

    Must catch: an extractor that returns an empty command (the shell runs it successfully -- it would be COMPARED, so
    copies_compared would stay 5), and a missing copy that is skipped while the run still reports agreement.
    """
    parity = _parity()
    private = _private_layout(shared_reference_layout, tmp_path / "layout")
    _MISSING_COPIES[copy](private)

    with pytest.raises(parity.CopyNotFoundError, match=copy):
        parity.load_copy(private, copy)

    report = parity.run_parity(private, parity.build_rows())

    assert not report.ok
    assert len(report.errors) == 1 and copy in report.errors[0], f"exactly the missing copy is reported: {report.errors}"
    assert copy in report.message()
    assert report.copies_compared == 4, f"the missing copy must not count as compared: {report.summary()}"
    assert report.rows_compared == 14
    assert report.disagreements == [], f"the other four copies still agree (control): {report.message()}"
    assert not any(c == copy for (c, _row) in report.verdicts), "a copy that cannot be found must have no verdicts"


@pytest.mark.shared_layout_reader
@pytest.mark.parametrize("case", sorted(_STAND_INS))
def test_a_copy_writing_wrongly_or_reporting_another_location_fails_naming_copy_and_row(shared_reference_layout, case):
    # covers: INF-500d-4-ix
    # angle: discrimination
    """AC-6/9/12: a usable verdict is exit 0 AND exactly one line in the declared stream AND nothing else changed, and a
    copy that reports a location must report the canonical one. A stand-in that writes TWO lines, one that writes the
    line to the WRONG file, and one that is right about the verdict but reports another location each make ``ok`` false
    and name the copy and the row; the same stand-in written correctly passes (control).

    Must catch: reading "exit 0 and one file changed" as usable (all three pass that), and ``ok`` ignoring the location.
    """
    parity = _parity()
    layout = Path(str(shared_reference_layout))
    rows = [row for row in parity.build_rows() if row.name in _STAND_IN_ROWS]
    assert len(rows) == len(_STAND_IN_ROWS)

    control = parity.run_parity(layout, rows, copies={"stand_in": _stand_in_writer(parity, "one\\n", lambda i: i.stream)})
    assert control.ok, f"control: a correct one-line writer must pass:\n{control.message()}"

    report = parity.run_parity(layout, rows, copies={"stand_in": _STAND_INS[case](parity)})

    assert not report.vacuous and report.errors == [], report.message()
    assert not report.ok, f"{case}: a wrong stand-in must fail the check\n{report.message()}"
    message = report.message()
    assert "stand_in" in message and "valid_log_dir_present" in message, message
    if case == "location_only_drift":
        assert report.disagreements == [], "the verdict is right; only the location differs"
        assert [(m.copy, m.row) for m in report.location_mismatches] == [("stand_in", "valid_log_dir_present")]
        assert "agent_telemetry.jsonl" in message and "elsewhere.jsonl" in message, "both paths must be in the message"
    else:
        assert {(d.copy, d.row) for d in report.disagreements} == {("stand_in", "valid_log_dir_present")}, message
