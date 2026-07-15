"""
MODULE: test_llm_expert_artifacts
GOAL: Backfill green, source-contract coverage for the 27 BP-200 acceptance
    criteria (the llm-expert agent surface). Each test reads a shipped artifact
    file and asserts its structure/content against the corresponding AC's
    criteria — mirroring the parse-file-as-text / parse-JSON pattern in
    unit_tests/workflows/test_finalize_feature_preflight.py.

    Nature: CODE_NO_TEST backfill. The artifacts already exist and are correct;
    these tests never modify them. Every test carries a `# covers: <AC-id>`
    comment naming the AC it backs.

    Surfaces under test (all read-only):
      - templates/agents/llm-expert.md              (agent template)
      - docs/agents/llm-expert/PROJECT_CONTEXT.md   (six knowledge sections)
      - config/agent_registry.json                  (registry entries)
      - templates/skills/prompt-audit/SKILL.md      (read-only audit skill)
      - docs/agents/README.md                       (phase-agents table)

TICKET: tickets/00_inbox/epics/EPIC-BuildPipelineTestBackfill/01_bp200_llm_expert_test_coverage.md
ACs: BP-200a-1 .. BP-200e-3 (27 total)

KNOWN RED (asserted honestly, artifact NOT weakened to force green):
    BP-200a-2 "each item has a Correct form example" — checklist items 3, 5 and 6
    in templates/agents/llm-expert.md carry a Violation example but no literal
    "Correct form" line, so test_bp200a_2_each_checklist_item_has_correct_form
    fails by design (the audit note in the ticket flags items 5 & 6; item 3 is
    also missing it). The companion green test still covers BP-200a-2.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Robust repo-root resolution: walk up until we find the directory that holds
# both templates/ and config/ (works from the worktree or the main checkout).
# ---------------------------------------------------------------------------

class _RepoRootNotFound(RuntimeError):
    """Raised when no ancestor directory holds both templates/ and config/."""

    def __init__(self) -> None:
        super().__init__("repo root (dir containing templates/ and config/) not found")


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "templates").is_dir() and (candidate / "config").is_dir():
            return candidate
    raise _RepoRootNotFound


_ROOT = _repo_root()
_LLM_EXPERT_TEMPLATE = _ROOT / "templates" / "agents" / "llm-expert.md"
_PROJECT_CONTEXT = _ROOT / "docs" / "agents" / "llm-expert" / "PROJECT_CONTEXT.md"
_REGISTRY = _ROOT / "config" / "agent_registry.json"
_PROMPT_AUDIT_SKILL = _ROOT / "templates" / "skills" / "prompt-audit" / "SKILL.md"
_AGENTS_README = _ROOT / "docs" / "agents" / "README.md"
# TICKET-20260715-BuildPipelineAuditFindings accuracy-correction tests
_BP_100B9_YAML = (
    _ROOT / "docs" / "acceptance-criteria" / "build_pipeline"
    / "BP-100-reliable-builds" / "BP-100b-9.yaml"
)
_FRONTEND_UPGRADE_HOWTO = (
    _ROOT / "docs" / "how-to" / "upgrade-frontend-coder-unified-agent.md"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _frontmatter(text: str) -> dict:
    """Parse the leading YAML frontmatter block of a markdown file."""
    parts = text.split("---", 2)
    assert len(parts) >= 3, "file does not open with a --- frontmatter block"
    return yaml.safe_load(parts[1])


def _md_section(text: str, heading: str) -> str:
    """Return the text of the markdown section that starts with `heading`
    (matched on the stripped line prefix), up to the next heading of the same
    or higher level. Fenced code blocks (```-delimited) are skipped when
    detecting headings so that `#`-prefixed shell comments inside code blocks
    are not mistaken for markdown headings. Returns '' when heading is absent."""
    level = len(heading) - len(heading.lstrip("#"))
    lines = text.splitlines()
    start = None
    in_fence = False
    for i, line in enumerate(lines):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence and line.strip().startswith(heading):
            start = i
            break
    if start is None:
        return ""
    end = len(lines)
    in_fence = False
    for j in range(start + 1, len(lines)):
        line = lines[j]
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence and line.startswith("#"):
            cur_level = len(line) - len(line.lstrip("#"))
            if cur_level <= level:
                end = j
                break
    return "\n".join(lines[start:end])


def _tool_list(value: str) -> list[str]:
    return [tok.strip() for tok in value.split(",") if tok.strip()]


def _checklist_items(template_text: str) -> dict[int, str]:
    """Split the Prompt-Quality Checklist section into its numbered items."""
    section = _md_section(template_text, "## Prompt-Quality Checklist")
    starts = list(re.finditer(r"^(\d+)\.\s+\*\*", section, re.MULTILINE))
    items: dict[int, str] = {}
    for idx, match in enumerate(starts):
        begin = match.start()
        finish = starts[idx + 1].start() if idx + 1 < len(starts) else len(section)
        items[int(match.group(1))] = section[begin:finish]
    return items


def _registry_agent(agent_id: str) -> dict:
    data = json.loads(_read(_REGISTRY))
    matches = [a for a in data["agents"] if a.get("id") == agent_id]
    assert len(matches) == 1, f"expected exactly one '{agent_id}' registry entry"
    return matches[0]


# ---------------------------------------------------------------------------
# BP-200a — agent template (templates/agents/llm-expert.md)
# ---------------------------------------------------------------------------

def test_bp200a_1_frontmatter_required_fields():
    # covers: BP-200a-1
    fm = _frontmatter(_read(_LLM_EXPERT_TEMPLATE))
    assert fm["name"] == "llm-expert"
    assert isinstance(fm["description"], str) and fm["description"].strip()
    assert fm["model"] == "sonnet"
    tools = _tool_list(fm["tools"])
    for tool in ("Bash", "Read", "Edit", "Write", "Agent"):
        assert tool in tools, f"tools missing {tool}: {tools}"
    assert fm["portable"] is True
    assert fm["signoff"] is True
    assert fm["domain"] is None
    assert fm["requires_verification"] is True
    assert isinstance(fm["default_artifact_checklist"], list)
    assert fm["default_artifact_checklist"], "default_artifact_checklist is empty"


def test_bp200a_2_checklist_has_six_items_with_violations_and_blocker():
    # covers: BP-200a-2
    text = _read(_LLM_EXPERT_TEMPLATE)
    items = _checklist_items(text)
    assert sorted(items) == [1, 2, 3, 4, 5, 6], f"expected 6 numbered items, got {sorted(items)}"
    for n, body in items.items():
        assert "Violation" in body, f"checklist item {n} lacks a Violation example"
    section = _md_section(text, "## Prompt-Quality Checklist")
    assert "A checklist item that fails is a blocker" in section


def test_bp200a_2_each_checklist_item_has_correct_form():
    # covers: BP-200a-2
    # AC BP-200a-2 requires EACH of the six items to include a "Correct form"
    # example. This is asserted honestly against the shipped artifact; it is a
    # genuine RED because items 3, 5 and 6 carry only a Violation example.
    items = _checklist_items(_read(_LLM_EXPERT_TEMPLATE))
    missing = [n for n, body in sorted(items.items()) if "Correct form" not in body]
    assert not missing, (
        "Prompt-Quality Checklist items missing a 'Correct form' example: "
        f"{missing}. AC BP-200a-2 requires every item to include one."
    )


def test_bp200a_3_stop_and_ask_defers_infra_edits():
    # covers: BP-200a-3
    section = _md_section(_read(_LLM_EXPERT_TEMPLATE), "## Stop-and-Ask Rule")
    assert section, "Stop-and-Ask Rule section not found"
    assert "workflow-architect" in section
    for target in ("agent_registry.json", "build.py", "build_phases.py",
                   "build_precommit.py", "commit_guardian.json"):
        assert target in section, f"Stop-and-Ask does not defer {target}"
    assert "ambiguous" in section.lower()
    assert "destructive" in section.lower() or "delete" in section.lower()
    assert "mcp__" in section


def test_bp200a_3_i_constraints_prohibit_source_and_search_edits():
    # covers: BP-200a-3-i
    section = _md_section(_read(_LLM_EXPERT_TEMPLATE), "## Constraints")
    assert section, "Constraints section not found"
    for ext in (".py", ".sql", ".ts", ".tsx", ".html", ".css"):
        assert ext in section, f"Constraints does not prohibit {ext}"
    assert "(status: blocker)" in section
    assert "agent_registry.json" in section
    assert "build.py" in section
    assert "Grep" in section and "Glob" in section and "MCP" in section
    assert "Read before Edit" in section


def test_bp200a_4_preflight_reads_order():
    # covers: BP-200a-4
    section = _md_section(_read(_LLM_EXPERT_TEMPLATE), "## Pre-Flight Reads")
    assert section, "Pre-Flight Reads section not found"
    pc_pos = section.find("PROJECT_CONTEXT.md")
    signoff_pos = section.find("signoff")
    ticket_pos = section.lower().find("ticket")
    template_pos = section.lower().find("existing agent")
    assert pc_pos != -1, "PROJECT_CONTEXT.md not referenced"
    # PROJECT_CONTEXT.md must be the first read.
    assert "1. **`PROJECT_CONTEXT.md`**" in section
    assert signoff_pos > pc_pos, "signoff skill must be read after PROJECT_CONTEXT.md"
    assert ticket_pos != -1, "ticket body read not described"
    assert template_pos != -1, "existing agent template read not described"


def test_bp200a_4_i_graceful_degradation_when_context_absent():
    # covers: BP-200a-4-i
    section = _md_section(_read(_LLM_EXPERT_TEMPLATE), "## Pre-Flight Reads")
    assert "PROJECT_CONTEXT.md not found for llm-expert; running" in section
    assert "continue" in section.lower()
    # Must NOT instruct the agent to abort/raise when the file is missing.
    assert "abort" not in section.lower()


def test_bp200a_5_skills_table_lists_exactly_three():
    # covers: BP-200a-5
    section = _md_section(_read(_LLM_EXPERT_TEMPLATE), "## Skills")
    assert section, "Skills section not found"
    for skill in ("add-agent-to-package", "add-skill-to-package", "signoff"):
        assert skill in section, f"Skills table missing {skill}"
        assert f"skills/{skill}/SKILL.md" in section, f"{skill} row lacks SKILL.md path"
    # A markdown table with exactly three data rows (rows referencing SKILL.md).
    data_rows = [ln for ln in section.splitlines() if "SKILL.md" in ln and ln.strip().startswith("|")]
    assert len(data_rows) == 3, f"expected exactly 3 skill rows, got {len(data_rows)}"


# ---------------------------------------------------------------------------
# BP-200b — PROJECT_CONTEXT.md (docs/agents/llm-expert/PROJECT_CONTEXT.md)
# ---------------------------------------------------------------------------

def test_bp200b_1_six_sections_in_order():
    # covers: BP-200b-1
    text = _read(_PROJECT_CONTEXT)
    ordered = [
        "## Section 1: Shell Convention",
        "## Section 2: Agent Frontmatter Schema",
        "## Section 3: Skill Frontmatter Schema",
        "## Section 4: Signoff Protocol",
        "## Section 5: Nesting / Spawn-Allowlist Rules",
        "## Section 6: Prompt-Quality Checklist (Expanded)",
    ]
    positions = [text.find(h) for h in ordered]
    for heading, pos in zip(ordered, positions):
        assert pos != -1, f"missing section heading: {heading}"
    assert positions == sorted(positions), "sections are not in the required order"


def test_bp200b_2_shell_convention_rule_table_and_examples():
    # covers: BP-200b-2
    section = _md_section(_read(_PROJECT_CONTEXT), "## Section 1: Shell Convention")
    assert section, "Section 1 not found"
    assert "single, simple command" in section
    for pattern in ("&&", ";", "||", "cd "):
        assert pattern in section, f"detection heuristic missing pattern {pattern!r}"
    assert "pipe" in section.lower(), "side-effect pipe pattern not documented"
    wrong = len(re.findall(r"#\s*Wrong", section))
    right = len(re.findall(r"#\s*Right", section))
    assert wrong >= 4, f"expected >=4 Wrong examples, got {wrong}"
    assert right >= 4, f"expected >=4 Right examples, got {right}"
    assert "ENV=value" in section or "MY_ENV=value" in section or "ENV=val" in section


def test_bp200b_3_frontmatter_schemas_distinguish_required_and_injected():
    # covers: BP-200b-3
    text = _read(_PROJECT_CONTEXT)
    sec2 = _md_section(text, "## Section 2: Agent Frontmatter Schema")
    assert "Required Fields (hand-authored)" in sec2
    assert "Build-Injected Fields" in sec2
    for field in ("name", "description", "model", "tools", "portable", "signoff",
                  "domain", "config_keys", "adopter_notes", "requires_verification",
                  "spawn_allowlist"):
        assert field in sec2, f"Section 2 missing required field {field}"
    assert "inject_registry" in sec2
    assert "Do NOT hand-author" in sec2
    for model in ("haiku", "sonnet", "opus"):
        assert model in sec2, f"model enum missing {model}"
    sec3 = _md_section(text, "## Section 3: Skill Frontmatter Schema")
    for field in ("name", "description", "allowed-tools"):
        assert field in sec3, f"Section 3 missing required field {field}"


def test_bp200b_4_signoff_protocol_parity_timestamp_status():
    # covers: BP-200b-4
    section = _md_section(_read(_PROJECT_CONTEXT), "## Section 4: Signoff Protocol")
    assert section, "Section 4 not found"
    assert "§2" in section and "§4" in section
    assert "Three-Place Parity Rule" in section
    assert "YYYY-MM-DD HH:MM" in section
    for tag in ("(status: ok)", "(status: blocker)", "(status: question)"):
        assert tag in section, f"status tag missing: {tag}"


def test_bp200b_5_nesting_depth_and_spawn_allowlist_contract():
    # covers: BP-200b-5
    section = _md_section(_read(_PROJECT_CONTEXT), "## Section 5: Nesting / Spawn-Allowlist Rules")
    assert section, "Section 5 not found"
    for depth in ("Depth 0", "Depth 1", "Depth 2", "Depth 3"):
        assert depth in section, f"depth-cap table missing {depth}"
    assert "spawn_allowlist" in section
    assert "spawned_by" in section
    assert "runs at depth 1" in section
    assert "`[]`" in section, "empty default spawn_allowlist not documented"


# ---------------------------------------------------------------------------
# BP-200c — registry (config/agent_registry.json) + README
# ---------------------------------------------------------------------------

def test_bp200c_1_registry_entry_fields():
    # covers: BP-200c-1
    entry = _registry_agent("llm-expert")
    assert entry["id"] == "llm-expert"
    assert entry["name"] == "LLM Expert"
    assert entry["tier"] == "phase"
    assert entry["role"] == "authoring"
    assert entry["portable"] is True
    assert entry["domain"] is None
    assert entry["is_ticket_phase"] is True
    assert entry["model"] == "sonnet"
    assert entry["template_path"] == "templates/agents/llm-expert.md"
    assert entry["selection_criteria"]["default_status"] == "not_needed"


def test_bp200c_1_i_default_status_not_needed():
    # covers: BP-200c-1-i
    entry = _registry_agent("llm-expert")
    assert entry["selection_criteria"]["default_status"] == "not_needed"


def test_bp200c_2_trigger_conditions_dsl_and_llm():
    # covers: BP-200c-2
    entry = _registry_agent("llm-expert")
    conditions = entry["selection_criteria"]["trigger_conditions"]
    dsl = [c for c in conditions if c.get("type") == "dsl"]
    llm = [c for c in conditions if c.get("type") == "llm"]
    assert dsl, "no dsl trigger condition"
    dsl_expr = " ".join(c["expression"] for c in dsl)
    for glob in ("templates/agents/*.md", "templates/skills/*/SKILL.md",
                 "templates/workflows/*.md"):
        assert glob in dsl_expr, f"dsl expression missing glob {glob}"
    assert len(llm) >= 2, f"expected >=2 llm trigger conditions, got {len(llm)}"
    llm_expr = " ".join(c["expression"] for c in llm).lower()
    assert "agent template" in llm_expr or "skill body" in llm_expr
    assert "prompt-quality checklist" in llm_expr


def test_bp200c_3_spawn_wiring_and_skills_used():
    # covers: BP-200c-3
    supervisor = _registry_agent("ticket-supervisor")
    assert "llm-expert" in supervisor["spawn_allowlist"]
    entry = _registry_agent("llm-expert")
    assert "ticket-supervisor" in entry["spawned_by"]
    assert "research-agent" in entry["spawn_allowlist"]
    for skill in ("add-agent-to-package", "add-skill-to-package", "signoff"):
        assert skill in entry["skills_used"], f"skills_used missing {skill}"


def test_bp200c_4_readme_phase_agents_row():
    # covers: BP-200c-4
    text = _read(_AGENTS_README)
    rows = [ln for ln in text.splitlines() if ln.startswith("|") and "llm-expert" in ln]
    assert len(rows) == 1, f"expected exactly one llm-expert README row, got {len(rows)}"
    row = rows[0]
    for token in ("agent templates", "skill bodies", "slash-command",
                  "Prompt-Quality Checklist"):
        assert token in row, f"README row description missing {token!r}"
    assert "audits" in row.lower()
    # Positioned alphabetically: after how-to-author, before pr-reviewer.
    assert text.find("| [how-to-author]") < text.find("llm-expert") < text.find("| [pr-reviewer]")


# ---------------------------------------------------------------------------
# BP-200d — prompt-audit skill (templates/skills/prompt-audit/SKILL.md)
# ---------------------------------------------------------------------------

def test_bp200d_1_skill_frontmatter_read_only_contract():
    # covers: BP-200d-1
    text = _read(_PROMPT_AUDIT_SKILL)
    fm = _frontmatter(text)
    assert fm["name"] == "prompt-audit"
    desc = fm["description"].lower()
    assert "audit" in desc
    assert "checklist" in desc
    assert "violations" in desc
    allowed = _tool_list(fm["allowed-tools"])
    assert allowed == ["Bash", "Read"], f"allowed-tools must be exactly Bash, Read; got {allowed}"
    for forbidden in ("Edit", "Write", "Agent"):
        assert forbidden not in allowed, f"allowed-tools must not include {forbidden}"


def test_bp200d_2_six_checks_with_steps_and_severity():
    # covers: BP-200d-2
    text = _read(_PROMPT_AUDIT_SKILL)
    expected = {
        1: "Frontmatter Schema Validation",
        2: "Tool Allowlist vs Body Usage",
        3: "Compound Bash Detection",
        4: "Signoff Protocol Validation",
        5: "spawn_allowlist Validation",
        6: "Stop-and-Ask Rules",
    }
    for n, title in expected.items():
        heading = f"### Check {n} —"
        section = _md_section(text, heading)
        assert section, f"Check {n} heading not found"
        assert title in section, f"Check {n} title mismatch (expected {title!r})"
        assert re.search(r"^1\.", section, re.MULTILINE) or "Detection steps" in section, \
            f"Check {n} lacks numbered detection steps"
        assert "error" in section.lower() or "warning" in section.lower(), \
            f"Check {n} assigns no severity"


def test_bp200d_2_i_check4_skipped_when_signoff_false():
    # covers: BP-200d-2-i
    section = _md_section(_read(_PROMPT_AUDIT_SKILL), "### Check 4 —")
    assert section, "Check 4 not found"
    assert "signoff: true" in section
    assert "skip this check" in section
    assert "N/A" in section
    # Report field is null (not false) when skipped.
    report = _md_section(_read(_PROMPT_AUDIT_SKILL), "## Audit Report Format")
    assert re.search(r"signoff_protocol_valid.*None", report), \
        "signoff_protocol_valid is not documented as null/None when N/A"


def test_bp200d_2_ii_check2_severity_asymmetry():
    # covers: BP-200d-2-ii
    section = _md_section(_read(_PROMPT_AUDIT_SKILL), "### Check 2 —")
    assert section, "Check 2 not found"
    assert re.search(r"Undeclared tool used.*error", section, re.DOTALL), \
        "undeclared-tool must be classified as error"
    assert re.search(r"Overly permissive allowlist.*warning", section, re.DOTALL), \
        "over-permissive allowlist must be classified as warning"
    assert "do not block" in section.lower()


def test_bp200d_3_structured_report_schema_sorted():
    # covers: BP-200d-3
    section = _md_section(_read(_PROMPT_AUDIT_SKILL), "## Audit Report Format")
    assert section, "Audit Report Format section not found"
    for field in ("template_name", "file_path", "frontmatter_valid",
                  "tool_allowlist_valid", "no_compound_bash",
                  "signoff_protocol_valid", "spawn_allowlist_valid",
                  "stop_and_ask_valid", "violations", "passed_checks", "summary"):
        assert field in section, f"report schema missing field {field}"
    for vfield in ("check_name", "severity", "line_number", "description",
                   "suggested_fix"):
        assert vfield in section, f"violation object missing field {vfield}"
    for sfield in ("total_violations", "total_errors", "total_warnings"):
        assert sfield in section, f"summary missing field {sfield}"
    assert "sorted by line_number ascending" in section.lower()


def test_bp200d_4_read_only_no_autofix():
    # covers: BP-200d-4
    section = _md_section(_read(_PROMPT_AUDIT_SKILL), "## Constraints")
    assert section, "Constraints section not found"
    assert "read-only" in section.lower()
    assert "do not auto-fix" in section.lower()
    assert "remediation" in section.lower() and "llm-expert" in section
    for forbidden in ("Edit", "Write"):
        assert forbidden in section, f"Constraints should exclude {forbidden}"


def test_bp200d_5_single_batch_and_isolated_invocation():
    # covers: BP-200d-5
    section = _md_section(_read(_PROMPT_AUDIT_SKILL), "## Running an Audit")
    assert section, "Running an Audit section not found"
    assert "Single file audit" in section
    assert "Batch audit" in section
    assert "Invoking individual checks" in section
    assert re.search(r"total_errors\s*desc", section), "batch sort order not documented"


# ---------------------------------------------------------------------------
# BP-200e — checklist wiring (template) + audit pipe classification (skill)
# ---------------------------------------------------------------------------

def test_bp200e_1_implementation_sequence_runs_checklist_between_draft_and_write():
    # covers: BP-200e-1
    text = _read(_LLM_EXPERT_TEMPLATE)
    section = _md_section(text, "## Implementation Sequence")
    assert section, "Implementation Sequence section not found"
    # AC BP-200e-1 requires draft-body -> run-checklist -> write-file sequencing.
    draft_pos = section.find("**Draft the body")
    check_pos = section.find("**Run the Prompt-Quality Checklist")
    write_pos = section.find("**Write the file")
    assert draft_pos != -1, "no 'Draft the body' step"
    assert check_pos != -1, "no 'Run the Prompt-Quality Checklist' step"
    assert write_pos != -1, "no 'Write the file' step"
    assert draft_pos < check_pos < write_pos, (
        "checklist run must fall after drafting the body and before writing the file"
    )
    # The run-checklist step applies every item and fixes violations before writing.
    run_step = section[check_pos:write_pos]
    assert "apply every item" in run_step
    assert "before writing the file" in run_step
    checklist = _md_section(text, "## Prompt-Quality Checklist")
    assert "A checklist item that fails is a blocker" in checklist


def test_bp200e_2_response_payload_checklist_results_table():
    # covers: BP-200e-2
    section = _md_section(_read(_LLM_EXPERT_TEMPLATE), "## Response Payload")
    assert section, "Response Payload section not found"
    assert "Prompt-Quality Checklist Results" in section
    assert "| Item | Status | Notes |" in section
    for item in ("No compound bash commands", "Tool allowlist matches body",
                 "No tools in body absent from allowlist", "spawn_allowlist declared",
                 "Signoff section present", "Stop-and-ask rules present"):
        assert item in section, f"checklist-results table missing row: {item}"
    assert "pass/fail" in section


def test_bp200e_3_check3_distinguishes_pipe_kinds_with_severities():
    # covers: BP-200e-3
    section = _md_section(_read(_PROMPT_AUDIT_SKILL), "### Check 3 —")
    assert section, "Check 3 not found"
    assert re.search(r"Side-effect pipe.*error", section), "side-effect pipe not error"
    assert re.search(r"Read-only pipe.*warning", section), "read-only pipe not warning"
    # The table escapes the pipe operator as \|\| inside markdown cells.
    normalized = section.replace("\\", "")
    for pattern in ("&&", ";", "||", "cd "):
        assert pattern in normalized, f"Check 3 table missing {pattern!r}"
    # Every pattern row carries a severity, and a suggested_fix is documented.
    assert "error" in section and "warning" in section
    assert "suggested_fix" in section


# ---------------------------------------------------------------------------
# TICKET-20260715-BuildPipelineAuditFindings — accuracy corrections
# AC-1: BP-100b-9 criteria path, AC-2: spawn_allowlist consistency, AC-3: how-to
# ---------------------------------------------------------------------------


def test_ac1_bp100b9_criteria_names_workflows_js():
    # covers: BP-100b-9
    """AC-1: BP-100b-9 criteria must use 'templates/workflows-js/' (the real build
    source per build_phases.py:685) not 'templates/scripts/workflows/' (which does
    not exist). The correction must also be recorded in amended_by.

    Fails now because BP-100b-9.yaml still contains 'templates/scripts/workflows/'
    in its criteria field and has no non-split amended_by entry.
    Make green: update the criteria via the governance amendment path and add
    an amended_by entry for the correction.
    """
    data = yaml.safe_load(_read(_BP_100B9_YAML))
    criteria = data.get("criteria", "")

    # The real build source must be named in the corrected criterion.
    assert "templates/workflows-js/" in criteria, (
        "BP-100b-9 criteria must name 'templates/workflows-js/' as the shimmed "
        "workflow-scripts source directory (build_phases.py:685: "
        "`workflows_js_src = TEMPLATES_DIR / 'workflows-js'`). "
        "Currently the criteria still contains the non-existent path."
    )

    # The stale non-existent path must be removed from the criteria.
    assert "templates/scripts/workflows/" not in criteria, (
        "BP-100b-9 criteria still references 'templates/scripts/workflows/' "
        "which does not exist in the repo. Replace it with 'templates/workflows-js/' "
        "via the AC-amendment mechanism."
    )

    # The amendment must be recorded: at least one non-split amended_by entry.
    amended_entries = data.get("amended_by") or []
    non_split_amendments = [
        e for e in amended_entries
        if isinstance(e, str) and not e.strip().startswith("split:")
    ]
    assert non_split_amendments, (
        "BP-100b-9.yaml must record the criteria path correction in its "
        "'amended_by' field. Add an entry such as: "
        "\"corrected: criteria source path templates/scripts/workflows/ -> "
        "templates/workflows-js/, YYYY-MM-DD\""
    )


def test_ac2_llm_expert_spawn_allowlist_surfaces_agree():
    # covers: UNKNOWN
    """AC-2: The spawn_allowlist value stated in PROJECT_CONTEXT.md §5 for llm-expert
    must match the value in config/agent_registry.json.

    Fails now because PROJECT_CONTEXT.md §5 states the allowlist is `[]` while
    agent_registry.json lists `["research-agent"]`. Both surfaces must agree.
    Make green: update whichever surface is wrong so both declare the same value.
    """
    # Registry is the canonical source.
    registry_entry = _registry_agent("llm-expert")
    registry_allowlist = sorted(registry_entry.get("spawn_allowlist", []))

    # PROJECT_CONTEXT.md §5 must state the same value.
    section = _md_section(
        _read(_PROJECT_CONTEXT), "## Section 5: Nesting / Spawn-Allowlist Rules"
    )
    assert section, "Section 5 not found in PROJECT_CONTEXT.md"

    # Find the sentence that states llm-expert's spawn_allowlist value.
    # Expected format: "... is: `[...]` ..." on a single line.
    match = re.search(
        r"`llm-expert`[^\n]*?spawn_allowlist[^\n]*?is:\s*`(\[[^\]`]*\])`",
        section,
    )
    assert match, (
        "PROJECT_CONTEXT.md §5 must contain a sentence declaring llm-expert's "
        "spawn_allowlist value in the format '... is: `[...]`' so the two "
        "surfaces can be compared mechanically. "
        "Currently the sentence states `[]` while the registry has `[\"research-agent\"]`."
    )

    doc_allowlist = sorted(json.loads(match.group(1)))
    assert doc_allowlist == registry_allowlist, (
        f"spawn_allowlist mismatch between surfaces: "
        f"PROJECT_CONTEXT.md §5 says {json.loads(match.group(1))!r} "
        f"but config/agent_registry.json says "
        f"{registry_entry.get('spawn_allowlist', [])!r}. "
        "Both surfaces must declare the same value."
    )


def test_ac3_frontend_coder_howto_no_false_clean_prune_claim():
    # covers: UNKNOWN
    """AC-3: The how-to must NOT claim that 'build.py --clean' removes the
    .claude/skills/frontend-design/ directory.

    Fails now because the doc contains the phrase 'remove the stale
    `frontend-design` skill directory' in a --clean context (lines ~48, ~150).
    That claim is false: _build_source_manifests() treats deprecated templates
    as still-managed so clean_stale_artifacts() never prunes them.
    Make green: remove the false --clean prune claim from the how-to.
    """
    text = _read(_FRONTEND_UPGRADE_HOWTO)

    # The specific false statement must be absent after correction.
    assert "remove the stale `frontend-design` skill directory" not in text, (
        "The how-to falsely claims 'build.py --clean' removes the "
        ".claude/skills/frontend-design/ directory. That claim is incorrect — "
        "clean_stale_artifacts() does not prune deprecated-but-still-managed "
        "templates. Remove this false --clean prune sentence from the doc."
    )


def test_ac3_frontend_coder_howto_describes_real_removal_mechanism():
    # covers: UNKNOWN
    """AC-3: The how-to must describe the REAL removal mechanism for frontend-design/:
    deploy-time exclusion (deprecated: true causes _build_source_manifests() to skip
    deployment) + skills_config.json migration + template overwrite — not --clean.

    Fails now because the doc only describes the (false) --clean approach and
    does not mention the actual deploy-time exclusion / deprecated-skip mechanism.
    Make green: add a description of the real mechanism to the how-to.
    """
    text = _read(_FRONTEND_UPGRADE_HOWTO)

    # At least one of these signals must appear to document the real mechanism.
    real_mechanism_described = (
        "deploy-time" in text
        or "deprecated skip" in text
        or "excluded at deploy" in text
        or ("deprecated: true" in text)
        or "_build_source_manifests" in text
    )
    assert real_mechanism_described, (
        "The how-to must describe the real removal mechanism for frontend-design/: "
        "deploy-time exclusion (frontend-design is retained in templates/skills/ "
        "with 'deprecated: true', causing _build_source_manifests() to treat it as "
        "still-managed and skip deployment) + skills_config migration + template "
        "overwrite. Currently the doc only describes the false --clean approach."
    )
