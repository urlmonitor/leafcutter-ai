"""
unit_tests/test_defect_fixes.py — Regression tests for 7 defect ACs found during
code review of the commit message classification system.

Each test class targets one AC and is expected to FAIL (red) until the
python-coder applies the corresponding fix to:
  - scripts/commit_classifier.py
  - scripts/commit_pattern_learner.py

AC coverage:
  AC BO-1100a-6    — Path rules match only intended directory subtree
  AC BO-1100a-6-i  — Infix path segments not matched
  AC BO-1100c-4    — Pattern config reflects current file on every invocation
  AC BO-1100d-5    — Observation store write failure does not crash workflow
  AC BO-1100d-6    — Already-classified shapes not recorded as unknown
  AC BO-1100e-4    — History filter wired into learning pipeline + positive bound
  AC BO-1100e-4-i  — Negative max_commits rejected
"""
# @ac-tag: BO-1100a-6
# @ac-tag: BO-1100a-6-i
# @ac-tag: BO-1100c-4
# @ac-tag: BO-1100d-5
# @ac-tag: BO-1100d-6
# @ac-tag: BO-1100e-4
# @ac-tag: BO-1100e-4-i

from __future__ import annotations

import json
import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Path setup — make scripts/ importable regardless of working directory.
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from commit_classifier import (
    FileGroup,
    classify_staged_files,
    group_files_by_type,
)
from commit_pattern_learner import (
    PROPOSAL_THRESHOLD,
    filter_history_by_shape,
    maybe_propose_rule,
)


# ===========================================================================
# AC BO-1100a-6 — Path rules match only intended directory subtree
# ===========================================================================


class TestPathRulesMatchOnlyIntendedSubtree(unittest.TestCase):
    """AC BO-1100a-6: Path-matching rules must be anchored so that a rule for
    'config/ac_store/' does not fire on 'config/accounting/report.csv', and
    a rule for 'tickets/' does not fire on a mid-path segment like
    'archived/old-tickets/readme.md'.

    All of these tests currently fail because:
      - re.compile(r"config/ac") matches 'config/accounting/...' (too broad).
      - re.compile(r"tickets/") matches mid-path 'archived/old-tickets/...'
        because re.search() is used (not re.match() / anchored pattern).
      - re.compile(r"(^|/)config/") matches 'vendor/some-lib/config/setup.py'.
    """

    # -----------------------------------------------------------------------
    # False-positive cases (currently wrong — will classify into wrong group)
    # -----------------------------------------------------------------------

    def test_ac1_config_accounting_not_classified_as_shipped_acs(self):
        # covers: BO-1100a-6
        """AC BO-1100a-6: config/accounting/report.csv must NOT be SHIPPED_ACS.

        The regex r'config/ac' currently matches the substring 'ac' in
        'accounting', causing a false-positive SHIPPED_ACS classification.
        After the fix the rule must require a full path-component boundary so
        that 'config/ac_store/' matches but 'config/accounting/' does not.
        """
        groups = group_files_by_type(["config/accounting/report.csv"])
        self.assertNotIn(
            FileGroup.SHIPPED_ACS,
            groups,
            msg=(
                "config/accounting/report.csv was incorrectly classified as "
                "SHIPPED_ACS — the 'config/ac' regex is too broad and matches "
                "'accounting'."
            ),
        )

    def test_ac1_config_access_not_classified_as_shipped_acs(self):
        # covers: BO-1100a-6
        """AC BO-1100a-6: config/access/policy.json must NOT be SHIPPED_ACS."""
        groups = group_files_by_type(["config/access/policy.json"])
        self.assertNotIn(
            FileGroup.SHIPPED_ACS,
            groups,
            msg=(
                "config/access/policy.json was incorrectly classified as "
                "SHIPPED_ACS — the 'config/ac' regex matches 'access'."
            ),
        )

    def test_ac1_mid_path_tickets_not_classified_as_tickets(self):
        # covers: BO-1100a-6
        """AC BO-1100a-6: archived/old-tickets/readme.md must NOT be TICKETS.

        'tickets/' appears as an infix segment; the rule must only fire when
        the path starts with 'tickets/' or has 'tickets/' immediately after a
        directory separator at the top level.
        """
        groups = group_files_by_type(["archived/old-tickets/readme.md"])
        self.assertNotIn(
            FileGroup.TICKETS,
            groups,
            msg=(
                "archived/old-tickets/readme.md was incorrectly classified as "
                "TICKETS — the unanchored 'tickets/' regex fires on mid-path segments."
            ),
        )

    def test_ac1_vendor_config_subpath_not_classified_as_config(self):
        # covers: BO-1100a-6
        """AC BO-1100a-6: vendor/some-lib/config/setup.py must NOT be CONFIG.

        The rule r'(^|/)config/' currently uses re.search(), which matches
        '/config/' anywhere in the path.  After the fix the rule must only
        match when 'config/' appears at the top level of the path (i.e. the
        path starts with 'config/' or has a recognised top-level directory
        component equal to 'config').
        """
        groups = group_files_by_type(["vendor/some-lib/config/setup.py"])
        self.assertNotIn(
            FileGroup.CONFIG,
            groups,
            msg=(
                "vendor/some-lib/config/setup.py was incorrectly classified as "
                "CONFIG — the regex (^|/)config/ fires on mid-path 'config/' segments."
            ),
        )

    # -----------------------------------------------------------------------
    # True-positive cases (must still classify correctly after the fix)
    # -----------------------------------------------------------------------

    def test_ac1_ac_store_still_classified_as_shipped_acs(self):
        # covers: BO-1100a-6
        """Legitimate AC-store path must still be SHIPPED_ACS after the fix."""
        groups = group_files_by_type(["config/ac_store/AC-001.yaml"])
        self.assertIn(
            FileGroup.SHIPPED_ACS,
            groups,
            msg="config/ac_store/AC-001.yaml should remain classified as SHIPPED_ACS.",
        )

    def test_ac1_top_level_tickets_still_classified_as_tickets(self):
        # covers: BO-1100a-6
        """Paths starting with tickets/ must still be TICKETS after the fix."""
        groups = group_files_by_type(["tickets/00_inbox/TICKET.md"])
        self.assertIn(
            FileGroup.TICKETS,
            groups,
            msg="tickets/00_inbox/TICKET.md should remain classified as TICKETS.",
        )

    def test_ac1_top_level_config_still_classified_as_config(self):
        # covers: BO-1100a-6
        """Top-level config paths must still be CONFIG after the fix."""
        groups = group_files_by_type(["config/agent_registry.json"])
        self.assertIn(
            FileGroup.CONFIG,
            groups,
            msg="config/agent_registry.json should remain classified as CONFIG.",
        )


# ===========================================================================
# AC BO-1100a-6-i — Infix path segments not matched
# ===========================================================================


class TestInfixPathSegmentsNotMatched(unittest.TestCase):
    """AC BO-1100a-6-i: When the ac_store token appears as part of a longer
    directory name, or when the path prefix before 'config/' is not a
    recognised top-level directory, the SHIPPED_ACS rule must NOT fire.

    All of these tests currently fail because the rule r'config/ac' is too
    broad and fires on any path containing the substring 'config/ac'.
    """

    def test_ac2_ac_store_backup_dir_not_shipped_acs(self):
        # covers: BO-1100a-6-i
        """config/ac_store_backup/old-data.json must NOT be SHIPPED_ACS.

        The directory name 'ac_store_backup' starts with 'ac_store' but is a
        different directory; the rule must be anchored to the exact token
        'ac_store' followed by '/' (not any prefix match).
        """
        groups = group_files_by_type(["config/ac_store_backup/old-data.json"])
        self.assertNotIn(
            FileGroup.SHIPPED_ACS,
            groups,
            msg=(
                "config/ac_store_backup/old-data.json was incorrectly classified "
                "as SHIPPED_ACS — the rule must match only 'config/ac_store/' exactly."
            ),
        )

    def test_ac2_my_config_prefix_not_shipped_acs(self):
        # covers: BO-1100a-6-i
        """my-config/ac_store/leftover.yaml must NOT be SHIPPED_ACS.

        The path contains 'ac_store' but under a different top-level directory
        ('my-config', not 'config').  The rule must require the standard
        top-level directory.
        """
        groups = group_files_by_type(["my-config/ac_store/leftover.yaml"])
        self.assertNotIn(
            FileGroup.SHIPPED_ACS,
            groups,
            msg=(
                "my-config/ac_store/leftover.yaml was incorrectly classified as "
                "SHIPPED_ACS — 'my-config' is not the expected 'config' directory."
            ),
        )

    def test_ac2_tools_reconfig_not_shipped_acs(self):
        # covers: BO-1100a-6-i
        """tools/reconfig/ac_store_migrator.py must NOT be SHIPPED_ACS.

        The path contains 'ac' and 'config' as substrings but none of the
        known ac_store patterns apply.
        """
        groups = group_files_by_type(["tools/reconfig/ac_store_migrator.py"])
        self.assertNotIn(
            FileGroup.SHIPPED_ACS,
            groups,
            msg=(
                "tools/reconfig/ac_store_migrator.py was incorrectly classified as "
                "SHIPPED_ACS — the rule must not match arbitrary substrings."
            ),
        )


# ===========================================================================
# AC BO-1100c-4 — Pattern config reflects current file on every invocation
# ===========================================================================


class TestPatternConfigReflectsCurrentFileOnEveryInvocation(unittest.TestCase):
    """AC BO-1100c-4: classify_staged_files() must re-read (or re-evaluate)
    commit_message_patterns.json on every call — it must not use a
    module-level cache that was loaded once at import time.

    Currently, DEFAULT_PATTERNS is populated at module-import time and never
    refreshed.  After the fix, a second call to classify_staged_files() after
    the on-disk config changes must reflect the NEW patterns.

    These tests currently fail because classify_staged_files() reads from the
    module-level DEFAULT_PATTERNS constant, which is set once at import time.
    """

    def test_ac3_updated_config_used_by_second_call(self):
        # covers: BO-1100c-4
        """After modifying the config file on disk, the next classify_staged_files()
        call must use the NEW patterns.

        The test:
        1. Writes an initial config to a temp file.
        2. Monkeypatches commit_classifier._PATTERNS_CONFIG_PATH to point at it.
        3. Makes a first call to classify_staged_files() (primes any runtime cache).
        4. Overwrites the config on disk with a custom ticket pattern.
        5. Makes a second call to classify_staged_files().
        6. Asserts that the second result uses the updated pattern.
        """
        import commit_classifier

        initial_data = {
            "patterns": {
                "tickets": "chore(tickets): {detail}",
                "new_acs": "feat(ac-store): {detail}",
                "shipped_acs": "chore(ac-store): {detail}",
                "implementation_code": "feat: {detail}",
                "status_changes": "chore(status): {detail}",
                "tests": "test: {detail}",
                "docs": "docs: {detail}",
                "config": "chore(config): {detail}",
                "unknown": "chore: {detail}",
            }
        }
        updated_data = dict(initial_data)
        updated_data["patterns"] = dict(initial_data["patterns"])
        updated_data["patterns"]["tickets"] = "UPDATED(tickets): {detail}"

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(initial_data, tmp)
            tmp_path = Path(tmp.name)

        original_config_path = commit_classifier._PATTERNS_CONFIG_PATH
        try:
            commit_classifier._PATTERNS_CONFIG_PATH = tmp_path

            # First call — seeds any runtime state.
            _first = classify_staged_files(["tickets/00_inbox/t.md"])

            # Overwrite the config on disk.
            tmp_path.write_text(json.dumps(updated_data), encoding="utf-8")

            # Second call — must reflect the updated config.
            second = classify_staged_files(["tickets/00_inbox/t.md"])

            self.assertTrue(
                second.suggested_subject.startswith("UPDATED(tickets):"),
                msg=(
                    f"classify_staged_files() used a stale import-time cache. "
                    f"Expected subject starting with 'UPDATED(tickets):' but got "
                    f"{second.suggested_subject!r}. The function must re-read the "
                    f"config on every invocation (AC BO-1100c-4)."
                ),
            )
        finally:
            commit_classifier._PATTERNS_CONFIG_PATH = original_config_path
            tmp_path.unlink(missing_ok=True)

    def test_ac3_deleted_config_uses_fallback_not_cached_patterns(self):
        # covers: BO-1100c-4
        """After a first call that loaded a CUSTOM pattern, deleting the config
        file and making a second call must produce the fallback subject — NOT
        the stale custom pattern that was in the now-deleted file.

        This test is deliberately stronger than a plain "fallback matches
        fallback" assertion.  It works as follows:

        1. Writes a config with a distinctive custom pattern for 'tickets'
           that differs from both the real config and the fallback.
        2. Monkeypatches _PATTERNS_CONFIG_PATH so classify_staged_files()
           reads only the temp file.
        3. First call — the custom pattern must be used (proves the
           monkeypatch works and that on-disk reading occurs).
        4. Deletes the config file.
        5. Second call — must NOT use the custom pattern (file is gone) and
           must instead produce the fallback subject.

        If classify_staged_files() caches patterns at import time (the current
        bug), the monkeypatching of _PATTERNS_CONFIG_PATH has no effect and
        neither the first call (which should show the custom pattern) nor the
        second call (which should show the fallback) will behave correctly.
        The test therefore catches the cache bug at step 3 (first call will
        NOT show the custom prefix) and fails there, which is the correct red
        signal for this AC.
        """
        import commit_classifier
        from commit_classifier import _FALLBACK_PATTERNS

        custom_tickets_prefix = "CUSTOM_CACHE_CHECK(tickets): "
        custom_data = {
            "patterns": {
                "tickets": f"{custom_tickets_prefix}{{detail}}",
                "new_acs": "feat(ac-store): {detail}",
                "shipped_acs": "chore(ac-store): {detail}",
                "implementation_code": "feat: {detail}",
                "status_changes": "chore(status): {detail}",
                "tests": "test: {detail}",
                "docs": "docs: {detail}",
                "config": "chore(config): {detail}",
                "unknown": "chore: {detail}",
            }
        }
        expected_fallback_prefix = _FALLBACK_PATTERNS[FileGroup.TICKETS].split("{detail}")[0]

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        ) as tmp:
            json.dump(custom_data, tmp)
            tmp_path = Path(tmp.name)

        original_config_path = commit_classifier._PATTERNS_CONFIG_PATH
        try:
            commit_classifier._PATTERNS_CONFIG_PATH = tmp_path

            # First call — with file present, MUST use the custom pattern.
            # (If the function uses the import-time DEFAULT_PATTERNS cache,
            # this assertion will fail — that IS the red state for AC BO-1100c-4.)
            first = classify_staged_files(["tickets/00_inbox/t.md"])
            self.assertTrue(
                first.suggested_subject.startswith("CUSTOM_CACHE_CHECK"),
                msg=(
                    f"classify_staged_files() used a stale import-time cache. "
                    f"Expected first call subject to start with 'CUSTOM_CACHE_CHECK' "
                    f"(custom config was present on disk), but got: "
                    f"{first.suggested_subject!r}. The function must re-read the "
                    f"config on every invocation (AC BO-1100c-4)."
                ),
            )

            # Delete the config file.
            tmp_path.unlink()

            # Second call — file gone, must fall back to compiled-in defaults.
            second = classify_staged_files(["tickets/00_inbox/t.md"])
            self.assertFalse(
                second.suggested_subject.startswith("CUSTOM_CACHE_CHECK"),
                msg=(
                    f"classify_staged_files() used a stale cache from a deleted "
                    f"config file. After the file is deleted, the function must "
                    f"fall back to compiled-in defaults (AC BO-1100c-4). Got: "
                    f"{second.suggested_subject!r}"
                ),
            )
            self.assertTrue(
                second.suggested_subject.startswith(expected_fallback_prefix),
                msg=(
                    f"Expected fallback prefix {expected_fallback_prefix!r} after "
                    f"config deletion, got {second.suggested_subject!r}."
                ),
            )
        finally:
            commit_classifier._PATTERNS_CONFIG_PATH = original_config_path
            # tmp_path may already be deleted in the happy path.
            tmp_path.unlink(missing_ok=True)


# ===========================================================================
# AC BO-1100d-5 — Observation store write failure does not crash workflow
# ===========================================================================


class TestObservationStoreWriteFailureIsSilent(unittest.TestCase):
    """AC BO-1100d-5: When the observation store path is read-only (or
    otherwise unwritable), maybe_propose_rule() must NOT propagate OSError.
    Instead it must:
      - log a WARNING,
      - return None gracefully.

    Currently record_unknown_shape() catches OSError but re-raises it, so
    maybe_propose_rule() propagates the exception to its caller.  The fix
    must swallow the OSError inside maybe_propose_rule() (or inside
    record_unknown_shape()) and return None instead.
    """

    def test_ac4_readonly_obs_path_does_not_raise(self):
        # covers: BO-1100d-5
        """maybe_propose_rule() must not raise OSError when the observation
        store is not writable.

        The test creates a read-only directory so that file creation inside it
        fails with PermissionError (a subclass of OSError), then verifies that
        maybe_propose_rule() catches it and returns None.
        """
        with tempfile.TemporaryDirectory() as tmp:
            readonly_dir = Path(tmp) / "readonly_store"
            readonly_dir.mkdir()
            obs_path = readonly_dir / "obs.jsonl"

            # Make the directory read-only so writes fail.
            readonly_dir.chmod(stat.S_IREAD | stat.S_IEXEC)
            try:
                result = maybe_propose_rule(
                    ["tools/foo.rb"],
                    obs_path=obs_path,
                )
                self.assertIsNone(
                    result,
                    msg=(
                        "maybe_propose_rule() should return None when the observation "
                        "store is unwritable, but raised or returned non-None."
                    ),
                )
            except OSError as exc:
                self.fail(
                    f"maybe_propose_rule() propagated OSError when observation store "
                    f"was read-only. It must catch and swallow the error (AC BO-1100d-5). "
                    f"Got: {exc}"
                )
            finally:
                # Restore write permission so the temp dir can be cleaned up.
                readonly_dir.chmod(stat.S_IRWXU)

    def test_ac4_write_failure_logs_warning(self):
        # covers: BO-1100d-5
        """A WARNING must be emitted when the observation store write fails.

        Uses patch to simulate an OSError on the open() call inside
        record_unknown_shape(), then asserts that a warning was logged.
        """
        with self.assertLogs("commit_pattern_learner", level="WARNING") as log_ctx:
            with patch(
                "commit_pattern_learner.record_unknown_shape",
                side_effect=OSError("simulated disk full"),
            ):
                result = maybe_propose_rule(["tools/foo.rb"])

        # Should return None (not raise).
        self.assertIsNone(result)

        # At least one WARNING must have been emitted.
        warning_msgs = [r for r in log_ctx.output if "WARNING" in r]
        self.assertTrue(
            len(warning_msgs) > 0,
            msg=(
                "Expected at least one WARNING log when observation store write "
                "fails, but none were emitted (AC BO-1100d-5)."
            ),
        )

    def test_ac4_returns_none_gracefully_on_write_failure(self):
        # covers: BO-1100d-5
        """Return value is None (not a raised exception) when write fails."""
        with patch(
            "commit_pattern_learner.record_unknown_shape",
            side_effect=OSError("simulated write error"),
        ):
            # Suppress the expected warning log to keep test output clean.
            with patch("commit_pattern_learner.logger"):
                result = maybe_propose_rule(["some/path.rb"])
        self.assertIsNone(
            result,
            msg=(
                "maybe_propose_rule() must return None on write failure, "
                "not propagate the OSError."
            ),
        )


# ===========================================================================
# AC BO-1100d-6 — Already-classified shapes not recorded as unknown
# ===========================================================================


class TestAlreadyClassifiedShapesNotRecordedAsUnknown(unittest.TestCase):
    """AC BO-1100d-6: maybe_propose_rule() must NOT write to the observation
    store when all staged files matched a known pattern (i.e. when the
    classify_staged_files() call returned specific_pattern_matched=True).

    Currently maybe_propose_rule() records every call, even when the commit
    agent would never call it (because a specific pattern matched).  The fix
    must add a guard — either a new parameter or an internal check — so that
    known shapes are excluded from the observation store.

    The simplest fix is to add a `classification_was_unknown: bool` parameter
    to maybe_propose_rule() that defaults to True for backward compatibility,
    and to only write the observation when it is True.
    """

    def test_ac5_known_classification_does_not_write_obs_store(self):
        # covers: BO-1100d-6
        """When classification_was_unknown=False is passed, the observation
        store must NOT be written.

        After the fix, maybe_propose_rule() accepts a `classification_was_unknown`
        keyword argument.  When False, the function returns None immediately
        without touching the observation store.
        """
        with tempfile.TemporaryDirectory() as tmp:
            obs_path = Path(tmp) / "obs.jsonl"

            # Call with known-classified paths and classification_was_unknown=False.
            result = maybe_propose_rule(
                ["scripts/build.py"],
                obs_path=obs_path,
                classification_was_unknown=False,
            )

            self.assertIsNone(
                result,
                msg=(
                    "maybe_propose_rule() should return None immediately when "
                    "classification_was_unknown=False."
                ),
            )
            self.assertFalse(
                obs_path.exists(),
                msg=(
                    "maybe_propose_rule() wrote to the observation store even "
                    "though classification_was_unknown=False.  Known shapes must "
                    "not be recorded (AC BO-1100d-6)."
                ),
            )

    def test_ac5_known_classification_across_many_calls_never_accumulates(self):
        # covers: BO-1100d-6
        """Multiple calls with classification_was_unknown=False must not
        accumulate observations in the store.

        Even if called PROPOSAL_THRESHOLD times, no proposal should be returned
        and the store must remain empty.
        """
        with tempfile.TemporaryDirectory() as tmp:
            obs_path = Path(tmp) / "obs.jsonl"
            results = []
            for _ in range(PROPOSAL_THRESHOLD + 5):
                results.append(
                    maybe_propose_rule(
                        ["scripts/build.py"],
                        obs_path=obs_path,
                        classification_was_unknown=False,
                    )
                )

            self.assertTrue(
                all(r is None for r in results),
                msg=(
                    "maybe_propose_rule() returned a non-None proposal for a "
                    "known-classified shape.  The observation store must not "
                    "accumulate observations for known shapes (AC BO-1100d-6)."
                ),
            )
            self.assertFalse(
                obs_path.exists(),
                msg=(
                    "Observation store was created/written even when "
                    "classification_was_unknown=False."
                ),
            )

    def test_ac5_unknown_classification_still_records(self):
        # covers: BO-1100d-6
        """When classification_was_unknown=True (the default), the store IS written."""
        with tempfile.TemporaryDirectory() as tmp:
            obs_path = Path(tmp) / "obs.jsonl"
            maybe_propose_rule(
                ["tools/mystery.rb"],
                obs_path=obs_path,
                classification_was_unknown=True,
            )
            self.assertTrue(
                obs_path.exists(),
                msg=(
                    "Observation store was NOT written when "
                    "classification_was_unknown=True. The existing recording "
                    "behaviour must be preserved for unknown shapes."
                ),
            )


# ===========================================================================
# AC BO-1100e-4 — History filter wired into learning pipeline + positive bound
# ===========================================================================


class TestHistoryFilterWiredIntoPipeline(unittest.TestCase):
    """AC BO-1100e-4: filter_history_by_shape() must be called by
    maybe_propose_rule() when the occurrence threshold is reached.

    Currently maybe_propose_rule() never calls filter_history_by_shape().
    After the fix, once count >= threshold, the function calls
    filter_history_by_shape(shape) before (or while) generating the proposal,
    so that the git history can inform the proposal.

    Additionally, passing max_commits=0 to filter_history_by_shape() must
    raise ValueError (currently 0 passes through to git as --max-count=0
    which returns no commits silently, a logic error).
    """

    def test_ac6_filter_history_called_when_threshold_reached(self):
        # covers: BO-1100e-4
        """filter_history_by_shape() must be invoked by maybe_propose_rule()
        when the observation count reaches the threshold.

        The test patches filter_history_by_shape and asserts it was called at
        least once during the run that crosses the threshold.
        """
        with tempfile.TemporaryDirectory() as tmp:
            obs_path = Path(tmp) / "obs.jsonl"
            paths = ["tools/foo.rb"]

            with patch(
                "commit_pattern_learner.filter_history_by_shape",
                return_value=[],
            ) as mock_filter:
                # Run exactly threshold times so the last call triggers the proposal.
                for _ in range(PROPOSAL_THRESHOLD):
                    maybe_propose_rule(paths, obs_path=obs_path)

            self.assertTrue(
                mock_filter.called,
                msg=(
                    "filter_history_by_shape() was never called by "
                    "maybe_propose_rule() even though the threshold was reached. "
                    "The history filter must be wired into the learning pipeline "
                    "(AC BO-1100e-4)."
                ),
            )

    def test_ac6_max_commits_zero_raises_value_error(self):
        # covers: BO-1100e-4
        """filter_history_by_shape(max_commits=0) must raise ValueError.

        max_commits=0 is a logical error (git --max-count=0 returns nothing).
        The function must validate the parameter and raise ValueError with a
        descriptive message before invoking git.
        """
        from commit_pattern_learner import extract_shape

        shape = extract_shape(["scripts/build.py"])
        with self.assertRaises(
            ValueError,
            msg=(
                "filter_history_by_shape(max_commits=0) must raise ValueError "
                "but did not.  A zero commit limit is a logic error that silently "
                "returns no history (AC BO-1100e-4)."
            ),
        ):
            filter_history_by_shape(shape, max_commits=0)


# ===========================================================================
# AC BO-1100e-4-i — Negative max_commits rejected
# ===========================================================================


class TestNegativeMaxCommitsRejected(unittest.TestCase):
    """AC BO-1100e-4-i: filter_history_by_shape() must raise ValueError for
    any negative max_commits value.

    Currently negative values pass through unchecked and reach git as
    '--max-count=-1', which git interprets as "unlimited" — a silent
    correctness violation that defeats the bounding guarantee of AC BO-1100e.
    """

    def test_ac7_max_commits_minus_one_raises_value_error(self):
        # covers: BO-1100e-4-i
        """filter_history_by_shape(max_commits=-1) must raise ValueError."""
        from commit_pattern_learner import extract_shape

        shape = extract_shape(["scripts/build.py"])
        with self.assertRaises(
            ValueError,
            msg=(
                "filter_history_by_shape(max_commits=-1) must raise ValueError. "
                "Negative values pass --max-count=-1 to git, which disables the "
                "bounding guarantee (AC BO-1100e-4-i)."
            ),
        ):
            filter_history_by_shape(shape, max_commits=-1)

    def test_ac7_max_commits_minus_100_raises_value_error(self):
        # covers: BO-1100e-4-i
        """filter_history_by_shape(max_commits=-100) must raise ValueError."""
        from commit_pattern_learner import extract_shape

        shape = extract_shape(["scripts/build.py"])
        with self.assertRaises(
            ValueError,
            msg=(
                "filter_history_by_shape(max_commits=-100) must raise ValueError. "
                "Any negative max_commits defeats the bounding guarantee (AC BO-1100e-4-i)."
            ),
        ):
            filter_history_by_shape(shape, max_commits=-100)

    def test_ac7_positive_max_commits_still_accepted(self):
        # covers: BO-1100e-4-i
        """Positive max_commits values must still be accepted (regression guard)."""
        from commit_pattern_learner import extract_shape

        shape = extract_shape(["scripts/build.py"])
        # Should NOT raise — positive value is valid.
        try:
            with patch(
                "commit_pattern_learner.subprocess.run",
                return_value=MagicMock(returncode=0, stdout="", stderr=""),
            ):
                filter_history_by_shape(shape, max_commits=50, repo_root=Path("/fake"))
        except ValueError as exc:
            self.fail(
                f"filter_history_by_shape() raised ValueError for a valid positive "
                f"max_commits=50: {exc}. Only non-positive values should be rejected."
            )


if __name__ == "__main__":
    unittest.main()
