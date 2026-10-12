"""AR-300a-5 -- every agent permitted to dispatch sub-agents has them named in its
COMPILED prompt (one generated section, macro shown as the agents it resolved to), and an
agent permitted none gets no section at all (no heading over an empty list).

Source of truth: .../AR-300a-5.yaml. Contract: _ar_300e_support.py item 2. Evidence rule:
every assertion reads compiled prompt bytes (the deployed layout, or the real in-process
``build_agents`` over a planted package) -- never the registry copy; the declarations only
supply the population, derived by parsing, never enumerated.

RED BASELINE (slice 5): ``build_per_agent_spawn_table`` is computed by no build step, so
no agent receives a section from its declaration and nothing registers a ``spawn_allowlist``
preparation (assertion red).
"""

from __future__ import annotations

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import layout_roots  # noqa: E402
from _ar_300b_support import copy_roots  # noqa: E402
from _ar_300e_support import (  # noqa: E402
    BODY,
    MACRO,
    agent_prompts,
    fresh_spawn_build,
    has_sub_agent_heading,
    named_sub_agents,
    real_known_ids,
    real_registry,
    real_spawn_declarations,
    resolve_declared,
    sfm,
    spawn_accounts,
    spawn_registrations,
    strip_spawn_sections,
    workers,
)


@pytest.mark.shared_layout_reader
def test_every_permitted_agent_compiled_prompt_carries_one_sub_agent_section(shared_reference_layout):
    # covers: AR-300a-5
    # angle: deployed
    """AR-300a-5: for every agent whose declaration permits a sub-agent (population derived
    from the declarations), each compiled prompt in BOTH platform roots carries exactly one
    sub-agent section -- and no agent that declares nothing carries one (a hand-written table
    on an undeclared agent is the second account AR-300a-5-i removes)."""
    roots = layout_roots(shared_reference_layout)
    assert len(roots) >= 2, f"expected claude + gemini compiled roots, found {roots}"
    declared, known = real_spawn_declarations(), real_known_ids()
    assert declared, "0 declaring agents examined: an empty population is not a pass"
    wrong, examined = [], 0
    for root in roots:
        for prompt in agent_prompts(root):
            examined += 1
            count = len(spawn_accounts(prompt.read_text(encoding="utf-8"), known))
            if count != (1 if prompt.stem in declared else 0):
                wrong.append((root.parent.name, prompt.stem, count))
    assert examined > 2 * len(declared)
    assert not wrong, f"{len(wrong)}/{examined} compiled prompts carry the wrong number of sub-agent sections: {wrong[:6]}"


@pytest.mark.shared_layout_reader
def test_section_names_every_declared_sub_agent_once_with_macro_resolved(shared_reference_layout):
    # covers: AR-300a-5
    # angle: real_artifact
    """AR-300a-5: each compiled section names EVERY declared sub-agent exactly once, so it is
    the whole permission and not a sample; the agent holding the ticket-phase macro (derived:
    whoever declares it) names every agent whose ``is_ticket_phase`` is true and never the
    literal token. Wrong version caught: printing the macro, which 'names the declaration'
    and tells the supervisor nothing."""
    roots = layout_roots(shared_reference_layout)
    declared, registry, known = real_spawn_declarations(), real_registry(), real_known_ids()
    holders = sorted(stem for stem, decl in declared.items() if MACRO in decl)
    assert declared and holders, f"no agent declares the ticket-phase macro (declaring agents: {sorted(declared)})"
    phase = {a["id"] for a in registry if a.get("is_ticket_phase")}
    wrong = []
    for root in roots:
        for stem, decl in sorted(declared.items()):
            text = (root / f"{stem}.md").read_text(encoding="utf-8")
            ids = [i for a in spawn_accounts(text, known) for i in a["ids"]]
            if sorted(ids) != sorted(resolve_declared(decl, registry)) or MACRO in text:
                wrong.append((root.parent.name, stem, sorted(set(ids) ^ set(resolve_declared(decl, registry)))))
            if stem in holders and not phase <= set(ids):
                wrong.append((root.parent.name, stem, f"missing ticket-phase agents {sorted(phase - set(ids))}"))
    assert not wrong, f"{len(wrong)} sections are not the whole permission, each once: {wrong[:5]}"


def test_absent_or_empty_declaration_yields_no_section(tmp_path, monkeypatch):
    # covers: AR-300a-5
    # angle: boundary
    """AR-300a-5: an agent with NO declaration (even though the registry copy lists
    sub-agents for it) and an agent with ``spawn_allowlist: []`` carry no sub-agent section
    and no bare heading; the declaring control agent carries exactly one, so the silence is
    caused by the missing declaration and not by a dead delivery."""
    templates = {"zz-has": (sfm("zz-has", ["zz-w1"]), BODY), "zz-none": (sfm("zz-none"), BODY),
                 "zz-empty": (sfm("zz-empty", []), BODY), **workers("zz-w1")}
    _mod, _pkg, roots, _preps = fresh_spawn_build(tmp_path, monkeypatch, templates,
                                                  registry_spawn={"zz-none": ["zz-w1"], "zz-empty": ["zz-w1"]})
    known = set(templates)
    assert len(roots) == 2
    for root in roots:
        assert [a["ids"] for a in spawn_accounts((root / "zz-has.md").read_text(encoding="utf-8"), known)] == [["zz-w1"]]
        for stem in ("zz-none", "zz-empty"):
            assert not has_sub_agent_heading((root / f"{stem}.md").read_text(encoding="utf-8")), \
                f"{stem}: a sub-agent heading was compiled for an agent permitted nothing"


def test_delivery_evidence_counts_examined_and_permitted_and_fails_on_zero(tmp_path, monkeypatch):
    # covers: AR-300a-5
    # angle: boundary
    """AR-300a-5: the delivery evidence enumerates every compiled prompt in BOTH roots and
    states how many it examined and how many held a permission: 7 agents x 2 roots = 14
    examined, exactly the 3 declaring agents registered a ``spawn_allowlist`` preparation,
    the clean verdict lists that preparation among the kinds, and a run that registered
    nothing over a non-empty tree fails instead of passing on an empty population."""
    templates = {"zz-a": (sfm("zz-a", ["zz-w1"]), BODY), "zz-b": (sfm("zz-b", ["zz-w1", "zz-w2"]), BODY),
                 "zz-c": (sfm("zz-c", ["zz-w2"]), BODY), "zz-n": (sfm("zz-n"), BODY),
                 "zz-e": (sfm("zz-e", []), BODY), **workers("zz-w1", "zz-w2")}
    mod, _pkg, roots, preps = fresh_spawn_build(tmp_path, monkeypatch, templates)
    registered = {p["agent"] for p in spawn_registrations(preps)}
    assert registered == {"zz-a", "zz-b", "zz-c"}, f"agents holding a permission: {sorted(registered)}"
    expected = len(templates) * len(roots)
    verdict = mod.verify_preparations_delivered(list(roots), expected_prompt_count=expected, preparations=preps)
    assert verdict["inspected_prompt_count"] == expected == 14
    assert sorted(verdict["roots_examined"]) == sorted(str(r) for r in roots)
    assert "spawn_allowlist" in verdict["preparation_kinds"]
    assert not [f for f in verdict["findings"] if f.get("preparation") == "spawn_allowlist"]
    nothing = mod.verify_preparations_delivered(list(roots), expected_prompt_count=expected, preparations=[])
    assert nothing["ok"] is False
    assert [f for f in nothing["findings"] if f.get("kind") == "empty-population"]


def test_delivery_is_read_from_compiled_prompt_not_registry(tmp_path, monkeypatch):
    # covers: AR-300a-5
    # angle: discrimination
    """AR-300a-5: with the section stripped from ONE compiled prompt (one root) while the
    declaration and the registry copy are both correct, the delivery check fails for exactly
    that agent in exactly that root. Control: the byte copy before the strip passes. Wrong
    version caught: an assertion that reads the registry or the template instead of the
    compiled prompt (both untouched, so it would stay green)."""
    templates = {"zz-a": (sfm("zz-a", ["zz-w1"]), BODY), "zz-b": (sfm("zz-b", ["zz-w1", "zz-w2"]), BODY),
                 **workers("zz-w1", "zz-w2")}
    mod, _pkg, roots, preps = fresh_spawn_build(tmp_path, monkeypatch, templates)
    assert {p["agent"] for p in spawn_registrations(preps)} == {"zz-a", "zz-b"}, "control: nothing delivered"
    copies = copy_roots(roots, tmp_path / "copies")
    expected = len(templates) * len(copies)
    before = mod.verify_preparations_delivered(copies, expected_prompt_count=expected, preparations=preps)
    assert before["ok"] is True, before["findings"]
    victim = copies[1] / "zz-b.md"
    text = victim.read_text(encoding="utf-8")
    victim.write_text(strip_spawn_sections(text), encoding="utf-8")
    assert victim.read_text(encoding="utf-8") != text, "mutation changed nothing"
    assert named_sub_agents(victim.read_text(encoding="utf-8"), set(templates)) == set()
    after = mod.verify_preparations_delivered(copies, expected_prompt_count=expected, preparations=preps)
    hits = [(f["agent"], f["preparation"], f["platform_root"]) for f in after["findings"] if "agent" in f]
    assert after["ok"] is False and hits == [("zz-b", "spawn_allowlist", str(copies[1]))], hits
