"""
MODULE: test_tkt_500f_12
GOAL: RED test stubs for TKT-500f-12. Verifies that generate_ticket_from_ac.py
      wires ``ac-validator`` and ``ac-fulfillment-gate`` as ``needed`` phases in the
      generated ticket's agents map when the AC's files_touched list contains at
      least one implementation ``.py`` file; and does NOT force those agents onto
      docs/config-only ACs (no ``.py`` in files_touched).

      Both tests call main() with --dry-run and a minimal fixture AC, then
      parse the YAML frontmatter from stdout to inspect the ``agents`` map.

TICKET: TICKET-20260717-TKT-500f-12.md
COVERS: TKT-500f-12
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


class TestAcValidatorAndFulfillmentGateWiring(unittest.TestCase):
    """TKT-500f-12: agents map must wire ac-validator and ac-fulfillment-gate
    as needed phases when files_touched contains an implementation .py file.
    """

    def test_code_ticket_wires_ac_validator_and_fulfillment_gate(self):
        # covers: TKT-500f-12
        """Generate a ticket from an AC whose files_touched contains a .py file;
        assert that both ac-validator and ac-fulfillment-gate are wired as 'needed'
        phases in the generated ticket's agents map.

        Must be RED before implementation: _build_agents_map has no logic to detect
        .py files in files_touched and add ac-validator / ac-fulfillment-gate to the
        computed agents map. Currently neither agent appears in guardrail_gates.yaml
        nor in _CANONICAL_PHASE_ORDER.

        After the fix, when files_touched contains at least one implementation .py
        file (e.g. scripts/ac_store/generate_ticket_from_ac.py), the generated
        ticket's agents frontmatter must include:
          ac-validator: needed
          ac-fulfillment-gate: needed

        The detection must key off files_touched (produced by _build_files_touched);
        a stale or doc_links-only files_touched would mis-classify a code AC as
        docs-only (per implementation notes).
        """
        # Fixture AC: has a .py file as its reference_file_path, so files_touched
        # will include 'scripts/ac_store/generate_ticket_from_ac.py'.
        ac_data = {
            "title": "Code AC fixture — TKT-500f-12 agents-map wiring test",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "assigned_agent": "python-coder",
            "component": "ticket-creation",
            "estimated_complexity": "M",
            "change_target": "code",
            "risk_surface": "internal",
            "it_requirements": {
                # This path ends in .py, so files_touched will contain a .py entry.
                "reference_file_path": "scripts/ac_store/generate_ticket_from_ac.py",
            },
            "criteria": (
                "Given a leaf AC whose files_touched contains at least one .py file,\n"
                "When a ticket is generated from that AC by generate_ticket_from_ac.py,\n"
                "Then the generated ticket's agents map wires ac-validator as a needed phase,\n"
                "And the agents map wires ac-fulfillment-gate as a needed phase."
            ),
        }

        fm = _run_dry_run(ac_data, ac_id="TKT-500f-12-code-fixture")
        agents = fm.get("agents", {})

        self.assertEqual(
            agents.get("ac-validator"),
            "needed",
            (
                "ac-validator must be wired as 'needed' in the agents map when "
                "files_touched contains a .py file. "
                f"Current agents map: {agents!r}. "
                "The current _build_agents_map has no logic to detect .py files "
                "in files_touched; python-coder must add this wiring logic."
            ),
        )

        self.assertEqual(
            agents.get("ac-fulfillment-gate"),
            "needed",
            (
                "ac-fulfillment-gate must be wired as 'needed' in the agents map when "
                "files_touched contains a .py file. "
                f"Current agents map: {agents!r}. "
                "The current _build_agents_map has no logic to detect .py files "
                "in files_touched; python-coder must add this wiring logic."
            ),
        )

    def test_docs_only_ticket_not_forced(self):
        # covers: TKT-500f-12
        """Generate a ticket from a docs/config-only AC (no .py in files_touched);
        assert that ac-validator and ac-fulfillment-gate are NOT force-added to the
        generated ticket's agents map beyond the pipeline's existing rules.

        This is a regression guard: after the implementation adds .py detection to
        the agents-map builder, docs/config-only ACs must not be incorrectly forced
        to carry ac-validator and ac-fulfillment-gate.

        NOTE: This test may pass immediately before implementation (the agents are
        absent from docs-only tickets both before and after the fix — the fix only
        adds them for code tickets with .py in files_touched). It is included as a
        regression guard that will fail if the implementation incorrectly adds these
        agents to ALL tickets regardless of files_touched content.

        After the fix, a docs-only AC (change_target: docs, risk_surface: internal,
        reference_file_path: docs/reference/ac-schema.md) must NOT carry:
          ac-validator: needed
          ac-fulfillment-gate: needed
        because its files_touched list contains no .py file.
        """
        # Fixture AC: docs-only; reference_file_path is a .md file (no .py).
        # files_touched will contain only 'docs/reference/ac-schema.md'.
        ac_data = {
            "title": "Docs-only AC fixture — TKT-500f-12 no-force test",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "assigned_agent": "documentation-expert",
            "component": "ticket-creation",
            "estimated_complexity": "S",
            "change_target": "docs",
            "risk_surface": "internal",
            "it_requirements": {
                # This path ends in .md, NOT .py — so files_touched has no .py entry.
                "reference_file_path": "docs/reference/ac-schema.md",
            },
            "criteria": (
                "Given a docs/config-only AC with no .py file in files_touched,\n"
                "When a ticket is generated from that AC by generate_ticket_from_ac.py,\n"
                "Then the agents map does not force ac-validator as a needed phase,\n"
                "And the agents map does not force ac-fulfillment-gate as a needed phase."
            ),
        }

        fm = _run_dry_run(ac_data, ac_id="TKT-500f-12-docs-only-fixture")
        agents = fm.get("agents", {})

        self.assertNotEqual(
            agents.get("ac-validator"),
            "needed",
            (
                "ac-validator must NOT be forced as 'needed' for a docs-only AC "
                "(no .py in files_touched). "
                f"Current agents map: {agents!r}. "
                "The .py detection must key off files_touched; docs-only ACs must "
                "not carry ac-validator."
            ),
        )

        self.assertNotEqual(
            agents.get("ac-fulfillment-gate"),
            "needed",
            (
                "ac-fulfillment-gate must NOT be forced as 'needed' for a docs-only AC "
                "(no .py in files_touched). "
                f"Current agents map: {agents!r}. "
                "The .py detection must key off files_touched; docs-only ACs must "
                "not carry ac-fulfillment-gate."
            ),
        )


if __name__ == "__main__":
    unittest.main()
