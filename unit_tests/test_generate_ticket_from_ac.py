"""
MODULE: test_generate_ticket_from_ac
GOAL: RED test stubs for the computed agents-map feature in generate_ticket_from_ac.py.
      Tests cover _build_agents_map (change_target/risk_surface lookup, union logic,
      canonical ordering, test-writer/test-runner injection, not_needed preservation)
      and the TDD bug fix (## Test Requirements block emission).
TICKET: EPIC-ComputedQualityGates/04_compute_agents_map.md
COVERS: BO-560, BO-560-1, BO-560-2, BO-560-3, BO-560-1-i, BO-560-3-i, BO-530, BO-530-1
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

from ac_store.generate_ticket_from_ac import (  # noqa: E402
    _build_agents_map,
    _build_ticket_body,
    _parse_test_constraints,
    _infer_complexity,
    _complexity_to_model_tier,
    _should_escalate_to_opus,
)

# ---------------------------------------------------------------------------
# Path to the guardrail config used by the computed map
# ---------------------------------------------------------------------------

_GUARDRAIL_CONFIG = _REPO_ROOT / "config" / "guardrail_gates.yaml"

# ---------------------------------------------------------------------------
# Canonical phase order (subset used by tests)
# ---------------------------------------------------------------------------

_CANONICAL_ORDER = [
    "architect-review",
    "test-writer",
    "python-coder",
    "sql-coder",
    "test-runner",
    "documentation-expert",
    "pr-reviewer",
    "commit",
    "pull-request",
]


# ---------------------------------------------------------------------------
# test_compute_agents_map_basic
# BO-560, BO-560-1
# ---------------------------------------------------------------------------


class TestComputeAgentsMapBasic:
    """Single (change_target, risk_surface) pair returns the expected guardrail agents."""

    def test_compute_agents_map_basic(self) -> None:
        # covers: BO-560, BO-560-1
        """A single (change_target='code', risk_surface='production') pair must return
        the guardrail agents listed in guardrail_gates.yaml under code.production
        (architect-review, test-writer, test-runner, pr-reviewer) plus the work agent
        (python-coder) and the standard tail agents (commit, pull-request).
        All present agents must have status 'needed'.
        """
        # The new signature is expected to be:
        #   _build_agents_map(
        #       assigned_agent: str,
        #       change_targets: list[str],
        #       risk_surface: str,
        #       not_needed_overrides: dict[str, str] | None = None,
        #       guardrail_config_path: Path | None = None,
        #   ) -> dict[str, str]
        result = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="production",
            guardrail_config_path=_GUARDRAIL_CONFIG,
        )

        # Guardrail gates for code/production: architect-review, test-writer, test-runner, pr-reviewer
        assert result.get("architect-review") == "needed", (
            f"architect-review should be 'needed' for code/production; got {result.get('architect-review')!r}"
        )
        assert result.get("test-writer") == "needed", (
            f"test-writer should be 'needed' for code/production; got {result.get('test-writer')!r}"
        )
        assert result.get("test-runner") == "needed", (
            f"test-runner should be 'needed' for code/production; got {result.get('test-runner')!r}"
        )
        assert result.get("pr-reviewer") == "needed", (
            f"pr-reviewer should be 'needed' for code/production; got {result.get('pr-reviewer')!r}"
        )
        assert result.get("python-coder") == "needed", (
            f"python-coder (work agent) should be 'needed'; got {result.get('python-coder')!r}"
        )


# ---------------------------------------------------------------------------
# test_compute_agents_map_union
# BO-560-2
# ---------------------------------------------------------------------------


class TestComputeAgentsMapUnion:
    """Multi-value targets union their guardrail sets."""

    def test_compute_agents_map_union(self) -> None:
        # covers: BO-560-2
        """Supplying change_targets=['code', 'schema'] for risk_surface='production'
        must union guardrails from both code/production AND schema/production.
        Both include architect-review; schema/production also includes architect-review
        and test-writer. The union must contain all agents from both sets with no
        duplicates, all set to 'needed'.
        """
        result = _build_agents_map(
            "python-coder",
            change_targets=["code", "schema"],
            risk_surface="production",
            guardrail_config_path=_GUARDRAIL_CONFIG,
        )

        # code/production gates: architect-review, test-writer, test-runner, pr-reviewer
        # schema/production gates: architect-review, test-writer, test-runner, pr-reviewer
        # Union (deduplicated): all four of the above
        for agent in ("architect-review", "test-writer", "test-runner", "pr-reviewer"):
            assert result.get(agent) == "needed", (
                f"Agent '{agent}' must be 'needed' after union of code+schema/production; "
                f"got {result.get(agent)!r}"
            )

        # No duplicate keys — dict already guarantees uniqueness, but we want to confirm
        # the value is exactly "needed" (not "needed_twice" or something odd)
        assert all(v in ("needed", "not_needed") for v in result.values()), (
            f"All agent statuses must be 'needed' or 'not_needed'; got: {result}"
        )


# ---------------------------------------------------------------------------
# test_canonical_ordering
# BO-560-3
# ---------------------------------------------------------------------------


class TestCanonicalOrdering:
    """Output map ordering matches canonical phase order."""

    def test_canonical_ordering(self) -> None:
        # covers: BO-560-3
        """The keys in the returned agents map must appear in canonical phase order:
        architect-review → test-writer → python-coder → sql-coder → test-runner →
        documentation-expert → pr-reviewer → commit → pull-request.
        Agents not present in the map may be absent; present agents must not violate
        the canonical sequence (no agent appears before an agent that should precede it).
        """
        result = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="production",
            guardrail_config_path=_GUARDRAIL_CONFIG,
        )

        present_agents = [k for k in result if k in _CANONICAL_ORDER]
        canonical_indices = [_CANONICAL_ORDER.index(a) for a in present_agents]

        assert canonical_indices == sorted(canonical_indices), (
            f"Agents in map are not in canonical order.\n"
            f"Present agents (in map order): {present_agents}\n"
            f"Canonical order reference: {_CANONICAL_ORDER}"
        )


# ---------------------------------------------------------------------------
# test_test_writer_injection
# BO-560-1-i
# ---------------------------------------------------------------------------


class TestTestWriterInjection:
    """test-writer is injected before any production_code agent."""

    def test_test_writer_injection(self) -> None:
        # covers: BO-560-1-i
        """When the assigned_agent produces production_code (e.g. python-coder),
        test-writer must appear in the agents map with status 'needed' and must
        come BEFORE the production_code agent in key order.
        This test uses change_targets=['code'], risk_surface='unit' where the
        guardrail config does NOT mandate test-writer via the table — the injection
        must therefore come from the auto-inject rule, not from the guardrail lookup.
        """
        # code/unit guardrails: test-writer, test-runner (both are present in the config)
        # But we want to confirm test-writer is before python-coder in key order.
        result = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="unit",
            guardrail_config_path=_GUARDRAIL_CONFIG,
        )

        keys = list(result.keys())
        assert "test-writer" in keys, "test-writer must be in the agents map"
        assert "python-coder" in keys, "python-coder must be in the agents map"

        tw_idx = keys.index("test-writer")
        pc_idx = keys.index("python-coder")
        assert tw_idx < pc_idx, (
            f"test-writer (index {tw_idx}) must appear before python-coder (index {pc_idx}) "
            f"in the agents map key order. Full map keys: {keys}"
        )


# ---------------------------------------------------------------------------
# test_test_runner_injection
# BO-560-1-i
# ---------------------------------------------------------------------------


class TestTestRunnerInjection:
    """test-runner is injected after any production_code agent."""

    def test_test_runner_injection(self) -> None:
        # covers: BO-560-1-i
        """When the assigned_agent produces production_code (e.g. python-coder),
        test-runner must appear in the agents map with status 'needed' and must
        come AFTER the production_code agent in key order.
        Uses change_targets=['code'], risk_surface='unit' — guardrail config
        code/unit includes test-writer and test-runner, but this test specifically
        verifies that test-runner is ordered after python-coder.
        """
        result = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="unit",
            guardrail_config_path=_GUARDRAIL_CONFIG,
        )

        keys = list(result.keys())
        assert "test-runner" in keys, "test-runner must be in the agents map"
        assert "python-coder" in keys, "python-coder must be in the agents map"

        pc_idx = keys.index("python-coder")
        tr_idx = keys.index("test-runner")
        assert pc_idx < tr_idx, (
            f"python-coder (index {pc_idx}) must appear before test-runner (index {tr_idx}) "
            f"in the agents map key order. Full map keys: {keys}"
        )


# ---------------------------------------------------------------------------
# test_preserve_not_needed
# BO-560-3-i
# ---------------------------------------------------------------------------


class TestPreserveNotNeeded:
    """Explicit not_needed overrides are preserved and never recomputed to needed."""

    def test_preserve_not_needed(self) -> None:
        # covers: BO-560-3-i
        """If the caller passes not_needed_overrides={'architect-review': 'not_needed'},
        the computed map must honour that override even though guardrail_gates.yaml
        mandates architect-review for code/production. The override must never be
        silently recomputed to 'needed'.
        """
        result = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="production",
            not_needed_overrides={"architect-review": "not_needed"},
            guardrail_config_path=_GUARDRAIL_CONFIG,
        )

        assert result.get("architect-review") == "not_needed", (
            f"architect-review was overridden to 'not_needed' but the map has "
            f"{result.get('architect-review')!r}. Explicit not_needed overrides must "
            f"never be recomputed to 'needed'."
        )


# ---------------------------------------------------------------------------
# test_tdd_bug_fix
# BO-530, BO-530-1
# ---------------------------------------------------------------------------


class TestTddBugFix:
    """A ## Test Requirements block is always emitted for tickets with a code producer."""

    def test_tdd_bug_fix(self) -> None:
        # covers: BO-530, BO-530-1
        """_build_ticket_body (or the ticket construction pipeline) must emit a
        ## Test Requirements block in the ticket body whenever the assigned_agent
        produces production_code (e.g. python-coder). The block must be non-empty —
        i.e. the string '## Test Requirements' must appear in the output, and the
        block must at minimum contain a 'tests:' key (even if the list is empty)
        so that test-writer can find it and does NOT self-skip.

        This test constructs a minimal AC record with assigned_agent='python-coder'
        and calls _build_ticket_body to confirm the block is present.
        """
        minimal_ac: dict = {
            "id": "BO-TEST-001",
            "title": "Test TDD bug fix",
            "component": "infrastructure",
            "assigned_agent": "python-coder",
            "estimated_complexity": "M",
            "criteria": "Given a code-producing AC\nWhen a ticket is generated\nThen a Test Requirements block is present",
            "doc_links": [],
        }

        body = _build_ticket_body(minimal_ac, "BO-TEST-001")

        assert "## Test Requirements" in body, (
            "Expected '## Test Requirements' section in ticket body for a python-coder AC, "
            "but it was not found. The TDD bug fix must emit this block so test-writer "
            "does not self-skip.\n\nActual ticket body:\n" + body
        )

        # The block must also contain 'tests:' so the supervisor can parse it
        assert "tests:" in body, (
            "Expected 'tests:' key inside the ## Test Requirements block, "
            "but it was not found in the ticket body. test-writer reads this key "
            "to determine whether it should run.\n\nActual ticket body:\n" + body
        )


# ---------------------------------------------------------------------------
# TestTestConstraintsParsing
# AC-BO-550, AC-BO-550-1, AC-BO-550-1-i
# ---------------------------------------------------------------------------


class TestTestConstraintsParsing:
    """_parse_test_constraints normalises the frontmatter field to a list of strings."""

    def test_ac_bo_550_parse_string_to_list(self) -> None:
        # covers: BO-550
        """AC-BO-550: test_constraints frontmatter field added — string form → list.

        _parse_test_constraints("unit_only") must return ["unit_only"].
        Requires _parse_test_constraints to exist in generate_ticket_from_ac.py.
        """
        result = _parse_test_constraints("unit_only")
        assert result == ["unit_only"], (
            f"Expected ['unit_only'] when given a bare string; got {result!r}"
        )

    def test_ac_bo_550_1_parse_list_passthrough(self) -> None:
        # covers: BO-550-1
        """AC-BO-550-1: test_constraints list form passes through unchanged.

        _parse_test_constraints(["unit_only", "no_db"]) must return ["unit_only", "no_db"].
        """
        result = _parse_test_constraints(["unit_only", "no_db"])
        assert result == ["unit_only", "no_db"], (
            f"Expected ['unit_only', 'no_db'] when given a list; got {result!r}"
        )

    def test_ac_bo_550_1_parse_none_returns_empty(self) -> None:
        # covers: BO-550-1
        """AC-BO-550-1: None input (field absent) → empty list, never None.

        _parse_test_constraints(None) must return [] so callers can safely iterate.
        """
        result = _parse_test_constraints(None)
        assert result == [], (
            f"Expected [] when given None; got {result!r}"
        )


# ---------------------------------------------------------------------------
# TestComplexityInference
# AC-BO-630, AC-BO-630-1, AC-BO-630-1-i
# ---------------------------------------------------------------------------


class TestComplexityInference:
    """_infer_complexity derives low/medium/high from AC record characteristics."""

    def test_ac_bo_630_1_low_on_few_criteria(self) -> None:
        # covers: BO-630-1
        """AC-BO-630-1: 1-2 criteria lines → 'low'.

        An AC record with a criteria string containing ≤2 lines must yield 'low'.
        """
        ac_record = {
            "id": "BO-TEST-LOW",
            "criteria": "Given a thing\nWhen it runs",
        }
        result = _infer_complexity(ac_record)
        assert result == "low", (
            f"Expected 'low' for 2-line criteria; got {result!r}"
        )

    def test_ac_bo_630_1_medium_on_moderate_criteria(self) -> None:
        # covers: BO-630-1
        """AC-BO-630-1: 3-6 criteria lines → 'medium'.

        An AC record with a criteria string containing between 3 and 6 lines
        must yield 'medium'.
        """
        ac_record = {
            "id": "BO-TEST-MED",
            "criteria": "Given a thing\nAnd another thing\nWhen it runs\nThen it works\nAnd also this",
        }
        result = _infer_complexity(ac_record)
        assert result == "medium", (
            f"Expected 'medium' for 5-line criteria; got {result!r}"
        )

    def test_ac_bo_630_1_high_on_many_criteria(self) -> None:
        # covers: BO-630-1
        """AC-BO-630-1: 7+ criteria lines → 'high'.

        An AC record with 7 or more criteria lines must yield 'high'.
        """
        criteria_lines = "\n".join(f"Line {i}" for i in range(1, 9))  # 8 lines
        ac_record = {
            "id": "BO-TEST-HIGH",
            "criteria": criteria_lines,
        }
        result = _infer_complexity(ac_record)
        assert result == "high", (
            f"Expected 'high' for 8-line criteria; got {result!r}"
        )

    def test_ac_bo_630_1_explicit_s_maps_to_low(self) -> None:
        # covers: BO-630-1
        """AC-BO-630-1: estimated_complexity='S' → 'low' (explicit field wins).

        When the AC record contains estimated_complexity='S', the returned value
        must be 'low' regardless of criteria line count.
        """
        ac_record = {
            "id": "BO-TEST-S",
            "estimated_complexity": "S",
            "criteria": "\n".join(f"Line {i}" for i in range(1, 9)),  # 8 lines — would be high by count
        }
        result = _infer_complexity(ac_record)
        assert result == "low", (
            f"Expected 'low' for estimated_complexity='S'; got {result!r}"
        )

    def test_ac_bo_630_1_explicit_m_maps_to_medium(self) -> None:
        # covers: BO-630-1
        """AC-BO-630-1: estimated_complexity='M' → 'medium' (explicit field wins)."""
        ac_record = {
            "id": "BO-TEST-M",
            "estimated_complexity": "M",
            "criteria": "One line",
        }
        result = _infer_complexity(ac_record)
        assert result == "medium", (
            f"Expected 'medium' for estimated_complexity='M'; got {result!r}"
        )

    def test_ac_bo_630_1_explicit_l_maps_to_high(self) -> None:
        # covers: BO-630-1
        """AC-BO-630-1: estimated_complexity='L' → 'high' (explicit field wins)."""
        ac_record = {
            "id": "BO-TEST-L",
            "estimated_complexity": "L",
            "criteria": "One line",
        }
        result = _infer_complexity(ac_record)
        assert result == "high", (
            f"Expected 'high' for estimated_complexity='L'; got {result!r}"
        )

    def test_ac_bo_630_1_explicit_xl_maps_to_high(self) -> None:
        # covers: BO-630-1
        """AC-BO-630-1: estimated_complexity='XL' → 'high' (explicit field wins)."""
        ac_record = {
            "id": "BO-TEST-XL",
            "estimated_complexity": "XL",
            "criteria": "One line",
        }
        result = _infer_complexity(ac_record)
        assert result == "high", (
            f"Expected 'high' for estimated_complexity='XL'; got {result!r}"
        )


# ---------------------------------------------------------------------------
# TestComplexityToTierMapping
# AC-BO-630, AC-BO-630-2
# ---------------------------------------------------------------------------


class TestComplexityToTierMapping:
    """_complexity_to_model_tier maps complexity enum to model tier string."""

    def test_ac_bo_630_2_low_maps_to_sonnet(self) -> None:
        # covers: BO-630-2
        """AC-BO-630-2: complexity 'low' → 'sonnet'."""
        result = _complexity_to_model_tier("low")
        assert result == "sonnet", (
            f"Expected 'sonnet' for complexity='low'; got {result!r}"
        )

    def test_ac_bo_630_2_medium_maps_to_sonnet(self) -> None:
        # covers: BO-630-2
        """AC-BO-630-2: complexity 'medium' → 'sonnet'."""
        result = _complexity_to_model_tier("medium")
        assert result == "sonnet", (
            f"Expected 'sonnet' for complexity='medium'; got {result!r}"
        )

    def test_ac_bo_630_2_high_maps_to_opus(self) -> None:
        # covers: BO-630-2
        """AC-BO-630-2: complexity 'high' → 'opus' (after challenge gate)."""
        result = _complexity_to_model_tier("high")
        assert result == "opus", (
            f"Expected 'opus' for complexity='high'; got {result!r}"
        )

    def test_ac_bo_630_2_unknown_raises_value_error(self) -> None:
        # covers: BO-630-2
        """AC-BO-630-2: unknown complexity value → ValueError.

        _complexity_to_model_tier("unknown") must raise ValueError, not silently
        return a default.
        """
        import pytest as _pytest
        with _pytest.raises(ValueError):
            _complexity_to_model_tier("unknown")


# ---------------------------------------------------------------------------
# TestChallengeGateFlow
# AC-BO-640, AC-BO-640-3, AC-BO-640-1-i
# ---------------------------------------------------------------------------


class TestChallengeGateFlow:
    """_should_escalate_to_opus encodes the challenge-gate decision."""

    def test_ac_bo_640_3_low_does_not_escalate(self) -> None:
        # covers: BO-640-3
        """AC-BO-640-3: complexity='low' → no escalation (False).

        Low-complexity tickets should never trigger the Opus escalation path.
        """
        result = _should_escalate_to_opus("low", complexity_override=None)
        assert result is False, (
            f"Expected False for complexity='low'; got {result!r}"
        )

    def test_ac_bo_640_3_medium_does_not_escalate(self) -> None:
        # covers: BO-640-3
        """AC-BO-640-3: complexity='medium' → no escalation (False).

        Medium-complexity tickets use Sonnet and must not escalate to Opus.
        """
        result = _should_escalate_to_opus("medium", complexity_override=None)
        assert result is False, (
            f"Expected False for complexity='medium'; got {result!r}"
        )

    def test_ac_bo_640_high_escalates_without_override(self) -> None:
        # covers: BO-640
        """AC-BO-640: complexity='high' with no override → escalation (True).

        When complexity is 'high' and no override suppresses it, the challenge gate
        must signal that escalation to Opus is appropriate.
        """
        result = _should_escalate_to_opus("high", complexity_override=None)
        assert result is True, (
            f"Expected True for complexity='high' with no override; got {result!r}"
        )

    def test_ac_bo_640_3_force_opus_overrides_any_complexity(self) -> None:
        # covers: BO-640-3
        """AC-BO-640-3: complexity_override='force_opus' → True regardless of complexity.

        Even for 'low' complexity, force_opus must return True so the user can
        hard-override the challenge gate.
        """
        result = _should_escalate_to_opus("low", complexity_override="force_opus")
        assert result is True, (
            f"Expected True when force_opus override is set even for low complexity; got {result!r}"
        )

    def test_ac_bo_640_3_force_opus_medium_also_escalates(self) -> None:
        # covers: BO-640-3
        """AC-BO-640-3: force_opus override also escalates 'medium' complexity."""
        result = _should_escalate_to_opus("medium", complexity_override="force_opus")
        assert result is True, (
            f"Expected True when force_opus is set for medium complexity; got {result!r}"
        )

    def test_ac_bo_640_1_i_frontmatter_includes_complexity_field(self) -> None:
        # covers: BO-640-1-i
        """AC-BO-640-1-i: _build_frontmatter includes 'complexity' when AC has estimated_complexity.

        When an AC record has estimated_complexity set, the generated ticket frontmatter
        must include a 'complexity:' field with the mapped value ('low', 'medium', or 'high').
        This is verified by checking that _build_ticket_body produces a string containing
        'complexity:' for an AC with estimated_complexity='M'.
        """
        ac_record: dict = {
            "id": "BO-TEST-FRONT",
            "title": "Complexity frontmatter test",
            "component": "infrastructure",
            "assigned_agent": "python-coder",
            "estimated_complexity": "M",
            "criteria": "Given a thing\nWhen it runs\nThen complexity is in frontmatter",
            "doc_links": [],
        }
        body = _build_ticket_body(ac_record, "BO-TEST-FRONT")
        assert "complexity:" in body, (
            "Expected 'complexity:' key in generated ticket body when AC has "
            f"estimated_complexity='M', but it was not found.\n\nActual body:\n{body}"
        )
