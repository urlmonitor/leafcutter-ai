"""
MODULE: unit_tests/evals/test_inf_800f_1.py
COVERS: INF-800f-1 arms 2 and 3 -- the restructuring specialist applies
    complexity-reduction when the demand is about complexity, and does not on a
    file-size demand.

GOAL: Arms 2 and 3 are model behaviour, so a unit test cannot prove them. What it
    CAN prove, offline and deterministically, is that the eval rows exist, that they
    carry the right demand, and that the harness's own scoring REJECTS a report that
    gets the skill wrong in either direction. A live run needs model credentials that
    CI does not hold (the informational gate).

EVAL CONTRACT the coder must satisfy (label mode, so the existing harness runs it):
  scripts/evals/agent_eval_config.json  agents["restructuring-specialist"]:
      template            templates/agents/restructuring-specialist.md
      eval_set            <path to a jsonl the coder creates>
      scoring_mode        "label"
      input_field         names the row field carrying the demand text
      expected_field      "expected" (a dict keyed by skill id -> bool)
      label_axes          contains "complexity-reduction"
      response_label_field "skills_applied": the report's machine-readable
                          skills-applied object, a mapping of skill id -> bool
      triggers            the agent's own files only (owner decision 2026-10-06)
  Eval rows (at least):
      complexity row  demand text names scripts/planner.py, plan_batches, complexity 31,
                      30 allowed;           expected["complexity-reduction"] is True
      file-size row   demand text names a file-size demand of 120 measured lines to
                      leave scripts/planner.py; expected["complexity-reduction"] is False

MUST-CATCH (named mutation 2, THE ALWAYS-ON SKILL): complexity-reduction loaded on
    every engagement. Modelled below as a report claiming complexity-reduction on the
    file-size row; the harness scoring must reject it, while the same report on the
    complexity row (the control) must pass.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EVALS_DIR = _REPO_ROOT / "scripts" / "evals"
sys.path.insert(0, str(_EVALS_DIR))
import eval_selector  # noqa: E402
import run_agent_eval  # noqa: E402

_AGENT = "restructuring-specialist"
_SKILL = "complexity-reduction"


def _cfg() -> dict[str, Any]:
    """Return the agent's eval config block, asserting it exists."""
    config = json.loads((_EVALS_DIR / "agent_eval_config.json").read_text(encoding="utf-8"))
    block = config["agents"].get(_AGENT)
    assert block is not None, f"{_AGENT} is not registered in agent_eval_config.json"
    return block


def _rows(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Load the agent's real eval rows through the harness's own loader."""
    return run_agent_eval.load_eval_rows(_REPO_ROOT / cfg["eval_set"])


def _demand(row: dict[str, Any], cfg: dict[str, Any]) -> str:
    return str(row.get(cfg["input_field"], ""))


def _complexity_row(cfg: dict[str, Any]) -> dict[str, Any]:
    matches = [
        r
        for r in _rows(cfg)
        if all(tok in _demand(r, cfg) for tok in ("scripts/planner.py", "plan_batches", "31", "30"))
    ]
    assert len(matches) == 1, f"expected exactly 1 complexity row, found {len(matches)}"
    return matches[0]


def _size_row(cfg: dict[str, Any]) -> dict[str, Any]:
    matches = [
        r
        for r in _rows(cfg)
        if "120" in _demand(r, cfg)
        and "scripts/planner.py" in _demand(r, cfg)
        and "plan_batches" not in _demand(r, cfg)
    ]
    assert len(matches) == 1, f"expected exactly 1 file-size row, found {len(matches)}"
    return matches[0]


def _score(report: dict[str, Any], row: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    """Score a model report against a row exactly as run_label_eval does."""
    predicted = run_agent_eval._extract_labels(report, cfg.get("response_label_field"))
    return run_agent_eval.score_label_row(predicted, row[cfg["expected_field"]], cfg["label_axes"])


def test_inf800f1_eval_is_registered_in_label_mode_reading_the_skills_applied_field() -> None:
    # covers: INF-800f-1
    # angle: criterion
    """The agent is a real eval target: label mode, scoring the skills-applied field."""
    cfg = _cfg()
    assert cfg["scoring_mode"] == "label"
    assert cfg["template"] == "templates/agents/restructuring-specialist.md"
    assert (_REPO_ROOT / cfg["template"]).is_file()
    assert _SKILL in cfg["label_axes"]
    assert cfg["response_label_field"] == "skills_applied"
    assert (_REPO_ROOT / cfg["eval_set"]).is_file()


def test_inf800f1_eval_complexity_demand_reports_complexity_reduction() -> None:
    # covers: INF-800f-1
    # angle: criterion
    """AC-4: the complexity row expects complexity-reduction, and scoring rejects its absence."""
    cfg = _cfg()
    row = _complexity_row(cfg)
    assert row[cfg["expected_field"]][_SKILL] is True

    applied = {"skills_applied": {_SKILL: True}}
    not_applied = {"skills_applied": {_SKILL: False}}
    assert _score(applied, row, cfg)["passed"] is True
    assert _score(not_applied, row, cfg)["passed"] is False


def test_inf800f1_eval_file_size_demand_does_not_report_complexity_reduction() -> None:
    # covers: INF-800f-1
    # angle: discrimination
    """AC-5: the file-size row expects no complexity-reduction; the always-on skill is rejected."""
    cfg = _cfg()
    row = _size_row(cfg)
    assert row[cfg["expected_field"]][_SKILL] is False

    always_on = {"skills_applied": {_SKILL: True}}  # THE ALWAYS-ON SKILL
    demand_chosen = {"skills_applied": {_SKILL: False}}
    assert _score(always_on, row, cfg)["passed"] is False
    assert _score(demand_chosen, row, cfg)["passed"] is True

    # Control (Q3): the identical always-on report PASSES on the complexity row, so the
    # size-row rejection is caused by the demand, not by the report being malformed.
    assert _score(always_on, _complexity_row(cfg), cfg)["passed"] is True


def test_inf800f1_self_test_scores_every_real_row_through_the_harness() -> None:
    # covers: INF-800f-1
    # angle: seam
    """Pipe the REAL eval rows into the REAL run_label_eval scorer (no model call)."""
    cfg = _cfg()
    rows = _rows(cfg)
    results = run_agent_eval.run_label_eval(
        rows,
        "",
        cfg,
        self_test=True,
        timeout=1,
        backend="cli",
    )
    assert len(results) == len(rows)
    assert len(results) >= 2
    assert all(r["score"]["passed"] for r in results)
    flags = sorted(r["predicted"][_SKILL] for r in results)
    assert flags[0] is False and flags[-1] is True, "rows must cover both skill outcomes"


@pytest.mark.parametrize(
    ("changed", "affects"),
    [
        ("templates/agents/restructuring-specialist.md", True),
        ("scripts/evals/run_agent_eval.py", True),
        ("config/ac_store_schema.json", False),
        ("docs/acceptance-criteria/infrastructure/INF-800-safe-restructuring/INF-800f-1.yaml", False),
        ("kernel/adapters/claude_code/install.py", False),
    ],
)
def test_inf800f1_triggers_are_limited_to_the_agents_own_files(changed: str, affects: bool) -> None:
    # covers: INF-800f-1
    # angle: boundary
    """Owner decision 2026-10-06: only the agent's own files trigger its eval."""
    config = eval_selector.load_config(_EVALS_DIR / "agent_eval_config.json")
    triggers = eval_selector.agent_triggers(config)
    assert _AGENT in triggers, f"{_AGENT} has no triggers"
    split = eval_selector.compute_affected([changed], triggers)
    assert (_AGENT in split["affected"]) is affects
