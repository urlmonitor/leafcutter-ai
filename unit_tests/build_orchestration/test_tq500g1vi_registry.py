"""
MODULE: unit_tests/build_orchestration/test_tq500g1vi_registry.py
GOAL: RED test for TQ-500g-1-vi, the registry edit that lets the two heavy-lane twins dispatch the shell
    executor: command-step-runner's spawned_by names build-feature.js and build-ticket.js, its generated card
    mirrors the registry, and the registry validator's spawn checks pass.
BUSINESS CONTEXT: Reads the REAL config/agent_registry.json and docs/agents/cards/command-step-runner.card.md and
    runs the REAL validators (scripts/registry_validator.py and the check-agent-spawn-consistency hook's own
    functions). Today spawned_by lists only "user" and "fast-lane-ship.js", so the test fails on an assertion.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
AGENT = "command-step-runner"
WANT = ["user", "fast-lane-ship.js", "build-feature.js", "build-ticket.js"]
HOOK = REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "hooks" / "check_agent_spawn_consistency.py"
CARD = REPO_ROOT / "docs" / "agents" / "cards" / f"{AGENT}.card.md"


def _registry() -> list[dict]:
    return json.loads((REPO_ROOT / "config" / "agent_registry.json").read_text(encoding="utf-8"))["agents"]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _card_spawned_by() -> list[str]:
    text = CARD.read_text(encoding="utf-8")
    section = text.split("### Spawned By", 1)[1].split("---", 1)[0]
    return re.findall(r"^- `([^`]+)`", section, re.MULTILINE)


def test_command_step_runner_spawned_by_names_both_routes():
    # covers: TQ-500g-1-vi
    # angle: real_artifact
    agents = _registry()
    entry = next(a for a in agents if a["id"] == AGENT)
    assert entry["spawned_by"] == WANT, f"spawned_by is {entry['spawned_by']}, wanted {WANT}"
    assert entry["permits_shell"] is True and entry["spawn_allowlist"] == [], "no other field of the entry changes"
    assert sum(1 for a in agents if a["id"] == AGENT) == 1, "no new registry entry"
    assert _card_spawned_by() == WANT, f"the card's Spawned By list is {_card_spawned_by()}, wanted {WANT}"
    diagram = CARD.read_text(encoding="utf-8").split("```mermaid", 1)[1].split("```", 1)[0]
    for name in ("build-feature.js", "build-ticket.js"):
        assert re.search(rf'\["{re.escape(name)}\\n', diagram), f"the spawn diagram shows no node for {name}"
    assert len(re.findall(r"-->\|dispatches\| command_step_runner", diagram)) == len(WANT), "one dispatch edge per caller"
    # the validators accept the callers: the registry validator and the spawn-consistency hook's card mirror check
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    errors = _load("tq500g1vi_registry_validator", REPO_ROOT / "scripts" / "registry_validator.py").validate_agent_registry(REPO_ROOT)
    assert not [e for e in errors if AGENT in e], f"registry validator: {[e for e in errors if AGENT in e]}"
    hook = _load("tq500g1vi_spawn_hook", HOOK)
    scoped = [a for a in agents if a["id"] == AGENT]
    mirror = hook._check_card_registry_mirror(scoped, REPO_ROOT / "docs" / "agents" / "cards", REPO_ROOT)
    assert mirror == [], f"card/registry mirror: {mirror}"
    asymmetric = hook._check_asymmetric_spawns(agents, REPO_ROOT)
    assert not [e for e in asymmetric if AGENT in e], f"asymmetric spawns: {asymmetric}"
    notes = (REPO_ROOT / "templates" / "agents" / f"{AGENT}.md").read_text(encoding="utf-8")
    assert "build-feature.js" in notes and "build-ticket.js" in notes, "the executor template's adopter_notes still name only the fast lane"
