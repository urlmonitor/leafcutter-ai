"""
MODULE: test_build
GOAL: Unit tests for leafcutter/scripts/build.py.
BUSINESS CONTEXT: Verifies that build.py correctly strips frontmatter,
    injects config values, handles sign-off flags, validates schemas,
    and respects dry-run and idempotency constraints.
ARCHITECTURE: Standard unittest. No database, no network, no file I/O to
    project directories. Uses tempfile.TemporaryDirectory for all output.
    Adds the leafcutter/scripts/ directory to sys.path so that
    build.py's relative imports of config_loader and template_compiler work
    correctly, then loads the module via importlib.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Load build module from its canonical location (outside unit_tests/)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_BUILD_PATH = _SCRIPTS_DIR / "build.py"

# Prepend the scripts directory so that build.py's `from config_loader import ...`
# and `from template_compiler import ...` resolve correctly during exec_module.
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _load_build():
    """Load build.py as a module without side-effects.

    Returns:
        The loaded build module object with all public symbols accessible.
    """
    spec = importlib.util.spec_from_file_location("portable_build", _BUILD_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load build.py from {_BUILD_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_build = _load_build()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestFrontmatterParsing(unittest.TestCase):
    """Tests for parse_frontmatter."""

    def test_no_frontmatter(self):
        text = "# Hello\n\nBody text."
        fm, body = _build.parse_frontmatter(text)
        self.assertEqual(fm, {})
        self.assertEqual(body, text)

    def test_simple_frontmatter(self):
        text = "---\nname: my-agent\nmodel: sonnet\n---\n\n# Body\n"
        fm, body = _build.parse_frontmatter(text)
        self.assertEqual(fm.get("name"), "my-agent")
        self.assertIn("# Body", body)
        self.assertNotIn("---", body)

    def test_frontmatter_without_trailing_newline(self):
        text = "---\nname: x\n---\nBody"
        fm, body = _build.parse_frontmatter(text)
        self.assertEqual(fm.get("name"), "x")
        self.assertIn("Body", body)


class TestStripMetadataSections(unittest.TestCase):
    """Tests for strip_metadata_sections."""

    def test_strips_configuration_section(self):
        body = "# Intro\n\nSome text.\n\n## Configuration\n\nKey: value.\n"
        result = _build.strip_metadata_sections(body)
        self.assertNotIn("## Configuration", result)
        self.assertNotIn("Key: value", result)
        self.assertIn("Some text.", result)

    def test_strips_section_until_next_heading(self):
        body = "## Keep This\n\nGood.\n\n## Configuration\n\nMeta.\n\n## Also Keep\n\nAlso good.\n"
        result = _build.strip_metadata_sections(body)
        self.assertNotIn("## Configuration", result)
        self.assertNotIn("Meta.", result)
        self.assertIn("## Keep This", result)
        self.assertIn("## Also Keep", result)

    def test_no_stripped_sections(self):
        body = "## Overview\n\nContent.\n\n## Implementation\n\nCode.\n"
        result = _build.strip_metadata_sections(body)
        self.assertIn("## Overview", result)
        self.assertIn("## Implementation", result)

    def test_strips_at_eof(self):
        body = "## Content\n\nGood stuff.\n\n## Configuration\n\nKey stuff at EOF."
        result = _build.strip_metadata_sections(body)
        self.assertNotIn("## Configuration", result)
        self.assertIn("Good stuff.", result)


class TestInjectConfig(unittest.TestCase):
    """Tests for inject_config."""

    def test_resolves_known_key(self):
        config = {"default_branch": "main"}
        body = "Merge to {{config.default_branch}} when done."
        result = _build.inject_config(body, config)
        self.assertEqual(result, "Merge to main when done.")

    def test_leaves_unknown_key_unresolved(self):
        config = {}
        body = "Run {{config.unknown_key}} here."
        result = _build.inject_config(body, config)
        self.assertIn("{{config.unknown_key}}", result)

    def test_resolves_list_value(self):
        config = {"top_level_packages": ["live_trader", "collector"]}
        body = "Packages: {{config.top_level_packages}}"
        result = _build.inject_config(body, config)
        self.assertIn("live_trader", result)
        self.assertIn("collector", result)

    def test_no_placeholders(self):
        config = {"key": "val"}
        body = "No placeholders here."
        result = _build.inject_config(body, config)
        self.assertEqual(result, body)


class TestLoadConfig(unittest.TestCase):
    """Tests for load_config with defaults and overrides."""

    def test_defaults_loaded_without_project_config(self):
        """When no project config exists, defaults from package are loaded."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            config = _build.load_config(None, target)
            # Should have default keys from skills_config.default.json
            self.assertIn("default_branch", config)

    def test_project_config_overrides_defaults(self):
        """Project config values override package defaults."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            claude_dir = target / ".claude"
            claude_dir.mkdir()
            config_path = claude_dir / "skills_config.json"
            config_path.write_text(json.dumps({"default_branch": "develop"}))

            config = _build.load_config(None, target)
            self.assertEqual(config.get("default_branch"), "develop")

    def test_explicit_config_path_overrides(self):
        """Explicit --config-path overrides auto-detection."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            config_path = target / "custom_config.json"
            config_path.write_text(json.dumps({"default_branch": "release"}))

            config = _build.load_config(config_path, target)
            self.assertEqual(config.get("default_branch"), "release")


class TestDryRun(unittest.TestCase):
    """Tests for dry-run mode: no files written."""

    def test_dry_run_writes_no_files(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir)
            config = {"default_branch": "main"}
            written = _build.build_agents(target, config, dry_run=True, force=False)
            # In dry-run, the count reflects what would be written
            # but actual .claude/agents/ should not exist
            agents_dir = target / ".claude" / "agents"
            self.assertFalse(agents_dir.exists())


class TestIdempotency(unittest.TestCase):
    """Tests for idempotency: re-running produces same output."""

    def test_existing_file_not_overwritten_without_force(self):
        """Without --force, existing files are skipped."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "test.md"
            original_content = "original"
            target_file.write_text(original_content)

            # Attempt to write different content without force
            written = _build.write_file(
                target_file, "new content", dry_run=False, force=False
            )
            self.assertFalse(written)
            self.assertEqual(target_file.read_text(), original_content)

    def test_existing_file_overwritten_with_force(self):
        """With --force, existing files are overwritten."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "test.md"
            target_file.write_text("original")

            written = _build.write_file(
                target_file, "new content", dry_run=False, force=True
            )
            self.assertTrue(written)
            self.assertEqual(target_file.read_text(), "new content")


class TestSchemaValidation(unittest.TestCase):
    """Tests for config schema validation."""

    def test_valid_config_passes(self):
        config = {"default_branch": "main", "tickets_inbox_path": "tickets/00_inbox"}
        errors = _build.validate_config(config)
        # Only check for actual schema errors, not missing-library warnings
        schema_errors = [e for e in errors if not e.startswith("jsonschema")]
        self.assertEqual(schema_errors, [])

    def test_extra_keys_allowed(self):
        """Schema uses additionalProperties: true so extra keys are fine."""
        config = {"default_branch": "main", "custom_key": "value"}
        errors = _build.validate_config(config)
        schema_errors = [e for e in errors if not e.startswith("jsonschema")]
        self.assertEqual(schema_errors, [])


class TestCompareBeforeWrite(unittest.TestCase):
    """Tests for the compare-before-write guard in write_file."""

    def test_write_file_skips_identical_content(self):
        """write_file returns False and leaves mtime unchanged for byte-identical content."""
        import tempfile
        import time
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "output.md"
            content = "Hello, identical world!"
            target_file.write_text(content, encoding="utf-8")

            # Capture mtime before the call.
            mtime_before = target_file.stat().st_mtime

            # Small sleep to ensure mtime would differ if the file were rewritten.
            time.sleep(0.05)

            result = _build.write_file(target_file, content, dry_run=False, force=True)

            self.assertFalse(result, "Expected False: content identical, write should be skipped")
            self.assertEqual(target_file.stat().st_mtime, mtime_before,
                             "mtime must not change when content is identical")
            self.assertEqual(target_file.read_text(encoding="utf-8"), content)

    def test_write_file_writes_changed_content(self):
        """write_file returns True and updates the file when content differs."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "output.md"
            target_file.write_text("original content", encoding="utf-8")

            result = _build.write_file(
                target_file, "changed content", dry_run=False, force=True
            )

            self.assertTrue(result, "Expected True: content changed, write should proceed")
            self.assertEqual(target_file.read_text(encoding="utf-8"), "changed content")

    def test_write_file_dry_run_identical(self):
        """dry-run with identical content: returns True (reports intent) without writing.

        Dry-run mode reports what *would* happen if force were honoured, not
        what the compare-before-write guard would do.  The guard only fires
        on actual disk writes; in dry-run no read is performed either — the
        function returns True to indicate "would write" regardless of content.
        """
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "output.md"
            content = "same content"
            target_file.write_text(content, encoding="utf-8")

            # dry_run=True: the guard is bypassed; should always report True
            # (would write) for files that pass the overwrite check.
            result = _build.write_file(target_file, content, dry_run=True, force=True)

            self.assertTrue(result, "dry-run should return True even for identical content")
            # The file on disk must NOT have been modified.
            self.assertEqual(target_file.read_text(encoding="utf-8"), content)

    def test_write_file_new_file_always_written(self):
        """write_file creates a new file regardless of content guard."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "new_output.md"
            self.assertFalse(target_file.exists())

            result = _build.write_file(target_file, "brand new", dry_run=False, force=True)

            self.assertTrue(result, "New file should always be written")
            self.assertEqual(target_file.read_text(encoding="utf-8"), "brand new")

    def test_write_file_unicode_decode_error_falls_through(self):
        """write_file falls through to an unconditional write for binary/non-UTF-8 files."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            target_file = Path(tmpdir) / "binary.bin"
            # Write raw bytes that are not valid UTF-8.
            target_file.write_bytes(b"\xff\xfe\x00\x01")

            # Write new text content over a non-UTF-8 file: guard must not raise.
            result = _build.write_file(
                target_file, "new text content", dry_run=False, force=True
            )

            self.assertTrue(result, "Binary source file should fall through to write")
            self.assertEqual(target_file.read_text(encoding="utf-8"), "new text content")


if __name__ == "__main__":
    unittest.main()
