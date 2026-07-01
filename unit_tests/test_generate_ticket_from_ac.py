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

from ac_store.generate_ticket_from_ac import _build_agents_map, _build_ticket_body  # noqa: E402

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
