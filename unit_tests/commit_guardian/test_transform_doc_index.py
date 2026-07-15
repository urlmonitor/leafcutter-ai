"""
MODULE: test_transform_doc_index
GOAL: TDD failing test stubs for TICKET-20260715-DocIndexAutoRegen.
      Three areas under test:
        1. generate_doc_index.py emits stable YAML frontmatter (AC-1 — idempotency)
        2. transform_doc_index hook regenerates and restages docs/INDEX.md on a
           docs/ change (AC-2 — restage on change)
        3. transform_doc_index hook is a no-op when no docs/ files are staged
           (AC-2 — no-op guard)
        4. Hook registered in commit_guardian.json before the doc validators (AC-3, AC-4)
BUSINESS CONTEXT: docs/INDEX.md drifts between build.py runs because nothing
      regenerates it at commit time. These tests pin the required behaviour for a
      new pre-commit transform hook that keeps the index fresh automatically.
ARCHITECTURE: All tests are intentionally RED. python-coder must implement:
        - YAML frontmatter block (title, type, status, created, description) in
          scripts/generate_doc_index._HEADER_TEMPLATE, with 'created' preserved
          from the existing file's frontmatter on re-runs.
        - templates/scripts/commit_guardian/transform_doc_index.py with:
            * staged-file scan (docs/*.md, excluding INDEX.md itself)
            * regenerate-and-git-add path when docs files are staged
            * fail-open exit-0 contract
        - transform-doc-index entry in scripts/commit_guardian/commit_guardian.json,
          ordered before check-doc-frontmatter and check-description-field.

====================================================================
DECISION HISTORY
====================================================================
- 2026-07-15 [TICKET-20260715-DocIndexAutoRegen]: Initial TDD stubs (test-writer).
  Tests are red until python-coder implements:
    scripts/generate_doc_index.py — frontmatter block + created preservation
    templates/scripts/commit_guardian/transform_doc_index.py
    scripts/commit_guardian/commit_guardian.json — hook entry + ordering
====================================================================
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_CG_TEMPLATES_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_CG_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "commit_guardian"
_TRANSFORM_DOC_INDEX_PATH = _CG_TEMPLATES_DIR / "transform_doc_index.py"
_COMMIT_GUARDIAN_JSON = _CG_TEMPLATES_DIR / "commit_guardian.json"

# generate_doc_index already exists — import it on module load so test class
# definitions that reference `gdi` are always resolvable.
sys.path.insert(0, str(_SCRIPTS_DIR))
import generate_doc_index as gdi  # noqa: E402


# ---------------------------------------------------------------------------
# Import helper for the not-yet-existing transform module
# ---------------------------------------------------------------------------


def _import_transform_doc_index():
    """Import transform_doc_index from templates/scripts/commit_guardian/.

    Returns:
        The imported module object.

    Raises:
        ImportError: When the module does not yet exist (expected RED state).
    """
    spec = importlib.util.spec_from_file_location(
        "transform_doc_index", _TRANSFORM_DOC_INDEX_PATH
    )
    if spec is None or spec.loader is None:
        raise ImportError(  # noqa: TRY003
            f"Cannot import transform_doc_index: {_TRANSFORM_DOC_INDEX_PATH} "
            "does not exist. python-coder must create this file."
        )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# AC-1: generate_doc_index.py emits stable YAML frontmatter
# ---------------------------------------------------------------------------


class TestGenerateDocIndexFrontmatter(unittest.TestCase):
    """AC-1: generate_index() output must begin with YAML frontmatter that includes
    title, type, status, created, and description fields.  The 'created' field must
    be preserved from the existing docs/INDEX.md on re-runs (idempotency).
    """

    def test_ac1_emits_yaml_frontmatter(self):
        # covers: UNKNOWN
        """AC-1: generate_index() must start with a '---' YAML frontmatter delimiter
        and include title, type, status, created, and description fields.

        Current state: _HEADER_TEMPLATE starts with '# Documentation Index' (no
        frontmatter).  This test fails with AssertionError until python-coder adds
        the frontmatter block.
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            content = gdi.generate_index(repo_root)

        self.assertTrue(
            content.startswith("---\n"),
            "generate_index() output must start with '---\\n' YAML frontmatter delimiter. "
            "Implement a frontmatter block at the top of _HEADER_TEMPLATE in "
            "scripts/generate_doc_index.py.",
        )

        # Split on the closing delimiter to extract the frontmatter body only.
        # Avoid asserting on the full content which also contains the body text.
        closing_idx = content.find("\n---\n", 3)
        self.assertGreater(
            closing_idx,
            0,
            "Frontmatter must be closed by a '\\n---\\n' delimiter after the opening '---\\n'.",
        )
        frontmatter_body = content[4:closing_idx]  # strip leading "---\n"

        required_fields = ("title:", "type:", "status:", "created:", "description:")
        for field in required_fields:
            self.assertIn(
                field,
                frontmatter_body,
                f"YAML frontmatter must contain a '{field}' field (AC-1). "
                f"Frontmatter body was: {frontmatter_body!r}",
            )

    def test_ac1_created_preserved_on_rerun(self):
        # covers: UNKNOWN
        """AC-1: Calling write_index() twice must yield the same 'created' date.

        On the first run 'created' is set to today.  On the second run the
        generator must read the existing INDEX.md, extract its 'created' field,
        and re-emit the same value — not reset it to today.

        This test fails at the first assertIsNotNone because the current output
        has no frontmatter at all.
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            docs_dir = repo_root / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)

            # First run — INDEX.md does not yet exist; 'created' must be set to today.
            out1 = gdi.write_index(repo_root)
            content1 = out1.read_text(encoding="utf-8")

            m1 = re.search(r"^created:\s*(.+)$", content1, re.MULTILINE)
            self.assertIsNotNone(
                m1,
                "First write_index() run must produce a 'created:' field in the frontmatter. "
                "Implement YAML frontmatter in _HEADER_TEMPLATE.",
            )
            created1 = m1.group(1).strip()  # type: ignore[union-attr]
            self.assertTrue(created1, "First 'created' value must be non-empty.")

            # Second run — INDEX.md now exists with 'created: <date>'; that date
            # must survive unchanged.
            out2 = gdi.write_index(repo_root)
            content2 = out2.read_text(encoding="utf-8")

            m2 = re.search(r"^created:\s*(.+)$", content2, re.MULTILINE)
            self.assertIsNotNone(m2, "Second write_index() run must also have 'created:' field.")
            created2 = m2.group(1).strip()  # type: ignore[union-attr]

            self.assertEqual(
                created1,
                created2,
                f"'created' must be identical across runs (idempotency). "
                f"Run 1: {created1!r}, Run 2: {created2!r}",
            )


# ---------------------------------------------------------------------------
# AC-2: transform_doc_index restages INDEX.md when docs files are staged
# ---------------------------------------------------------------------------


class TestTransformDocIndexRestages(unittest.TestCase):
    """AC-2: When at least one staged file is under docs/ (and is not INDEX.md),
    transform_doc_index must regenerate docs/INDEX.md and call 'git add' on it.
    """

    def test_ac2_restages_when_docs_file_staged(self):
        # covers: UNKNOWN
        """AC-2: hook calls 'git add docs/INDEX.md' when a docs/ file is staged.

        Simulates 'git diff --cached --name-only' returning one docs file.
        Asserts that subprocess.run is subsequently called with
        ['git', 'add', ...] targeting docs/INDEX.md.

        This test fails with ImportError until python-coder creates
        templates/scripts/commit_guardian/transform_doc_index.py.
        """
        tdi = _import_transform_doc_index()

        # Staged files: one real docs file (not INDEX.md).
        staged_output = "docs/how-to/some-new-guide.md\n"

        git_add_calls: list[list[str]] = []

        def fake_subprocess_run(cmd, **kwargs):
            mock_result = MagicMock()
            mock_result.returncode = 0
            if cmd[:3] == ["git", "diff", "--cached"]:
                mock_result.stdout = staged_output
            elif cmd[0:2] == ["git", "add"]:
                git_add_calls.append(list(cmd))
                mock_result.stdout = ""
            else:
                mock_result.stdout = ""
            return mock_result

        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            docs_dir = repo_root / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)

            with patch("subprocess.run", side_effect=fake_subprocess_run):
                exit_code = tdi.main(repo_root=repo_root)

        self.assertEqual(
            exit_code,
            0,
            f"transform_doc_index.main() must return 0 (fail-open). Got {exit_code}.",
        )

        # At least one git add call must reference docs/INDEX.md.
        index_add_calls = [
            c for c in git_add_calls
            if any("INDEX.md" in arg for arg in c)
        ]
        self.assertTrue(
            len(index_add_calls) > 0,
            f"Expected 'git add ... docs/INDEX.md' to be called when docs file is staged. "
            f"git add calls seen: {git_add_calls}",
        )

    def test_ac2_fail_open_exits_zero_on_error(self):
        # covers: UNKNOWN
        """AC-2 fail-open contract: main() must return 0 even when an internal error occurs.

        This test fails with ImportError until transform_doc_index.py is created.
        """
        tdi = _import_transform_doc_index()

        def always_raise(cmd, **kwargs):
            raise OSError("simulated git failure")  # noqa: TRY003

        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            with patch("subprocess.run", side_effect=always_raise):
                exit_code = tdi.main(repo_root=repo_root)

        self.assertEqual(
            exit_code,
            0,
            "transform_doc_index.main() must return 0 (fail-open) even when "
            f"subprocess.run raises OSError. Got {exit_code}.",
        )


# ---------------------------------------------------------------------------
# AC-2 no-op: hook does nothing when no docs/ files are staged
# ---------------------------------------------------------------------------


class TestTransformDocIndexNoOp(unittest.TestCase):
    """AC-2 no-op guard: When no docs/ files are staged, transform_doc_index must
    NOT regenerate or restage docs/INDEX.md.
    """

    def test_ac2_noop_when_no_docs_staged(self):
        # covers: UNKNOWN
        """AC-2: When 'git diff --cached' returns no docs/*.md files, the hook must
        not write docs/INDEX.md and must not call 'git add'.

        This test fails with ImportError until transform_doc_index.py is created.
        """
        tdi = _import_transform_doc_index()

        # Staged files: a Python script — no docs/*.md files.
        staged_output = "scripts/some_helper.py\n"
        git_add_calls: list[list[str]] = []

        def fake_subprocess_run(cmd, **kwargs):
            mock_result = MagicMock()
            mock_result.returncode = 0
            if cmd[:3] == ["git", "diff", "--cached"]:
                mock_result.stdout = staged_output
            elif cmd[0:2] == ["git", "add"]:
                git_add_calls.append(list(cmd))
                mock_result.stdout = ""
            else:
                mock_result.stdout = ""
            return mock_result

        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            docs_dir = repo_root / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            index_path = docs_dir / "INDEX.md"
            original_content = "# Sentinel — must not be overwritten\n"
            index_path.write_text(original_content, encoding="utf-8")

            with patch("subprocess.run", side_effect=fake_subprocess_run):
                exit_code = tdi.main(repo_root=repo_root)

            self.assertEqual(exit_code, 0, "main() must return 0 even on no-op path.")

            # INDEX.md must be untouched.
            final_content = index_path.read_text(encoding="utf-8")
            self.assertEqual(
                final_content,
                original_content,
                "docs/INDEX.md must NOT be modified when no docs/ files are staged.",
            )

            # No git add should have been called at all.
            self.assertEqual(
                git_add_calls,
                [],
                f"'git add' must not be called when no docs files are staged. "
                f"Calls seen: {git_add_calls}",
            )

    def test_ac2_index_md_itself_does_not_trigger_rerun(self):
        # covers: UNKNOWN
        """AC-2: Staging INDEX.md itself must NOT trigger a re-run (avoid infinite loop).

        This test fails with ImportError until transform_doc_index.py is created.
        """
        tdi = _import_transform_doc_index()

        # Only INDEX.md itself is staged — the hook must not trigger.
        staged_output = "docs/INDEX.md\n"
        git_add_calls: list[list[str]] = []

        def fake_subprocess_run(cmd, **kwargs):
            mock_result = MagicMock()
            mock_result.returncode = 0
            if cmd[:3] == ["git", "diff", "--cached"]:
                mock_result.stdout = staged_output
            elif cmd[0:2] == ["git", "add"]:
                git_add_calls.append(list(cmd))
                mock_result.stdout = ""
            else:
                mock_result.stdout = ""
            return mock_result

        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            docs_dir = repo_root / "docs"
            docs_dir.mkdir(parents=True, exist_ok=True)
            original_content = "# Sentinel — must not be overwritten\n"
            (docs_dir / "INDEX.md").write_text(original_content, encoding="utf-8")

            with patch("subprocess.run", side_effect=fake_subprocess_run):
                exit_code = tdi.main(repo_root=repo_root)

        self.assertEqual(exit_code, 0, "main() must return 0 on the INDEX.md-only path.")
        self.assertEqual(
            git_add_calls,
            [],
            "Staging INDEX.md itself must NOT cause a further git add call "
            f"(avoid infinite loop). Calls seen: {git_add_calls}",
        )


# ---------------------------------------------------------------------------
# AC-3, AC-4: Hook registered in commit_guardian.json with correct ordering
# ---------------------------------------------------------------------------


class TestTransformDocIndexHookRegistration(unittest.TestCase):
    """AC-3 + AC-4: transform-doc-index must be registered in commit_guardian.json
    and appear before check-doc-frontmatter / check-description-field.
    """

    def _load_hook_ids(self) -> list[str]:
        self.assertTrue(
            _COMMIT_GUARDIAN_JSON.exists(),
            f"commit_guardian.json not found at {_COMMIT_GUARDIAN_JSON}",
        )
        with open(_COMMIT_GUARDIAN_JSON, encoding="utf-8") as fh:
            config = json.load(fh)
        hooks = config.get("hooks_manifest", {}).get("hooks", [])
        return [h.get("id", "") for h in hooks]

    def test_ac4_hook_registered_in_commit_guardian_json(self):
        # covers: UNKNOWN
        """AC-4: 'transform-doc-index' must appear in hooks_manifest.hooks in
        scripts/commit_guardian/commit_guardian.json.

        This test fails with AssertionError until python-coder adds the entry.
        """
        hook_ids = self._load_hook_ids()
        self.assertIn(
            "transform-doc-index",
            hook_ids,
            "Expected 'transform-doc-index' to be registered in "
            "commit_guardian.json hooks_manifest. "
            "Add an entry with id='transform-doc-index' to the hooks list.",
        )

    def test_ac3_hook_runs_before_check_doc_frontmatter(self):
        # covers: UNKNOWN
        """AC-3: transform-doc-index must appear before check-doc-frontmatter
        in hooks_manifest.hooks so its emitted frontmatter survives validation.

        This test fails with AssertionError until python-coder adds the entry
        in the correct position.
        """
        hook_ids = self._load_hook_ids()

        self.assertIn(
            "transform-doc-index",
            hook_ids,
            "transform-doc-index must be registered before ordering can be checked.",
        )

        validator_id = "check-doc-frontmatter"
        if validator_id in hook_ids and "transform-doc-index" in hook_ids:
            t_idx = hook_ids.index("transform-doc-index")
            v_idx = hook_ids.index(validator_id)
            self.assertLess(
                t_idx,
                v_idx,
                f"'transform-doc-index' (position {t_idx}) must appear before "
                f"'{validator_id}' (position {v_idx}) in hooks_manifest.hooks.",
            )

    def test_ac3_hook_runs_before_check_description_field(self):
        # covers: UNKNOWN
        """AC-3: transform-doc-index must appear before check-description-field
        so the description field in the emitted frontmatter survives that validator too.

        This test fails with AssertionError until python-coder adds the entry
        in the correct position.
        """
        hook_ids = self._load_hook_ids()

        self.assertIn(
            "transform-doc-index",
            hook_ids,
            "transform-doc-index must be registered before ordering can be checked.",
        )

        validator_id = "check-description-field"
        if validator_id in hook_ids and "transform-doc-index" in hook_ids:
            t_idx = hook_ids.index("transform-doc-index")
            v_idx = hook_ids.index(validator_id)
            self.assertLess(
                t_idx,
                v_idx,
                f"'transform-doc-index' (position {t_idx}) must appear before "
                f"'{validator_id}' (position {v_idx}) in hooks_manifest.hooks.",
            )


if __name__ == "__main__":
    unittest.main()
