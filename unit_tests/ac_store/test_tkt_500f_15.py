"""
MODULE: test_tkt_500f_15
GOAL: RED test stubs for TKT-500f-15. Verifies that generate_ticket_from_ac.py
      treats a SCALAR-string ``components`` field as a single logical component,
      never as an iterable of characters (per-character shatter).

      The three tests exercise _build_components_list via the --dry-run path:

      1. A fixture AC with scalar ``components: build_orchestration`` yields
         a generated components LIST == ['build_orchestration'] (exactly 1 element).
      2. A scalar-string ``components`` value never produces a LIST of
         single-character elements (never ['b','u','i','l','d',...]).
      3. A scalar index.yaml kebab namespace key (e.g. ``ticket-creation``) is
         emitted as its components.json underscore graph id
         (``ticket_creation_pipeline``), not left verbatim or character-shattered.

      All three must fail (RED) before the fix lands in _build_components_list.

TICKET: TICKET-20260721-TKT-500f-15.md
COVERS: TKT-500f-15
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
# (same pattern as test_tkt_500f_14.py)
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


class TestScalarComponentsNotShatters(unittest.TestCase):
    """TKT-500f-15: _build_components_list must treat a scalar-string components
    field as a single logical component value, wrapping it in a one-element list
    and resolving any kebab key through the MIGRATION_MAP.

    The bug: when ``components`` in an AC is a scalar string (not a YAML list),
    the current code does ``list(existing)`` which iterates over the characters of
    the string, producing per-character shatter instead of a single-element list.
    """

    def test_scalar_string_components_becomes_single_element_graph_id_list(self):
        # covers: TKT-500f-15
        """A fixture AC with scalar components: build_orchestration yields exactly
        ['build_orchestration'] — a one-element list.

        Must be RED before implementation: _build_components_list currently does
        list("build_orchestration") which returns 18 single-char elements, not 1.

        After the fix, when the ``components`` field is a scalar string (not a list),
        _build_components_list must wrap it: [existing_string_resolved_via_map].

        Fixture: components set to the scalar string "build_orchestration" (an
        underscore graph id that is already in graph-id form, so MIGRATION_MAP is a
        no-op — the output is just ["build_orchestration"]).
        """
        ac_data = {
            "title": "Scalar components fixture — TKT-500f-15 single-element test",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "assigned_agent": "python-coder",
            "component": "ticket-creation",
            "estimated_complexity": "S",
            "change_target": "pipeline",
            "risk_surface": "internal",
            # SCALAR string, NOT a list — this is the bug trigger.
            # Current code: list("build_orchestration") = 18 single-char elements.
            # Expected after fix: ["build_orchestration"] (single-element list).
            "components": "build_orchestration",
            "it_requirements": {
                "reference_file_path": "scripts/ac_store/generate_ticket_from_ac.py",
            },
            "criteria": (
                "Given a leaf AC whose components field is a scalar string,\n"
                "When a ticket is generated from that AC,\n"
                "Then the generated ticket's components LIST is a single-element list."
            ),
        }

        fm = _run_dry_run(ac_data, ac_id="TKT-500f-15-scalar-fixture")
        components = fm.get("components", [])

        self.assertEqual(
            components,
            ["build_orchestration"],
            (
                "Expected components to be ['build_orchestration'] (1 element) "
                "when the AC's components field is the scalar string 'build_orchestration'. "
                f"Actual components: {components!r}. "
                "The current _build_components_list does list('build_orchestration') "
                "which produces a per-character shatter of 18 single-char elements. "
                "Fix: detect that existing is a str and wrap it: [existing] instead of "
                "list(existing)."
            ),
        )

    def test_scalar_components_never_per_character_shatter(self):
        # covers: TKT-500f-15
        """A scalar-string components value must never produce a list of single-char
        elements — the per-character shatter must not appear in the output.

        Must be RED before implementation: the current list("build_orchestration")
        call produces 18 elements each of length 1 — every element is a single char.

        After the fix, none of the elements in the components list may be a single
        character (each element is a full component graph id, which is always > 1 char).

        Fixture: same as test_scalar_string_components_becomes_single_element_graph_id_list.
        """
        ac_data = {
            "title": "Scalar shatter check fixture — TKT-500f-15",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "assigned_agent": "python-coder",
            "component": "ticket-creation",
            "estimated_complexity": "S",
            "change_target": "pipeline",
            "risk_surface": "internal",
            # SCALAR string — triggers list(str) per-char shatter in current code.
            "components": "build_orchestration",
            "it_requirements": {
                "reference_file_path": "scripts/ac_store/generate_ticket_from_ac.py",
            },
            "criteria": (
                "Given a leaf AC whose components field is a scalar string,\n"
                "When a ticket is generated from that AC,\n"
                "Then the generated ticket's components LIST contains no single-char elements."
            ),
        }

        fm = _run_dry_run(ac_data, ac_id="TKT-500f-15-shatter-fixture")
        components = fm.get("components", [])

        single_char_elements = [c for c in components if isinstance(c, str) and len(c) == 1]

        self.assertEqual(
            single_char_elements,
            [],
            (
                "Expected zero single-character elements in the components list, "
                "but found per-character shatter. "
                f"All single-char elements found: {single_char_elements!r}. "
                f"Full components list: {components!r}. "
                "The current _build_components_list does list('build_orchestration') "
                "which produces every character as a separate element. "
                "Fix: treat a scalar string as a single value, not an iterable."
            ),
        )

    def test_scalar_kebab_namespace_key_resolves_to_graph_id(self):
        # covers: TKT-500f-15
        """A scalar index.yaml kebab namespace key is resolved to its components.json
        underscore graph id via the MIGRATION_MAP, not left verbatim or shattered.

        Must be RED before implementation: the current code does list('ticket-creation')
        which produces 15 single-char elements — it never reaches MIGRATION_MAP because
        the scalar string is truthy so the early-return path fires.

        After the fix, a scalar 'ticket-creation' must be looked up in _COMPONENT_MIGRATION_MAP
        and emitted as its underscore graph id: ['ticket_creation_pipeline'].
        MIGRATION_MAP['ticket-creation'] == 'ticket_creation_pipeline' (per
        scripts/migrate_component_vocab.py line 64).

        Fixture: components set to the scalar string 'ticket-creation' (a kebab key
        from the index.yaml namespace that maps to 'ticket_creation_pipeline' in the
        components.json graph vocabulary).
        """
        ac_data = {
            "title": "Scalar kebab resolution fixture — TKT-500f-15",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "assigned_agent": "python-coder",
            "component": "ticket-creation",
            "estimated_complexity": "S",
            "change_target": "pipeline",
            "risk_surface": "internal",
            # SCALAR kebab key — should be resolved to graph id 'ticket_creation_pipeline'.
            # Current code: list("ticket-creation") = 15 single-char elements (shatter).
            # Expected after fix: ["ticket_creation_pipeline"].
            "components": "ticket-creation",
            "it_requirements": {
                "reference_file_path": "scripts/ac_store/generate_ticket_from_ac.py",
            },
            "criteria": (
                "Given a leaf AC whose components field is the scalar kebab string 'ticket-creation',\n"
                "When a ticket is generated from that AC,\n"
                "Then the generated ticket's components LIST is ['ticket_creation_pipeline']."
            ),
        }

        fm = _run_dry_run(ac_data, ac_id="TKT-500f-15-kebab-fixture")
        components = fm.get("components", [])

        self.assertEqual(
            components,
            ["ticket_creation_pipeline"],
            (
                "Expected components to be ['ticket_creation_pipeline'] when the AC's "
                "components field is the scalar string 'ticket-creation' (a kebab key). "
                f"Actual components: {components!r}. "
                "The current _build_components_list does list('ticket-creation') which "
                "produces 15 single-char shatter elements and never consults MIGRATION_MAP. "
                "Fix: detect that existing is a str, wrap in list after MIGRATION_MAP lookup: "
                "[_COMPONENT_MIGRATION_MAP.get(existing, existing)]."
            ),
        )


if __name__ == "__main__":
    unittest.main()
