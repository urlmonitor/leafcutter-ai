"""AR-300c -- the DEPLOYED-layout checks of the AR-300c-1/-2/-3 contract.

These six tests read (or, for the one mutator, rebuild) the shared reference
build of the package, so they request the ``shared_reference_layout`` fixture.
They live apart from the other AR-300c modules on purpose: those six modules
are re-run by test_ar_400e_1_iv_helper_retired.py in an isolated copy of the
package with a bare pytest config (no plugins), where no deployed layout can be
produced, so every test in them must be fixture-free. The tests moved here
verbatim in intent (same ACs, same angles, same assertions) from:

* test_ar_300c_1_frontmatter_declaration.py
* test_ar_300c_2_consolidation.py
* test_ar_300c_3_derived_copy_comparison.py
* test_ar_300c_3_ii_registry_transform.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300c_support import (  # noqa: E402
    REPO_ROOT,
    compiled_agent_roots,
    declared_entries,
    declared_ids,
    descriptive_only_ids,
    granted_ids,
    installed_skill_ids,
    named_abilities,
    output_root_name,
    pristine_registry_agents,
    pristine_template_level,
    template_frontmatter,
    template_only_grants,
    template_stem,
)
from test_ar_300c_3_ii_registry_transform import (  # noqa: E402
    SPAWN,
    _compare_findings,
    _hook_or_fail,
    _prepared,
    _prepared_spawn,
    _records,
)


@pytest.mark.shared_layout_reader
def test_compiled_prompt_abilities_equal_the_frontmatter_declaration(shared_reference_layout):
    # covers: AR-300c-1
    # angle: deployed
    """AR-300c-1: abilities in each compiled prompt are exactly the template's
    frontmatter declaration, in EVERY platform root."""
    layout = shared_reference_layout  # deployed target: compiled prompts only
    # The shared layout is built from this worktree's source, so the source
    # declarations (population) live under REPO_ROOT; evidence is the layout.
    installed = installed_skill_ids(REPO_ROOT)
    roots = compiled_agent_roots(layout)
    assert len(roots) >= 2, f"expected claude + gemini agent roots, found {roots}"
    src_agents = REPO_ROOT / "templates" / "agents"
    assert any(src_agents.glob("*.md")), "source templates not found"

    declaring = {}
    for tpl in sorted(src_agents.glob("*.md")):
        if tpl.name.startswith("_"):
            continue
        ids = declared_ids(template_frontmatter(tpl)) & installed
        if ids:
            declaring[tpl.name] = ids
    assert declaring, "0 templates declare abilities in frontmatter (examined 0) -- empty population fails"

    wrong = []
    for name, ids in declaring.items():
        for root in roots:
            compiled = (root / name).read_text(encoding="utf-8")
            got = named_abilities(compiled, installed)
            if got != ids:
                wrong.append((root.name, name, sorted(ids ^ got)))
    assert not wrong, f"{len(declaring)} declaring agents x {len(roots)} roots; mismatches: {wrong[:5]}"


@pytest.mark.shared_layout_reader
def test_descriptive_only_entries_are_absent_from_compiled_prompts(shared_reference_layout):
    # covers: AR-300c-2
    # angle: deployed
    """AR-300c-2 (descriptive_only rule): in EVERY platform root the compiled
    prompt of each agent carrying a descriptive_only entry (a) names its real
    grants (positive control -- otherwise absence of the descriptive id would
    hold vacuously on an undelivered tree) and (b) never mentions the
    descriptive id."""
    layout = shared_reference_layout
    installed = installed_skill_ids(REPO_ROOT)
    roots = compiled_agent_roots(layout)
    assert len(roots) >= 2
    agents = pristine_registry_agents()
    population = {(a["id"], sid) for a in agents for sid in descriptive_only_ids(a)}
    assert population
    by_id = {a["id"]: a for a in agents}
    for agent_id, skill_id in sorted(population):
        a = by_id[agent_id]
        # Positive control against the CURRENT declaration (the source of truth), not the
        # frozen pre-consolidation registry: a grant legitimately added later
        # (python-coder/complexity-reduction, once main shipped that skill) must not read
        # as a defect here (same rule as AR-300d-3 / decision 12).
        declared = declared_ids(template_frontmatter(REPO_ROOT / "templates" / "agents" / f"{template_stem(a)}.md"))
        assert granted_ids(a) & installed <= declared, (agent_id, "a pre-migration grant was lost")
        for root in roots:
            text = (root / f"{template_stem(a)}.md").read_text(encoding="utf-8")
            assert named_abilities(text, installed) == declared & installed, (agent_id, root.name)
            assert skill_id not in text, f"{agent_id} compiled prompt mentions {skill_id} ({root.name})"


@pytest.mark.shared_layout_reader
def test_template_level_only_grants_are_named_in_compiled_prompts_of_every_root(shared_reference_layout):
    # covers: AR-300c-2
    # angle: deployed
    """AR-300c-2 (user-visible symptom): in EVERY platform root, each agent
    holding a template-level-only grant (derived; today product-owner and
    business-analyst hold ac-tree-split) names that ability in its compiled
    prompt."""
    layout = shared_reference_layout
    installed = installed_skill_ids(REPO_ROOT)
    roots = compiled_agent_roots(layout)
    assert len(roots) >= 2
    only = template_only_grants(pristine_template_level(), pristine_registry_agents())
    only = {s: ids & installed for s, ids in only.items() if ids & installed}
    assert only, "no installed template-level-only grant to deliver"
    for stem, ids in sorted(only.items()):
        for root in roots:
            text = (root / f"{stem}.md").read_text(encoding="utf-8")
            got = named_abilities(text, installed)
            assert ids <= got, f"{stem} ({root.name}) does not name {sorted(ids - got)}"


@pytest.mark.shared_layout_mutator
def test_hand_edited_central_record_is_reported_with_both_ability_sets(shared_reference_layout):
    # covers: AR-300c-3
    # angle: criterion
    """AR-300c-3: hand-edit one agent's registry record (inputs otherwise
    correct), rebuild the private copy with the real build.py. Per the user
    decision of 2026-10-09 the build REPORTS and does NOT refuse: it exits 0,
    its output names the agent, the declaration's abilities and the record's
    abilities, the compiled prompts (every platform root) still name the
    declaration's abilities, and the build did NOT write to the source tree
    (config/agent_registry.json is byte-identical to the hand-edited bytes --
    only the pre-commit transform hook regenerates the derived copy)."""
    layout = shared_reference_layout
    installed = installed_skill_ids(layout)
    victim = None
    for tpl in sorted((layout / "templates" / "agents").glob("*.md")):
        if tpl.name.startswith("_"):
            continue
        entries = declared_entries(template_frontmatter(tpl))
        if entries:
            victim = (tpl.stem, {e["skill_id"] for e in entries})
            break
    assert victim, "0 templates declare abilities -- nothing to disagree with"
    agent_id_stem, declared = victim
    other = sorted(installed - declared)[0]

    reg_path = layout / "config" / "agent_registry.json"
    data = json.loads(reg_path.read_text(encoding="utf-8"))
    for a in data["agents"]:
        if template_stem(a) == agent_id_stem:
            agent_id = a["id"]
            a["skills_invoked"] = [{"skill_id": other, "mode": "always"}]
    reg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    edited_bytes = reg_path.read_bytes()

    proc = subprocess.run(
        [sys.executable, str(layout / "scripts" / "build.py"), "--target-dir", str(layout)],
        cwd=str(layout), capture_output=True, text=True, timeout=300, check=False,
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, f"build refused a hand-edited central record (exit {proc.returncode}): {out[-600:]}"
    assert agent_id in out
    assert other in out
    assert all(d in out for d in declared)
    # the declaration wins: compiled prompts still name exactly the declared abilities
    roots = compiled_agent_roots(layout)
    assert len(roots) >= 2
    for root in roots:
        text = (root / f"{agent_id_stem}.md").read_text(encoding="utf-8")
        assert named_abilities(text, installed) == declared & installed, root.name
    # the build never writes the package source tree
    assert reg_path.read_bytes() == edited_bytes, "build modified config/agent_registry.json"


@pytest.mark.shared_layout_reader
def test_deployed_transform_hook_regenerates_the_copy_from_the_deployed_layout(shared_reference_layout, tmp_path):
    # covers: AR-300c-3
    # angle: deployed
    """AR-300c-3: the hook runs from the DEPLOYED layout (a build output), not
    just the source tree -- its dependencies must be in the deploy manifest or it
    is a silent no-op / ModuleNotFoundError in every consumer. Same regeneration
    result as the source-tree run."""
    layout = shared_reference_layout
    deployed = layout / output_root_name(layout) / "scripts" / "commit_guardian" / "transform_agent_registry.py"
    assert deployed.is_file(), f"hook not deployed: {deployed}"
    pkg, edited, _s1 = _prepared(tmp_path)
    assert _compare_findings(pkg), "no divergence to repair"
    _hook_or_fail(deployed, pkg)
    assert _compare_findings(pkg) == []


@pytest.mark.shared_layout_reader
def test_deployed_transform_hook_regenerates_spawn_allowlist_from_the_deployed_layout(shared_reference_layout, tmp_path):
    # covers: AR-300c-5-ii
    # angle: deployed
    """AR-300c-5-ii: the DEPLOYED hook (a build output, run from <output_root>/scripts/
    commit_guardian/) regenerates the spawn lists exactly as the source-tree run does -- the
    spawn-side helper it imports must be deployed with it, or it is a silent no-op /
    ModuleNotFoundError in every consumer."""
    layout = shared_reference_layout
    deployed = layout / output_root_name(layout) / "scripts" / "commit_guardian" / "transform_agent_registry.py"
    assert deployed.is_file(), f"hook not deployed: {deployed}"
    pkg, roles, _s1 = _prepared_spawn(tmp_path)
    assert sorted(_records(pkg)[roles["undeclared"]][SPAWN]) != [], "control: nothing to regenerate"
    _hook_or_fail(deployed, pkg)
    after = _records(pkg)
    assert after[roles["undeclared"]][SPAWN] == [] and after[roles["added"]][SPAWN] == ["research-agent"]
    assert roles["dropped"] not in after[roles["revoked"]][SPAWN]
