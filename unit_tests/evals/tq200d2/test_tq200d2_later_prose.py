"""
MODULE: unit_tests/evals/tq200d2/test_tq200d2_later_prose
GOAL: RED tests for TQ-200d-2-i: the to-run-later check of the sql-test-writer "stored-procedure
    regression" row stops requiring the function name inside the free-prose wrong version. The
    function is checked in the entry's test id (``::``), the wrong version only for being non-empty,
    and the file's ac_id must match.
Target: scripts/evals/sql_test_writer_eval/evidence_kinds.py, scripts/evals/sets/sql-test-writer.jsonl,
    docs/reference/produced-tests-eval-assertion-kinds-sql-test-writer.md
Every probe is a recorded to-run-later file (written by json.dump; the live one is the file shape of the
2026-10-25 before-score) laid over the REAL gold output of the row, so a probe can only fail for the
reason it carries. Scored through the real scoring path; no model, no network.
"""

from __future__ import annotations

import json

import unit_tests.evals.tq200d1ii._helpers as ref
import unit_tests.evals.tq200d2._helpers as h
import unit_tests.evals.tq200d2._probes as p

LATER = h.FIXTURES / "probes_later"
KEYWORD = "fn_refresh_due"
LIVE_WRONG_VERSION = "select refresh_due (retry_due parameter ignored entirely)"


def _spec() -> dict:
    return next(a for a in h.real_row("reg")["expected"]["assertions"] if a["kind"] == h.K_TO_RUN_LATER)


def _out(tmp_path, name: str, probe: str):
    """The regression gold output with only the to-run-later file replaced by the probe *probe*."""
    row = h.real_row("reg")
    return h.output_with(row, tmp_path / name, {h.TO_RUN_LATER: LATER / probe})


def test_live_to_run_later_entry_in_own_words_passes(tmp_path):
    # covers: TQ-200d-2-i
    # angle: discrimination
    # must_catch: revert the fix
    # must_catch: function name required inside the wrong-version text
    row = h.real_row("reg")
    spec = _spec()
    live = json.loads((LATER / "live_own_words.json").read_text(encoding="utf-8"))
    wrong_versions = [e["wrong_version"] for e in live["to_run_later"]]
    assert len(wrong_versions) == 4 and LIVE_WRONG_VERSION in wrong_versions
    assert not any(KEYWORD in w for w in wrong_versions), "control: no wrong version of the live file names the function"
    # every entry's test id names the function; the prose never does, and the check still passes
    record = h.expect_passes(row, tmp_path / "live", _out(tmp_path, "live", "live_own_words.json"))
    assert p.assertion(record, h.K_TO_RUN_LATER)["passed"] is True
    # a file whose only entry names neither the function nor retry_due in its prose passes too (no any-of keyword list)
    record = h.expect_passes(row, tmp_path / "select_true", _out(tmp_path, "select_true", "live_select_true_only.json"))
    assert p.assertion(record, h.K_TO_RUN_LATER)["passed"] is True
    # the row spec no longer carries the keyword key (its only user was the prose check)
    assert "wrong_version_contains" not in spec, f"the key is removed from row 1 of sets/sql-test-writer.jsonl: {spec}"
    assert spec["ac_id"] == "TQ-9501" and spec["contains"] == KEYWORD, spec


def test_to_run_later_entries_that_must_not_count(tmp_path):
    # covers: TQ-200d-2-i
    # angle: discrimination
    # must_catch: test-id function check dropped with the prose check
    # must_catch: blank wrong version counted
    # must_catch: entry without a '::' test id counted
    # must_catch: ac_id not checked
    # must_catch: failing detail omits the uncovered function
    row = h.real_row("reg")
    h.expect_passes(row, tmp_path / "control", _out(tmp_path, "control", "live_own_words.json"))  # the same file shape, one thing right
    cases = [
        ("wrong_function.json", (KEYWORD,)),  # the test id names another function; the wrong version is non-empty prose
        ("function_only_in_prose.json", (KEYWORD,)),  # the function is named in the prose, not in the test id
        ("empty_wrong_version.json", (KEYWORD,)),
        ("whitespace_wrong_version.json", (KEYWORD,)),
        ("null_wrong_version.json", (KEYWORD,)),  # str(None) is not a wrong version
        ("no_node_id.json", (KEYWORD,)),  # the test names the file, no ``::`` test id
        ("other_ac_id.json", ("TQ-9999", "TQ-9501")),
    ]
    for probe, words in cases:
        name = probe.removesuffix(".json")
        h.expect_fails_only(row, tmp_path / name, _out(tmp_path, name, probe), h.K_TO_RUN_LATER, *words)
    # a file written for another AC (no TQ-9501.json in the output at all) fails as well
    other = _out(tmp_path, "other_file", "other_ac_id.json")
    (other / h.TO_RUN_LATER).rename(other / "leafcutter" / "to-run-later" / "TQ-9999.json")
    h.expect_fails_only(row, tmp_path / "other_file", other, h.K_TO_RUN_LATER, "TQ-9501")


def test_sql_test_writer_gold_still_passes(tmp_path):
    # covers: TQ-200d-2-i
    # angle: reachability
    proc, payload = h.score_gold_cli(tmp_path)
    assert payload is not None, f"stdout={proc.stdout[-500:]} stderr={proc.stderr[-500:]}"
    assert proc.returncode == 0, f"stdout={proc.stdout[-600:]} stderr={proc.stderr[-600:]}"
    rows = {r["id"]: r for r in payload["rows"]}
    assert sorted(rows) == sorted(h.ROW_IDS.values())
    assert [i for i, r in rows.items() if not r["score"]["passed"]] == []
    reg = {a["kind"]: a for a in rows[h.ROW_IDS["reg"]]["score"]["assertions"]}
    assert reg[h.K_TO_RUN_LATER]["passed"] is True, reg[h.K_TO_RUN_LATER]
    assert "wrong_version_contains" not in _spec(), "the row spec change is wired into the set the CLI replays"


def test_reference_entry_examples_score_as_stated_and_template_line_unchanged(tmp_path):
    # covers: TQ-200d-2-i
    # angle: real_artifact
    entry = p.entry_of(h.K_TO_RUN_LATER)
    text = p.text_of(entry)
    for phrase in (LIVE_WRONG_VERSION, "test id", "non-empty", "ac_id"):
        assert phrase in text, f"the {h.K_TO_RUN_LATER} entry must state {phrase!r}"
    assert "wrong_version_contains" not in text, "the entry no longer describes the removed spec key"
    passing, failing = p.probe_files(entry, "Passing example"), p.probe_files(entry, "Failing example")
    assert any(f.endswith("/live_own_words.json") for f in passing), f"the live entry is the passing example: {passing}"
    assert any(f.endswith("/wrong_function.json") for f in failing), f"the wrong-function file is the failing example: {failing}"
    row = h.real_row("reg")
    for verdict, files in ((True, passing), (False, failing)):
        for n, named in enumerate(files):
            assert named.endswith(".json"), f"a to-run-later example is a .json file: {named}"
            out = h.output_with(row, tmp_path / f"{verdict}{n}", {h.TO_RUN_LATER: p.REPO_ROOT / named})
            record = h.score(row, out, tmp_path / f"{verdict}{n}" / "work")
            assert p.assertion(record, h.K_TO_RUN_LATER)["passed"] is verdict, f"{named} must {'pass' if verdict else 'fail'} as the entry says"
    template = ref.norm((p.REPO_ROOT / "templates/agents/sql-test-writer.md").read_text(encoding="utf-8"))
    assert "the wrong version in your own words" in template
    assert any("in your own words" in quote for quote, _path in ref.quotes_of(entry)), "the entry quotes the template line"


def test_review_new_spec_keys_are_in_the_real_rows():
    # covers: TQ-200d-2-i
    # angle: seam
    # must_catch: the empty-window SQL checked without naming the view
    # must_catch: the to-run-later row still carrying the removed wrong_version_contains key
    """Moved here from test_tq200d2_review.py: that test pinned ``wrong_version_contains == fn_refresh_due`` on row 1,
    the rule this AC removes. The view half is unchanged; the key half now says the key is gone."""
    empty = next(a for a in h.real_row("empty")["expected"]["assertions"] if a["kind"] == h.K_COUNTS)
    assert empty.get("view") == "buy_volume_window", empty
    spec = _spec()
    assert spec.get("wrong_version_contains") is None, spec
    assert spec.get("ac_id") == h.AC_IDS["reg"] and spec.get("contains") == KEYWORD
    gold_path = h.gold_dir(h.real_row("reg")) / h.TO_RUN_LATER
    gold = json.loads(gold_path.read_text(encoding="utf-8"))["to_run_later"][0]
    assert KEYWORD in gold["wrong_version"] and "::" in gold["test"]
