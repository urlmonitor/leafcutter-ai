"""
MODULE: unit_tests/commit_guardian/test_ge_118d_2.py
COVERS: GE-118d-2 -- "A labelled entry carrying more than one path is refused
    rather than resolved by guesswork"

GOAL: RED test-first stubs for all three test_spec entries on GE-118d-2
    (angles: criterion, failure, boundary). The resolver already refuses a
    two-key mapping (it only accepts len == 1), and validate_paths() reports
    it -- but with the generic "Unsupported entry ... accepted shapes are ..."
    text. The AC requires the refusal to name the ARITY rule ("a labelled entry
    carries exactly one label and one path") and to name the entry, identically
    in all three path fields. Those are the gaps pinned here; the
    must-not-happen arm (neither named path enters the checked set) is a
    regression guard against the register's own KI-CG-008 sketch and against
    taking the first value.

ENTRY POINT: the criterion test drives the real hook
    (`run_hook.py check_doc_frontmatter.py`) as a subprocess. Documents are
    yaml.safe_dump output; every named path exists on disk so path existence
    can never be the reason for a refusal.
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

from ._ge_118d_fixtures import _TEMPLATES_CG_DIR, _init_repo, _run_hook_against_source, _write
from ._ge_118d_refusal_fixtures import doc_text, import_resolver, write_existing_targets

_FIRST = "docs/explanation/architecture.md"
_SECOND = "docs/reference/configuration.md"
_TWO_KEY_ENTRY = {"explanation": _FIRST, "reference": _SECOND}
_FIELDS = ("related_docs", "related_code", "architecture_diagrams")
_ARITY_RULE = re.compile(r"exactly one label and one path", re.IGNORECASE)


def _refusal_line(combined: str, field: str) -> list[str]:
    """Lines naming *field* and showing the two-key entry as parsed."""
    return [ln for ln in combined.splitlines() if field in ln and repr(_TWO_KEY_ENTRY) in ln]


class TestGe118d2ThreeFields(unittest.TestCase):
    """Criterion arm: one rule, three fields, one message."""

    def _run_for_field(self, field: str):
        tmp = tempfile.TemporaryDirectory(prefix=f"ge118d2_{field}_")
        self.addCleanup(tmp.cleanup)
        repo = Path(tmp.name)
        _init_repo(repo)
        write_existing_targets(repo)
        doc_rel = f"docs/ge118d2_{field}_doc.md"
        _write(repo / doc_rel, doc_text({field: [_TWO_KEY_ENTRY]}))
        result = _run_hook_against_source(repo, [doc_rel])
        return result, result.stdout + result.stderr

    def test_ge_118d_2_two_key_mapping_is_refused_identically_in_each_of_the_three_path_fields(
        self,
    ) -> None:
        # covers: GE-118d-2
        # angle: criterion
        """Parameterised over related_docs, related_code and
        architecture_diagrams, both paths in the entry existing on disk. Each
        is refused (non-zero exit, no traceback), the refusal names the entry
        and states the arity rule, and the three messages are identical except
        for the field name -- so no per-field special case exists.

        FAILS TODAY: the refusal text is the generic accepted-shapes sentence;
        it neither shows the entry nor states "exactly one label and one path".
        """
        messages: dict[str, str] = {}
        for field in _FIELDS:
            with self.subTest(field=field):
                result, combined = self._run_for_field(field)
                self.assertNotEqual(0, result.returncode, msg=f"{field} not refused:\n{combined}")
                self.assertNotIn("Traceback", combined, msg=combined)
                lines = _refusal_line(combined, field)
                self.assertEqual(1, len(lines), msg=f"one refusal naming the entry:\n{combined}")
                self.assertRegex(lines[0], _ARITY_RULE)
                messages[field] = lines[0].replace(field, "<FIELD>")
        self.assertEqual(
            len(_FIELDS), len(messages), msg="every field must have produced a message"
        )
        self.assertEqual(
            1,
            len(set(messages.values())),
            msg=f"messages must differ only by field name, got {messages!r}",
        )


class TestGe118d2NeitherValueAccepted(unittest.TestCase):
    """Failure arm: the register's sketch and first-value are both refused."""

    def test_ge_118d_2_neither_the_first_value_nor_every_value_is_accepted_as_a_path(
        self,
    ) -> None:
        # covers: GE-118d-2
        # angle: failure
        """The resolver returns a refusal for the two-key entry AND the set of
        paths validate_paths() went on to check is exactly the one control
        path -- neither named path is in it. Taking the first value, taking
        every value (the KI-CG-008 sketch) and a bare "an error was reported"
        implementation are told apart: the first two put a named path into the
        checked set; the control entry proves the recording is live.

        FAILS TODAY: the arity-rule wording is absent from the refusal the
        guard reports, which this test also requires (the refusal must say WHY,
        not just that the entry was skipped).
        """
        resolver = import_resolver()
        refusal = resolver.resolve_frontmatter_path_entry(_TWO_KEY_ENTRY, "related_docs")
        self.assertIsInstance(refusal, resolver.PathEntryRefusal)

        if str(_TEMPLATES_CG_DIR) not in sys.path:
            sys.path.insert(0, str(_TEMPLATES_CG_DIR))
        from frontmatter_validators import validate_paths

        checked: list[str] = []

        class _RecordingPath(type(Path())):  # type: ignore[misc]
            def __truediv__(self, other):  # noqa: ANN001
                checked.append(str(other))
                return super().__truediv__(other)

        control = "docs/control.md"
        errors = validate_paths(
            {"related_docs": [_TWO_KEY_ENTRY, control]}, _RecordingPath("/nonexistent-root")
        )

        self.assertEqual([control], checked, msg=f"only the control path may be checked: {checked}")
        self.assertNotIn(_FIRST, checked)
        self.assertNotIn(_SECOND, checked)
        refusals = [e for e in errors if "Broken path" not in e]
        self.assertEqual(1, len(refusals), msg=f"exactly one refusal expected: {errors!r}")
        self.assertRegex(refusals[0], _ARITY_RULE)


class TestGe118d2ArityNotExistence(unittest.TestCase):
    """Boundary arm: the refusal names arity, not path existence."""

    def test_ge_118d_2_refusal_names_the_arity_rule_and_not_path_existence(self) -> None:
        # covers: GE-118d-2
        # angle: boundary
        """Both paths exist on disk, so the refusal can only be about arity:
        the message states a labelled entry carries exactly one label and one
        path, and does not claim a broken or missing path. Boundary: a
        one-key mapping naming an existing path is the control and produces no
        error at all, so the arity message is not a blanket refusal of
        mappings.

        FAILS TODAY: the message does not state the arity rule.
        """
        if str(_TEMPLATES_CG_DIR) not in sys.path:
            sys.path.insert(0, str(_TEMPLATES_CG_DIR))
        from frontmatter_validators import validate_paths

        with tempfile.TemporaryDirectory(prefix="ge118d2_arity_") as tmp:
            root = Path(tmp)
            write_existing_targets(root)
            self.assertTrue((root / _FIRST).exists() and (root / _SECOND).exists())

            control_errors = validate_paths({"related_docs": [{"explanation": _FIRST}]}, root)
            self.assertEqual([], control_errors, msg="one label + one path must be accepted")

            errors = validate_paths({"related_docs": [_TWO_KEY_ENTRY]}, root)

        self.assertEqual(1, len(errors), msg=f"exactly one error expected: {errors!r}")
        self.assertRegex(errors[0], _ARITY_RULE)
        lowered = errors[0].lower()
        for existence_claim in ("broken path", "does not exist", "missing"):
            self.assertNotIn(existence_claim, lowered, msg=errors[0])


if __name__ == "__main__":
    unittest.main()
