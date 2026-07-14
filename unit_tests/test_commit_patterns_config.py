"""
unit_tests/test_commit_patterns_config.py — tests for AC BO-1100c.

Verifies that commit message patterns are defined in a single external
configuration file (config/commit_message_patterns.json) that the classifier
loads at runtime. Adding a new pattern should be a one-line config edit, not
a code change.

TestRoutingConfigIsArraySchema (added for the BO-1100 phantom-done remediation)
asserts that the config is a TOP-LEVEL ARRAY of {group, path_pattern, template}
entries per AC BO-1100c-1 and BO-1100c-2. The current config uses a 'patterns'
dict (object) format — these tests are the RED baseline the python-coder must
satisfy by converting the schema.
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


class TestRoutingConfigIsArraySchema(unittest.TestCase):
    """AC BO-1100c-1/2 schema tests: config must be a top-level JSON array.

    AC BO-1100c-1 specifies: "the file is valid JSON containing a top-level
    array of routing entries" with each entry having at minimum 'group',
    'path_pattern', and 'template' fields, evaluated in array order (first
    match wins). At least 5 built-in entries must ship with the default config.

    AC BO-1100c-2 specifies: appending a 6th entry activates it on next
    invocation without modifying any code or agent prompt file.

    CURRENT STATE (RED): config/commit_message_patterns.json uses a
    'patterns' object (dict of group→template), not a top-level array. The
    'path_pattern' field does not exist. These tests are the red baseline.
    """

    def test_routing_config_is_array_schema(self) -> None:
        # covers: BO-1100c-1
        """AC BO-1100c-1: commit_message_patterns.json must be a top-level JSON array.

        The current config is a dict with a 'patterns' key (object schema).
        After remediation it must be a list of routing-rule objects.
        """
        with _PATTERNS_CONFIG_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertIsInstance(
            data,
            list,
            msg=(
                "config/commit_message_patterns.json must be a top-level JSON array "
                "of routing entries per AC BO-1100c-1. "
                f"Got: {type(data).__name__!r}. "
                "Current config uses a {{patterns: dict}} structure (phantom-done: "
                "BO-1100c-1 array schema is not implemented)."
            ),
        )

    def test_ac_bo1100c1_each_entry_has_path_pattern_field(self) -> None:
        # covers: BO-1100c-1
        """AC BO-1100c-1: each array entry must contain 'group', 'path_pattern', 'template'.

        The 'path_pattern' field is new — the current config has no such field.
        """
        with _PATTERNS_CONFIG_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertIsInstance(data, list, msg="Top-level config must be a list.")
        self.assertGreater(len(data), 0, msg="Config must have at least one routing entry.")
        for i, entry in enumerate(data):
            with self.subTest(entry_index=i):
                self.assertIn(
                    "group",
                    entry,
                    msg=f"Entry {i} is missing required field 'group'.",
                )
                self.assertIn(
                    "path_pattern",
                    entry,
                    msg=(
                        f"Entry {i} is missing required field 'path_pattern' "
                        "(AC BO-1100c-1: each entry must specify a path glob/regex). "
                        "The current config does not include path_pattern at all."
                    ),
                )
                self.assertIn(
                    "template",
                    entry,
                    msg=f"Entry {i} is missing required field 'template'.",
                )

    def test_ac_bo1100c1_at_least_five_default_entries(self) -> None:
        # covers: BO-1100c-1
        """AC BO-1100c-1: at least 5 built-in entries must ship (tickets, new ACs,
        shipped ACs, implementation code, status-changes).
        """
        with _PATTERNS_CONFIG_PATH.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertIsInstance(data, list)
        self.assertGreaterEqual(
            len(data),
            5,
            msg=(
                "Config must ship with at least 5 built-in routing entries per AC "
                "BO-1100c-1 (tickets, new ACs, shipped ACs, implementation code, "
                "status changes)."
            ),
        )

    def test_ac_bo1100c2_new_rule_addable_via_config_path_param(self) -> None:
        # covers: BO-1100c-2
        """AC BO-1100c-2: appending a new rule to the array activates it without code changes.

        classify_staged_files() must accept a patterns_config_path parameter
        so it can load from a custom array-format config. This exercises the
        'no code change required' guarantee: add a line to the JSON, done.
        """
        custom_rules = [
            {
                "group": "architecture-docs",
                "path_pattern": "^docs/architecture/",
                "template": "docs(arch): {detail}",
            },
        ]
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(custom_rules, tmp)
            tmp_path = Path(tmp.name)

        try:
            # classify_staged_files must accept a patterns_config_path kwarg
            # (new parameter) so the commit agent can point it at the live config.
            result = classify_staged_files(
                ["docs/architecture/components/new-component.md"],
                patterns_config_path=tmp_path,
            )
            self.assertTrue(
                result.specific_pattern_matched,
                msg=(
                    "classify_staged_files must route by path_pattern from the "
                    "array config (BO-1100c-2). Currently path rules are hardcoded "
                    "in _PATH_RULES and not read from config."
                ),
            )
            self.assertTrue(
                result.suggested_subject.startswith("docs(arch):"),
                msg=(
                    f"Expected 'docs(arch):' prefix from array config entry, "
                    f"got: {result.suggested_subject!r}"
                ),
            )
        finally:
            tmp_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
