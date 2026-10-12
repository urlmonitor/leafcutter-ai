"""AR-300c-2-i -- an agent recorded in only ONE of the two registry ability
fields arrives with exactly that field's abilities in its COMPILED prompt.

Evidence is the compiled prompt, never the migrated declaration. The tree
compiled is the MIGRATED PRISTINE COPY (real migration CLI over
``copy_package_slice()``, every migrated template compiled in-process with the
real ``compile_agent_template``): this pins the property "the migration carries
each single-field agent's grants into its compiled prompt". It deliberately does
NOT read the real tree, because a later legitimate revocation there (AR-300d-3,
e.g. a stale ``signoff`` grant removed from an agent with ``signoff: false``)
must not break a migration test. The single-field populations are DERIVED by
differencing the PRISTINE registry fields at run time -- no enumerated names.

RED BASELINE: before the migration existed these failed with "migration CLI
failed". Expected sets are intersected with INSTALLED skill ids (the registry
holds e.g. ``run-tests``, which no templates/skills dir provides), so the
comparison stays about delivery. The platform-root duplication (claude/gemini)
is a build step, covered by the AR-300a delivery tests; here one compiled
prompt per agent is the unit.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300c_support import (  # noqa: E402
    REPO_ROOT,
    add_registry_agent,
    compile_template,
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

_CACHE: dict = {}


def _compiled_migrated(tmp_path_factory) -> dict[str, str]:
    """stem -> compiled prompt, from the real migration over a pristine copy."""
    if "texts" not in _CACHE:
        pkg = copy_package_slice(tmp_path_factory.mktemp("ar300c2i") / "pkg")
        migrate_or_fail(pkg)
        agents = registry_agents(pkg)
        reg_path = pkg / "config" / "agent_registry.json"
        _CACHE["texts"] = {
            tpl.stem: compile_template(tpl, agents, reg_path)
            for tpl in sorted((pkg / "templates" / "agents").glob("*.md"))
            if not tpl.name.startswith("_")
        }
    return _CACHE["texts"]


def _single_field_populations(agents):
    newer_only = [a for a in agents if registry_ids(a, "skills_invoked") and not registry_ids(a, "skills_used")]
    older_only = [a for a in agents if registry_ids(a, "skills_used") and not registry_ids(a, "skills_invoked")]
    return newer_only, older_only


def _check_population(texts, population, field, installed):
    bad = []
    tl = pristine_template_level()  # the template's own lists are a third grant source
    for a in population:
        stem = template_stem(a)
        expect = (set(registry_ids(a, field)) | tl.get(stem, set())) & installed
        if stem not in texts:
            bad.append((a["id"], "no compiled prompt"))
            continue
        got = named_abilities(texts[stem], installed)
        if got != expect:
            bad.append((a["id"], sorted(got ^ expect)))
    return bad


def test_each_newer_field_only_agent_receives_exactly_that_fields_abilities(tmp_path_factory):
    # covers: AR-300c-2-i
    # angle: deployed
    """AR-300c-2-i: every newer-field-only agent (derived), checked
    individually, names exactly that field's abilities in its compiled prompt
    (migrated pristine copy compiled with the real compiler)."""
    texts = _compiled_migrated(tmp_path_factory)
    installed = installed_skill_ids(REPO_ROOT)
    newer_only, _ = _single_field_populations(pristine_registry_agents())
    templated = [a for a in newer_only if template_stem(a)]
    assert templated, "derived newer-only population is empty"
    bad = _check_population(texts, templated, "skills_invoked", installed)
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


def test_older_field_only_agent_is_treated_identically(tmp_path_factory, tmp_path):
    # covers: AR-300c-2-i
    # angle: boundary
    """AR-300c-2-i: older-field-only agents get exactly that field's abilities;
    when the real registry has none the case is CONSTRUCTED, never skipped."""
    texts = _compiled_migrated(tmp_path_factory)
    installed = installed_skill_ids(REPO_ROOT)
    _, older_only = _single_field_populations(pristine_registry_agents())
    templated = [a for a in older_only if template_stem(a)]
    if templated:
        bad = _check_population(texts, templated, "skills_used", installed)
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


def test_derived_population_size_is_reported_and_zero_fails(tmp_path_factory):
    # covers: AR-300c-2-i
    # angle: boundary
    """AR-300c-2-i: state the derived single-field population size; zero fails;
    delivered count must equal population size (short also fails)."""
    texts = _compiled_migrated(tmp_path_factory)
    installed = installed_skill_ids(REPO_ROOT)
    newer_only, older_only = _single_field_populations(pristine_registry_agents())
    population = [a for a in newer_only + older_only if template_stem(a)]
    n = len(population)
    print(f"single-field population examined: {n}")
    assert n > 0, "derived single-field population is 0 -- vacuous"
    delivered = sum(
        1 for a in population
        if template_stem(a) in texts and named_abilities(texts[template_stem(a)], installed)
    )
    assert delivered == n, f"delivered {delivered} of {n} single-field agents"
