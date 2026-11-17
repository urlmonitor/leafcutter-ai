"""AR-300d-4 -- no agent's delivery depends on an opt-in marker an author has to
remember: delivery follows the declaration over a DERIVED population in every
platform root, both counts are stated (zero fails), an agent receiving nothing
while holding a grant is NAMED, and a body token is not consulted.

Source of truth: .../AR-300d-4.yaml. Premise observed at the COMPILED prompts
(not by inspecting the delivery step's source).

RED / GREEN-ALREADY map:
  test_every_granted_agent_receives_its_abilities_with_no_marker_present_anywhere  GREEN-ALREADY (slice 1 appends from frontmatter)
  test_both_population_counts_are_stated_and_zero_fails                            RED (comparison module absent)
  test_an_agent_receiving_nothing_while_holding_a_grant_is_named_individually      RED (comparison module absent)
  test_no_delivery_branch_consults_a_body_token                                    RED (template_compiler still has the marker-gated
        {{my_skills_used}} branch: a token + a registry record doubles the section; a token with
        no registry record raises ValueError)
  test_population_is_derived_and_covers_every_platform_root                        RED (comparison module absent)
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import (  # noqa: E402
    REPO_ROOT,
    RETIRED_SKILLS_TOKEN,
    RETIRED_SPAWN_TOKEN,
    accounts,
    agent_prompts,
    agent_fm,
    compile_with,
    compiled_agent_roots,
    installed_skill_ids,
    layout_roots,
    make_skill,
    named_in_accounts,
    per_prompt_findings,
    real_declarations,
    source_templates,
    verdict_for,
    write_compiled_tree,
    write_template,
)

SKILLS = {
    "zz-alpha": "Alpha skill forges alpha widgets on request",
    "zz-beta": "Beta skill audits beta ledgers before release",
}
BODY = "# Agent\n\nDo the work.\n"


def _skills_root(tmp_path: Path) -> Path:
    root = tmp_path / "skills"
    for sid, desc in SKILLS.items():
        make_skill(root, sid, desc)
    return root


def _g(*ids: str) -> list[dict]:
    return [{"skill_id": i, "mode": "always"} for i in ids]


@pytest.mark.shared_layout_reader
def test_every_granted_agent_receives_its_abilities_with_no_marker_present_anywhere(shared_reference_layout):
    # covers: AR-300d-4
    # angle: deployed
    """AR-300d-4: with no definition carrying an opt-in marker (premise observed
    over every source template AND every compiled prompt: zero occurrences of the
    retired tokens), every agent holding a non-empty grant has its abilities named
    in its compiled prompt, in every platform root. GREEN-ALREADY via slice 1."""
    installed = installed_skill_ids(REPO_ROOT)
    roots = layout_roots(shared_reference_layout)
    declarations = real_declarations()
    sources = source_templates()
    assert len(roots) >= 2 and declarations and sources
    carriers = [t.name for t in sources
                if RETIRED_SKILLS_TOKEN in t.read_text(encoding="utf-8")
                or RETIRED_SPAWN_TOKEN in t.read_text(encoding="utf-8")]
    assert carriers == [], f"premise broken: templates carrying a marker: {carriers}"

    examined, missing = 0, []
    for root in roots:
        for prompt in agent_prompts(root):
            text = prompt.read_text(encoding="utf-8")
            assert RETIRED_SKILLS_TOKEN not in text, f"visible marker in {prompt}"
            if prompt.stem in declarations:
                examined += 1
                want = {e["skill_id"] if isinstance(e, dict) else e for e in declarations[prompt.stem]}
                if named_in_accounts(text, installed) != want:
                    missing.append((root.parent.name, prompt.stem))
    assert examined == len(declarations) * len(roots) > 0
    assert not missing, f"{len(missing)}/{examined} granted prompts do not name their grant: {missing[:5]}"


def test_both_population_counts_are_stated_and_zero_fails(tmp_path):
    # covers: AR-300d-4
    # angle: boundary
    """AR-300d-4: the run states agents examined AND agents found to hold a grant;
    either coming back zero FAILS rather than reading as delivery succeeded.
    Control: a healthy 2-agent tree states 4 / 2 and is ok."""
    templates = {
        "zz-granted": (agent_fm("zz-granted", _g("zz-alpha")), BODY),
        "zz-plain": (agent_fm("zz-plain"), BODY),
    }
    skills_root = _skills_root(tmp_path)
    roots = write_compiled_tree(tmp_path / "t", templates, skills_root)
    declarations = {"zz-granted": templates["zz-granted"][0]["skills"]}
    healthy = verdict_for(declarations, roots, expected=4, known=set(SKILLS))
    assert healthy["ok"] is True, healthy["findings"]
    assert (healthy["inspected_count"], healthy["granted_count"]) == (4, 1)

    no_prompts = [tmp_path / "void" / "agents"]
    no_prompts[0].mkdir(parents=True)
    zero_examined = verdict_for(declarations, no_prompts, expected=4, known=set(SKILLS))
    assert zero_examined["ok"] is False and zero_examined["inspected_count"] == 0

    no_grants = verdict_for({}, roots, expected=4, known=set(SKILLS))
    assert no_grants["ok"] is False and no_grants["granted_count"] == 0 and no_grants["inspected_count"] == 4


def test_an_agent_receiving_nothing_while_holding_a_grant_is_named_individually(tmp_path):
    # covers: AR-300d-4
    # angle: criterion
    """AR-300d-4: ONE granted agent whose compiled prompt lacks the section is
    named in the finding, per root -- not folded into a count -- while the other
    granted agents are not named. (The victim's prompt is compiled from a
    template that omits the grant, authentically reproducing 'granted but received
    nothing'.)"""
    skills_root = _skills_root(tmp_path)
    grant = _g("zz-alpha", "zz-beta")
    compiled_from = {f"zz-agent-{k}": (agent_fm(f"zz-agent-{k}", grant), BODY) for k in range(3)}
    compiled_from["zz-victim"] = (agent_fm("zz-victim"), BODY)  # prompt compiled WITHOUT the grant
    roots = write_compiled_tree(tmp_path / "t", compiled_from, skills_root)
    declarations = {stem: grant for stem in ("zz-agent-0", "zz-agent-1", "zz-agent-2", "zz-victim")}
    verdict = verdict_for(declarations, roots, expected=len(compiled_from) * len(roots), known=set(SKILLS))
    assert verdict["ok"] is False
    named = [f for f in per_prompt_findings(verdict) if f["kind"] == "undelivered"]
    assert sorted((f["agent"], f["platform_root"]) for f in named) == sorted(("zz-victim", str(r)) for r in roots)
    assert all(sorted(f["missing"]) == ["zz-alpha", "zz-beta"] for f in named)
    assert verdict["granted_count"] == 4


@pytest.mark.parametrize("registry_state", ["record_with_other_abilities", "record_absent", "no_registry"])
def test_no_delivery_branch_consults_a_body_token(tmp_path, registry_state):
    # covers: AR-300d-4
    # angle: real_artifact
    """AR-300d-4: adding the retired body token to a template changes NOTHING about
    whether or where the section is delivered -- one account, naming exactly the
    declaration (never the registry's different list), at the END of the prompt,
    identical from its heading onward to the no-token build. Proves the
    marker-gated branch is GONE rather than unused. Three registry states: a
    record naming OTHER abilities (a marker branch would substitute them at the
    token and double the section), no record (a marker branch raises), no
    registry. RED today: the compiler still honours ``{{my_skills_used}}``."""
    skills_root = _skills_root(tmp_path)
    fm = agent_fm("zz-marked", _g("zz-alpha"))
    body_plain = "# Agent\n\nDo the work.\n\n## Closing\n\nFinish cleanly.\n"
    body_token = f"# Agent\n\nDo the work.\n\n{RETIRED_SKILLS_TOKEN}\n\n## Closing\n\nFinish cleanly.\n"
    plain_tpl = write_template(tmp_path / "plain" / "zz-marked.md", fm, body_plain)
    token_tpl = write_template(tmp_path / "token" / "zz-marked.md", fm, body_token)
    assert RETIRED_SKILLS_TOKEN in token_tpl.read_text(encoding="utf-8") and RETIRED_SKILLS_TOKEN not in plain_tpl.read_text(encoding="utf-8")

    if registry_state == "record_with_other_abilities":
        agents = [{"id": "zz-marked", "template_path": "templates/agents/zz-marked.md", "skills_used": ["zz-beta"]}]
    elif registry_state == "record_absent":
        agents = [{"id": "someone-else", "template_path": "templates/agents/someone-else.md", "skills_used": ["zz-beta"]}]
    else:
        agents = None

    plain = compile_with(plain_tpl, agents=agents, skills_root=skills_root)
    marked = compile_with(token_tpl, agents=agents, skills_root=skills_root)
    for label, text in (("plain", plain), ("marked", marked)):
        found = accounts(text, set(SKILLS))
        assert len(found) == 1, f"{label}: {len(found)} accounts"
        assert named_in_accounts(text, set(SKILLS)) == {"zz-alpha"}, f"{label}: abilities other than the declaration"
        assert text.index("## Your Available Skills") > text.index("Finish cleanly."), f"{label}: section is not at the end"

    def tail(text: str) -> str:
        return text[text.index("## Your Available Skills"):]

    assert tail(marked) == tail(plain)


@pytest.mark.shared_layout_reader
def test_population_is_derived_and_covers_every_platform_root(shared_reference_layout, tmp_path):
    # covers: AR-300d-4
    # angle: deployed
    """AR-300d-4: the examined set is DERIVED from the prompts the build compiled
    and spans every platform root; no literal count appears in the assertion --
    proven by ADDING one granted agent to a copy of the compiled tree (a prompt
    in each root + its declaration) and watching the counts rise by exactly
    2 examined / 1 granted. A hard-coded 60 / 31 would not move."""
    installed = installed_skill_ids(REPO_ROOT)
    declarations = real_declarations()
    real_roots = compiled_agent_roots(shared_reference_layout)
    assert len(real_roots) >= 2 and declarations
    copies = []
    for root in real_roots:
        dst = tmp_path / root.relative_to(shared_reference_layout)
        shutil.copytree(root, dst)
        copies.append(dst)
    base_expected = len(source_templates()) * len(copies)
    base = verdict_for(declarations, copies, expected=base_expected, known=installed)
    assert base["inspected_count"] == base_expected
    assert sorted(base["roots_examined"]) == sorted(str(c) for c in copies)

    skill_id = sorted(installed)[0]
    extra_fm = agent_fm("zz-extra", _g(skill_id))
    tpl = write_template(tmp_path / "extra_src" / "zz-extra.md", extra_fm, BODY)
    text = compile_with(tpl, agents=None, skills_root=REPO_ROOT / "templates" / "skills")
    for root in copies:
        (root / "zz-extra.md").write_text(text, encoding="utf-8")
    grown = verdict_for({**declarations, "zz-extra": extra_fm["skills"]}, copies,
                        expected=base_expected + len(copies), known=installed)
    assert grown["inspected_count"] == base["inspected_count"] + len(copies)
    assert grown["granted_count"] == base["granted_count"] + 1
