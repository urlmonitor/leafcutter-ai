"""AR-400c-2 / AR-400c-3 -- dead grants removed from adr-author and product-owner,
and llm-expert stops telling authors to hand-write an abilities section.

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/
AR-400c-2.yaml and AR-400c-3.yaml. Compiled-prompt tests use the real in-process
``build_agents`` over a copy of the real tree (every platform root); the registry test
runs the REAL transform hook script over a copy of the real tree.

DEFERRED / PARTIAL:
  * AR-400c-2 test_product_owner_signoff_citation_produces_no_finding: the "validator
    reports no finding" half needs the AR-400b-1 gate (not built); the citation half
    (product-owner still cites signoff's SKILL.md and it resolves) is asserted here and
    is GREEN-BY-DESIGN today -- it guards the grant removal turning a citation into a fault.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import accounts, agent_fm, real_slice, write_template  # noqa: E402
from _ar_400_support import (  # noqa: E402
    REPO_ROOT,
    SKILLS_ROOT,
    abilities_section,
    ability_rows,
    built_prompts,
    compile_real,
    compile_with,
    installed_skill_ids,
    skills_entries,
)

HOOK = REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "transform_agent_registry.py"
REGISTRY = REPO_ROOT / "config" / "agent_registry.json"


def _condition_of(stem: str, skill_id: str) -> str:
    return next(str(e.get("condition") or "") for e in skills_entries(stem) if e["skill_id"] == skill_id)


def test_compiled_adr_author_and_product_owner_drop_only_the_dead_grants():
    # covers: AR-400c-2
    # angle: deployed
    installed = installed_skill_ids(REPO_ROOT)
    signoff_cond = _condition_of("adr-author", "signoff")
    assert signoff_cond, "adr-author's signoff grant must keep its condition"
    for root, text in built_prompts("adr-author").items():
        rows = ability_rows(text, installed)
        assert "doc-enforcer" not in rows, f"{root}: adr-author's abilities section still lists doc-enforcer"
        assert "signoff" in rows and signoff_cond in " ".join(rows["signoff"]), f"{root}: adr-author lost signoff/its condition"
    for root, text in built_prompts("product-owner").items():
        rows = ability_rows(text, installed)
        assert "signoff" not in rows, f"{root}: product-owner's abilities section still lists signoff"
        for sid in ("knowledge-query", "ac-tree-split"):
            cond = _condition_of("product-owner", sid)
            assert sid in rows and cond in " ".join(rows[sid]), f"{root}: product-owner lost {sid} or its condition"


def test_regenerated_registry_lists_neither_removed_grant(tmp_path):
    # covers: AR-400c-2
    # angle: real_artifact
    pkg = real_slice(tmp_path / "src")
    proc = subprocess.run([sys.executable, str(HOOK), "--package-root", str(pkg)],
                          capture_output=True, text=True, timeout=120, check=False)
    assert proc.returncode == 0, f"transform hook exited {proc.returncode}: {proc.stderr[-400:]}"
    regenerated = (pkg / "config" / "agent_registry.json").read_bytes()
    entries = {a["id"]: a for a in json.loads(regenerated)["agents"]}

    def granted(agent: str) -> set[str]:
        e = entries[agent]
        invoked = {i["skill_id"] if isinstance(i, dict) else i for i in (e.get("skills_invoked") or [])}
        return set(e.get("skills_used") or []) | invoked

    assert "doc-enforcer" not in granted("adr-author"), "regenerated registry still lists doc-enforcer for adr-author"
    assert "signoff" not in granted("product-owner"), "regenerated registry still lists signoff for product-owner"
    assert regenerated == REGISTRY.read_bytes(), "committed config/agent_registry.json is not byte-identical to the hook's output"


def test_product_owner_signoff_citation_produces_no_finding():
    # covers: AR-400c-2
    # angle: criterion
    # (validator half deferred -- AR-400b-1 gate not built. Citation half only; green-by-design today.)
    text = compile_real("product-owner")
    assert re.search(r"templates/skills/signoff/SKILL\.md", text), "product-owner's citation of signoff's SKILL.md vanished"
    assert (SKILLS_ROOT / "signoff" / "SKILL.md").is_file()


def _drafting_sections(text: str) -> list[str]:
    step = re.search(r"Draft the body\*\*(.*?)(?=\n\d+\.\s+\*\*)", text, re.S)
    assert step, "llm-expert has no 'Draft the body' drafting step"
    body = re.sub(r"\s+", " ", step.group(1))
    listing = body.split(":", 1)[1].split(". ")[0] if ":" in body else ""
    listing = re.sub(r"\([^)]*\)", "", listing)
    return [i.strip(" .") for i in listing.split(",") if 0 < len(i.split()) <= 6]


def test_compiled_llm_expert_has_exactly_one_abilities_section():
    # covers: AR-400c-3
    # angle: deployed
    installed = installed_skill_ids(REPO_ROOT)
    for root, text in built_prompts("llm-expert").items():
        found = accounts(text, installed)
        assert len(found) == 1, f"{root}: {len(found)} abilities sections, want exactly the delivered one"
        assert found[0]["heading"] == "## Your Available Skills", f"{root}: the one section is {found[0]['heading']!r}"
        assert abilities_section(text).strip(), f"{root}: delivered abilities section is empty"
        sections = _drafting_sections(text)
        assert sections, f"{root}: could not read the drafting step's section list"
        assert "Skills" not in sections, f"{root}: drafting step still lists a 'Skills' body section: {sections}"
        assert re.search(r"declared once in (?:its|the) `skills:` header", text) and "delivered by the build" in text, (
            f"{root}: drafting step does not say abilities are declared once in `skills:` and delivered by the build")
        assert not re.search(r"the skills table above", text, re.IGNORECASE), f"{root}: 'the Skills table above' still present"
        promo = re.search(r"\*\*Promote.*?(?=\n\d+\.\s+\*\*)", text, re.S).group(0)
        assert "add-agent-to-package" in promo and "add-skill-to-package" in promo
        assert re.search(r"abilities section|Your Available Skills", promo), "promotion step does not point at the delivered section"


def test_specialist_drafted_per_guidance_compiles_with_one_abilities_section(tmp_path):
    # covers: AR-400c-3
    # angle: criterion
    # must_catch: the guidance still yields a hand-written Skills section duplicating the delivered one
    installed = installed_skill_ids(REPO_ROOT)
    sections = _drafting_sections(compile_real("llm-expert"))
    assert sections, "could not read the drafting step's section list"
    row = "| signoff | always | record the phase sign-off |"
    body = "\n\n".join(
        f"## {s}\n\n" + (f"| Skill | Mode | Purpose |\n|---|---|---|\n{row}\n" if s.lower() == "skills" else f"{s} content.")
        for s in sections)
    fm = agent_fm("zz-fixture-specialist", skills=[{"skill_id": "signoff", "mode": "always"}])
    tpl = write_template(tmp_path / "zz-fixture-specialist.md", fm, body)
    compiled = compile_with(tpl, agents=None, skills_root=SKILLS_ROOT)
    found = accounts(compiled, installed)
    assert len(found) == 1, f"specialist drafted per guidance has {len(found)} abilities sections: {[a['heading'] for a in found]}"
