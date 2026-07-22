"""
MODULE: unit_tests/build/test_doc_index_frontmatter.py
GOAL: RED baseline — verify that the DEPLOYED generate_doc_index.py emits a
      ``last_updated`` field in the generated INDEX.md YAML frontmatter, and
      that the real docs/INDEX.md on disk already has this field.

BUSINESS CONTEXT: The pre-commit hook ``transform_doc_index.py`` calls
      ``generate_index()`` from the DEPLOYED ``.leafcutter/scripts/generate_doc_index.py``
      (the workspace-parent deployed copy), NOT from ``scripts/generate_doc_index.py``
      (the source in the repo).  The source was fixed in commit 3a2cb7be5 to add
      ``last_updated`` to ``_HEADER_TEMPLATE``, but the deployed copy was not rebuilt.
      As a result, every doc commit that triggers the transform-doc-index hook regenerates
      INDEX.md WITHOUT ``last_updated``, causing check-doc-frontmatter to reject it and
      forcing SKIP=check-doc-frontmatter on every such commit.

ARCHITECTURE: Two test classes:
      1. TestDeployedGeneratorFrontmatter — imports the deployed generator via
         importlib.util.spec_from_file_location (isolates from the source version)
         and calls generate_index() against a TemporaryDirectory.  Skips gracefully
         when the deployed path does not exist (pure CI environment without a workspace).
      2. TestRealIndexMdFrontmatter — reads the real docs/INDEX.md from the repo tree
         and checks its frontmatter directly.  Runs everywhere (no workspace dependency).

      The source generator supports an ``output_path`` keyword arg in write_index();
      the deployed version also accepts it.  Both write to a user-supplied path, so
      tests can redirect output to a TemporaryDirectory without touching docs/INDEX.md.

      Required fields per docs/FRONTMATTER.md § Required Fields (all architecture docs)
      and scripts/commit_guardian/config.py DOC_FM_REQUIRED_FIELDS_BY_GLOB ``docs/**``:
          title, type, status, created, last_updated, components
"""

from __future__ import annotations

import importlib.util
import re
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

#: Repository root (leafcutter-ai/).
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

#: Workspace parent (leafcutter/), where build.py deploys outputs.
_WORKSPACE = _REPO_ROOT.parent

#: Path to the DEPLOYED generator — the version the pre-commit hook actually calls.
#: This copy is in the workspace's .leafcutter/ build-output directory, NOT in the repo.
_DEPLOYED_GENERATOR_PATH = _WORKSPACE / ".leafcutter" / "scripts" / "generate_doc_index.py"

#: Real docs/INDEX.md — the artifact produced by the deployed hook on every doc commit.
_REAL_INDEX_MD = _REPO_ROOT / "docs" / "INDEX.md"

#: Required frontmatter fields for docs/** per docs/FRONTMATTER.md and config.py.
#: The validator gate (check-doc-frontmatter) requires ALL of these on docs/INDEX.md.
_REQUIRED_DOC_FIELDS = ["title", "type", "status", "created", "last_updated", "components"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_frontmatter(content: str) -> dict[str, str]:
    """Extract key→value pairs from the YAML frontmatter block of *content*.

    Reads the first ``---`` ... ``---`` block and returns a flat dict mapping
    each ``key:`` to its raw string value (surrounding quotes stripped).

    Args:
        content: Raw UTF-8 text of a Markdown file.

    Returns:
        Dict mapping each frontmatter key name to its value string.
        Empty dict when frontmatter is absent or malformed.
    """
    result: dict[str, str] = {}
    if not content.startswith("---"):
        return result
    end = content.find("\n---", 3)
    if end == -1:
        return result
    # Skip the opening "---\n" (4 chars)
    body = content[4:end]
    for line in body.splitlines():
        m = re.match(r"^(\w+):\s*(.+?)\s*$", line)
        if m:
            result[m.group(1)] = m.group(2).strip("'\"")
    return result


def _load_module_from_path(path: Path, module_name: str) -> ModuleType:
    """Load a Python module from an explicit filesystem path via importlib.

    Used to import the DEPLOYED generator independently of the source version,
    avoiding Python module-cache collisions (both are named generate_doc_index).

    Args:
        path: Absolute path to the .py file.
        module_name: Logical name to register in sys.modules.

    Returns:
        The loaded module object.

    Raises:
        ImportError: When the spec cannot be built or the loader is absent.
        FileNotFoundError: When path does not exist.
    """
    if not path.exists():
        raise FileNotFoundError(path)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(module_name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


# ---------------------------------------------------------------------------
# Test class 1: deployed generator output
# ---------------------------------------------------------------------------


class TestDeployedGeneratorFrontmatter(unittest.TestCase):
    """The DEPLOYED .leafcutter/scripts/generate_doc_index.py must emit last_updated.

    RED until the deployed copy is rebuilt from the fixed source (scripts/generate_doc_index.py
    commit 3a2cb7be5).  Skips when the workspace-parent .leafcutter/ tree does not exist
    (plain CI checkout without a self-hosted workspace).
    """

    #: Loaded deployed generator module (set in setUpClass).
    _gdi: ModuleType | None = None
    _skip_reason: str = ""

    @classmethod
    def setUpClass(cls) -> None:
        """Attempt to load the deployed generator.  Record failure for skip."""
        try:
            cls._gdi = _load_module_from_path(
                _DEPLOYED_GENERATOR_PATH,
                "generate_doc_index_deployed",
            )
        except (FileNotFoundError, ImportError) as exc:
            cls._gdi = None
            cls._skip_reason = str(exc)

    def _require_deployed_gdi(self) -> ModuleType:
        """Skip this test when the deployed generator is not reachable."""
        if self._gdi is None:
            self.skipTest(
                f"Deployed generator not accessible — skipping: {self._skip_reason}"
            )
        return self._gdi  # type: ignore[return-value]

    def test_deployed_generator_emits_last_updated(self) -> None:
        # covers: UNKNOWN
        """Deployed generate_doc_index.generate_index() must include last_updated in frontmatter.

        RED: the deployed _HEADER_TEMPLATE at .leafcutter/scripts/generate_doc_index.py
        does not contain a ``last_updated: {last_updated}`` substitution slot.  The
        generated frontmatter therefore omits last_updated, causing check-doc-frontmatter
        to reject INDEX.md on every doc commit.

        GREEN when: the deployed copy is rebuilt from the fixed source, which adds
        ``last_updated: {last_updated}`` to _HEADER_TEMPLATE and a
        ``_extract_last_updated()`` fallback chain.

        What to implement:
          1. Run ``python leafcutter-ai/scripts/build.py --target-dir .`` from the
             workspace parent (or equivalent rebuild step) to redeploy the fixed
             scripts/generate_doc_index.py to .leafcutter/scripts/.
          2. Regenerate docs/INDEX.md: ``python scripts/generate_doc_index.py``.
          3. Commit both .leafcutter/scripts/generate_doc_index.py and docs/INDEX.md.
        """
        gdi = self._require_deployed_gdi()
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            content = gdi.generate_index(repo_root)

        fm = _parse_frontmatter(content)
        self.assertIn(
            "last_updated",
            fm,
            (
                f"Deployed .leafcutter/scripts/generate_doc_index.generate_index() "
                f"must emit a 'last_updated:' field in the YAML frontmatter.  "
                f"Fields found: {sorted(fm.keys())}.  "
                f"The deployed _HEADER_TEMPLATE is missing the last_updated slot — "
                f"rebuild from the fixed source (scripts/generate_doc_index.py)."
            ),
        )

    def test_deployed_generator_last_updated_is_non_empty(self) -> None:
        # covers: UNKNOWN
        """last_updated value in deployed generator output must be a non-empty string.

        A blank or null last_updated is not accepted by the check-doc-frontmatter gate.
        After the fix, last_updated falls back to the 'created' value (never to
        datetime.now() on repeated runs), keeping the generator idempotent.
        """
        gdi = self._require_deployed_gdi()
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            content = gdi.generate_index(repo_root)

        fm = _parse_frontmatter(content)
        if "last_updated" not in fm:
            # Let test_deployed_generator_emits_last_updated report the missing field
            self.skipTest("last_updated absent — covered by test_deployed_generator_emits_last_updated")
        self.assertTrue(
            fm["last_updated"].strip(),
            (
                f"Deployed generator emitted an empty last_updated value. "
                f"After the fix, last_updated should equal the 'created' date "
                f"(or a preserved existing value) rather than an empty string."
            ),
        )

    def test_deployed_generator_all_required_fields_present(self) -> None:
        # covers: UNKNOWN
        """Deployed generator output must contain ALL doc frontmatter required fields.

        Required fields per docs/FRONTMATTER.md § Required Fields and
        scripts/commit_guardian/config.py DOC_FM_REQUIRED_FIELDS_BY_GLOB 'docs/**':
            title, type, status, created, last_updated, components

        RED: the deployed version omits last_updated.
        GREEN: rebuilt deployed version includes all required fields.
        """
        gdi = self._require_deployed_gdi()
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            content = gdi.generate_index(repo_root)

        fm = _parse_frontmatter(content)
        missing = [f for f in _REQUIRED_DOC_FIELDS if f not in fm]
        self.assertEqual(
            missing,
            [],
            (
                f"Deployed generate_doc_index output is missing required frontmatter "
                f"fields: {missing}.  Fields found: {sorted(fm.keys())}.  "
                f"Per docs/FRONTMATTER.md, docs/** requires: {_REQUIRED_DOC_FIELDS}."
            ),
        )


# ---------------------------------------------------------------------------
# Test class 2: real docs/INDEX.md on disk
# ---------------------------------------------------------------------------


class TestRealIndexMdFrontmatter(unittest.TestCase):
    """The real docs/INDEX.md on disk must have all required frontmatter fields.

    RED until: the fixed deployed generator is used to regenerate docs/INDEX.md
    and the result is committed.
    GREEN when: docs/INDEX.md contains last_updated (and all other required fields).
    """

    def _read_real_index(self) -> str:
        """Read and return the content of the real docs/INDEX.md."""
        self.assertTrue(
            _REAL_INDEX_MD.exists(),
            f"docs/INDEX.md does not exist at {_REAL_INDEX_MD} — "
            f"run: python scripts/generate_doc_index.py",
        )
        return _REAL_INDEX_MD.read_text(encoding="utf-8")

    def test_real_index_md_has_last_updated(self) -> None:
        # covers: UNKNOWN
        """docs/INDEX.md on disk must contain a last_updated frontmatter field.

        RED: the current docs/INDEX.md was generated by the deployed generator
        that omits last_updated.  The check-doc-frontmatter gate rejects this file.

        GREEN when: docs/INDEX.md is regenerated by the fixed generator and committed.

        Regression check: once green, this test prevents future regressions where
        the generator is re-deployed without last_updated.
        """
        content = self._read_real_index()
        fm = _parse_frontmatter(content)
        self.assertIn(
            "last_updated",
            fm,
            (
                f"docs/INDEX.md is missing 'last_updated' in its YAML frontmatter.  "
                f"Fields found: {sorted(fm.keys())}.  "
                f"Regenerate with the fixed generator: "
                f"python scripts/generate_doc_index.py"
            ),
        )

    def test_real_index_md_has_all_required_fields(self) -> None:
        # covers: UNKNOWN
        """docs/INDEX.md must contain ALL fields required by check-doc-frontmatter.

        Required: title, type, status, created, last_updated, components.
        Per docs/FRONTMATTER.md § Required Fields and config.py DOC_FM_REQUIRED_FIELDS.
        """
        content = self._read_real_index()
        fm = _parse_frontmatter(content)
        missing = [f for f in _REQUIRED_DOC_FIELDS if f not in fm]
        self.assertEqual(
            missing,
            [],
            (
                f"docs/INDEX.md frontmatter is missing required fields: {missing}.  "
                f"Fields found: {sorted(fm.keys())}.  "
                f"Per docs/FRONTMATTER.md, docs/** requires: {_REQUIRED_DOC_FIELDS}.  "
                f"Fix: regenerate docs/INDEX.md using the rebuilt deployed generator."
            ),
        )

    def test_real_index_md_has_frontmatter_at_all(self) -> None:
        # covers: UNKNOWN
        """docs/INDEX.md must open with a YAML frontmatter block delimited by ---."""
        content = self._read_real_index()
        self.assertTrue(
            content.startswith("---"),
            (
                "docs/INDEX.md does not start with a YAML frontmatter block (---).  "
                "The check-doc-frontmatter gate requires frontmatter on all docs/**/*.md files."
            ),
        )
        end = content.find("\n---", 3)
        self.assertGreater(
            end,
            3,
            "docs/INDEX.md frontmatter block has no closing --- delimiter.",
        )

    def test_real_index_md_last_updated_is_iso8601_date(self) -> None:
        # covers: UNKNOWN
        """last_updated in docs/INDEX.md must be a valid ISO-8601 date (YYYY-MM-DD).

        RED: last_updated is absent from the current file (caught by test_real_index_md_has_last_updated).
        GREEN when: last_updated is present and has the format YYYY-MM-DD per
        docs/FRONTMATTER.md § Required Fields.
        """
        content = self._read_real_index()
        fm = _parse_frontmatter(content)
        if "last_updated" not in fm:
            self.skipTest("last_updated absent — covered by test_real_index_md_has_last_updated")
        date_str = fm["last_updated"]
        self.assertRegex(
            date_str,
            r"^\d{4}-\d{2}-\d{2}$",
            (
                f"docs/INDEX.md last_updated value {date_str!r} is not a valid "
                f"ISO-8601 date (YYYY-MM-DD).  Per docs/FRONTMATTER.md, the format "
                f"must be YYYY-MM-DD."
            ),
        )


if __name__ == "__main__":
    unittest.main()
