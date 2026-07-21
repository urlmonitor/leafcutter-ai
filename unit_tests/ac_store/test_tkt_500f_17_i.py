"""
MODULE: test_tkt_500f_17_i
GOAL: RED test stubs for TKT-500f-17-i. Verifies that generate_ticket_from_ac.py
      surfaces an unresolvable component value VERBATIM in the generated components
      LIST (not dropped, not replaced by a fabricated id) AND emits a SINGLE WARNING
      that names both the source AC id and the offending value.

      This edge case bounds TKT-500f-17, ensuring the WARNING path stays visible and
      deterministic rather than masking or guessing:

      1. An AC with an unresolvable component value X causes generate_ticket_from_ac.py
         to emit exactly ONE WARNING whose message text contains BOTH the source AC id
         and the exact value X.  (AC-1)

      2. The unresolved value X appears verbatim in the generated components LIST —
         it is neither silently dropped nor replaced by a fabricated graph id.  (AC-2)

      3. When X appears more than once in the AC's components field, the WARNING is
         still emitted at most once for that distinct value (de-duplication).  (AC-3)

      All three tests must fail RED before the fix lands in _build_components_list:
      the current code performs no validation against docs/components.json and emits
      no WARNING for unresolvable values — so self.assertLogs raises AssertionError
      ("no logs of level WARNING or higher triggered on generate_ticket_from_ac").

TICKET: TICKET-20260721-TKT-500f-17-i.md
COVERS: TKT-500f-17-i
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
    # parts[0] is empty (before first ---), parts[1] is the YAML, parts[2]+ is body
    if len(parts) >= 3:
        try:
            parsed = yaml.safe_load(parts[1])
            if isinstance(parsed, dict):
                return parsed
        except yaml.YAMLError:
            pass
    return {}


# ---------------------------------------------------------------------------
# Fixture constant: a component value that cannot be resolved to any valid
# components.json graph id and is NOT a key in MIGRATION_MAP.
# ---------------------------------------------------------------------------

_UNRESOLVABLE = "totally-unresolvable-xyz-999"


# ---------------------------------------------------------------------------
# Shared AC fixture builder
# ---------------------------------------------------------------------------


def _make_ac_data(components_value: "list[str] | str") -> dict:
    """Return a minimal AC dict whose ``components`` field is *components_value*.

    Uses ``change_target: pipeline`` and ``risk_surface: internal`` so that the
    guardrail-gates lookup succeeds (no spurious guardrail WARNING that would
    interfere with assertLogs assertions).
    """
    return {
        "title": "Unresolvable component fixture — TKT-500f-17-i",
        "level": "L3",
        "status": "active",
        "work_status": "todo",
        "assigned_agent": "python-coder",
        "component": "ticket-creation",
        "estimated_complexity": "S",
        "change_target": "pipeline",
        "risk_surface": "internal",
        "components": components_value,
        "it_requirements": {
            "reference_file_path": "scripts/ac_store/generate_ticket_from_ac.py",
        },
        "criteria": (
            "Given a leaf AC whose component value cannot be resolved to any valid\n"
            "  components.json graph id,\n"
            "When a ticket is generated from that AC,\n"
            "Then the WARNING message identifies both the source AC id and the exact\n"
            "  unresolved component value,\n"
            "And the unresolved value is passed through to the generated components LIST\n"
            "  verbatim."
        ),
    }


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestUnresolvableComponentVerbatim(unittest.TestCase):
    """TKT-500f-17-i: _build_components_list (via generate_ticket_from_ac.py --dry-run)
    must surface an unresolvable component value verbatim AND emit exactly one WARNING
    that identifies both the source AC id and the exact unresolved value.

    All three tests are RED before implementation because the current
    _build_components_list performs no validation against docs/components.json and
    emits no WARNING for values that cannot be resolved — so assertLogs raises
    AssertionError with "no logs of level WARNING or higher triggered on
    generate_ticket_from_ac".
    """

    def test_warning_names_source_ac_id_and_unresolved_value(self):
        # covers: TKT-500f-17-i
        """AC-1: The WARNING for an unresolvable component value must name both
        the source AC id and the exact unresolved value string.

        Must be RED before implementation: current _build_components_list does not
        validate against components.json and emits NO WARNING for unknown component
        values.  assertLogs raises AssertionError("no logs of level WARNING or higher
        triggered on generate_ticket_from_ac").

        After the fix:
          - _build_components_list (or a caller) validates each value against the
            valid graph ids in docs/components.json.
          - For any value not found, it emits a WARNING via the module logger that
            contains BOTH the source AC id AND the unresolved value string.
          - This test asserts exactly 1 such matching WARNING record is captured.
        """
        ac_id = "TKT-500f-17-i-warn-content-fixture"
        ac_data = _make_ac_data([_UNRESOLVABLE])

        with self.assertLogs("generate_ticket_from_ac", level="WARNING") as cm:
            _run_dry_run(ac_data, ac_id=ac_id)

        matching = [
            r
            for r in cm.records
            if ac_id in r.getMessage() and _UNRESOLVABLE in r.getMessage()
        ]
        self.assertEqual(
            len(matching),
            1,
            (
                f"Expected exactly 1 WARNING log record whose message contains BOTH "
                f"the source AC id {ac_id!r} AND the unresolved value {_UNRESOLVABLE!r}. "
                f"Found {len(matching)} matching record(s). "
                f"All captured WARNING records: "
                f"{[r.getMessage() for r in cm.records]!r}."
            ),
        )

    def test_unresolved_value_passed_through_verbatim_not_dropped_or_fabricated(self):
        # covers: TKT-500f-17-i
        """AC-2: The unresolved value must appear verbatim in the generated components
        LIST; it must not be silently dropped nor replaced by a fabricated graph id.

        Must be RED before implementation: assertLogs raises AssertionError because
        no WARNING is emitted, so the context manager itself fails before the
        components-list assertion is reached.

        After the fix:
          - The unresolved value is retained verbatim in the components LIST so the
            downstream Component-vocab CI check surfaces it visibly.
          - A WARNING is emitted (confirmed by assertLogs passing).
          - The value must appear unchanged in components — this assertion then
            confirms the verbatim passthrough (not dropped, not fabricated).
        """
        ac_id = "TKT-500f-17-i-verbatim-fixture"
        ac_data = _make_ac_data([_UNRESOLVABLE])

        with self.assertLogs("generate_ticket_from_ac", level="WARNING") as cm:
            fm = _run_dry_run(ac_data, ac_id=ac_id)

        # AC-2a: The unresolved value must appear verbatim in the components list.
        components = fm.get("components", [])
        self.assertIn(
            _UNRESOLVABLE,
            components,
            (
                f"Expected the unresolved value {_UNRESOLVABLE!r} to appear verbatim "
                f"in the generated components LIST, but it was absent. "
                f"Actual components: {components!r}. "
                "The value must not be silently dropped or replaced by a fabricated "
                "graph id — it should remain visible so the Component-vocab CI check "
                "can surface it."
            ),
        )

        # AC-2b: At least one WARNING mentioning the unresolved value was emitted.
        value_warned = any(_UNRESOLVABLE in r.getMessage() for r in cm.records)
        self.assertTrue(
            value_warned,
            (
                f"Expected a WARNING log record mentioning the unresolved value "
                f"{_UNRESOLVABLE!r}, but no such record was captured. "
                f"All captured WARNING records: "
                f"{[r.getMessage() for r in cm.records]!r}."
            ),
        )

    def test_warning_emitted_at_most_once_per_distinct_value(self):
        # covers: TKT-500f-17-i
        """AC-3: When the same unresolvable value appears more than once in the AC's
        components field, the WARNING must be emitted at most once for that distinct
        value (de-duplication).

        Must be RED before implementation: assertLogs raises AssertionError because
        no WARNING is emitted at all — so the context manager itself fails before the
        de-duplication assertion is reached.

        After the fix:
          - The implementation de-duplicates WARNING emissions per distinct unresolved
            value: even if _UNRESOLVABLE appears twice in the components list, the
            logger emits exactly 1 WARNING for it.
          - assertLogs passes (at least 1 record captured).
          - The subsequent assertEqual(len(matching), 1) confirms de-duplication.
        """
        ac_id = "TKT-500f-17-i-dedup-fixture"
        # The same unresolvable value appears TWICE in the components list.
        ac_data = _make_ac_data([_UNRESOLVABLE, _UNRESOLVABLE])

        with self.assertLogs("generate_ticket_from_ac", level="WARNING") as cm:
            _run_dry_run(ac_data, ac_id=ac_id)

        matching = [r for r in cm.records if _UNRESOLVABLE in r.getMessage()]

        # Exactly 1 WARNING for the distinct unresolved value — not 0, not 2.
        self.assertEqual(
            len(matching),
            1,
            (
                f"Expected exactly 1 WARNING for the distinct unresolved value "
                f"{_UNRESOLVABLE!r} even though it appeared twice in the AC's "
                f"components field. "
                f"Found {len(matching)} matching record(s) — de-duplication "
                f"{'missing (0 warnings)' if len(matching) == 0 else 'not applied (>1 warnings)'}. "
                f"Matching records: {[r.getMessage() for r in matching]!r}."
            ),
        )


if __name__ == "__main__":
    unittest.main()
