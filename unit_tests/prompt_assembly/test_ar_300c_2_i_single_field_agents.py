"""AR-300c-2-i -- an agent recorded in only ONE of the two registry ability
fields arrives with exactly that field's abilities in its COMPILED prompt.

Evidence is the compiled prompt (shared layout, every platform root), never
the migrated declaration. The single-field populations are DERIVED by
differencing the registry fields at run time -- no enumerated agent names.

RED BASELINE: no compiled prompt carries an abilities section today (and the
migration tool does not exist), so population checks / named-set equality
fail with AssertionError (or "migration CLI failed" for the planted cases).
Expected sets are intersected with INSTALLED skill ids (the registry holds
e.g. ``run-tests``, which no templates/skills dir provides -- AR-300c-3-i's
territory), so the comparison stays about delivery.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300c_support import (  # noqa: E402
    REPO_ROOT,
    add_registry_agent,
    compile_template,
    compiled_agent_roots,
    copy_package_slice,
    installed_skill_ids,
    migrate_or_fail,
    named_abilities,
    pristine_registry_agents,
    pristine_template_level,
    registry_agents,
    registry_ids,
    template_stem,
    write_template,
)


def _single_field_populations(agents):
    newer_only = [a for a in agents if registry_ids(a, "skills_invoked") and not registry_ids(a, "skills_used")]
    older_only = [a for a in agents if registry_ids(a, "skills_used") and not registry_ids(a, "skills_invoked")]
    return newer_only, older_only


def _check_population(layout, population, field, installed, roots):
    bad = []
    tl = pristine_template_level()  # the template's own lists are a third grant source
    for a in population:
        stem = template_stem(a)
        expect = (set(registry_ids(a, field)) | tl.get(stem, set())) & installed
        for root in roots:
            path = root / f"{stem}.md"
            if not path.is_file():
                bad.append((a["id"], root.name, "no compiled prompt"))
                continue
            got = named_abilities(path.read_text(encoding="utf-8"), installed)
            if got != expect:
                bad.append((a["id"], root.name, sorted(got ^ expect)))
    return bad


@pytest.mark.shared_layout_reader
def test_each_newer_field_only_agent_receives_exactly_that_fields_abilities(shared_reference_layout):
    # covers: AR-300c-2-i
    # angle: deployed
    """AR-300c-2-i: every newer-field-only agent (derived), checked
    individually in every platform root, names exactly that field's abilities."""
    layout = shared_reference_layout  # deployed target; registry source is REPO_ROOT
    installed = installed_skill_ids(REPO_ROOT)
    roots = compiled_agent_roots(layout)
    assert len(roots) >= 2
    newer_only, _ = _single_field_populations(pristine_registry_agents())
    templated = [a for a in newer_only if template_stem(a)]
    assert templated, "derived newer-only population is empty"
    bad = _check_population(layout, templated, "skills_invoked", installed, roots)
    assert not bad, f"{len(templated)} newer-only agents examined; failures: {bad[:6]}"


def test_the_single_field_population_is_derived_not_enumerated(tmp_path):
    # covers: AR-300c-2-i
    # angle: criterion
    """AR-300c-2-i: add an agent to ONE field alone (no test edit) and it is in
    scope -- migration + compile deliver exactly its abilities. Wrong version
    caught: a hard-coded list of twelve names / delivery keyed off skills_used."""
    pkg = copy_package_slice(tmp_path / "pkg")
    add_registry_agent(pkg, {
        "id": "zz-newer-only", "template_path": "templates/agents/zz-newer-only.md",
        "skills_used": [],
        "skills_invoked": [{"skill_id": "route-knowledge", "mode": "always"},
                           {"skill_id": "ticket-wiring", "mode": "conditional"}],
    })
    tpl = write_template(pkg / "templates" / "agents" / "zz-newer-only.md",
                         {"name": "zz-newer-only", "description": "d", "model": "sonnet", "tools": "Read"})
    migrate_or_fail(pkg)
    out = compile_template(tpl, registry_agents(pkg), pkg / "config" / "agent_registry.json")
    assert named_abilities(out, installed_skill_ids(REPO_ROOT)) == {"route-knowledge", "ticket-wiring"}


@pytest.mark.shared_layout_reader
def test_older_field_only_agent_is_treated_identically(shared_reference_layout, tmp_path):
    # covers: AR-300c-2-i
    # angle: boundary
    """AR-300c-2-i: older-field-only agents get exactly that field's abilities;
    when the real registry has none the case is CONSTRUCTED, never skipped."""
    layout = shared_reference_layout  # deployed target; registry source is REPO_ROOT
    installed = installed_skill_ids(REPO_ROOT)
    roots = compiled_agent_roots(layout)
    assert len(roots) >= 2
    _, older_only = _single_field_populations(pristine_registry_agents())
    templated = [a for a in older_only if template_stem(a)]
    if templated:
        bad = _check_population(layout, templated, "skills_used", installed, roots)
        assert not bad, f"{len(templated)} older-only agents examined; failures: {bad[:6]}"

    # constructed symmetric case (always run: guards the empty-set vacuity)
    pkg = copy_package_slice(tmp_path / "pkg")
    add_registry_agent(pkg, {
        "id": "zz-older-only", "template_path": "templates/agents/zz-older-only.md",
        "skills_used": ["route-knowledge", "ticket-wiring"], "skills_invoked": [],
    })
    tpl = write_template(pkg / "templates" / "agents" / "zz-older-only.md",
                         {"name": "zz-older-only", "description": "d", "model": "sonnet", "tools": "Read"})
    migrate_or_fail(pkg)
    out = compile_template(tpl, registry_agents(pkg), pkg / "config" / "agent_registry.json")
    assert named_abilities(out, installed_skill_ids(REPO_ROOT)) == {"route-knowledge", "ticket-wiring"}


@pytest.mark.shared_layout_reader
def test_derived_population_size_is_reported_and_zero_fails(shared_reference_layout):
    # covers: AR-300c-2-i
    # angle: boundary
    """AR-300c-2-i: state the derived single-field population size; zero fails;
    delivered count must equal population size (short also fails)."""
    layout = shared_reference_layout  # deployed target; registry source is REPO_ROOT
    installed = installed_skill_ids(REPO_ROOT)
    roots = compiled_agent_roots(layout)
    newer_only, older_only = _single_field_populations(pristine_registry_agents())
    population = [a for a in newer_only + older_only if template_stem(a)]
    n = len(population)
    print(f"single-field population examined: {n}")
    assert n > 0, "derived single-field population is 0 -- vacuous"
    delivered = 0
    for a in population:
        if all(
            (root / f"{template_stem(a)}.md").is_file()
            and named_abilities((root / f"{template_stem(a)}.md").read_text(encoding="utf-8"), installed)
            for root in roots
        ):
            delivered += 1
    assert roots and delivered == n, f"delivered {delivered} of {n} single-field agents"
