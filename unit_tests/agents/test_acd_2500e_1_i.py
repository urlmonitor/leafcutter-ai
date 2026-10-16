"""
MODULE: unit_tests/agents/test_acd_2500e_1_i.py
COVERS: ACD-2500e-1-i
GOAL: Red-first specification of ticket 42 (G5): an advisory profile-consistency check lists every
    agent whose tools can write or edit files while its profile declares it changes nothing. It
    makes ACD-2500e-1 durable: without it the next profile drifts the same way the it-po profile did.
DESIGN (G5 architect note, D5): a new module scripts/build_phases_profile_consistency.py with
    `check_profiles(registry, package_root) -> (flagged, examined, errors)` and a `main()` CLI
    (`--registry <agent_registry.json> --templates <templates/agents dir>`), called once at the
    tail of build_phases_agent_validation.validate_agent_self_description. "Writes or edits" is
    derived from the template frontmatter `tools:` (Write, Edit, NotebookEdit); "changes nothing"
    from `mutates` entries ALL named `none`; no agent list is hard-coded. Severity is a module
    constant `warning` (ADR-026 warn-before-required): a flagged agent never changes an exit
    code. An unreadable registry or template is an error, never "zero flagged".
INTERPRETATIONS PINNED HERE (the AC leaves them open): `registry` is the PATH of the registry json
    (an unreadable registry has to be detectable inside the function); `package_root` is the package
    root that registry `template_path` entries resolve against; `--templates` is the agents template
    directory (templates/agents); `flagged` is a list of agent ids; the report says `examined N`.
HONEST LIMIT: these tests prove the check's decisions on fixtures built with the real serializers
    (yaml.safe_dump, json.dumps) and its wiring; they cannot prove the build prints the report.
RED STATE: the module does not exist, so its tests fail with ModuleNotFoundError or a failed
    subprocess (an absence red); the wiring test calls the existing function and fails on its
    assertion (the warning count does not rise).
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
MADE_UP_ID = "zz-fixture-agent-9f3a"  # in no registry: a hard-coded agent list cannot know it
_BOILERPLATE_LISTS = ("behavioral_patterns", "pre_flight_reads", "inputs", "outputs")
WRITE_TOOLS = "Read, Write, Bash"
READ_ONLY_TOOLS = "Read, Grep, Glob, Bash"
NONE_MUTATES = [{"name": "none", "surface": "none", "description": "Read-only agent"}]
STORE_MUTATES = [{
    "name": "requirement_records",
    "surface": "AC YAML store (docs/acceptance-criteria/)",
    "description": "Edits the technical fields of a requirement record",
}]
# The it-po profile as it stood BEFORE ACD-2500e-1 (frozen copy, not a git lookup): write-capable
# tools, `mutates: none`, `produces: analysis`.
PRE_FIX_IT_PO = {
    "name": "it-po",
    "tools": "Read, Write, Edit, Bash, Skill",
    "mutates": NONE_MUTATES,
    "produces": "analysis",
    "description": "IT Product Owner, technical enrichment agent",
}

if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def _env() -> dict:
    return {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def _profile(agent_id: str, tools: str, mutates: list[dict]) -> dict:
    """One agent's frontmatter: the profile fields under test plus the self-description boilerplate."""
    front = {"name": agent_id, "tools": tools, "mutates": mutates, "produces": "analysis"}
    front["description"] = f"{agent_id} fixture agent"
    front.update({field: [] for field in _BOILERPLATE_LISTS})
    return front


def _package(tmp_path: Path, profiles: list[dict], *, registry_text: str | None = None) -> Path:
    """A tmp package: templates written with yaml.safe_dump, registry with json.dumps (the real
    serializers, never hand-typed literals). `registry_text` overrides the registry file."""
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
        entry.update({"category": "planning", "produces": "analysis", "description": profile["description"]})
        entry.update({field: [] for field in ("skills_invoked", "knowledge_channels")})
        entries.append(entry)
    text = registry_text if registry_text is not None else json.dumps(
        {"self_description_enforcement": "warning", "agents": entries}, indent=2)
    (root / "config" / "agent_registry.json").write_text(text, encoding="utf-8")
    return root


def _check(root: Path):
    import build_phases_profile_consistency as check

    return check.check_profiles(root / "config" / "agent_registry.json", root)


def _names(flagged) -> list[str]:
    return [item if isinstance(item, str) else item.get("id") or item.get("agent") for item in flagged]


def _cli(root: Path, registry: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CLI), "--registry", str(registry or root / "config" / "agent_registry.json"),
         "--templates", str(root / "templates" / "agents")],
        capture_output=True, text=True, encoding="utf-8", timeout=120, env=_env(), cwd=str(REPO),
    )


# --------------------------------------------------------------------------
# AC-1: every write-capable agent that declares it changes nothing is listed, by name
# --------------------------------------------------------------------------
@pytest.mark.parametrize("tools", ["Read, Write, Bash", "Read, Edit", "Read, NotebookEdit, Bash"])
def test_write_capable_agent_declaring_no_change_listed(tmp_path, tools):
    # covers: ACD-2500e-1-i
    # angle: criterion
    """An agent whose `tools` include Write, Edit or NotebookEdit and whose mutates is `none` is
    listed by name -- each write tool on its own is enough. Control in the same package: the same
    tools with a mutates entry that names a surface is NOT listed, so the verdict follows the
    mutates declaration, not the tools alone."""
    root = _package(tmp_path, [
        _profile("fx-liar", tools, NONE_MUTATES),
        _profile("fx-honest", tools, STORE_MUTATES),
    ])
    flagged, examined, errors = _check(root)
    assert errors == []
    assert _names(flagged) == ["fx-liar"]
    assert examined == 2


def test_pre_fix_it_po_profile_listed(tmp_path):
    # covers: ACD-2500e-1-i
    # angle: criterion
    """The frozen pre-ACD-2500e-1 it-po profile is listed. Control: the corrected profile (same
    tools, mutates names the requirement store) is not -- the fixture, not the id, decides."""
    root = _package(tmp_path, [PRE_FIX_IT_PO])
    assert _names(_check(root)[0]) == ["it-po"]
    corrected = {**PRE_FIX_IT_PO, "mutates": STORE_MUTATES, "produces": "requirement_records"}
    assert _names(_check(_package(tmp_path / "fixed", [corrected]))[0]) == []


def test_read_only_agent_declaring_no_change_not_listed(tmp_path):
    # covers: ACD-2500e-1-i
    # angle: boundary
    """An agent with read-only tools and mutates `none` is not listed. Boundary rows next to it:
    Bash alone is not a write tool for this check, and a mutates list that mixes `none` with a real
    surface does not declare "changes nothing". The listed agent in the same package proves the
    check ran (a dead check lists nothing)."""
    root = _package(tmp_path, [
        _profile("fx-reader", READ_ONLY_TOOLS, NONE_MUTATES),
        _profile("fx-mixed", WRITE_TOOLS, NONE_MUTATES + STORE_MUTATES),
        _profile("fx-liar", WRITE_TOOLS, NONE_MUTATES),
    ])
    flagged, examined, errors = _check(root)
    assert errors == []
    assert _names(flagged) == ["fx-liar"]
    assert examined == 3


# --------------------------------------------------------------------------
# AC-2 / AC-3: the report states how many were examined; the check warns, never blocks
# --------------------------------------------------------------------------
def test_report_states_agents_examined(tmp_path):
    # covers: ACD-2500e-1-i
    # angle: criterion
    """The count is returned by check_profiles and printed by the CLI as `examined N` -- N is the
    number of agents in the package (4, not the number flagged: 1), so a count of flagged agents
    or a hard-coded number fails."""
    root = _package(tmp_path, [
        _profile("fx-a", READ_ONLY_TOOLS, NONE_MUTATES),
        _profile("fx-b", READ_ONLY_TOOLS, NONE_MUTATES),
        _profile("fx-c", WRITE_TOOLS, STORE_MUTATES),
        _profile("fx-liar", WRITE_TOOLS, NONE_MUTATES),
    ])
    flagged, examined, _ = _check(root)
    assert (len(flagged), examined) == (1, 4)
    proc = _cli(root)
    assert re.search(r"\bexamined\s+4\b", proc.stdout, re.IGNORECASE), proc.stdout + proc.stderr
    assert "fx-liar" in proc.stdout


def test_check_warns_not_blocks(tmp_path):
    # covers: ACD-2500e-1-i
    # angle: seam
    """A flagged agent produces a WARNING and exit code 0 (ADR-026 warn-before-required). The seam:
    the CLI's real output and exit code, and the report names the agent."""
    root = _package(tmp_path, [_profile("fx-liar", WRITE_TOOLS, NONE_MUTATES)])
    proc = _cli(root)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "fx-liar" in proc.stdout
    assert re.search(r"warning", proc.stdout, re.IGNORECASE), proc.stdout


# --------------------------------------------------------------------------
# failure: an unreadable input is an error, never "zero flagged"
# --------------------------------------------------------------------------
def test_unreadable_registry_is_an_error_not_zero_flagged(tmp_path):
    # covers: ACD-2500e-1-i
    # angle: failure
    """A registry that does not parse, and one that is missing, each give a non-empty `errors` and
    a non-zero CLI exit; an agent whose template file is missing is an error naming it. Control: a
    healthy package gives no errors and exit 0 (so non-zero is the input's doing)."""
    healthy = _package(tmp_path / "ok", [_profile("fx-a", READ_ONLY_TOOLS, NONE_MUTATES)])
    assert _check(healthy)[2] == [] and _cli(healthy).returncode == 0

    broken = _package(tmp_path / "bad", [], registry_text="{ this is not json")
    flagged, _, errors = _check(broken)
    assert errors, "an unparseable registry was reported as a clean run"
    assert _cli(broken).returncode != 0

    missing = tmp_path / "bad" / "config" / "absent.json"
    assert _cli(broken, registry=missing).returncode != 0

    orphan = _package(tmp_path / "orphan", [_profile("fx-gone", WRITE_TOOLS, NONE_MUTATES)])
    (orphan / "templates" / "agents" / "fx-gone.md").unlink()
    _, _, errors = _check(orphan)
    assert any("fx-gone" in error for error in errors), errors
    assert _cli(orphan).returncode != 0


# --------------------------------------------------------------------------
# discrimination: no hard-coded agent list
# --------------------------------------------------------------------------
def test_no_agent_list_is_hard_coded(tmp_path):
    # covers: ACD-2500e-1-i
    # angle: discrimination
    """Wrong versions this fails: (a) a built-in list of known offenders -- a made-up id in no
    registry is flagged; (b) a name test on `it-po` -- a READ-ONLY agent called it-po is not
    flagged; (c) a list of known-clean agents -- the made-up id is flagged even when a clean agent
    sits beside it."""
    root = _package(tmp_path, [
        _profile(MADE_UP_ID, WRITE_TOOLS, NONE_MUTATES),
        _profile("it-po", READ_ONLY_TOOLS, NONE_MUTATES),
    ])
    flagged, examined, errors = _check(root)
    assert errors == []
    assert _names(flagged) == [MADE_UP_ID]
    assert examined == 2


# --------------------------------------------------------------------------
# reachability: the CLI, the build's validation function, and the real registry
# --------------------------------------------------------------------------
_RUN_VALIDATION = (
    "import json, sys\n"
    "from pathlib import Path\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "import build_phases_agent_validation as v\n"
    "level = sys.argv[3]\n"
    "result = v.validate_agent_self_description(\n"
    "    Path(sys.argv[2]), {}, False, level, package_root=Path(sys.argv[2]))\n"
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
def test_acd_2500e_1_i_reachable_from_entry_point(tmp_path, level):
    # covers: ACD-2500e-1-i
    # angle: reachability
    """Entry points resolved (Step 1.1 CLI + the build's own validation function):
    (a) `validate_agent_self_description` on two tmp packages that differ ONLY in one agent's
        mutates (store vs `none`), run in a fresh interpreter, in the build's 'warning' mode and in
        'error' mode (config says error today): the warning count rises by exactly 1 and the error
        count stays the same -- the check is advisory even when the self-description gate is
        blocking;
    (b) the CLI as a subprocess prints the flagged agent and exits 0."""
    honest = _package(tmp_path / "honest", [_profile("fx-agent", WRITE_TOOLS, STORE_MUTATES)])
    liar = _package(tmp_path / "liar", [_profile("fx-agent", WRITE_TOOLS, NONE_MUTATES)])
    before, after = _validation_result(honest, level), _validation_result(liar, level)
    assert before == [0, 0], f"fixture package is not self-description clean: {before}"
    assert after[0] == before[0], f"a profile finding became an error: {before} -> {after}"
    assert after[1] == before[1] + 1, f"the warning count did not rise by one: {before} -> {after}"

    proc = _cli(liar)
    assert proc.returncode == 0 and "fx-agent" in proc.stdout, proc.stdout + proc.stderr


def test_real_registry_is_examined_and_the_corrected_it_po_is_not_listed():
    # covers: ACD-2500e-1-i
    # angle: real_artifact
    """Seam with ticket 41: the REAL registry and templates. Every registry agent is examined, the
    run exits 0 and reports `examined N`, and it-po -- whose profile ticket 41 corrects -- is not
    listed. (Day-one figure from the architect note: 61 examined, 17 listed after ticket 41; the
    exact listed set is data and is recorded in the ticket, not pinned here.)"""
    agents = json.loads((REPO / "config" / "agent_registry.json").read_text(encoding="utf-8"))["agents"]
    import build_phases_profile_consistency as check

    flagged, examined, errors = check.check_profiles(REPO / "config" / "agent_registry.json", REPO)
    assert errors == []
    assert examined == len(agents)
    assert "it-po" not in _names(flagged)
    proc = subprocess.run(
        [sys.executable, str(CLI), "--registry", str(REPO / "config" / "agent_registry.json"),
         "--templates", str(REPO / "templates" / "agents")],
        capture_output=True, text=True, encoding="utf-8", timeout=180, env=_env(), cwd=str(REPO),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert re.search(rf"\bexamined\s+{len(agents)}\b", proc.stdout, re.IGNORECASE), proc.stdout
