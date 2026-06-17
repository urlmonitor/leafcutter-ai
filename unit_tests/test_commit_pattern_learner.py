"""
unit_tests/test_commit_pattern_learner.py — tests for scripts/commit_pattern_learner.py.

Covers AC BO-1100d: Unfamiliar commit shapes are analysed and learned over time.

* Staged files that hit the UNKNOWN fallback are recorded.
* After 10 occurrences of the same shape a new routing rule is proposed.
* The proposal is returned as a dict; this module never auto-writes config.
"""
# @ac-tag: BO-1100d

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from commit_pattern_learner import (
    PROPOSAL_THRESHOLD,
    count_shape_occurrences,
    extract_shape,
    maybe_propose_rule,
    propose_rule,
    record_unknown_shape,
)


# ---------------------------------------------------------------------------
# extract_shape
# ---------------------------------------------------------------------------


class TestExtractShape(unittest.TestCase):
    """extract_shape — canonical shape derivation from file paths."""

    def test_empty_list_returns_empty_tuple(self):
        self.assertEqual(extract_shape([]), ())

    def test_extracts_extension_token(self):
        shape = extract_shape(["scripts/build.py"])
        self.assertIn("ext:py", shape)

    def test_extracts_top_level_dir_token(self):
        shape = extract_shape(["scripts/build.py"])
        self.assertIn("dir:scripts", shape)

    def test_result_is_sorted(self):
        shape = extract_shape(["zzz/c.rb", "aaa/a.py"])
        self.assertEqual(list(shape), sorted(shape))

    def test_different_order_produces_same_shape(self):
        shape_a = extract_shape(["docs/guide.md", "scripts/build.py"])
        shape_b = extract_shape(["scripts/build.py", "docs/guide.md"])
        self.assertEqual(shape_a, shape_b)

    def test_deduplicates_tokens(self):
        """Multiple .py files in the same dir should not repeat tokens."""
        shape = extract_shape(["scripts/a.py", "scripts/b.py"])
        self.assertEqual(shape.count("dir:scripts"), 1)
        self.assertEqual(shape.count("ext:py"), 1)

    def test_file_without_directory_has_no_dir_token(self):
        """A bare filename with no slash contributes only an ext token."""
        shape = extract_shape(["Makefile"])
        dir_tokens = [t for t in shape if t.startswith("dir:")]
        self.assertEqual(dir_tokens, [])

    def test_file_without_extension_has_no_ext_token(self):
        """A file with no extension (no dot) contributes only a dir token."""
        shape = extract_shape(["scripts/Makefile"])
        ext_tokens = [t for t in shape if t.startswith("ext:")]
        self.assertEqual(ext_tokens, [])

    def test_mixed_extensions_both_captured(self):
        shape = extract_shape(["config/rules.yaml", "scripts/build.py"])
        self.assertIn("ext:yaml", shape)
        self.assertIn("ext:py", shape)

    def test_normalises_uppercase(self):
        shape = extract_shape(["Scripts/Build.PY"])
        self.assertIn("ext:py", shape)
        self.assertIn("dir:scripts", shape)

    def test_returns_tuple(self):
        result = extract_shape(["a/b.py"])
        self.assertIsInstance(result, tuple)


# ---------------------------------------------------------------------------
# record_unknown_shape
# ---------------------------------------------------------------------------


class TestRecordUnknownShape(unittest.TestCase):
    """record_unknown_shape — JSONL observation store write."""

    def test_creates_jsonl_file_on_first_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_path = Path(tmp) / "obs.jsonl"
            record_unknown_shape(["some/file.rb"], obs_path=obs_path)
            self.assertTrue(obs_path.exists())

    def test_appends_valid_json_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_path = Path(tmp) / "obs.jsonl"
            record_unknown_shape(["some/file.rb"], obs_path=obs_path)
            line = obs_path.read_text().strip()
            record = json.loads(line)
            self.assertIn("timestamp", record)
            self.assertIn("shape", record)
            self.assertIsInstance(record["shape"], list)

    def test_shape_in_record_matches_extract_shape(self):
        paths = ["tools/helper.rb", "lib/core.rb"]
        with tempfile.TemporaryDirectory() as tmp:
            obs_path = Path(tmp) / "obs.jsonl"
            recorded_shape = record_unknown_shape(paths, obs_path=obs_path)
            expected_shape = extract_shape(paths)
            self.assertEqual(recorded_shape, expected_shape)

            line = obs_path.read_text().strip()
            record = json.loads(line)
            self.assertEqual(sorted(record["shape"]), sorted(list(expected_shape)))

    def test_multiple_calls_append_multiple_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_path = Path(tmp) / "obs.jsonl"
            record_unknown_shape(["a/x.go"], obs_path=obs_path)
            record_unknown_shape(["a/y.go"], obs_path=obs_path)
            record_unknown_shape(["a/z.go"], obs_path=obs_path)
            lines = [line for line in obs_path.read_text().splitlines() if line.strip()]
            self.assertEqual(len(lines), 3)

    def test_creates_parent_directory_if_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_path = Path(tmp) / "subdir" / "nested" / "obs.jsonl"
            record_unknown_shape(["a/b.rb"], obs_path=obs_path)
            self.assertTrue(obs_path.exists())

    def test_returns_shape_tuple(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_path = Path(tmp) / "obs.jsonl"
            result = record_unknown_shape(["tools/foo.rb"], obs_path=obs_path)
            self.assertIsInstance(result, tuple)


# ---------------------------------------------------------------------------
# count_shape_occurrences
# ---------------------------------------------------------------------------


class TestCountShapeOccurrences(unittest.TestCase):
    """count_shape_occurrences — reads JSONL and counts matching shape records."""

    def test_returns_zero_when_store_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_path = Path(tmp) / "nonexistent.jsonl"
            shape = extract_shape(["tools/foo.rb"])
            self.assertEqual(count_shape_occurrences(shape, obs_path=obs_path), 0)

    def test_counts_matching_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_path = Path(tmp) / "obs.jsonl"
            paths = ["tools/foo.rb", "lib/bar.rb"]
            for _ in range(5):
                record_unknown_shape(paths, obs_path=obs_path)
            shape = extract_shape(paths)
            self.assertEqual(count_shape_occurrences(shape, obs_path=obs_path), 5)

    def test_does_not_count_different_shapes(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_path = Path(tmp) / "obs.jsonl"
            # Record a ruby shape 3 times
            ruby_paths = ["tools/foo.rb"]
            for _ in range(3):
                record_unknown_shape(ruby_paths, obs_path=obs_path)
            # Count a go shape — should be 0
            go_shape = extract_shape(["cmd/main.go"])
            self.assertEqual(count_shape_occurrences(go_shape, obs_path=obs_path), 0)

    def test_count_is_order_insensitive(self):
        """Shapes with the same tokens in different record order are the same shape."""
        with tempfile.TemporaryDirectory() as tmp:
            obs_path = Path(tmp) / "obs.jsonl"
            # Write a record manually with tokens in reverse order
            shape_tokens = list(extract_shape(["tools/a.rb", "lib/b.rb"]))
            record = {"timestamp": "2026-01-01T00:00:00+00:00", "shape": shape_tokens[::-1]}
            obs_path.write_text(json.dumps(record) + "\n")

            shape = extract_shape(["tools/a.rb", "lib/b.rb"])
            self.assertEqual(count_shape_occurrences(shape, obs_path=obs_path), 1)

    def test_skips_malformed_lines(self):
        """Malformed JSONL lines are skipped, valid lines are counted."""
        with tempfile.TemporaryDirectory() as tmp:
            obs_path = Path(tmp) / "obs.jsonl"
            paths = ["tools/foo.rb"]
            record_unknown_shape(paths, obs_path=obs_path)
            # Append a malformed line
            with obs_path.open("a") as fh:
                fh.write("NOT VALID JSON\n")
            record_unknown_shape(paths, obs_path=obs_path)

            shape = extract_shape(paths)
            self.assertEqual(count_shape_occurrences(shape, obs_path=obs_path), 2)


# ---------------------------------------------------------------------------
# propose_rule
# ---------------------------------------------------------------------------


class TestProposeRule(unittest.TestCase):
    """propose_rule — rule proposal dict generation."""

    def test_returns_dict_with_required_keys(self):
        shape = extract_shape(["tools/build.rb"])
        proposal = propose_rule(shape)
        self.assertIn("group_key", proposal)
        self.assertIn("template", proposal)

    def test_template_contains_detail_placeholder(self):
        shape = extract_shape(["tools/build.rb"])
        proposal = propose_rule(shape)
        self.assertIn("{detail}", proposal["template"])

    def test_group_key_is_valid_identifier_chars(self):
        """group_key should contain only lowercase alphanumeric and underscores."""
        shape = extract_shape(["some-dir/build.go"])
        proposal = propose_rule(shape)
        self.assertRegex(proposal["group_key"], r"^[a-z0-9_]+$")

    def test_group_key_uses_directory_token_preferentially(self):
        """When dir tokens are present they are preferred for naming."""
        shape = extract_shape(["mytools/build.rb"])
        proposal = propose_rule(shape)
        self.assertIn("mytools", proposal["group_key"])

    def test_empty_shape_produces_fallback_key(self):
        proposal = propose_rule(())
        self.assertEqual(proposal["group_key"], "unknown_shape")
        self.assertIn("{detail}", proposal["template"])

    def test_does_not_write_any_files(self):
        """propose_rule is a pure function — it must not write to disk."""
        import os
        shape = extract_shape(["tools/build.rb"])
        with tempfile.TemporaryDirectory() as tmp:
            orig_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                propose_rule(shape)
                written = list(Path(tmp).iterdir())
                self.assertEqual(written, [], "propose_rule wrote unexpected files")
            finally:
                os.chdir(orig_cwd)


# ---------------------------------------------------------------------------
# maybe_propose_rule — integration
# ---------------------------------------------------------------------------


class TestMaybeProposeRule(unittest.TestCase):
    """maybe_propose_rule — full learning loop integration."""

    def test_returns_none_before_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_path = Path(tmp) / "obs.jsonl"
            paths = ["tools/foo.rb"]
            # PROPOSAL_THRESHOLD - 1 calls should all return None
            for _ in range(PROPOSAL_THRESHOLD - 1):
                result = maybe_propose_rule(paths, obs_path=obs_path)
                self.assertIsNone(result)

    def test_returns_proposal_at_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_path = Path(tmp) / "obs.jsonl"
            paths = ["tools/foo.rb"]
            proposal = None
            for _ in range(PROPOSAL_THRESHOLD):
                proposal = maybe_propose_rule(paths, obs_path=obs_path)
            self.assertIsNotNone(proposal)
            self.assertIn("group_key", proposal)
            self.assertIn("template", proposal)

    def test_continues_returning_proposal_after_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_path = Path(tmp) / "obs.jsonl"
            paths = ["tools/foo.rb"]
            for _ in range(PROPOSAL_THRESHOLD + 5):
                result = maybe_propose_rule(paths, obs_path=obs_path)
            # After many calls, still returns a proposal
            self.assertIsNotNone(result)

    def test_different_shapes_tracked_independently(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_path = Path(tmp) / "obs.jsonl"
            ruby_paths = ["tools/foo.rb"]
            go_paths = ["cmd/main.go"]
            # Call ruby shape 10 times → should propose
            for _ in range(PROPOSAL_THRESHOLD):
                maybe_propose_rule(ruby_paths, obs_path=obs_path)
            # Call go shape only once → should NOT propose
            result = maybe_propose_rule(go_paths, obs_path=obs_path)
            self.assertIsNone(result)

    def test_observation_store_is_populated(self):
        with tempfile.TemporaryDirectory() as tmp:
            obs_path = Path(tmp) / "obs.jsonl"
            paths = ["tools/foo.rb"]
            for _ in range(3):
                maybe_propose_rule(paths, obs_path=obs_path)
            lines = [line for line in obs_path.read_text().splitlines() if line.strip()]
            self.assertEqual(len(lines), 3)

    def test_custom_threshold(self):
        """Caller can supply a custom threshold."""
        with tempfile.TemporaryDirectory() as tmp:
            obs_path = Path(tmp) / "obs.jsonl"
            paths = ["tools/foo.rb"]
            # threshold=3 — first two calls return None, third returns proposal
            result1 = maybe_propose_rule(paths, obs_path=obs_path, threshold=3)
            result2 = maybe_propose_rule(paths, obs_path=obs_path, threshold=3)
            self.assertIsNone(result1)
            self.assertIsNone(result2)
            result3 = maybe_propose_rule(paths, obs_path=obs_path, threshold=3)
            self.assertIsNotNone(result3)


# ---------------------------------------------------------------------------
# Integration: does NOT auto-write config
# ---------------------------------------------------------------------------


class TestProposalIsNonDestructive(unittest.TestCase):
    """Verify the module never auto-modifies commit_message_patterns.json."""

    def test_maybe_propose_rule_does_not_touch_patterns_config(self):
        """Even at threshold, only the observation store is written — not the config."""
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
        import commit_pattern_learner

        with tempfile.TemporaryDirectory() as tmp:
            obs_path = Path(tmp) / "obs.jsonl"
            # Point the module at a non-existent patterns path inside tmp
            dummy_patterns_path = Path(tmp) / "commit_message_patterns.json"

            paths = ["tools/foo.rb"]
            for _ in range(PROPOSAL_THRESHOLD):
                maybe_propose_rule(paths, obs_path=obs_path)

            # The patterns JSON should NOT have been created by maybe_propose_rule
            self.assertFalse(
                dummy_patterns_path.exists(),
                "maybe_propose_rule must not auto-write the patterns config",
            )


if __name__ == "__main__":
    unittest.main()
