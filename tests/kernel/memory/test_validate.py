"""
MODULE: tests.kernel.memory.test_validate
GOAL: Store validation: the committed JSON Schema matches the model, and a store is refused for a
    bad schema, a duplicate id, a mismatched file name, an unresolved or inconsistent link, a
    filter outside the existing vocabularies, a non-human approver, a stale or missing index and
    constructs outside the plain-YAML subset.
BUSINESS CONTEXT: "Validated at commit" (ADR-059) is enforced through this code, run by
    `python -m kernel decisions validate`, by the committed-store test and by CI, because a new
    pre-commit hook is package surface. Every rule must therefore fail on a bad store.
ARCHITECTURE: A temporary repository (real schema and vocabularies copied from the checkout) with
    records written by the real dumper and then damaged one rule at a time.
"""

from __future__ import annotations

import yaml

from kernel.memory.index import INDEX_NAME
from kernel.memory.publish import rebuild_index
from kernel.memory.validate import render_schema, validate_store
from tests.kernel.memory.support import (
    CHECKOUT,
    StoreCase,
    make_record,
    schema,
    vocabulary,
)

FIRST_ID = "dec-0123456789abcdef"
SECOND_ID = "dec-1111111111111111"


def messages(report) -> str:  # noqa: ANN001
    """Return every problem of a report as one searchable text."""
    return " | ".join(f"{p.file}: {p.message}" for p in report.problems)


class TestSchemaFile(StoreCase):
    """The committed schema is the model's schema."""

    def test_the_committed_schema_is_generated_from_the_model(self) -> None:
        committed = (CHECKOUT / "config" / "decision_record.schema.json").read_text(
            encoding="utf-8")
        self.assertEqual(committed.replace("\r\n", "\n"), render_schema())

    def test_the_schema_is_in_the_config_folder_next_to_the_kernel_schema(self) -> None:
        self.assertTrue((CHECKOUT / "config" / "kernel_config.schema.json").is_file())


class TestValidStore(StoreCase):
    """A good store passes, and so does an empty one."""

    def validate(self):  # noqa: ANN202
        return validate_store(self.folder, schema=schema(), vocab=vocabulary())

    def test_an_absent_store_is_valid(self) -> None:
        self.assertTrue(self.validate().ok)

    def test_a_record_with_a_current_index_is_valid(self) -> None:
        self.write_record(make_record())
        rebuild_index(self.folder, schema(), vocabulary())
        report = self.validate()
        self.assertTrue(report.ok, messages(report))
        self.assertEqual(list(report.records), [FIRST_ID])


class TestRefusals(StoreCase):
    """One bad store per rule."""

    def validate(self, **kw):  # noqa: ANN003, ANN202
        return validate_store(self.folder, schema=schema(), vocab=vocabulary(), **kw)

    def indexed(self, *records) -> None:  # noqa: ANN002
        for record in records:
            self.write_record(record)
        rebuild_index(self.folder, schema(), vocabulary())

    def test_a_missing_index_is_reported(self) -> None:
        self.write_record(make_record())
        self.assertIn("index.json is missing", messages(self.validate()))

    def test_a_stale_index_is_reported(self) -> None:
        self.indexed(make_record())
        self.write_record(make_record(id=SECOND_ID))
        self.assertIn("out of date", messages(self.validate()))

    def test_an_index_with_crlf_endings_is_still_current(self) -> None:
        self.indexed(make_record())
        path = self.folder / INDEX_NAME
        path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
        self.assertTrue(self.validate().ok)

    def test_a_schema_violation_is_reported_with_its_path(self) -> None:
        # covers: DK-300d-2
        path = self.write_record(make_record())
        broken = yaml.safe_load(path.read_text(encoding="utf-8"))
        broken["approval"]["approved_by"] = "host:fake"
        path.write_text(yaml.safe_dump(broken, sort_keys=False), encoding="utf-8")
        self.assertIn("approval/approved_by", messages(self.validate(check_index=False)))

    def test_an_unparseable_file_is_reported(self) -> None:
        self.folder.mkdir(parents=True)
        (self.folder / "dec-aaaaaaaaaaaaaaaa.yaml").write_text("a: [unclosed\n", encoding="utf-8")
        self.assertIn("not valid YAML", messages(self.validate(check_index=False)))

    def test_a_file_name_that_is_not_the_id_is_reported(self) -> None:
        path = self.write_record(make_record())
        path.rename(self.folder / "dec-ffffffffffffffff.yaml")
        self.assertIn(f"file name must be {FIRST_ID}.yaml",
                      messages(self.validate(check_index=False)))

    def test_a_duplicate_id_is_reported(self) -> None:
        path = self.write_record(make_record())
        (self.folder / "dec-aaaaaaaaaaaaaaaa.yaml").write_text(
            path.read_text(encoding="utf-8"), encoding="utf-8")
        self.assertIn("duplicate record id", messages(self.validate(check_index=False)))

    def test_a_link_to_a_missing_record_is_reported(self) -> None:
        # covers: DK-300d-2
        self.indexed(make_record(related=[SECOND_ID]))
        self.assertIn(f"related target {SECOND_ID} does not exist", messages(self.validate()))

    def test_superseded_by_must_be_mirrored_by_supersedes(self) -> None:
        self.indexed(make_record(superseded_by=[SECOND_ID]), make_record(id=SECOND_ID))
        self.assertIn("does not list", messages(self.validate()))
        self.indexed(make_record(superseded_by=[SECOND_ID]),
                     make_record(id=SECOND_ID, supersedes=[FIRST_ID]))
        self.assertTrue(self.validate().ok, messages(self.validate()))

    def test_a_filter_outside_the_vocabularies_is_reported(self) -> None:
        # covers: DK-300d-2
        for field, value in (("components", "not_a_component"), ("change_target", "magic"),
                             ("risk_surface", "vibes"), ("roadmap_phase", "phase_nine"),
                             ("file_globs", "**/*.cobol")):
            self.write_record(make_record(**{field: [value]}))
            found = messages(self.validate(check_index=False))
            self.assertIn(f"{field} value {value!r} is not in the existing vocabulary", found)

    def test_a_file_glob_from_the_rule_files_is_accepted(self) -> None:
        self.write_record(make_record(file_globs=["*.py"]))
        self.assertNotIn("file_globs", messages(self.validate(check_index=False)))

    def test_constructs_outside_the_plain_subset_are_reported(self) -> None:
        path = self.write_record(make_record())
        path.write_text(path.read_text(encoding="utf-8") + "extra_anchor: &a 1\n",
                        encoding="utf-8")
        self.assertIn("anchor", messages(self.validate(check_index=False)))


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Each validation rule has a store that breaks only that rule, so a
#   rule cannot be removed without a test failing; this suite is what "validated at commit"
#   means in a repository with no new pre-commit hook. (#KernelDecisionStore)
# ====================================================================
