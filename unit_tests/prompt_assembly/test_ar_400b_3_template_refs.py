"""AR-400b-3-i / -ii / -iii / -iv -- four specialists name or are granted abilities
correctly: research-agent gets knowledge-query (+ Skill tool), python-coder loads
``signoff`` by its real id, architecture-diagram-author uses the real casing of
write-c4-diagram, sql-coder hands query scaffolding to the sql-query SUB-AGENT.

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/
AR-400b-3-{i,ii,iii,iv}.yaml. Tests read the COMPILED prompt (real in-process
``build_agents`` over a copy of the real tree, every platform root).

DEFERRED (need the not-yet-built reference gate of AR-400b-1 / AR-400b-2-*):
  * test_validator_has_no_not_granted_finding_for_research_agent       (AR-400b-3-i)
  * test_validator_has_no_finding_for_python_coder_signoff             (AR-400b-3-ii)
  * test_validator_has_no_case_finding_for_diagram_author              (AR-400b-3-iii)
  * test_validator_has_no_names_an_agent_finding_for_sql_coder         (AR-400b-3-iv)
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_400_support import (  # noqa: E402
    REPO_ROOT,
    ability_rows,
    built_prompts,
    installed_skill_ids,
    instruction_lines,
    named_sub_agents,
    real_known_ids,
    skills_entries,
    spawn_accounts,
    tools_of,
)

# research-agent's `tools:` BEFORE the AR-400b-3-i change, captured from the tree on
# 2026-10-14 (24 exact tokens). The change must add exactly "Skill" and drop nothing.
RESEARCH_TOOLS_BEFORE = frozenset({
    "Bash", "Read", "Grep", "Glob",
    "mcp__jcodemunch__get_blast_radius", "mcp__jcodemunch__get_dependency_graph",
    "mcp__jcodemunch__get_class_hierarchy", "mcp__jcodemunch__get_context_bundle",
    "mcp__jcodemunch__find_references", "mcp__jcodemunch__find_importers",
    "mcp__jcodemunch__search_symbols", "mcp__jcodemunch__search_text",
    "mcp__jcodemunch__get_symbol", "mcp__jcodemunch__get_file_outline",
    "mcp__jcodemunch__get_related_symbols", "mcp__jcodemunch__get_ranked_context",
    "mcp__plugin_serena_serena__find_symbol", "mcp__plugin_serena_serena__find_declaration",
    "mcp__plugin_serena_serena__find_implementations", "mcp__plugin_serena_serena__find_referencing_symbols",
    "mcp__plugin_serena_serena__search_for_pattern", "mcp__plugin_serena_serena__get_symbols_overview",
    "mcp__plugin_context7_context7__resolve-library-id", "mcp__plugin_context7_context7__query-docs",
})
_LOAD_SIGNOFF_BAD_RE = re.compile(r"\b(?:load|invoke|run)\b[^\n.]{0,40}\bsign-off\s+(?:skill|ability)", re.IGNORECASE)
_LOAD_SIGNOFF_GOOD_RE = re.compile(r"\bload\b[^\n.]{0,40}\bsignoff\b", re.IGNORECASE)
_C4_RE = re.compile(r"write[- ]c4[- ]diagram", re.IGNORECASE)


def test_compiled_research_agent_lists_knowledge_query_with_condition():
    # covers: AR-400b-3-i
    # angle: deployed
    installed = installed_skill_ids(REPO_ROOT)
    for root, text in built_prompts("research-agent").items():
        rows = ability_rows(text, installed).get("knowledge-query", [])
        assert len(rows) == 1, f"{root}: delivered abilities section lists knowledge-query {len(rows)}x, want 1"
        row = rows[0].lower()
        assert "conditional" in row, f"{root}: knowledge-query row is not mode conditional: {rows[0]!r}"
        assert re.search(r"knowledge[- ]graph", row), f"{root}: row carries no knowledge-graph condition: {rows[0]!r}"
    declared = {e["skill_id"]: e for e in skills_entries("research-agent")}
    assert declared.get("knowledge-query", {}).get("mode") == "conditional", "frontmatter grant missing / not conditional"


def test_research_agent_tools_gain_skill_and_keep_every_existing_tool():
    # covers: AR-400b-3-i
    # angle: criterion
    # must_catch: a search tool is dropped while editing the tools line
    # must_catch: the grant is added without the Skill tool
    tools = tools_of("research-agent")
    assert len(tools) == len(set(tools)), f"duplicate tokens in tools: {tools}"
    assert set(tools) == RESEARCH_TOOLS_BEFORE | {"Skill"}, (
        f"tools differ from pre-change set + Skill: missing={sorted((RESEARCH_TOOLS_BEFORE | {'Skill'}) - set(tools))} "
        f"extra={sorted(set(tools) - RESEARCH_TOOLS_BEFORE - {'Skill'})}")


def test_compiled_python_coder_loads_signoff_by_id():
    # covers: AR-400b-3-ii
    # angle: deployed
    for root, text in built_prompts("python-coder").items():
        lines = instruction_lines(text)
        bad = [ln.strip() for ln in lines if _LOAD_SIGNOFF_BAD_RE.search(ln)]
        assert not bad, f"{root}: instruction(s) still tell python-coder to load an ability named 'sign-off': {bad}"
        good = [ln for ln in lines if _LOAD_SIGNOFF_GOOD_RE.search(ln)]
        assert good, f"{root}: no sign-off instruction names the ability 'signoff' by id"


def test_compiled_diagram_author_names_write_c4_diagram_in_canonical_case():
    # covers: AR-400b-3-iii
    # angle: deployed
    for root, text in built_prompts("architecture-diagram-author").items():
        names = [m.group(0) for m in _C4_RE.finditer(text)]
        assert names, f"{root}: compiled prompt never names write-c4-diagram"
        wrong = sorted({n for n in names if n != "write-c4-diagram"})
        assert not wrong, f"{root}: ability named in non-canonical form(s): {wrong}"


def test_compiled_sql_coder_hands_scaffolding_to_sql_query_sub_agent():
    # covers: AR-400b-3-iv
    # angle: deployed
    known = real_known_ids()
    for root, text in built_prompts("sql-coder").items():
        lines = instruction_lines(text)
        as_ability = [ln.strip() for ln in lines
                      if re.search(r"`sql-query`\s+(?:skill|ability)|(?:load|invoke|run)\b[^\n.]{0,30}\bsql-query\b[^\n.]{0,10}skill",
                                   ln, re.IGNORECASE)]
        assert not as_ability, f"{root}: sql-coder is still told to use sql-query as an ability: {as_ability}"
        prose = "\n".join(ln for ln in lines if not ln.lstrip().startswith("|"))
        verb = r"(?:sub-?agent|hand[- ]?(?:off|over)|hand\s|spawn|\bAgent\b)"
        scaffold = re.search(rf"sql-query[^.]{{0,100}}{verb}|{verb}[^.]{{0,100}}sql-query", prose, re.IGNORECASE)
        assert scaffold, f"{root}: no instruction hands query scaffolding to the sql-query sub-agent"
        accounts = spawn_accounts(text, known)
        assert "sql-query" in named_sub_agents(text, known), f"{root}: sql-query dropped from the compiled hand-off list"
        assert len(accounts) == 1, f"{root}: expected one hand-off account, got {len(accounts)}"
