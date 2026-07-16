"""
MODULE: test_tkt_500f_9
GOAL: RED test stubs for TKT-500f-9.  Verifies that generate_ticket_from_ac.py
      produces a ticket frontmatter that includes an ac_traceability entry
      naming both the AC id and the store path, in addition to (not replacing)
      the bare source_ac scalar.

      All three tests call main() with --dry-run and a minimal fixture AC, then
      parse the YAML frontmatter from stdout to inspect the ac_traceability field.
      Each test will be RED before implementation because _build_frontmatter
      (near line 900 of generate_ticket_from_ac.py) only emits source_ac as a
      bare scalar and does NOT yet emit ac_traceability.

TICKET: TICKET-20260715-TKT-500f-9.md
COVERS: TKT-500f-9
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
# Shared fixture AC data (minimal valid AC for dry-run generation)
# ---------------------------------------------------------------------------

_FIXTURE_AC_DATA: dict = {
    "title": "ac_traceability test fixture — TKT-500f-9",
    "level": "L2",
    "status": "active",
    "work_status": "todo",
    "criteria": (
        "Given a fixture AC with a known store path\n"
        "When a ticket is generated from it\n"
        "Then the frontmatter carries an ac_traceability entry with id and path."
    ),
}


# ---------------------------------------------------------------------------
# Helper: run --dry-run and return the parsed frontmatter dict
# ---------------------------------------------------------------------------


def _run_dry_run(ac_data: dict, ac_id: str = "TKT-500f-9-fixture") -> dict:
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
        # Place the AC in a sub-directory mirroring the store layout.
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


class TestAcTraceabilityFrontmatter(unittest.TestCase):
    """TKT-500f-9: frontmatter must carry ac_traceability with id and store path."""

    def test_frontmatter_has_ac_traceability_id_and_path(self):
        # covers: TKT-500f-9
        """Generate a ticket from a fixture AC; assert frontmatter ac_traceability
        contains both the AC id and the store path.

        Must be RED before implementation: _build_frontmatter currently emits only
        a bare source_ac scalar (line 900 in generate_ticket_from_ac.py) and does
        NOT emit an ac_traceability entry.  After the fix, the frontmatter must
        carry ac_traceability: {id: <ac_id>, path: <store_path>} in addition to
        the bare source_ac.
        """
        ac_id = "TKT-500f-9-trace-fixture"
        fm = _run_dry_run(_FIXTURE_AC_DATA, ac_id=ac_id)

        self.assertIn(
            "ac_traceability",
            fm,
            "frontmatter must contain an 'ac_traceability' entry — currently absent "
            "because _build_frontmatter only emits source_ac scalar (line 900). "
            "Implementation must add ac_traceability: {id, path}.",
        )
        traceability = fm["ac_traceability"]
        self.assertIn(
            "id",
            traceability,
            "ac_traceability must have an 'id' key naming the source AC id.",
        )
        self.assertIn(
            "path",
            traceability,
            "ac_traceability must have a 'path' key naming the repo-root-relative "
            "store path to the source AC YAML.",
        )
        self.assertEqual(
            traceability["id"],
            ac_id,
            f"ac_traceability.id must equal the AC id '{ac_id}'.",
        )

    def test_source_ac_scalar_still_present(self):
        # covers: TKT-500f-9
        """Assert the bare source_ac scalar is still emitted alongside the new
        ac_traceability entry (additive, not a replacement).

        The current code emits source_ac: <id> (a bare scalar) but no
        ac_traceability.  After the fix, BOTH must be present: source_ac for
        backward-compat consumers and ac_traceability for the gate consumers.

        This test fails at the second assertIn because ac_traceability is absent —
        the 'alongside / additive' requirement is not yet satisfied.
        """
        ac_id = "TKT-500f-9-scalar-fixture"
        fm = _run_dry_run(_FIXTURE_AC_DATA, ac_id=ac_id)

        # source_ac must still be present as a bare string scalar
        self.assertIn(
            "source_ac",
            fm,
            "Bare source_ac scalar must still be present in frontmatter "
            "(backward-compat with consumers that read source_ac directly).",
        )
        self.assertIsInstance(
            fm.get("source_ac"),
            str,
            "source_ac must remain a bare string scalar, not a dict or other type.",
        )

        # ac_traceability must ALSO be present (additive — not a replacement).
        # This assertion is the RED trigger: ac_traceability is not yet emitted.
        self.assertIn(
            "ac_traceability",
            fm,
            "ac_traceability must be present ALONGSIDE the bare source_ac "
            "(additive, not a replacement).  Currently absent — implementation "
            "must add it without removing the existing source_ac scalar.",
        )

    def test_traceability_path_resolves_to_source_file(self):
        # covers: TKT-500f-9
        """Assert the ac_traceability store path resolves to the actual source AC
        YAML file on disk.

        Writes an AC to a known location in a temp directory, generates the ticket
        with --dry-run, then verifies that the ac_traceability.path field (treated
        as repo-root-relative) points to the AC YAML file that was written.

        Must be RED before implementation: ac_traceability is not yet emitted, so
        the assertIn('ac_traceability', fm) assertion fails first.

        After implementation the path resolution assertion enforces that the emitted
        path is correct and actually resolvable — not a placeholder or wrong path.
        """
        ac_id = "TKT-500f-9-path-resolve-fixture"
        ac_yaml_data = dict(_FIXTURE_AC_DATA)
        ac_yaml_data["id"] = ac_id

        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            ac_root = tmppath / "docs" / "acceptance-criteria" / "fixture-component"
            ac_root.mkdir(parents=True)

            ac_file = ac_root / f"{ac_id}.yaml"
            ac_file.write_text(
                yaml.dump(ac_yaml_data, allow_unicode=True),
                encoding="utf-8",
            )

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

            # Parse the frontmatter block (between the two "---" markers)
            parts = output.split("---")
            fm: dict = {}
            if len(parts) >= 3:
                try:
                    parsed = yaml.safe_load(parts[1])
                    if isinstance(parsed, dict):
                        fm = parsed
                except yaml.YAMLError:
                    pass

            # This assertion will FAIL before implementation (ac_traceability absent)
            self.assertIn(
                "ac_traceability",
                fm,
                "ac_traceability must be present in frontmatter so that "
                "ac-validator and ac-fulfillment-gate can resolve the source AC "
                "without scanning the whole store.  Currently absent.",
            )

            store_path: str = fm["ac_traceability"]["path"]

            # The store path must be repo-root-relative.  In this test, tmppath
            # acts as the repo root (the AC is placed at
            # {tmppath}/docs/acceptance-criteria/fixture-component/{ac_id}.yaml).
            resolved = tmppath / store_path
            self.assertTrue(
                resolved.exists(),
                f"ac_traceability.path '{store_path}' does not resolve to an "
                f"existing file when joined to the repo root '{tmppath}'. "
                f"Full resolved path: {resolved}. "
                "The path must be repo-root-relative and point to the actual "
                "source AC YAML so gate consumers can read it directly.",
            )


if __name__ == "__main__":
    unittest.main()
