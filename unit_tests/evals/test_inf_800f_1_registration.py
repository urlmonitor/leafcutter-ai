"""
MODULE: unit_tests/evals/test_inf_800f_1_registration.py
COVERS: INF-800f-1 -- a restructuring specialist exists as an agent a run can bring in,
    separate from every coder.

GOAL: Prove, over the REAL registry, the REAL template and the DEPLOYED layout, that
    ``restructuring-specialist`` is registered as its own party (role not coding, own
    template, no coder resolving to it). The "ordered record of parties engaged" half
    of arm 1 belongs to BO-3800b-3's driver-harness tests: no run can engage the agent
    until that ticket wires the driver.

MUST-CATCH (named mutation 1, THE RENAMED CODER): the specialist registered as an
    alias that resolves to python-coder. Every distinctness assertion below goes red
    under it (id, role, template_path and template bytes are all compared with every
    coder).

IMPLEMENTATION CONTRACT the coder must satisfy:
  - config/agent_registry.json agents[] gains id ``restructuring-specialist`` with
    role ``restructuring``, tier ``phase``, portable true, spawn_allowlist [],
    is_ticket_phase true, components ["infrastructure"], template_path
    ``templates/agents/restructuring-specialist.md``, skills_invoked listing
    ``signoff`` (always) and ``complexity-reduction`` (conditional).
  - templates/agents/restructuring-specialist.md has frontmatter name equal to the id,
    tools Read/Edit/Write/Bash plus Skill (AR-300; no Agent), ``signoff: true`` and
    ``requires_verification: true``.
  - scripts/evals/agent_eval_config.json registers the agent in label mode so that
    ``python scripts/evals/run_agent_eval.py --agent restructuring-specialist
    --self-test`` is a real, passing run (see unit_tests/evals/test_inf_800f_1.py).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REGISTRY = _REPO_ROOT / "config" / "agent_registry.json"
_AGENT_ID = "restructuring-specialist"
_TEMPLATE_REL = "templates/agents/restructuring-specialist.md"


def _agents() -> list[dict[str, Any]]:
    """Return agents[] from the real registry file."""
    return json.loads(_REGISTRY.read_text(encoding="utf-8"))["agents"]


def _entry() -> dict[str, Any] | None:
    """Return the specialist's registry entry, or None when absent."""
    for agent in _agents():
        if agent.get("id") == _AGENT_ID:
            return agent
    return None


def _coders() -> list[dict[str, Any]]:
    """Return every registry entry whose role is coding."""
    return [a for a in _agents() if a.get("role") == "coding"]


def _frontmatter(path: Path) -> dict[str, Any]:
    """Parse the YAML frontmatter of an agent template."""
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---"), f"{path} has no frontmatter"
    return yaml.safe_load(text.split("---", 2)[1])


def _require_entry() -> dict[str, Any]:
    """Fail with an assertion (not a lookup error) when the specialist is unregistered."""
    entry = _entry()
    assert entry is not None, f"{_AGENT_ID} is not in config/agent_registry.json agents[]"
    return entry


def test_inf800f1_restructuring_specialist_is_registered_and_distinct_from_every_coder() -> None:
    # covers: INF-800f-1
    # angle: deployed
    """AC-2/AC-3: registered under its own id, and a different party from every coder."""
    entry = _require_entry()
    coders = _coders()
    assert coders, "control: the registry must hold coder entries to compare against"
    assert "python-coder" in {c["id"] for c in coders}

    assert entry["role"] == "restructuring"
    assert entry["role"] != "coding"
    assert entry["id"] not in {c["id"] for c in coders}
    assert entry["template_path"] == _TEMPLATE_REL
    assert entry["template_path"] not in {c.get("template_path") for c in coders}
    # No scalar field of the entry may be a coder's id or point at a coder template
    # (an alias such as {"resolves_to": "python-coder"} is the renamed coder).
    coder_ids = {c["id"] for c in coders}
    coder_templates = {c.get("template_path") for c in coders}
    for key, value in entry.items():
        if isinstance(value, str):
            assert value not in coder_ids, f"field {key!r} resolves to coder {value!r}"
            assert value not in coder_templates, f"field {key!r} points at a coder template"

    assert entry["tier"] == "phase"
    assert entry["portable"] is True
    assert entry["spawn_allowlist"] == []
    assert entry["is_ticket_phase"] is True
    assert entry["components"] == ["infrastructure"]
    invoked = {s["skill_id"]: s["mode"] for s in entry["skills_invoked"]}
    assert invoked.get("signoff") == "always"
    assert invoked.get("complexity-reduction") == "conditional"

    # Exactly one entry carries the id (no duplicate shadowing).
    assert [a["id"] for a in _agents()].count(_AGENT_ID) == 1


def test_inf800f1_template_is_its_own_verified_signing_off_non_spawning_file() -> None:
    # covers: INF-800f-1
    # angle: criterion
    """The template is its own file: Edit+Write present so requires_verification is true."""
    entry = _require_entry()
    template = _REPO_ROOT / entry["template_path"]
    assert template.is_file(), f"{template} does not exist"
    coder_template = _REPO_ROOT / "templates" / "agents" / "python-coder.md"
    assert template.read_bytes() != coder_template.read_bytes(), "template is a copy of python-coder"

    fm = _frontmatter(template)
    assert fm["name"] == _AGENT_ID
    tools = {t.strip() for t in str(fm["tools"]).split(",")}
    # AR-300: a non-empty skill grant requires the Skill tool; Agent stays absent (it spawns nobody).
    assert tools == {"Read", "Edit", "Write", "Bash", "Skill"}
    assert "Agent" not in tools
    assert fm["requires_verification"] is True
    assert fm["signoff"] is True


@pytest.mark.shared_layout_reader
def test_inf800f1_deployed_layout_carries_a_distinct_specialist_agent(
    shared_reference_layout: Path,
) -> None:
    # covers: INF-800f-1
    # angle: deployed
    """The DEPLOYED .claude/agents copy exists and is not python-coder under another name."""
    deployed = shared_reference_layout / ".claude" / "agents" / f"{_AGENT_ID}.md"
    assert deployed.is_file(), f"{deployed} missing from the deployed layout"
    coder = shared_reference_layout / ".claude" / "agents" / "python-coder.md"
    assert coder.is_file(), "control: python-coder must be deployed too"
    assert deployed.read_bytes() != coder.read_bytes()
    assert _frontmatter(deployed)["name"] == _AGENT_ID


def test_inf_800f_1_reachable_from_entry_point(tmp_path: Path) -> None:
    # covers: INF-800f-1
    # angle: reachability
    """Entry point: the eval runner CLI (subprocess, --self-test, no model call).

    Resolved entry point: ``python scripts/evals/run_agent_eval.py --agent
    restructuring-specialist --self-test``. Today the agent is not configured, so the
    CLI exits 2 ("Unknown agent"). Once configured, the run loads the real template and
    the real eval set and scores every row; at least the complexity row and the
    file-size row must be scored, and its exit code is consumed as the gate.
    """
    results = tmp_path / "results.json"
    proc = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "scripts" / "evals" / "run_agent_eval.py"),
            "--agent",
            _AGENT_ID,
            "--self-test",
            "--results-file",
            str(results),
        ],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        cwd=str(_REPO_ROOT),
    )
    assert proc.returncode == 0, f"eval CLI failed:\n{proc.stdout}\n{proc.stderr}"
    payload = json.loads(results.read_text(encoding="utf-8"))
    assert payload["agent"] == _AGENT_ID
    assert payload["mode"] == "label"
    assert payload["aggregate"]["rows"] >= 2
    assert payload["aggregate"]["passed"] == payload["aggregate"]["rows"]
