"""
MODULE: unit_tests/feedback/test_submit_feedback.py
GOAL: Regression tests for AC INF-100c-1 (config resolution anchored to
      the script's own location) and AC INF-100c-3 (all standard phase agents
      listed in allowed_writers for the categories they interact with).
BUSINESS CONTEXT: submit_feedback.py is the single write chokepoint for the
      Central Feedback Collection System. These tests guard against two classes
      of regression: (1) config resolution reverting to CWD-relative lookup,
      which breaks invocations from any working directory other than the repo
      root; (2) missing phase agents in allowed_writers, which silently rejects
      valid feedback submissions from standard phase agents.
ARCHITECTURE: Tests import submit_feedback.py via importlib.util to load the
      module without adding it to sys.modules permanently, avoiding namespace
      pollution between test classes. YAML assertions read the actual on-disk
      feedback_categories.yaml rather than a synthetic fixture so the tests
      fail immediately when the real file diverges from expectations.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from typing import ClassVar

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUBMIT_SCRIPT = _REPO_ROOT / "scripts" / "feedback" / "submit_feedback.py"
_CATEGORIES_FILE = _REPO_ROOT / "config" / "feedback_categories.yaml"

# ---------------------------------------------------------------------------
# Required phase agents per AC INF-100c-3
# ---------------------------------------------------------------------------

REQUIRED_PHASE_AGENTS = frozenset([
    "python-coder",
    "sql-coder",
    "frontend-coder",
    "llm-expert",
    "test-writer",
    "test-runner",
    "pr-reviewer",
    "commit",
])

# Categories that must include all standard phase agents.
# Excluded by design: quality-concern (reviewer-class), subagent-quality
# (supervisor-only), process-finding (hook-only).
BROAD_CATEGORIES = frozenset([
    "complete",
    "knowledge-gap",
    "tooling-issue",
    "convention-ambiguity",
    "blocker",
    "success-pattern",
])


# ---------------------------------------------------------------------------
# Module loader helper
# ---------------------------------------------------------------------------


def _load_submit_module(module_name: str = "submit_feedback"):
    """Load submit_feedback.py via importlib to avoid sys.modules pollution.

    Args:
        module_name: Module name for importlib registration; use a unique
            suffix per test class to avoid cross-test interference.

    Returns:
        module: The loaded submit_feedback module object.
    """
    spec = importlib.util.spec_from_file_location(module_name, str(_SUBMIT_SCRIPT))
    assert spec is not None and spec.loader is not None, f"could not load spec for {_SUBMIT_SCRIPT}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# INF-100c-1: Config resolution is anchored to the script's own location
# ---------------------------------------------------------------------------


class TestConfigResolutionAnchoring(unittest.TestCase):
    """AC INF-100c-1: config is resolved relative to __file__, not the process cwd."""

    def test_find_config_root_returns_file_relative_path(self):
        """_find_config_root() must return parents[2]/config of the script file.

        Covers: INF-100c-1.
        """
        # covers: INF-100c-1
        mod = _load_submit_module("sfb_anchor")
        result = mod._find_config_root()
        expected = _SUBMIT_SCRIPT.resolve().parents[2] / "config"
        self.assertEqual(
            result.resolve(),
            expected.resolve(),
            f"_find_config_root() returned {result!r}, expected {expected!r}. "
            "Config resolution may be CWD-dependent.",
        )

    def test_categories_file_module_constant_is_script_relative(self):
        """_CATEGORIES_FILE module constant must be anchored to the script location.

        Covers: INF-100c-1.
        """
        # covers: INF-100c-1
        mod = _load_submit_module("sfb_const")
        expected = (
            _SUBMIT_SCRIPT.resolve().parents[2] / "config" / "feedback_categories.yaml"
        )
        self.assertEqual(
            mod._CATEGORIES_FILE.resolve(),
            expected.resolve(),
            f"_CATEGORIES_FILE is {mod._CATEGORIES_FILE!r}, expected {expected!r}.",
        )

    def test_config_root_is_absolute_not_cwd_relative(self):
        """_find_config_root() must return an absolute path (not CWD-relative).

        Covers: INF-100c-1.
        """
        # covers: INF-100c-1
        mod = _load_submit_module("sfb_abs")
        result = mod._find_config_root()
        self.assertTrue(
            result.is_absolute(),
            f"_find_config_root() returned a non-absolute path: {result!r}. "
            "This indicates CWD dependency.",
        )

    def test_config_file_exists_at_resolved_path(self):
        """feedback_categories.yaml must exist at the script-relative resolved path.

        Covers: INF-100c-1.
        """
        # covers: INF-100c-1
        mod = _load_submit_module("sfb_exist")
        categories_path = mod._CATEGORIES_FILE
        self.assertTrue(
            categories_path.exists(),
            f"feedback_categories.yaml not found at resolved path: {categories_path}. "
            "Config resolution is broken or the config file is missing.",
        )

    def test_config_root_matches_categories_file_parent(self):
        """_find_config_root() and _CATEGORIES_FILE.parent must agree.

        Covers: INF-100c-1.
        """
        # covers: INF-100c-1
        mod = _load_submit_module("sfb_parity")
        config_root = mod._find_config_root()
        file_parent = mod._CATEGORIES_FILE.parent
        self.assertEqual(
            config_root.resolve(),
            file_parent.resolve(),
            "_find_config_root() and _CATEGORIES_FILE.parent disagree — "
            f"root={config_root!r}, parent={file_parent!r}.",
        )


# ---------------------------------------------------------------------------
# INF-100c-3: All standard phase agents in allowed_writers
# ---------------------------------------------------------------------------


class TestAllPhaseAgentsInAllowedWriters(unittest.TestCase):
    """AC INF-100c-3: all required phase agents are in allowed_writers for broad categories."""

    cats: ClassVar[dict] = {}

    @classmethod
    def setUpClass(cls):
        """Load feedback_categories.yaml once for all subtests in this class."""
        try:
            import yaml  # type: ignore[import]
        except ImportError as exc:
            msg = "PyYAML is not installed — skipping INF-100c-3 YAML assertions."
            raise unittest.SkipTest(msg) from exc
        try:
            with open(_CATEGORIES_FILE, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except OSError as exc:
            msg = f"Cannot read feedback_categories.yaml at {_CATEGORIES_FILE}: {exc}"
            raise unittest.SkipTest(msg) from exc
        cls.cats = {entry["id"]: entry for entry in data.get("categories", [])}

    def test_all_broad_categories_present_in_yaml(self):
        """All broad categories must exist in feedback_categories.yaml.

        Covers: INF-100c-3 (prerequisite — categories must exist before agents
        can be validated against them).
        """
        # covers: INF-100c-3
        for cat_id in sorted(BROAD_CATEGORIES):
            with self.subTest(category=cat_id):
                self.assertIn(
                    cat_id,
                    self.cats,
                    f"Category '{cat_id}' is missing from feedback_categories.yaml.",
                )

    def test_python_coder_in_all_broad_categories(self):
        """python-coder must be in allowed_writers for every broad category.

        Covers: INF-100c-3.
        """
        # covers: INF-100c-3
        self._assert_agent_in_broad_categories("python-coder")

    def test_sql_coder_in_all_broad_categories(self):
        """sql-coder must be in allowed_writers for every broad category.

        Covers: INF-100c-3.
        """
        # covers: INF-100c-3
        self._assert_agent_in_broad_categories("sql-coder")

    def test_frontend_coder_in_all_broad_categories(self):
        """frontend-coder must be in allowed_writers for every broad category.

        Covers: INF-100c-3.
        """
        # covers: INF-100c-3
        self._assert_agent_in_broad_categories("frontend-coder")

    def test_llm_expert_in_all_broad_categories(self):
        """llm-expert must be in allowed_writers for every broad category.

        Covers: INF-100c-3.
        """
        # covers: INF-100c-3
        self._assert_agent_in_broad_categories("llm-expert")

    def test_test_writer_in_all_broad_categories(self):
        """test-writer must be in allowed_writers for every broad category.

        Covers: INF-100c-3.
        """
        # covers: INF-100c-3
        self._assert_agent_in_broad_categories("test-writer")

    def test_test_runner_in_all_broad_categories(self):
        """test-runner must be in allowed_writers for every broad category.

        Covers: INF-100c-3.
        """
        # covers: INF-100c-3
        self._assert_agent_in_broad_categories("test-runner")

    def test_pr_reviewer_in_all_broad_categories(self):
        """pr-reviewer must be in allowed_writers for every broad category.

        Covers: INF-100c-3.
        """
        # covers: INF-100c-3
        self._assert_agent_in_broad_categories("pr-reviewer")

    def test_commit_agent_in_all_broad_categories(self):
        """commit must be in allowed_writers for every broad category.

        Covers: INF-100c-3.
        """
        # covers: INF-100c-3
        self._assert_agent_in_broad_categories("commit")

    def test_all_required_agents_present_in_success_pattern(self):
        """All required phase agents must appear in success-pattern allowed_writers.

        Covers: INF-100c-3 (success-pattern explicit check).
        """
        # covers: INF-100c-3
        cat = self.cats.get("success-pattern", {})
        allowed = set(cat.get("allowed_writers", []))
        missing = REQUIRED_PHASE_AGENTS - allowed
        self.assertEqual(
            missing,
            set(),
            f"success-pattern is missing required phase agents: {sorted(missing)}.",
        )

    def test_no_existing_historic_entries_removed(self):
        """Previously present well-known agents must still appear (additive-only constraint).

        Covers: INF-100c-3 (no existing entries removed).
        """
        # covers: INF-100c-3
        historic_agents = {
            "architect-review",
            "documentation-expert",
            "pr-reviewer",
            "commit",
        }
        checked_categories = ["complete", "knowledge-gap", "success-pattern"]
        for cat_id in checked_categories:
            cat = self.cats.get(cat_id, {})
            allowed = set(cat.get("allowed_writers", []))
            for agent in sorted(historic_agents):
                with self.subTest(category=cat_id, agent=agent):
                    self.assertIn(
                        agent,
                        allowed,
                        f"Historic agent '{agent}' was removed from '{cat_id}' "
                        "allowed_writers — the change must be additive-only.",
                    )

    def _assert_agent_in_broad_categories(self, agent: str) -> None:
        """Assert `agent` appears in allowed_writers for every broad category.

        Args:
            agent: Agent name string to check.
        """
        for cat_id in sorted(BROAD_CATEGORIES):
            cat = self.cats.get(cat_id, {})
            allowed = cat.get("allowed_writers", [])
            with self.subTest(category=cat_id):
                self.assertIn(
                    agent,
                    allowed,
                    f"Agent '{agent}' is missing from '{cat_id}' allowed_writers. "
                    "Add it to config/feedback_categories.yaml and the template copy.",
                )


if __name__ == "__main__":
    unittest.main()

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-07-08 [python-coder/EPIC-Phase1ReadyHardening/03_InfrastructureFixes]:
#   Initial test suite for AC INF-100c-1 (config resolution anchoring) and
#   AC INF-100c-3 (all phase agents in allowed_writers). Tests use importlib
#   to load submit_feedback.py from its tracked path and PyYAML to read the
#   actual feedback_categories.yaml. Both test classes are included in the
#   same file to co-locate the regression guards for the two ACs addressed
#   by ticket 03_InfrastructureFixes.
# ====================================================================
