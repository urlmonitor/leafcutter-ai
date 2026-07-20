"""
MODULE: test_tkt_500f_10
GOAL: RED test stubs for TKT-500f-10.  Verifies that generate_ticket_from_ac.py
      renders the AC's delivers_to and expects_from contract fields into the
      generated ticket body, and that null contracts produce no contract block.

      Tests test_delivers_to_rendered and test_expects_from_rendered will be RED
      before implementation: _build_ticket_body (lines 1057+ of
      generate_ticket_from_ac.py) does not access or render the delivers_to or
      expects_from fields from the AC record.

      test_null_contracts_no_render validates the null-guard path and is expected
      to pass immediately (since the current code does not render contracts at
      all).  It is included as a regression guard and is flagged in red_baseline
      with note "passes immediately — may be under-specified".

TICKET: TICKET-20260717-TKT-500f-10.md
COVERS: TKT-500f-10
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
# Shared base fixture AC data (minimal valid AC for dry-run generation)
# ---------------------------------------------------------------------------

_BASE_AC_DATA: dict = {
    "title": "Contract rendering test fixture — TKT-500f-10",
    "level": "L2",
    "status": "active",
    "work_status": "todo",
    "assigned_agent": "python-coder",
    "component": "ticket-creation",
    "estimated_complexity": "M",
    "criteria": (
        "Given a fixture AC with contract fields,\n"
        "When a ticket is generated,\n"
        "Then the ticket renders the contracts correctly."
    ),
}


# ---------------------------------------------------------------------------
# Helper: run --dry-run and return the full stdout (frontmatter + body)
# ---------------------------------------------------------------------------


def _run_dry_run_output(ac_data: dict, ac_id: str = "TKT-500f-10-fixture") -> str:
    """Run generate_ticket_from_ac.py --dry-run with the given AC data.

    Writes a temporary AC YAML file, invokes main() with --dry-run, captures
    stdout, and returns the full output string (frontmatter and body).

    Args:
        ac_data: AC record dict.  The 'id' key is set to *ac_id* automatically.
        ac_id:   The AC id to use for the fixture file.

    Returns:
        Full captured stdout string from the --dry-run invocation.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        ac_root = tmppath / "docs" / "acceptance-criteria" / "fixture-component"
        ac_root.mkdir(parents=True)

        ac_yaml_data = dict(ac_data)
        ac_yaml_data["id"] = ac_id

        ac_file = ac_root / f"{ac_id}.yaml"
        ac_file.write_text(
            yaml.dump(ac_yaml_data, allow_unicode=True), encoding="utf-8"
        )

        captured = io.StringIO()
        with patch("sys.stdout", captured):
            _main(
                [
                    "--ac",
                    ac_id,
                    "--ac-root",
                    str(tmppath / "docs" / "acceptance-criteria"),
                    "--dry-run",
                ]
            )

        return captured.getvalue()


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestContractRendering(unittest.TestCase):
    """TKT-500f-10: ticket body must render delivers_to/expects_from contracts."""

    def test_delivers_to_rendered(self):
        # covers: TKT-500f-10
        """AC with delivers_to {agent, contract}; assert generated ticket renders
        the downstream agent name and the contract text.

        Must be RED before implementation: _build_ticket_body (line 1057+ of
        generate_ticket_from_ac.py) does not access the delivers_to field from
        the AC record.  The contract text and the agent reference will therefore
        be absent from the generated ticket.

        After implementation, the generated ticket must contain:
          - the delivers_to contract text ("a de-duplicated files_touched list")
          - the downstream agent name in a contract context
        The contract text is unique enough that it cannot appear without explicit
        rendering from the delivers_to field.
        """
        ac_data = dict(_BASE_AC_DATA)
        ac_data["delivers_to"] = {
            "agent": "python-coder",
            "contract": "a de-duplicated files_touched list",
        }
        ac_data["expects_from"] = None

        output = _run_dry_run_output(ac_data, ac_id="TKT-500f-10-delivers-fixture")

        # PRIMARY ASSERTION (RED trigger): the unique contract text must appear.
        # This assertion WILL FAIL before implementation because _build_ticket_body
        # ignores delivers_to entirely.
        self.assertIn(
            "a de-duplicated files_touched list",
            output,
            "Generated ticket must contain the delivers_to contract text "
            "'a de-duplicated files_touched list'.  Currently absent because "
            "_build_ticket_body does not render the delivers_to field from the AC.  "
            "Implementation must add contract rendering in _build_ticket_body "
            "(near line 1057 of generate_ticket_from_ac.py).",
        )

    def test_expects_from_rendered(self):
        # covers: TKT-500f-10
        """AC with expects_from {ac_id, contract}; assert generated ticket renders
        the upstream AC id and the contract text.

        Must be RED before implementation: _build_ticket_body (line 1057+ of
        generate_ticket_from_ac.py) does not access the expects_from field from
        the AC record.  The upstream AC id and contract text will therefore be
        absent from the generated ticket.

        After implementation, the generated ticket must contain:
          - the expects_from upstream AC id ("TKT-500f-8")
          - the expects_from contract text ("the union edit surface")
        Both strings are unique and cannot appear without explicit rendering.
        """
        ac_data = dict(_BASE_AC_DATA)
        ac_data["delivers_to"] = None
        ac_data["expects_from"] = {
            "ac_id": "TKT-500f-8",
            "contract": "the union edit surface",
        }

        output = _run_dry_run_output(ac_data, ac_id="TKT-500f-10-expects-fixture")

        # PRIMARY ASSERTION (RED trigger): the unique contract text must appear.
        # This assertion WILL FAIL before implementation.
        self.assertIn(
            "the union edit surface",
            output,
            "Generated ticket must contain the expects_from contract text "
            "'the union edit surface'.  Currently absent because "
            "_build_ticket_body does not render the expects_from field from the AC.  "
            "Implementation must add contract rendering in _build_ticket_body.",
        )

        # SECONDARY ASSERTION (RED trigger): upstream AC id must appear.
        # "TKT-500f-8" won't appear in the body unless explicitly rendered from
        # expects_from["ac_id"].
        self.assertIn(
            "TKT-500f-8",
            output,
            "Generated ticket must reference the upstream AC id 'TKT-500f-8' from "
            "expects_from.  Currently absent — contract block not yet rendered.",
        )

    def test_null_contracts_no_render(self):
        # covers: TKT-500f-10
        """AC with delivers_to null and expects_from null; assert no contract block
        is rendered and generation completes without error.

        This test verifies the null-guard path: when both delivers_to and
        expects_from are explicitly set to null in the AC, the generated ticket
        must NOT include any contract rendering block, and the generation must
        complete without raising an exception.

        NOTE: This test is expected to pass immediately before implementation,
        because the current code does not render contracts at all.  It is included
        as a regression guard for the null-handling path once the feature lands.
        Flagged in red_baseline as 'passes immediately — may be under-specified'.
        """
        ac_data = dict(_BASE_AC_DATA)
        ac_data["delivers_to"] = None
        ac_data["expects_from"] = None

        # Generation must complete without raising.
        try:
            output = _run_dry_run_output(
                ac_data, ac_id="TKT-500f-10-null-fixture"
            )
        except Exception as exc:  # noqa: BLE001
            self.fail(
                "generate_ticket_from_ac.py raised an unexpected exception when "
                f"delivers_to and expects_from are null: {exc}"
            )

        # No contract-rendering sentinel should appear when contracts are null.
        # "## Agent Contracts" is the section header the implementation is
        # expected to emit for non-null contracts; it must NOT appear here.
        self.assertNotIn(
            "## Agent Contracts",
            output,
            "Generated ticket must NOT contain an '## Agent Contracts' section "
            "when both delivers_to and expects_from are null.  A contract section "
            "was found unexpectedly — the null guard is broken.",
        )

        # Smoke check: standard ticket structure must still be intact.
        self.assertIn(
            "## Acceptance Criteria",
            output,
            "Standard '## Acceptance Criteria' section must be present in the "
            "generated ticket even when contract fields are null.",
        )

        # Guard against accidental rendering of the literal string "None" in a
        # contract context (a common mistake when null-guard is missing).
        # We check the body portion only (after the first "---\n") to avoid
        # false positives from YAML frontmatter values.
        body = output.split("---", 2)[-1] if "---" in output else output
        self.assertNotIn(
            "delivers_to: None",
            body,
            "Generated ticket body must NOT contain 'delivers_to: None' — "
            "null contracts must be silently omitted, not rendered as 'None'.",
        )
        self.assertNotIn(
            "expects_from: None",
            body,
            "Generated ticket body must NOT contain 'expects_from: None' — "
            "null contracts must be silently omitted, not rendered as 'None'.",
        )


if __name__ == "__main__":
    unittest.main()
