"""Guardrail matrix must not make status-checker needed on generated tickets.

Runs the real config/guardrail_gates.yaml through the real
``_build_agents_map``.  A generated build ticket gets status-checker only when
its AC's assigned_agent is status-checker (user decision F5, 2026-10-06); the
cells that used to list it list architect-review instead.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parent.parent
_GATES_PATH = _REPO_ROOT / "config" / "guardrail_gates.yaml"
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "ac_store"))

from generate_ticket_from_ac import _build_agents_map  # noqa: E402


def _load_gates() -> dict:
    with open(_GATES_PATH, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _agents_map(assigned_agent: str, change_target: str, risk_surface: str) -> dict:
    return _build_agents_map(
        assigned_agent,
        change_targets=[change_target],
        risk_surface=risk_surface,
        guardrail_config_path=_GATES_PATH,
    )


def _real_cells(gates: dict) -> list[tuple[str, str]]:
    """Every (change_target, risk_surface) cell and flow-change gate in the YAML."""
    cells: list[tuple[str, str]] = []
    for target, surfaces in gates.items():
        # Matrix rows are the dicts keyed by risk surface (they all carry
        # "internal"); other dict sections (documentation_gates etc.) are not cells.
        if isinstance(surfaces, dict) and "internal" in surfaces:
            cells.extend(
                (target, surface)
                for surface, agents in surfaces.items()
                if isinstance(agents, list)
            )
    for entry in gates.get("flow_change_gates") or []:
        cells.append((entry["change_target"], entry["risk_surface"]))
    return sorted(set(cells))


def test_no_real_guardrail_cell_makes_status_checker_needed():
    # covers: ACD-400b-1
    # angle: real_artifact
    """AC-1/AC-2: no real cell or flow-change gate yields status-checker needed."""
    cells = _real_cells(_load_gates())
    assert cells, "no cells read from the real guardrail YAML"
    offenders = [
        cell
        for cell in cells
        if _agents_map("python-coder", *cell).get("status-checker") == "needed"
    ]
    assert offenders == [], f"cells still making status-checker needed: {offenders}"


def test_assigned_status_checker_is_still_needed():
    # covers: ACD-400b-1
    # angle: boundary
    """AC-3: an AC assigned to status-checker still gets it needed."""
    for cell in (("config", "contract_boundary"), ("code", "internal")):
        agents = _agents_map("status-checker", *cell)
        assert agents.get("status-checker") == "needed", (cell, agents)


def test_config_contract_boundary_gets_architect_review():
    # covers: ACD-400b-1
    # angle: criterion
    """AC-4: config/contract_boundary gets architect-review and pr-reviewer."""
    agents = _agents_map("python-coder", "config", "contract_boundary")
    assert agents.get("architect-review") == "needed", agents
    assert agents.get("pr-reviewer") == "needed", agents
    assert agents.get("status-checker", "not_needed") == "not_needed", agents


def test_flow_change_gate_names_architect_review_not_status_checker():
    # covers: ACD-400b-1
    # angle: real_artifact
    """AC-1: the config/contract_boundary flow-change gate names architect-review."""
    gates = _load_gates()
    entries = [
        e
        for e in gates.get("flow_change_gates") or []
        if e.get("change_target") == "config" and e.get("risk_surface") == "contract_boundary"
    ]
    assert len(entries) == 1, entries
    entry = entries[0]
    assert entry["mandatory_agents"] == ["architect-review", "pr-reviewer"], entry
    assert "status-checker" not in entry["phase_constraint"], entry["phase_constraint"]
