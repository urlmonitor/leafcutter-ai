"""
MODULE: test_tkt_500f_11
GOAL: RED test stubs for TKT-500f-11.  Verifies that generate_ticket_from_ac.py
      emits machine-parseable '- [ ] AC-N:' checkbox lines inside the
      '## Acceptance Criteria' section of the generated ticket body, alongside
      (not replacing) the human-readable Gherkin block.

      All three tests call main() with --dry-run and a minimal fixture AC, then
      inspect the captured stdout to examine the '## Acceptance Criteria' section.

      Each test will be RED before implementation because _build_ticket_body
      (lines 1043-1065 of generate_ticket_from_ac.py) only emits a ```gherkin
      block and does NOT yet emit any '- [ ] AC-N:' checkbox lines.

TICKET: TICKET-20260716-TKT-500f-11.md
COVERS: TKT-500f-11
"""

from __future__ import annotations

import io
import re
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
# Shared fixture AC data (minimal valid AC for dry-run generation)
# ---------------------------------------------------------------------------

_FIXTURE_AC_DATA: dict = {
    "title": "Checkbox emission test fixture — TKT-500f-11",
    "level": "L2",
    "status": "active",
    "work_status": "todo",
    "assigned_agent": "python-coder",
    "component": "ticket-creation",
    "estimated_complexity": "M",
    "criteria": (
        "Given a leaf AC whose criteria expresses distinct conditions,\n"
        "When a ticket is generated from that AC,\n"
        "Then the '## Acceptance Criteria' section contains at least one\n"
        "  machine-parseable checkbox line of the form '- [ ] AC-1: <text>'."
    ),
}

# ---------------------------------------------------------------------------
# Helper: run --dry-run and return the full stdout output
# ---------------------------------------------------------------------------


def _run_dry_run_output(ac_data: dict, ac_id: str = "TKT-500f-11-fixture") -> str:
    """Run generate_ticket_from_ac.py --dry-run with the given AC data.

    Writes a temporary AC YAML file, invokes main() with --dry-run, captures
    stdout, and returns the full captured output string.

    Args:
        ac_data: AC record dict.  The 'id' key is set to *ac_id* automatically.
        ac_id:   The AC id to use for the fixture file.

    Returns:
        The full stdout output string from the --dry-run invocation.
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

        return captured.getvalue()


def _extract_ac_section(output: str) -> str:
    """Extract the '## Acceptance Criteria' section from a dry-run ticket output.

    The section spans from the '## Acceptance Criteria' heading to the next
    level-2 heading (## ...) or to the end of the string.

    Args:
        output: Full stdout string from a --dry-run invocation.

    Returns:
        The text of the '## Acceptance Criteria' section (including the heading),
        or an empty string when the section is not found.
    """
    match = re.search(
        r"(## Acceptance Criteria.*?)(?=\n## |\Z)",
        output,
        re.DOTALL,
    )
    if match:
        return match.group(1)
    return ""


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestAcceptanceCriteriaCheckboxEmission(unittest.TestCase):
    """TKT-500f-11: ## Acceptance Criteria section must emit '- [ ] AC-N:' checkboxes."""

    def test_acceptance_criteria_has_checkbox_line(self):
        # covers: TKT-500f-11
        """Generate a ticket; assert the '## Acceptance Criteria' section contains
        at least one line matching the pattern '- [ ] AC-1:'.

        Must be RED before implementation: _build_ticket_body (lines 1043-1065)
        only emits a ```gherkin block; it does NOT emit any '- [ ] AC-N:' checkbox
        lines.  After the fix the section must contain at least one line of the
        exact form '- [ ] AC-1: <text>'.
        """
        output = _run_dry_run_output(
            _FIXTURE_AC_DATA, ac_id="TKT-500f-11-checkbox-fixture"
        )
        ac_section = _extract_ac_section(output)

        self.assertTrue(
            ac_section,
            "The '## Acceptance Criteria' section was not found in the generated "
            "ticket output.  The section should always be present.",
        )

        checkbox_pattern = re.compile(r"^- \[ \] AC-1:", re.MULTILINE)
        self.assertTrue(
            checkbox_pattern.search(ac_section),
            "The '## Acceptance Criteria' section must contain at least one line "
            "matching '- [ ] AC-1: <text>'.  Currently absent because _build_ticket_body "
            "only emits a ```gherkin block (lines 1043-1065) and does not emit any "
            "'- [ ] AC-N:' checkbox lines.  Implementation must add these lines.",
        )

    def test_checkbox_and_gherkin_coexist(self):
        # covers: TKT-500f-11
        """Assert the machine-parseable checkbox lines are present alongside (not
        replacing) the human-readable Gherkin block.

        Must be RED before implementation: the '- [ ] AC-N:' checkbox lines are
        absent, so the checkbox assertion fails even though the Gherkin block is
        present.  After the fix, BOTH the ```gherkin block AND at least one
        '- [ ] AC-N:' line must appear in the section — additive, not a replacement.
        """
        output = _run_dry_run_output(
            _FIXTURE_AC_DATA, ac_id="TKT-500f-11-coexist-fixture"
        )
        ac_section = _extract_ac_section(output)

        self.assertTrue(
            ac_section,
            "The '## Acceptance Criteria' section was not found in the generated "
            "ticket output.",
        )

        # The Gherkin block must still be present (never replaced).
        self.assertIn(
            "```gherkin",
            ac_section,
            "The human-readable ```gherkin block must still be present in the "
            "'## Acceptance Criteria' section after the checkbox lines are added.  "
            "The checkbox lines are additive — they must not replace the Gherkin block.",
        )

        # The checkbox lines must ALSO be present (additive, not a replacement).
        # This assertion is the RED trigger: checkbox lines are not yet emitted.
        checkbox_pattern = re.compile(r"^- \[ \] AC-\d+:", re.MULTILINE)
        self.assertTrue(
            checkbox_pattern.search(ac_section),
            "At least one '- [ ] AC-N:' checkbox line must be present IN ADDITION TO "
            "the ```gherkin block.  Currently absent — the implementation must emit "
            "checkbox lines alongside the Gherkin block without removing it.",
        )

    def test_ac_validator_recognizes_checkboxes(self):
        # covers: TKT-500f-11
        """Parse the generated section with ac-validator's checkbox parser; assert
        the recognized-criteria count is at least 1.

        Uses the same pattern ac-validator applies when scanning a ticket's
        '## Acceptance Criteria' section: lines matching '^- \\[ \\] AC-\\d+:'.
        Must be RED before implementation: no checkbox lines are emitted, so the
        regex finds zero matches and the count assertion fails.  After the fix,
        every emitted '- [ ] AC-N:' line must be recognized as an acceptance-criterion
        checkbox so ac-validator has criteria to assert against.
        """
        output = _run_dry_run_output(
            _FIXTURE_AC_DATA, ac_id="TKT-500f-11-validator-fixture"
        )
        ac_section = _extract_ac_section(output)

        self.assertTrue(
            ac_section,
            "The '## Acceptance Criteria' section was not found in the generated "
            "ticket output.",
        )

        # ac-validator's checkbox parser pattern: lines of the form '- [ ] AC-N: <text>'
        checkbox_parser = re.compile(r"^- \[ \] AC-\d+:\s*\S", re.MULTILINE)
        recognized = checkbox_parser.findall(ac_section)

        self.assertGreaterEqual(
            len(recognized),
            1,
            f"ac-validator's checkbox parser recognized {len(recognized)} criteria "
            "in the '## Acceptance Criteria' section; expected at least 1.  "
            "Currently 0 because _build_ticket_body does not emit any '- [ ] AC-N:' "
            "lines.  After implementation, every emitted checkbox line must match "
            "the pattern '^- \\[ \\] AC-N: <non-whitespace>' so ac-validator can "
            "assert against them.",
        )


if __name__ == "__main__":
    unittest.main()
