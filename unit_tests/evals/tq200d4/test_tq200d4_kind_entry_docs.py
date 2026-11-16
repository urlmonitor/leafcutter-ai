"""
MODULE: unit_tests/evals/tq200d4/test_tq200d4_kind_entry_docs
GOAL: RED tests for the documentation and configuration half of TQ-200d-4-i and TQ-200d-4-iv: the
    reference entry of the new kind ``report_pass_quotes_a_count`` (its examples score as the entry says),
    the declaration of ``testing_context.test_command`` in the skills-config schema, the produced-tests
    lines of scripts/evals/README.md, the test-runner notes of agent_eval_config.json, and the two
    known issues that move to resolved.
Target: docs/reference/produced-tests-eval-assertion-kinds-database-setting.md, config/skills_config.schema.json,
    scripts/evals/README.md, scripts/evals/agent_eval_config.json, docs/known-issues/
Documentation is part of each AC; these read the REAL pages, schema, README and register.
"""

from __future__ import annotations

import json

import jsonschema

import unit_tests.evals.tq200d1ii._helpers as ref
import unit_tests.evals.tq200d2._probes as p
import unit_tests.evals.tq200d4._helpers as h
import unit_tests.evals.tq200d4._review_helpers as r

ROW_ID, COUNT, PYTEST, ntc_row = p.NTC_ROW_ID, p.COUNT_KIND, p.PYTEST_KIND, p.ntc_row
DB_PAGE = ref.FAMILY_PAGE["database-setting"]
RULE_SENTENCE = "Report PASS only when the report quotes a passed-test count greater than zero"
SCHEMA = h.REPO_ROOT / "config" / "skills_config.schema.json"
FIELDS_DOC = h.REPO_ROOT / "docs" / "reference" / "skills-config-fields.md"


def test_new_kind_entry_examples_score_as_stated(tmp_path):
    # covers: TQ-200d-4-iv
    # angle: real_artifact
    pages = ref.read_real_pages()
    homes = [name for name, e in ref.all_entries(pages) if e["kind"] == COUNT]
    assert homes == [DB_PAGE], f"{COUNT} has one entry, on the database-setting page: {homes}"
    entry = p.entry_of(COUNT)
    assert ROW_ID in p.part(entry, "Used by"), "the entry names the trap row it is used by"
    quotes = ref.quotes_of(entry)
    assert any(RULE_SENTENCE in quote and path == "templates/agents/test-runner.md" for quote, path in quotes), f"the entry quotes the PASS rule of the template: {quotes}"
    passing, failing = p.probe_files(entry, "Passing example"), p.probe_files(entry, "Failing example")
    assert any(f.endswith("recorded/no-test-collected/report.md") for f in passing), f"the honest gold report is the passing example: {passing}"
    assert any(f.endswith("probes_ntc/pass_without_count.md") for f in failing), f"the PASS-without-count output is the failing example: {failing}"
    for verdict, files in ((True, passing), (False, failing)):
        for n, named in enumerate(files):
            row = ntc_row()
            base = tmp_path / f"{verdict}{n}"
            out = r.output_with(row, base, report=(p.REPO_ROOT / named).read_text(encoding="utf-8"))
            record = h.score("test-runner", row, out, base / "work")
            assert p.assertion(record, COUNT)["passed"] is verdict, f"{named} must {'pass' if verdict else 'fail'} as the entry says"
    used = p.part(p.entry_of(PYTEST), "Used by")
    assert ROW_ID in used, "the commands_ran_pytest entry names the trap row in its 'Used by'"


def test_schema_declares_testing_context_test_command():
    # covers: TQ-200d-4-iv
    # angle: real_artifact
    # must_catch: test_command not declared in the skills_config schema
    # must_catch: test_command added to the required list
    context = json.loads(SCHEMA.read_text(encoding="utf-8"))["properties"]["testing_context"]
    declared = context["properties"].get("test_command")
    assert declared is not None, "testing_context.test_command must be declared under testing_context.properties"
    assert declared["type"] == "string" and "default" not in declared, declared
    assert "test_command" not in context["required"], "optional: not added to required"
    description = declared["description"].lower()
    assert "test runner" in description or "test-runner" in description, "the description names the test runner as its reader"
    assert "python -m pytest <file>" in declared["description"], "the description names the fallback"
    assert any(ln.startswith("| `testing_context.test_command` |") for ln in FIELDS_DOC.read_text(encoding="utf-8").splitlines()), "skills-config-fields.md has the row"
    fixtures = sorted((h.SETS_DIR / "test-runner" / "projects").glob("*/.claude/skills_config.json"))
    assert len(fixtures) == 4, f"the four test-runner fixture projects: {[str(f) for f in fixtures]}"
    for fixture in fixtures:
        for key, value in json.loads(fixture.read_text(encoding="utf-8"))["testing_context"].items():
            assert key in context["properties"], f"{fixture.parent.parent.name}: testing_context.{key} is not declared"
            jsonschema.validate(value, context["properties"][key])


def test_readme_states_the_address_rule_in_one_linked_line():
    # covers: TQ-200d-4-i
    # angle: real_artifact
    # must_catch: README line missing, or naming the rule without linking the kind's entry
    p.check_readme_line("report_names_no_address", DB_PAGE, "scheme", "host")


def test_readme_states_the_pass_rule_and_names_the_four_rows():
    # covers: TQ-200d-4-iv
    # angle: real_artifact
    # must_catch: README line missing, or naming the rule without linking the kind's entry
    p.check_readme_line(COUNT, DB_PAGE, "passed-test count", "PASS")
    body = ref.section(p.README.read_text(encoding="utf-8"), "Produced-tests mode")
    for row_id in (*h.ROW_IDS.values(), ROW_ID):
        assert row_id in body, f"the produced-tests section names the test-runner row {row_id!r}"
    notes = h.agent_config("test-runner")["notes"]
    assert ROW_ID in notes, "the notes of the test-runner entry in agent_eval_config.json name the new trap row"


def test_checker_message_known_issue_is_resolved():
    # covers: TQ-200d-4-i
    # angle: real_artifact
    # must_catch: the known issue left open or its register row left under Open
    p.ki_resolved("ki-tq-20261025-test-runner-row-fails-on-quoted-checker-message", "TQ-200d-4-i")


def test_test_file_as_script_known_issue_is_resolved():
    # covers: TQ-200d-4-iv
    # angle: real_artifact
    # must_catch: the known issue left open or its register row left under Open
    p.ki_resolved("ki-tq-20261025-test-runner-runs-a-test-file-as-a-script", "TQ-200d-4-ii", "TQ-200d-4-iii", "TQ-200d-4-iv")
