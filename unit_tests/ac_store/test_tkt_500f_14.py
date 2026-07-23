"""
MODULE: test_tkt_500f_14
GOAL: RED test stubs for TKT-500f-14. Verifies that generate_ticket_from_ac.py
      wires ``ac-validator`` and ``ac-fulfillment-gate`` as ``needed`` phases in the
      generated ticket's agents map for ANY code ticket — not only .py tickets:
      1. When files_touched contains a non-.py source file (e.g. .js)
      2. When the assigned agent is a coder (python-coder/frontend-coder/sql-coder)
         even when files_touched contains no .py file

      Both tests call main() with --dry-run and a minimal fixture AC, then
      parse the YAML frontmatter from stdout to inspect the ``agents`` map.

TICKET: TICKET-20260720-TKT-500f-14.md
COVERS: TKT-500f-14
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
# (same pattern as test_tkt_500f_12.py)
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


class TestAcGatesForNonPyAndCoderTickets(unittest.TestCase):
    """TKT-500f-14: ac-validator and ac-fulfillment-gate must be wired as
    needed phases for any code ticket — not only .py tickets.

    The broadening covers two signals:
      1. files_touched contains a recognised source extension that is not .py
         (e.g. .js, .ts, .tsx, .sql, .vue, .svelte)
      2. The assigned agent is a known coder (python-coder/frontend-coder/sql-coder)
         regardless of whether files_touched contains any source file at all
    """

    def test_non_py_source_ticket_gets_ac_gates(self):
        # covers: TKT-500f-14
        """Generate a ticket from an AC whose files_touched contains only a .js file;
        assert that both ac-validator and ac-fulfillment-gate are wired as 'needed'.

        Must be RED before implementation: _build_agents_map currently only checks
        for .py files in files_touched (TKT-500f-12 wiring). A .js-only files_touched
        list fails the check ``any(p.endswith(".py") for p in files_touched)``
        so neither gate is added by the current code.

        After the fix (TKT-500f-14), when files_touched contains ANY recognised
        source-code extension (including .js), the generated ticket's agents
        frontmatter must include:
          ac-validator: needed
          ac-fulfillment-gate: needed

        Fixture: change_target=pipeline, risk_surface=internal, assigned_agent=python-coder,
        reference_file_path=templates/workflows/build-feature.js
        Guardrail (pipeline, internal) → [pr-reviewer] — does NOT include ac-validator or
        ac-fulfillment-gate. The only path that could wire them is the .py check, which
        does NOT fire for .js. This test MUST be AssertionError before the fix lands.
        """
        ac_data = {
            "title": "JS-source AC fixture — TKT-500f-14 non-.py gate wiring test",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "assigned_agent": "python-coder",
            "component": "ticket-creation",
            "estimated_complexity": "S",
            # Use pipeline+internal so the computed path is exercised.
            # Guardrail (pipeline, internal) → [pr-reviewer] only — no ac gates.
            "change_target": "pipeline",
            "risk_surface": "internal",
            "it_requirements": {
                # This path ends in .js, NOT .py.
                # files_touched will be ['templates/workflows/build-feature.js'].
                # Current check: any(p.endswith(".py") ...) → False → gates NOT wired.
                "reference_file_path": "templates/workflows/build-feature.js",
            },
            "criteria": (
                "Given a leaf AC whose files_touched contains only a .js source file,\n"
                "When a ticket is generated from that AC by generate_ticket_from_ac.py,\n"
                "Then the generated ticket's agents map wires ac-validator as a needed phase,\n"
                "And the agents map wires ac-fulfillment-gate as a needed phase."
            ),
        }

        fm = _run_dry_run(ac_data, ac_id="TKT-500f-14-js-fixture")
        agents = fm.get("agents", {})

        self.assertEqual(
            agents.get("ac-validator"),
            "needed",
            (
                "ac-validator must be wired as 'needed' in the agents map when "
                "files_touched contains a .js file. "
                f"Current agents map: {agents!r}. "
                "The current _build_agents_map only checks for .py files in "
                "files_touched; python-coder must broaden the check to include "
                "other recognised source extensions (.js, .ts, .tsx, .sql, etc.)."
            ),
        )

        self.assertEqual(
            agents.get("ac-fulfillment-gate"),
            "needed",
            (
                "ac-fulfillment-gate must be wired as 'needed' in the agents map when "
                "files_touched contains a .js file. "
                f"Current agents map: {agents!r}. "
                "The current _build_agents_map only checks for .py files in "
                "files_touched; python-coder must broaden the check to include "
                "other recognised source extensions (.js, .ts, .tsx, .sql, etc.)."
            ),
        )

    def test_coder_assignment_gets_ac_gates(self):
        # covers: TKT-500f-14
        """Generate a ticket from an AC assigned python-coder with no .py in files_touched;
        assert that both ac-validator and ac-fulfillment-gate are wired as 'needed'.

        Must be RED before implementation: _build_agents_map currently only checks
        for .py files in files_touched (TKT-500f-12). When assigned_agent is python-coder
        but files_touched contains only a .md docs file, the check
        ``any(p.endswith(".py") for p in files_touched)`` is False, so neither gate is
        added by the current code — the coder-assignment signal is not yet consulted.

        After the fix (TKT-500f-14), when the assigned agent is a recognised coder
        (python-coder/frontend-coder/sql-coder), the generated ticket's agents
        frontmatter must include:
          ac-validator: needed
          ac-fulfillment-gate: needed
        even when files_touched contains no .py file.

        Fixture: change_target=pipeline, risk_surface=internal, assigned_agent=python-coder,
        reference_file_path=docs/reference/ac-schema.md (a .md file — no .py).
        Guardrail (pipeline, internal) → [pr-reviewer] — does NOT include ac-validator or
        ac-fulfillment-gate. The only path that could wire them is the .py check, which
        does NOT fire for .md. This test MUST be AssertionError before the fix lands.
        """
        ac_data = {
            "title": "Coder-assigned AC fixture — TKT-500f-14 coder-signal gate wiring test",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            # Assigned to a coder — this IS the code-ticket signal for TKT-500f-14.
            "assigned_agent": "python-coder",
            "component": "ticket-creation",
            "estimated_complexity": "S",
            # Use pipeline+internal so the computed path is exercised.
            # Guardrail (pipeline, internal) → [pr-reviewer] only — no ac gates.
            "change_target": "pipeline",
            "risk_surface": "internal",
            "it_requirements": {
                # This path ends in .md, NOT .py.
                # files_touched will be ['docs/reference/ac-schema.md'] — no .py.
                # The assigned agent IS python-coder (a coder), but the current code
                # does not key off the assigned agent — it only checks files_touched.
                "reference_file_path": "docs/reference/ac-schema.md",
            },
            "criteria": (
                "Given a leaf AC assigned to python-coder with no .py file in files_touched,\n"
                "When a ticket is generated from that AC by generate_ticket_from_ac.py,\n"
                "Then the generated ticket's agents map wires ac-validator as a needed phase,\n"
                "And the agents map wires ac-fulfillment-gate as a needed phase."
            ),
        }

        fm = _run_dry_run(ac_data, ac_id="TKT-500f-14-coder-fixture")
        agents = fm.get("agents", {})

        self.assertEqual(
            agents.get("ac-validator"),
            "needed",
            (
                "ac-validator must be wired as 'needed' when the assigned agent is a coder "
                "(python-coder) even when files_touched contains no .py file. "
                f"Current agents map: {agents!r}. "
                "The current _build_agents_map does not key off the assigned agent; "
                "python-coder must add the coder-assignment signal so that a coder "
                "assignment alone is sufficient to wire the AC gates."
            ),
        )

        self.assertEqual(
            agents.get("ac-fulfillment-gate"),
            "needed",
            (
                "ac-fulfillment-gate must be wired as 'needed' when the assigned agent is a "
                "coder (python-coder) even when files_touched contains no .py file. "
                f"Current agents map: {agents!r}. "
                "The current _build_agents_map does not key off the assigned agent; "
                "python-coder must add the coder-assignment signal so that a coder "
                "assignment alone is sufficient to wire the AC gates."
            ),
        )


if __name__ == "__main__":
    unittest.main()
