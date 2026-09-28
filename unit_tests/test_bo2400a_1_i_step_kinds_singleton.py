"""
MODULE: unit_tests/test_bo2400a_1_i_step_kinds_singleton.py
GOAL: RED failing test for BO-2400a-1-i's clause "no agent entry other than
      the command-step-runner's gains step_kinds in this change" -- in the
      shipped config/agent_registry.json, exactly one entry may carry
      step_kinds, and it must be command-step-runner.
TICKET: none (hand-driven build; AC YAML is the spec) -- see
    docs/acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-2400a-1-i.yaml

Placed directly under unit_tests/ (not unit_tests/build_orchestration/) per
the AC's own test_spec target_dir for this specific test entry -- this
repository already has loose top-level test files under unit_tests/ (e.g.
test_agent_registry_legacy_flags.py, test_registry_no_version_suffix.py), so
this is an existing, not a new, convention.

ASSUMED PRODUCTION API: config/agent_registry.json gains exactly one entry
with a 'step_kinds' key -- the new command-step-runner entry. No existing
entry's step_kinds is touched (none has one today).

RED BASELINE (empirically confirmed against today's worktree): zero entries
in the shipped registry currently carry a 'step_kinds' key at all, so the
"exactly one, and it is command-step-runner" assertion fails on the count
(0, expected 1) before command-step-runner is even in the picture.
"""
# covers: BO-2400a-1-i

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
_REGISTRY_PATH = REPO_ROOT / "config" / "agent_registry.json"
_AGENT_ID = "command-step-runner"


def _load_registry_agents() -> list[dict[str, Any]]:
    """Load the real, shipped agents list from config/agent_registry.json."""
    raw = yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8"))
    return raw["agents"]


def test_only_the_command_step_runner_declares_step_kinds():
    # covers: BO-2400a-1-i
    # angle: real_artifact
    """In the shipped config/agent_registry.json exactly one entry carries
    step_kinds, and it is command-step-runner."""
    agents = _load_registry_agents()
    entries_with_step_kinds = [
        agent.get("id") for agent in agents if "step_kinds" in agent
    ]

    assert len(entries_with_step_kinds) == 1, (
        "Exactly one registry entry must carry a 'step_kinds' key; found "
        f"{len(entries_with_step_kinds)}: {entries_with_step_kinds!r}. No "
        f"agent other than '{_AGENT_ID}' may gain step_kinds in this change."
    )
    assert entries_with_step_kinds[0] == _AGENT_ID, (
        "The one entry carrying step_kinds must be "
        f"'{_AGENT_ID}'; found {entries_with_step_kinds[0]!r} instead."
    )
