"""
MODULE: test_tkt_500f_16
GOAL: RED test stubs for TKT-500f-16. Verifies that generate_ticket_from_ac.py
      normalises every element of a YAML-LIST ``components`` field to its
      components.json underscore graph id via ``_COMPONENT_MIGRATION_MAP``.

      The three tests exercise _build_components_list via the --dry-run path:

      1. A fixture AC with a LIST ``components: [build-pipeline]`` (kebab)
         yields a generated components LIST == ['build_pipeline'] — the kebab
         element is resolved to its graph id.
      2. A mixed list ``['ticket_creation_pipeline', 'build-orchestration']``
         emits only underscore graph ids; no element retains a hyphen.
      3. An element already a valid underscore graph id (``build_orchestration``)
         is preserved unchanged and appears exactly once — not duplicated when
         the normalisation pass runs alongside a kebab sibling.

      All three must fail (RED) before the fix lands in _build_components_list.

      Bug: ``_build_components_list`` currently handles a list input with
      ``list(existing)`` — a pass-through that leaves kebab elements such as
      ``build-pipeline`` and ``build-orchestration`` unnormalised in the
      generated ticket frontmatter.

TICKET: TICKET-20260721-TKT-500f-16.md
COVERS: TKT-500f-16
"""

from __future__ import annotations

import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

# ---------------------------------------------------------------------------
# Path setup: unit_tests/ac_store/ is 3 levels below the repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import main as _main  # noqa: E402


# ---------------------------------------------------------------------------
# Helper: run --dry-run and return the parsed frontmatter dict
# (same pattern as test_tkt_500f_15.py)
# ---------------------------------------------------------------------------


def _run_dry_run(ac_data: dict, ac_id: str) -> dict:
    """Run generate_ticket_from_ac.py --dry-run with the given AC data.

    Writes a temporary AC YAML file, invokes main() with --dry-run, captures
    stdout, and parses the YAML frontmatter block from the output.

    Args:
        ac_data: AC record dict.  The 'id' key is set to *ac_id* automatically.
        ac_id:   The AC id to use for the fixture file.

    Returns:
        Parsed frontmatter dict, or an empty dict when parsing fails.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        ac_root = tmppath / "docs" / "acceptance-criteria" / "fixture-component"
        ac_root.mkdir(parents=True)

        ac_yaml_data = dict(ac_data)
        ac_yaml_data["id"] = ac_id

        ac_file = ac_root / f"{ac_id}.yaml"
        ac_file.write_text(yaml.dump(ac_yaml_data, allow_unicode=True), encoding="utf-8")

        captured = io.StringIO()
        with patch("sys.stdout", captured):
            _main(
                [
                    "--ac", ac_id,
                    "--ac-root", str(tmppath / "docs" / "acceptance-criteria"),
                    "--dry-run",
                ]
            )

        output = captured.getvalue()

    # The output format is:  ---\n<YAML>\n---\n\n<body>\n
    # Split on "---" to extract the frontmatter block.
    parts = output.split("---")
    # parts[0] is empty (before first ---), parts[1] is the YAML, parts[2]+ is the body
    if len(parts) >= 3:
        try:
            parsed = yaml.safe_load(parts[1])
            if isinstance(parsed, dict):
                return parsed
        except yaml.YAMLError:
            pass
    return {}


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestListComponentsNormalisedToGraphIds(unittest.TestCase):
    """TKT-500f-16: _build_components_list must normalise every element of a
    YAML-LIST ``components`` field to its components.json underscore graph id.

    The bug: when ``components`` in an AC is a YAML list, the current code
    does ``list(existing)`` which is a plain pass-through — kebab elements
    such as ``build-pipeline`` or ``build-orchestration`` survive into the
    generated ticket frontmatter unmodified. Per TKT-500f-16, every element
    must be resolved through ``_COMPONENT_MIGRATION_MAP`` so that no kebab
    element passes through when an underscore graph id exists for it.
    """

    def test_kebab_list_element_normalised_to_graph_id(self):
        # covers: TKT-500f-16
        """A fixture AC with LIST components: [build-pipeline] (kebab) yields
        a generated components LIST == ['build_pipeline'] — the single kebab
        element is resolved to its graph id via _COMPONENT_MIGRATION_MAP.

        Must be RED before implementation: the current _build_components_list
        does list(['build-pipeline']) which returns ['build-pipeline'] unchanged
        (the kebab element passes straight through without normalisation).

        After the fix, each element of a list input must be resolved through
        _COMPONENT_MIGRATION_MAP; 'build-pipeline' maps to 'build_pipeline'
        (per scripts/migrate_component_vocab.py MIGRATION_MAP line 59).

        Fixture: components set to the YAML list ['build-pipeline'] (a single
        kebab element that has an underscore graph id entry in MIGRATION_MAP).
        """
        ac_data = {
            "title": "Kebab list element fixture — TKT-500f-16 single-element test",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "assigned_agent": "python-coder",
            "component": "ticket-creation",
            "estimated_complexity": "S",
            "change_target": "pipeline",
            "risk_surface": "internal",
            # YAML LIST with a single kebab element — this is the bug trigger.
            # Current code: list(['build-pipeline']) = ['build-pipeline'] (passthrough).
            # Expected after fix: ['build_pipeline'] (resolved via MIGRATION_MAP).
            "components": ["build-pipeline"],
            "it_requirements": {
                "reference_file_path": "scripts/ac_store/generate_ticket_from_ac.py",
            },
            "criteria": (
                "Given a leaf AC whose components LIST contains the kebab element 'build-pipeline',\n"
                "When a ticket is generated from that AC,\n"
                "Then the generated ticket's components LIST is ['build_pipeline']."
            ),
        }

        fm = _run_dry_run(ac_data, ac_id="TKT-500f-16-kebab-list-fixture")
        components = fm.get("components", [])

        self.assertEqual(
            components,
            ["build_pipeline"],
            (
                "Expected components to be ['build_pipeline'] (normalised graph id) "
                "when the AC's components LIST is ['build-pipeline'] (a kebab element). "
                f"Actual components: {components!r}. "
                "The current _build_components_list does list(['build-pipeline']) "
                "which passes the kebab element through unchanged. "
                "Fix: iterate the list, resolving each element through _COMPONENT_MIGRATION_MAP."
            ),
        )

    def test_mixed_list_yields_all_underscore_graph_ids(self):
        # covers: TKT-500f-16
        """A mixed list ['ticket_creation_pipeline', 'build-orchestration'] emits
        only underscore graph ids; no element retains a hyphen.

        Must be RED before implementation: the current _build_components_list
        does list(['ticket_creation_pipeline', 'build-orchestration']) which
        returns the same list unchanged — 'build-orchestration' retains its
        hyphen instead of being normalised to 'build_orchestration'.

        After the fix, each element is resolved through _COMPONENT_MIGRATION_MAP;
        'ticket_creation_pipeline' (already a graph id) stays unchanged, and
        'build-orchestration' is resolved to 'build_orchestration'
        (per scripts/migrate_component_vocab.py MIGRATION_MAP line 66).

        Fixture: components set to the YAML list ['ticket_creation_pipeline',
        'build-orchestration'] — one already-valid graph id and one kebab element.
        """
        ac_data = {
            "title": "Mixed list normalisation fixture — TKT-500f-16",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "assigned_agent": "python-coder",
            "component": "ticket-creation",
            "estimated_complexity": "S",
            "change_target": "pipeline",
            "risk_surface": "internal",
            # YAML LIST: one valid graph id + one kebab element.
            # Current code: list([...]) = ['ticket_creation_pipeline', 'build-orchestration']
            # (kebab passes through unchanged).
            # Expected after fix: ['ticket_creation_pipeline', 'build_orchestration'].
            "components": ["ticket_creation_pipeline", "build-orchestration"],
            "it_requirements": {
                "reference_file_path": "scripts/ac_store/generate_ticket_from_ac.py",
            },
            "criteria": (
                "Given a leaf AC whose components LIST is ['ticket_creation_pipeline', 'build-orchestration'],\n"
                "When a ticket is generated from that AC,\n"
                "Then the generated ticket's components LIST is "
                "['ticket_creation_pipeline', 'build_orchestration'] "
                "and no element retains a hyphen."
            ),
        }

        fm = _run_dry_run(ac_data, ac_id="TKT-500f-16-mixed-list-fixture")
        components = fm.get("components", [])

        # Primary assertion: no element in the generated LIST retains a hyphen.
        hyphen_elements = [c for c in components if isinstance(c, str) and "-" in c]

        self.assertEqual(
            hyphen_elements,
            [],
            (
                "Expected zero hyphen-bearing elements in the components list "
                "(all kebab elements must be resolved to underscore graph ids), "
                f"but found: {hyphen_elements!r}. "
                f"Full components list: {components!r}. "
                "The current _build_components_list passes 'build-orchestration' through "
                "unchanged. Fix: resolve each list element through _COMPONENT_MIGRATION_MAP."
            ),
        )

        # Secondary assertion: the full normalised list is exactly right.
        self.assertEqual(
            components,
            ["ticket_creation_pipeline", "build_orchestration"],
            (
                "Expected components == ['ticket_creation_pipeline', 'build_orchestration'] "
                "after normalising the mixed input list. "
                f"Actual: {components!r}."
            ),
        )

    def test_existing_graph_id_preserved_and_not_duplicated(self):
        # covers: TKT-500f-16
        """An element already a valid underscore graph id is preserved unchanged
        and appears exactly once — the normalisation pass must not duplicate it.

        Uses a mixed fixture ['build_orchestration', 'build-pipeline'] to make
        this test RED with the current code: the 'build-pipeline' kebab element
        passes through unnormalised (current list() pass-through), so the full
        assertion ['build_orchestration', 'build_pipeline'] fails.

        After the fix, 'build_orchestration' (already a valid graph id) must:
        - remain 'build_orchestration' in the output (preserved unchanged), AND
        - appear exactly once (not duplicated by the normalisation logic),
        while 'build-pipeline' is resolved to 'build_pipeline'.

        Fixture: components set to ['build_orchestration', 'build-pipeline'] —
        one already-valid graph id followed by one kebab element.
        """
        ac_data = {
            "title": "Graph id preservation and no-dup fixture — TKT-500f-16",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "assigned_agent": "python-coder",
            "component": "ticket-creation",
            "estimated_complexity": "S",
            "change_target": "pipeline",
            "risk_surface": "internal",
            # YAML LIST: one valid graph id + one kebab element.
            # Current code: list([...]) = ['build_orchestration', 'build-pipeline']
            # (kebab passes through unchanged; graph id is preserved but kebab isn't fixed).
            # Expected after fix: ['build_orchestration', 'build_pipeline'].
            "components": ["build_orchestration", "build-pipeline"],
            "it_requirements": {
                "reference_file_path": "scripts/ac_store/generate_ticket_from_ac.py",
            },
            "criteria": (
                "Given a leaf AC whose components LIST is ['build_orchestration', 'build-pipeline'],\n"
                "When a ticket is generated from that AC,\n"
                "Then the generated ticket's components LIST is "
                "['build_orchestration', 'build_pipeline'], "
                "with 'build_orchestration' appearing exactly once."
            ),
        }

        fm = _run_dry_run(ac_data, ac_id="TKT-500f-16-graph-id-preserved-fixture")
        components = fm.get("components", [])

        # Assertion A: the full normalised list is correct.
        # This fails with the current code because 'build-pipeline' is not normalised.
        self.assertEqual(
            components,
            ["build_orchestration", "build_pipeline"],
            (
                "Expected components == ['build_orchestration', 'build_pipeline'] "
                "after normalising ['build_orchestration', 'build-pipeline']. "
                f"Actual: {components!r}. "
                "The current code does list([...]) which passes 'build-pipeline' through "
                "as a hyphen-bearing kebab. Fix: resolve each element through _COMPONENT_MIGRATION_MAP."
            ),
        )

        # Assertion B: 'build_orchestration' (already-valid graph id) appears exactly once.
        count = components.count("build_orchestration")
        self.assertEqual(
            count,
            1,
            (
                "Expected 'build_orchestration' to appear exactly once in the components list "
                f"(not duplicated by the normalisation pass), but found count={count}. "
                f"Full components list: {components!r}."
            ),
        )


if __name__ == "__main__":
    unittest.main()
