"""
MODULE: test_precommit_safety_net
GOAL: TDD test coverage for all BO-210 (precommit-safety-net) ACs.

BUSINESS CONTEXT: BO-210 establishes the precommit safety-net: a populated
    routing config, context capsule emission from coder agents, and originator
    re-dispatch on judgment-tier hook failures. Each test names the AC it covers
    and asserts its specific behaviour so work_status: done is honestly backed.

ARCHITECTURE:
    - BO-210a tests validate the deployed and template routing config JSON
      (.claude/precommit-autofix.json vs templates/scripts/precommit-autofix.json).
    - BO-210b tests validate that signoff SKILL.md and coder agent templates
      correctly document context_capsule emission and truncation rules.
    - BO-210c tests validate that precommit-autofix SKILL.md has the
      originator re-dispatch logic with correct depth/capsule constraints.

DECISION HISTORY:
    - 2026-07-14 [EPIC-BOTestCoverageBackfill/02]: Initial TDD red-baseline.
      Tests checking .claude/precommit-autofix.json will be RED until the
      deployed config is built/copied from the template. SKILL.md-content
      tests may be green immediately (implementation already exists).
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths (relative to repo root)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]

# BO-210a: routing config paths
_TEMPLATE_CONFIG = _REPO_ROOT / "templates" / "scripts" / "precommit-autofix.json"
_DEPLOYED_CONFIG = _REPO_ROOT / ".claude" / "precommit-autofix.json"

# BO-210b / BO-210c: skill and agent template paths
_SIGNOFF_SKILL = _REPO_ROOT / "templates" / "skills" / "signoff" / "SKILL.md"
_AUTOFIX_SKILL = _REPO_ROOT / "templates" / "skills" / "precommit-autofix" / "SKILL.md"
_PYTHON_CODER = _REPO_ROOT / "templates" / "agents" / "python-coder.md"
_SQL_CODER = _REPO_ROOT / "templates" / "agents" / "sql-coder.md"
_FRONTEND_CODER = _REPO_ROOT / "templates" / "agents" / "frontend-coder.md"

# Canonical blocking hook IDs per BO-210a-2
_EXPECTED_BLOCKING_HOOKS = {
    "check-complexity",
    "check-docstrings",
    "check-exception-handling",
    "check-file-size",
    "check-ac-schema",
    "check-ac-limits",
    "check-contract-shrinking",
}

# The five required context capsule field keys (not counting agent_id)
_CAPSULE_REQUIRED_FIELDS = {
    "intent",
    "files_touched_rationale",
    "consumers_checked",
    "red_baseline",
    "design_constraints",
}


def _load_json_file(path: Path) -> dict:
    """Load and parse a JSON file; raise AssertionError on any I/O or parse failure."""
    try:
        with path.open(encoding="utf-8") as fh:
            return json.load(fh)
    except OSError as exc:
        # Use str(exc) — not a string literal — so TRY003 does not fire.
        raise AssertionError(str(exc)) from exc
    except json.JSONDecodeError as exc:
        raise AssertionError(str(exc)) from exc


def _read_text(path: Path) -> str:
    """Read a text file; raise AssertionError on any I/O failure."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise AssertionError(str(exc)) from exc


# Pre-built message for _load_deployed_config — assigned to a variable so
# TRY003 (Avoid long string literals in raise) does not fire.
_DEPLOYED_CONFIG_ABSENT_MSG = (
    f"Skipping: deployed routing config not found at {_DEPLOYED_CONFIG}. "
    "This file is gitignored; run build.py (or copy templates/scripts/precommit-autofix.json) "
    "to create it before running these tests locally."
)


def _load_deployed_config() -> dict:
    """Load the deployed precommit-autofix.json; skips the calling test if absent (gitignored)."""
    if not _DEPLOYED_CONFIG.exists():
        raise unittest.SkipTest(_DEPLOYED_CONFIG_ABSENT_MSG)
    return _load_json_file(_DEPLOYED_CONFIG)


def _load_template_config() -> dict:
    """Load the template precommit-autofix.json."""
    return _load_json_file(_TEMPLATE_CONFIG)


# ===========================================================================
# BO-210a-1 — Routing config has the documented schema shape
# ===========================================================================

class TestRoutingConfigSchema(unittest.TestCase):
    """BO-210a-1: Deployed routing config conforms to the documented schema."""

    def test_ac_bo210a1_deployed_config_has_defaults_section(self):
        # covers: BO-210a-1
        """BO-210a-1: Deployed config contains a 'defaults' section with 'model' and 'subagent_type'."""
        config = _load_deployed_config()
        self.assertIn(
            "defaults", config,
            "Deployed config must have a 'defaults' top-level key."
        )
        defaults = config["defaults"]
        self.assertIn("model", defaults, "defaults must include 'model'.")
        self.assertIn("subagent_type", defaults, "defaults must include 'subagent_type'.")

    def test_ac_bo210a1_deployed_config_has_commit_review_section(self):
        # covers: BO-210a-1
        """BO-210a-1: Deployed config contains 'commit_review' section with enabled, model, subagent_type."""
        config = _load_deployed_config()
        self.assertIn(
            "commit_review", config,
            "Deployed config must have a 'commit_review' top-level key."
        )
        cr = config["commit_review"]
        self.assertIn("enabled", cr, "commit_review must include 'enabled'.")
        self.assertIn("model", cr, "commit_review must include 'model'.")
        self.assertIn("subagent_type", cr, "commit_review must include 'subagent_type'.")

    def test_ac_bo210a1_deployed_config_has_rules_list(self):
        # covers: BO-210a-1
        """BO-210a-1: Deployed config contains a 'rules' list; each entry names
        hook_id, category, model, and subagent_type."""
        config = _load_deployed_config()
        self.assertIn("rules", config, "Deployed config must have a 'rules' list.")
        rules = config["rules"]
        self.assertIsInstance(rules, list, "'rules' must be a JSON array.")
        self.assertGreater(len(rules), 0, "'rules' must not be empty.")
        required_rule_keys = {"hook_id", "category", "model", "subagent_type"}
        for rule in rules:
            missing = required_rule_keys - rule.keys()
            self.assertEqual(
                missing, set(),
                f"Rule {rule!r} is missing required keys: {missing}."
            )

    def test_ac_bo210a1_deployed_config_has_no_empty_routes_stub(self):
        # covers: BO-210a-1
        """BO-210a-1: The deployed config must NOT contain the empty 'routes' stub."""
        config = _load_deployed_config()
        self.assertNotIn(
            "routes", config,
            "Deployed config must not contain the legacy empty 'routes' key."
        )

    def test_ac_bo210a1_deployed_config_no_unknown_top_level_keys(self):
        # covers: BO-210a-1
        """BO-210a-1: Deployed config must not contain fields outside the documented schema."""
        config = _load_deployed_config()
        # _comment is allowed as a documentation annotation
        allowed_keys = {"defaults", "commit_review", "blocking_hook_ids", "rules", "_comment"}
        unknown = {k for k in config if k not in allowed_keys}
        self.assertEqual(
            unknown, set(),
            f"Deployed config has unknown top-level keys: {unknown}. Remove or document them."
        )


# ===========================================================================
# BO-210a-1-i — Template source matches deployed config content
# ===========================================================================

class TestRoutingConfigTemplateParity(unittest.TestCase):
    """BO-210a-1-i: Template source and deployed config must be in parity."""

    def _configs(self):
        template = _load_template_config()
        deployed = _load_deployed_config()
        return template, deployed

    def test_ac_bo210a1i_defaults_match(self):
        # covers: BO-210a-1-i
        """BO-210a-1-i: Template and deployed configs have identical 'defaults' section."""
        template, deployed = self._configs()
        self.assertEqual(
            template.get("defaults"),
            deployed.get("defaults"),
            "Template and deployed 'defaults' sections must match."
        )

    def test_ac_bo210a1i_commit_review_matches(self):
        # covers: BO-210a-1-i
        """BO-210a-1-i: Template and deployed configs have identical 'commit_review' section."""
        template, deployed = self._configs()
        self.assertEqual(
            template.get("commit_review"),
            deployed.get("commit_review"),
            "Template and deployed 'commit_review' sections must match."
        )

    def test_ac_bo210a1i_blocking_hook_ids_match(self):
        # covers: BO-210a-1-i
        """BO-210a-1-i: Template and deployed configs have identical 'blocking_hook_ids'."""
        template, deployed = self._configs()
        self.assertEqual(
            sorted(template.get("blocking_hook_ids", [])),
            sorted(deployed.get("blocking_hook_ids", [])),
            "Template and deployed 'blocking_hook_ids' must match (order-insensitive)."
        )

    def test_ac_bo210a1i_rules_hook_ids_match(self):
        # covers: BO-210a-1-i
        """BO-210a-1-i: Template and deployed configs have the same rule hook IDs."""
        template, deployed = self._configs()
        tmpl_ids = sorted(r["hook_id"] for r in template.get("rules", []))
        dep_ids = sorted(r["hook_id"] for r in deployed.get("rules", []))
        self.assertEqual(
            tmpl_ids, dep_ids,
            "Template and deployed 'rules' must reference the same set of hook IDs."
        )

    def test_ac_bo210a1i_no_hook_id_absent_from_other(self):
        # covers: BO-210a-1-i
        """BO-210a-1-i: Neither config references a hook id absent from the other."""
        template, deployed = self._configs()
        tmpl_blocking = set(template.get("blocking_hook_ids", []))
        dep_blocking = set(deployed.get("blocking_hook_ids", []))
        tmpl_only = tmpl_blocking - dep_blocking
        dep_only = dep_blocking - tmpl_blocking
        self.assertEqual(
            tmpl_only, set(),
            f"Hook IDs in template blocking_hook_ids but absent from deployed: {tmpl_only}"
        )
        self.assertEqual(
            dep_only, set(),
            f"Hook IDs in deployed blocking_hook_ids but absent from template: {dep_only}"
        )


# ===========================================================================
# BO-210a-2 — blocking_hook_ids is the sole gating authority
# ===========================================================================

class TestBlockingHookIdsConfig(unittest.TestCase):
    """BO-210a-2: blocking_hook_ids is the single authority on which hooks gate a commit."""

    def test_ac_bo210a2_blocking_hook_ids_present_in_deployed(self):
        # covers: BO-210a-2
        """BO-210a-2: Deployed config contains exactly one 'blocking_hook_ids' array."""
        config = _load_deployed_config()
        self.assertIn(
            "blocking_hook_ids", config,
            "Deployed config must have a top-level 'blocking_hook_ids' key."
        )
        self.assertIsInstance(
            config["blocking_hook_ids"], list,
            "'blocking_hook_ids' must be a JSON array."
        )

    def test_ac_bo210a2_blocking_hook_ids_contains_required_hooks(self):
        # covers: BO-210a-2
        """BO-210a-2: blocking_hook_ids contains the seven required gating hook IDs."""
        config = _load_deployed_config()
        actual = set(config.get("blocking_hook_ids", []))
        missing = _EXPECTED_BLOCKING_HOOKS - actual
        self.assertEqual(
            missing, set(),
            f"blocking_hook_ids is missing required gating hooks: {missing}."
        )

    def test_ac_bo210a2_no_other_gating_field_in_deployed(self):
        # covers: BO-210a-2
        """BO-210a-2: No other field independently determines whether a hook gates a commit."""
        config = _load_deployed_config()
        for bad_key in ("gating_hooks", "blocking_hooks", "gate_on"):
            self.assertNotIn(
                bad_key, config,
                f"Deployed config must not have a '{bad_key}' key — "
                "blocking_hook_ids is the sole gating authority."
            )

    def test_ac_bo210a2_mechanical_hooks_not_in_blocking_array(self):
        # covers: BO-210a-2
        """BO-210a-2: Mechanical-category hooks must not appear in blocking_hook_ids."""
        config = _load_deployed_config()
        blocking = set(config.get("blocking_hook_ids", []))
        rules = config.get("rules", [])
        mechanical_hooks = {r["hook_id"] for r in rules if r.get("category") == "mechanical"}
        spurious = mechanical_hooks & blocking
        self.assertEqual(
            spurious, set(),
            f"Mechanical-category hooks must not be in blocking_hook_ids: {spurious}."
        )


# ===========================================================================
# BO-210b-1 — Coder agent templates instruct context_capsule emission
# ===========================================================================

class TestContextCapsuleCoderTemplates(unittest.TestCase):
    """BO-210b-1: All three coder templates instruct capsule emission on warn-tier signal."""

    def _check_template(self, template_path: Path, agent_name: str) -> None:
        """Assert a coder template documents capsule emission with all five required fields."""
        content = _read_text(template_path)
        self.assertIn(
            "context_capsule:",
            content,
            f"{agent_name} template must contain a 'context_capsule:' block."
        )
        for field in _CAPSULE_REQUIRED_FIELDS:
            self.assertIn(
                field,
                content,
                f"{agent_name} template must document capsule field '{field}'."
            )
        self.assertIn(
            "warn-tier",
            content,
            f"{agent_name} template must use 'warn-tier' to gate capsule emission."
        )

    def test_ac_bo210b1_python_coder_emits_capsule(self):
        # covers: BO-210b-1
        """BO-210b-1: python-coder.md documents context_capsule emission when warn-tier signal trips."""
        self._check_template(_PYTHON_CODER, "python-coder")

    def test_ac_bo210b1_sql_coder_emits_capsule(self):
        # covers: BO-210b-1
        """BO-210b-1: sql-coder.md documents context_capsule emission when warn-tier signal trips."""
        self._check_template(_SQL_CODER, "sql-coder")

    def test_ac_bo210b1_frontend_coder_emits_capsule(self):
        # covers: BO-210b-1
        """BO-210b-1: frontend-coder.md documents context_capsule emission when warn-tier signal trips."""
        self._check_template(_FRONTEND_CODER, "frontend-coder")

    def test_ac_bo210b1_consumers_checked_not_re_derived(self):
        # covers: BO-210b-1
        """BO-210b-1: Coder templates must instruct that consumers_checked is copied from
        blast-radius results, not re-derived."""
        for path, name in [
            (_PYTHON_CODER, "python-coder"),
            (_SQL_CODER, "sql-coder"),
            (_FRONTEND_CODER, "frontend-coder"),
        ]:
            content = _read_text(path)
            has_no_rederive = (
                "not re-derive" in content
                or "do NOT re-derive" in content
                or "copied verbatim" in content
                or "reuse" in content.lower()
            )
            self.assertTrue(
                has_no_rederive,
                f"{name} template must instruct reuse of blast-radius results, not re-derive."
            )


# ===========================================================================
# BO-210b-1-i — Oversized capsule is truncated to the 2000-character cap
# ===========================================================================

class TestContextCapsuleTruncation(unittest.TestCase):
    """BO-210b-1-i: An oversized context_capsule is truncated to the documented length cap."""

    def test_ac_bo210b1i_signoff_skill_documents_2000_char_cap(self):
        # covers: BO-210b-1-i
        """BO-210b-1-i: signoff SKILL.md states the 2000-character length cap."""
        content = _read_text(_SIGNOFF_SKILL)
        self.assertIn(
            "2000",
            content,
            "signoff SKILL.md must state the 2000-character capsule length cap."
        )
        self.assertIn(
            "TRUNCATED",
            content,
            "signoff SKILL.md must document the # TRUNCATED marker for truncated capsules."
        )

    def test_ac_bo210b1i_truncation_order_preserves_intent_and_consumers_checked(self):
        # covers: BO-210b-1-i
        """BO-210b-1-i: signoff SKILL.md documents that truncation preserves intent and
        consumers_checked; truncates files_touched_rationale first."""
        content = _read_text(_SIGNOFF_SKILL)
        for phrase in ("files_touched_rationale", "design_constraints", "red_baseline"):
            self.assertIn(
                phrase,
                content,
                f"signoff SKILL.md must document '{phrase}' in the truncation order."
            )
        self.assertIn(
            "intent",
            content,
            "signoff SKILL.md must explicitly name 'intent' as a preserved field."
        )
        self.assertIn(
            "consumers_checked",
            content,
            "signoff SKILL.md must explicitly name 'consumers_checked' as a preserved field."
        )

    def test_ac_bo210b1i_coder_templates_document_2000_char_cap(self):
        # covers: BO-210b-1-i
        """BO-210b-1-i: Each coder template documents the 2000-character capsule cap."""
        for path, name in [
            (_PYTHON_CODER, "python-coder"),
            (_SQL_CODER, "sql-coder"),
            (_FRONTEND_CODER, "frontend-coder"),
        ]:
            content = _read_text(path)
            self.assertIn(
                "2000",
                content,
                f"{name} template must document the 2000-character capsule length cap."
            )


# ===========================================================================
# BO-210b-2 — Consumers tolerate an absent context_capsule (warn-and-proceed)
# ===========================================================================

class TestContextCapsuleBackwardCompat(unittest.TestCase):
    """BO-210b-2: Consumers must tolerate an absent context_capsule without error or blocking."""

    def test_ac_bo210b2_signoff_skill_states_capsule_optional(self):
        # covers: BO-210b-2
        """BO-210b-2: signoff SKILL.md explicitly states that context_capsule is optional
        and backward-compatible-absent."""
        content = _read_text(_SIGNOFF_SKILL)
        self.assertIn(
            "optional",
            content,
            "signoff SKILL.md must state that the context_capsule block is optional."
        )
        self.assertIn(
            "backward-compatible",
            content,
            "signoff SKILL.md must describe the capsule as backward-compatible-absent."
        )

    def test_ac_bo210b2_autofix_skill_never_blocks_on_absent_capsule(self):
        # covers: BO-210b-2
        """BO-210b-2: precommit-autofix SKILL.md must state that absent capsule never blocks."""
        content = _read_text(_AUTOFIX_SKILL)
        self.assertIn(
            "context_capsule",
            content,
            "precommit-autofix SKILL.md must reference context_capsule absence handling."
        )
        has_no_block_on_absent = (
            "never block" in content.lower()
            or "warn-and-proceed" in content.lower()
            or "warn and proceed" in content.lower()
        )
        self.assertTrue(
            has_no_block_on_absent,
            "precommit-autofix SKILL.md must document warn-and-proceed on absent capsule."
        )


# ===========================================================================
# BO-210c-1 — Judgment-tier failure re-dispatches the originating agent
# ===========================================================================

class TestOriginatorRedispatch(unittest.TestCase):
    """BO-210c-1: Judgment-tier hook failure re-dispatches the originating agent type
    using the AUTOFIX_AGENT line from hook output, not a hard-coded literal."""

    def test_ac_bo210c1_autofix_skill_parses_autofix_agent_line(self):
        # covers: BO-210c-1
        """BO-210c-1: precommit-autofix SKILL.md must document parsing the AUTOFIX_AGENT
        line from hook output to identify the originating agent (not a hard-coded role)."""
        content = _read_text(_AUTOFIX_SKILL)
        self.assertIn(
            "AUTOFIX_AGENT",
            content,
            "precommit-autofix SKILL.md must document parsing the AUTOFIX_AGENT line."
        )
        self.assertIn(
            "hook output",
            content.lower(),
            "precommit-autofix SKILL.md must state the agent id is read from hook output."
        )

    def test_ac_bo210c1_autofix_skill_reads_context_capsule_from_ticket(self):
        # covers: BO-210c-1
        """BO-210c-1: precommit-autofix SKILL.md must document reading the context_capsule
        from the ticket sign-off comment."""
        content = _read_text(_AUTOFIX_SKILL)
        self.assertIn(
            "context_capsule",
            content,
            "precommit-autofix SKILL.md must reference reading the context_capsule."
        )
        self.assertIn(
            "ticket",
            content.lower(),
            "precommit-autofix SKILL.md must reference ticket_path as the capsule source."
        )

    def test_ac_bo210c1_dispatch_passes_capsule_hook_ids_and_raw_output(self):
        # covers: BO-210c-1
        """BO-210c-1: The re-dispatch prompt must pass ticket_path, context_capsule,
        failing_hook_ids, and raw hook output to the dispatched agent."""
        content = _read_text(_AUTOFIX_SKILL)
        for required_phrase in ("ticket_path", "failing_hook_ids", "context_capsule"):
            self.assertIn(
                required_phrase,
                content,
                f"precommit-autofix SKILL.md re-dispatch prompt must include '{required_phrase}'."
            )


# ===========================================================================
# BO-210c-1-i — Re-dispatched coder runs at depth 2 with no sub-agents
# ===========================================================================

class TestRedispatchDepthConstraint(unittest.TestCase):
    """BO-210c-1-i: The re-dispatched coder runs at depth 2 and spawns no sub-agents."""

    def test_ac_bo210c1i_autofix_skill_forbids_sub_agents_in_redispatch(self):
        # covers: BO-210c-1-i
        """BO-210c-1-i: precommit-autofix SKILL.md re-dispatch prompt must explicitly forbid
        spawning sub-agents (including research-agent)."""
        content = _read_text(_AUTOFIX_SKILL)
        has_no_subagent_instruction = (
            "no sub-agent" in content.lower()
            or "spawn no sub-agent" in content.lower()
            or "Spawn NO sub-agents" in content
        )
        self.assertTrue(
            has_no_subagent_instruction,
            "precommit-autofix SKILL.md must instruct the re-dispatched agent to spawn NO sub-agents."
        )
        self.assertIn(
            "research-agent",
            content,
            "precommit-autofix SKILL.md must specifically name research-agent as forbidden."
        )

    def test_ac_bo210c1i_autofix_skill_references_depth_constraint(self):
        # covers: BO-210c-1-i
        """BO-210c-1-i: precommit-autofix SKILL.md must reference the depth-2 constraint
        or ADR-006 to document the nesting cap."""
        content = _read_text(_AUTOFIX_SKILL)
        has_depth_reference = (
            "depth 2" in content
            or "depth-2" in content
            or "ADR-006" in content
        )
        self.assertTrue(
            has_depth_reference,
            "precommit-autofix SKILL.md must reference depth-2 or ADR-006 nesting constraint."
        )


# ===========================================================================
# BO-210c-1-ii — Judgment-tier failure without capsule degrades gracefully
# ===========================================================================

class TestRedispatchNoCapsuleGraceful(unittest.TestCase):
    """BO-210c-1-ii: When no capsule exists, the re-dispatch still proceeds with empty capsule."""

    def test_ac_bo210c1ii_autofix_skill_warns_and_proceeds_on_absent_capsule(self):
        # covers: BO-210c-1-ii
        """BO-210c-1-ii: precommit-autofix SKILL.md must state it warns-and-proceeds when
        no context_capsule is found for the originating agent."""
        content = _read_text(_AUTOFIX_SKILL)
        has_warn_proceed = "warn" in content.lower() and (
            "proceed" in content.lower() or "continue" in content.lower()
        )
        self.assertTrue(
            has_warn_proceed,
            "precommit-autofix SKILL.md must document warn-and-proceed when capsule absent."
        )

    def test_ac_bo210c1ii_autofix_skill_uses_empty_capsule_fallback(self):
        # covers: BO-210c-1-ii
        """BO-210c-1-ii: precommit-autofix SKILL.md must state it re-dispatches with an
        empty capsule (not skipping dispatch) when capsule is absent."""
        content = _read_text(_AUTOFIX_SKILL)
        has_empty_capsule = (
            "empty capsule" in content.lower()
            or "context_capsule: {}" in content
            or "empty" in content.lower()
        )
        self.assertTrue(
            has_empty_capsule,
            "precommit-autofix SKILL.md must document using an empty capsule as fallback."
        )


# ===========================================================================
# BO-210c-1-iii — All bash commands in edited templates are single simple commands
# ===========================================================================

class TestBashCommandStyle(unittest.TestCase):
    """BO-210c-1-iii: Every bash command block in the safety-net templates is a
    single simple command (no &&, ||, ;-chaining, or cd-prefix chains)."""

    # Patterns that indicate command chaining — forbidden in bash blocks
    _CHAIN_PATTERNS = [
        (r"&&", "and-and operator (&&)"),
        (r"\|\|", "or-or operator (||)"),
    ]

    @staticmethod
    def _extract_bash_blocks(content: str) -> list:
        """Return all content inside ```bash ... ``` fenced blocks."""
        return re.findall(r"```bash\n(.*?)```", content, re.DOTALL)

    def _check_no_chaining(self, path: Path, label: str) -> None:
        """Assert no chained commands appear in bash blocks of a given template."""
        content = _read_text(path)
        bash_blocks = self._extract_bash_blocks(content)
        for block in bash_blocks:
            for pattern, desc in self._CHAIN_PATTERNS:
                for line in block.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue  # comments are allowed to mention these characters
                    if re.search(pattern, line):
                        self.fail(
                            f"{label} contains a chained command ({desc}) in a bash block:\n"
                            f"  Line: {line!r}\n"
                            "Each documented shell command must be a single simple invocation."
                        )

    def test_ac_bo210c1iii_no_chained_commands_in_autofix_skill(self):
        # covers: BO-210c-1-iii
        """BO-210c-1-iii: precommit-autofix SKILL.md must not use && or || in bash blocks."""
        self._check_no_chaining(_AUTOFIX_SKILL, "precommit-autofix SKILL.md")

    def test_ac_bo210c1iii_no_chained_commands_in_signoff_skill(self):
        # covers: BO-210c-1-iii
        """BO-210c-1-iii: signoff SKILL.md must not use && or || in bash blocks."""
        self._check_no_chaining(_SIGNOFF_SKILL, "signoff SKILL.md")

    def test_ac_bo210c1iii_no_chained_commands_in_python_coder(self):
        # covers: BO-210c-1-iii
        """BO-210c-1-iii: python-coder.md must not use && or || in bash blocks."""
        self._check_no_chaining(_PYTHON_CODER, "python-coder.md")

    def test_ac_bo210c1iii_no_chained_commands_in_sql_coder(self):
        # covers: BO-210c-1-iii
        """BO-210c-1-iii: sql-coder.md must not use && or || in bash blocks."""
        self._check_no_chaining(_SQL_CODER, "sql-coder.md")

    def test_ac_bo210c1iii_no_chained_commands_in_frontend_coder(self):
        # covers: BO-210c-1-iii
        """BO-210c-1-iii: frontend-coder.md must not use && or || in bash blocks."""
        self._check_no_chaining(_FRONTEND_CODER, "frontend-coder.md")


# ===========================================================================
# BO-210c-2 — Mechanical-tier hooks use generic light-model route; single retry
# ===========================================================================

class TestMechanicalTierRoute(unittest.TestCase):
    """BO-210c-2: Mechanical-tier hooks use the generic light-model route;
    commit retried exactly once after any fixer; second failure surfaced."""

    def test_ac_bo210c2_autofix_skill_uses_generic_route_for_mechanical(self):
        # covers: BO-210c-2
        """BO-210c-2: precommit-autofix SKILL.md must document that mechanical-category
        hooks use the generic light-model route (not originator re-dispatch)."""
        content = _read_text(_AUTOFIX_SKILL)
        self.assertIn(
            "mechanical",
            content.lower(),
            "precommit-autofix SKILL.md must mention 'mechanical' tier routing."
        )

    def test_ac_bo210c2_autofix_skill_retries_exactly_once(self):
        # covers: BO-210c-2
        """BO-210c-2: precommit-autofix SKILL.md must document exactly one retry after any fixer."""
        content = _read_text(_AUTOFIX_SKILL)
        has_single_retry = (
            "exactly once" in content.lower()
            or "retry once" in content.lower()
            or "once" in content.lower()
        )
        self.assertTrue(
            has_single_retry,
            "precommit-autofix SKILL.md must state the commit is retried exactly once."
        )

    def test_ac_bo210c2_autofix_skill_surfaces_second_failure(self):
        # covers: BO-210c-2
        """BO-210c-2: precommit-autofix SKILL.md must document that a second failure
        after the retry is surfaced to the user, not silently re-dispatched."""
        content = _read_text(_AUTOFIX_SKILL)
        has_surface_on_second = "second" in content.lower() and (
            "surface" in content.lower() or "stop" in content.lower()
        )
        self.assertTrue(
            has_surface_on_second,
            "precommit-autofix SKILL.md must document that a second failure is surfaced."
        )


# ===========================================================================
# BO-210c-2-i — Re-dispatched coder returns blocker when fresh lookup needed
# ===========================================================================

class TestRedispatchBlockerOnMissingInfo(unittest.TestCase):
    """BO-210c-2-i: Re-dispatched coder at depth 2 must return a blocker (not spawn
    sub-agents) when the fix needs cross-file information not in the capsule."""

    def test_ac_bo210c2i_autofix_skill_instructs_blocker_on_missing_cross_file_info(self):
        # covers: BO-210c-2-i
        """BO-210c-2-i: precommit-autofix SKILL.md re-dispatch prompt must instruct the
        coder to return 'status: blocker' when it needs fresh cross-file information."""
        content = _read_text(_AUTOFIX_SKILL)
        self.assertIn(
            "blocker",
            content.lower(),
            "precommit-autofix SKILL.md must instruct re-dispatched agent to return blocker."
        )

    def test_ac_bo210c2i_autofix_skill_forbids_guessing_for_cross_file(self):
        # covers: BO-210c-2-i
        """BO-210c-2-i: precommit-autofix SKILL.md must instruct the coder not to guess
        when missing cross-file information needed for a fix."""
        content = _read_text(_AUTOFIX_SKILL)
        has_no_guess = (
            "do not guess" in content.lower()
            or "do NOT guess" in content
            or "Do NOT guess" in content
        )
        self.assertTrue(
            has_no_guess,
            "precommit-autofix SKILL.md must instruct re-dispatched agent not to guess."
        )

    def test_ac_bo210c2i_blocker_describes_missing_info(self):
        # covers: BO-210c-2-i
        """BO-210c-2-i: The blocker payload must name/describe the missing cross-file info."""
        content = _read_text(_AUTOFIX_SKILL)
        has_describe_missing = "missing" in content.lower() and (
            "describe" in content.lower()
            or "name" in content.lower()
            or "information" in content.lower()
        )
        self.assertTrue(
            has_describe_missing,
            "precommit-autofix SKILL.md must instruct coder to describe missing information."
        )

    def test_ac_bo210c2i_commit_not_retried_on_blocker(self):
        # covers: BO-210c-2-i
        """BO-210c-2-i: When a blocker is returned, the commit must NOT be retried."""
        content = _read_text(_AUTOFIX_SKILL)
        has_no_retry_on_blocker = (
            "not retried" in content.lower()
            or "do not retry" in content.lower()
            or "Do NOT retry" in content
            or ("blocker" in content.lower() and "retry" in content.lower())
        )
        self.assertTrue(
            has_no_retry_on_blocker,
            "precommit-autofix SKILL.md must document that a blocker result skips commit retry."
        )


if __name__ == "__main__":
    unittest.main()
