"""
MODULE: test_composition_depth
GOAL: Unit tests for resolve_behavior_stack() in scan_ac_store.py.
BUSINESS CONTEXT: Verifies ACS-500e-2 — composition depth is visible through
    the AC parent-child hierarchy using only the standard depends_on and
    implements_pattern fields.
ARCHITECTURE: Tests the resolve_behavior_stack() function which traverses a
    three-layer AC graph: page AC → composite pattern (via implements_pattern)
    → atomic patterns (via depends_on on the composite). No additional
    hierarchy mechanism is exercised.
TICKET: EPIC-Defineabehavioronce,reusethespec/17_TICKET-20260611-ACS-500e-2.md
COVERS: ACS-500e-2
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from scan_ac_store import _build_id_index, _load_ac, resolve_behavior_stack  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_ac(
    ac_root: Path,
    ac_id: str,
    *,
    criteria: str = "Given a behavior, When triggered, Then it works.",
    implements_pattern: str | None = None,
    pattern_bindings: dict[str, Any] | None = None,
    depends_on: list[str] | None = None,
    level: str = "L2",
    component: str = "ac-store",
) -> Path:
    """Write a minimal AC YAML file and return its path."""
    parts = ac_id.split("-")
    subdir = ac_root / "-".join(parts[:2]) if len(parts) >= 2 else ac_root
    subdir.mkdir(parents=True, exist_ok=True)
    path = subdir / f"{ac_id}.yaml"
    data: dict[str, Any] = {
        "id": ac_id,
        "title": f"AC {ac_id}",
        "component": component,
        "level": level,
        "status": "active",
        "work_status": "todo",
        "criteria": criteria,
    }
    if implements_pattern is not None:
        data["implements_pattern"] = implements_pattern
    if pattern_bindings is not None:
        data["pattern_bindings"] = pattern_bindings
    if depends_on is not None:
        data["depends_on"] = depends_on
    path.write_text(yaml.dump(data, allow_unicode=True), encoding="utf-8")
    return path


def _build_index_from_dir(ac_root: Path) -> dict:
    """Load all AC YAML files from *ac_root* and return an id_index dict."""
    records = []
    for yaml_path in sorted(ac_root.rglob("*.yaml")):
        record = _load_ac(yaml_path)
        if record is not None:
            records.append(record)
    return _build_id_index(records)


# ---------------------------------------------------------------------------
# ACS-500e-2: Three-layer behavior stack traversal
# ---------------------------------------------------------------------------


class TestResolveThreeLayerStack:
    """ACS-500e-2: Full behavior stack resolved through depends_on + implements_pattern."""

    def test_full_three_layer_stack_returned_in_order(self, tmp_path: Path) -> None:
        # covers: ACS-500e-2
        """ACS-500e-2: Page AC → composite (implements_pattern) → atomics (depends_on).

        Given a page AC references composite pattern PTN-020,
        And PTN-020 depends_on atomic patterns [PTN-010, PTN-011, PTN-012],
        When a reader traverses the dependency graph starting from the page AC,
        Then they can resolve the full behavior stack in order:
          1. Page-specific criteria (from the page AC itself),
          2. Composite wiring behavior (from PTN-020),
          3. Atomic behaviors (from PTN-010, PTN-011, PTN-012).
        """
        # Atomic patterns — independent, no depends_on between them
        _write_ac(
            tmp_path,
            "PTN-010",
            criteria="Given a sortable table, When header clicked, Then rows sorted.",
        )
        _write_ac(
            tmp_path,
            "PTN-011",
            criteria="Given a filter bar, When text entered, Then rows filtered.",
        )
        _write_ac(
            tmp_path,
            "PTN-012",
            criteria="Given a paginated collection, When loaded, Then shows page 1.",
        )

        # Composite pattern — wires atomics via depends_on
        _write_ac(
            tmp_path,
            "PTN-020",
            criteria="Given all three behaviors, When filter changes, Then pagination resets.",
            depends_on=["PTN-010", "PTN-011", "PTN-012"],
        )

        # Page AC — references composite via implements_pattern
        _write_ac(
            tmp_path,
            "PAGE-001",
            criteria="No page-specific wiring — all behavior inherited from PTN-020.",
            implements_pattern="PTN-020",
            pattern_bindings={"columns": "invoice_number, date, amount"},
        )

        id_index = _build_index_from_dir(tmp_path)
        stack = resolve_behavior_stack("PAGE-001", id_index)

        assert len(stack) == 5, (
            f"Expected 5 layers (1 page + 1 composite + 3 atomics), got {len(stack)}"
        )

        # Layer 1: page
        assert stack[0]["layer"] == "page"
        assert stack[0]["ac_id"] == "PAGE-001"
        assert stack[0]["source"] == "self"
        assert "page-specific" in (stack[0]["criteria"] or "").lower() or stack[0]["criteria"]

        # Layer 2: composite
        assert stack[1]["layer"] == "composite"
        assert stack[1]["ac_id"] == "PTN-020"
        assert stack[1]["source"] == "implements_pattern"

        # Layers 3-5: atomics in depends_on declaration order
        atomic_ids = [layer["ac_id"] for layer in stack[2:]]
        assert atomic_ids == ["PTN-010", "PTN-011", "PTN-012"], (
            f"Atomics must appear in depends_on declaration order, got: {atomic_ids}"
        )
        for atomic_layer in stack[2:]:
            assert atomic_layer["layer"] == "atomic"
            assert atomic_layer["source"] == "depends_on"

    def test_each_layer_is_distinct_ac_with_own_criteria(self, tmp_path: Path) -> None:
        # covers: ACS-500e-2
        """ACS-500e-2: Each layer has its own distinct ac_id and criteria."""
        _write_ac(tmp_path, "PTN-010", criteria="Atomic PTN-010 criteria.")
        _write_ac(tmp_path, "PTN-011", criteria="Atomic PTN-011 criteria.")
        _write_ac(
            tmp_path, "PTN-020",
            criteria="Composite PTN-020 wiring criteria.",
            depends_on=["PTN-010", "PTN-011"],
        )
        _write_ac(
            tmp_path, "PAGE-001",
            criteria="Page-specific criteria for PAGE-001.",
            implements_pattern="PTN-020",
        )

        id_index = _build_index_from_dir(tmp_path)
        stack = resolve_behavior_stack("PAGE-001", id_index)

        # All ac_ids must be distinct
        ac_ids = [layer["ac_id"] for layer in stack]
        assert len(ac_ids) == len(set(ac_ids)), (
            f"All layer ac_ids must be distinct, got: {ac_ids}"
        )

        # All criteria must be non-None and distinct
        criteria_texts = [layer.get("criteria") for layer in stack]
        assert all(c is not None for c in criteria_texts), (
            f"Every layer must have a criteria value, got: {criteria_texts}"
        )
        assert len(set(criteria_texts)) == len(criteria_texts), (
            f"All criteria texts must be distinct (each layer owns its own), "
            f"got: {criteria_texts}"
        )

    def test_layering_expressible_without_additional_mechanism(self, tmp_path: Path) -> None:
        # covers: ACS-500e-2
        """ACS-500e-2: Behavior stack is fully resolvable via depends_on + implements_pattern only.

        No additional hierarchy mechanism (e.g. custom level tags, extra fields, separate
        catalog) is required. The standard AC schema fields are sufficient.
        """
        _write_ac(tmp_path, "PTN-010", criteria="Atomic A.")
        _write_ac(tmp_path, "PTN-020", criteria="Composite.", depends_on=["PTN-010"])
        _write_ac(tmp_path, "PAGE-001", criteria="Page.", implements_pattern="PTN-020")

        id_index = _build_index_from_dir(tmp_path)
        stack = resolve_behavior_stack("PAGE-001", id_index)

        # Verify that source values reference only the two standard fields
        allowed_sources = {"self", "implements_pattern", "depends_on"}
        for layer in stack:
            assert layer["source"] in allowed_sources, (
                f"Unexpected source field '{layer['source']}' — only standard fields are allowed"
            )


# ---------------------------------------------------------------------------
# Edge cases: missing references and absent fields
# ---------------------------------------------------------------------------


class TestResolveEdgeCases:
    """Edge cases for resolve_behavior_stack()."""

    def test_absent_page_ac_returns_empty(self, tmp_path: Path) -> None:
        # covers: ACS-500e-2
        """resolve_behavior_stack returns [] when the page AC is not in the index."""
        _write_ac(tmp_path, "PTN-010", criteria="Atomic A.")
        id_index = _build_index_from_dir(tmp_path)

        result = resolve_behavior_stack("NONEXISTENT-001", id_index)

        assert result == [], (
            f"Expected [] for unknown AC, got: {result}"
        )

    def test_page_ac_without_implements_pattern_returns_single_layer(
        self, tmp_path: Path
    ) -> None:
        # covers: ACS-500e-2
        """resolve_behavior_stack returns only the page layer when implements_pattern is absent."""
        _write_ac(tmp_path, "PAGE-001", criteria="Standalone page criteria.")

        id_index = _build_index_from_dir(tmp_path)
        stack = resolve_behavior_stack("PAGE-001", id_index)

        assert len(stack) == 1, (
            f"Expected 1 layer (page only) when implements_pattern is absent, "
            f"got {len(stack)}"
        )
        assert stack[0]["layer"] == "page"
        assert stack[0]["ac_id"] == "PAGE-001"

    def test_composite_with_no_depends_on_returns_two_layers(self, tmp_path: Path) -> None:
        # covers: ACS-500e-2
        """resolve_behavior_stack returns page + composite when composite has no depends_on."""
        _write_ac(tmp_path, "PTN-020", criteria="Composite with no atomic deps.")
        _write_ac(tmp_path, "PAGE-001", criteria="Page.", implements_pattern="PTN-020")

        id_index = _build_index_from_dir(tmp_path)
        stack = resolve_behavior_stack("PAGE-001", id_index)

        assert len(stack) == 2, (
            f"Expected 2 layers (page + composite) when composite has no depends_on, "
            f"got {len(stack)}"
        )
        assert stack[0]["layer"] == "page"
        assert stack[1]["layer"] == "composite"

    def test_missing_composite_in_index_returns_single_layer(self, tmp_path: Path) -> None:
        # covers: ACS-500e-2
        """When the composite referenced by implements_pattern is absent from the index,
        only the page layer is returned (no crash)."""
        _write_ac(tmp_path, "PAGE-001", criteria="Page.", implements_pattern="PTN-MISSING")

        id_index = _build_index_from_dir(tmp_path)
        stack = resolve_behavior_stack("PAGE-001", id_index)

        assert len(stack) == 1, (
            f"Expected 1 layer when composite is absent from index, got {len(stack)}"
        )
        assert stack[0]["layer"] == "page"

    def test_missing_atomic_in_index_still_appears_with_none_criteria(
        self, tmp_path: Path
    ) -> None:
        # covers: ACS-500e-2
        """When an atomic referenced by depends_on is absent from the index, its layer
        is included with criteria=None rather than omitted."""
        _write_ac(
            tmp_path, "PTN-020",
            criteria="Composite.",
            depends_on=["PTN-010", "PTN-MISSING"],
        )
        _write_ac(tmp_path, "PTN-010", criteria="Atomic A.")
        _write_ac(tmp_path, "PAGE-001", criteria="Page.", implements_pattern="PTN-020")

        id_index = _build_index_from_dir(tmp_path)
        stack = resolve_behavior_stack("PAGE-001", id_index)

        # page + composite + PTN-010 + PTN-MISSING (with None criteria)
        assert len(stack) == 4, (
            f"Expected 4 layers even when one atomic is missing, got {len(stack)}"
        )
        missing_layer = next(
            (l for l in stack if l["ac_id"] == "PTN-MISSING"), None
        )
        assert missing_layer is not None, "PTN-MISSING layer must still appear"
        assert missing_layer["criteria"] is None, (
            f"Missing atomic must have criteria=None, got: {missing_layer['criteria']}"
        )
        assert missing_layer["layer"] == "atomic"
        assert missing_layer["source"] == "depends_on"

    def test_empty_id_index_returns_empty(self) -> None:
        # covers: ACS-500e-2
        """resolve_behavior_stack returns [] when the id_index is empty."""
        result = resolve_behavior_stack("PAGE-001", {})
        assert result == [], f"Expected [] for empty index, got: {result}"


# ---------------------------------------------------------------------------
# Layer ordering and source field integrity
# ---------------------------------------------------------------------------


class TestLayerOrdering:
    """Verify that resolve_behavior_stack() returns layers in the correct order."""

    def test_page_layer_is_always_first(self, tmp_path: Path) -> None:
        # covers: ACS-500e-2
        """The page-specific layer must always be the first element in the stack."""
        _write_ac(tmp_path, "PTN-010", criteria="Atomic.")
        _write_ac(tmp_path, "PTN-020", criteria="Composite.", depends_on=["PTN-010"])
        _write_ac(tmp_path, "PAGE-001", criteria="Page.", implements_pattern="PTN-020")

        id_index = _build_index_from_dir(tmp_path)
        stack = resolve_behavior_stack("PAGE-001", id_index)

        assert stack[0]["layer"] == "page", (
            f"Page layer must be first, got layer='{stack[0]['layer']}'"
        )

    def test_composite_layer_precedes_atomics(self, tmp_path: Path) -> None:
        # covers: ACS-500e-2
        """The composite wiring layer must come before atomic layers."""
        _write_ac(tmp_path, "PTN-010", criteria="Atomic A.")
        _write_ac(tmp_path, "PTN-011", criteria="Atomic B.")
        _write_ac(
            tmp_path, "PTN-020",
            criteria="Composite.",
            depends_on=["PTN-010", "PTN-011"],
        )
        _write_ac(tmp_path, "PAGE-001", criteria="Page.", implements_pattern="PTN-020")

        id_index = _build_index_from_dir(tmp_path)
        stack = resolve_behavior_stack("PAGE-001", id_index)

        composite_idx = next(
            i for i, l in enumerate(stack) if l["layer"] == "composite"
        )
        for i, layer in enumerate(stack):
            if layer["layer"] == "atomic":
                assert composite_idx < i, (
                    f"Composite (index {composite_idx}) must precede atomic (index {i})"
                )

    def test_atomics_appear_in_depends_on_declaration_order(self, tmp_path: Path) -> None:
        # covers: ACS-500e-2
        """Atomic layers must appear in the order declared in the composite's depends_on list."""
        for atomic_id in ["PTN-010", "PTN-011", "PTN-012"]:
            _write_ac(tmp_path, atomic_id, criteria=f"Atomic {atomic_id}.")

        # Declare in a specific order
        declared_order = ["PTN-012", "PTN-010", "PTN-011"]
        _write_ac(tmp_path, "PTN-020", criteria="Composite.", depends_on=declared_order)
        _write_ac(tmp_path, "PAGE-001", criteria="Page.", implements_pattern="PTN-020")

        id_index = _build_index_from_dir(tmp_path)
        stack = resolve_behavior_stack("PAGE-001", id_index)

        atomic_ids = [l["ac_id"] for l in stack if l["layer"] == "atomic"]
        assert atomic_ids == declared_order, (
            f"Atomics must appear in depends_on declaration order "
            f"({declared_order}), got: {atomic_ids}"
        )
