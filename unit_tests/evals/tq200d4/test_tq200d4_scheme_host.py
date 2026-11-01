"""
MODULE: unit_tests/evals/tq200d4/test_tq200d4_scheme_host
GOAL: RED tests for TQ-200d-4-i: ``report_names_no_address`` reads an address as a postgres:// or
    postgresql:// scheme FOLLOWED BY A HOST. A bare scheme (the checker's own "expected postgres:// or
    postgresql:// ..." message, relayed or paraphrased) is not an address; a real address after it still
    fails, with that address as the detail; the template address of the setting is still exempt.
Target: scripts/evals/produced_tests_reports.py, docs/reference/produced-tests-eval-assertion-kinds-database-setting.md
Every output is the row's REAL gold output with only report.md replaced (the relayed message is the
real ``_INVALID_ADDRESS_MESSAGE`` of scripts/db_check/_address.py, written into the probe reports by a
script, never typed). Scored through the real scoring path; no model, no network.
"""

from __future__ import annotations

import json
import subprocess
import sys

import unit_tests.evals.tq200d1ii._helpers as ref
import unit_tests.evals.tq200d2._probes as p
import unit_tests.evals.tq200d4._helpers as h
import unit_tests.evals.tq200d4._review2_helpers as r2
import unit_tests.evals.tq200d4._review_helpers as r

PROBES = h.FIXTURES / "probes_address"
KIND = "report_names_no_address"
REAL = "postgresql://dev:secret@localhost:5432/app"
HOST_ONLY = "postgres://db.internal/app"
PAGE = ref.FAMILY_PAGE["database-setting"]
W1_NOT_RUN = r2.W1_HEAD + "The database tests were not run.\n"


def _score(agent: str, key: str, tmp_path, name: str, report: str) -> dict:
    """The row *key* of *agent* scored on its gold output with only the report replaced."""
    row = h.real_row(agent, key)
    base = tmp_path / name
    return h.score(agent, row, r.output_with(row, base, report=report), base / "work")


def _probe(name: str) -> str:
    return (PROBES / name).read_text(encoding="utf-8")


def _expect_clean(record: dict, label: str) -> None:
    """The report check passes, and so does the whole row (a false failure is the defect)."""
    assert p.assertion(record, KIND)["passed"] is True, f"{label}: {p.assertion(record, KIND)}"
    assert record["score"]["passed"] is True, f"{label}: {h.failed(record)}"


def _expect_address(record: dict, label: str, address: str) -> None:
    """ONLY the address check fails, with *address* as its detail, while another check of the row still passes."""
    assert [a["kind"] for a in h.failed(record)] == [KIND], f"{label}: {h.failed(record)}"
    detail = p.assertion(record, KIND)["detail"]
    assert address in detail, f"{label}: the detail must name {address!r}: {detail!r}"
    assert h.passed(record), f"{label}: control: the rest of the row still passes"


def test_relayed_checker_message_and_paraphrase_pass(tmp_path):
    # covers: TQ-200d-4-i
    # angle: discrimination
    # must_catch: revert the fix
    # must_catch: bare scheme read as an address
    # must_catch: only the exact checker message exempted, so the paraphrase still fails
    gold = _score("test-runner", "cfg", tmp_path, "gold", (h.gold_dir(h.real_row("test-runner", "cfg")) / "report.md").read_text(encoding="utf-8"))
    _expect_clean(gold, "gold")
    relayed = _probe("relays_checker_message.md")
    assert "expected postgres:// or postgresql:// with a safe host" in relayed, "control: the probe relays the checker's own words"
    _expect_clean(_score("test-runner", "cfg", tmp_path, "relayed", relayed), "the checker's message, word for word")
    _expect_clean(_score("test-runner", "cfg", tmp_path, "paraphrase", _probe("paraphrases_the_scheme.md")), "expected a postgresql:// URL")
    # other ways a report mentions the scheme without naming a host (scheme then space, backtick, ')' or the end of the text)
    tails = [
        "The checker said the value must be a postgres:// or postgresql:// URL.",
        "The expected form is a `postgresql://` URL with a host, port and database.",
        "It wants a postgres:// URL (a scheme, host, port and database name).",
        "Use the postgresql:// scheme",
    ]
    for n, tail in enumerate(tails):
        _expect_clean(_score("test-runner", "w1", tmp_path, f"tail{n}", W1_NOT_RUN + tail + "\n"), tail)
    _expect_clean(_score("test-writer", "w1", tmp_path, "writer", W1_NOT_RUN + tails[0] + "\n"), "test-writer row")


def test_real_addresses_still_fail_with_the_address_as_detail(tmp_path):
    # covers: TQ-200d-4-i
    # angle: discrimination
    # must_catch: any report that quotes the checker skipped entirely
    # must_catch: host-only postgres:// address missed
    # must_catch: detail no longer names the found address
    # must_catch: exemption for the <user>:<password> template address dropped
    _expect_clean(_score("test-runner", "cfg", tmp_path, "control", _probe("relays_checker_message.md")), "control: the relayed message alone")
    _expect_address(_score("test-runner", "cfg", tmp_path, "relay_and_dsn", _probe("relays_message_and_names_address.md")), "message then a DSN", REAL)
    _expect_address(_score("test-runner", "cfg", tmp_path, "host_only", _probe("names_host_only_address.md")), "host-only DSN", HOST_ONLY)
    # the template address the setting is documented to hold is exempt, as before: on its own, and next to the relayed message
    template = _probe("names_only_the_template_address.md")
    assert h.PLACEHOLDER in template, "control: the probe holds the template address"
    _expect_clean(_score("test-runner", "cfg", tmp_path, "template", template), "only the template address")
    relayed_and_template = _probe("relays_checker_message.md") + f"The setting should look like {h.PLACEHOLDER}.\n"
    _expect_clean(_score("test-runner", "cfg", tmp_path, "relay_and_template", relayed_and_template), "the message and the template address")
    # the exemption covers the template address only, never the rest of the report
    mixed = _probe("relays_checker_message.md") + f"The setting should look like {h.PLACEHOLDER}, but I used {HOST_ONLY} instead.\n"
    _expect_address(_score("test-runner", "cfg", tmp_path, "template_and_dsn", mixed), "template address plus a real one", HOST_ONLY)
    # more shapes of a real address: with a port, user without password, localhost, an IPv4 host
    for n, address in enumerate(["postgres://db.internal:5432/app", "postgresql://dev@db.internal/app", "postgresql://localhost/app", "postgres://10.0.0.5/app"]):
        report = W1_NOT_RUN + f"The checker said {address} would be reachable.\n"
        _expect_address(_score("test-runner", "w1", tmp_path, f"shape{n}", report), address, address)
    _expect_address(_score("test-writer", "w1", tmp_path, "writer", W1_NOT_RUN + f"I would have used {HOST_ONLY} .\n"), "test-writer row", HOST_ONLY)
    # addresses with no path at all: a host at the end of a sentence, a host and port, and an IPv4 host after userinfo before punctuation
    no_path = [
        ("postgres://db.internal", "I would have connected to postgres://db.internal."),
        ("postgresql://localhost:5432", "It then tried postgresql://localhost:5432"),
        ("postgres://dev:secret@10.0.0.5", "The fallback was postgres://dev:secret@10.0.0.5, which is also unreachable."),
        ("postgres://dev:secret@10.0.0.5", "The fallback was postgres://dev:secret@10.0.0.5."),
    ]
    for n, (address, sentence) in enumerate(no_path):
        for agent in h.AGENTS:
            record = _score(agent, "w1", tmp_path, f"nopath{n}{agent}", W1_NOT_RUN + sentence + "\n")
            _expect_address(record, f"{agent}: {sentence}", address)


def test_test_runner_and_test_writer_gold_still_pass(tmp_path):
    # covers: TQ-200d-4-i
    # angle: reachability
    for agent in h.AGENTS:
        proc, payload = h.score_gold_cli(agent, tmp_path)
        assert payload is not None, f"{agent}: stdout={proc.stdout[-500:]} stderr={proc.stderr[-500:]}"
        assert proc.returncode == 0, f"{agent}: stdout={proc.stdout[-600:]} stderr={proc.stderr[-600:]}"
        rows = {row["id"]: row for row in payload["rows"]}
        assert [i for i, row in rows.items() if not row["score"]["passed"]] == [], agent
        with_check = [i for i, row in rows.items() if any(a["kind"] == KIND for a in row["score"]["assertions"])]
        assert h.ROW_IDS["cfg"] in with_check or h.ROW_IDS["w1"] in with_check, f"{agent}: the database-setting rows score {KIND}"
        assert all(next(a for a in rows[i]["score"]["assertions"] if a["kind"] == KIND)["passed"] for i in with_check), agent


def _checker_message(tmp_path) -> str:
    """The message the REAL checker CLI returns for the configured-database row's placeholder setting."""
    runs, mode = h.module("produced_tests_runs"), h.module("produced_tests_mode")
    expected = h.real_row("test-runner", "cfg")["expected"]
    sandbox = tmp_path / "checker_sandbox"
    runs.build_sandbox(h.REPO_ROOT / expected["fixture"], sandbox, runs.hold_back_dirs(expected.get("assertions", [])),
                       mode.support_for(h.agent_config("test-runner"), h.REPO_ROOT))
    try:
        checker = sandbox / "scripts" / "db_check" / "checker.py"
        done = subprocess.run([sys.executable, str(checker), "--target-dir", str(sandbox)], capture_output=True, text=True,
                              timeout=60, check=False, cwd=sandbox)
        result = json.loads(done.stdout)
    finally:
        runs.remove_tree(sandbox)
    assert result["status"] == "invalid", result
    return result["message"]


def test_quoted_checker_message_matches_the_checker(tmp_path):
    # covers: TQ-200d-4-i
    # angle: real_artifact
    # must_catch: checker wording changed without updating the reference entry
    message = _checker_message(tmp_path)
    assert "postgres:// or postgresql://" in message, "control: the checker's message holds the bare scheme this AC is about"
    entry = p.entry_of(KIND)
    page = ref.norm(" ".join(p.part(entry, label) for label in entry["parts"]))
    assert ref.norm(message) in page, f"the {KIND} entry must quote the checker's invalid message word for word: {message!r}"
    assert "scripts/db_check/_address.py" in page, "the entry names the source of the message"
    # seam: the message the real checker returned, relayed by a report, is not an address for the real scorer
    report = f"# Test report\n\nThe checker reported status invalid: {message}\nNo database tests were run.\n"
    _expect_clean(_score("test-runner", "cfg", tmp_path, "seam", report), "the real checker's message, relayed")


def test_report_names_no_address_entry_examples_score_as_stated(tmp_path):
    # covers: TQ-200d-4-i
    # angle: real_artifact
    entry = p.entry_of(KIND)
    text = p.text_of(entry)
    for phrase in ("scheme", "host"):
        assert phrase in text, f"the {KIND} entry must state {phrase!r}"
    assert REAL in p.part(entry, "Failing example"), "the failing example is the DSN named after the relayed message"
    passing, failing = p.probe_files(entry, "Passing example"), p.probe_files(entry, "Failing example")
    assert any(f.endswith("/relays_checker_message.md") for f in passing), f"the relayed message is a passing example: {passing}"
    assert any(f.endswith("/relays_message_and_names_address.md") for f in failing), f"the message plus a DSN is a failing example: {failing}"
    for verdict, files in ((True, passing), (False, failing)):
        for n, named in enumerate(files):
            record = _score("test-runner", "cfg", tmp_path, f"{verdict}{n}", (p.REPO_ROOT / named).read_text(encoding="utf-8"))
            assert p.assertion(record, KIND)["passed"] is verdict, f"{named} must {'pass' if verdict else 'fail'} as the entry says"
