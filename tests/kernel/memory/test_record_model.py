"""
MODULE: tests.kernel.memory.test_record_model
GOAL: The decision record model and its YAML form: consistency rules, the human-only approval,
    a stable dump that round-trips, the plain-YAML subset lint, and that the stdlib knowledge-map
    parser reads a record exactly as the dumper writes it.
BUSINESS CONTEXT: A record is reviewed as a git diff and read by tools that have no PyYAML; a
    format that only this module can read, or a record that could name a model as its approver,
    would defeat the store (ADR-059, ADR-060).
ARCHITECTURE: Real models and the real dumper; the knowledge-map check feeds the dumper's own
    output (not a hand-typed literal) to scripts/knowledge_frontmatter_reader.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest

from pydantic import ValidationError

from kernel.memory.codec import (
    RecordReadError,
    dump_record,
    parse_yaml_text,
    plain_subset_problems,
)
from kernel.memory.models import DecisionRecord
from tests.kernel.memory.support import CHECKOUT, make_record, record_data


def _reader():  # noqa: ANN202
    """Load the stdlib knowledge-map frontmatter reader by path (it is not a package)."""
    path = CHECKOUT / "scripts" / "knowledge_frontmatter_reader.py"
    spec = importlib.util.spec_from_file_location("kfr_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["kfr_under_test"] = module
    spec.loader.exec_module(module)
    return module


class TestRecordConsistency(unittest.TestCase):
    """The model refuses an inconsistent or unauthorised record."""

    def test_the_fixture_is_valid(self) -> None:
        self.assertEqual(make_record().id, "dec-0123456789abcdef")

    def test_a_non_human_approver_is_refused(self) -> None:
        for actor in ("host:fake", "jev", "kernel", "service:x"):
            data = record_data()
            data["approval"] = {**data["approval"], "approved_by": actor}
            with self.assertRaises(ValidationError, msg=actor):
                DecisionRecord.model_validate(data)

    def test_the_only_approval_status_is_approved(self) -> None:
        data = record_data()
        data["approval"] = {**data["approval"], "approval_status": "proposed"}
        with self.assertRaises(ValidationError):
            DecisionRecord.model_validate(data)

    def test_the_selected_option_must_be_one_of_the_options(self) -> None:
        with self.assertRaises(ValidationError):
            make_record(selected_option_id="opt.missing")

    def test_cited_evidence_must_be_listed(self) -> None:
        data = record_data()
        data["criteria"] = [{**data["criteria"][0], "evidence_ids": ["ev-bbbbbbbbbbbbbbbb"]}]
        with self.assertRaises(ValidationError):
            DecisionRecord.model_validate(data)

    def test_a_record_without_any_filter_is_refused(self) -> None:
        empty = {"components": [], "change_target": [], "risk_surface": [], "roadmap_phase": [],
                 "file_globs": [], "repository_wide": False}
        with self.assertRaises(ValidationError):
            make_record(**empty)
        self.assertTrue(make_record(**{**empty, "repository_wide": True}).repository_wide)

    def test_a_record_cannot_supersede_itself(self) -> None:
        with self.assertRaises(ValidationError):
            make_record(supersedes=["dec-0123456789abcdef"])

    def test_a_bad_link_id_is_refused(self) -> None:
        with self.assertRaises(ValidationError):
            make_record(related=["ADR-056"])

    def test_unknown_fields_are_refused(self) -> None:
        with self.assertRaises(ValidationError):
            make_record(surprise="x")


class TestYamlForm(unittest.TestCase):
    """The dump is stable, indented, readable by PyYAML and by the stdlib parser."""

    def test_the_dump_round_trips_to_the_same_record(self) -> None:
        record = make_record()
        again = DecisionRecord.model_validate(parse_yaml_text(dump_record(record), "x"))
        self.assertEqual(again, record)
        self.assertEqual(dump_record(again), dump_record(record))

    def test_timestamps_stay_strings(self) -> None:
        loaded = parse_yaml_text(dump_record(make_record()), "x")
        self.assertIsInstance(loaded["approval"]["approved_at"], str)

    def test_the_dump_is_in_the_plain_subset(self) -> None:
        self.assertEqual(plain_subset_problems(dump_record(make_record())), [])

    def test_the_lint_names_anchors_aliases_tags_and_flow_mappings(self) -> None:
        text = "a: &x 1\nb: *x\nc: !!str d\ne: {f: 1}\n"
        found = " ".join(plain_subset_problems(text))
        for word in ("anchor", "alias", "tag", "flow mapping"):
            self.assertIn(word, found)

    def test_the_lint_names_a_second_document(self) -> None:
        self.assertIn("more than one", " ".join(plain_subset_problems("a: 1\n---\nb: 2\n")))

    def test_a_non_mapping_is_a_read_error(self) -> None:
        with self.assertRaises(RecordReadError):
            parse_yaml_text("- a\n- b\n", "x")

    def test_the_stdlib_parser_reads_id_title_and_filters_from_the_real_dump(self) -> None:
        reader = _reader()
        fields = reader._parse_yaml_file(dump_record(make_record()))
        self.assertEqual(fields["id"], "dec-0123456789abcdef")
        self.assertEqual(fields["title"], "Keep decision records in one YAML file each")
        self.assertEqual(fields["components"], ["decision_kernel"])
        self.assertEqual(fields["roadmap_phase"], ["phase_kernel_1_founding"])
        self.assertIn(fields["repository_wide"], (False, "false"))


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: The knowledge-map check parses the dumper's own output with the
#   real stdlib reader: a hand-typed indented literal would not prove the real file is readable.
#   (#KernelDecisionStore)
# ====================================================================
