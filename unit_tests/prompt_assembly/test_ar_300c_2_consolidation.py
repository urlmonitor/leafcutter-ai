"""AR-300c-2 -- the consolidation carries the UNION of both registry ability
fields (skills_used, skills_invoked) into per-template frontmatter, and
reports what it did with each agent.

Source of truth: .../AR-300c-2.yaml. Contract assumed (see
_ar_300c_support.py): ``python scripts/migrate_agent_abilities.py
--package-root DIR --report PATH``; report ``counts`` keys are
``skills_used`` / ``skills_invoked`` / ``union`` (the AC says "the three
counts" without naming them -- flagged to the caller).

All tests run the REAL migration CLI as a subprocess over a copy of the REAL
templates + registry (fixture authenticity: real on-disk artifacts, no
hand-typed literals). RED BASELINE: scripts/migrate_agent_abilities.py does not
exist, so every migrate_or_fail() assertion fails ("migration CLI failed").
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300c_support import (  # noqa: E402
    GRANT_KEY,
    REPO_ROOT,
    compiled_agent_roots,
    copy_package_slice,
    declared_entries,
    declared_ids,
    descriptive_only_ids,
    granted_ids,
    installed_skill_ids,
    migrate_or_fail,
    named_abilities,
    pristine_registry_agents,
    pristine_template_level,
    registry_agents,
    registry_ids,
    strip_frontmatter_keys,
    template_frontmatter,
    template_level_ids,
    template_stem,
    TEMPLATE_LEVEL_KEYS,
)

_CACHE: dict = {}


@pytest.fixture
def migrated(tmp_path_factory):
    """(pkg_root, report, original_registry_agents) from one real migration run."""
    if "m" not in _CACHE:
        pkg = copy_package_slice(tmp_path_factory.mktemp("ar300c2") / "pkg")
        orig = registry_agents(pkg)
        # third source, captured from the PRISTINE copy before the migration runs
        tpl_dir = pkg / "templates" / "agents"
        fms = {t.stem: template_frontmatter(t) for t in tpl_dir.glob("*.md")}
        _CACHE["tl"] = {s: template_level_ids(fm) for s, fm in fms.items()}
        _CACHE["tl_keys"] = {s: {k for k in TEMPLATE_LEVEL_KEYS if k in fm} for s, fm in fms.items()}
        report = migrate_or_fail(pkg)
        _CACHE["m"] = (pkg, report, orig)
    return _CACHE["m"]


@pytest.fixture
def template_level(migrated):
    """(ids_by_stem, template_level_keys_present_by_stem) of the pristine input."""
    return _CACHE["tl"], _CACHE["tl_keys"]


def _populations(orig):
    used = {a["id"] for a in orig if registry_ids(a, "skills_used")}
    inv = {a["id"] for a in orig if registry_ids(a, "skills_invoked")}
    return used, inv


def _decl_for(pkg, agent):
    stem = template_stem(agent)
    if not stem:
        return None
    return template_frontmatter(pkg / "templates" / "agents" / f"{stem}.md")


def test_every_agent_named_in_either_field_has_a_declaration_afterwards(migrated):
    # covers: AR-300c-2
    # angle: real_artifact
    """AR-300c-2: the consolidated population is the UNION (not either field
    alone) -- includes the agents present in only one field."""
    pkg, _report, orig = migrated
    used, inv = _populations(orig)
    union = used | inv
    only_one = union - (used & inv)
    assert union and only_one, "empty union / no single-field agents examined"
    missing = []
    examined = 0
    for a in orig:
        if a["id"] not in union or not template_stem(a) or not granted_ids(a):
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
    """AR-300c-2: for agents whose two fields DIFFER, the declaration holds the
    union -- no grant dropped (the union also spans the template's own
    frontmatter lists). Wrong version caught: consolidating onto one field only."""
    pkg, _report, orig = migrated
    tl, _keys = template_level
    differing = 0
    for a in orig:
        u, i = set(registry_ids(a, "skills_used")), set(registry_ids(a, "skills_invoked"))
        if not granted_ids(a) or not template_stem(a):
            continue
        if u != i:
            differing += 1
        expect = granted_ids(a) | tl.get(template_stem(a), set())
        assert declared_ids(_decl_for(pkg, a)) == expect, a["id"]
    assert differing > 0, "no agent with differing field contents was examined"


def test_no_agent_gains_an_ability_neither_field_recorded(migrated, template_level):
    # covers: AR-300c-2
    # angle: criterion
    """AR-300c-2: no declared ability appears that no source recorded (registry
    fields or the template's own lists)."""
    pkg, _report, orig = migrated
    tl, _keys = template_level
    checked = 0
    for a in orig:
        if not template_stem(a):
            continue
        recorded = (set(registry_ids(a, "skills_used")) | set(registry_ids(a, "skills_invoked"))
                    | tl.get(template_stem(a), set()))
        got = declared_ids(_decl_for(pkg, a))
        checked += 1
        assert got <= recorded, (a["id"], sorted(got - recorded))
    assert checked > 0
    assert any(declared_ids(_decl_for(pkg, a)) for a in orig if template_stem(a)), \
        "nothing was declared at all"


def test_migration_reports_each_agent_by_name_with_its_provenance_and_the_three_counts(migrated):
    # covers: AR-300c-2
    # angle: criterion
    """AR-300c-2: report names every agent in either field, which side(s) its
    abilities came from, and the three counts (older, newer, union)."""
    pkg, report, orig = migrated
    used, inv = _populations(orig)
    union = used | inv
    counts = report["counts"]
    # tie the report to the files: reported abilities == what was declared
    by_id = {a["id"]: a for a in orig}
    tied = 0
    for row in report["agents"]:
        a = by_id.get(row["agent"])
        if a is not None and template_stem(a) and granted_ids(a):
            assert set(row["abilities"]) == declared_ids(_decl_for(pkg, a)), row["agent"]
            tied += 1
    assert tied > 0, "no report row could be tied to a migrated template"
    assert counts == {"skills_used": len(used), "skills_invoked": len(inv), "union": len(union)}
    by_agent = {r["agent"]: r for r in report["agents"]}
    assert set(by_agent) >= union
    for agent in union:
        expect = {s for s, pop in (("skills_used", used), ("skills_invoked", inv)) if agent in pop}
        # template-level provenance entries are checked separately; compare the registry side here
        registry_sources = {s for s in by_agent[agent]["sources"] if "template" not in s}
        assert registry_sources == expect, agent
    assert len(used) != len(union) != len(inv), "degenerate counts cannot distinguish union from either side"


def test_agent_in_neither_field_ends_with_no_declaration_key(migrated):
    # covers: AR-300c-2
    # angle: boundary
    """AR-300c-2: an ungranted agent gains NO key (not an empty list). Control:
    granted agents do have it, so this is not 'no key written anywhere'."""
    pkg, _report, orig = migrated
    used, inv = _populations(orig)
    union = used | inv
    ungranted = [a for a in orig if a["id"] not in union and template_stem(a)]
    granted = [a for a in orig if a["id"] in union and template_stem(a) and granted_ids(a)]
    assert ungranted and granted
    for a in ungranted:
        fm = _decl_for(pkg, a)
        assert GRANT_KEY not in fm, f"{a['id']} gained {GRANT_KEY}={fm.get(GRANT_KEY)!r}"
    assert all(GRANT_KEY in _decl_for(pkg, a) for a in granted)


def test_running_the_migration_twice_is_byte_stable(tmp_path):
    # covers: AR-300c-2
    # angle: real_artifact
    """AR-300c-2: second run over the migrated tree is byte-identical (all
    templates AND the regenerated registry)."""
    pkg = copy_package_slice(tmp_path / "pkg")
    migrate_or_fail(pkg)

    def snapshot():
        files = sorted((pkg / "templates" / "agents").glob("*.md")) + [pkg / "config" / "agent_registry.json"]
        return {str(f.relative_to(pkg)): f.read_bytes() for f in files}

    first = snapshot()
    migrate_or_fail(pkg)
    second = snapshot()
    assert len(first) > 30
    migrated_templates = [
        t for t in (pkg / "templates" / "agents").glob("*.md") if GRANT_KEY in template_frontmatter(t)
    ]
    assert migrated_templates, "migration declared nothing (no template carries the key)"
    assert first == second


def test_migration_inserts_only_the_new_key_and_leaves_other_frontmatter_untouched(tmp_path):
    # covers: AR-300c-2
    # angle: real_artifact
    """AR-300c-2: the only permitted changes to a template are (1) ADD the
    ``skills:`` key and (2) REMOVE the template-level ``skills_used`` /
    ``skills_invoked`` keys (the declaration is the single place). Every other
    original line survives, in order, byte-identical (including the
    comma-separated ``tools:`` string); bodies identical."""
    pkg = copy_package_slice(tmp_path / "pkg")
    originals = {p.name: p.read_text(encoding="utf-8") for p in (pkg / "templates" / "agents").glob("*.md")}
    registry_grants = {template_stem(a): granted_ids(a) for a in pristine_registry_agents() if template_stem(a)}
    migrate_or_fail(pkg)
    changed = 0
    for name, before in originals.items():
        after = (pkg / "templates" / "agents" / name).read_text(encoding="utf-8")
        if after == before:
            continue
        changed += 1
        permitted_before, _n = strip_frontmatter_keys(before, TEMPLATE_LEVEL_KEYS)
        it = iter(after.splitlines())
        assert all(any(line == nxt for nxt in it) for line in permitted_before.splitlines()), \
            f"{name}: original lines (minus template-level grant keys) not preserved in order"
        from template_compiler import parse_frontmatter
        fm_b, body_b = parse_frontmatter(before)
        fm_a, body_a = parse_frontmatter(after)
        assert body_a == body_b, f"{name}: body touched"
        removable = set(TEMPLATE_LEVEL_KEYS) | {GRANT_KEY}
        assert {k: v for k, v in fm_a.items() if k != GRANT_KEY} == \
            {k: v for k, v in fm_b.items() if k not in TEMPLATE_LEVEL_KEYS}, name
        assert GRANT_KEY not in fm_b
        # "has grants" is derived from the data: pristine registry fields (minus
        # descriptive_only) plus the template's own pre-migration lists.
        has_grants = bool(registry_grants.get(Path(name).stem, set()) | template_level_ids(fm_b))
        if has_grants:
            assert GRANT_KEY in fm_a, f"{name}: has grants but gained no {GRANT_KEY}"
        else:
            # nothing granted anywhere: no declaration key (not even empty); the
            # only change is the removal of the template-level keys (checked above)
            assert GRANT_KEY not in fm_a, f"{name}: no grants yet gained {GRANT_KEY}={fm_a.get(GRANT_KEY)!r}"
        assert not (removable - {GRANT_KEY}) & set(fm_a), f"{name}: template-level grant key left behind"
    assert changed > 0, "no template was migrated"


def test_registry_ability_fields_are_regenerated_from_the_declarations(migrated):
    # covers: AR-300c-2
    # angle: seam
    """AR-300c-2 (it_requirements): the registry's ability fields survive and
    are regenerated from the declarations, so the derived copy is correct on day
    one (id sets equal the declarations for every templated agent)."""
    pkg, _report, _orig = migrated
    data = json.loads((pkg / "config" / "agent_registry.json").read_text(encoding="utf-8"))
    checked = 0
    for a in data["agents"]:
        if not template_stem(a):
            continue
        decl = declared_ids(_decl_for(pkg, a))
        # descriptive_only entries are not grants: tolerated or dropped from the copy
        assert granted_ids(a) == decl, a["id"]
        checked += 1
    assert checked > 30
    assert all(declared_entries(_decl_for(pkg, a)) is not None for a in data["agents"] if template_stem(a))


def _descriptive_population(agents):
    return {(a["id"], sid) for a in agents for sid in descriptive_only_ids(a)}


def test_descriptive_only_entries_are_not_written_into_any_declaration(migrated):
    # covers: AR-300c-2
    # angle: boundary
    """AR-300c-2 (descriptive_only rule): descriptive_only registry entries
    describe behaviour and are not grants, so no migrated ``skills:``
    declaration holds them. The population is DERIVED from the registry
    (today python-coder/run-tests and documentation-expert/direct-write);
    zero fails. Control: the same agents DO get their real grants declared."""
    pkg, _report, orig = migrated
    population = _descriptive_population(orig)
    assert population, "no descriptive_only entries found in the registry"
    by_id = {a["id"]: a for a in orig}
    for agent_id, skill_id in population:
        a = by_id[agent_id]
        decl = declared_ids(_decl_for(pkg, a))
        assert skill_id not in decl, f"{agent_id} declares descriptive-only {skill_id}"
        assert decl == granted_ids(a) and decl, f"{agent_id}: real grants not declared"


def test_descriptive_only_entries_are_listed_in_the_report_exclusions(migrated):
    # covers: AR-300c-2
    # angle: criterion
    """AR-300c-2 (descriptive_only rule): the report's ``excluded`` list names
    every descriptive_only entry left out, by agent and id, with a reason."""
    pkg, report, orig = migrated
    population = _descriptive_population(orig)
    assert population
    # tie the report to the files: a left-out entry means the agent's REAL
    # grants were migrated and the excluded id was not
    by_id = {a["id"]: a for a in orig}
    for agent_id, skill_id in population:
        decl = declared_ids(_decl_for(pkg, by_id[agent_id]))
        assert decl and skill_id not in decl, (agent_id, skill_id)
    excluded = report.get("excluded")
    assert isinstance(excluded, list), "report has no `excluded` list"
    got = {(e["agent"], e["skill_id"]) for e in excluded}
    assert got == population
    assert all(isinstance(e.get("reason"), str) and e["reason"].strip() for e in excluded)


@pytest.mark.shared_layout_reader
def test_descriptive_only_entries_are_absent_from_compiled_prompts(shared_reference_layout):
    # covers: AR-300c-2
    # angle: deployed
    """AR-300c-2 (descriptive_only rule): in EVERY platform root the compiled
    prompt of each agent carrying a descriptive_only entry (a) names its real
    grants (positive control -- otherwise absence of the descriptive id would
    hold vacuously on an undelivered tree) and (b) never mentions the
    descriptive id. Red today: the real grants are not delivered."""
    layout = shared_reference_layout
    installed = installed_skill_ids(REPO_ROOT)
    roots = compiled_agent_roots(layout)
    assert len(roots) >= 2
    agents = pristine_registry_agents()
    population = _descriptive_population(agents)
    assert population
    by_id = {a["id"]: a for a in agents}
    for agent_id, skill_id in sorted(population):
        a = by_id[agent_id]
        # Positive control against the CURRENT declaration (the source of truth), not the
        # frozen pre-migration registry: a grant legitimately added after the migration
        # (python-coder/complexity-reduction, once main shipped that skill) must not read
        # as a defect here (same rule as AR-300d-3 / decision 12).
        declared = declared_ids(template_frontmatter(REPO_ROOT / "templates" / "agents" / f"{template_stem(a)}.md"))
        assert granted_ids(a) & installed <= declared, (agent_id, "a pre-migration grant was lost")
        for root in roots:
            text = (root / f"{template_stem(a)}.md").read_text(encoding="utf-8")
            assert named_abilities(text, installed) == declared & installed, (agent_id, root.name)
            assert skill_id not in text, f"{agent_id} compiled prompt mentions {skill_id} ({root.name})"


def _template_only_grants(tl, orig):
    """stem -> ids granted ONLY at template level (derived: template-level ids
    minus what the agent's registry record already grants)."""
    registry_by_stem = {template_stem(a): granted_ids(a) for a in orig if template_stem(a)}
    out = {}
    for stem, ids in tl.items():
        extra = ids - registry_by_stem.get(stem, set())
        if extra:
            out[stem] = extra
    return out


def test_ids_granted_only_at_template_level_appear_in_the_migrated_declaration(migrated, template_level):
    # covers: AR-300c-2
    # angle: real_artifact
    """AR-300c-2 (third source): the union spans registry skills_used +
    registry skills_invoked + the template's OWN frontmatter lists. Population
    DERIVED from the pristine templates (no agent names); empty fails. Every
    template-level id lands in that agent's migrated ``skills:`` declaration.
    Only the id is asserted -- no mode/condition for bare template-level grants.
    Red today: the migration reads the registry only and drops them."""
    pkg, _report, orig = migrated
    tl, _keys = template_level
    only = _template_only_grants(tl, orig)
    assert only, "no id is granted only at template level (third-source population is empty)"
    for stem, ids in tl.items():
        decl = declared_ids(template_frontmatter(pkg / "templates" / "agents" / f"{stem}.md"))
        assert ids <= decl, f"{stem}: template-level ids missing from declaration: {sorted(ids - decl)}"


def test_no_template_carries_a_template_level_grant_key_after_migration(migrated, template_level):
    # covers: AR-300c-1
    # angle: criterion
    """AR-300c-1/2: after migration NO template has a template-level
    ``skills_used`` or ``skills_invoked`` key, not even an empty one -- ``skills:``
    is the single place. Population of templates that had one is derived and
    must be non-empty. Red today: the keys are left in place."""
    pkg, _report, _orig = migrated
    _tl, keys = template_level
    had = {stem for stem, ks in keys.items() if ks}
    assert had, "no pristine template carried a template-level grant key"
    leftover = {}
    for stem in sorted(had):
        fm = template_frontmatter(pkg / "templates" / "agents" / f"{stem}.md")
        left = [k for k in TEMPLATE_LEVEL_KEYS if k in fm]
        if left:
            leftover[stem] = left
    assert not leftover, f"template-level grant keys survive: {leftover}"
    for t in (pkg / "templates" / "agents").glob("*.md"):
        assert not set(TEMPLATE_LEVEL_KEYS) & set(template_frontmatter(t)), t.name


def test_report_provenance_names_the_template_field_for_template_level_grants(migrated, template_level):
    # covers: AR-300c-2
    # angle: criterion
    """AR-300c-2: the report records where each ability came from, including
    the template's own list: each agent holding a template-only grant has a
    ``sources`` entry naming the template field, and its ability listed."""
    _pkg, report, orig = migrated
    tl, _keys = template_level
    only = _template_only_grants(tl, orig)
    assert only
    registry_stem_to_id = {template_stem(a): a["id"] for a in orig if template_stem(a)}
    by_agent = {r["agent"]: r for r in report["agents"]}
    for stem, ids in only.items():
        row = by_agent.get(registry_stem_to_id.get(stem, stem))
        assert row is not None, f"{stem} absent from the report"
        assert any("template" in s and any(k in s for k in TEMPLATE_LEVEL_KEYS)
                   for s in row["sources"]), row["sources"]
        assert ids <= set(row["abilities"]), (stem, sorted(ids - set(row["abilities"])))


@pytest.mark.shared_layout_reader
def test_template_level_only_grants_are_named_in_compiled_prompts_of_every_root(shared_reference_layout):
    # covers: AR-300c-2
    # angle: deployed
    """AR-300c-2 (user-visible symptom): in EVERY platform root, each agent
    holding a template-level-only grant (derived; today product-owner and
    business-analyst hold ac-tree-split) names that ability in its compiled
    prompt. Red today: ac-tree-split is left out of the declaration, so it is
    never delivered."""
    layout = shared_reference_layout
    installed = installed_skill_ids(REPO_ROOT)
    roots = compiled_agent_roots(layout)
    assert len(roots) >= 2
    only = _template_only_grants(pristine_template_level(), pristine_registry_agents())
    only = {s: ids & installed for s, ids in only.items() if ids & installed}
    assert only, "no installed template-level-only grant to deliver"
    for stem, ids in sorted(only.items()):
        for root in roots:
            text = (root / f"{stem}.md").read_text(encoding="utf-8")
            got = named_abilities(text, installed)
            assert ids <= got, f"{stem} ({root.name}) does not name {sorted(ids - got)}"
