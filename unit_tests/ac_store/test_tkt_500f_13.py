"""
MODULE: test_tkt_500f_13
GOAL: RED test stubs for TKT-500f-13. Verifies that generate_ticket_from_ac.py
      normalises the generated ticket's ``components`` LIST to the
      components.json underscore graph id (e.g. ``build_orchestration``) rather
      than copying the scalar kebab namespace key (``build-orchestration``)
      verbatim.

      Both tests call main() with --dry-run and a minimal fixture AC whose
      ``component`` scalar is the kebab namespace key ``build-orchestration``,
      then parse the YAML frontmatter from stdout to inspect the ``components``
      LIST.

      These tests are intentionally RED before the fix.  The current code at
      generate_ticket_from_ac.py line ~1054 does:
          "components": [ac.get("component", "unknown")],
      which copies the kebab scalar directly — so the generated LIST is
      ``["build-orchestration"]``, not ``["build_orchestration"]``.

TICKET: TICKET-20260720-TKT-500f-13.md
COVERS: TKT-500f-13
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
# Fixture AC data shared across tests
# ---------------------------------------------------------------------------

_BUILD_ORCHESTRATION_AC: dict = {
    "title": "Build-orchestration AC fixture — TKT-500f-13 components LIST normalisation",
    "level": "L2",
    "status": "active",
    "work_status": "todo",
    "assigned_agent": "python-coder",
    # component scalar uses the KEBAB namespace key (index.yaml) — NOT the
    # underscore graph id.  The current code copies this verbatim into the
    # components LIST, producing ["build-orchestration"] instead of
    # ["build_orchestration"].
    "component": "build-orchestration",
    "estimated_complexity": "S",
    "change_target": "pipeline",
    "risk_surface": "internal",
    "it_requirements": {
        "reference_file_path": "scripts/ac_store/generate_ticket_from_ac.py",
    },
    "criteria": (
        "Given a leaf AC whose component is the kebab namespace key build-orchestration,\n"
        "When a ticket is generated from that AC by generate_ticket_from_ac.py,\n"
        "Then the generated ticket's components LIST contains build_orchestration "
        "(the underscore graph id from components.json),\n"
        "And the kebab namespace key build-orchestration is NOT copied into the LIST."
    ),
}


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


class TestComponentsListNormalisation(unittest.TestCase):
    """TKT-500f-13: generated ticket's components LIST must use the underscore
    graph id, not the kebab namespace scalar.
    """

    def test_generated_components_list_uses_underscore_graph_id(self):
        # covers: TKT-500f-13
        """AC-1: generated ticket's components LIST contains the underscore graph id.

        Generate a ticket for a fixture AC whose component is 'build-orchestration'
        (kebab namespace key); assert the generated ticket's frontmatter
        ``components`` LIST equals ``['build_orchestration']`` (underscore graph id).

        Must be RED before the fix: the current _build_frontmatter at line ~1054
        does ``"components": [ac.get("component", "unknown")]``, which produces
        ``["build-orchestration"]`` — the kebab scalar, NOT the underscore id.

        After the fix, the components LIST must be normalised using the
        MIGRATION_MAP from scripts/migrate_component_vocab.py (or by preferring
        the AC's own ``components`` LIST if present).
        """
        fm = _run_dry_run(_BUILD_ORCHESTRATION_AC, ac_id="TKT-500f-13-build-orch-fixture")
        components = fm.get("components")

        self.assertEqual(
            components,
            ["build_orchestration"],
            (
                "The generated ticket's 'components' LIST must be ['build_orchestration'] "
                "(underscore graph id from components.json / MIGRATION_MAP), "
                f"but got {components!r}. "
                "The current _build_frontmatter copies the scalar kebab 'component' key "
                "verbatim ('build-orchestration') into the LIST. "
                "python-coder must apply the MIGRATION_MAP normalisation from "
                "scripts/migrate_component_vocab.py at generation time."
            ),
        )

    def test_two_axis_taxonomy_preserved(self):
        # covers: TKT-500f-13
        """AC-2 & AC-3: two-axis taxonomy preserved — kebab scalar kept separate from
        the underscore LIST.

        Assert (a) the generated ``components`` LIST contains the underscore graph id
        ``'build_orchestration'``, and (b) the kebab namespace key
        ``'build-orchestration'`` is NOT present in the LIST (the two-axis taxonomy
        requires these to be separate surfaces).

        Must be RED before the fix: the current code produces
        ``["build-orchestration"]``, which fails both:
        - assertion (a): ``"build_orchestration" not in ["build-orchestration"]``
        - assertion (b): ``"build-orchestration" in ["build-orchestration"]``
        """
        fm = _run_dry_run(_BUILD_ORCHESTRATION_AC, ac_id="TKT-500f-13-two-axis-fixture")
        components = fm.get("components", [])

        self.assertIn(
            "build_orchestration",
            components,
            (
                "The generated ticket's 'components' LIST must contain the underscore "
                "graph id 'build_orchestration', but it was absent. "
                f"Actual components: {components!r}. "
                "The fix must normalise the kebab scalar 'build-orchestration' → "
                "'build_orchestration' via MIGRATION_MAP before writing the LIST."
            ),
        )

        self.assertNotIn(
            "build-orchestration",
            components,
            (
                "The kebab namespace key 'build-orchestration' must NOT appear in the "
                "generated ticket's 'components' LIST. "
                f"Actual components: {components!r}. "
                "The two-axis taxonomy requires the LIST to carry only underscore "
                "graph ids; the kebab scalar belongs only to the source AC's "
                "'component' field (index.yaml namespace), not the generated LIST."
            ),
        )


if __name__ == "__main__":
    unittest.main()
