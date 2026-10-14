"""AR-400a-3-i / -ii / -iii -- agent templates and the skills README stop naming
abilities that do not exist (trading-project residue and retired ``route-learning``).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/
AR-400a-3-{i,ii,iii}.yaml.

Every test reads the COMPILED prompt (real ``build_agents`` over a copy of the real
tree, both platform roots) or the real shipped file -- never a typed literal.

DEFERRED (need the not-yet-built reference gate of AR-400a-1 / AR-400b-1):
  * test_validator_reports_no_nonexistent_finding_for_research_agent   (AR-400a-3-i)
  * test_validator_reports_no_ability_finding_for_retrospective_agent  (AR-400a-3-ii)
  * the "existence check reports zero findings" half of
    test_skills_readme_has_zero_findings_and_no_retired_examples        (AR-400a-3-iii)
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_400_support import (  # noqa: E402
    REPO_ROOT,
    SKILLS_ROOT,
    abilities_section,
    ability_rows,
    built_prompts,
    installed_skill_ids,
    tools_of,
)

README = REPO_ROOT / "templates" / "skills" / "README.md"
TRADING_ABILITIES = ("import-scanner", "find-context-candle", "trade-analysis")
_IMPORT_ROW_RE = re.compile(r"^\|\s*[^|]*which python files import a specific symbol[^|]*\|(?P<target>.*)\|\s*$",
                            re.IGNORECASE)
_SKILL_PATH_RE = re.compile(r"skills/([a-z0-9][a-z0-9-]*)/SKILL\.md")


def test_compiled_research_agent_has_no_trading_ability_instructions():
    # covers: AR-400a-3-i
    # angle: deployed
    prompts = built_prompts("research-agent")
    for root, text in prompts.items():
        lowered = text.lower()
        for name in TRADING_ABILITIES:
            assert name not in lowered, f"{root}: compiled research-agent still names {name!r}"
        assert "1-minute candle" not in lowered, f"{root}: candle routing row still present"
        assert "why a trade fired" not in lowered, f"{root}: trade-fired routing row still present"


def test_import_question_is_routed_to_a_granted_tool():
    # covers: AR-400a-3-i
    # angle: criterion
    # must_catch: the import row is deleted outright / points at an ability that does not exist
    granted = set(tools_of("research-agent"))
    shipped = installed_skill_ids(REPO_ROOT)
    for root, text in built_prompts("research-agent").items():
        rows = [m for m in (_IMPORT_ROW_RE.match(ln) for ln in text.splitlines()) if m]
        assert len(rows) == 1, f"{root}: expected exactly one 'which Python files import a specific symbol' row, got {len(rows)}"
        target = rows[0].group("target")
        missing = [s for s in _SKILL_PATH_RE.findall(target) if s not in shipped]
        assert not missing, f"{root}: import row routes to ability(ies) that do not exist: {missing}"
        named = {t for t in granted if re.search(rf"(?<![\w-]){re.escape(t)}(?![\w-])", target)}
        assert named, f"{root}: import row names none of research-agent's granted tools: {target.strip()!r}"
        assert "import-scanner" not in target


def test_compiled_retrospective_agent_names_route_knowledge_not_route_learning():
    # covers: AR-400a-3-ii
    # angle: deployed
    installed = installed_skill_ids(REPO_ROOT)
    for root, text in built_prompts("retrospective-agent").items():
        assert "route-learning" not in text, f"{root}: 'route-learning' still in compiled retrospective-agent"
        body_hits = len(re.findall(r"route-knowledge", text.replace(abilities_section(text), "")))
        assert body_hits >= 4, f"{root}: route-knowledge named at {body_hits} former call sites, want >= 4"
        assert "route-knowledge" in ability_rows(text, installed), (
            f"{root}: delivered abilities section does not list route-knowledge")


def test_retrospective_agent_permits_the_skill_tool():
    # covers: AR-400a-3-ii
    # angle: criterion
    # must_catch: the grant is added without the Skill tool
    tools = tools_of("retrospective-agent")
    for needed in ("Skill", "Bash", "Read", "Write", "Agent"):
        assert needed in tools, f"retrospective-agent tools {tools} lack exact token {needed!r}"


def test_skills_readme_has_zero_findings_and_no_retired_examples():
    # covers: AR-400a-3-iii
    # angle: real_artifact
    # (existence-check half deferred: the gate of AR-400a-1 is not built; the retired-name half is asserted.)
    lines = README.read_text(encoding="utf-8").splitlines()
    offenders = [(n, ln.strip()) for n, ln in enumerate(lines, 1) if re.search(r"route-learning|capture-learning", ln)]
    assert not offenders, f"templates/skills/README.md still names retired abilities: {offenders}"


def test_readme_worked_example_names_a_shipped_ability():
    # covers: AR-400a-3-iii
    # angle: criterion
    text = README.read_text(encoding="utf-8")
    ids = _SKILL_PATH_RE.findall(text)
    assert ids, "README has no 'skills/<id>/SKILL.md' worked load example at all"
    missing = [i for i in ids if not (SKILLS_ROOT / i / "SKILL.md").is_file()]
    assert not missing, f"README worked example names abilities with no templates/skills/<id>/SKILL.md: {missing}"
    assert any("route-knowledge" in i for i in ids), "worked example should load route-knowledge (AR-400a-3-iii)"
