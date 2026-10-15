"""
MODULE: unit_tests/agents/test_acd_2500d_5.py
COVERS: ACD-2500d-5
GOAL: Red-first specification of ticket 27: one code-aware planning agent, `test-designer`, is
    registered in config/agent_registry.json and has the canonical template
    templates/agents/test-designer.md (Sonnet; tools Bash, Read, Write, Edit; no search tools),
    whose profile declares that it mutates requirement records and produces two outputs
    (test design for ACD-2500c, file findings for ACD-2500d) in separate fields. it-po still
    declares no source-code access (ADR-009).
BUSINESS CONTEXT: ADR-009 keeps the technical planner away from source, so something that may
    read code must design tests and file findings before the build (ADR-071/-072). This ticket
    only creates the skeleton: frontmatter, the machine-parsed contract, step 1 (read the
    pre-pass report first) and the two output groups. The two procedures are filled by tickets
    29, 35, 36, 38 and 40, and tested there.
HONEST LIMIT: a template is a prompt. These tests prove what is decidable about the file and the
    registry (parsed frontmatter, parsed JSON, the real registry validator, the real prompt
    renderer on a tmp copy, paragraph-scoped presence). They cannot prove a model obeys the rule.
    Nothing here spawns build.py (CLAUDE.md); the build's own deploy parity is its own guard.
RED STATE: templates/agents/test-designer.md and its registry entry do not exist, so every test
    fails on an assertion (or on the explicit existence assertion), not on an import.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
REGISTRY = REPO / "config" / "agent_registry.json"
TEMPLATES = REPO / "templates" / "agents"
TEMPLATE = TEMPLATES / "test-designer.md"
IT_PO = TEMPLATES / "it-po.md"
RENDER_CLI = REPO / "scripts" / "render_effective_prompt.py"
AC_FILE = (
    REPO / "docs" / "acceptance-criteria" / "ac-driven-dev"
    / "ACD-2500-right-job-right-agent" / "ACD-2500d-5.yaml"
)
VALIDATOR_CLI = REPO / "scripts" / "registry_validator.py"
AGENT_ID = "test-designer"
CONTRACT_PHRASE = "Machine-Parsed Dispatch Output Contract"
TEST_DESIGN_FIELDS = ("test_spec", "test_design_authorship", "test_design_opened_files")
FILE_FINDINGS_FIELDS = ("file_findings", "file_findings_opened_files")
SEARCH_TOOLS = {"Grep", "Glob", "Agent", "Skill"}


def _flat(text: str) -> str:
    """Prose view: emphasis dropped, whitespace collapsed (a wrapped line is one line)."""
    return re.sub(r"\s+", " ", text.replace("`", "").replace("**", "")).strip()


def _split(path: Path) -> tuple[dict, str]:
    """(parsed frontmatter, body) of an agent template; fails with a plain message if absent."""
    assert path.is_file(), f"{path.relative_to(REPO).as_posix()} does not exist yet"
    _, front, body = path.read_text(encoding="utf-8").split("---", 2)
    return yaml.safe_load(front), body


def _agents() -> list[dict]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))["agents"]


def _entry() -> dict:
    found = [agent for agent in _agents() if agent["id"] == AGENT_ID]
    assert len(found) == 1, f"expected exactly one registry entry {AGENT_ID!r}, found {len(found)}"
    return found[0]


def _tools(frontmatter: dict) -> list[str]:
    return [tool.strip() for tool in str(frontmatter["tools"]).split("#")[0].split(",") if tool.strip()]


def _paragraphs(body: str) -> list[str]:
    return [_flat(block) for block in re.split(r"\n\s*\n", body) if block.strip()]


def _paragraph_with(body: str, *needles: str) -> str:
    """The flattened paragraph containing every needle (case-insensitive)."""
    for paragraph in _paragraphs(body):
        if all(needle.lower() in paragraph.lower() for needle in needles):
            return paragraph
    pytest.fail(f"no paragraph of the template mentions all of {needles!r}")


def _env() -> dict:
    return {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


# --------------------------------------------------------------------------
# AC-1: exactly one new agent, read-code role, Sonnet
# --------------------------------------------------------------------------
def test_test_designer_registered_on_sonnet():
    # covers: ACD-2500d-5
    # angle: criterion
    """AC-1: config/agent_registry.json has exactly one `test-designer` entry, model sonnet, whose
    template exists, internal (not a ticket phase), spawned only by plan-feature.js, and that
    passes the REAL registry validator (orphan templates, produces, tool grants)."""
    entry = _entry()
    sys.path.insert(0, str(REPO / "scripts"))
    import registry_validator

    assert entry["model"] == "sonnet"
    assert entry["template_path"] == "templates/agents/test-designer.md"
    assert (REPO / entry["template_path"]).is_file()
    assert entry["is_ticket_phase"] is False
    assert entry["selection_criteria"] is None
    assert entry["spawned_by"] == ["plan-feature.js"]
    assert entry["spawn_allowlist"] == []
    assert (entry["tier"], entry["role"], entry["category"], entry["produces"]) == (
        "utility", "analysis", "planning", "analysis",
    )
    assert entry["portable"] is True and entry["domain"] is None
    assert registry_validator.validate_agent_registry(REPO) == []


def test_ac1_exactly_one_agent_owns_the_two_outputs_and_registry_matches_template():
    # covers: ACD-2500d-5
    # angle: discrimination
    """AC-1 (wrong versions caught): (a) a second agent template also declaring `file_findings` or
    `test_design` among its outputs -- "exactly one new agent" would be false; (b) a registry model,
    name or produces that drifts from the template frontmatter (profile honesty, ACD-2500e-1-i)."""
    owners = []
    for path in sorted(TEMPLATES.glob("*.md")):
        match = re.match(r"---\r?\n(.*?)\r?\n---\r?\n", path.read_text(encoding="utf-8"), re.S)
        if match is None:
            continue  # shared prompt fragments (_signoff_block.md, ...) carry no frontmatter
        front = yaml.safe_load(match.group(1)) or {}
        names = {item.get("name") for item in front.get("outputs") or [] if isinstance(item, dict)}
        if names & {"file_findings", "test_design"}:
            owners.append(path.stem)
    front, _ = _split(TEMPLATE)
    entry = _entry()

    assert owners == [AGENT_ID], owners
    assert front["name"] == entry["id"] == AGENT_ID
    assert front["model"] == entry["model"] == "sonnet"
    assert front["produces"] == entry["produces"]
    assert front["portable"] is True and front["signoff"] is False
    assert front["domain"] is None and front["visibility"] == "internal"


# --------------------------------------------------------------------------
# AC-2: tools
# --------------------------------------------------------------------------
def test_test_designer_tools_exclude_search():
    # covers: ACD-2500d-5
    # angle: boundary
    """AC-2: the tool grant is exactly Bash, Read, Write, Edit (the ADR-033 section 2.6 Sonnet floor):
    it can read and edit files, and carries no Grep, Glob, MCP search tool, Agent or Skill. Exact set
    equality, so adding any search tool (the boundary just outside the grant) turns it red."""
    front, _ = _split(TEMPLATE)
    tools = _tools(front)

    assert set(tools) == {"Bash", "Read", "Write", "Edit"}, tools
    assert len(tools) == 4, f"duplicate tool entries: {tools}"
    assert not (set(tools) & SEARCH_TOOLS)
    assert not [tool for tool in tools if tool.startswith("mcp__")]
    assert "skills" not in front and "spawn_allowlist" not in front


def test_ac2_template_forbids_shell_search_of_the_repository():
    # covers: ACD-2500d-5
    # angle: criterion
    """AC-2 (architect note section 1): Bash is in the floor, so "no repository-wide search" is a
    template statement, not a tool restriction. The template forbids find, grep -r, rg and git grep."""
    _, body = _split(TEMPLATE)
    paragraph = _paragraph_with(body, "git grep")

    assert re.search(r"\b(no|never|do not|must not)\b", paragraph, re.I), paragraph
    for command in ("find", "grep -r", "rg", "git grep"):
        assert command in paragraph, f"{command!r} missing from: {paragraph}"


# --------------------------------------------------------------------------
# AC-3: profile declares the mutation and the two outputs
# --------------------------------------------------------------------------
def test_test_designer_profile_declares_two_outputs():
    # covers: ACD-2500d-5
    # angle: criterion
    """AC-3: the profile declares it mutates the requirement store (`mutates` names
    requirement_records on the AC YAML store) and produces two outputs, `test_design` and
    `file_findings`, in `outputs` (parsed frontmatter, not grep)."""
    front, _ = _split(TEMPLATE)
    mutates = front.get("mutates")
    outputs = front.get("outputs")

    assert isinstance(mutates, list) and len(mutates) == 1, mutates
    assert mutates[0]["name"] == "requirement_records"
    assert "AC YAML store" in str(mutates[0]["surface"])
    assert [item["name"] for item in outputs] == ["test_design", "file_findings"], outputs
    assert front["produces"] == "analysis"


def test_ac3_description_names_both_outputs_and_a_use_when_line():
    # covers: ACD-2500d-5
    # angle: criterion
    """AC-3 / ADR-033 section 2.5: the description is the agent's public profile; it names the test
    design (ACD-2500c) and the file findings (ACD-2500d), says it reads code and existing tests
    before the build, and carries a concrete `Use when` line."""
    front, _ = _split(TEMPLATE)
    description = _flat(front["description"])

    assert re.search(r"test design", description, re.I), description
    assert re.search(r"file findings", description, re.I), description
    assert re.search(r"(code|source)[^.]{0,80}(tests?|before the build)", description, re.I), description
    assert "Use when" in description, description


# --------------------------------------------------------------------------
# AC-4: separate fields, one group per run
# --------------------------------------------------------------------------
def test_ac4_one_output_group_leaves_the_other_groups_fields_untouched():
    # covers: ACD-2500d-5
    # angle: criterion
    """AC-4: the template names each output group's fields (test design: test_spec,
    test_design_authorship, test_design_opened_files; file findings: file_findings,
    file_findings_opened_files), the groups share no field, and one paragraph says a run that
    produces one group leaves the other group's fields untouched."""
    _, body = _split(TEMPLATE)
    paragraph = _paragraph_with(body, "untouched")

    assert not set(TEST_DESIGN_FIELDS) & set(FILE_FINDINGS_FIELDS)
    for field in TEST_DESIGN_FIELDS + FILE_FINDINGS_FIELDS:
        assert field in paragraph, f"{field!r} not named in the untouched-rule paragraph: {paragraph}"
    assert re.search(r"(one|only one|just one)[^.]{0,80}(group|output)", paragraph, re.I), paragraph


def test_ac4_dispatch_contract_shape_reports_each_group_separately():
    # covers: ACD-2500d-5
    # angle: criterion
    """AC-4 + architect note section 1: the template carries the Machine-Parsed Dispatch Output
    Contract phrase (test_bp_300e_6 requires it for any agent in a workflow pipeline) and the return
    shape {status: ok|blocked, records: [{id, test_design: written|pending|not_needed,
    file_findings: written|none, reason}], anomalies}: one value per group per record."""
    _, body = _split(TEMPLATE)

    assert CONTRACT_PHRASE in body
    contract = body[body.index(CONTRACT_PHRASE):]
    flat = _flat(contract)
    for token in ("status", "records", "anomalies", "reason", "test_design", "file_findings"):
        assert token in flat, f"{token!r} missing from the contract section"
    assert re.search(r"written\W+pending\W+not_needed", flat), flat
    assert re.search(r"written\W+none", flat), flat
    assert re.search(r"ok\W+blocked", flat), flat
    assert re.search(r"exactly one JSON value", flat, re.I), flat


# --------------------------------------------------------------------------
# AC-5: pre-pass report first
# --------------------------------------------------------------------------
def test_ac5_step_one_reads_the_pre_pass_report_before_opening_any_file():
    # covers: ACD-2500d-5
    # angle: criterion
    """AC-5: step 1 of the procedure reads the pre-pass report the workflow embeds in the prompt
    BEFORE opening any file, and takes existence, to-be-created and test-directory facts from it
    rather than re-deriving them."""
    _, body = _split(TEMPLATE)
    paragraph = _paragraph_with(body, "pre-pass", "before")

    assert re.search(r"before (you )?(open|opening|reading|read)[^.]{0,30}any", paragraph, re.I), paragraph
    assert re.search(r"(never|not|rather than)[^.]{0,40}re-?deriv", paragraph, re.I), paragraph
    assert re.search(r"to_be_created|to-be-created", paragraph, re.I), paragraph
    first_pre_pass = re.search(r"pre-?pass", body, re.I).start()
    first_open = re.search(r"\b(open|opened)\b", body, re.I)
    assert first_open is None or first_pre_pass < first_open.start(), "files are mentioned before the pre-pass"


# --------------------------------------------------------------------------
# AC-6: it-po still has no source access (seam between the two profiles)
# --------------------------------------------------------------------------
def test_it_po_still_declares_no_source_access():
    # covers: ACD-2500d-5
    # angle: seam
    """AC-6, both sides of the division: it-po's REAL template still carries the no-source-access
    declaration (tool line comment and the NEVER READ source/test list, no Grep/Glob), AND the
    test-designer template states the division from its side: the technical planner does not read
    source, source reading happens only in this step. A designer that quietly widened it-po, or
    that never mentions the planner boundary, fails."""
    it_po_front, it_po_body = _split(IT_PO)
    raw_tools_line = next(line for line in IT_PO.read_text(encoding="utf-8").splitlines() if line.startswith("tools:"))
    designer_front, designer_body = _split(TEMPLATE)

    assert "No source code access" in raw_tools_line
    assert not set(_tools(it_po_front)) & {"Grep", "Glob", "Agent"}
    assert "Source code (.py, .ts, .tsx, .sql, .js, .sh files)" in it_po_body
    assert it_po_body.index("You NEVER READ") < it_po_body.index("Source code (.py")
    paragraph = _paragraph_with(designer_body, "ADR-009", "source")
    assert re.search(r"(does not|never|no)[^.]{0,60}(read|access)[^.]{0,40}source", paragraph, re.I), paragraph
    assert designer_front["model"] == "sonnet"


# --------------------------------------------------------------------------
# reachability: the real entry points
# --------------------------------------------------------------------------
def test_acd_2500d_5_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500d-5
    # angle: reachability
    """Entry point resolved (Step 1.1, CLI scripts with main under scripts/):
    (a) `python scripts/registry_validator.py` as a subprocess -- the build's own registry gate --
        must exit 0 with the new entry and template present (a registry entry with no template, or a
        template with no entry, makes it exit 1);
    (b) `python scripts/render_effective_prompt.py --agent test-designer --ac ACD-2500d-5` as a subprocess on a tmp
        copy of the TEMPLATE and the registry: the prompt the agent receives at spawn time carries the
        Machine-Parsed Dispatch Output Contract and the pre-pass step. The CLI prefers the deployed
        copy under .claude/agents (build output, stale until the build runs), so it is pointed at a
        tmp repo root; the build is not run here."""
    assert TEMPLATE.is_file(), "templates/agents/test-designer.md does not exist yet"
    registry = subprocess.run(
        [sys.executable, str(VALIDATOR_CLI)], capture_output=True, text=True, encoding="utf-8",
        timeout=120, env=_env(), cwd=str(REPO),
    )
    assert registry.returncode == 0, registry.stdout + registry.stderr
    assert _entry()["template_path"] == "templates/agents/test-designer.md"

    root = tmp_path / "repo"
    (root / "templates" / "agents").mkdir(parents=True)
    (root / "config").mkdir()
    shutil.copyfile(TEMPLATE, root / "templates" / "agents" / "test-designer.md")
    shutil.copyfile(REGISTRY, root / "config" / "agent_registry.json")
    ac_folder = root / "docs" / "acceptance-criteria" / "ac-driven-dev"
    ac_folder.mkdir(parents=True)
    shutil.copyfile(AC_FILE, ac_folder / "ACD-2500d-5.yaml")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    proc = subprocess.run(
        [sys.executable, str(RENDER_CLI), "--agent", AGENT_ID, "--ac", "ACD-2500d-5",
         "--repo-root", str(root), "--out-dir", str(out_dir), "--quiet"],
        capture_output=True, text=True, encoding="utf-8", timeout=120, env=_env(), cwd=str(REPO),
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    rendered = next(out_dir.glob("effective_prompt_test-designer*.md")).read_text(encoding="utf-8")
    assert CONTRACT_PHRASE in rendered
    assert re.search(r"pre-?pass", rendered, re.I)
