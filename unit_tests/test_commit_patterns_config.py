"""
unit_tests/test_commit_patterns_config.py — tests for AC BO-1100c.

Verifies that commit message patterns are defined in a single external
configuration file (config/commit_message_patterns.json) that the classifier
loads at runtime. Adding a new pattern should be a one-line config edit, not
a code change.
"""
# @ac-tag: BO-1100c

import json
import sys
import os
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from commit_classifier import (
    DEFAULT_PATTERNS,
    FileGroup,
    _FALLBACK_PATTERNS,
    _PATTERNS_CONFIG_PATH,
    classify_staged_files,
    load_patterns,
)


class TestPatternsConfigFileExists(unittest.TestCase):
    """The config file exists, is valid JSON, and has the expected structure."""

    def test_config_file_exists(self):
        """config/commit_message_patterns.json must be present in the repo."""
        self.assertTrue(
            _PATTERNS_CONFIG_PATH.exists(),
            msg=f"Expected config file at {_PATTERNS_CONFIG_PATH}",
        )

    def test_config_file_is_valid_json(self):
        """The config file must be parseable as JSON."""
        with _PATTERNS_CONFIG_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertIsInstance(data, dict)

    def test_config_file_has_patterns_key(self):
        """Top-level 'patterns' key must be a dict."""
        with _PATTERNS_CONFIG_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertIn("patterns", data)
        self.assertIsInstance(data["patterns"], dict)

    def test_config_patterns_cover_all_file_groups(self):
        """Every FileGroup value must have a pattern entry in the config."""
        with _PATTERNS_CONFIG_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        config_keys = set(data["patterns"].keys())
        for group in FileGroup:
            with self.subTest(group=group):
                self.assertIn(
                    group.value,
                    config_keys,
                    msg=f"FileGroup.{group.name} ({group.value!r}) missing from config",
                )

    def test_all_patterns_contain_detail_placeholder(self):
        """Every pattern string must contain the {detail} placeholder."""
        with _PATTERNS_CONFIG_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        for key, template in data["patterns"].items():
            with self.subTest(key=key):
                self.assertIn(
                    "{detail}",
                    template,
                    msg=f"Pattern for {key!r} is missing {{detail}} placeholder",
                )


class TestLoadPatterns(unittest.TestCase):
    """load_patterns() — config loading and fallback behaviour."""

    def test_load_patterns_returns_dict(self):
        result = load_patterns()
        self.assertIsInstance(result, dict)

    def test_load_patterns_covers_all_groups(self):
        """Loaded patterns must have an entry for every FileGroup member."""
        result = load_patterns()
        for group in FileGroup:
            with self.subTest(group=group):
                self.assertIn(group, result)

    def test_load_patterns_values_are_strings(self):
        result = load_patterns()
        for group, template in result.items():
            with self.subTest(group=group):
                self.assertIsInstance(template, str)

    def test_load_patterns_values_contain_detail_placeholder(self):
        result = load_patterns()
        for group, template in result.items():
            with self.subTest(group=group):
                self.assertIn("{detail}", template)

    def test_load_patterns_with_missing_file_falls_back_to_defaults(self):
        """When the config file does not exist, compiled-in defaults are used."""
        missing = Path("/nonexistent/path/commit_message_patterns.json")
        result = load_patterns(config_path=missing)
        self.assertEqual(result, _FALLBACK_PATTERNS)

    def test_load_patterns_with_custom_path_overrides_a_pattern(self):
        """A custom config file can override a single pattern entry."""
        custom_data = {
            "patterns": {
                "tickets": "custom(tickets): {detail}",
            }
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(custom_data, tmp)
            tmp_path = Path(tmp.name)

        try:
            result = load_patterns(config_path=tmp_path)
            # The overridden pattern should use the custom value.
            self.assertEqual(result[FileGroup.TICKETS], "custom(tickets): {detail}")
            # All other groups should retain their fallback values.
            self.assertEqual(
                result[FileGroup.IMPLEMENTATION_CODE],
                _FALLBACK_PATTERNS[FileGroup.IMPLEMENTATION_CODE],
            )
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_load_patterns_with_invalid_json_falls_back_to_defaults(self):
        """Malformed JSON in the config file triggers fallback."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write("{ this is not valid json }")
            tmp_path = Path(tmp.name)

        try:
            result = load_patterns(config_path=tmp_path)
            self.assertEqual(result, _FALLBACK_PATTERNS)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_load_patterns_with_no_patterns_key_falls_back(self):
        """Config file missing the 'patterns' key triggers fallback."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump({"_comment": "no patterns key here"}, tmp)
            tmp_path = Path(tmp.name)

        try:
            result = load_patterns(config_path=tmp_path)
            self.assertEqual(result, _FALLBACK_PATTERNS)
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_load_patterns_ignores_unknown_group_key(self):
        """An unrecognised group key in the config is skipped without error."""
        custom_data = {
            "patterns": {
                "tickets": "chore(tickets): {detail}",
                "not_a_real_group": "custom: {detail}",
            }
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(custom_data, tmp)
            tmp_path = Path(tmp.name)

        try:
            result = load_patterns(config_path=tmp_path)
            # Should succeed and not raise.
            self.assertIsInstance(result, dict)
            # The unknown key should not appear as a FileGroup in the result.
            for group in result:
                self.assertIsInstance(group, FileGroup)
        finally:
            tmp_path.unlink(missing_ok=True)


class TestDefaultPatternsLoadedFromConfig(unittest.TestCase):
    """DEFAULT_PATTERNS at module level matches what load_patterns() returns."""

    def test_default_patterns_matches_load_patterns(self):
        """Module-level DEFAULT_PATTERNS must equal load_patterns() output."""
        fresh = load_patterns()
        self.assertEqual(DEFAULT_PATTERNS, fresh)

    def test_default_patterns_match_fallback_values(self):
        """Loaded patterns must match the fallback (since config ships same values)."""
        for group in FileGroup:
            with self.subTest(group=group):
                self.assertEqual(
                    DEFAULT_PATTERNS[group],
                    _FALLBACK_PATTERNS[group],
                    msg=f"Mismatch for {group}: config overrides fallback unexpectedly",
                )


class TestConfigIsConsultedByClassifier(unittest.TestCase):
    """classify_staged_files() uses the loaded config patterns."""

    def test_classify_uses_config_pattern_for_tickets(self):
        """The classifier uses the tickets pattern from the loaded config."""
        result = classify_staged_files(["tickets/00_inbox/t.md"])
        expected_template = DEFAULT_PATTERNS[FileGroup.TICKETS]
        # The subject line should start with whatever the config says for tickets.
        prefix = expected_template.split("{detail}")[0]
        self.assertTrue(
            result.suggested_subject.startswith(prefix),
            msg=f"Expected subject starting with {prefix!r}, got {result.suggested_subject!r}",
        )

    def test_one_line_config_edit_changes_a_pattern(self):
        """AC BO-1100c: adding/changing a pattern is a one-line config edit.

        This test simulates writing a modified config and verifies the classifier
        picks up the new pattern when load_patterns() is pointed at that file.
        """
        custom_template = "CUSTOM(tickets): {detail}"
        custom_data = {"patterns": {"tickets": custom_template}}

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(custom_data, tmp)
            tmp_path = Path(tmp.name)

        try:
            custom_patterns = load_patterns(config_path=tmp_path)
            self.assertEqual(custom_patterns[FileGroup.TICKETS], custom_template)

            # classify_staged_files with the custom pattern map should use it.
            result = classify_staged_files(
                ["tickets/00_inbox/t.md"], patterns=custom_patterns
            )
            self.assertTrue(
                result.suggested_subject.startswith("CUSTOM(tickets):"),
                msg=f"Expected custom prefix, got {result.suggested_subject!r}",
            )
        finally:
            tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
