"""
MODULE: unit_tests/agents/test_acd_2500f_1_i.py
COVERS: ACD-2500f-1-i
GOAL: Red-first specification of ticket 11: the profile consistency check
    (scripts/build_phases_profile_consistency.py, ACD-2500e-1-i) gains ONE more rule. An agent
    whose profile declares a change surface in the requirement store (docs/acceptance-criteria/)
    but produces something other than "requirement_records" is listed, naming the agent, the
    surface and the declared produces value. Each mismatch is reported by exactly one rule.
DESIGN: no second checker; "changes the requirement store" comes from a declared `mutates`
    surface, never from the Write/Edit tools; no agent list is hard-coded; warning first
    (ADR-026), so a listed agent never changes an exit code.
INTERPRETATIONS PINNED HERE (the AC leaves them open): which rule listed an agent is read from
    the CLI report, one line per finding. The new rule's line names the agent, the surface
    (it contains "docs/acceptance-criteria/") and the produces value; the existing rule's line
    keeps its "mutates: none" wording. `check_profiles` keeps its (flagged, examined, errors)
    shape; a flagged item may be an id or a dict carrying the id.
HONEST LIMIT: fixtures are built with the real serializers (yaml.safe_dump, json.dumps); the
    tests prove the check's decisions and its wiring, not that the build prints them.
RED STATE: the new rule does not exist, so fixture-req-writer is not listed (an assertion red),
    and on the real registry test-designer is listed by nothing yet but product-owner and
    business-analyst are listed by the existing rule (an assertion red until ACD-2500f-1).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
CLI = SCRIPTS / "build_phases_profile_consistency.py"
STORE = "docs/acceptance-criteria/"
WRITER, READER = "fixture-req-writer", "fixture-reader"
REQUIREMENT_WRITERS = ("it-po", "product-owner", "business-analyst", "test-designer")
_BOILERPLATE_LISTS = ("behavioral_patterns", "pre_flight_reads", "inputs", "outputs")
WRITE_TOOLS = "Read, Write, Edit, Bash"
READ_ONLY_TOOLS = "Read, Grep, Glob, Bash"
NONE_MUTATES = [{"name": "none", "surface": "none", "description": "Read-only agent"}]
STORE_MUTATES = [{
    "name": "requirement_records",
    "surface": "AC YAML store (docs/acceptance-criteria/)",
    "description": "Edits the criteria of a requirement record",
}]
# The business-analyst profile as it stood BEFORE ACD-2500f-1 (frozen copy, not a git lookup).
PRE_FIX_BA = {
    "name": "business-analyst",
    "tools": "Read, Write, Edit, Bash, Skill, Agent",
    "mutates": NONE_MUTATES,
    "produces": "analysis",
    "description": "Business Analyst, L2/L3 behavioral decomposition agent",
}

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _env() -> dict:
    return {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def _profile(agent_id: str, tools: str, mutates: list[dict], produces: str = "analysis") -> dict:
    front = {"name": agent_id, "tools": tools, "mutates": mutates, "produces": produces}
    front["description"] = f"{agent_id} fixture agent"
    front.update({field: [] for field in _BOILERPLATE_LISTS})
    return front


def _package(tmp_path: Path, profiles: list[dict]) -> Path:
    """A tmp package like test_acd_2500e_1_i.py's: templates via yaml.safe_dump, registry via
    json.dumps. The registry entry carries the profile's own produces value."""
    root = tmp_path / "pkg"
    (root / "templates" / "agents").mkdir(parents=True)
    (root / "config").mkdir()
    entries = []
    for profile in profiles:
        agent_id = profile["name"]
        front = yaml.safe_dump(profile, sort_keys=False)
        (root / "templates" / "agents" / f"{agent_id}.md").write_text(
            f"---\n{front}---\n\nYou are {agent_id}.\n", encoding="utf-8")
        entry = {"id": agent_id, "template_path": f"templates/agents/{agent_id}.md", "portable": True}
        entry.update({"category": "planning", "produces": profile["produces"],
                      "description": profile["description"], "skills_invoked": [], "knowledge_channels": []})
        entries.append(entry)
    registry = {"self_description_enforcement": "warning", "agents": entries}
    (root / "config" / "agent_registry.json").write_text(json.dumps(registry, indent=2), encoding="utf-8")
    return root


def _check(registry: Path, package_root: Path):
    import build_phases_profile_consistency as check

    return check.check_profiles(registry, package_root)


def _names(flagged) -> list[str]:
    return [item if isinstance(item, str) else item.get("id") or item.get("agent") for item in flagged]


def _cli(registry: Path, templates: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), "--registry", str(registry), "--templates", str(templates)],
        capture_output=True, text=True, encoding="utf-8", timeout=180, env=_env(), cwd=str(REPO),
    )


def _cli_pkg(root: Path) -> subprocess.CompletedProcess:
    return _cli(root / "config" / "agent_registry.json", root / "templates" / "agents")


def _lines_naming(stdout: str, agent_id: str) -> list[str]:
    """Report lines (header excluded) naming `agent_id` as a whole token."""
    token = re.compile(rf"(?<![\w-]){re.escape(agent_id)}(?![\w-])")
    return [line for line in stdout.splitlines()[1:] if token.search(line)]


def _is_store_rule_line(line: str) -> bool:
    return STORE in line


# --------------------------------------------------------------------------
# the new rule lists a requirement-store writer that declares another produces value
# --------------------------------------------------------------------------
def test_requirement_store_writer_declaring_analysis_listed(tmp_path):
    # covers: ACD-2500f-1-i
    # angle: criterion
    """fixture-req-writer (mutates surface under docs/acceptance-criteria/, produces analysis) is
    listed by the new rule: check_profiles lists it exactly once, and the report's one line for
    it names the agent, the requirement-store surface and "analysis" (not the existing rule's
    "mutates: none" wording)."""
    root = _package(tmp_path, [_profile(WRITER, WRITE_TOOLS, STORE_MUTATES)])
    flagged, examined, errors = _check(root / "config" / "agent_registry.json", root)
    assert errors == []
    assert examined == 1
    assert _names(flagged) == [WRITER], flagged

    proc = _cli_pkg(root)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    lines = _lines_naming(proc.stdout, WRITER)
    assert len(lines) == 1, proc.stdout
    assert _is_store_rule_line(lines[0]), f"the listing does not name the store surface: {lines[0]}"
    assert "analysis" in lines[0], f"the listing does not name the declared produces: {lines[0]}"
    assert "mutates: none" not in lines[0], lines[0]


def test_reader_declaring_no_change_not_listed(tmp_path):
    # covers: ACD-2500f-1-i
    # angle: boundary
    """fixture-reader (read-only tools, mutates none, produces analysis) is listed by neither rule.
    Control in the same package: fixture-req-writer IS listed, so the check ran and the new rule
    is live (a dead rule would pass the negative row for the wrong reason)."""
    root = _package(tmp_path, [
        _profile(READER, READ_ONLY_TOOLS, NONE_MUTATES),
        _profile(WRITER, WRITE_TOOLS, STORE_MUTATES),
    ])
    flagged, examined, errors = _check(root / "config" / "agent_registry.json", root)
    assert errors == []
    assert examined == 2
    assert _names(flagged) == [WRITER], flagged

    proc = _cli_pkg(root)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert _lines_naming(proc.stdout, READER) == [], proc.stdout
    assert len(_lines_naming(proc.stdout, WRITER)) == 1, proc.stdout


def test_real_requirement_writers_not_listed():
    # covers: ACD-2500f-1-i
    # angle: criterion
    """check_profiles on the REAL config/agent_registry.json and templates: none of it-po,
    product-owner, business-analyst, test-designer is listed by either rule, in the returned list
    or in the CLI report. Red until ACD-2500f-1 is done (product-owner and business-analyst still
    declare mutates none; test-designer writes the store yet produces analysis)."""
    registry = REPO / "config" / "agent_registry.json"
    flagged, _, errors = _check(registry, REPO)
    assert errors == []
    listed = [agent for agent in REQUIREMENT_WRITERS if agent in _names(flagged)]
    assert listed == [], f"requirement writers still listed: {listed}"

    proc = _cli(registry, REPO / "templates" / "agents")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    in_report = {agent: _lines_naming(proc.stdout, agent) for agent in REQUIREMENT_WRITERS}
    assert all(lines == [] for lines in in_report.values()), in_report


def test_pre_fix_business_analyst_reported_once_by_existing_rule(tmp_path):
    # covers: ACD-2500f-1-i
    # angle: discrimination
    """The frozen pre-ACD-2500f-1 business-analyst profile (Write/Edit tools, mutates none,
    produces analysis) is reported exactly ONCE, by the ACD-2500e-1-i rule ("mutates: none"
    line), and not by the new rule. Control in the same package: fixture-req-writer is listed by
    the new rule, so "not by the new rule" is not a dead rule's silence.
    Wrong versions this catches: (a) a new rule that also fires on mutates none -> two lines;
    (b) a new rule that reads "changes the store" from Write/Edit tools -> two lines;
    (c) a hard-coded list of the four requirement writers -> business-analyst gets a second
    line, and the made-up fixture-req-writer (in no such list) is not listed."""
    root = _package(tmp_path, [PRE_FIX_BA | {f: [] for f in _BOILERPLATE_LISTS},
                               _profile(WRITER, WRITE_TOOLS, STORE_MUTATES)])
    flagged, examined, errors = _check(root / "config" / "agent_registry.json", root)
    assert errors == []
    assert examined == 2
    assert _names(flagged).count("business-analyst") == 1, flagged
    assert _names(flagged).count(WRITER) == 1, flagged

    proc = _cli_pkg(root)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    ba_lines = _lines_naming(proc.stdout, "business-analyst")
    assert len(ba_lines) == 1, f"reported {len(ba_lines)} times: {proc.stdout}"
    assert "mutates: none" in ba_lines[0] and not _is_store_rule_line(ba_lines[0]), ba_lines[0]
    writer_lines = _lines_naming(proc.stdout, WRITER)
    assert len(writer_lines) == 1 and _is_store_rule_line(writer_lines[0]), proc.stdout


# --------------------------------------------------------------------------
# reachability: the CLI and the build's own validation function
# --------------------------------------------------------------------------
_RUN_VALIDATION = (
    "import json, sys\n"
    "from pathlib import Path\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "import build_phases_agent_validation as v\n"
    "result = v.validate_agent_self_description(\n"
    "    Path(sys.argv[2]), {}, False, sys.argv[3], package_root=Path(sys.argv[2]))\n"
    "print('RESULT ' + json.dumps(list(result)))\n"
)


def _validation_result(root: Path, level: str) -> list[int]:
    proc = subprocess.run(
        [sys.executable, "-c", _RUN_VALIDATION, str(SCRIPTS), str(root), level],
        capture_output=True, text=True, encoding="utf-8", timeout=120, env=_env(), cwd=str(REPO),
    )
    line = next((ln for ln in proc.stdout.splitlines() if ln.startswith("RESULT ")), None)
    assert line, proc.stdout + proc.stderr
    return json.loads(line[len("RESULT "):])


@pytest.mark.parametrize("level", ["warning", "error"])
def test_profile_rule_reachable_from_cli_and_build_validation(tmp_path, level):
    # covers: ACD-2500f-1-i
    # angle: reachability
    """Entry points resolved: (a) build_phases_profile_consistency.py as a subprocess lists
    fixture-req-writer and exits 0 (warning first, ADR-026); (b) validate_agent_self_description
    in a fresh interpreter on two packages differing ONLY in fixture-req-writer's produces
    (requirement_records vs analysis, in template and registry alike): the warning count rises
    by exactly one and the error count does not, in the build's warning and error modes. Never
    spawns build.py."""
    honest = _package(tmp_path / "honest",
                      [_profile(WRITER, WRITE_TOOLS, STORE_MUTATES, produces="requirement_records")])
    drifted = _package(tmp_path / "drifted", [_profile(WRITER, WRITE_TOOLS, STORE_MUTATES)])
    before, after = _validation_result(honest, level), _validation_result(drifted, level)
    assert before == [0, 0], f"fixture package is not clean: {before}"
    assert after[0] == before[0], f"a profile finding became an error: {before} -> {after}"
    assert after[1] == before[1] + 1, f"the warning count did not rise by one: {before} -> {after}"

    proc = _cli_pkg(drifted)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert len(_lines_naming(proc.stdout, WRITER)) == 1, proc.stdout
