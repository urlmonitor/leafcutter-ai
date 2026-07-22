"""
MODULE: test_generate_doc_index_last_updated
GOAL: Verify that generate_doc_index.py emits a ``last_updated`` field in the
    generated INDEX.md YAML frontmatter and preserves it across re-runs (idempotency).
BUSINESS CONTEXT: The check-doc-frontmatter pre-commit hook rejects INDEX.md when
    ``last_updated`` is absent from the frontmatter, causing every commit that
    regenerates INDEX.md via the transform-doc-index hook to fail validation.
    The fix preserves ``last_updated`` from an existing file and falls back to
    the ``created`` value (never to datetime.now()) to maintain idempotency.
ARCHITECTURE: Unit tests exercising generate_index() and write_index() against
    temporary directories.  No I/O to the real docs/ tree.
"""

from __future__ import annotations

import re
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup: unit_tests/commit_guardian/ is 3 levels below the repo root
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import generate_doc_index as gdi  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_frontmatter(content: str) -> dict[str, str]:
    """Extract key→value pairs from the YAML frontmatter of *content*.

    Reads the first ``---`` … ``---`` block and returns a flat dict of
    ``key: value`` string pairs.  Values are stripped of surrounding quotes.

    Args:
        content: Raw text of a generated INDEX.md file.

    Returns:
        Dict mapping each frontmatter key to its raw string value.
    """
    result: dict[str, str] = {}
    if not content.startswith("---"):
        return result
    end = content.find("\n---", 3)
    if end == -1:
        return result
    body = content[4:end]  # skip "---\n"
    for line in body.splitlines():
        m = re.match(r"^(\w+):\s*(.+?)\s*$", line)
        if m:
            result[m.group(1)] = m.group(2).strip("'\"")
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLastUpdatedFieldPresent(unittest.TestCase):
    """Generated INDEX.md frontmatter must contain a ``last_updated:`` field."""

    def test_generate_index_emits_last_updated(self) -> None:
        """generate_index() output must include ``last_updated:`` in the YAML frontmatter.

        Fails before the fix because _HEADER_TEMPLATE had no last_updated field.
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            content = gdi.generate_index(repo_root)

        fm = _parse_frontmatter(content)
        self.assertIn(
            "last_updated",
            fm,
            "generate_index() frontmatter must contain a 'last_updated' field "
            "so that check-doc-frontmatter does not reject INDEX.md. "
            f"Frontmatter keys found: {sorted(fm.keys())}",
        )
        self.assertTrue(
            fm["last_updated"].strip(),
            "The 'last_updated' value must be non-empty.",
        )

    def test_write_index_emits_last_updated(self) -> None:
        """write_index() must produce a file whose frontmatter has ``last_updated:``."""
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            (repo_root / "docs").mkdir(parents=True, exist_ok=True)
            out = gdi.write_index(repo_root)
            content = out.read_text(encoding="utf-8")

        fm = _parse_frontmatter(content)
        self.assertIn(
            "last_updated",
            fm,
            "write_index() output file frontmatter must contain 'last_updated'. "
            f"Frontmatter keys found: {sorted(fm.keys())}",
        )


class TestLastUpdatedIdempotency(unittest.TestCase):
    """Re-running generate_index() must not change ``last_updated``."""

    def test_last_updated_stable_across_reruns(self) -> None:
        """Two consecutive write_index() calls must produce the same last_updated value.

        Confirms that last_updated is preserved from the existing file on the second run
        rather than being reset to datetime.now(), which would break idempotency and
        change the file on every commit.
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            docs_dir = repo_root / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)

            # First run — INDEX.md does not yet exist.
            out1 = gdi.write_index(repo_root)
            content1 = out1.read_text(encoding="utf-8")
            fm1 = _parse_frontmatter(content1)

            self.assertIn(
                "last_updated",
                fm1,
                "First write_index() run must emit a 'last_updated' field.",
            )
            lu1 = fm1["last_updated"]
            self.assertTrue(lu1, "First 'last_updated' value must be non-empty.")

            # Second run — INDEX.md now exists with last_updated already set.
            out2 = gdi.write_index(repo_root)
            content2 = out2.read_text(encoding="utf-8")
            fm2 = _parse_frontmatter(content2)

            self.assertIn(
                "last_updated",
                fm2,
                "Second write_index() run must still emit 'last_updated'.",
            )
            lu2 = fm2["last_updated"]

            self.assertEqual(
                lu1,
                lu2,
                "last_updated must be identical across runs (idempotency). "
                f"Run 1: {lu1!r}, Run 2: {lu2!r}. "
                "If they differ, the generator used datetime.now() on the second run "
                "instead of preserving the existing value.",
            )


class TestLastUpdatedPreservationAndFallback(unittest.TestCase):
    """Preservation from existing file and fallback to ``created`` when absent."""

    def test_last_updated_preserved_from_existing_index(self) -> None:
        """When the existing INDEX.md has last_updated, the new run must preserve it.

        Simulates an existing INDEX.md whose last_updated is a historic date.
        After regeneration, the same date must appear — not today's date.
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            docs_dir = repo_root / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)

            # Write an existing INDEX.md that already has created and last_updated.
            historic_date = "2025-01-01"
            existing_content = (
                "---\n"
                'title: "Documentation Index"\n'
                "type: reference\n"
                "status: active\n"
                f"created: {historic_date}\n"
                f"last_updated: {historic_date}\n"
                "components: []\n"
                'description: "historic"\n'
                "---\n\n"
                "# Documentation Index\n"
            )
            (docs_dir / "INDEX.md").write_text(existing_content, encoding="utf-8")

            # Regenerate.
            out = gdi.write_index(repo_root)
            content = out.read_text(encoding="utf-8")

        fm = _parse_frontmatter(content)
        self.assertEqual(
            fm.get("last_updated"),
            historic_date,
            f"last_updated must be preserved from the existing INDEX.md ({historic_date!r}). "
            f"Got: {fm.get('last_updated')!r}. "
            "The generator must read and preserve last_updated, not reset it to today.",
        )

    def test_last_updated_falls_back_to_created_when_absent(self) -> None:
        """When existing INDEX.md has no last_updated, value falls back to created.

        This is the "first-generation upgrade" scenario: an old INDEX.md has a
        ``created`` date but was generated before last_updated was added.  After
        regeneration, last_updated must equal the preserved created value (not today).
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            docs_dir = repo_root / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)

            historic_created = "2024-06-15"
            # Existing file has created but NO last_updated.
            existing_content = (
                "---\n"
                'title: "Documentation Index"\n'
                "type: reference\n"
                "status: active\n"
                f"created: {historic_created}\n"
                "components: []\n"
                'description: "old index without last_updated"\n'
                "---\n\n"
                "# Documentation Index\n"
            )
            (docs_dir / "INDEX.md").write_text(existing_content, encoding="utf-8")

            # Regenerate.
            out = gdi.write_index(repo_root)
            content = out.read_text(encoding="utf-8")

        fm = _parse_frontmatter(content)
        self.assertIn(
            "last_updated",
            fm,
            "Regeneration of a file without last_updated must still emit last_updated.",
        )
        self.assertEqual(
            fm.get("last_updated"),
            historic_created,
            f"When last_updated is absent from the existing INDEX.md, it must fall back "
            f"to the existing created value ({historic_created!r}), NOT to today's date. "
            f"Got: {fm.get('last_updated')!r}",
        )
        # created must also be preserved.
        self.assertEqual(
            fm.get("created"),
            historic_created,
            f"created must be preserved from the existing INDEX.md ({historic_created!r}). "
            f"Got: {fm.get('created')!r}",
        )


if __name__ == "__main__":
    unittest.main()
