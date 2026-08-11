"""
MODULE: test_bo_2200c_4_i
GOAL: RED tests for BO-2200c-4-i — heterogeneous doc_links (bare strings and
    objects with missing optional fields) handled gracefully.
BUSINESS CONTEXT: doc_links entries may be plain path strings (not dict objects)
    or dicts missing optional fields like 'relevance' or 'status'. Currently bare
    strings are silently skipped (the continue statement). The fix must surface
    bare strings with just their path and must not crash the generator.
ARCHITECTURE: Tests call _build_doc_links_cross_link_lines directly with mixed
    doc_links shapes to verify correct rendering without fabricated metadata or None values.

test_bare_path_doc_link_surfaced_without_crash is RED before the fix:
    the current code does 'if not isinstance(link, dict): continue' which silently
    drops bare string entries. The path is absent from the result.

test_object_missing_optional_field_omits_absent may already be GREEN (the
    existing code already guards each metadata field with 'if relationship:' etc.),
    but is included as a regression guard per the AC spec.

Target file to implement: scripts/ac_store/generate_ticket_from_ac.py
AC source: docs/acceptance-criteria/build-orchestration/
           BO-2200-documentation-coverage-guarantee/BO-2200c-4-i.yaml
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import _build_doc_links_cross_link_lines  # noqa: E402


# ---------------------------------------------------------------------------
# TestBarePathDocLinkSurfaced
# BO-2200c-4-i
# ---------------------------------------------------------------------------


class TestBarePathDocLinkSurfaced(unittest.TestCase):
    """BO-2200c-4-i: A plain-string doc_links entry is surfaced with its path.

    RED before implementation: _build_doc_links_cross_link_lines has
    'if not isinstance(link, dict): continue' which silently drops all bare
    string entries. The path never appears in the result.

    Fix: detect bare strings before the isinstance(link, dict) guard; surface
    them as bare path bullets ('- <path>') so long as they are not http URLs
    and are non-empty.
    """

    def test_bare_path_doc_link_surfaced_without_crash(self) -> None:
        # covers: BO-2200c-4-i
        """A plain-string doc_links entry is surfaced with just its path and
        does not crash the generator.

        Input: doc_links containing a single bare string path.
        Expected: the result list contains an entry with the path.
        No fabricated metadata (relationship/status/relevance) is emitted.

        Red state (current): bare strings hit 'if not isinstance(link, dict): continue'
        and are dropped from the result. The result list is empty.

        Green state (after fix): the path appears in the result list as a bare bullet.
        """
        doc_links = ["docs/reference/api-schema.md"]

        # Must not raise.
        result = _build_doc_links_cross_link_lines(doc_links)

        self.assertIsInstance(result, list, "Must return a list, not raise.")
        joined = "\n".join(result)
        self.assertIn(
            "docs/reference/api-schema.md",
            joined,
            "The bare-string path 'docs/reference/api-schema.md' must appear in the "
            "result. Currently it is silently dropped by the 'not isinstance(link, dict)' "
            "guard.\n\n"
            f"Actual result: {result}",
        )

    def test_bare_string_http_url_skipped(self) -> None:
        # covers: BO-2200c-4-i
        """A bare-string doc_links entry that is an http URL is skipped (not surfaced).

        This confirms the skip-http rule applies to bare strings as well as dict entries.
        """
        doc_links = ["https://example.com/doc"]

        result = _build_doc_links_cross_link_lines(doc_links)

        self.assertNotIn(
            "https://example.com/doc",
            "\n".join(result),
            "HTTP URL bare strings must be skipped, not surfaced.\n"
            f"Actual result: {result}",
        )

    def test_mixed_bare_string_and_dict_both_surfaced(self) -> None:
        # covers: BO-2200c-4-i
        """A doc_links list mixing a bare string and a dict entry surfaces both.

        Red state: the bare string is dropped; only the dict entry appears.
        Green state: both the bare string path and the dict entry path appear.
        """
        doc_links = [
            "docs/reference/legacy-path.md",
            {
                "path": "docs/architecture/components/build-orchestration.md",
                "relationship": "describes",
                "status": "exists",
            },
        ]

        result = _build_doc_links_cross_link_lines(doc_links)

        joined = "\n".join(result)
        self.assertIn(
            "docs/reference/legacy-path.md",
            joined,
            "Bare string entry 'docs/reference/legacy-path.md' must be surfaced.\n"
            f"Actual result: {result}",
        )
        self.assertIn(
            "docs/architecture/components/build-orchestration.md",
            joined,
            "Dict entry path must still be surfaced alongside the bare string.\n"
            f"Actual result: {result}",
        )


# ---------------------------------------------------------------------------
# TestObjectMissingOptionalFieldOmitsAbsent
# BO-2200c-4-i
# ---------------------------------------------------------------------------


class TestObjectMissingOptionalFieldOmitsAbsent(unittest.TestCase):
    """BO-2200c-4-i: Object doc_links entries missing optional fields are surfaced
    with only the fields they have; absent fields produce neither 'None' nor empty values.

    NOTE: This test is expected to be GREEN already with the current implementation
    (the existing code guards each metadata field with 'if relationship:' etc.).
    It is retained as a regression guard per the AC spec: the fix for bare strings
    must not break correct object handling.
    """

    def test_object_missing_optional_field_omits_absent(self) -> None:
        # covers: BO-2200c-4-i
        """An object doc_links entry missing 'relevance' and 'status' is surfaced
        with only the fields it has. No 'None' or empty-value output is emitted.

        Input: dict with 'path' and 'relationship' only (no status, no relevance).
        Expected:
          - Path appears in the result.
          - 'relationship: describes' appears.
          - 'status:' does NOT appear (absent field omitted).
          - 'relevance:' does NOT appear (absent field omitted).
          - 'None' does NOT appear anywhere in the result.
        """
        doc_links = [
            {
                "path": "docs/reference/bar.md",
                "relationship": "describes",
                # Intentionally no 'status', no 'relevance'
            }
        ]

        result = _build_doc_links_cross_link_lines(doc_links)

        self.assertIsInstance(result, list)
        joined = "\n".join(result)

        self.assertIn(
            "docs/reference/bar.md",
            joined,
            f"Path must appear in result.\nActual: {result}",
        )
        self.assertIn(
            "relationship: describes",
            joined,
            f"'relationship: describes' must appear.\nActual: {result}",
        )
        self.assertNotIn(
            "None",
            joined,
            f"'None' must not appear in result.\nActual: {result}",
        )
        self.assertNotIn(
            "status:",
            joined,
            "Absent 'status' field must not produce 'status:' in output.\n"
            f"Actual: {result}",
        )
        self.assertNotIn(
            "relevance:",
            joined,
            "Absent 'relevance' field must not produce 'relevance:' in output.\n"
            f"Actual: {result}",
        )


if __name__ == "__main__":
    unittest.main()
