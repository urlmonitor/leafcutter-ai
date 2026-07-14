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

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import (  # noqa: E402
    _build_agents_map,
    _build_frontmatter as _build_frontmatter_top,
    _build_ticket_body,
    _find_ac_by_id,
    _normalize_change_target,
    _parse_test_constraints,
    _infer_complexity,
    _complexity_to_model_tier,
    _should_escalate_to_opus,
    main as _generator_main,
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
            risk_surface="contract_boundary",
            guardrail_config_path=_GUARDRAIL_CONFIG,
        )

        # Guardrail gates for code/contract_boundary: architect-review, test-writer, test-runner, pr-reviewer
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
            risk_surface="contract_boundary",
            guardrail_config_path=_GUARDRAIL_CONFIG,
        )

        # code/contract_boundary gates: architect-review, test-writer, test-runner, pr-reviewer
        # schema/contract_boundary gates: architect-review, test-writer, test-runner, pr-reviewer
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

        Uses code/internal, which is NOT a flow-change pair, so _CANONICAL_PHASE_ORDER
        applies (documentation-expert after python-coder). Using code/production would
        trigger the flow-change gate and _FLOW_CHANGE_PHASE_ORDER, which intentionally
        places documentation-expert BEFORE python-coder — a different, valid ordering.
        """
        result = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="internal",
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


# ---------------------------------------------------------------------------
# TestEndToEndGeneratorComputedMap
# AC-1 / AC-6 — CRITICAL: end-to-end test driving the real generator
# ---------------------------------------------------------------------------


import tempfile
import yaml as _yaml_mod


class TestEndToEndGeneratorComputedMap:
    """AC-1 / AC-6: Driving the real generator with a code/production AC must
    produce a ticket whose agents: frontmatter contains architect-review.

    This test is RED before the ticket-07 fix because _build_ticket_body and
    main() call _build_agents_map(assigned_agent) with no change_targets/risk_surface,
    so the legacy path is always used and architect-review is never included.
    """

    def test_ac1_ac6_generated_ticket_has_architect_review_for_code_production(self) -> None:
        # covers: AC-1
        # covers: AC-6
        """AC-1 / AC-6: A ticket generated from a code/production AC must have
        architect-review in its agents: frontmatter block.

        This test exercises the REAL generator path end-to-end (not just the
        isolated _build_agents_map function), so it catches the phantom-done hole
        where _build_agents_map is implemented but never wired in.

        The test is RED before the fix because _build_ticket_body() at line ~537
        calls _build_agents_map(assigned_agent) with NO change_targets/risk_surface,
        which activates the legacy path. The legacy path does not add architect-review
        for python-coder.
        """
        # Build a synthetic AC record with change_target=code, risk_surface=contract_boundary
        ac_record: dict = {
            "id": "BO-E2E-001",
            "title": "End-to-end generated ticket must include architect-review",
            "component": "infrastructure",
            "assigned_agent": "python-coder",
            "change_target": "code",
            "risk_surface": "contract_boundary",
            "estimated_complexity": "M",
            "criteria": (
                "Given an AC with change_target=code and risk_surface=production\n"
                "When the ticket generator runs\n"
                "Then the generated ticket's agents: frontmatter contains architect-review"
            ),
            "doc_links": [],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write the synthetic AC to a temp directory
            ac_root = Path(tmpdir) / "docs" / "acceptance-criteria" / "infrastructure"
            ac_root.mkdir(parents=True)
            ac_file = ac_root / "BO-E2E-001.yaml"
            with open(ac_file, "w", encoding="utf-8") as fh:
                _yaml_mod.dump(ac_record, fh, allow_unicode=True)

            tickets_root = Path(tmpdir) / "tickets" / "00_inbox"
            tickets_root.mkdir(parents=True)

            # Run the real generator
            exit_code = _generator_main([
                "--ac", "BO-E2E-001",
                "--ac-root", str(ac_root.parent.parent),
                "--tickets-root", str(tickets_root),
            ])

            assert exit_code == 0, (
                f"Generator exited with {exit_code} — expected 0. "
                f"Check that the AC record is valid and the temp directories exist."
            )

            # Find the generated ticket file (inside tmpdir, still alive)
            generated_tickets = list(tickets_root.rglob("*.md"))
            assert len(generated_tickets) == 1, (
                f"Expected exactly one generated ticket file; found {len(generated_tickets)}: "
                f"{[str(p) for p in generated_tickets]}"
            )

            ticket_text = generated_tickets[0].read_text(encoding="utf-8")

            # Parse the frontmatter
            assert ticket_text.startswith("---"), (
                "Generated ticket must start with YAML frontmatter (---)"
            )
            parts = ticket_text.split("---", 2)
            assert len(parts) >= 3, (
                "Generated ticket must have opening and closing --- delimiters"
            )
            fm = _yaml_mod.safe_load(parts[1])
            agents_fm = fm.get("agents", {})

            assert "architect-review" in agents_fm, (
                f"Expected 'architect-review' in agents: frontmatter for a code/production AC, "
                f"but it was not found.\n\n"
                f"Agents map: {agents_fm}\n\n"
                f"This is the phantom-done hole: _build_agents_map() is never called with "
                f"change_target/risk_surface in the real generation path. The fix must thread "
                f"ac['change_target'] and ac['risk_surface'] through to _build_agents_map() "
                f"at all real call sites (main(), _build_ticket_body())."
            )

            assert agents_fm.get("architect-review") == "needed", (
                f"architect-review must be 'needed' (not '{agents_fm.get('architect-review')}') "
                f"for a code/production AC."
            )


# ---------------------------------------------------------------------------
# TestComputedMapTestRequirementsGating
# AC-3: ## Test Requirements emitted based on computed map, not assigned agent
# ---------------------------------------------------------------------------


class TestComputedMapTestRequirementsGating:
    """AC-3: ## Test Requirements block is emitted when the COMPUTED map contains
    a production_code producer, even if the assigned agent is a non-coder.

    This test is RED before the ticket-07 fix because _build_ticket_body() gates
    the ## Test Requirements block on _agent_produces_production_code(assigned_agent),
    not on whether the computed map contains any production_code producer.
    """

    def test_ac3_test_requirements_emitted_when_computed_map_has_coder(self) -> None:
        # covers: AC-3
        """AC-3: When the computed agent map for a (change_target, risk_surface) pair
        includes a production_code producer (e.g. python-coder via guardrails), the
        ## Test Requirements block must be emitted in the ticket body even if the
        assigned agent is a non-coder (e.g. documentation-expert).

        This test is RED before the fix because _build_ticket_body() at line ~539 checks:
            is_code_producer = _agent_produces_production_code(assigned_agent)
        which is False for 'documentation-expert', so the block is suppressed.
        The fix must change the gate to check whether any agent in the *computed* map
        is a production_code producer.
        """
        # Use code/production change classification — guardrail config mandates
        # python-coder-adjacent agents (test-writer, test-runner, architect-review, pr-reviewer)
        # for code/production. We create a scenario where the assigned agent is
        # 'documentation-expert' (non-coder) but the computed map pulls in a coder via
        # the guardrail union.
        #
        # For this test we explicitly construct the computed map to include 'python-coder'
        # as a guardrail-injected agent, then call _build_ticket_body with an AC that has
        # assigned_agent='documentation-expert'. The test asserts the block is present.
        #
        # If _build_ticket_body doesn't accept change_target/risk_surface, the block will
        # be absent because documentation-expert is not a production_code producer.
        ac_record_noncoder: dict = {
            "id": "BO-AC3-001",
            "title": "Non-coder AC that pulls in a coder via computed guardrails",
            "component": "infrastructure",
            "assigned_agent": "documentation-expert",
            "change_target": "code",
            "risk_surface": "contract_boundary",
            "estimated_complexity": "S",
            "criteria": (
                "Given a non-coder assigned agent\n"
                "And the computed map includes a coder via guardrail union\n"
                "When a ticket is generated\n"
                "Then the test-requirements section is present in the output"
            ),
            "doc_links": [],
        }

        body = _build_ticket_body(ac_record_noncoder, "BO-AC3-001")

        # Use a line-anchored search: the section heading must appear at the start of a
        # line (not embedded in gherkin criteria text). Check for the heading followed by
        # a newline or end-of-string to distinguish it from substring matches inside criteria.
        import re as _re
        has_test_requirements_section = bool(
            _re.search(r"^## Test Requirements\s*$", body, _re.MULTILINE)
        )

        assert has_test_requirements_section, (
            "Expected a '## Test Requirements' section heading (on its own line) in the "
            "ticket body because the computed agent map for code/production includes "
            "production_code producers via guardrail union. The assigned agent is "
            "'documentation-expert' (non-coder), but the computed guardrails should force "
            "the block.\n\n"
            "This test is RED before the fix: the current code checks "
            "_agent_produces_production_code(assigned_agent) and skips the block because "
            "documentation-expert is not a coder. The fix must change the gate to check "
            "whether any agent in the *computed* map is a production_code producer.\n\n"
            f"Actual ticket body:\n{body}"
        )


# ---------------------------------------------------------------------------
# TestFlowChangeSequencing
# AC-4: flow_change_gates consumed — architect-review + documentation-expert
# appear BEFORE any coder for flow-change pairs
# ---------------------------------------------------------------------------


class TestFlowChangeSequencing:
    """AC-4: For flow-change (target, surface) pairs, architect-review and
    documentation-expert must appear BEFORE any coder in the computed map.

    This test is RED before the ticket-07 fix because _build_agents_map never
    reads the flow_change_gates section of guardrail_gates.yaml, so
    documentation-expert is never added for code/production.
    """

    def test_ac4_flow_change_code_production_includes_documentation_expert(self) -> None:
        # covers: AC-4
        """AC-4: For the code/production flow-change pair, documentation-expert must
        appear in the computed map with status 'needed'.

        The guardrail_gates.yaml flow_change_gates section declares code/production
        as a flow-change pair with mandatory_agents: [architect-review, documentation-expert].
        _build_agents_map must read this section and include documentation-expert.

        This test is RED before the fix because _build_agents_map only reads the
        per-surface gate table (code → production → [...]) and never reads flow_change_gates.
        documentation-expert is not in the code/production gate list, so it is absent.
        """
        result = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="contract_boundary",
            guardrail_config_path=_GUARDRAIL_CONFIG,
        )

        assert "documentation-expert" in result, (
            f"Expected 'documentation-expert' in the computed map for code/contract_boundary "
            f"(a flow-change pair per guardrail_gates.yaml flow_change_gates), "
            f"but it was absent.\n\n"
            f"Computed map: {result}\n\n"
            f"The fix must read flow_change_gates from the YAML and union mandatory_agents "
            f"into the computed map for matching (change_target, risk_surface) pairs."
        )

        assert result.get("documentation-expert") == "needed", (
            f"documentation-expert must be 'needed'; got {result.get('documentation-expert')!r}"
        )

    def test_ac4_documentation_expert_before_coder_for_flow_change_pair(self) -> None:
        # covers: AC-4
        """AC-4: documentation-expert must appear BEFORE python-coder in the computed
        map key order for the code/production flow-change pair.

        This verifies that the canonical ordering (architect-review priority 4,
        documentation-expert priority 10 per SKILL.md) places both agents before
        any coder (python-coder priority 6, sql-coder priority 7).

        Note: The _CANONICAL_PHASE_ORDER list places documentation-expert AFTER
        python-coder, so the fix must either use a modified ordering or ensure
        that for flow-change pairs, documentation-expert is treated as a pre-coder
        agent. The test specifically requires documentation-expert before python-coder.

        This test is RED before the fix because documentation-expert is absent
        from the computed map entirely (flow_change_gates not consumed).
        """
        result = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="contract_boundary",
            guardrail_config_path=_GUARDRAIL_CONFIG,
        )

        keys = list(result.keys())
        assert "documentation-expert" in keys, (
            "documentation-expert must be present in the computed map for code/contract_boundary "
            "(flow-change pair). It is currently absent because flow_change_gates is not consumed."
        )
        assert "python-coder" in keys, (
            "python-coder must be present in the computed map."
        )

        de_idx = keys.index("documentation-expert")
        pc_idx = keys.index("python-coder")

        assert de_idx < pc_idx, (
            f"documentation-expert (index {de_idx}) must appear BEFORE python-coder "
            f"(index {pc_idx}) in the computed map for a flow-change pair.\n"
            f"Full map keys: {keys}\n\n"
            f"The fix must ensure flow-change pairs place documentation-expert before "
            f"any coder in the agent ordering."
        )


# ---------------------------------------------------------------------------
# TestDeterministicOrdering
# AC-5: Agents outside _CANONICAL_PHASE_ORDER placed at stable phase, not
# after commit/pull-request
# ---------------------------------------------------------------------------


class TestDeterministicOrdering:
    """AC-5: Non-canonical agents must be placed at a stable sorted position,
    never after commit/pull-request.

    This test is RED before the ticket-07 fix because the current code appends
    non-canonical agents via set-iteration order (nondeterministic) at the end,
    AFTER commit/pull-request.
    """

    def test_ac5_non_canonical_agent_not_after_commit_pull_request(self, tmp_path: Path) -> None:
        # covers: AC-5
        """AC-5: An agent that is NOT in _CANONICAL_PHASE_ORDER (e.g. 'status-checker')
        must appear BEFORE commit and pull-request in the output map.

        Uses an injected fixture guardrail config (written to tmp_path) that explicitly
        maps config/contract_boundary to include 'status-checker' (a non-canonical agent).
        The test is fully deterministic: it never depends on the production
        config/guardrail_gates.yaml, so it cannot be silently skipped by a YAML rebuild.

        status-checker is NOT in _CANONICAL_PHASE_ORDER, so it is a non-canonical agent.
        The production code's non-canonical insertion logic must place it at a stable
        sorted position BEFORE commit and pull-request.  The test FAILS if a non-canonical
        agent is appended after those terminal-phase agents.
        """
        # Build a minimal fixture guardrail YAML that mandates status-checker.
        # Using config/contract_boundary so the pair always mandates status-checker
        # regardless of what the production guardrail_gates.yaml contains.
        fixture_gates = {
            "config": {
                "contract_boundary": ["status-checker", "pr-reviewer"],
                "internal": [],
            },
            "flow_change_gates": [],
        }
        fixture_path = tmp_path / "fixture_guardrail_gates.yaml"
        fixture_path.write_text(
            _yaml_mod.dump(fixture_gates, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )

        result = _build_agents_map(
            "python-coder",
            change_targets=["config"],
            risk_surface="contract_boundary",
            guardrail_config_path=fixture_path,
        )

        keys = list(result.keys())

        # status-checker is mandated by the fixture YAML and is NOT in _CANONICAL_PHASE_ORDER
        assert "status-checker" in keys, (
            f"Expected 'status-checker' (a non-canonical guardrail agent) to be "
            f"present in the computed map for config/contract_boundary; got keys: {keys}"
        )

        commit_idx = keys.index("commit") if "commit" in keys else len(keys)
        pull_request_idx = keys.index("pull-request") if "pull-request" in keys else len(keys)
        non_canonical_idx = keys.index("status-checker")

        assert non_canonical_idx < commit_idx, (
            f"'status-checker' (index {non_canonical_idx}) must appear BEFORE "
            f"'commit' (index {commit_idx}) in the computed map.\n"
            f"Full map keys: {keys}\n\n"
            f"The fix must place non-canonical agents at a stable sorted phase position, "
            f"not at the end after commit/pull-request."
        )

        assert non_canonical_idx < pull_request_idx, (
            f"'status-checker' (index {non_canonical_idx}) must appear BEFORE "
            f"'pull-request' (index {pull_request_idx}) in the computed map.\n"
            f"Full map keys: {keys}"
        )

    def test_ac5_deterministic_ordering_multiple_calls(self) -> None:
        # covers: AC-5
        """AC-5: Calling _build_agents_map multiple times with the same args must
        produce identical key ordering (no set-iteration nondeterminism).

        This test runs the function 20 times and asserts all outputs have the same
        key order. In CPython 3.7+ dict insertion order is deterministic, but the
        intermediate 'all_needed' set is still a Python set (hash-order nondeterministic
        across interpreter runs). The sort/canonicalization must be stable.

        Note: This test may be green in a single interpreter session due to CPython's
        fixed-seed hash for small sets in a single run. The ac5_non_canonical_agent
        placement test above is the primary red indicator; this test is an additional
        assertion for determinism.
        """
        baseline = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="contract_boundary",
            guardrail_config_path=_GUARDRAIL_CONFIG,
        )
        baseline_keys = list(baseline.keys())

        for i in range(19):
            repeated = _build_agents_map(
                "python-coder",
                change_targets=["code"],
                risk_surface="contract_boundary",
                guardrail_config_path=_GUARDRAIL_CONFIG,
            )
            repeated_keys = list(repeated.keys())
            assert repeated_keys == baseline_keys, (
                f"Call {i+2} produced different key order than call 1.\n"
                f"  Call 1 keys:   {baseline_keys}\n"
                f"  Call {i+2} keys: {repeated_keys}\n\n"
                f"The ordering is nondeterministic. The fix must sort or canonicalize "
                f"non-canonical agents so the output is stable across calls."
            )


# ---------------------------------------------------------------------------
# AC-4: _build_frontmatter emits change_target / risk_surface when AC carries them
# (ticket 08)
# ---------------------------------------------------------------------------
# RED before fix: _build_frontmatter does not include change_target or risk_surface
# in the fm dict, so generated frontmatter never contains these fields.
# ---------------------------------------------------------------------------


class TestBuildFrontmatterEmitsAxes:
    """AC-4: _build_frontmatter emits change_target/risk_surface when the source AC carries them."""

    def test_ac4_frontmatter_emits_change_target_when_present(self) -> None:
        # covers: UNKNOWN
        """AC-4: When the source AC has change_target='code', the generated ticket
        frontmatter must include change_target: code.

        RED before fix: _build_frontmatter() does not add change_target to the fm dict.
        Fix: add 'change_target': ac.get('change_target') to fm when present.
        """
        import yaml as _yaml

        from generate_ticket_from_ac import _build_frontmatter  # noqa: E402

        ac: dict = {
            "id": "BO-FM-001",
            "title": "Test frontmatter change_target emission",
            "component": "test",
            "assigned_agent": "python-coder",
            "change_target": "code",
            "criteria": "Given something\nWhen something\nThen something",
        }
        agents = {"python-coder": "needed", "commit": "needed", "pull-request": "needed"}

        fm_str = _build_frontmatter(ac, "BO-FM-001", [], agents)

        parts = fm_str.split("---", 2)
        fm = _yaml.safe_load(parts[1])

        assert "change_target" in fm, (
            "Expected 'change_target' in the generated ticket frontmatter when the source "
            "AC carries change_target='code'. Currently _build_frontmatter does not emit "
            "this field. Fix: add ac.get('change_target') to the fm dict and only include "
            "it when the value is not None."
        )
        assert fm["change_target"] == "code", (
            f"Expected change_target='code' in frontmatter, got {fm.get('change_target')!r}"
        )

    def test_ac4_frontmatter_emits_risk_surface_when_present(self) -> None:
        # covers: UNKNOWN
        """AC-4: When the source AC has risk_surface='internal', the generated ticket
        frontmatter must include risk_surface: internal.

        RED before fix: _build_frontmatter() does not add risk_surface to the fm dict.
        """
        import yaml as _yaml

        from generate_ticket_from_ac import _build_frontmatter  # noqa: E402

        ac: dict = {
            "id": "BO-FM-002",
            "title": "Test frontmatter risk_surface emission",
            "component": "test",
            "assigned_agent": "python-coder",
            "risk_surface": "internal",
            "criteria": "Given something\nWhen something\nThen something",
        }
        agents = {"python-coder": "needed", "commit": "needed", "pull-request": "needed"}

        fm_str = _build_frontmatter(ac, "BO-FM-002", [], agents)

        parts = fm_str.split("---", 2)
        fm = _yaml.safe_load(parts[1])

        assert "risk_surface" in fm, (
            "Expected 'risk_surface' in the generated ticket frontmatter when the source "
            "AC carries risk_surface='internal'. Currently _build_frontmatter does not "
            "emit this field. Fix: include ac.get('risk_surface') in the fm dict."
        )
        assert fm["risk_surface"] == "internal", (
            f"Expected risk_surface='internal' in frontmatter, got {fm.get('risk_surface')!r}"
        )

    def test_ac4_frontmatter_emits_both_axes_when_present(self) -> None:
        # covers: UNKNOWN
        """AC-4: When the source AC has both change_target and risk_surface, both
        must appear in the generated frontmatter.

        RED before fix: neither field is emitted by _build_frontmatter.
        """
        import yaml as _yaml

        from generate_ticket_from_ac import _build_frontmatter  # noqa: E402

        ac: dict = {
            "id": "BO-FM-003",
            "title": "Test frontmatter both axes",
            "component": "test",
            "assigned_agent": "python-coder",
            "change_target": "schema",
            "risk_surface": "contract_boundary",
            "criteria": "Given something\nWhen something\nThen something",
        }
        agents = {"python-coder": "needed", "commit": "needed", "pull-request": "needed"}

        fm_str = _build_frontmatter(ac, "BO-FM-003", [], agents)

        parts = fm_str.split("---", 2)
        fm = _yaml.safe_load(parts[1])

        assert "change_target" in fm, (
            "Expected 'change_target' in frontmatter when AC has change_target='schema'. "
            f"Generated frontmatter keys: {sorted(fm.keys())}"
        )
        assert "risk_surface" in fm, (
            "Expected 'risk_surface' in frontmatter when AC has risk_surface='contract_boundary'. "
            f"Generated frontmatter keys: {sorted(fm.keys())}"
        )


# ---------------------------------------------------------------------------
# AC-5 (H-1): _build_agents_map logs WARNING on guardrail lookup miss (ticket 08)
# ---------------------------------------------------------------------------
# RED before fix: _build_agents_map silently ignores a miss (no warning logged).
# ---------------------------------------------------------------------------


class TestBuildAgentsMapWarnOnMiss:
    """AC-5 (H-1): _build_agents_map logs a WARNING when a guardrail lookup misses."""

    def test_ac5_build_agents_map_warns_on_missing_guardrail_entry(
        self, tmp_path: Path, caplog: object
    ) -> None:
        # covers: UNKNOWN
        """AC-5: When change_targets=['schema'] has no entry in the fixture guardrail
        config, _build_agents_map must log a WARNING via the project logger.

        RED before fix: _build_agents_map does not log any warning — the miss is
        silently ignored and guardrail_set stays empty.
        Fix: add logger.warning(...) when gate_list is empty for a (target, surface) pair.
        """
        import logging

        import yaml as _yaml

        # Fixture guardrail config: only "code/internal" has an entry.
        # Calling with change_target="schema" → no entry → should warn.
        fixture_gates = {
            "code": {
                "internal": ["test-writer"],
            },
            "flow_change_gates": [],
        }
        fixture_path = tmp_path / "fixture_guardrail.yaml"
        fixture_path.write_text(
            _yaml.dump(fixture_gates, default_flow_style=False, allow_unicode=True),
            encoding="utf-8",
        )

        with caplog.at_level(logging.WARNING):
            _build_agents_map(
                "python-coder",
                change_targets=["schema"],  # "schema" has no entry in fixture
                risk_surface="internal",
                guardrail_config_path=fixture_path,
            )

        warning_records = [r for r in caplog.records if r.levelno >= logging.WARNING]
        assert len(warning_records) > 0, (
            "_build_agents_map must log a WARNING when (change_target='schema', "
            "risk_surface='internal') has no guardrail entry in the config. "
            "Currently no warning is logged — the miss is silently ignored. "
            "Fix: add logger.warning(...) for each (target, surface) pair where "
            "gate_list is empty or the surface key is absent from the config."
        )


# ---------------------------------------------------------------------------
# AC-6 (M-1): _build_ticket_body accepts pre-computed agents_map (ticket 08)
# ---------------------------------------------------------------------------
# RED before fix: _build_ticket_body(ac, ac_id) has no agents_map parameter.
# Calling it with agents_map=... raises TypeError.
# ---------------------------------------------------------------------------


class TestBuildTicketBodyAcceptsPrecomputedAgentsMap:
    """AC-6 M-1: _build_ticket_body accepts a pre-computed agents map."""

    def test_ac6_m1_build_ticket_body_accepts_agents_map_kwarg(self) -> None:
        # covers: UNKNOWN
        """AC-6 M-1: _build_ticket_body must accept an agents_map kwarg and use it
        in the Sign-offs section instead of recomputing the map internally.

        RED before fix: the current signature is _build_ticket_body(ac, ac_id) with
        no agents_map parameter → TypeError when called with agents_map=...
        Fix: add agents_map parameter to _build_ticket_body; use it when provided.
        """
        ac: dict = {
            "id": "BO-M1-001",
            "title": "Test pre-computed agents map acceptance",
            "component": "test",
            "assigned_agent": "python-coder",
            "change_target": "code",
            "risk_surface": "internal",
            "criteria": "Given something\nWhen it runs\nThen it works",
        }
        # The unique marker agent must appear in the Sign-offs section when the
        # pre-computed map is used (proves the map was not recomputed).
        custom_agents_map = {
            "sentinel-agent-M1": "needed",
            "python-coder": "needed",
            "commit": "needed",
            "pull-request": "needed",
        }

        # This raises TypeError before the fix:
        # "_build_ticket_body() got an unexpected keyword argument 'agents_map'"
        body = _build_ticket_body(ac, "BO-M1-001", agents_map=custom_agents_map)

        assert "sentinel-agent-M1" in body, (
            "Expected 'sentinel-agent-M1' (a unique marker) in the ticket body when a "
            "pre-computed agents_map is passed to _build_ticket_body. The map must be "
            "used as-is rather than recomputed. "
            f"Actual body (first 600 chars):\n{body[:600]}"
        )


# ---------------------------------------------------------------------------
# AC-6 (M-2): _normalize_change_target helper (ticket 08)
# ---------------------------------------------------------------------------
# RED before fix: function does not exist → ImportError.
# ---------------------------------------------------------------------------


class TestNormalizeChangeTargetHelper:
    """AC-6 M-2: _normalize_change_target helper normalizes str/list/None consistently."""

    def test_ac6_m2_normalize_str_returns_single_item_list(self) -> None:
        # covers: UNKNOWN
        """AC-6 M-2: _normalize_change_target({"change_target": "code"}) → ["code"].

        RED before fix: function does not exist in generate_ticket_from_ac → ImportError.
        Fix: extract inline normalization logic into a named _normalize_change_target(ac)
        helper that returns list[str] | None.
        """
        from generate_ticket_from_ac import _normalize_change_target  # noqa: E402

        result = _normalize_change_target({"change_target": "code"})
        assert result == ["code"], (
            f"Expected ['code'] for change_target='code' (string form), got {result!r}"
        )

    def test_ac6_m2_normalize_list_passthrough(self) -> None:
        # covers: UNKNOWN
        """AC-6 M-2: _normalize_change_target({"change_target": ["code", "schema"]}) → ["code", "schema"].

        RED before fix: ImportError.
        """
        from generate_ticket_from_ac import _normalize_change_target  # noqa: E402

        result = _normalize_change_target({"change_target": ["code", "schema"]})
        assert result == ["code", "schema"], (
            f"Expected ['code', 'schema'] for list form, got {result!r}"
        )

    def test_ac6_m2_normalize_absent_field_returns_none(self) -> None:
        # covers: UNKNOWN
        """AC-6 M-2: _normalize_change_target({}) → None when field is absent.

        RED before fix: ImportError.
        """
        from generate_ticket_from_ac import _normalize_change_target  # noqa: E402

        result = _normalize_change_target({})
        assert result is None, (
            f"Expected None when change_target is absent, got {result!r}"
        )

    def test_ac6_m2_normalize_empty_list_returns_none(self) -> None:
        # covers: UNKNOWN
        """AC-6 M-2: _normalize_change_target({"change_target": []}) → None (empty list).

        RED before fix: ImportError.
        """
        from generate_ticket_from_ac import _normalize_change_target  # noqa: E402

        result = _normalize_change_target({"change_target": []})
        assert result is None, (
            f"Expected None for empty change_target list, got {result!r}"
        )

    def test_ac6_m2_normalize_none_field_returns_none(self) -> None:
        # covers: UNKNOWN
        """AC-6 M-2: _normalize_change_target({"change_target": None}) → None.

        RED before fix: ImportError.
        """
        from generate_ticket_from_ac import _normalize_change_target  # noqa: E402

        result = _normalize_change_target({"change_target": None})
        assert result is None, (
            f"Expected None for change_target: None, got {result!r}"
        )


# ---------------------------------------------------------------------------
# AC-6 (M-3): flow_change_gates uses blast-radius risk_surface vocabulary (ticket 08)
# ---------------------------------------------------------------------------
# RED before fix: current flow_change_gates entries use 'production' and 'all'
# as risk_surface labels, which are NOT in the blast-radius vocabulary.
# ---------------------------------------------------------------------------


class TestFlowChangeGatesBlastRadiusVocabulary:
    """AC-6 M-3: flow_change_gates entries must use blast-radius risk_surface values."""

    def test_ac6_m3_flow_change_gates_risk_surface_in_allowed(self) -> None:
        # covers: UNKNOWN
        """AC-6 M-3: Every risk_surface value in flow_change_gates must be one of the
        6 blast-radius values: internal, contract_boundary, auth, privacy, safety, cost.

        RED before fix: current flow_change_gates uses 'production' and 'all' as
        risk_surface labels — neither is in ALLOWED_RISK_SURFACES.
        Fix: migrate each flow_change_gates entry to use the correct blast-radius label
        (e.g. 'production' → 'contract_boundary' or 'safety', 'all' → suitable label).
        """
        import yaml as _yaml

        guardrail_path = _REPO_ROOT / "config" / "guardrail_gates.yaml"
        gates = _yaml.safe_load(guardrail_path.read_text(encoding="utf-8"))
        flow_change_gates = gates.get("flow_change_gates") or []

        _ALLOWED_RISK_SURFACES = frozenset(
            {"internal", "contract_boundary", "auth", "privacy", "safety", "cost"}
        )

        invalid_entries = []
        for entry in flow_change_gates:
            if not isinstance(entry, dict):
                continue
            rs = entry.get("risk_surface")
            ct = entry.get("change_target")
            if rs not in _ALLOWED_RISK_SURFACES:
                invalid_entries.append(f"  ({ct!r}, risk_surface={rs!r})")

        assert not invalid_entries, (
            "flow_change_gates entries must use blast-radius risk_surface values "
            "{{internal, contract_boundary, auth, privacy, safety, cost}}. "
            "The following entries use legacy labels not in ALLOWED_RISK_SURFACES:\n"
            + "\n".join(invalid_entries)
            + "\n\nFix: migrate each entry to use the correct blast-radius label."
        )


# ---------------------------------------------------------------------------
# TestRealStoreComputedMapE2E
# Ticket 10 AC-3: Anti-phantom-done gate — real store, real backfilled AC.
# ---------------------------------------------------------------------------
# This test loads TQ-100d-1.yaml from the REAL on-disk AC store (not a synthetic
# dict) and asserts that the generator's computed output for that record:
#   (a) emits change_target and risk_surface in the frontmatter, and
#   (b) includes architect-review in the agents: map.
#
# WHY A SYNTHETIC AC WOULD DEFEAT THIS TEST'S PURPOSE:
#   The phantom-done failure pattern for EPIC-ComputedQualityGates was that
#   real AC YAML files in the store were NOT backfilled with change_target /
#   risk_surface, so the generator always fell through to the legacy (no-axes)
#   path and emitted agents maps without architect-review.  A test using a
#   hard-coded dict {'change_target': 'code', 'risk_surface': 'contract_boundary'}
#   would pass regardless of whether the real store was correctly backfilled —
#   it only proves the generator *can* compute a map, not that the real store
#   *contains* the right data to drive it.
#
#   Loading via _find_ac_by_id against the REAL ac_root proves both at once:
#   - The backfilled YAML is present and readable.
#   - The generator, fed data that actually lives on disk, computes the expected map.
# ---------------------------------------------------------------------------

# Real AC store root — the directory that exists in this worktree on disk.
_REAL_AC_ROOT = _REPO_ROOT / "docs" / "acceptance-criteria"


class TestRealStoreComputedMapE2E:
    """Anti-phantom-done gate: real-store end-to-end test for computed agents map.

    This class exercises the generator against the REAL backfilled TQ-100d-1 AC
    record from the on-disk store (not a synthetic hard-coded dict).

    The test proves that:
      (a) the backfilled TQ-100d-1.yaml carries change_target and risk_surface
          — confirming the backfill action (ticket 10) actually wrote to disk, and
      (b) the generator, fed data that lives on disk, emits an agents: frontmatter
          block containing architect-review — the unambiguous signal that the
          computed contract_boundary path fired, not the legacy map.

    A synthetic AC dict would defeat this gate because it would pass even if
    the real store files were never backfilled (phantom-done).  Loading from
    _find_ac_by_id against the real ac_root is the only way to prove both
    the store state and the generator wiring simultaneously.
    """

    def test_real_backfilled_ac_gets_architect_review(self) -> None:
        # covers: UNKNOWN
        """Real-store anti-phantom-done gate for TQ-100d-1.

        Loads TQ-100d-1 from the real AC store via _find_ac_by_id (NOT a
        synthetic dict), runs the generator's computed-map path, and asserts:

        (a) The loaded record carries change_target and risk_surface
            (confirms the backfill wrote to disk).
        (b) _build_agents_map driven by those real axes returns a map where
            architect-review == 'needed' (confirms the computed path fired).
        (c) _build_frontmatter driven by the real record emits both
            change_target and risk_surface in the YAML block (confirms
            the axes pass through to the ticket frontmatter).

        If TQ-100d-1.yaml is missing from the real store, the test fails
        immediately with a clear message — it never falls back to a synthetic
        path.
        """
        import yaml as _yaml

        # ---- Step 1: Load the real AC record from disk ----
        assert _REAL_AC_ROOT.is_dir(), (
            f"Real AC store root does not exist: {_REAL_AC_ROOT}\n"
            "This test requires the worktree to contain the docs/acceptance-criteria/ "
            "directory populated by the ticket-10 backfill."
        )

        result = _find_ac_by_id(_REAL_AC_ROOT, "TQ-100d-1")

        assert result is not None, (
            f"_find_ac_by_id could not locate 'TQ-100d-1' under {_REAL_AC_ROOT}.\n"
            "Verify that the backfill (ticket 10) has written TQ-100d-1.yaml to the store."
        )

        _ac_path, ac = result

        # ---- Step 2: Assert the backfill wrote the axes to disk ----
        assert "change_target" in ac, (
            f"TQ-100d-1.yaml (loaded from {_ac_path}) is missing the 'change_target' field.\n"
            "The ticket-10 backfill must add change_target: [config, code] to this record.\n"
            f"Current record keys: {sorted(ac.keys())}"
        )

        assert "risk_surface" in ac, (
            f"TQ-100d-1.yaml (loaded from {_ac_path}) is missing the 'risk_surface' field.\n"
            "The ticket-10 backfill must add risk_surface: contract_boundary to this record.\n"
            f"Current record keys: {sorted(ac.keys())}"
        )

        # ---- Step 3: Drive _build_agents_map with the real record's axes ----
        assigned_agent = ac.get("assigned_agent", "python-coder")
        change_targets = _normalize_change_target(ac)
        risk_surface = ac.get("risk_surface") or None

        # Both axes must be non-None for the computed path to fire
        assert change_targets is not None, (
            f"_normalize_change_target returned None for the real AC record — "
            f"change_target value in YAML: {ac.get('change_target')!r}"
        )
        assert risk_surface is not None, (
            f"risk_surface is None after reading the real AC record — "
            f"risk_surface value in YAML: {ac.get('risk_surface')!r}"
        )

        agents = _build_agents_map(
            assigned_agent,
            change_targets=change_targets,
            risk_surface=risk_surface,
            guardrail_config_path=_GUARDRAIL_CONFIG,
        )

        assert "architect-review" in agents, (
            f"Expected 'architect-review' in the computed agents map for the real "
            f"TQ-100d-1 record (change_target={change_targets!r}, "
            f"risk_surface={risk_surface!r}), but it was absent.\n\n"
            f"This is the anti-phantom-done signal: architect-review is present only "
            f"when the computed (change_target, risk_surface) path fires, NOT the "
            f"legacy fallback path.\n\n"
            f"Computed agents map: {agents}\n\n"
            f"AC loaded from: {_ac_path}"
        )

        assert agents.get("architect-review") == "needed", (
            f"architect-review must be 'needed' in the computed map for "
            f"change_target={change_targets!r} / risk_surface={risk_surface!r}; "
            f"got {agents.get('architect-review')!r}.\n"
            f"Full agents map: {agents}"
        )

        # ---- Step 4: Assert _build_frontmatter emits the axes ----
        files_touched: list[str] = []  # no doc_links required for this assertion
        fm_str = _build_frontmatter_top(ac, "TQ-100d-1", files_touched, agents)

        assert fm_str.startswith("---"), (
            "Generated frontmatter must start with '---'."
        )
        parts = fm_str.split("---", 2)
        assert len(parts) >= 3, (
            "Generated frontmatter must have opening and closing '---' delimiters."
        )
        fm = _yaml.safe_load(parts[1])

        assert "change_target" in fm, (
            "Expected 'change_target' in the generated ticket frontmatter when "
            "the real TQ-100d-1 record carries that field.\n"
            f"Frontmatter keys present: {sorted(fm.keys())}\n"
            f"change_target value in AC record: {ac.get('change_target')!r}"
        )

        assert "risk_surface" in fm, (
            "Expected 'risk_surface' in the generated ticket frontmatter when "
            "the real TQ-100d-1 record carries that field.\n"
            f"Frontmatter keys present: {sorted(fm.keys())}\n"
            f"risk_surface value in AC record: {ac.get('risk_surface')!r}"
        )

        # ---- Step 5: Assert the agents block in the frontmatter has architect-review ----
        agents_fm = fm.get("agents", {})

        assert "architect-review" in agents_fm, (
            f"Expected 'architect-review' in the 'agents:' block of the generated "
            f"frontmatter for TQ-100d-1.\n\n"
            f"agents block: {agents_fm}\n\n"
            "This is the real-store phantom-done gate: the axes from the on-disk "
            "YAML must flow through _build_frontmatter into the emitted ticket."
        )

        assert agents_fm.get("architect-review") == "needed", (
            f"architect-review must be 'needed' in the frontmatter agents block; "
            f"got {agents_fm.get('architect-review')!r}.\n"
            f"Full agents block: {agents_fm}"
        )


# ---------------------------------------------------------------------------
# Test Requirements derived from the AC (source of truth)
# ---------------------------------------------------------------------------

import re as _re_tc  # noqa: E402

from generate_ticket_from_ac import (  # noqa: E402
    _build_test_requirements_section,
    _build_verification_report,
    _derive_tests_from_criteria,
    _test_descriptors_from_spec,
)


class TestTestRequirementsDerivedFromAC:
    """## Test Requirements is derived from the AC's test_spec/criteria, never a
    hardcoded empty stub. This is the hybrid source-of-truth behaviour."""

    _CODE_AGENTS = {
        "python-coder": "needed",
        "test-writer": "needed",
        "test-runner": "needed",
    }

    def test_derives_from_explicit_test_spec(self):
        ac = {
            "assigned_agent": "python-coder",
            "criteria": "Given x\nWhen y\nThen z",
            "test_spec": [
                {"name": "test_alpha", "target_dir": "unit_tests/ac_store/",
                 "description": "alpha holds", "framework": "pytest", "type": "unit"},
                {"name": "test_beta", "target_dir": "unit_tests/ac_store/"},
            ],
        }
        section = _build_test_requirements_section(ac, "ZZ-100a-1")
        assert "## Test Requirements" in section
        assert "test_alpha" in section and "test_beta" in section
        # file path derived from target_dir + ac slug
        assert "unit_tests/ac_store/test_zz_100a_1.py" in section
        # no hardcoded empty stub
        assert "tests: []" not in section

    def test_falls_back_to_criteria_then_clauses(self):
        ac = {
            "assigned_agent": "python-coder",
            "criteria": "Given a store\nWhen scanned\nThen it returns ready ACs\nThen it sorts by priority",
        }
        descriptors = _derive_tests_from_criteria(ac, "BP-811")
        # one descriptor per Then clause
        assert len(descriptors) == 2
        assert all(d["name"].startswith("test_bp_811_") for d in descriptors)
        assert all(d["covers"] == ["BP-811"] for d in descriptors)

    def test_no_then_clause_yields_one_generic_stub(self):
        ac = {"assigned_agent": "python-coder", "criteria": "A prose criterion with no gherkin."}
        descriptors = _derive_tests_from_criteria(ac, "BP-900")
        assert len(descriptors) == 1
        assert descriptors[0]["name"] == "test_bp_900_satisfies_criteria"

    def test_colliding_then_clauses_yield_unique_names(self):
        # Slugs that collide after the disambiguation suffix must not silently
        # produce two descriptors with the same name (one test would be lost).
        ac = {
            "assigned_agent": "python-coder",
            "criteria": "Given a\nWhen b\nThen x 2\nThen x\nThen x",
        }
        descriptors = _derive_tests_from_criteria(ac, "ZZ-100")
        names = [d["name"] for d in descriptors]
        assert len(names) == len(set(names)), f"duplicate test names: {names}"

    def test_test_required_false_omits_section(self):
        ac = {
            "assigned_agent": "llm-expert",
            "criteria": "Given a prompt\nWhen edited\nThen it reads better",
            "test_required": False,
        }
        section = _build_test_requirements_section(ac, "GE-700a-2")
        assert section == ""

    def test_spec_descriptor_normalisation(self):
        ac = {"test_spec": [{"name": "t1", "target_dir": "unit_tests/x/",
                             "requires_db": True, "covers": ["A-1", "A-2"]}]}
        descriptors = _test_descriptors_from_spec(ac, "A-1")
        assert descriptors[0]["requires_db"] is True
        assert descriptors[0]["covers"] == ["A-1", "A-2"]

    def test_generated_block_passes_name_entry_regex(self):
        # The ticket-level guard requires at least one "- name: <x>" entry.
        ac = {
            "assigned_agent": "python-coder",
            "criteria": "Given a\nWhen b\nThen c happens",
        }
        body = _build_ticket_body(
            ac, "ZZ-200a-1", agents_map=dict(self._CODE_AGENTS)
        )
        assert _re_tc.search(r"^\s*-\s+name:\s+\S+", body, _re_tc.MULTILINE), (
            "derived ## Test Requirements must contain a populated test entry so the "
            "check-ticket-test-requirements guard passes"
        )


class TestVerificationReport:
    """--verify report flags source-of-truth gaps without a hard FAIL on the
    common (criteria-derivable) path."""

    def test_report_passes_with_test_spec(self):
        ac = {
            "assigned_agent": "python-coder",
            "readiness": "approved",
            "criteria": "Given a\nWhen b\nThen c",
            "it_requirements": ["reuse the loader"],
            "test_spec": [{"name": "test_c", "target_dir": "unit_tests/x/"}],
        }
        agents = {"python-coder": "needed", "test-writer": "needed"}
        body = _build_ticket_body(ac, "ZZ-300a-1", agents_map=agents)
        report, has_fail = _build_verification_report(ac, "ZZ-300a-1", agents, body, ["scripts/x.py"])
        assert has_fail is False
        assert "test_spec authored" in report

    def test_report_warns_without_test_spec_but_no_fail(self):
        ac = {
            "assigned_agent": "python-coder",
            "readiness": "approved",
            "criteria": "Given a\nWhen b\nThen c",
        }
        agents = {"python-coder": "needed", "test-writer": "needed"}
        body = _build_ticket_body(ac, "ZZ-301a-1", agents_map=agents)
        report, has_fail = _build_verification_report(ac, "ZZ-301a-1", agents, body, [])
        assert has_fail is False
        assert "DERIVED from criteria" in report

    def test_report_fails_when_no_criteria_and_no_spec(self):
        ac = {"assigned_agent": "python-coder", "readiness": "approved", "criteria": ""}
        agents = {"python-coder": "needed", "test-writer": "needed"}
        body = _build_ticket_body(ac, "ZZ-302a-1", agents_map=agents)
        report, has_fail = _build_verification_report(ac, "ZZ-302a-1", agents, body, [])
        assert has_fail is True
        assert "BLOCKED" in report


# ===========================================================================
# BO-500 AC Coverage Backfill Tests
# Ticket: 03_bo500_test_coverage.md
# ACs covered: BO-510-1, BO-510-2, BO-510-4, BO-510-4-i, BO-510-5,
#              BO-530-1-i, BO-530-2, BO-530-3, BO-530-3-i, BO-540-1,
#              BO-540-1-i, BO-540-2, BO-550-1-i, BO-660-1
# ===========================================================================

import json as _json  # noqa: E402
import re as _re_bo500  # noqa: E402

from generate_ticket_from_ac import (  # noqa: E402
    _load_production_code_agents,
)

_AGENT_REGISTRY_PATH = _REPO_ROOT / "config" / "agent_registry.json"
_TEMPLATES_DIR = _REPO_ROOT / "templates" / "agents"
_BUILDING_EPICS_SKILL = (
    _REPO_ROOT / "templates" / "skills" / "building-epics" / "SKILL.md"
)

# Enum values from BO-510-1 AC definition.
_VALID_PRODUCES_ENUM = frozenset({
    "production_code",
    "documentation",
    "configuration",
    "prompt",
    "review_verdict",
    "orchestration",
    "test_artifact",
    "analysis",
})

# Role → produces mapping from BO-510-1 criteria
_ROLE_PRODUCES_MAPPING = {
    "coding": "production_code",
    "documentation": "documentation",
    "review": "review_verdict",
    "orchestration": "orchestration",
    "quality": "test_artifact",
    "analysis": "analysis",
}


# ---------------------------------------------------------------------------
# TestBO510Registry
# BO-510-1: Agent registry entries carry a produces trait field from a defined enum
# ---------------------------------------------------------------------------


class TestBO510Registry:
    """BO-510-1: Every agent_registry.json entry carries a 'produces' field
    with a value from the 8-member enum; the role→produces mapping is consistent.
    """

    def test_bo510_1_all_registry_entries_have_produces_field(self) -> None:
        # covers: BO-510-1
        """BO-510-1: Every entry in agent_registry.json must have a 'produces' field
        (not absent and not null). The field is required by the BO-510-1 schema contract.
        """
        assert _AGENT_REGISTRY_PATH.exists(), (
            f"agent_registry.json not found at {_AGENT_REGISTRY_PATH}"
        )
        with open(_AGENT_REGISTRY_PATH, encoding="utf-8") as fh:
            registry = _json.load(fh)

        missing = []
        for agent in registry.get("agents", []):
            agent_id = agent.get("id", "<unknown>")
            if "produces" not in agent or agent["produces"] is None:
                missing.append(agent_id)

        assert not missing, (
            f"BO-510-1: The following agents are missing the 'produces' field or have "
            f"produces: null:\n  {missing}\n\n"
            "Every agent entry must carry a non-null 'produces' field per BO-510-1."
        )

    def test_bo510_1_produces_values_match_defined_enum(self) -> None:
        # covers: BO-510-1
        """BO-510-1: Every produces field value must be one of the 8-member enum:
        production_code, documentation, configuration, prompt, review_verdict,
        orchestration, test_artifact, analysis.
        """
        with open(_AGENT_REGISTRY_PATH, encoding="utf-8") as fh:
            registry = _json.load(fh)

        invalid = []
        for agent in registry.get("agents", []):
            agent_id = agent.get("id", "<unknown>")
            produces = agent.get("produces")
            if produces is not None and produces not in _VALID_PRODUCES_ENUM:
                invalid.append(f"{agent_id}: {produces!r}")

        assert not invalid, (
            f"BO-510-1: The following agents have produces values outside the defined enum "
            f"{sorted(_VALID_PRODUCES_ENUM)}:\n  " + "\n  ".join(invalid)
        )

    def test_bo510_1_role_coding_maps_to_production_code(self) -> None:
        # covers: BO-510-1
        """BO-510-1: Agents with role='coding' must have produces='production_code'.

        The AC criteria states: 'agents with role "coding" have produces: production_code'.
        """
        with open(_AGENT_REGISTRY_PATH, encoding="utf-8") as fh:
            registry = _json.load(fh)

        violations = []
        for agent in registry.get("agents", []):
            role = agent.get("role", "")
            produces = agent.get("produces")
            agent_id = agent.get("id", "<unknown>")
            if role in _ROLE_PRODUCES_MAPPING:
                expected = _ROLE_PRODUCES_MAPPING[role]
                if produces != expected:
                    violations.append(
                        f"{agent_id}: role={role!r} → expected produces={expected!r}, "
                        f"got {produces!r}"
                    )

        assert not violations, (
            "BO-510-1: Role→produces mapping violated for the following agents:\n  "
            + "\n  ".join(violations)
            + "\n\nExpected mapping: "
            + str(_ROLE_PRODUCES_MAPPING)
        )


# ---------------------------------------------------------------------------
# TestBO510TemplateProduces
# BO-510-2: Agent template frontmatter carries the produces trait matching the registry
# BO-510-4: llm-expert populates the produces trait on every existing agent template
# ---------------------------------------------------------------------------


class TestBO510TemplateProduces:
    """BO-510-2, BO-510-4: Agent templates have produces field in YAML frontmatter,
    populated to match the registry entry for each agent.
    """

    def _load_registry_produces_map(self) -> dict[str, str]:
        """Load agent_id → produces mapping from the registry."""
        with open(_AGENT_REGISTRY_PATH, encoding="utf-8") as fh:
            registry = _json.load(fh)

        return {
            agent.get("id", ""): agent.get("produces")
            for agent in registry.get("agents", [])
            if agent.get("id")
        }

    def test_bo510_2_all_agent_templates_have_produces_in_frontmatter(self) -> None:
        # covers: BO-510-2
        # covers: BO-510-4
        """BO-510-2, BO-510-4: Every agent template in templates/agents/ that has a
        corresponding registry entry with template_path must contain a 'produces:' key
        in its YAML frontmatter.
        """
        assert _TEMPLATES_DIR.exists(), (
            f"templates/agents/ directory not found at {_TEMPLATES_DIR}"
        )

        missing = []
        for tmpl_path in sorted(_TEMPLATES_DIR.glob("*.md")):
            # Skip non-agent special files
            if tmpl_path.name.startswith("_") or tmpl_path.name == "README.md":
                continue
            content = tmpl_path.read_text(encoding="utf-8")
            # Check YAML frontmatter between --- delimiters
            if not content.startswith("---"):
                continue
            parts = content.split("---", 2)
            if len(parts) < 3:
                continue
            frontmatter = parts[1]
            # Check for 'produces:' key in frontmatter (any position)
            if "produces:" not in frontmatter:
                missing.append(tmpl_path.name)

        assert not missing, (
            "BO-510-2/BO-510-4: The following agent templates are missing the 'produces:' "
            "field in their YAML frontmatter:\n  " + "\n  ".join(missing)
            + "\n\nAll templates must have 'produces:' populated per BO-510-4."
        )

    def test_bo510_2_template_produces_matches_registry_value(self) -> None:
        # covers: BO-510-2
        """BO-510-2: The produces value in each template frontmatter must match exactly
        the produces value in the corresponding agent_registry.json entry.

        A mismatch means the template was populated with a different value than the registry,
        violating the single-source-of-truth constraint.
        """
        import yaml as _yaml

        registry_map = self._load_registry_produces_map()
        mismatches = []

        for tmpl_path in sorted(_TEMPLATES_DIR.glob("*.md")):
            if tmpl_path.name.startswith("_") or tmpl_path.name == "README.md":
                continue
            content = tmpl_path.read_text(encoding="utf-8")
            if not content.startswith("---"):
                continue
            parts = content.split("---", 2)
            if len(parts) < 3:
                continue
            try:
                fm = _yaml.safe_load(parts[1])
            except _yaml.YAMLError:
                continue
            if not isinstance(fm, dict):
                continue

            # Derive agent_id from template filename (remove .md suffix)
            tmpl_id = tmpl_path.stem
            if tmpl_id not in registry_map:
                continue  # Not in registry — skip (may be a utility template)

            registry_produces = registry_map[tmpl_id]
            template_produces = fm.get("produces")

            if registry_produces is None:
                continue  # Null in registry is handled by BO-510-4-i
            if template_produces != registry_produces:
                mismatches.append(
                    f"{tmpl_path.name}: template produces={template_produces!r}, "
                    f"registry produces={registry_produces!r}"
                )

        assert not mismatches, (
            "BO-510-2: produces field mismatch between template frontmatter and registry:\n  "
            + "\n  ".join(mismatches)
        )


# ---------------------------------------------------------------------------
# TestBO510AmbiguousAndTrait
# BO-510-4-i: llm-expert flags ambiguous agent trait for human review (produces: null)
# BO-510-5: ticket-supervisor reads the produces trait to determine guardrails
# ---------------------------------------------------------------------------


class TestBO510AmbiguousAndTrait:
    """BO-510-4-i, BO-510-5: Ambiguous produces handling and trait-based guardrail dispatch."""

    def test_bo510_4i_null_produces_excluded_from_production_code_agents(
        self, tmp_path: Path
    ) -> None:
        # covers: BO-510-4-i
        """BO-510-4-i: An agent entry with produces: null must NOT appear in the set
        of production_code producers returned by _load_production_code_agents.

        When llm-expert flags an ambiguous agent with produces: null (per BO-510-4-i),
        that agent must not trigger TDD injection. The test verifies that
        _load_production_code_agents correctly excludes null-produces entries.
        """
        # Write a fixture registry with one ambiguous agent (produces: null)
        fixture_registry = {
            "agents": [
                {"id": "python-coder", "produces": "production_code"},
                {"id": "ambiguous-coder", "produces": None},  # flagged as ambiguous
                {"id": "doc-writer", "produces": "documentation"},
            ]
        }
        fixture_path = tmp_path / "fixture_registry.json"
        fixture_path.write_text(
            _json.dumps(fixture_registry, indent=2),
            encoding="utf-8",
        )

        producers = _load_production_code_agents(fixture_path)

        assert "python-coder" in producers, (
            "_load_production_code_agents must include agents with produces='production_code'"
        )
        assert "ambiguous-coder" not in producers, (
            "BO-510-4-i: An agent flagged with produces=null must NOT be included in the "
            "production_code producers set — the null flag signals human review is required, "
            "and the agent must not trigger TDD guardrail injection until resolved."
        )
        assert "doc-writer" not in producers, (
            "Agents with produces='documentation' must not be in the production_code set."
        )

    def test_bo510_5_production_code_agent_triggers_tdd_injection(self) -> None:
        # covers: BO-510-5
        """BO-510-5: When the assigned agent has produces: production_code, test-writer
        must be injected before it and test-runner after it in the computed map.

        ticket-supervisor reads the 'produces' field to determine that TDD guardrails apply.
        This test verifies that the produces field (via registry lookup) drives the injection,
        not the agent name string.
        """
        # python-coder has produces: production_code in the real registry.
        result = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="internal",
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY_PATH,
        )
        keys = list(result.keys())

        assert "test-writer" in keys, (
            "BO-510-5: test-writer must be in agents map when assigned agent "
            "has produces: production_code (python-coder)"
        )
        assert "test-runner" in keys, (
            "BO-510-5: test-runner must be in agents map when assigned agent "
            "has produces: production_code (python-coder)"
        )

        tw_idx = keys.index("test-writer")
        pc_idx = keys.index("python-coder")
        tr_idx = keys.index("test-runner")

        assert tw_idx < pc_idx, (
            f"BO-510-5: test-writer (idx {tw_idx}) must precede python-coder (idx {pc_idx})"
        )
        assert pc_idx < tr_idx, (
            f"BO-510-5: python-coder (idx {pc_idx}) must precede test-runner (idx {tr_idx})"
        )

    def test_bo510_5_documentation_agent_skips_tdd_injection(self) -> None:
        # covers: BO-510-5
        """BO-510-5: When the assigned agent has produces: documentation (e.g.
        documentation-expert), TDD guardrails (test-writer, test-runner) must NOT be
        injected around the documentation agent.

        ticket-supervisor reads produces: documentation → determines TDD does NOT apply.
        """
        result = _build_agents_map(
            "documentation-expert",
            change_targets=["docs"],
            risk_surface="internal",
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY_PATH,
        )

        # docs/internal guardrail includes documentation-expert, but NOT test-writer or test-runner.
        # documentation-expert has produces: documentation (not production_code).
        # Therefore the auto-inject rule must NOT add test-writer or test-runner.
        assert result.get("test-writer") != "needed", (
            "BO-510-5: test-writer must NOT be 'needed' when assigned agent has "
            "produces: documentation (documentation-expert). TDD guardrails must be "
            "skipped for non-production_code agents."
        )
        assert result.get("test-runner") != "needed", (
            "BO-510-5: test-runner must NOT be 'needed' when assigned agent has "
            "produces: documentation (documentation-expert)."
        )


# ---------------------------------------------------------------------------
# TestBO530TddSandwich
# BO-530-1-i: Ticket with doc_change skips TDD injection entirely
# BO-530-2: test-runner is injected after every coder-class agent
# BO-530-3: Test failure hands context back to implementation agent for rework
# BO-530-3-i: Retry cap on test-failure rework loop
# ---------------------------------------------------------------------------


class TestBO530TddSandwich:
    """BO-530 group: TDD sandwich behavior — injection, ordering, and rework loop."""

    def test_bo530_1i_documentation_change_skips_tdd_injection(self) -> None:
        # covers: BO-530-1-i
        """BO-530-1-i: A docs change with documentation-expert assigned must produce
        an agent chain that does NOT contain test-writer or test-runner.

        Given change_type: doc_change and assigned agent documentation-expert
        (produces: documentation), the TDD injection must be skipped entirely.
        """
        result = _build_agents_map(
            "documentation-expert",
            change_targets=["docs"],
            risk_surface="internal",
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY_PATH,
        )

        # The docs/internal guardrail does not mandate test-writer or test-runner.
        # documentation-expert does not produce production_code.
        # Therefore neither test-writer nor test-runner should be "needed".
        assert result.get("test-writer") != "needed", (
            "BO-530-1-i: test-writer must not be 'needed' for a docs/internal documentation change. "
            f"Got agents map: {result}"
        )
        assert result.get("test-runner") != "needed", (
            "BO-530-1-i: test-runner must not be 'needed' for a docs/internal documentation change. "
            f"Got agents map: {result}"
        )
        assert "documentation-expert" in result, (
            "BO-530-1-i: documentation-expert must be in the computed agents map."
        )

    def test_bo530_2_test_runner_after_python_coder(self) -> None:
        # covers: BO-530-2
        """BO-530-2: test-runner must appear in the computed agents map with a higher
        sequence position than python-coder (the production_code producer).

        The TDD sandwich invariant: test-writer → coder → test-runner must hold for
        all agents with produces: production_code.
        """
        result = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="internal",
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY_PATH,
        )

        keys = list(result.keys())

        assert "test-runner" in keys, (
            "BO-530-2: test-runner must be present in the agents map for a code/internal change "
            "with python-coder assigned."
        )
        assert "python-coder" in keys, (
            "python-coder must be in the agents map."
        )

        pc_idx = keys.index("python-coder")
        tr_idx = keys.index("test-runner")

        assert pc_idx < tr_idx, (
            f"BO-530-2: python-coder (index {pc_idx}) must appear BEFORE test-runner "
            f"(index {tr_idx}) in the agents map key order. "
            f"Full map: {result}"
        )

    def test_bo530_2_test_runner_before_pr_reviewer(self) -> None:
        # covers: BO-530-2
        """BO-530-2: test-runner must also appear BEFORE pr-reviewer in the computed
        agents map. The AC criteria states: 'test-runner appears BEFORE pr-reviewer'.
        """
        result = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="contract_boundary",
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY_PATH,
        )
        keys = list(result.keys())

        assert "test-runner" in keys, "test-runner must be in agents map for code/contract_boundary"
        assert "pr-reviewer" in keys, "pr-reviewer must be in agents map for code/contract_boundary"

        tr_idx = keys.index("test-runner")
        pr_idx = keys.index("pr-reviewer")

        assert tr_idx < pr_idx, (
            f"BO-530-2: test-runner (index {tr_idx}) must appear BEFORE pr-reviewer "
            f"(index {pr_idx}). Full map keys: {keys}"
        )

    def test_bo530_3_work_agent_correctly_recorded_in_agents_map(self) -> None:
        # covers: BO-530-3
        """BO-530-3: The generated agents map must correctly record the work agent
        (e.g. python-coder vs sql-coder) so that ticket-supervisor can re-dispatch
        the ORIGINAL work agent after test-runner failure.

        If the work agent is sql-coder, the map must have sql-coder: needed (not
        defaulting to python-coder).
        """
        result_python = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="internal",
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY_PATH,
        )
        result_sql = _build_agents_map(
            "sql-coder",
            change_targets=["code"],
            risk_surface="internal",
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY_PATH,
        )

        assert result_python.get("python-coder") == "needed", (
            "BO-530-3: python-coder must be 'needed' in the agents map when assigned "
            "so ticket-supervisor can re-dispatch it on test failure."
        )
        assert result_sql.get("sql-coder") == "needed", (
            "BO-530-3: sql-coder must be 'needed' in the agents map when assigned "
            "so ticket-supervisor re-dispatches sql-coder (not python-coder) on failure."
        )
        # Must not confuse the work agent identity
        assert result_sql.get("python-coder") != "needed" or "python-coder" not in result_sql, (
            "BO-530-3: When sql-coder is the work agent, python-coder must NOT be 'needed' "
            "in the computed map (to avoid ticket-supervisor dispatching the wrong agent)."
        )

    def test_bo530_3i_building_epics_documents_test_failure_rework_cap(self) -> None:
        # covers: BO-530-3-i
        """BO-530-3-i: The building-epics SKILL.md must explicitly document a retry cap
        for the test-failure rework loop with a configurable default of 2 attempts.

        The AC criteria state: 'the retry cap is configurable in the building-epics skill
        (default: 2 rework attempts)'.

        RED before fix: The current §4 Retry Caps table has 'Sibling respawn from review:
        1 per phase pair per ticket' — this is a GENERIC cap that does not specifically
        address the test-failure rework cycle (test-runner fails → python-coder reworks).
        The SKILL.md must be updated to include an explicit test-failure rework cap of 2
        (configurable). Until that update, this test is RED.
        """
        assert _BUILDING_EPICS_SKILL.exists(), (
            f"building-epics SKILL.md not found at {_BUILDING_EPICS_SKILL}"
        )
        skill_text = _BUILDING_EPICS_SKILL.read_text(encoding="utf-8")

        # Look for explicit mention of "test-failure rework" (or equivalent) with
        # a numeric cap of 2 in the §4 Retry Caps table or a dedicated section.
        # The string "test-failure rework" must appear near a "2" in the retry cap table.
        has_test_failure_rework_row = bool(
            _re_bo500.search(
                r"test.failure.rework",
                skill_text,
                _re_bo500.IGNORECASE,
            )
        )

        assert has_test_failure_rework_row, (
            "BO-530-3-i: The building-epics SKILL.md §4 Retry Caps table must include an "
            "explicit row for 'test-failure rework' with a configurable default of 2 attempts.\n\n"
            "Currently the §4 table only has:\n"
            "  - Coder respawn after own failure (§3.1): 1 per phase per ticket\n"
            "  - Sibling respawn from review (§3.2): 1 per phase pair per ticket\n\n"
            "Neither row specifically addresses the test-runner failure → coder rework loop, "
            "and neither documents the 2-attempt default required by BO-530-3-i.\n\n"
            "Fix: Add a 'test-failure rework' row to the §4 table with cap=2 (configurable).\n"
            f"Searched in: {_BUILDING_EPICS_SKILL}"
        )


# ---------------------------------------------------------------------------
# TestBO540FlowChangeOrdering
# BO-540-1: flow_change injects architect-review before any coder
# BO-540-1-i: Coder dispatch is blocked if architect-review has not signed off
# BO-540-2: flow_change injects documentation-expert before any coder
# ---------------------------------------------------------------------------


class TestBO540FlowChangeOrdering:
    """BO-540 group: Flow-change pair agent ordering requirements."""

    def test_bo540_1_architect_review_before_coder_for_flow_change(self) -> None:
        # covers: BO-540-1
        """BO-540-1: For a flow_change pair (code/contract_boundary), architect-review
        must appear in the computed agents map BEFORE python-coder.

        The AC criteria: 'architect-review appears in the chain AND architect-review has
        a lower sequence number than python-coder'.
        """
        result = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="contract_boundary",
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY_PATH,
        )
        keys = list(result.keys())

        assert "architect-review" in keys, (
            "BO-540-1: architect-review must be in the agents map for code/contract_boundary "
            "(a flow_change pair). Currently absent — the flow_change_gates entry must mandate "
            f"architect-review for this pair. Full map: {result}"
        )

        ar_idx = keys.index("architect-review")
        pc_idx = keys.index("python-coder")

        assert ar_idx < pc_idx, (
            f"BO-540-1: architect-review (index {ar_idx}) must appear BEFORE python-coder "
            f"(index {pc_idx}) for the code/contract_boundary flow_change pair.\n"
            f"Full map keys: {keys}"
        )

    def test_bo540_1i_architect_review_before_test_writer_in_flow_change(self) -> None:
        # covers: BO-540-1-i
        """BO-540-1-i: For a flow_change pair, architect-review must appear BEFORE
        test-writer in the computed map, not just before python-coder.

        The AC criteria: 'architect-review must sign off before any coder or test-writer
        is dispatched' — this implies architect-review precedes test-writer as well.
        """
        result = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="contract_boundary",
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY_PATH,
        )
        keys = list(result.keys())

        assert "architect-review" in keys, (
            "BO-540-1-i: architect-review must be present for code/contract_boundary."
        )
        assert "test-writer" in keys, (
            "BO-540-1-i: test-writer must be present for code/contract_boundary."
        )

        ar_idx = keys.index("architect-review")
        tw_idx = keys.index("test-writer")

        assert ar_idx < tw_idx, (
            f"BO-540-1-i: architect-review (index {ar_idx}) must appear BEFORE test-writer "
            f"(index {tw_idx}). architect-review must sign off before test-writer is dispatched.\n"
            f"Full map keys: {keys}"
        )

    def test_bo540_2_documentation_expert_before_coder_for_flow_change(self) -> None:
        # covers: BO-540-2
        """BO-540-2: For a flow_change pair (code/contract_boundary), documentation-expert
        must appear in the computed agents map BEFORE python-coder.

        The AC criteria: 'documentation-expert has a lower sequence number than python-coder
        AND documentation-expert has a lower sequence number than test-writer'.
        """
        result = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="contract_boundary",
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY_PATH,
        )
        keys = list(result.keys())

        assert "documentation-expert" in keys, (
            "BO-540-2: documentation-expert must be in the agents map for code/contract_boundary "
            "(a flow_change pair). The flow_change_gates mandatory_agents for this pair includes "
            f"documentation-expert. Full map: {result}"
        )

        de_idx = keys.index("documentation-expert")
        pc_idx = keys.index("python-coder")

        assert de_idx < pc_idx, (
            f"BO-540-2: documentation-expert (index {de_idx}) must appear BEFORE "
            f"python-coder (index {pc_idx}) for the code/contract_boundary flow_change pair.\n"
            f"Full map keys: {keys}"
        )

    def test_bo540_2_documentation_expert_before_test_writer_in_flow_change(self) -> None:
        # covers: BO-540-2
        """BO-540-2: For a flow_change pair, documentation-expert must also appear BEFORE
        test-writer. The AC states: 'documentation-expert has a lower sequence number than
        test-writer' (documentation planning must happen before TDD authoring).
        """
        result = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="contract_boundary",
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY_PATH,
        )
        keys = list(result.keys())

        assert "documentation-expert" in keys, (
            "BO-540-2: documentation-expert must be present for code/contract_boundary."
        )
        assert "test-writer" in keys, (
            "BO-540-2: test-writer must be present for code/contract_boundary."
        )

        de_idx = keys.index("documentation-expert")
        tw_idx = keys.index("test-writer")

        assert de_idx < tw_idx, (
            f"BO-540-2: documentation-expert (index {de_idx}) must appear BEFORE "
            f"test-writer (index {tw_idx}) for the code/contract_boundary flow_change pair.\n"
            "documentation-expert plans the spec before test-writer authors tests.\n"
            f"Full map keys: {keys}"
        )


# ---------------------------------------------------------------------------
# TestBO550ItPoConstraints
# BO-550-1-i: IT PO modifying agents map for testing is rejected in favor of
#              the computed chain
# ---------------------------------------------------------------------------


class TestBO550ItPoConstraints:
    """BO-550-1-i: The computed chain takes precedence over IT PO's manual
    test-agent additions or removals. test-writer and test-runner cannot be
    excluded from the map by passing not_needed_overrides when the computed
    chain mandates them.

    RED before fix: _build_agents_map currently honors not_needed_overrides
    unconditionally — including for TDD-mandated agents (test-writer, test-runner).
    BO-550-1-i requires that the computed chain wins: these agents cannot be
    removed by manual override.
    """

    def test_bo550_1i_test_writer_not_overridable_to_not_needed(self) -> None:
        # covers: BO-550-1-i
        """BO-550-1-i: When the guardrail config mandates test-writer for a
        (change_target, risk_surface) pair (e.g. code/internal → test-writer),
        passing not_needed_overrides={'test-writer': 'not_needed'} must be REJECTED.
        The computed chain takes precedence; test-writer must remain 'needed'.

        RED before fix: _build_agents_map respects not_needed_overrides.discard('test-writer'),
        then sets agents['test-writer'] = 'not_needed' via the phase-order loop.
        After fix: TDD-mandated agents (test-writer, test-runner) must be protected from
        not_needed_overrides when they are required by the computed guardrail chain.
        """
        result = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="internal",
            not_needed_overrides={"test-writer": "not_needed"},
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY_PATH,
        )

        # BO-550-1-i requires the computed chain to win:
        assert result.get("test-writer") == "needed", (
            "BO-550-1-i: test-writer must remain 'needed' even when "
            "not_needed_overrides={'test-writer': 'not_needed'} is passed, because the "
            "guardrail config for code/internal mandates test-writer.\n\n"
            "The computed chain takes precedence over the IT PO's manual override. "
            "Currently _build_agents_map removes test-writer from all_needed and sets it "
            "to not_needed in the phase-order loop — violating BO-550-1-i.\n\n"
            f"Actual agents map: {result}"
        )

    def test_bo550_1i_test_runner_not_overridable_to_not_needed(self) -> None:
        # covers: BO-550-1-i
        """BO-550-1-i: Similarly to test-writer, test-runner cannot be excluded by
        not_needed_overrides when the computed chain mandates it.

        RED before fix: same as test_bo550_1i_test_writer_not_overridable_to_not_needed.
        """
        result = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="internal",
            not_needed_overrides={"test-runner": "not_needed"},
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY_PATH,
        )

        assert result.get("test-runner") == "needed", (
            "BO-550-1-i: test-runner must remain 'needed' even when "
            "not_needed_overrides={'test-runner': 'not_needed'} is passed, because the "
            "guardrail config for code/internal mandates test-runner.\n\n"
            "The computed chain takes precedence over the IT PO's manual override.\n\n"
            f"Actual agents map: {result}"
        )

    def test_bo550_1i_non_tdd_agents_remain_overridable(self) -> None:
        # covers: BO-550-1-i
        """BO-550-1-i: The protection against override applies ONLY to TDD-mandated
        agents (test-writer, test-runner). Other agents (e.g. architect-review) must
        still be overridable via not_needed_overrides (per TestPreserveNotNeeded / BO-560-3-i).

        This test confirms the fix is targeted — not a blanket rejection of all overrides.
        """
        result = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="contract_boundary",
            not_needed_overrides={"architect-review": "not_needed"},
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=_AGENT_REGISTRY_PATH,
        )

        # architect-review is in the guardrail for code/contract_boundary, but the override
        # says not_needed. For NON-TDD agents, the override must still be respected.
        # Note: After the BO-550-1-i fix, this test verifies the fix is scoped.
        # Currently this is GREEN (overrides work for non-TDD agents).
        assert result.get("architect-review") == "not_needed", (
            "BO-550-1-i: non-TDD agents (e.g. architect-review) must still be overridable "
            "via not_needed_overrides. The BO-550-1-i protection applies only to "
            "test-writer and test-runner.\n\n"
            f"Actual agents map: {result}"
        )


# ---------------------------------------------------------------------------
# TestBO660TraitBasedInheritance
# BO-660-1: New agent type inherits guardrails from its declared produces trait
# ---------------------------------------------------------------------------


class TestBO660TraitBasedInheritance:
    """BO-660-1: A new agent with produces: production_code inherits the same
    guardrails as python-coder for the same (change_target, risk_surface) pair,
    without any manual update to the guardrail mapping.
    """

    def test_bo660_1_new_production_code_agent_gets_same_guardrails_as_python_coder(
        self, tmp_path: Path
    ) -> None:
        # covers: BO-660-1
        """BO-660-1: A new agent 'rust-coder' with produces: production_code in a fixture
        registry must receive the SAME guardrail agents as python-coder for the same
        (change_target, risk_surface) pair (code/contract_boundary).

        No manual update to guardrail_gates.yaml is required — the inheritance is
        trait-based (produces field lookup), not ID-based.
        """
        # Write a fixture registry that includes a novel agent "rust-coder"
        fixture_registry = {
            "agents": [
                {"id": "python-coder", "produces": "production_code"},
                {"id": "rust-coder", "produces": "production_code"},  # new agent
                {"id": "sql-coder", "produces": "production_code"},
                {"id": "documentation-expert", "produces": "documentation"},
                {"id": "test-writer", "produces": "test_artifact"},
                {"id": "test-runner", "produces": "test_artifact"},
                {"id": "architect-review", "produces": "review_verdict"},
                {"id": "pr-reviewer", "produces": "review_verdict"},
            ]
        }
        fixture_reg_path = tmp_path / "fixture_registry.json"
        fixture_reg_path.write_text(
            _json.dumps(fixture_registry, indent=2),
            encoding="utf-8",
        )

        # Build agents map for python-coder (established agent)
        python_map = _build_agents_map(
            "python-coder",
            change_targets=["code"],
            risk_surface="contract_boundary",
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=fixture_reg_path,
        )

        # Build agents map for rust-coder (new agent, same produces trait)
        rust_map = _build_agents_map(
            "rust-coder",
            change_targets=["code"],
            risk_surface="contract_boundary",
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=fixture_reg_path,
        )

        # BO-660-1: rust-coder must inherit architect-review guardrail (same as python-coder)
        assert "architect-review" in rust_map, (
            "BO-660-1: 'rust-coder' (a new agent with produces: production_code) must inherit "
            "architect-review from the code/contract_boundary guardrail, just like python-coder. "
            "No manual update to guardrail_gates.yaml should be required.\n\n"
            f"python-coder map: {python_map}\n"
            f"rust-coder map:   {rust_map}"
        )

        assert rust_map.get("architect-review") == "needed", (
            f"architect-review must be 'needed' for rust-coder; got "
            f"{rust_map.get('architect-review')!r}"
        )

        # BO-660-1: rust-coder must inherit test-writer and test-runner (same as python-coder)
        assert rust_map.get("test-writer") == "needed", (
            "BO-660-1: test-writer must be injected for rust-coder (produces: production_code). "
            "TDD guardrail inheritance must be trait-based, not ID-based.\n\n"
            f"rust-coder map: {rust_map}"
        )
        assert rust_map.get("test-runner") == "needed", (
            "BO-660-1: test-runner must be injected for rust-coder (produces: production_code).\n\n"
            f"rust-coder map: {rust_map}"
        )

    def test_bo660_1_guardrail_inheritance_not_id_based(
        self, tmp_path: Path
    ) -> None:
        # covers: BO-660-1
        """BO-660-1: Guardrail inheritance is trait-based, not ID-based.
        An entirely new agent name that is NOT in any hardcoded fallback list
        still receives production_code guardrails if its produces trait is
        correctly set in the fixture registry.

        'And no manual update to the guardrail mapping is required for the new agent'.
        """
        # Novel agent not in any hardcoded fallback set
        fixture_registry = {
            "agents": [
                {"id": "totally-new-lang-coder", "produces": "production_code"},
                {"id": "test-writer", "produces": "test_artifact"},
                {"id": "test-runner", "produces": "test_artifact"},
            ]
        }
        fixture_reg_path = tmp_path / "fixture_novel_registry.json"
        fixture_reg_path.write_text(
            _json.dumps(fixture_registry, indent=2),
            encoding="utf-8",
        )

        result = _build_agents_map(
            "totally-new-lang-coder",
            change_targets=["code"],
            risk_surface="internal",
            guardrail_config_path=_GUARDRAIL_CONFIG,
            agent_registry_path=fixture_reg_path,
        )

        # The novel agent must get test-writer and test-runner injected via the produces trait
        # (code/internal guardrail mandates test-writer, test-runner AND the auto-inject rule
        # fires because totally-new-lang-coder has produces: production_code).
        assert "test-writer" in result, (
            "BO-660-1: test-writer must be auto-injected for 'totally-new-lang-coder' "
            "because it has produces: production_code in the fixture registry. "
            "This confirms trait-based (not ID-based) guardrail inheritance.\n\n"
            f"Result map: {result}"
        )
        assert "test-runner" in result, (
            "BO-660-1: test-runner must be auto-injected for 'totally-new-lang-coder' "
            "via trait-based inheritance.\n\n"
            f"Result map: {result}"
        )
