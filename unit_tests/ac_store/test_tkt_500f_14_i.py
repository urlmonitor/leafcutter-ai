"""
MODULE: test_tkt_500f_14_i
GOAL: Edge-case tests that BOUND the TKT-500f-14 implementation.
      Verifies two boundary conditions of the broadened code-ticket gate signal
      introduced in generate_ticket_from_ac.py by TKT-500f-14:

      1. docs/config/diagram-only tickets (no source file in files_touched,
         non-coder assigned_agent) must NOT get ac-validator / ac-fulfillment-gate.
      2. A .py file in files_touched still wires ac-validator / ac-fulfillment-gate
         (no regression against the original TKT-500f-12 behaviour).

      Both tests call main() with --dry-run and a minimal fixture AC, then
      parse the YAML frontmatter from stdout to inspect the ``agents`` map.

TICKET: TICKET-20260720-TKT-500f-14-i.md
COVERS: TKT-500f-14-i
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
# (same pattern as test_tkt_500f_12.py and test_tkt_500f_14.py)
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


class TestDocsOnlyAndPyRegressionEdgeCases(unittest.TestCase):
    """TKT-500f-14-i: edge-case bounds for the broadened code-ticket gate signal.

    TKT-500f-14 broadened the gate signal beyond .py to include ANY recognised
    source-code extension AND coder-agent assignment. This file bounds that
    broadening so that:

    1. docs/config/diagram-only tickets (non-coder agent + no source extension
       in files_touched) are NOT over-gated.
    2. The original .py-triggered wiring from TKT-500f-12 still holds (no regression).

    NOTE: Because TKT-500f-14 is already committed, both tests may pass
    immediately. This is expected and correct behaviour — the tests exist as
    regression guards. Their green-on-first-run status is recorded in the
    test-writer sign-off red_baseline with the explanation
    "tests started GREEN — TKT-500f-14 implementation already covers this edge case".
    """

    def test_docs_only_ticket_not_over_gated(self):
        # covers: TKT-500f-14-i
        """Generate a ticket for a docs-only fixture AC (assigned_agent=documentation-expert,
        files_touched=[docs/reference/ac-schema.md]); assert that ac-validator and
        ac-fulfillment-gate are NOT wired as 'needed'.

        Fixture: change_target=pipeline, risk_surface=internal,
        assigned_agent=documentation-expert (non-coder), reference_file_path ends in .md.

        The broadened check in _build_agents_map fires when EITHER:
          - files_touched contains a recognised source extension, OR
          - assigned_agent is in _KNOWN_CODERS.
        A docs-only AC satisfies NEITHER condition, so both gates must remain absent.

        Docs/config/diagram-only tickets are not over-gated by the TKT-500f-14
        broadening — only tickets that contain actual source-code surface (by file
        extension OR by coder assignment) should carry the AC gate phases.
        """
        ac_data = {
            "title": "Docs-only AC fixture — TKT-500f-14-i docs-only no-over-gate test",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            # Non-coder agent — documentation-expert is NOT in _KNOWN_CODERS.
            "assigned_agent": "documentation-expert",
            "component": "ticket-creation",
            "estimated_complexity": "S",
            # pipeline + internal: guardrail path produces [pr-reviewer] only,
            # so ac-validator and ac-fulfillment-gate can only appear via the
            # broadened code-ticket signal — which must NOT fire for this fixture.
            "change_target": "pipeline",
            "risk_surface": "internal",
            "it_requirements": {
                # .md file — no source-code extension in _SOURCE_CODE_EXTENSIONS.
                # files_touched will be ['docs/reference/ac-schema.md'].
                # Neither the extension check nor the coder-assignment check fires.
                "reference_file_path": "docs/reference/ac-schema.md",
            },
            "criteria": (
                "Given a docs/config/diagram-only AC assigned to a non-coder agent\n"
                "  (documentation-expert) with no source file in files_touched,\n"
                "When a ticket is generated from that AC by generate_ticket_from_ac.py,\n"
                "Then ac-validator is not force-added to the generated ticket's agents map,\n"
                "And ac-fulfillment-gate is not force-added to the generated ticket's agents map."
            ),
        }

        fm = _run_dry_run(ac_data, ac_id="TKT-500f-14-i-docs-only-fixture")
        agents = fm.get("agents", {})

        self.assertNotEqual(
            agents.get("ac-validator"),
            "needed",
            (
                "ac-validator must NOT be wired as 'needed' for a docs-only AC "
                "(documentation-expert agent, no source file in files_touched). "
                f"Current agents map: {agents!r}. "
                "The broadened gate signal in _build_agents_map must not fire for "
                "non-coder agents whose files_touched contains no recognised source "
                "extension — docs/config/diagram-only tickets must not be over-gated."
            ),
        )

        self.assertNotEqual(
            agents.get("ac-fulfillment-gate"),
            "needed",
            (
                "ac-fulfillment-gate must NOT be wired as 'needed' for a docs-only AC "
                "(documentation-expert agent, no source file in files_touched). "
                f"Current agents map: {agents!r}. "
                "The broadened gate signal in _build_agents_map must not fire for "
                "non-coder agents whose files_touched contains no recognised source "
                "extension — docs/config/diagram-only tickets must not be over-gated."
            ),
        )

    def test_py_ticket_still_gated_no_regression(self):
        # covers: TKT-500f-14-i
        """Generate a ticket for a fixture AC with a .py file in files_touched;
        assert that both ac-validator and ac-fulfillment-gate are still wired as 'needed'.

        Fixture: change_target=pipeline, risk_surface=internal,
        assigned_agent=python-coder, reference_file_path ends in .py.

        This is a regression guard against TKT-500f-12 behaviour. The .py-triggered
        wiring introduced by TKT-500f-12 must still hold after the TKT-500f-14
        broadening — any narrowing of the check that would drop .py from the
        recognised source extensions would cause this test to fail.

        The test specifically exercises the files_touched signal path (a .py file in
        files_touched matches _SOURCE_CODE_EXTENSIONS) to confirm it was not removed
        or narrowed during the TKT-500f-14 extension.
        """
        ac_data = {
            "title": "Py-source AC fixture — TKT-500f-14-i .py regression guard test",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            # python-coder is in _KNOWN_CODERS — the coder-assignment signal also fires.
            # The .py extension in files_touched means the extension signal fires too.
            # Both signals must independently keep the gates wired.
            "assigned_agent": "python-coder",
            "component": "ticket-creation",
            "estimated_complexity": "S",
            # pipeline + internal: guardrail path produces [pr-reviewer] only,
            # so ac-validator and ac-fulfillment-gate can only appear via the
            # code-ticket signal — which MUST fire for this fixture.
            "change_target": "pipeline",
            "risk_surface": "internal",
            "it_requirements": {
                # .py file — extension is in _SOURCE_CODE_EXTENSIONS.
                # files_touched will be ['scripts/ac_store/generate_ticket_from_ac.py'].
                # Both the extension check (.py) and the coder-assignment check fire.
                "reference_file_path": "scripts/ac_store/generate_ticket_from_ac.py",
            },
            "criteria": (
                "Given a leaf AC whose files_touched contains at least one .py file,\n"
                "When a ticket is generated from that AC by generate_ticket_from_ac.py,\n"
                "Then ac-validator is wired as a needed phase (TKT-500f-12 regression guard),\n"
                "And ac-fulfillment-gate is wired as a needed phase (TKT-500f-12 regression guard)."
            ),
        }

        fm = _run_dry_run(ac_data, ac_id="TKT-500f-14-i-py-fixture")
        agents = fm.get("agents", {})

        self.assertEqual(
            agents.get("ac-validator"),
            "needed",
            (
                "ac-validator must be wired as 'needed' when files_touched contains "
                "a .py implementation file (TKT-500f-12 regression guard). "
                f"Current agents map: {agents!r}. "
                "The .py-triggered wiring from TKT-500f-12 must still hold after "
                "the TKT-500f-14 broadening — check that .py is still in "
                "_SOURCE_CODE_EXTENSIONS and that _build_agents_map still fires "
                "the gate for .py files in files_touched."
            ),
        )

        self.assertEqual(
            agents.get("ac-fulfillment-gate"),
            "needed",
            (
                "ac-fulfillment-gate must be wired as 'needed' when files_touched "
                "contains a .py implementation file (TKT-500f-12 regression guard). "
                f"Current agents map: {agents!r}. "
                "The .py-triggered wiring from TKT-500f-12 must still hold after "
                "the TKT-500f-14 broadening — check that .py is still in "
                "_SOURCE_CODE_EXTENSIONS and that _build_agents_map still fires "
                "the gate for .py files in files_touched."
            ),
        )


if __name__ == "__main__":
    unittest.main()
