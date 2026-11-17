"""AR-300b-1-ii -- the delivery failure says WHY: a closed ``cause`` value on the
SAME finding object (no-destination vs empty-preparation), the agent and the
preparation named, the affected-agent count reported alongside the findings, and
a deterministic cause when both states hold at once.

Source of truth: .../AR-300b-1-ii.yaml. Contract: _ar_300b_support.py (B).
Compiled trees are authentic (the REAL ``build_agents`` over a planted package);
the registrations under test are explicit entries because the cause is derived
from the (destination_offered, content) pair the preparation step carries.

RED BASELINE: scripts/agent_preparation_delivery.py does not exist (absence red).
"""

from __future__ import annotations

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import agent_fm  # noqa: E402
from _ar_300b_support import (  # noqa: E402
    BODY,
    append_block,
    block_for,
    entry,
    fresh_build,
    per_agent,
    unique,
    verdict_of,
)

CAUSES = {"no-destination", "empty-preparation"}


def test_missing_destination_and_empty_preparation_carry_different_causes(tmp_path, monkeypatch):
    # covers: AR-300b-1-ii
    # angle: criterion
    """AR-300b-1-ii: a preparation offered no destination (non-empty content, none
    in the prompt) is cause ``no-destination``; one whose computation produced
    nothing (destination offered, empty content) is ``empty-preparation``; a
    delivered third one produces no finding. Exact: one finding per root for
    each failing preparation, none for the control. Wrong version caught: one
    undifferentiated cause, or the cause swapped."""
    built = fresh_build(tmp_path, monkeypatch)
    no_dest, empty, ok = unique("p-nodest"), unique("p-empty"), unique("p-ok")
    append_block(built.roots, ["zz-holder-c"], block_for(ok, "zz-holder-c"))
    preps = [
        entry(no_dest, "zz-holder-a", "content that exists in no compiled prompt " + no_dest, offered=False),
        entry(empty, "zz-holder-b", "", offered=True),
        entry(ok, "zz-holder-c", block_for(ok, "zz-holder-c"), offered=True),
    ]
    found = per_agent(verdict_of(built.mod, built.roots, preps, built.expected))
    by_name = {}
    for f in found:
        by_name.setdefault(f["preparation"], []).append(f)
    assert set(by_name) == {no_dest, empty}, f"control row {ok} reported, or a failing one missed: {set(by_name)}"
    assert [f["cause"] for f in by_name[no_dest]] == ["no-destination"] * len(built.roots)
    assert [f["cause"] for f in by_name[empty]] == ["empty-preparation"] * len(built.roots)


def test_finding_names_both_the_agent_and_the_preparation(tmp_path, monkeypatch):
    # covers: AR-300b-1-ii
    # angle: criterion
    """AR-300b-1-ii: every finding states the agent id and the preparation name
    explicitly (the pairing is not left to be re-derived), and the pairs are
    exactly the (agent, preparation) pairs registered and undelivered. Wrong
    version caught: a finding naming only the preparation, or only the agent."""
    built = fresh_build(tmp_path, monkeypatch)
    pairs = {("zz-holder-a", unique("p-one")), ("zz-holder-b", unique("p-two"))}
    preps = [entry(name, agent, "absent content " + name, offered=False) for agent, name in pairs]
    found = per_agent(verdict_of(built.mod, built.roots, preps, built.expected))
    assert {(f["agent"], f["preparation"]) for f in found} == pairs
    assert all(f.get("agent") and f.get("preparation") and f.get("cause") in CAUSES for f in found)


def test_shared_preparation_failure_reports_the_affected_agent_count(tmp_path, monkeypatch):
    # covers: AR-300b-1-ii
    # angle: boundary
    """AR-300b-1-ii: one preparation failing for SIX agents is reported for all
    six (not only the first encountered), the verdict states the affected-agent
    count for that preparation, and the rendered report shows the count on the
    preparation's own line. Wrong version caught: stopping at the first
    instance (60 agents read as 1)."""
    templates = {f"zz-many-{k}": (agent_fm(f"zz-many-{k}"), BODY) for k in range(6)}
    built = fresh_build(tmp_path, monkeypatch, templates)
    shared = unique("p-shared")
    preps = [entry(shared, stem, "never delivered " + shared, offered=False) for stem in sorted(templates)]
    verdict = verdict_of(built.mod, built.roots, preps, built.expected)
    found = per_agent(verdict)
    assert {f["agent"] for f in found} == set(templates), "not every affected agent is named"
    assert len(found) == 6 * len(built.roots)
    assert verdict["affected_agent_counts"][shared] == 6
    lines = [ln for ln in built.mod.render_preparation_verdict(verdict).splitlines() if shared in ln]
    assert lines and any(re.search(r"\b6\b", ln) for ln in lines), lines


def test_cause_is_derived_from_state_not_guessed(tmp_path, monkeypatch):
    # covers: AR-300b-1-ii
    # angle: failure
    """AR-300b-1-ii: a preparation that is BOTH destination-less and empty is
    classified deterministically: exactly one finding per (agent, root) with one
    cause from the closed set, identical on five repeats and when the entries
    and the roots are presented in the opposite order. Wrong versions caught:
    both causes emitted (two findings), none emitted, an order-dependent
    branch."""
    built = fresh_build(tmp_path, monkeypatch)
    name = unique("p-both")
    preps = [entry(name, "zz-holder-a", "", offered=False), entry(name, "zz-holder-b", "", offered=False)]

    def causes(entries, roots):
        found = [f for f in per_agent(verdict_of(built.mod, roots, entries, built.expected))
                 if f["preparation"] == name]
        assert len(found) == len(entries) * len(roots), found
        return sorted((f["agent"], f["platform_root"], f["cause"]) for f in found)

    first = causes(preps, built.roots)
    assert {c for _a, _r, c in first} <= CAUSES and len({c for _a, _r, c in first}) == 1
    assert all(causes(preps, built.roots) == first for _ in range(5))
    assert causes(list(reversed(preps)), list(reversed(built.roots))) == first
