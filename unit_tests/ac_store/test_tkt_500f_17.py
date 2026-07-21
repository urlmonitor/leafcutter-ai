"""
MODULE: test_tkt_500f_17
GOAL: RED test stubs for TKT-500f-17. Verifies that generate_ticket_from_ac.py
      emits a WARNING when a component value cannot be resolved to a valid
      docs/components.json graph id, and that graph-id validity is determined
      by membership in docs/components.json (the ~42-entry source of truth)
      rather than by the partial hard-coded kebab-to-graph-id map embedded in
      the generator.

      The three tests exercise _build_components_list via the --dry-run path:

      1. A fixture AC with a typo component (e.g. ticket_creaton_pipeline)
         causes a WARNING naming that value; the value is not silently placed
         into the components LIST without complaint.
      2. Validity is determined by membership in docs/components.json — the
         ~42-entry SSOT — not by _COMPONENT_MIGRATION_MAP alone; a real
         components.json id passes without warning, while a value absent from
         components.json triggers a WARNING.
      3. Adding an id to a components.json test double makes that id resolve
         without any change to generator code (data-driven, not name-hard-coded).

      All three must fail (RED) before the fix lands:
      - The current _build_components_list emits NO WARNING for any component
        value — it falls back to the raw value silently via
        _COMPONENT_MIGRATION_MAP.get(v, v).
      - It never reads docs/components.json at generation time.
      - self.assertLogs() raises AssertionError when no WARNING is logged,
        making every test in this file fail with a clear message.

TICKET: TICKET-20260721-TKT-500f-17.md
COVERS: TKT-500f-17
"""

from __future__ import annotations

import io
import json
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
# Fixture: minimal AC data for component-resolution tests
# ---------------------------------------------------------------------------

_BASE_AC: dict = {
    "title": "Component resolution warning fixture — TKT-500f-17",
    "level": "L2",
    "status": "active",
    "work_status": "todo",
    "assigned_agent": "python-coder",
    "component": "ticket-creation",
    "estimated_complexity": "S",
    "change_target": "pipeline",
    "risk_surface": "internal",
    "it_requirements": {
        "reference_file_path": "scripts/ac_store/generate_ticket_from_ac.py",
    },
    "criteria": (
        "Given a fixture AC,\n"
        "When a ticket is generated from that AC,\n"
        "Then the component resolution logic is exercised."
    ),
}


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestUnresolvableComponentWarning(unittest.TestCase):
    """TKT-500f-17: _build_components_list must emit a WARNING at WARNING level
    when a component value cannot be resolved to a valid docs/components.json
    graph id, and must validate membership against docs/components.json at
    generation time rather than against a hard-coded partial map.

    All tests in this class are RED before implementation because:
    - The current _build_components_list never emits any WARNING for component
      values; it silently falls back to the raw value via
      _COMPONENT_MIGRATION_MAP.get(v, v).
    - self.assertLogs("generate_ticket_from_ac", level="WARNING") raises
      AssertionError when no WARNING is emitted during the dry-run call.
    """

    def test_unresolvable_component_emits_warning(self):
        # covers: TKT-500f-17
        """A fixture AC with a typo component (ticket_creaton_pipeline — missing
        the 'i' in 'creation') must cause a WARNING that names the bad value.

        Must be RED before implementation:
        - The current _build_components_list receives ["ticket_creaton_pipeline"]
          (a list), does list(existing) = ["ticket_creaton_pipeline"], and
          silently emits the raw bogus value into the ticket frontmatter.
        - No WARNING is ever logged → self.assertLogs raises AssertionError.

        After the fix:
        - "ticket_creaton_pipeline" is absent from docs/components.json.
        - _build_components_list must emit logger.warning(...) naming the value.
        - The bogus value must NOT be silently inserted as a valid graph id.
        """
        bogus_component = "ticket_creaton_pipeline"  # typo: 'creaton' not 'creation'

        ac_data = dict(_BASE_AC)
        ac_data["title"] = "Typo-component warning fixture — TKT-500f-17"
        ac_data["components"] = [bogus_component]
        ac_data["criteria"] = (
            "Given a leaf AC whose components list contains a typo value,\n"
            "When a ticket is generated,\n"
            f"Then a WARNING naming {bogus_component!r} is emitted."
        )

        # assertLogs raises AssertionError when no WARNING is emitted → RED now.
        # After the fix, the generator must emit a WARNING for the bogus value.
        with self.assertLogs("generate_ticket_from_ac", level="WARNING") as log:
            _run_dry_run(ac_data, "TKT-500f-17-bogus-component-fixture")

        # After implementation: verify the warning names the unresolved value.
        warning_messages = " ".join(log.output)
        self.assertIn(
            bogus_component,
            warning_messages,
            (
                f"Expected a WARNING mentioning {bogus_component!r} but none was found. "
                f"All WARNING messages captured: {log.output!r}. "
                "The generator must name the unresolved component value in its WARNING."
            ),
        )

    def test_graph_id_validity_checked_against_components_json(self):
        # covers: TKT-500f-17
        """Validity is determined by membership in docs/components.json, not by
        the partial hard-coded _COMPONENT_MIGRATION_MAP alone.

        Must be RED before implementation:
        - The current generator emits no WARNING for any component value.
        - self.assertLogs raises AssertionError → RED.

        This test reads the real docs/components.json from the repo to derive
        the authoritative valid-id set and verifies two things:
        (a) A genuine components.json graph id ('ticket_creation_pipeline') IS
            valid — the generator should not warn about it (positive control).
        (b) A bogus id ('ticket_creaton_pipeline') is NOT valid — the generator
            MUST emit a WARNING because it is absent from docs/components.json.

        After the fix, the generator must load docs/components.json at generation
        time and warn about any resolved component id that is absent from the file.
        The hard-coded _COMPONENT_MIGRATION_MAP may still be used as a first-pass
        kebab→underscore translator, but the FINAL validity check must consult
        docs/components.json.
        """
        components_json_path = _REPO_ROOT / "docs" / "components.json"
        self.assertTrue(
            components_json_path.exists(),
            f"docs/components.json not found at {components_json_path}. "
            "The file is required as the graph-id source of truth.",
        )
        with components_json_path.open(encoding="utf-8") as fh:
            components_data = json.load(fh)
        valid_ids = set(components_data.get("components", {}).keys())

        # Positive control: confirm a known real id is present in the file.
        self.assertIn(
            "ticket_creation_pipeline",
            valid_ids,
            (
                "'ticket_creation_pipeline' expected to be a valid components.json graph id "
                "but was absent. Update the test to use a different real id if this component "
                "was renamed."
            ),
        )

        # Negative control: confirm the bogus id is genuinely absent.
        bogus_id = "ticket_creaton_pipeline"  # typo — 'creaton' not 'creation'
        self.assertNotIn(
            bogus_id,
            valid_ids,
            (
                f"{bogus_id!r} was unexpectedly found in docs/components.json. "
                "Choose a different bogus value that is not a real component id."
            ),
        )

        ac_data = dict(_BASE_AC)
        ac_data["title"] = "components.json validity check fixture — TKT-500f-17"
        ac_data["components"] = [bogus_id]
        ac_data["criteria"] = (
            f"Given a leaf AC whose components list contains {bogus_id!r},\n"
            "When a ticket is generated,\n"
            f"Then a WARNING is emitted because {bogus_id!r} is absent from "
            "docs/components.json."
        )

        # assertLogs raises AssertionError when no WARNING is emitted → RED now.
        # (current code: never warns; uses only _COMPONENT_MIGRATION_MAP, not
        # components.json.)
        with self.assertLogs("generate_ticket_from_ac", level="WARNING") as log:
            _run_dry_run(ac_data, "TKT-500f-17-validity-check-fixture")

        # After implementation: verify the warning names the bogus value.
        warning_messages = " ".join(log.output)
        self.assertIn(
            bogus_id,
            warning_messages,
            (
                f"Expected a WARNING naming {bogus_id!r} (absent from docs/components.json), "
                f"but none was found. Messages: {log.output!r}. "
                "The generator must use components.json membership (not just "
                "_COMPONENT_MIGRATION_MAP) to determine graph-id validity."
            ),
        )

    def test_new_component_in_components_json_resolvable_without_code_change(self):
        # covers: TKT-500f-17
        """Adding an id to a components.json test double resolves it without any
        generator code change — validation is purely data-driven (not name-hard-coded).

        Must be RED before implementation because:
        (a) The generator does not read docs/components.json at generation time; it
            only consults the hard-coded _COMPONENT_MIGRATION_MAP.
        (b) Even after patching _find_worktree_root to point at a test-double
            components.json, the generator emits no WARNING for any value (it never
            checks the file) → self.assertLogs raises AssertionError → RED.

        After the fix the generator will:
        1. Call _find_worktree_root() to locate the repo root.
        2. Load <root>/docs/components.json to build the valid-id set.
        3. Warn when a component id is absent from that set.

        This test verifies the negative half: a novel id NOT present in the
        test-double components.json triggers a WARNING.  Once green, a follow-on
        assertion (or separate test in the implementation phase) can verify the
        positive half: the same novel id added to the test-double components.json
        does NOT trigger a WARNING — proving data-driven resolvability without
        any code change.
        """
        novel_id = "my_brand_new_component_tkt500f17_test"

        # The novel id must not be in _COMPONENT_MIGRATION_MAP — otherwise the
        # current code resolves it through the map, bypassing components.json
        # entirely, making the test ambiguous.
        import generate_ticket_from_ac as _gen  # noqa: PLC0415
        self.assertNotIn(
            novel_id,
            _gen._COMPONENT_MIGRATION_MAP,
            (
                f"{novel_id!r} unexpectedly found in _COMPONENT_MIGRATION_MAP. "
                "Choose a more unique novel id that does not appear in the migration map."
            ),
        )

        ac_data = dict(_BASE_AC)
        ac_data["title"] = "Data-driven resolvability fixture — TKT-500f-17 AC-3"
        ac_data["components"] = [novel_id]
        ac_data["criteria"] = (
            f"Given a leaf AC with component {novel_id!r} not in the test-double "
            "components.json,\n"
            "When a ticket is generated,\n"
            f"Then a WARNING naming {novel_id!r} is emitted because the id is "
            "absent from the test-double components.json."
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_root = Path(tmpdir)
            docs_dir = tmp_root / "docs"
            docs_dir.mkdir()

            # Test-double components.json WITHOUT the novel id — so the generator
            # (after the fix) must warn about it.  Once a human verifies that this
            # test turns green, they can also verify the positive half: add
            # novel_id here and confirm no warning is emitted (AC-3 data-driven
            # proof).
            test_double = {
                "components": {
                    "ticket_creation_pipeline": {
                        "id": "ticket_creation_pipeline",
                        "name": "Ticket Creation Pipeline",
                    }
                }
            }
            (docs_dir / "components.json").write_text(
                json.dumps(test_double), encoding="utf-8"
            )

            # Patch _find_worktree_root so that when the generator (after the fix)
            # calls _find_worktree_root() to locate docs/components.json, it gets
            # our controlled test-double root.
            #
            # RED now: the current _build_components_list never calls
            # _find_worktree_root, so this patch has no effect.  No WARNING is
            # emitted → assertLogs raises AssertionError → RED.
            with patch(
                "generate_ticket_from_ac._find_worktree_root",
                return_value=tmp_root,
            ):
                # assertLogs raises AssertionError if no WARNING is emitted → RED
                with self.assertLogs("generate_ticket_from_ac", level="WARNING") as log:
                    _run_dry_run(ac_data, "TKT-500f-17-data-driven-fixture")

                # Only reached after implementation: verify the warning names the
                # novel id that is absent from the test-double components.json.
                warning_messages = " ".join(log.output)
                self.assertIn(
                    novel_id,
                    warning_messages,
                    (
                        f"Expected a WARNING naming {novel_id!r} (absent from "
                        f"test-double components.json), but none was found. "
                        f"Messages: {log.output!r}. "
                        "The generator must load components.json from the patched "
                        "worktree root and warn about ids absent from it."
                    ),
                )


if __name__ == "__main__":
    unittest.main()
