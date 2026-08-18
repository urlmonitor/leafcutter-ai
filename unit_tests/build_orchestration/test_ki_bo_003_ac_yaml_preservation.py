"""
MODULE: unit_tests/build_orchestration/test_ki_bo_003_ac_yaml_preservation.py
GOAL: RED test stubs pinning the CORRECT contract for
    scripts/build_orchestration/fast_lane.py::_update_ac_work_status
    (KI-BO-003, docs/known-issues/build-orchestration.md).

BUSINESS CONTEXT: _update_ac_work_status changes ONE field (work_status) of an
    acceptance-criterion YAML file, but it does so by round-tripping the whole
    document through yaml.safe_load -> yaml.safe_dump. That rewrite:
      - alphabetises every top-level key, destroying the authored field order
      - reflows hand-authored block scalars (criteria: |, notes: |) into
        folded/quoted strings
      - drops comments
    Real evidence: TKT-600a-1.yaml changed 161 lines in commit 19eca859a for
    what is semantically `work_status: todo -> done`. The docstring's claim
    that "every other field is preserved unchanged" is true of VALUES and
    false of FORMATTING. A 161-line diff on a requirements file hides real
    changes in reformatting noise -- this is a review-integrity defect, not a
    cosmetic one. The function is shared: BOTH claim_build_set and
    mark_done_built_acs route through it, so it fires twice per fast-lane run
    per AC.

    These tests pin the CORRECT contract: after a work_status-only update,
    the file's content must differ from the original by EXACTLY the
    work_status line -- captured as a literal before/after diff, not merely
    "the values still parse equal" (the existing sibling suite,
    test_bo2400f_lifecycle.py, only asserts value equality field-by-field via
    yaml.safe_load, which is exactly the assertion style blind to this
    defect). They are RED against the current yaml.safe_dump round-trip
    implementation and must go GREEN only once python-coder replaces it with
    a targeted, format-preserving edit.

FIXTURE-AUTHENTICITY MANDATE: the base fixtures are copied byte-for-byte from
    real, on-disk, PO-reviewed AC YAML files in
    docs/acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/ --
    never hand-typed. A hand-typed fixture reproduces the test author's
    mental model of "what YAML looks like" (e.g. indentation choices,
    quoting style) and would hide exactly the kind of formatting bug this
    defect is about (project CLAUDE.md "Real-artifact behavioral spot-check";
    feedback_spotcheck_real_data_format). The two edge-case-formatting tests
    below (unusual spacing / quoted value) necessarily construct a
    deliberate edge case -- these still start from the real fixture's bytes
    and edit only the single work_status line under test, never fabricating
    the surrounding document.

Run with AC_ENFORCE_STRICT=1 to see the true (unmasked) result -- this repo's
pytest_ac_enforcement plugin otherwise xfails not-yet-done ACs:

    AC_ENFORCE_STRICT=1 python3 -m pytest \
        unit_tests/build_orchestration/test_ki_bo_003_ac_yaml_preservation.py -v
"""

from __future__ import annotations

import difflib
import inspect
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Repo path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_MODULE_DIR = _REPO_ROOT / "scripts" / "build_orchestration"
if str(_MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(_MODULE_DIR))

_AC_STORE_DIR = (
    _REPO_ROOT
    / "docs"
    / "acceptance-criteria"
    / "build-orchestration"
    / "BO-2400-fast-lane-build"
)

# Primary fixture: has an authored key order, a `criteria: |` block scalar, a
# `notes: |` block scalar, and a non-empty `amended_by` list -- exactly the
# shapes the round-trip defect corrupts.
_AC_FIXTURE_SOURCE = _AC_STORE_DIR / "BO-2400a-3-i.yaml"

# Secondary fixture: has an inline trailing comment on `child_limit_override`,
# used for the comment-survival test (the primary fixture has no comments).
_AC_FIXTURE_SOURCE_WITH_COMMENT = _AC_STORE_DIR / "BO-2400a.yaml"

# ---------------------------------------------------------------------------
# Import the production function under test.
# This module/function already exists, so an ImportError here would itself be
# a (different) defect -- but we still guard it the same way the sibling
# lifecycle suite does, for a clear failure message either way.
# ---------------------------------------------------------------------------

_IMPORT_OK = False
_IMPORT_ERR = ""
_update_ac_work_status = None  # type: ignore[assignment]

try:
    from fast_lane import _update_ac_work_status  # type: ignore[no-redef]
    _IMPORT_OK = True
except (ImportError, AttributeError) as _exc:
    _IMPORT_ERR = str(_exc)


def _require_impl(test_case: unittest.TestCase) -> None:
    """Fail with a descriptive message when _update_ac_work_status is not importable."""
    if not _IMPORT_OK:
        test_case.fail(
            "_update_ac_work_status not importable from fast_lane. "
            f"Import error: {_IMPORT_ERR}"
        )


def _diff_lines(before: str, after: str) -> list[str]:
    """Return only the +/- changed lines of a unified diff between before/after.

    Deliberately excludes the '+++'/'---' file-header lines and context lines
    so the count is exactly the number of added + removed content lines.
    """
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    return [
        line
        for line in difflib.unified_diff(before_lines, after_lines, lineterm="")
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    ]


def _extract_block(text: str, key: str) -> str:
    """Extract a `key: |` block scalar (header line + indented/blank body lines)."""
    lines = text.splitlines(keepends=True)
    start = next(i for i, line in enumerate(lines) if line.startswith(f"{key}: |"))
    block = [lines[start]]
    for line in lines[start + 1 :]:
        if line.strip() == "" or line.startswith(" ") or line.startswith("\t"):
            block.append(line)
        else:
            break
    return "".join(block)


def _extract_list_block(text: str, key: str) -> str:
    """Extract a `key:` block-style list (header line + indented/dash body lines)."""
    lines = text.splitlines(keepends=True)
    start = next(i for i, line in enumerate(lines) if line.startswith(f"{key}:"))
    block = [lines[start]]
    for line in lines[start + 1 :]:
        if line.strip() == "" or line.startswith(" ") or line.startswith("-"):
            block.append(line)
        else:
            break
    return "".join(block)


# ---------------------------------------------------------------------------
# Core contract: work_status-only update -> exactly a one-line diff
# ---------------------------------------------------------------------------


class TestUpdateAcWorkStatusPreservesFormatting(unittest.TestCase):
    """KI-BO-003: _update_ac_work_status must change ONLY the work_status
    line's value -- not reorder keys, reflow block scalars, or strip
    comments.

    Fixture: a byte-for-byte copy of the real, PO-reviewed AC YAML
    docs/acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/
    BO-2400a-3-i.yaml.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.fixture_path = self.tmp_path / "BO-2400a-3-i.yaml"
        # Real bytes, not a hand-typed literal (fixture-authenticity mandate).
        self.fixture_path.write_bytes(_AC_FIXTURE_SOURCE.read_bytes())

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_work_status_value_is_updated(self) -> None:
        # covers: KI-BO-003
        """After the call, work_status parses to the new value on disk."""
        _require_impl(self)

        _update_ac_work_status(self.fixture_path, "todo")

        data = yaml.safe_load(self.fixture_path.read_text(encoding="utf-8"))
        self.assertEqual(
            data["work_status"],
            "todo",
            "work_status must be updated to the new value on disk.",
        )

    def test_diff_is_exactly_one_changed_line(self) -> None:
        # covers: KI-BO-003
        """The strong assertion: before/after content differs on EXACTLY the
        work_status line -- not "the values still parse equal" but a literal
        one-line diff, the way a human reviewer would see it in `git diff`.

        This is the core KI-BO-003 assertion. It is RED today because
        yaml.safe_dump alphabetises keys, reflows block scalars, and drops
        comments -- producing a diff of (per the real incident, TKT-600a-1.yaml
        / commit 19eca859a) 161 changed lines for a semantic one-field change.
        """
        _require_impl(self)
        before = self.fixture_path.read_text(encoding="utf-8")

        _update_ac_work_status(self.fixture_path, "todo")

        after = self.fixture_path.read_text(encoding="utf-8")
        diff = _diff_lines(before, after)

        self.assertEqual(
            len(diff),
            2,
            "Changing only work_status must produce exactly one removed line "
            "and one added line (a unified diff of a single changed line) -- "
            "not a full-document reformat (KI-BO-003). "
            f"Got a {len(diff)}-line diff:\n" + "\n".join(diff),
        )
        self.assertTrue(
            all("work_status" in line for line in diff),
            "The only changed line(s) must be the work_status line -- every "
            "other byte of the file must be unchanged (KI-BO-003). "
            "Diff:\n" + "\n".join(diff),
        )

    def test_authored_key_order_preserved(self) -> None:
        # covers: KI-BO-003
        """Top-level key order in the file must match the authored order --
        never alphabetised by yaml.safe_dump.
        """
        _require_impl(self)
        before_text = self.fixture_path.read_text(encoding="utf-8")
        before_keys = list(yaml.safe_load(before_text).keys())

        _update_ac_work_status(self.fixture_path, "in_progress")

        after_text = self.fixture_path.read_text(encoding="utf-8")
        after_keys = list(yaml.safe_load(after_text).keys())

        self.assertEqual(
            after_keys,
            before_keys,
            "Top-level key order must be unchanged after a work_status-only "
            "update (KI-BO-003 -- yaml.safe_dump alphabetises keys). "
            f"Before: {before_keys}\nAfter: {after_keys}",
        )

    def test_block_scalars_survive_byte_identically(self) -> None:
        # covers: KI-BO-003
        """The `criteria: |` and `notes: |` block scalars -- including their
        indentation and internal blank lines -- must be byte-identical after
        the update, never reflowed into a folded or quoted scalar.
        """
        _require_impl(self)
        before_text = self.fixture_path.read_text(encoding="utf-8")

        before_criteria = _extract_block(before_text, "criteria")
        before_notes = _extract_block(before_text, "notes")
        self.assertTrue(before_criteria, "Fixture must have a criteria: | block to test against.")
        self.assertTrue(before_notes, "Fixture must have a notes: | block to test against.")

        _update_ac_work_status(self.fixture_path, "in_progress")

        after_text = self.fixture_path.read_text(encoding="utf-8")
        after_criteria = _extract_block(after_text, "criteria")
        after_notes = _extract_block(after_text, "notes")

        self.assertEqual(
            after_criteria,
            before_criteria,
            "The criteria: | block scalar must survive byte-identically "
            "(KI-BO-003 -- yaml.safe_dump reflows block scalars into "
            "folded/quoted strings).\n"
            f"Before:\n{before_criteria}\nAfter:\n{after_criteria}",
        )
        self.assertEqual(
            after_notes,
            before_notes,
            "The notes: | block scalar must survive byte-identically "
            f"(KI-BO-003).\nBefore:\n{before_notes}\nAfter:\n{after_notes}",
        )

    def test_amended_by_list_survives_byte_identically(self) -> None:
        # covers: KI-BO-003
        """The amended_by list (a list of dicts holding a long, hand-authored
        `reason` string) must be byte-identical after the update.
        """
        _require_impl(self)
        before_text = self.fixture_path.read_text(encoding="utf-8")
        before_data = yaml.safe_load(before_text)
        self.assertTrue(
            before_data.get("amended_by"),
            "Fixture must have a non-empty amended_by list to test against.",
        )
        before_block = _extract_list_block(before_text, "amended_by")

        _update_ac_work_status(self.fixture_path, "in_progress")

        after_text = self.fixture_path.read_text(encoding="utf-8")
        after_block = _extract_list_block(after_text, "amended_by")

        self.assertEqual(
            after_block,
            before_block,
            "The amended_by list block must survive byte-identically "
            f"(KI-BO-003).\nBefore:\n{before_block}\nAfter:\n{after_block}",
        )

    def test_round_trip_twice_still_one_line_diff(self) -> None:
        # covers: KI-BO-003
        """Round-tripping twice (todo -> in_progress -> done, mirroring
        claim_build_set then mark_done_built_acs -- both of which route
        through _update_ac_work_status) must still leave the file only a
        single line different from the original todo state.

        This pins the "fires twice per AC per run" sharing concern from
        KI-BO-003: two sequential calls must not compound formatting damage
        or leave a two-line diff from re-touching the same line twice.
        """
        _require_impl(self)
        # Normalize the starting state to todo (the fixture's real on-disk
        # value is `done`; only this one field is adjusted before the test
        # begins, everything else stays the real fixture bytes).
        original = self.fixture_path.read_text(encoding="utf-8")
        todo_baseline = original.replace("work_status: done", "work_status: todo", 1)
        self.assertNotEqual(
            todo_baseline,
            original,
            "Test setup sanity check: expected to find 'work_status: done' "
            "in the fixture to rewrite to the todo baseline.",
        )
        self.fixture_path.write_text(todo_baseline, encoding="utf-8")

        # Claim: todo -> in_progress.
        _update_ac_work_status(self.fixture_path, "in_progress")
        # Mark-done: in_progress -> done.
        _update_ac_work_status(self.fixture_path, "done")

        final = self.fixture_path.read_text(encoding="utf-8")
        diff = _diff_lines(todo_baseline, final)

        self.assertEqual(
            len(diff),
            2,
            "Two sequential work_status updates (claim then mark-done) must "
            "still produce exactly a one-line diff relative to the original "
            "todo state (KI-BO-003). "
            f"Got a {len(diff)}-line diff:\n" + "\n".join(diff),
        )
        final_data = yaml.safe_load(final)
        self.assertEqual(
            final_data["work_status"],
            "done",
            "After claim then mark-done, work_status must be done on disk.",
        )


# ---------------------------------------------------------------------------
# Comment survival
# ---------------------------------------------------------------------------


class TestUpdateAcWorkStatusPreservesComments(unittest.TestCase):
    """KI-BO-003: comments in the YAML must survive the update.

    Fixture: a byte-for-byte copy of the real, PO-reviewed AC YAML
    docs/acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/
    BO-2400a.yaml, which carries an inline trailing comment on
    `child_limit_override`.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self.fixture_path = self.tmp_path / "BO-2400a.yaml"
        self.fixture_path.write_bytes(_AC_FIXTURE_SOURCE_WITH_COMMENT.read_bytes())

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_inline_comment_survives(self) -> None:
        # covers: KI-BO-003
        """The inline trailing comment on child_limit_override must survive
        verbatim after a work_status-only update (KI-BO-003 -- yaml.safe_dump
        drops comments entirely, since PyYAML's safe_load/safe_dump round-trip
        carries no comment tokens).
        """
        _require_impl(self)
        before_text = self.fixture_path.read_text(encoding="utf-8")
        comment_lines_before = [
            line for line in before_text.splitlines() if "child_limit_override" in line
        ]
        self.assertEqual(
            len(comment_lines_before),
            1,
            "Fixture must have exactly one child_limit_override line with an "
            "inline comment to test against.",
        )
        self.assertIn(
            "#",
            comment_lines_before[0],
            "Fixture's child_limit_override line must carry an inline comment.",
        )

        _update_ac_work_status(self.fixture_path, "in_progress")

        after_text = self.fixture_path.read_text(encoding="utf-8")
        comment_lines_after = [
            line for line in after_text.splitlines() if "child_limit_override" in line
        ]

        self.assertEqual(
            comment_lines_after,
            comment_lines_before,
            "The child_limit_override line, including its inline comment, "
            "must be byte-identical after a work_status-only update "
            "(KI-BO-003 -- yaml.safe_dump drops comments). "
            f"Before: {comment_lines_before!r}\nAfter: {comment_lines_after!r}",
        )


# ---------------------------------------------------------------------------
# Unusual-but-valid spacing / quoted work_status value
# ---------------------------------------------------------------------------


class TestUpdateAcWorkStatusHandlesEdgeCaseFormatting(unittest.TestCase):
    """KI-BO-003 (robustness clause): the update must still work correctly
    when the work_status line has unusual-but-valid spacing, or when the
    value is quoted.

    These two fixtures necessarily construct a deliberate edge case (real
    files in the store do not naturally vary work_status's spacing/quoting),
    but they still start from the real BO-2400a-3-i.yaml bytes and edit ONLY
    the single work_status line under test -- the surrounding document
    (criteria/notes blocks, amended_by list, key order) is untouched real
    content, so the formatting-preservation assertions remain meaningful.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)
        self._real_bytes = _AC_FIXTURE_SOURCE.read_bytes().decode("utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _write_variant(self, name: str, replacement_line: str) -> Path:
        content = self._real_bytes.replace(
            "work_status: done", replacement_line, 1
        )
        self.assertNotEqual(
            content,
            self._real_bytes,
            "Test setup sanity check: expected to find 'work_status: done' "
            "in the real fixture to rewrite for this edge case.",
        )
        path = self.tmp_path / name
        path.write_text(content, encoding="utf-8")
        return path

    def test_unusual_spacing_around_colon_still_updates_correctly(self) -> None:
        # covers: KI-BO-003
        """A work_status line with extra spaces after the colon (still valid
        YAML) must still be found and updated correctly, without corrupting
        the rest of the file.
        """
        _require_impl(self)
        path = self._write_variant("unusual_spacing.yaml", "work_status:    done")
        before = path.read_text(encoding="utf-8")

        _update_ac_work_status(path, "todo")

        after = path.read_text(encoding="utf-8")
        data = yaml.safe_load(after)
        self.assertEqual(
            data["work_status"],
            "todo",
            "work_status must be updated correctly even with unusual-but-valid "
            "spacing around the colon (KI-BO-003 robustness clause).",
        )
        diff = _diff_lines(before, after)
        self.assertEqual(
            len(diff),
            2,
            "Only the work_status line may change, even when its original "
            "spacing was unusual (KI-BO-003). "
            f"Got a {len(diff)}-line diff:\n" + "\n".join(diff),
        )

    def test_quoted_work_status_value_still_updates_correctly(self) -> None:
        # covers: KI-BO-003
        """A work_status line whose value is quoted (e.g. work_status: "done")
        must still be found and updated correctly.
        """
        _require_impl(self)
        path = self._write_variant("quoted_value.yaml", 'work_status: "done"')
        before = path.read_text(encoding="utf-8")

        _update_ac_work_status(path, "todo")

        after = path.read_text(encoding="utf-8")
        data = yaml.safe_load(after)
        self.assertEqual(
            data["work_status"],
            "todo",
            "work_status must be updated correctly even when the original "
            "value was quoted (KI-BO-003 robustness clause).",
        )
        diff = _diff_lines(before, after)
        self.assertEqual(
            len(diff),
            2,
            "Only the work_status line may change, even when its original "
            "value was quoted (KI-BO-003). "
            f"Got a {len(diff)}-line diff:\n" + "\n".join(diff),
        )


# ---------------------------------------------------------------------------
# Docstring honesty guard
# ---------------------------------------------------------------------------


class TestWorkStatusKeyAbsent(unittest.TestCase):
    """An AC with no work_status key must gain one, not crash the lane.

    143 of the 3012 real AC files in this repo's store carry no
    `work_status:` key at all — they are `status: active` records authored
    by /quick-fix (ACD-1400 and siblings). The pre-KI-BO-003 round-trip
    implementation added the key silently, so claiming one of them worked.

    A targeted line edit that RAISES when the key is absent would turn that
    working path into a crash on 4.7% of the store. Adding the key is not a
    guess: the function's whole contract is "work_status is now <value>",
    and there is exactly one way to satisfy it when the line is missing.

    The >1-match case is different and must still raise — there the correct
    line genuinely is ambiguous.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _fixture_without_work_status(self) -> Path:
        """A REAL store AC that genuinely has no work_status key."""
        source = (
            _REPO_ROOT
            / "docs"
            / "acceptance-criteria"
            / "ac-driven-dev"
            / "ACD-1400.yaml"
        )
        self.assertTrue(
            source.exists(),
            f"Fixture must be a real store AC; {source} is missing.",
        )
        text = source.read_text(encoding="utf-8")
        self.assertNotIn(
            "\nwork_status:",
            "\n" + text,
            "Fixture must genuinely lack a column-0 work_status key — if this "
            "AC gained one, pick another from the 143 that have none.",
        )
        target = self.tmp_path / source.name
        target.write_bytes(source.read_bytes())
        return target

    def test_absent_work_status_is_added_not_raised(self) -> None:
        # covers: KI-BO-003
        """The key is created, and the call does not raise."""
        fixture = self._fixture_without_work_status()

        _update_ac_work_status(fixture, "in_progress")

        data = yaml.safe_load(fixture.read_text(encoding="utf-8"))
        self.assertEqual(
            data.get("work_status"),
            "in_progress",
            "An AC lacking work_status must gain it. Raising instead would "
            "crash the fast lane on the 143 real store records that have no "
            "such key (e.g. ACD-1400).",
        )

    def test_adding_the_key_changes_exactly_one_line(self) -> None:
        # covers: KI-BO-003
        """Creating the key is still a minimal, formatting-preserving edit."""
        fixture = self._fixture_without_work_status()
        before = fixture.read_text(encoding="utf-8")

        _update_ac_work_status(fixture, "done")

        after = fixture.read_text(encoding="utf-8")
        diff = _diff_lines(before, after)
        self.assertEqual(
            len(diff),
            1,
            "Adding an absent work_status must be a single added line, with "
            f"nothing else reformatted. Got a {len(diff)}-line diff:\n"
            + "\n".join(diff),
        )

    def test_every_other_byte_survives_when_the_key_is_added(self) -> None:
        # covers: KI-BO-003
        """The rest of the real record is untouched by the insertion."""
        fixture = self._fixture_without_work_status()
        before = fixture.read_text(encoding="utf-8")

        _update_ac_work_status(fixture, "todo")

        after = fixture.read_text(encoding="utf-8")
        for line in before.splitlines():
            self.assertIn(
                line,
                after.splitlines(),
                "Every pre-existing line must survive the insertion "
                f"byte-identically. Lost: {line!r}",
            )

    def test_ambiguous_multiple_matches_still_raise(self) -> None:
        # covers: KI-BO-003
        """Two column-0 work_status lines remain a hard error.

        Adding a missing key is unambiguous; choosing between two existing
        ones is not. The permissive case must not soften this one.
        """
        fixture = self.tmp_path / "two_keys.yaml"
        fixture.write_text(
            "id: X-1\nwork_status: todo\ntitle: t\nwork_status: done\n",
            encoding="utf-8",
        )

        with self.assertRaises(ValueError):
            _update_ac_work_status(fixture, "in_progress")


class TestDocstringHonesty(unittest.TestCase):
    """Guards against re-introducing the KI-BO-003 docstring dishonesty: the
    docstring's preservation claim must match what is actually tested and
    guaranteed -- byte/formatting preservation, not just value equality.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_docstring_claims_the_tested_preservation_guarantee(self) -> None:
        # covers: KI-BO-003
        """Whatever the final implementation, the docstring's preservation
        claim must be the ACTUALLY tested one.

        This is RED today for two independent reasons, either of which must
        fail this test:
        1. The current docstring says "every other field is preserved
           unchanged" without naming formatting / byte-identity / comments /
           key order -- the exact overclaim KI-BO-003 flags (true of VALUES,
           false of FORMATTING).
        2. Even if the docstring wording were changed without fixing the
           implementation, the round-trip check below would still catch it:
           a docstring cannot go green by rewording alone.
        """
        if not _IMPORT_OK:
            self.fail(
                "_update_ac_work_status not importable from fast_lane. "
                f"Import error: {_IMPORT_ERR}"
            )
        import fast_lane  # local import: safe once _IMPORT_OK is True

        doc = inspect.getdoc(fast_lane._update_ac_work_status) or ""
        self.assertTrue(
            doc,
            "_update_ac_work_status must have a docstring describing its "
            "preservation guarantee.",
        )

        preservation_keywords = ("byte", "format", "comment", "order")
        self.assertTrue(
            any(keyword in doc.lower() for keyword in preservation_keywords),
            "The docstring's preservation claim must name what is actually "
            "guaranteed -- formatting / byte-identity / comments / key order "
            "-- not just 'every other field is preserved unchanged' (true of "
            "VALUES, false of FORMATTING; KI-BO-003). "
            f"Got docstring:\n{doc}",
        )

        # The claim must also be TRUE: this test cannot go green merely by
        # rewording the docstring without fixing the implementation.
        fixture = self.tmp_path / "docstring_check.yaml"
        fixture.write_bytes(_AC_FIXTURE_SOURCE.read_bytes())
        before = fixture.read_text(encoding="utf-8")

        fast_lane._update_ac_work_status(fixture, "todo")

        after = fixture.read_text(encoding="utf-8")
        diff = _diff_lines(before, after)
        self.assertEqual(
            len(diff),
            2,
            "The docstring's preservation claim must be backed by actual "
            "byte-level preservation (a one-line diff), not merely reworded "
            f"language (KI-BO-003). Got a {len(diff)}-line diff:\n"
            + "\n".join(diff),
        )


if __name__ == "__main__":
    unittest.main()
