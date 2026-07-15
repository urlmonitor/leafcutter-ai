"""
MODULE: test_tkt_500f_8
GOAL: RED test stubs for TKT-500f-8.  Verifies that generate_ticket_from_ac.py
      produces a files_touched list that is the sorted, de-duplicated union of
      the AC's it_requirements.reference_file_path and its doc_links edit-surface
      paths, while excluding doc_links whose relationship is 'describes'.

      All three tests call main() with --dry-run and a minimal fixture AC, then
      parse the YAML frontmatter from stdout to inspect files_touched.  This
      exercises the complete production code path (lines 1419 and 1453 in
      generate_ticket_from_ac.py).

TICKET: TICKET-20260715-TKT-500f-8.md
COVERS: TKT-500f-8
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


def _run_dry_run(ac_data: dict, ac_id: str = "TKT-500f-8-fixture") -> dict:
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


class TestFilesTouchedUnionBehavior(unittest.TestCase):
    """TKT-500f-8: files_touched must union it_requirements and doc_links edit surfaces."""

    def test_files_touched_unions_it_requirements_and_doc_links(self):
        # covers: TKT-500f-8
        """Generate a ticket from a fixture AC whose it_requirements.reference_file_path=X
        and doc_links names edit-surface Y; assert files_touched == sorted-unique {X, Y}.

        Must be RED before implementation because the current code at lines 1419/1453
        computes files_touched as _extract_local_paths(ac.get("doc_links") or []),
        which ignores it_requirements.reference_file_path entirely.  After the fix,
        files_touched must be the sorted, de-duplicated union of both sources.
        """
        it_req_path = "scripts/ac_store/generate_ticket_from_ac.py"  # X: from it_requirements
        doc_link_path = "docs/reference/ac-schema.md"                 # Y: from doc_links (edit)

        ac_data = {
            "title": "Union test fixture — TKT-500f-8",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "it_requirements": {
                "reference_file_path": it_req_path,
            },
            "doc_links": [
                {"path": doc_link_path, "relationship": "constrains"},
            ],
            "criteria": (
                "Given a fixture AC\n"
                "Then files_touched contains the it_requirements path\n"
                "And files_touched contains the doc_links edit-surface path."
            ),
        }

        fm = _run_dry_run(ac_data, ac_id="TKT-500f-8-union-fixture")
        actual_files = fm.get("files_touched", [])

        expected = sorted({it_req_path, doc_link_path})

        self.assertEqual(
            sorted(actual_files),
            expected,
            f"files_touched must be the sorted union of it_requirements "
            f"({it_req_path!r}) and doc_links ({doc_link_path!r}). "
            f"Got: {actual_files}. "
            "The current code ignores it_requirements.reference_file_path; "
            "implementation must union both edit-surface sources."
        )

    def test_files_touched_dedups_shared_path(self):
        # covers: TKT-500f-8
        """AC where reference_file_path equals a doc_links edit-surface path; assert
        that path appears exactly once in files_touched.

        When the union logic is implemented without deduplication, the shared path
        would appear twice ([shared, shared]) and count == 2 would fail this test.
        The correct implementation deduplicates so the path appears exactly once.

        NOTE: This test may pass before implementation (the current code produces
        count=1 from doc_links alone, not from a real union).  It is included as a
        regression guard: it will fail against a naive union-without-dedup implementation.
        See red_baseline note for details.
        """
        shared_path = "scripts/ac_store/generate_ticket_from_ac.py"

        ac_data = {
            "title": "Dedup test fixture — TKT-500f-8",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "it_requirements": {
                "reference_file_path": shared_path,  # same path as in doc_links below
            },
            "doc_links": [
                # shared_path appears in BOTH sources; must be deduplicated
                {"path": shared_path, "relationship": "constrains"},
            ],
            "criteria": (
                "Given a fixture AC whose it_requirements path equals a doc_links path\n"
                "Then that path appears exactly once in files_touched."
            ),
        }

        fm = _run_dry_run(ac_data, ac_id="TKT-500f-8-dedup-fixture")
        actual_files = fm.get("files_touched", [])

        count = actual_files.count(shared_path)
        self.assertEqual(
            count,
            1,
            f"'{shared_path}' must appear exactly once in files_touched "
            f"(deduplication required when the same path comes from both "
            f"it_requirements and doc_links). Got count={count} in {actual_files}."
        )

    def test_describes_doc_links_excluded_from_files_touched(self):
        # covers: TKT-500f-8
        """AC carrying a doc_links entry with relationship=describes; assert that
        path is NOT added to files_touched.

        Must be RED before implementation because the current _extract_local_paths
        function includes ALL local doc_links paths regardless of the relationship
        field (it only filters out URLs starting with 'http').  After the fix,
        doc_links with relationship=describes must be excluded from files_touched.
        """
        edit_path = "scripts/ac_store/generate_ticket_from_ac.py"
        describes_path = "docs/architecture/adrs/ADR-010-ac-store-as-authoritative-backlog.md"

        ac_data = {
            "title": "Describes-exclusion test fixture — TKT-500f-8",
            "level": "L2",
            "status": "active",
            "work_status": "todo",
            "it_requirements": {
                "reference_file_path": edit_path,
            },
            "doc_links": [
                {"path": edit_path, "relationship": "constrains"},   # INCLUDED in files_touched
                {"path": describes_path, "relationship": "describes"},  # EXCLUDED from files_touched
            ],
            "criteria": (
                "Given a fixture AC with a doc_links entry whose relationship is 'describes'\n"
                "Then that path does NOT appear in files_touched."
            ),
        }

        fm = _run_dry_run(ac_data, ac_id="TKT-500f-8-describes-fixture")
        actual_files = fm.get("files_touched", [])

        self.assertNotIn(
            describes_path,
            actual_files,
            f"'{describes_path}' has relationship=describes and must NOT appear in "
            f"files_touched.  Got: {actual_files}. "
            "The current _extract_local_paths does not filter by relationship; "
            "implementation must exclude doc_links whose relationship is 'describes' "
            "(and 'related')."
        )


if __name__ == "__main__":
    unittest.main()
