"""
MODULE: test_bp900c1_1_real_extraction_consolidation
GOAL: Cross-layer seam coverage for BP-900c-1-1 (consolidated multi-template
    broken-reference entry) that pipes the REAL producer
    (``build_referential_integrity.extract_script_path_refs_with_sources``)
    into the REAL consumer (``build_propagation_audit.build_broken_ref_report``)
    against the actual on-disk ``templates/`` tree — not a hand-authored
    synthetic ``refs_to_sources`` dict.
TICKET: 10_TICKET-20260611-BP-900c-1-1-1.md (EPIC-DeploymentCompleteness)

Pre-existing coverage (``unit_tests/build_guards/test_bp_stragglers_backfill.py::
TestBrokenRefConsolidation``) already asserts the consolidation contract, but it
does so entirely against a hand-typed ``refs_to_sources`` dict, so it never
exercises the real ``extract_script_path_refs_with_sources`` scan (mocking both
sides of the producer/consumer seam is insufficient per the repo's
Source-of-Truth Discipline Rule 3 — a cross-layer seam test is required).

This module closes that gap: it scans the real ``templates/`` directory,
confirms the AC's own literal example
(``scripts/ac_store/generate_ticket_from_ac.py`` referenced by BOTH
``agents/build-ac.md`` and ``skills/ac-scanner/SKILL.md``) is present in the
real extraction output, and feeds that real dict through
``build_broken_ref_report`` with the script simulated as undeployed to prove
the consolidation contract holds end-to-end on real data, not just on a
fixture that could silently drift from what the extractor actually produces.

NOTE FOR REVIEWERS (test-writer TDD-order disclosure):
    ``build_broken_ref_report`` and its consolidation behaviour ALREADY EXIST
    and are ALREADY GREEN as of this file's authoring (see
    ``test_bp_stragglers_backfill.py::TestBrokenRefConsolidation``, written for
    a prior ticket — 06_stragglers_test_coverage.md / EPIC-BuildPipelineTestBackfill
    — against the same AC id, BP-900c-1-1). The AC store entry
    (docs/acceptance-criteria/build_pipeline/BP-900-deployment-completeness/
    BP-900c-1-1.yaml) already carries ``work_status: done`` with
    ``implemented_by: tickets/00_inbox/TICKET-20260611-BP-900c-1-1.md`` — a
    DIFFERENT ticket path than the one this test file was written for
    (10_TICKET-20260611-BP-900c-1-1-1.md), confirming this ticket duplicates
    already-completed work. All tests in this file pass immediately (green) on
    first run; there is no red baseline to capture. This is documented in the
    ticket's ``## Comments`` per the "TDD Order" project convention rather than
    silently signed off as a normal red-to-green cycle.
"""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — make scripts/ importable regardless of working directory.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_TEMPLATES_DIR = _REPO_ROOT / "templates"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


class TestRealExtractionFeedsConsolidation:
    """BP-900c-1-1: real extractor output, piped into the real consolidator.

    This is the cross-layer seam the AC's Gherkin literally describes:
    ``scripts/ac_store/generate_ticket_from_ac.py`` is referenced in BOTH
    ``agents/build-ac.md`` and ``skills/ac-scanner/SKILL.md``. We do not
    hand-author that mapping — we extract it from the real templates tree.
    """

    def test_ac1_real_templates_tree_names_the_ac_scenario_script_from_both_templates(self):
        # covers: BP-900c-1-1
        """The real templates/ tree must actually reproduce the AC's own
        literal example, or the rest of this test's premise is invalid.

        This is a sanity pin against the real on-disk artifact (not a
        synthetic fixture): if a future edit stops referencing
        ``generate_ticket_from_ac.py`` from one of these two templates, this
        assertion — not just the downstream consolidation assertion — will
        fail, making the drift visible at the correct layer.
        """
        from build_referential_integrity import extract_script_path_refs_with_sources

        refs_to_sources = extract_script_path_refs_with_sources(_TEMPLATES_DIR)
        key = "scripts/ac_store/generate_ticket_from_ac.py"

        assert key in refs_to_sources, (
            f"Expected {key!r} to be extracted from the real templates/ tree "
            f"— got keys: {sorted(refs_to_sources)[:10]}..."
        )
        sources = refs_to_sources[key]
        assert "agents/build-ac.md" in sources, (
            f"Expected 'agents/build-ac.md' among real referencing templates "
            f"for {key!r}, got {sources}"
        )
        assert "skills/ac-scanner/SKILL.md" in sources, (
            f"Expected 'skills/ac-scanner/SKILL.md' among real referencing "
            f"templates for {key!r}, got {sources}"
        )

    def test_ac1_real_extraction_output_consolidates_to_one_entry_when_missing(self):
        # covers: BP-900c-1-1
        """Feed the REAL refs_to_sources dict (from the real templates/ tree)
        into build_broken_ref_report, simulating the shared script as
        undeployed, and assert exactly ONE consolidated entry is produced
        naming every real referencing template — not one entry per template.

        This closes the producer/consumer seam gap: prior coverage only ever
        called ``build_broken_ref_report`` with a hand-typed two-key dict, so
        it could not catch a mismatch between what the real extractor
        actually returns and what the consolidator assumes it receives.
        """
        from build_propagation_audit import build_broken_ref_report
        from build_referential_integrity import extract_script_path_refs_with_sources

        refs_to_sources = extract_script_path_refs_with_sources(_TEMPLATES_DIR)
        key = "scripts/ac_store/generate_ticket_from_ac.py"
        assert key in refs_to_sources, "precondition: see sanity-pin test above"
        expected_sources = set(refs_to_sources[key])
        assert len(expected_sources) >= 2, (
            "precondition: the AC scenario requires at least two referencing "
            f"templates for {key!r}, got {expected_sources}"
        )

        # Simulate the shared script as NOT in the deployable set (the AC's
        # premise), while every OTHER extracted reference is treated as
        # deployed so only this one path produces a broken-reference entry.
        deployed_scripts = {path for path in refs_to_sources if path != key}

        entries = build_broken_ref_report(
            refs_to_sources=refs_to_sources,
            deployed_scripts=deployed_scripts,
            allowlist=frozenset(),
        )

        matching = [entry for entry in entries if entry.missing_path == key]
        assert len(matching) == 1, (
            f"Expected exactly ONE consolidated entry for {key!r} (not "
            f"{len(matching)}) — multiple templates referencing the same "
            "missing script must produce a single BrokenRefEntry, not one "
            f"per template (AC BP-900c-1-1). Full entries: {entries}"
        )

        entry = matching[0]
        assert set(entry.referencing_templates) == expected_sources, (
            f"Consolidated entry must name every real referencing template. "
            f"Expected {expected_sources}, got {set(entry.referencing_templates)}"
        )
        assert entry.suggested_action, (
            "Consolidated entry must carry a single non-empty suggested_action "
            "(appearing once, not once per referencing template) — got empty."
        )

    def test_ac1_real_extraction_produces_no_entry_when_script_is_deployed(self):
        # covers: BP-900c-1-1
        """Boundary check: when the shared script IS in deployed_scripts, no
        broken-reference entry is produced for it at all — the consolidation
        logic only activates on genuinely missing paths.

        Uses the same real extraction output as the two tests above so the
        boundary is proven on the identical real data, not a separate
        synthetic case.
        """
        from build_propagation_audit import build_broken_ref_report
        from build_referential_integrity import extract_script_path_refs_with_sources

        refs_to_sources = extract_script_path_refs_with_sources(_TEMPLATES_DIR)
        key = "scripts/ac_store/generate_ticket_from_ac.py"
        assert key in refs_to_sources, "precondition: see sanity-pin test above"

        # Every extracted reference (including the shared script) is treated
        # as deployed — nothing should be reported broken for this key.
        deployed_scripts = set(refs_to_sources)

        entries = build_broken_ref_report(
            refs_to_sources=refs_to_sources,
            deployed_scripts=deployed_scripts,
            allowlist=frozenset(),
        )

        matching = [entry for entry in entries if entry.missing_path == key]
        assert matching == [], (
            f"Expected NO broken-reference entry for {key!r} once it is "
            f"deployed, got {matching}"
        )
