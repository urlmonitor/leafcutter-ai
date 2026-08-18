"""Dedicated test coverage for AC BP-900c-1.

BP-900c-1 — Each broken-reference entry names the missing script, the
referencing template, and a suggested action.

Nature: this AC's production code (``BrokenRefEntry`` / ``build_broken_ref_report``
in ``scripts/build_propagation_audit.py``) was authored as part of a LATER commit
(BP-900c-3, PR #186) that also introduced a third, state-based suggested-action
value (``ACTION_COMMIT_UNDER_TEMPLATES``). The three-field *schema* invariant
this AC actually cares about (missing_path / referencing_template / suggested_action,
none empty or omitted) has never had a test tagged directly ``# covers: BP-900c-1``
— existing coverage only tags BP-900c-1-1 (consolidation) and BP-900c-3 /
BP-900c-3-i (the state-based action selector). This file closes that gap.

CLASSIFICATION NOTE (ADR-003 Source-of-Truth Discipline, Rule 1):
BP-900c-1's Gherkin criteria illustrates the suggested_action field with exactly
two example values ("add a deploy phase in build_phases.py" / "add to the
external-dependency allowlist"). Using the AC's own literal example path
(scripts/ac_store/ac_prioritizer.py) against current production code actually
selects a THIRD value, ACTION_COMMIT_UNDER_TEMPLATES, because BP-900c-3 added a
directory-prefix classification that this AC's YAML `notes` field explicitly
authorizes: "BP-900c-3 and BP-900c-3-i extend the suggested_action selection to
be state-based... Keep the three-field entry shape stable here — those ACs
change which value is chosen, not the schema of the entry." The AC's own
`it_requirements.constraints` corroborates this: "Suggested action must be one
of a finite set of known remediation options" (not "exactly one of two"). This
is classified as (classification: consumer_drift) — the illustrative example in
the Gherkin text is stale relative to the intentionally-extended production
contract; the schema (three non-empty fields, action drawn from a known finite
set) is the real, non-stale invariant. The test below asserts against the
module's exported action constants (currently three) rather than hardcoding the
two-value literal, per Rule 5 (prefer expanding the test over shrinking
production) and Rule 6 (test what the schema actually promises).

The second test in this file asserts on
docs/architecture/components/template-compiler.md, one of this ticket's
`files_touched` targets. As of authoring this test, that document does not
mention the broken-reference three-field entry schema anywhere — this is
genuinely un-implemented documentation and this test is RED until it is added.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Repo root — unit_tests/build_guards/test_*.py is 2 levels down from worktree root
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# scripts/ must be in sys.path for build_propagation_audit
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

# Lazy import so a genuine ImportError is a clear, readable failure rather than
# a collection-time crash for the whole file.
try:
    from build_propagation_audit import (
        ACTION_ADD_DEPLOY_PHASE,
        ACTION_ADD_TO_ALLOWLIST,
        ACTION_COMMIT_UNDER_TEMPLATES,
        BrokenRefEntry,
        build_broken_ref_report,
    )
except ImportError:
    build_broken_ref_report = None  # type: ignore[assignment]
    BrokenRefEntry = None  # type: ignore[assignment]
    ACTION_ADD_DEPLOY_PHASE = None  # type: ignore[assignment]
    ACTION_ADD_TO_ALLOWLIST = None  # type: ignore[assignment]
    ACTION_COMMIT_UNDER_TEMPLATES = None  # type: ignore[assignment]


class _BuildPropagationAuditNotAvailable(ImportError):
    """build_propagation_audit is not importable from scripts/."""

    def __init__(self) -> None:
        super().__init__(
            "build_propagation_audit could not be imported from scripts/ — "
            "BrokenRefEntry / build_broken_ref_report must exist to satisfy "
            "AC BP-900c-1."
        )


# ===========================================================================
# BP-900c-1 — schema-level test: three non-empty fields, real example
# ===========================================================================


class TestBP900c1BrokenRefEntryThreeFields(unittest.TestCase):
    """BP-900c-1: each broken-reference entry names all three required fields.

    Uses the AC's own literal example: the script
    "scripts/ac_store/ac_prioritizer.py" referenced by the compiled template
    "agents/build-ac.md", not deployed and not allowlisted.
    """

    def test_ac_bp900c1_entry_has_all_three_nonempty_fields(self):
        # covers: BP-900c-1
        """The report entry for the AC's literal example must contain:
          (a) missing_path == "scripts/ac_store/ac_prioritizer.py"
          (b) "agents/build-ac.md" present among referencing_templates
          (c) a non-empty suggested_action drawn from the module's known,
              finite set of remediation-action constants.

        None of the three fields may be empty or omitted (AC BP-900c-1
        constraint, verbatim from it_requirements.constraints).
        """
        if build_broken_ref_report is None:
            raise _BuildPropagationAuditNotAvailable

        refs_to_sources = {
            "scripts/ac_store/ac_prioritizer.py": {"agents/build-ac.md"},
        }
        entries = build_broken_ref_report(
            refs_to_sources, deployed_scripts=set(), allowlist=frozenset()
        )

        self.assertEqual(
            len(entries),
            1,
            f"Expected exactly 1 BrokenRefEntry for the single missing "
            f"script in the AC's example, got {len(entries)}: {entries!r}",
        )
        entry = entries[0]

        # (a) missing_path field — must be present and match exactly.
        self.assertTrue(
            entry.missing_path,
            "BrokenRefEntry.missing_path must not be empty or omitted "
            "(AC BP-900c-1).",
        )
        self.assertEqual(
            entry.missing_path,
            "scripts/ac_store/ac_prioritizer.py",
            "BrokenRefEntry.missing_path must equal the missing script path "
            "from the AC's example.",
        )

        # (b) referencing_template field — must be present and non-empty.
        self.assertTrue(
            entry.referencing_templates,
            "BrokenRefEntry.referencing_templates must not be empty or "
            "omitted (AC BP-900c-1).",
        )
        self.assertIn(
            "agents/build-ac.md",
            entry.referencing_templates,
            "BrokenRefEntry.referencing_templates must name the compiled "
            "template from the AC's example ('agents/build-ac.md').",
        )

        # (c) suggested_action field — must be present, non-empty, and drawn
        # from the module's known finite set of remediation actions. The
        # AC's own it_requirements.constraints says "one of a finite set of
        # known remediation options" — not a hardcoded two-value literal —
        # so this checks membership in whatever the module currently exports,
        # rather than re-encoding the (superseded) two-value Gherkin example.
        known_actions = {
            ACTION_ADD_DEPLOY_PHASE,
            ACTION_ADD_TO_ALLOWLIST,
            ACTION_COMMIT_UNDER_TEMPLATES,
        }
        self.assertTrue(
            entry.suggested_action,
            "BrokenRefEntry.suggested_action must not be empty or omitted "
            "(AC BP-900c-1).",
        )
        self.assertIn(
            entry.suggested_action,
            known_actions,
            f"BrokenRefEntry.suggested_action must be one of the module's "
            f"known finite remediation actions {known_actions!r}, got "
            f"{entry.suggested_action!r}.",
        )


# ===========================================================================
# BP-900c-1 — documentation coverage: template-compiler.md must describe the
# three-field broken-reference entry schema
# ===========================================================================


class TestBP900c1ArchitectureDocDescribesEntrySchema(unittest.TestCase):
    """BP-900c-1: docs/architecture/components/template-compiler.md must
    document the three-field broken-reference report entry schema.

    ``docs/architecture/components/template-compiler.md`` is one of this
    ticket's declared ``files_touched`` targets. As of writing this test, the
    document has no section describing ``BrokenRefEntry`` or its three
    required fields — this test is expected to be RED until that section is
    added.
    """

    def test_ac_bp900c1_architecture_doc_documents_broken_ref_entry_schema(self):
        # covers: BP-900c-1
        """template-compiler.md must name all three BrokenRefEntry fields:
        missing_path, referencing_template(s), and suggested_action — so a
        reader of the architecture doc can find the broken-reference report
        entry contract without reading the source directly.
        """
        doc_path = (
            _REPO_ROOT
            / "docs"
            / "architecture"
            / "components"
            / "template-compiler.md"
        )
        self.assertTrue(
            doc_path.exists(),
            "docs/architecture/components/template-compiler.md must exist.",
        )
        content = doc_path.read_text(encoding="utf-8")

        self.assertIn(
            "BrokenRefEntry",
            content,
            "template-compiler.md must reference 'BrokenRefEntry' (or "
            "otherwise document the broken-reference report entry) so AC "
            "BP-900c-1's three-field contract is discoverable from the "
            "architecture doc.",
        )
        self.assertIn(
            "missing_path",
            content,
            "template-compiler.md must name the 'missing_path' field of the "
            "broken-reference report entry (AC BP-900c-1).",
        )
        self.assertIn(
            "referencing_template",
            content,
            "template-compiler.md must name the 'referencing_template' "
            "field of the broken-reference report entry (AC BP-900c-1).",
        )
        self.assertIn(
            "suggested_action",
            content,
            "template-compiler.md must name the 'suggested_action' field of "
            "the broken-reference report entry (AC BP-900c-1).",
        )


if __name__ == "__main__":
    unittest.main()
