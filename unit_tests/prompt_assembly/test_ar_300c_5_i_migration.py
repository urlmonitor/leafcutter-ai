"""AR-300c-5-i -- moving sub-agent permissions into each agent's declaration carries the
UNION of every rival record (registry field, existing frontmatter key, hand-written body
table) and says what came from where.

Source of truth: .../AR-300c-5-i.yaml. Contract: _ar_300e_support.py item 3 (one-shot CLI
``scripts/migrate_agent_spawn_allowlist.py``, NOT wired into the build).

Evidence rule: the union is asserted against a PRE-migration snapshot of the real data
(the pristine registry fixture of slice 1, the real templates with their spawn keys
stripped, and verbatim snapshots of the eight templates that carried a source of their
own) -- after the real tree is migrated and remediated, architect-review no longer holds
architect-review-deep and a check on the live tree could not see the union. The oracle is
parsed independently (``source_sets``); the template/registry bytes come from real files.

RED BASELINE (slice 5): the migration CLI does not exist (exit 2), so every test fails on
the shared ``migrate_spawn_or_fail`` assertion (kind: absence of the new tool).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300e_support import (  # noqa: E402
    FRONTMATTER_STEMS,
    KEY,
    MACRO,
    copy_pristine_spawn_package,
    declared_after,
    migrate_spawn_or_fail,
    run_spawn_migration,
    source_sets,
    strip_frontmatter_keys,
    template_bytes,
    union_of,
    write_template,
)

_CACHE: dict = {}


def _migrated(tmp_path_factory):
    """(pkg, oracle sources, original template bytes, report): migrated ONCE per module.
    Not a fixture on purpose: a failing migration must fail the test, not error setup."""
    if "run" not in _CACHE:
        pkg = copy_pristine_spawn_package(tmp_path_factory.mktemp("spawn_migration") / "pkg")
        sources, before = source_sets(pkg), template_bytes(pkg)
        _CACHE["run"] = (pkg, sources, before, migrate_spawn_or_fail(pkg))
    return _CACHE["run"]


def test_every_agent_permitted_by_any_source_has_a_declaration_afterwards(tmp_path_factory):
    # covers: AR-300c-5-i
    # angle: real_artifact
    """AR-300c-5-i: run against the pre-migration snapshot of the real registry and templates,
    every agent that ANY of the three sources permits a sub-agent ends with a
    ``spawn_allowlist`` declaration."""
    pkg, sources, _before, _report = _migrated(tmp_path_factory)
    holders = {aid: s for aid, s in sources.items() if union_of(s)}
    assert len(holders) > 20, f"derived only {len(holders)} permitted agents from the snapshot"
    missing = sorted(aid for aid, s in holders.items() if declared_after(pkg, s["stem"]) is None)
    assert not missing, f"{len(missing)}/{len(holders)} permitted agents have no declaration: {missing}"


def test_declared_sub_agents_are_the_union_of_the_three_sources(tmp_path_factory):
    # covers: AR-300c-5-i
    # angle: real_artifact
    """AR-300c-5-i: each agent's declared list equals the union of its registry field, its
    existing frontmatter key and its body table, each id once. The two measured
    disagreements are the criterion's teeth: python-coder is declared test-runner (table
    only) and architect-review architect-review-deep (registry only); nothing is dropped."""
    pkg, sources, _before, _report = _migrated(tmp_path_factory)
    for aid, s in sorted(sources.items()):
        want = union_of(s)
        if not want:
            continue
        got = declared_after(pkg, s["stem"]) or []
        assert len(got) == len(set(got)), f"{aid}: duplicate ids in {got}"
        assert set(got) == want, f"{aid}: declared {sorted(got)} != union {sorted(want)}"
    assert {"research-agent", "test-runner"} <= set(declared_after(pkg, "python-coder") or [])
    assert {"research-agent", "architect-review-deep"} <= set(declared_after(pkg, "architect-review") or [])


def test_no_sub_agent_is_declared_that_no_source_recorded(tmp_path_factory, tmp_path):
    # covers: AR-300c-5-i
    # angle: criterion
    """AR-300c-5-i: no permission is invented. On the real snapshot every declared id was
    recorded by some source; on a planted package, sub-agents named only in running prose or
    in a fenced example (never in a permission source) are not declared, an agent no source
    permits gains no key, and the planted union is exact."""
    pkg, sources, _before, _report = _migrated(tmp_path_factory)
    for aid, s in sources.items():
        assert set(declared_after(pkg, s["stem"]) or []) <= union_of(s), f"{aid}: invented a permission"

    mini = tmp_path / "mini"
    (mini / "config").mkdir(parents=True)
    prose = "# Agent\n\nSometimes ask `zz-prose-only` for help.\n\n```\nspawn zz-fenced-only\n```\n"
    table = "# Agent\n\n## Your Available Sub-Agents\n\n| Agent | Role | Tier |\n|---|---|---|\n| zz-y | r | t |\n"
    for stem, body in (("zz-a", prose), ("zz-b", prose), ("zz-c", table)):
        write_template(mini / "templates" / "agents" / f"{stem}.md",
                       {"name": stem, "description": f"{stem} fixture", "model": "sonnet", "tools": "Read"}, body)
    registry = [{"id": s, "template_path": f"templates/agents/{s}.md", "spawn_allowlist": sp, "is_ticket_phase": False}
                for s, sp in (("zz-a", ["zz-x"]), ("zz-b", []), ("zz-c", []))]
    (mini / "config" / "agent_registry.json").write_text(json.dumps({"agents": registry}, indent=4), encoding="utf-8")
    migrate_spawn_or_fail(mini)
    assert declared_after(mini, "zz-a") == ["zz-x"]
    assert declared_after(mini, "zz-c") == ["zz-y"]
    assert declared_after(mini, "zz-b") is None


def test_ticket_phase_macro_is_carried_as_one_entry(tmp_path_factory):
    # covers: AR-300c-5-i
    # angle: discrimination
    """AR-300c-5-i: ticket-supervisor's migrated declaration holds the literal
    ``__ticket_phase_agents__`` item exactly once, beside its two named agents, and none of
    the ticket-phase agent names the macro stands for. Wrong version caught: the migration
    expands the macro into the ticket-phase names of migration day."""
    pkg, sources, _before, _report = _migrated(tmp_path_factory)
    registry_list = sources["ticket-supervisor"]["registry"]
    assert registry_list.count(MACRO) == 1, "control: the pristine registry holds the macro once"
    declared = declared_after(pkg, "ticket-supervisor")
    assert declared is not None and declared.count(MACRO) == 1, declared
    assert set(declared) == set(registry_list), f"declared {declared} != registry {registry_list}"
    expanded = {a["id"] for a in json.loads((pkg / "config" / "agent_registry.json").read_text("utf-8"))["agents"]
                if a.get("is_ticket_phase")} - set(registry_list)
    assert expanded and not (expanded & set(declared)), f"macro expanded into {sorted(expanded & set(declared))}"


def test_report_names_each_agent_with_provenance_disagreements_and_source_counts(tmp_path_factory):
    # covers: AR-300c-5-i
    # angle: criterion
    """AR-300c-5-i: the provenance report names every permitted agent with the source(s) of
    each permitted sub-agent (checked against the independent oracle), lists python-coder and
    architect-review among the disagreeing agents while the three tables that agree with the
    registry are NOT listed (control rows), and states how many agents each source held."""
    _pkg, sources, _before, report = _migrated(tmp_path_factory)
    want_ids = {aid for aid, s in sources.items() if union_of(s)}
    entries = {e["agent"]: e for e in report["agents"]}
    assert want_ids <= set(entries), f"report omits agents: {sorted(want_ids - set(entries))}"
    assert all(not e["sub_agents"] for aid, e in entries.items() if aid not in want_ids), "report invents permissions"
    for aid in sorted(want_ids):
        got = {sa["id"]: set(sa["sources"]) for sa in entries[aid]["sub_agents"]}
        want = {sid: {name for name in ("registry", "frontmatter", "body_table")
                      if sid in sources[aid][name]} for sid in union_of(sources[aid])}
        assert got == want, f"{aid}: provenance {got} != oracle {want}"
    assert {"python-coder", "architect-review"} <= set(report["disagreeing_agents"])
    assert not ({"frontend-coder", "test-writer", "business-analyst"} & set(report["disagreeing_agents"]))
    counts = report["source_holder_counts"]
    assert counts == {name: sum(1 for s in sources.values() if s[name]) for name in ("registry", "frontmatter", "body_table")}
    assert counts["body_table"] == 5 and counts["frontmatter"] == 2 and counts["registry"] > 20


def test_no_new_empty_declaration_and_existing_empty_left_untouched(tmp_path_factory):
    # covers: AR-300c-5-i
    # angle: boundary
    """AR-300c-5-i: an agent permitted by no source gains no key, and an explicit empty
    declaration already present (ac-triage, onboard-config-section) is left byte-identical.
    Controls: both populations are non-empty, so the assertion cannot pass on nothing."""
    pkg, sources, before, _report = _migrated(tmp_path_factory)
    after = template_bytes(pkg)
    empty = {aid: s for aid, s in sources.items() if not union_of(s)}
    explicit = sorted(s["stem"] for s in empty.values() if s["has_key"])
    silent = sorted(s["stem"] for s in empty.values() if not s["has_key"])
    assert explicit == sorted(set(FRONTMATTER_STEMS) & {"ac-triage", "onboard-config-section"}), explicit
    assert len(silent) > 10, f"only {len(silent)} unpermitted agents without a key to examine"
    for stem in explicit:
        assert after[f"{stem}.md"] == before[f"{stem}.md"], f"{stem}: explicit empty declaration was rewritten"
    gained = [stem for stem in silent if declared_after(pkg, stem) is not None]
    assert not gained, f"new empty declaration written for {gained}"


def test_spawn_migration_is_byte_stable_and_insert_only(tmp_path):
    # covers: AR-300c-5-i
    # angle: real_artifact
    """AR-300c-5-i (backfill discipline): a second run is byte-identical, and the ONLY change
    to any template is the inserted ``spawn_allowlist`` key -- ``tools:``, every other
    frontmatter key and the body survive byte-identical, and non-agent files are untouched.
    Control: many templates DID change, so 'identical' is not 'nothing ran'."""
    pkg = copy_pristine_spawn_package(tmp_path / "pkg")
    original = {p: p.read_bytes() for p in sorted((pkg / "templates" / "agents").iterdir())}
    migrate_spawn_or_fail(pkg)
    first = {p: p.read_bytes() for p in original}
    proc = run_spawn_migration(pkg, tmp_path / "second_report.json")
    assert proc.returncode == 0, proc.stderr[-400:]
    assert {p: p.read_bytes() for p in original} == first, "a second run changed the templates"
    changed = [p for p in original if first[p] != original[p]]
    assert len(changed) > 15, f"only {len(changed)} templates changed"
    for path in original:
        old, new = original[path].decode("utf-8"), first[path].decode("utf-8")
        if not path.name.endswith(".md") or path.name.startswith("_") or not old.startswith("---"):
            assert new == old, f"{path.name}: a non-agent file changed"
            continue
        assert strip_frontmatter_keys(new, (KEY,))[0] == strip_frontmatter_keys(old, (KEY,))[0], \
            f"{path.name}: more than the spawn_allowlist key changed"
    assert Path(pkg / "config" / "agent_registry.json").is_file()
