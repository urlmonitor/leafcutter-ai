"""
MODULE: test_inf_500d_3
GOAL: RED tests for AC INF-500d-3 -- a report that could not be written says which report failed and why.
    ``submit_feedback.py`` prints exactly one ``submit-failed:<reason>:<category>`` stderr line on every failure
    exit it controls, with ``<reason>`` drawn from the closed set in ``submit_failure_reasons.json``.
AC: INF-500d-3 (source_ac); depends on INF-500d (sink), INF-500d-4-i (declared-sink refusal).

This file holds the vocabulary, marker and caller-rule tests. The failure-exit, scenario, INF-500d-4-i wrapper
and parser tests are in ``test_inf_500d_3_exits.py``; the shared helpers are in ``_inf_500d_3_support.py``.

CONTRACT THIS FILE FIXES (python-coder implements against exactly this):

    1. ``templates/scripts/feedback/submit_failure_reasons.json`` exists (deployed whole with
       ``scripts/feedback/``). It holds five reason objects ``{id, meaning, record_written, detected_by}``
       (ids: writer-not-allowed, malformed-submission, facility-unavailable, destination-unwritable,
       written-uncited; ``record_written`` true for written-uncited alone), the marker form
       ``feedback-id: (submit-failed:<reason>:<category>)`` and three value patterns (real id, reasoned
       marker, legacy bare form). No ``{{config.*}}`` placeholder. The file's KEY NAMES are not fixed by the
       AC: this file reads the reasons as the one list of ``{"id": ...}`` objects in the file and finds each
       pattern and the marker form by what it matches / contains, so any key names work.
    2. On every failure exit the script controls, stderr carries exactly one line
       ``submit-failed:<reason>:<category>``, stdout stays empty, the exit status stays non-zero, the existing
       human-readable ERROR / usage / "Checked path" lines stay, no ``sidecar:`` / ``[submit_feedback] sink:``
       line appears, and no traceback ends the run. ``<category>`` is the ``--category`` value, or ``-`` when
       none was given or the value is not one token free of whitespace, ":", "(" and ")".
    3. Exit path -> reason: argument-parser errors and the source-argument check, an unrecognised category, a
       bad tag and a bad ``--addressed-by`` -> malformed-submission; the writer refusal -> writer-not-allowed;
       missing PyYAML, an absent / unparseable / empty categories file -> facility-unavailable; the declared-sink
       refusal, an uncreatable log directory, an unopenable or unwritable sink (incl. an ``--jsonl`` whose parent
       cannot be created) -> destination-unwritable. written-uncited and (for the missing-entry-point case)
       facility-unavailable are decided by the CALLER, so the script prints no reason line there.
    4. Fail-open: the script never substitutes a built-in reason list; with the vocabulary unreadable it still
       exits non-zero with empty stdout.
    5. INF-500d-4-i's two refusal-count sites count human-readable refusal lines through
       ``_inf_500d_4_helpers.refusal_lines`` (every non-blank stderr line minus at most ONE line that begins
       with ``submit-failed:``); ``stderr_lines`` keeps its meaning.

REAL-ARTIFACT NOTE: every run is the REAL ``submit_feedback.py`` of a copied layout as a subprocess with its own
    declared sink in a temp dir and a confined TMPDIR; the declaration is written by the real build helper. The
    vocabulary is read from the copied layout, never from a list in this file (test 1 alone names the five ids).
    No build.py is spawned and nothing mocks a write.
"""
# @ac-tag: INF-500d-3

from __future__ import annotations

import re
import subprocess

from unit_tests.feedback import _inf_500d_4_helpers as h
from unit_tests.feedback._inf_500d_3_support import (
    BARE,
    MARKER_EXAMPLE,
    REAL_ID_EXAMPLE,
    SINK_PREFIX,
    Scn,
    _argv,
    _assert_reason,
    _block_yaml,
    _caller_reason,
    _exec,
    _facts_of_a_write,
    _fill_form,
    _hook_argv,
    _holdable,
    _ids,
    _jsonl,
    _kw,
    _layout,
    _load_vocab,
    _marker_form,
    _patterns,
    _prep_jsonl_directory,
    _reason_lines,
    _reasoned_value,
    _reasons,
    _run,
    _sidecar_file,
    _vocab_file,
)

_EMIT_DRIVER = (
    "import importlib.util, json, sys\n"
    "spec = importlib.util.spec_from_file_location('ehf', sys.argv[1])\n"
    "m = importlib.util.module_from_spec(spec)\n"
    "sys.modules['ehf'] = m\n"
    "spec.loader.exec_module(m)\n"
    "try:\n"
    "    ret = m.emit_finding(hook_name='check_probe', outcome='warn',\n"
    "                         note='inf-500d-3 probe', tags=['probe'])\n"
    "except BaseException as exc:\n"
    "    print('RAISED ' + type(exc).__name__)\n"
    "    sys.exit(3)\n"
    "print('RETURNED ' + json.dumps(ret))\n"
)


# ---------------------------------------------------------------------------
# 1-2, 11-12: the vocabulary file
# ---------------------------------------------------------------------------

def test_vocabulary_file_holds_exactly_the_five_closed_set_reasons_with_their_flags(tmp_path):
    # covers: INF-500d-3
    # angle: discrimination
    """submit_failure_reasons.json (reached through the copied layout) holds exactly the five closed-set reasons."""
    lay = _layout(tmp_path)
    vocab = _load_vocab(lay.out_root)
    reasons = _reasons(vocab)

    assert len(reasons) == 5, f"exactly five reasons expected (no sixth, none missing): {[r.get('id') for r in reasons]}"
    assert sorted(r["id"] for r in reasons) == sorted(
        ["writer-not-allowed", "malformed-submission", "facility-unavailable", "destination-unwritable",
         "written-uncited"]), f"the five ids are fixed and never renamed: {_ids(vocab)}"
    for entry in reasons:
        where = entry["id"]
        assert isinstance(entry.get("meaning"), str) and len(entry["meaning"].split()) >= 3, f"{where}: needs a sentence"
        assert type(entry.get("record_written")) is bool, f"{where}: record_written must be a boolean: {entry!r}"
        assert entry.get("detected_by") in ("script", "caller"), f"{where}: detected_by must be script or caller"
    written = sorted(r["id"] for r in reasons if r["record_written"])
    assert written == ["written-uncited"], f"record_written is true for written-uncited alone: {written}"


def test_vocabulary_file_carries_the_marker_form_the_three_value_patterns_and_no_config_placeholder(tmp_path):
    # covers: INF-500d-3
    # angle: criterion
    """The same file holds the marker form and the three value patterns; each behaves as the AC states."""
    lay = _layout(tmp_path)
    vocab = _load_vocab(lay.out_root)
    text = _vocab_file(lay.out_root).read_text(encoding="utf-8")
    pats = _patterns(vocab)

    assert "{{" not in text, "the build runs inject_config over .json files: no double-brace placeholder allowed"
    assert "submit-failed:<reason>:<category>" in _marker_form(vocab)
    assert pats["real"].search(REAL_ID_EXAMPLE) and not pats["real"].search(MARKER_EXAMPLE)
    reasoned = pats["reasoned"].search(MARKER_EXAMPLE)
    assert reasoned and reasoned.group(1) in _ids(vocab) and reasoned.group(2) == "complete"
    for bad in ("a:b", "a b", "a(b", "a)b"):
        assert not pats["reasoned"].search(f"(submit-failed:destination-unwritable:{bad})"), f"category {bad!r} accepted"
    assert not pats["reasoned"].search(BARE)
    assert pats["legacy"].search(BARE)
    assert not pats["legacy"].search(MARKER_EXAMPLE) and not pats["legacy"].search("(submit-failed) trailing")


def test_only_a_written_uncited_marker_is_record_written_so_only_it_is_never_holdable(tmp_path):
    # covers: INF-500d-3
    # angle: discrimination
    """Holdability derives from record_written alone: only the written-uncited marker is not holdable."""
    lay = _layout(tmp_path)
    vocab = _load_vocab(lay.out_root)

    verdicts = {rid: _holdable(f"(submit-failed:{rid}:complete)", vocab) for rid in _ids(vocab)}

    assert verdicts.pop("written-uncited") is False, "a stored record must never be held or re-filed"
    assert verdicts == {rid: True for rid in verdicts} and len(verdicts) == 4, (
        f"the other four reasons mean nothing was written, so they are holdable: {verdicts}")
    assert _holdable(BARE, vocab) is False, "the legacy bare marker means reason unknown, never holdable"
    assert _patterns(vocab)["legacy"].search(BARE) and not _patterns(vocab)["reasoned"].search(BARE)
    # Control: a vocabulary with an extra reason is classified from its flag with no code change.
    future = {"id": "some-future-reason", "meaning": "A later reason.", "detected_by": "script"}
    for flag in (True, False):
        added = [*_reasons(vocab), {**future, "record_written": flag}]
        if isinstance(vocab, list):
            extended = added
        else:
            extended = {key: (added if value is _reasons(vocab) else value) for key, value in vocab.items()}
        assert _holdable("(submit-failed:some-future-reason:complete)", extended) is (not flag)


def test_written_uncited_marker_parses_as_a_record_that_exists_but_is_uncited(tmp_path):
    # covers: INF-500d-3
    # angle: criterion
    """feedback-id: (submit-failed:written-uncited:complete) parses to a reason whose record exists."""
    lay = _layout(tmp_path)
    vocab = _load_vocab(lay.out_root)
    value = "(submit-failed:written-uncited:complete)"

    match = _patterns(vocab)["reasoned"].search(value)

    assert match is not None, f"the reasoned-marker pattern must accept {value}"
    assert match.group(1) == "written-uncited" and match.group(2) == "complete"
    entry = {r["id"]: r for r in _reasons(vocab)}["written-uncited"]
    assert entry["record_written"] is True and entry["detected_by"] == "caller"
    assert "written" in entry["meaning"].lower(), f"the meaning must say the report was written: {entry['meaning']!r}"
    assert _fill_form(_marker_form(vocab), "written-uncited", "complete") == value


# ---------------------------------------------------------------------------
# caller rule: no reason line for the caller-decided reasons
# ---------------------------------------------------------------------------

def test_missing_entry_point_and_unreadable_vocabulary_leave_no_reason_line_for_the_caller_rule(tmp_path):
    # covers: INF-500d-3
    # angle: criterion
    """No reason line, sidecar or sink line when the entry point is gone; fail-open when the vocabulary is gone."""
    lay = _layout(tmp_path)
    vocab_ids = _ids(_load_vocab(lay.out_root))  # also fails clearly while the vocabulary file does not exist
    script = h.submit_script(lay.out_root)

    # (2) the vocabulary deleted first: the script still fails closed and never substitutes a reason list.
    _vocab_file(lay.out_root).unlink()
    no_vocab = _run(lay, _argv())
    assert no_vocab.returncode != 0, f"an unreadable vocabulary must not let the run succeed: {no_vocab.stderr!r}"
    assert no_vocab.stdout == "", f"no id may be printed: {no_vocab.stdout!r}"
    assert not _reason_lines(no_vocab) and not _facts_of_a_write(no_vocab), no_vocab.stderr
    assert not [rid for rid in vocab_ids if rid in no_vocab.stderr], f"a built-in reason list was used: {no_vocab.stderr!r}"
    assert not lay.sink.exists()

    # (1) the entry point deleted and invoked by its prescribed path: the interpreter's own error only.
    script.unlink()
    missing = _run(lay, _argv())
    assert missing.returncode != 0 and missing.stdout == ""
    assert missing.stderr.strip(), "the interpreter must report the missing file"
    assert not _reason_lines(missing) and not _facts_of_a_write(missing), missing.stderr
    assert _caller_reason(missing.stdout, missing.stderr, None) == "facility-unavailable"


# ---------------------------------------------------------------------------
# 8-10: success, category part, fail-open
# ---------------------------------------------------------------------------

def test_successful_submission_prints_no_reason_line_and_keeps_its_stdout_sidecar_and_sink_lines(tmp_path):
    # covers: INF-500d-3
    # angle: criterion
    """A successful run: the id alone on stdout, one sidecar line, one sink line, and no submit-failed line."""
    lay = _layout(tmp_path)
    vocab = _load_vocab(lay.out_root)
    uncited = {r["id"]: r for r in _reasons(vocab)}["written-uncited"]
    assert uncited["record_written"] is True, "the facts of a successful write are what written-uncited is decided from"

    proc = _run(lay, _argv())

    assert proc.returncode == 0, proc.stderr
    assert re.match(h.FEEDBACK_ID_RE, proc.stdout.strip()) and proc.stdout == proc.stdout.strip() + "\n"
    assert not _reason_lines(proc), f"a successful run never prints a reason line: {proc.stderr!r}"
    sink_lines = [line for line in proc.stderr.splitlines() if line.startswith(SINK_PREFIX)]
    assert sink_lines == [f"{SINK_PREFIX}{lay.sink.resolve()}"], proc.stderr
    recovery = _sidecar_file(proc)
    assert recovery.read_text(encoding="utf-8") == proc.stdout.strip()
    record_text = lay.sink.read_text(encoding="utf-8")
    assert proc.stdout.strip() in record_text
    # Deleting the recovery file changes nothing that was written, and the caller rule then reads written-uncited.
    recovery.unlink()
    assert lay.sink.read_text(encoding="utf-8") == record_text
    assert _caller_reason("", proc.stderr, None) == "written-uncited"
    # Control: a failed run carries neither fact, so the two situations cannot be confused.
    failed = _run(lay, _argv(category="subagent-quality"))
    assert not _facts_of_a_write(failed) and _caller_reason("", failed.stderr, None) == "writer-not-allowed"


def test_category_part_is_the_submitted_value_or_a_dash_never_a_default(tmp_path):
    # covers: INF-500d-3
    # angle: discrimination
    """The category part of the line is the --category value verbatim, or a dash when unrepresentable."""
    lay = _layout(tmp_path)
    pattern = _patterns(_load_vocab(lay.out_root))["reasoned"]
    verbatim = ("complete", "blocker", "subagent-quality", "zzz-unknown")
    dashed = {"missing --category": None, "a space": "a b", "a colon": "a:b", "an opening paren": "a(b",
              "a closing paren": "a)b", "an empty value": ""}

    for category in verbatim:
        proc = _run(lay, _argv(category=category, tags="1bad"))
        _assert_part(proc, category, pattern)
    for label, value in dashed.items():
        proc = _run(lay, _argv(category=value, tags="1bad"))
        _assert_part(proc, "-", pattern, label)


def _assert_part(proc: subprocess.CompletedProcess[str], expected: str, pattern: re.Pattern[str], label: str = "") -> None:
    lines = _reason_lines(proc)
    assert len(lines) == 1, f"{label or expected}: expected one reason line, stderr={proc.stderr!r}"
    parts = lines[0].split(":")
    assert len(parts) == 3 and parts[0] == "submit-failed", f"{label or expected}: line must have three parts: {lines[0]!r}"
    assert parts[2] == expected, f"{label or expected}: category part {parts[2]!r} != {expected!r}"
    match = pattern.search(_reasoned_value(lines[0]))
    assert match and match.group(2) == expected, f"{label or expected}: line must match the reasoned-marker pattern"


def test_failed_submission_stays_fail_open_for_hook_callers(tmp_path):
    # covers: INF-500d-3
    # angle: criterion
    """Hook mode still prints the one reason line; emit_finding returns False, never raises, and does not read as written."""
    lay = _layout(tmp_path)
    h.declaration_path(lay.out_root).unlink()

    refused = _run(lay, _hook_argv())
    _assert_reason(refused, "destination-unwritable", "process-finding", "hook, no declaration")
    no_outcome = _run(lay, _hook_argv(outcome=None))
    _assert_reason(no_outcome, "malformed-submission", "process-finding", "hook, no --outcome")

    target = str(lay.out_root / "scripts" / "feedback" / "emit_hook_finding.py")
    before = h.snapshot(tmp_path)
    driven = h.run_code(_EMIT_DRIVER, [target], lay.cwd, lay.tmpdir)
    assert driven.returncode == 0, f"emit_finding must not raise into its caller: {driven.stdout!r} {driven.stderr!r}"
    assert driven.stdout.strip().splitlines() == ["RETURNED false"], driven.stdout
    assert str(h.declaration_path(lay.out_root)) in driven.stderr, f"the reason must name the declaration: {driven.stderr!r}"
    assert not _facts_of_a_write(driven), f"the failure must not read as written: {driven.stderr!r}"
    assert not re.search(r"uncited|written but", driven.stderr, re.IGNORECASE), driven.stderr
    assert len(_reason_lines(driven)) <= 1 and all(
        line.startswith("submit-failed:destination-unwritable:") for line in _reason_lines(driven))
    assert h.snapshot(tmp_path) == before
    # Control: with a declaration the same entry point returns True.
    h.declare(lay.out_root, lay.root)
    ok = h.run_code(_EMIT_DRIVER, [target], lay.cwd, lay.tmpdir)
    assert ok.stdout.strip().splitlines()[-1] == "RETURNED true", f"{ok.stdout!r} {ok.stderr!r}"


# ---------------------------------------------------------------------------
# 13-14: the five markers from one layout
# ---------------------------------------------------------------------------

def test_five_failures_in_one_run_are_distinguishable_by_reason_from_the_markers_alone(tmp_path):
    # covers: INF-500d-3
    # angle: discrimination
    """Five markers from one layout (one TMPDIR, one sink) parse to five different reasons equal to the ids."""
    lay = _layout(tmp_path)
    vocab = _load_vocab(lay.out_root)
    pattern = _patterns(vocab)["reasoned"]
    runs = {
        "writer": Scn(argv=_kw(category="subagent-quality")),
        "malformed": Scn(argv=_kw(tags="1bad")),
        "facility": Scn(env=_block_yaml),
        "destination": Scn(prepare=_prep_jsonl_directory, argv=_jsonl(lambda lay: str(lay.base / "a_directory"))),
    }
    markers = []
    for name, scn in runs.items():
        proc, _before = _exec(lay, scn)
        lines = _reason_lines(proc)
        assert len(lines) == 1, f"{name}: expected one reason line, stderr={proc.stderr!r}"
        markers.append(_reasoned_value(lines[0]))
    # The fifth: a successful write whose id the caller did not capture (recovery file removed).
    ok = _run(lay, _argv())
    assert ok.returncode == 0, ok.stderr
    _sidecar_file(ok).unlink()
    reason = _caller_reason("", ok.stderr, None)
    markers.append(_fill_form(_marker_form(vocab), reason or "?", "complete"))

    parsed = [pattern.search(marker) for marker in markers]
    assert all(parsed), f"every marker must parse with the vocabulary pattern: {markers}"
    reasons = [m.group(1) for m in parsed if m]
    assert len(set(reasons)) == 5, f"the five failures must be told apart by reason alone: {reasons}"
    assert sorted(reasons) == sorted(_ids(vocab)), f"the five reasons must equal the vocabulary ids: {reasons}"
