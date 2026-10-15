"""AR-300c-2 -- the consolidation carried the UNION of both old registry ability
fields (skills_used, skills_invoked) into per-template frontmatter.

Source of truth: .../AR-300c-2.yaml. The consolidation itself has LANDED, so
these tests assert its OUTCOME: the committed templates (copied into a slice
whose registry is the frozen pre-consolidation snapshot, then passed through
the real commit-time transform hook) carry declarations equal to the union of
both old fields plus the pre-consolidation templates' own lists, minus
descriptive_only entries. See _ar_300c_support.py for the contract.

Fixture authenticity: the slice is the real on-disk templates and the frozen
real registry bytes; no hand-typed literals.
"""

from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300c_support import (  # noqa: E402
    GRANT_KEY,
    PRISTINE_TEMPLATES,
    REPO_ROOT,
    TEMPLATE_LEVEL_KEYS,
    copy_package_slice,
    declared_entries,
    declared_ids,
    descriptive_only_ids,
    expected_declared_ids,
    granted_ids,
    pristine_registry_agents,
    pristine_template_level,
    recorded_changes,
    registry_ids,
    template_frontmatter,
    template_only_grants,
    template_stem,
    transform_or_fail,
)

_CACHE: dict = {}


@pytest.fixture
def migrated(tmp_path_factory):
    """(pkg_root, pre-consolidation registry agents) after one real hook run."""
    if "m" not in _CACHE:
        pkg = copy_package_slice(tmp_path_factory.mktemp("ar300c2") / "pkg")
        transform_or_fail(pkg)
        _CACHE["m"] = (pkg, pristine_registry_agents())
    return _CACHE["m"]


@pytest.fixture
def template_level():
    """(ids_by_stem, template_level_keys_present_by_stem) of the frozen
    pre-consolidation templates (the third grant source)."""
    fms = {t.stem: template_frontmatter(t) for t in PRISTINE_TEMPLATES.glob("*.md")}
    keys = {s: {k for k in TEMPLATE_LEVEL_KEYS if k in fm} for s, fm in fms.items()}
    return pristine_template_level(), keys


def _populations(orig):
    used = {a["id"] for a in orig if registry_ids(a, "skills_used")}
    inv = {a["id"] for a in orig if registry_ids(a, "skills_invoked")}
    return used, inv


def _decl_for(pkg, agent):
    stem = template_stem(agent)
    if not stem:
        return None
    return template_frontmatter(pkg / "templates" / "agents" / f"{stem}.md")


def test_every_agent_named_in_either_field_has_a_declaration_afterwards(migrated, template_level):
    # covers: AR-300c-2
    # angle: real_artifact
    """AR-300c-2: the consolidated population is the UNION (not either field
    alone) -- includes the agents present in only one field. An agent whose
    every grant was later revoked (recorded in post_consolidation_changes.json)
    is not expected to declare anything."""
    pkg, orig = migrated
    tl, _keys = template_level
    used, inv = _populations(orig)
    union = used | inv
    only_one = union - (used & inv)
    assert union and only_one, "empty union / no single-field agents examined"
    missing = []
    examined = 0
    for a in orig:
        if a["id"] not in union or not template_stem(a) or not granted_ids(a):
            continue
        if not expected_declared_ids(a, tl):
            continue
        examined += 1
        fm = _decl_for(pkg, a)
        if not declared_ids(fm):
            missing.append(a["id"])
    assert examined > 0
    assert not missing, f"{len(missing)}/{examined} union agents lack a declaration: {missing}"


def test_each_agents_declared_abilities_are_the_union_of_both_records(migrated, template_level):
    # covers: AR-300c-2
    # angle: criterion
    """AR-300c-2: for agents whose two fields DIFFERED, the declaration holds the
    union -- no grant dropped (the union also spans the pre-consolidation
    template's own frontmatter lists). Wrong version caught: consolidating onto
    one field only. Exact set equality against the frozen union, adjusted only
    by the RECORDED later edits (post_consolidation_changes.json): an
    unrecorded revocation or addition fails here."""
    pkg, orig = migrated
    tl, _keys = template_level
    differing = 0
    for a in orig:
        u, i = set(registry_ids(a, "skills_used")), set(registry_ids(a, "skills_invoked"))
        if not granted_ids(a) or not template_stem(a):
            continue
        if u != i:
            differing += 1
        assert declared_ids(_decl_for(pkg, a)) == expected_declared_ids(a, tl), a["id"]
    assert differing > 0, "no agent with differing field contents was examined"


def test_no_agent_gains_an_ability_neither_field_recorded(migrated, template_level):
    # covers: AR-300c-2
    # angle: criterion
    """AR-300c-2: no declared ability appears that no source recorded (the old
    registry fields, the pre-consolidation template's own lists, or a RECORDED
    later addition in post_consolidation_changes.json)."""
    pkg, orig = migrated
    tl, _keys = template_level
    checked = 0
    for a in orig:
        if not template_stem(a):
            continue
        recorded = (set(registry_ids(a, "skills_used")) | set(registry_ids(a, "skills_invoked"))
                    | tl.get(template_stem(a), set())
                    | set(recorded_changes()["added"].get(template_stem(a), [])))
        got = declared_ids(_decl_for(pkg, a))
        checked += 1
        assert got <= recorded, (a["id"], sorted(got - recorded))
    assert checked > 0
    assert any(declared_ids(_decl_for(pkg, a)) for a in orig if template_stem(a)), \
        "nothing was declared at all"


def test_agent_in_neither_field_ends_with_no_declaration_key(migrated, template_level):
    # covers: AR-300c-2
    # angle: boundary
    """AR-300c-2: an ungranted agent has NO key (not an empty list) unless a
    RECORDED later grant exists for it. Control: granted agents do have it, so
    this is not 'no key written anywhere'."""
    pkg, orig = migrated
    tl, _keys = template_level
    used, inv = _populations(orig)
    union = used | inv
    ungranted = [a for a in orig if a["id"] not in union and template_stem(a)
                 and not expected_declared_ids(a, tl)]
    granted = [a for a in orig if a["id"] in union and template_stem(a) and granted_ids(a)
               and expected_declared_ids(a, tl)]
    assert ungranted and granted
    for a in ungranted:
        fm = _decl_for(pkg, a)
        assert GRANT_KEY not in fm, f"{a['id']} gained {GRANT_KEY}={fm.get(GRANT_KEY)!r}"
    assert all(GRANT_KEY in _decl_for(pkg, a) for a in granted)


def test_registry_ability_fields_are_regenerated_from_the_declarations(migrated):
    # covers: AR-300c-2
    # angle: seam
    """AR-300c-2 (it_requirements): the registry's ability field is regenerated
    from the declarations by the hook, so the derived copy is correct (id sets
    equal the declarations for every templated agent) and carries ONLY
    ``skills_invoked`` -- the retired ``skills_used`` is never written."""
    pkg, _orig = migrated
    data = json.loads((pkg / "config" / "agent_registry.json").read_text(encoding="utf-8"))
    checked = 0
    for a in data["agents"]:
        if not template_stem(a):
            continue
        decl = declared_ids(_decl_for(pkg, a))
        # descriptive_only entries are not grants: tolerated or dropped from the copy
        assert granted_ids(a) == decl, a["id"]
        assert "skills_used" not in a, a["id"]
        checked += 1
    assert checked > 30
    assert all(declared_entries(_decl_for(pkg, a)) is not None for a in data["agents"] if template_stem(a))


def _descriptive_population(agents):
    return {(a["id"], sid) for a in agents for sid in descriptive_only_ids(a)}


def test_descriptive_only_entries_are_not_written_into_any_declaration(migrated):
    # covers: AR-300c-2
    # angle: boundary
    """AR-300c-2 (descriptive_only rule): descriptive_only registry entries
    describe behaviour and are not grants, so no ``skills:`` declaration holds
    them. The population is DERIVED from the frozen registry (today
    python-coder/run-tests and documentation-expert/direct-write); zero fails.
    Control: the same agents DO have their real grants declared."""
    pkg, orig = migrated
    population = _descriptive_population(orig)
    assert population, "no descriptive_only entries found in the registry"
    by_id = {a["id"]: a for a in orig}
    for agent_id, skill_id in population:
        a = by_id[agent_id]
        decl = declared_ids(_decl_for(pkg, a))
        assert skill_id not in decl, f"{agent_id} declares descriptive-only {skill_id}"
        assert decl and granted_ids(a) <= decl, f"{agent_id}: real grants not declared"


def test_ids_granted_only_at_template_level_appear_in_the_migrated_declaration(migrated, template_level):
    # covers: AR-300c-2
    # angle: real_artifact
    """AR-300c-2 (third source): the union spans registry skills_used +
    registry skills_invoked + the pre-consolidation template's OWN frontmatter
    lists. Population DERIVED from the frozen templates (no agent names); empty
    fails. Every template-level id lands in that agent's ``skills:``
    declaration. Only the id is asserted -- no mode/condition for bare
    template-level grants."""
    pkg, orig = migrated
    tl, _keys = template_level
    only = template_only_grants(tl, orig)
    assert only, "no id is granted only at template level (third-source population is empty)"
    for stem, ids in tl.items():
        decl = declared_ids(template_frontmatter(pkg / "templates" / "agents" / f"{stem}.md"))
        assert ids <= decl, f"{stem}: template-level ids missing from declaration: {sorted(ids - decl)}"


def test_no_template_carries_a_template_level_grant_key_after_migration(template_level):
    # covers: AR-300c-1
    # angle: criterion
    """AR-300c-1/2: NO committed template has a template-level ``skills_used``
    or ``skills_invoked`` key, not even an empty one -- ``skills:`` is the single
    place. The population of templates that HAD one is derived from the frozen
    snapshots and must be non-empty."""
    _tl, keys = template_level
    had = {stem for stem, ks in keys.items() if ks}
    assert had, "no pristine template carried a template-level grant key"
    leftover = {}
    for stem in sorted(had):
        fm = template_frontmatter(REPO_ROOT / "templates" / "agents" / f"{stem}.md")
        left = [k for k in TEMPLATE_LEVEL_KEYS if k in fm]
        if left:
            leftover[stem] = left
    assert not leftover, f"template-level grant keys survive: {leftover}"
    for t in (REPO_ROOT / "templates" / "agents").glob("*.md"):
        assert not set(TEMPLATE_LEVEL_KEYS) & set(template_frontmatter(t)), t.name
