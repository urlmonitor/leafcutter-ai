"""
MODULE: test_transform_hooks_and_autofix_emission
GOAL: TDD red-baseline stubs for ticket 02_transform_tier.md.
    Seven tests targeting the 7 acceptance criteria that python-coder must
    make green:
      AC-1  transform_doc_frontmatter fills missing fields, re-stages, exits 0
      AC-2  transform_doc_frontmatter is fail-open on malformed YAML / absent layout
      AC-3  transform_description_field stubs description from title, exits 0
      AC-4  transform_description_field is fail-open (no title, bad YAML, absent layout)
      AC-5  every hooks_manifest entry has a tier field = "transform" | "judgment"
      AC-6  check_exception_handling emits AUTOFIX_AGENT: <agent> on violation
      AC-7  check_exception_handling does NOT emit AUTOFIX_AGENT on clean pass
BUSINESS CONTEXT: These tests are intentionally RED. They import or invoke
    modules / scripts that do not yet exist. python-coder must implement the
    listed modules to make these tests green.
ARCHITECTURE: Each test is a pure-stdlib unittest.TestCase. Tests for hooks
    (AC-6, AC-7) run the script as a subprocess via a temp .py file, mirroring
    the pattern used by test_check_exception_handling.py. Tests for the
    transform hooks use the public functions from the not-yet-existing scripts
    directly via importlib. AC-5 loads commit_guardian.json from disk.

====================================================================
DECISION HISTORY
====================================================================
- 2026-06-17 [EPIC-PrecommitSafetyNet/02]: Initial TDD stubs (test-writer phase).
  All tests are red until python-coder implements:
    scripts/commit_guardian/transform_doc_frontmatter.py
    scripts/commit_guardian/transform_description_field.py
    commit_guardian.json hooks_manifest tier field on all entries
    check_exception_handling.py AUTOFIX_AGENT emission
====================================================================
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "commit_guardian"
_TEMPLATES_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"

_TRANSFORM_DOC_FRONTMATTER = _TEMPLATES_DIR / "transform_doc_frontmatter.py"
_TRANSFORM_DESCRIPTION_FIELD = _TEMPLATES_DIR / "transform_description_field.py"
_CHECK_EXCEPTION_HANDLING = _TEMPLATES_DIR / "check_exception_handling.py"
_COMMIT_GUARDIAN_JSON = _SCRIPTS_DIR / "commit_guardian.json"


# ---------------------------------------------------------------------------
# Import helpers
# ---------------------------------------------------------------------------


def _import_transform_doc_frontmatter():
    """Import transform_doc_frontmatter from scripts/commit_guardian/.

    Returns:
        The imported module.

    Raises:
        ImportError: When the module does not yet exist (expected RED state).
    """
    spec = importlib.util.spec_from_file_location(
        "transform_doc_frontmatter", _TRANSFORM_DOC_FRONTMATTER
    )
    if spec is None or spec.loader is None:
        raise ImportError(  # noqa: TRY003
            f"Cannot import transform_doc_frontmatter: {_TRANSFORM_DOC_FRONTMATTER} does not exist"
        )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _import_transform_description_field():
    """Import transform_description_field from scripts/commit_guardian/.

    Returns:
        The imported module.

    Raises:
        ImportError: When the module does not yet exist (expected RED state).
    """
    spec = importlib.util.spec_from_file_location(
        "transform_description_field", _TRANSFORM_DESCRIPTION_FIELD
    )
    if spec is None or spec.loader is None:
        raise ImportError(  # noqa: TRY003
            f"Cannot import transform_description_field: {_TRANSFORM_DESCRIPTION_FIELD} does not exist"
        )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run_check_exception_handling(code: str) -> subprocess.CompletedProcess:
    """Write *code* to a temp .py file and invoke check_exception_handling.py against it.

    Args:
        code: Python source to write into the temp file.

    Returns:
        CompletedProcess with returncode, stdout, and stderr.
    """
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", encoding="utf-8", delete=False
    ) as f:
        f.write(textwrap.dedent(code))
        tmp_path = f.name

    try:
        return subprocess.run(
            [sys.executable, str(_CHECK_EXCEPTION_HANDLING), tmp_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# AC-1: transform_doc_frontmatter fills missing fields, re-stages, exits 0
# ---------------------------------------------------------------------------


class TestTransformDocFrontmatterFillsMissingFields(unittest.TestCase):
    """AC-1 (GE-102a): fills created/last_updated/type/status when absent."""

    def test_transform_doc_frontmatter_fills_missing_fields(self) -> None:
        # covers: UNKNOWN
        """AC-1: When a docs file is missing created, type, and status fields, the
        hook's transform function writes them, and the public API signals that
        changes were made (non-zero changed count or modified content).

        Must implement:
          transform_doc_frontmatter.transform_content(content, today_date, defaults)
          → (new_content: str, changed: int)
        Such that:
          - new_content contains 'created: <today>'
          - new_content contains 'type: <default_type>'
          - new_content contains 'status: <default_status>'
          - changed > 0
        """
        mod = _import_transform_doc_frontmatter()

        # A docs file with title only — missing created, type, status, last_updated
        content_missing_fields = "---\ntitle: Test Document\n---\n\nBody text.\n"
        today_date = "2026-06-17"
        defaults = {"type": "how-to", "status": "draft"}

        new_content, changed = mod.transform_content(content_missing_fields, today_date, defaults)

        self.assertGreater(
            changed,
            0,
            msg="Expected at least one field to be filled; got changed=0.",
        )
        self.assertIn(
            "created:",
            new_content,
            msg="Expected 'created:' field to appear in transformed content.",
        )
        self.assertIn(
            today_date,
            new_content,
            msg=f"Expected today's date '{today_date}' in transformed content.",
        )
        self.assertIn(
            "type:",
            new_content,
            msg="Expected 'type:' field to appear in transformed content.",
        )
        self.assertIn(
            "status:",
            new_content,
            msg="Expected 'status:' field to appear in transformed content.",
        )

    def test_transform_doc_frontmatter_preserves_existing_fields(self) -> None:
        # covers: UNKNOWN
        """AC-1: Fields that are already present must NOT be overwritten.

        If created is already set to '2025-01-01', it must remain '2025-01-01'
        after the transform.
        """
        mod = _import_transform_doc_frontmatter()

        content_with_existing = (
            "---\ntitle: Existing Doc\ncreated: 2025-01-01\ntype: reference\nstatus: active\n"
            "last_updated: 2025-01-15\n---\n\nBody.\n"
        )
        today_date = "2026-06-17"
        defaults = {"type": "how-to", "status": "draft"}

        new_content, changed = mod.transform_content(content_with_existing, today_date, defaults)

        self.assertEqual(
            changed,
            0,
            msg="Expected changed=0 when all fields are already present.",
        )
        self.assertIn(
            "created: 2025-01-01",
            new_content,
            msg="created date must not be overwritten when already set.",
        )


# ---------------------------------------------------------------------------
# AC-2: transform_doc_frontmatter is fail-open on bad YAML / absent layout
# ---------------------------------------------------------------------------


class TestTransformDocFrontmatterFailOpen(unittest.TestCase):
    """AC-2 (GE-102a-1-i): fail-open on parse uncertainty; no-op when no docs layout."""

    def test_transform_doc_frontmatter_fail_open(self) -> None:
        # covers: UNKNOWN
        """AC-2: When frontmatter is malformed YAML, the hook makes no edit (changed=0).

        Must implement:
          transform_doc_frontmatter.transform_content(content, today_date, defaults)
          → (new_content: str, changed: int)
        Such that on a file with malformed YAML:
          - changed == 0
          - new_content == content (no modification)
          - No unhandled exception is raised.
        """
        mod = _import_transform_doc_frontmatter()

        malformed_yaml = "---\ntitle: [unterminated bracket\ncreated:\n---\n\nBody.\n"
        today_date = "2026-06-17"
        defaults = {"type": "how-to", "status": "draft"}

        # Must not raise any unhandled exception
        try:
            new_content, changed = mod.transform_content(malformed_yaml, today_date, defaults)
        except Exception as exc:  # noqa: BLE001 — test intentionally catches all to surface better failure message
            self.fail(
                f"transform_content raised {type(exc).__name__} on malformed YAML: {exc}"
            )

        self.assertEqual(
            changed,
            0,
            msg="Expected changed=0 (fail-open) when frontmatter is malformed.",
        )

    def test_transform_doc_frontmatter_no_op_outside_docs_layout(self) -> None:
        # covers: UNKNOWN
        """AC-2: Files outside the docs/ layout target (e.g. a script file) must be
        silently skipped — no edit, no exception.

        Tests the main() function (or equivalent) with a path that does not
        match the configured docs glob.
        """
        mod = _import_transform_doc_frontmatter()

        # A path outside docs/ — should cause a no-op (the hook should skip it)
        # We verify by calling the public is_target_path() or equivalent helper,
        # or by asserting that transform_content on a non-docs path returns changed=0.
        content = "# Just a script\nNot a YAML frontmatter file\n"
        today_date = "2026-06-17"
        defaults = {"type": "how-to", "status": "draft"}

        # Verify the hook has a way to skip files outside docs/ layout.
        # The function must not raise; changed must be 0 for non-frontmatter content.
        try:
            new_content, changed = mod.transform_content(content, today_date, defaults)
        except Exception as exc:  # noqa: BLE001
            self.fail(
                f"transform_content raised {type(exc).__name__} on non-docs content: {exc}"
            )

        self.assertEqual(
            changed,
            0,
            msg="Expected changed=0 (no-op) when file has no YAML frontmatter.",
        )


# ---------------------------------------------------------------------------
# AC-3: transform_description_field stubs description from title, exits 0
# ---------------------------------------------------------------------------


class TestTransformDescriptionFieldStubsFromTitle(unittest.TestCase):
    """AC-3 (GE-102b): stubs missing description from title; no-op when present."""

    def test_transform_description_field_stubs_from_title(self) -> None:
        # covers: UNKNOWN
        """AC-3: When a staged file has a title but no description, transform writes
        a stub description derived from title.

        Must implement:
          transform_description_field.transform_content(content)
          → (new_content: str, changed: int)
        Such that:
          - new_content contains 'description:'
          - changed > 0
        """
        mod = _import_transform_description_field()

        content_with_title_no_desc = (
            "---\ntitle: How to Configure the Widget\ntype: how-to\nstatus: active\n---\n\nBody.\n"
        )

        new_content, changed = mod.transform_content(content_with_title_no_desc)

        self.assertGreater(
            changed,
            0,
            msg="Expected changed > 0 when description is absent and title is present.",
        )
        self.assertIn(
            "description:",
            new_content,
            msg="Expected 'description:' field to appear after transform.",
        )

    def test_transform_description_field_no_op_when_present(self) -> None:
        # covers: UNKNOWN
        """AC-3: When description is already present, no change must be made (changed=0)."""
        mod = _import_transform_description_field()

        content_with_desc = (
            "---\ntitle: Existing Doc\ndescription: Already filled in.\ntype: how-to\n"
            "status: active\n---\n\nBody.\n"
        )

        new_content, changed = mod.transform_content(content_with_desc)

        self.assertEqual(
            changed,
            0,
            msg="Expected changed=0 when description is already present.",
        )
        self.assertIn(
            "description: Already filled in.",
            new_content,
            msg="Existing description must not be modified.",
        )


# ---------------------------------------------------------------------------
# AC-4: transform_description_field is fail-open
# ---------------------------------------------------------------------------


class TestTransformDescriptionFieldFailOpen(unittest.TestCase):
    """AC-4 (GE-102b-1-i): fail-open when no title, malformed YAML, or absent layout."""

    def test_transform_description_field_fail_open(self) -> None:
        # covers: UNKNOWN
        """AC-4: When there is no title field, make no edit (changed=0), no exception.

        Must implement:
          transform_description_field.transform_content(content)
          → (new_content: str, changed: int)
        Such that on a file with no title and no description:
          - changed == 0
          - No unhandled exception is raised.
        """
        mod = _import_transform_description_field()

        content_no_title = (
            "---\ntype: how-to\nstatus: active\n---\n\nBody without a title.\n"
        )

        try:
            new_content, changed = mod.transform_content(content_no_title)
        except Exception as exc:  # noqa: BLE001
            self.fail(
                f"transform_content raised {type(exc).__name__} when no title present: {exc}"
            )

        self.assertEqual(
            changed,
            0,
            msg="Expected changed=0 when no title is present (fail-open).",
        )

    def test_transform_description_field_fail_open_malformed_yaml(self) -> None:
        # covers: UNKNOWN
        """AC-4: Malformed frontmatter must not raise; changed=0 (fail-open)."""
        mod = _import_transform_description_field()

        malformed = "---\ntitle: [broken\n---\n\nBody.\n"

        try:
            new_content, changed = mod.transform_content(malformed)
        except Exception as exc:  # noqa: BLE001
            self.fail(
                f"transform_content raised {type(exc).__name__} on malformed YAML: {exc}"
            )

        self.assertEqual(
            changed,
            0,
            msg="Expected changed=0 on malformed YAML frontmatter (fail-open).",
        )


# ---------------------------------------------------------------------------
# AC-5: every hooks_manifest entry has a tier field
# ---------------------------------------------------------------------------


class TestHooksManifestTierField(unittest.TestCase):
    """AC-5 (GE-102c): every hooks_manifest entry has tier in {transform, judgment}."""

    def test_hooks_manifest_tier_field(self) -> None:
        # covers: UNKNOWN
        """AC-5: Load commit_guardian.json; assert every hooks_manifest entry carries
        a 'tier' field whose value is exactly 'transform' or 'judgment'.

        Also assert that the two new transform hooks appear before any validator
        hook that checks the same field (transform-before-validator ordering).

        Expected state after python-coder is done:
          - All entries in hooks_manifest.hooks have "tier": "transform" or "judgment"
          - transform_doc_frontmatter appears before check-doc-frontmatter
          - transform_description_field appears before check-description-field
        """
        self.assertTrue(
            _COMMIT_GUARDIAN_JSON.exists(),
            msg=f"commit_guardian.json not found at {_COMMIT_GUARDIAN_JSON}",
        )

        with open(_COMMIT_GUARDIAN_JSON, encoding="utf-8") as fh:
            config = json.load(fh)

        hooks_manifest = config.get("hooks_manifest", {})
        hooks = hooks_manifest.get("hooks", [])

        self.assertGreater(
            len(hooks),
            0,
            msg="hooks_manifest.hooks must not be empty.",
        )

        valid_tiers = {"transform", "judgment"}
        missing_tier = []

        for hook in hooks:
            hook_id = hook.get("id", "<unknown>")
            tier = hook.get("tier")
            if tier not in valid_tiers:
                missing_tier.append(f"id={hook_id!r} tier={tier!r}")

        self.assertEqual(
            missing_tier,
            [],
            msg=(
                "The following hooks_manifest entries are missing a valid tier field "
                "(expected 'transform' or 'judgment'):\n  "
                + "\n  ".join(missing_tier)
            ),
        )

    def test_hooks_manifest_transform_hooks_ordered_before_validators(self) -> None:
        # covers: UNKNOWN
        """AC-5: Transform hooks must appear before their corresponding validator hooks.

        transform_doc_frontmatter must appear before check-doc-frontmatter.
        transform_description_field must appear before check-description-field.
        """
        self.assertTrue(
            _COMMIT_GUARDIAN_JSON.exists(),
            msg=f"commit_guardian.json not found at {_COMMIT_GUARDIAN_JSON}",
        )

        with open(_COMMIT_GUARDIAN_JSON, encoding="utf-8") as fh:
            config = json.load(fh)

        hooks = config.get("hooks_manifest", {}).get("hooks", [])
        hook_ids = [h.get("id", "") for h in hooks]

        ordering_pairs = [
            ("transform-doc-frontmatter", "check-doc-frontmatter"),
            ("transform-description-field", "check-description-field"),
        ]

        for transform_id, validator_id in ordering_pairs:
            # Both must exist in the manifest
            self.assertIn(
                transform_id,
                hook_ids,
                msg=f"Expected hook id '{transform_id}' to exist in hooks_manifest.",
            )
            # The transform must appear before its validator
            if transform_id in hook_ids and validator_id in hook_ids:
                t_idx = hook_ids.index(transform_id)
                v_idx = hook_ids.index(validator_id)
                self.assertLess(
                    t_idx,
                    v_idx,
                    msg=(
                        f"'{transform_id}' (position {t_idx}) must appear before "
                        f"'{validator_id}' (position {v_idx}) in hooks_manifest.hooks."
                    ),
                )


# ---------------------------------------------------------------------------
# AC-6: check_exception_handling emits AUTOFIX_AGENT on violation
# ---------------------------------------------------------------------------


class TestCheckExceptionHandlingEmitsAutofixAgent(unittest.TestCase):
    """AC-6 (GE-102d): emits AUTOFIX_AGENT: <agent> line on violation path."""

    def test_check_exception_handling_emits_autofix_agent(self) -> None:
        # covers: UNKNOWN
        """AC-6: When a staged Python file has a bare except:, check_exception_handling
        must emit a line starting with 'AUTOFIX_AGENT:' (matching the format used by
        check_complexity.py and check_doc_length.py).

        After python-coder adds the AUTOFIX_AGENT emission to check_exception_handling.py,
        this test must pass.
        """
        result = _run_check_exception_handling("""\
            def bad():
                try:
                    open("x")
                except:
                    pass
        """)

        # Must still exit 1 (violation found)
        self.assertEqual(
            result.returncode,
            1,
            msg=(
                f"Expected exit 1 for bare except:, got {result.returncode}.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )

        combined = result.stdout + result.stderr
        # Must emit an AUTOFIX_AGENT line
        autofix_lines = [
            line for line in combined.splitlines()
            if line.startswith("AUTOFIX_AGENT:")
        ]
        self.assertTrue(
            len(autofix_lines) > 0,
            msg=(
                "Expected at least one 'AUTOFIX_AGENT:' line in output on violation path.\n"
                f"Full output:\n{combined!r}"
            ),
        )

        # The line format must be: AUTOFIX_AGENT: <non-empty agent-id>
        for line in autofix_lines:
            parts = line.split(":", 1)
            self.assertEqual(len(parts), 2, msg=f"Malformed AUTOFIX_AGENT line: {line!r}")
            agent_id = parts[1].strip()
            self.assertTrue(
                len(agent_id) > 0,
                msg=f"AUTOFIX_AGENT line must include a non-empty agent id. Got: {line!r}",
            )


# ---------------------------------------------------------------------------
# AC-7: check_exception_handling does NOT emit AUTOFIX_AGENT on clean pass
# ---------------------------------------------------------------------------


class TestCheckExceptionHandlingNoEmissionClean(unittest.TestCase):
    """AC-7 (GE-102d-1-i): no AUTOFIX_AGENT line emitted on clean pass."""

    def test_check_exception_handling_no_emission_clean(self) -> None:
        # covers: UNKNOWN
        """AC-7: When a staged Python file is fully compliant, check_exception_handling
        must exit 0 and emit NO 'AUTOFIX_AGENT:' line in any output.
        """
        result = _run_check_exception_handling("""\
            import requests
            import logging

            logger = logging.getLogger(__name__)

            def fetch(url: str) -> dict:
                try:
                    response = requests.get(url, timeout=10)
                    response.raise_for_status()
                    return response.json()
                except requests.RequestException as exc:
                    logger.error("fetch failed: %s", exc)
                    raise

            def read_config(path: str) -> str:
                try:
                    with open(path, encoding="utf-8") as fh:
                        return fh.read()
                except OSError as exc:
                    logger.error("read_config failed: %s", exc)
                    raise
        """)

        # Must exit 0 (clean)
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                f"Expected exit 0 for compliant file, got {result.returncode}.\n"
                f"stdout: {result.stdout!r}\nstderr: {result.stderr!r}"
            ),
        )

        combined = result.stdout + result.stderr
        autofix_lines = [
            line for line in combined.splitlines()
            if line.startswith("AUTOFIX_AGENT:")
        ]
        self.assertEqual(
            autofix_lines,
            [],
            msg=(
                "Expected no 'AUTOFIX_AGENT:' line on clean pass.\n"
                f"Found: {autofix_lines!r}\nFull output:\n{combined!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
