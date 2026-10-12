"""AR-300b-2 -- the delivery guarantee covers a per-agent preparation ADDED LATER
with nothing edited: the covered set is DERIVED from what the build registered,
never from a list of names; the run states how many kinds it covered; every
placeholder-guarded injection the compiler computes registers itself.

Source of truth: .../AR-300b-2.yaml. Contract: _ar_300b_support.py (A, B, E).
Registration contract named by the test-writer: ``register_preparation(
preparation_name, agent, content, destination_offered)`` / ``reset_preparations()``
/ ``get_preparations()`` plus the computed ledger ``compute_preparation``.
Names used for the "added later" preparations are unique per run, so a gate
holding a literal name list cannot pass them.

RED BASELINE: scripts/agent_preparation_delivery.py does not exist (absence red).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import source_templates  # noqa: E402
from _ar_300b_support import (  # noqa: E402
    COUNTS_RE,
    append_block,
    block_for,
    entry,
    fresh_build,
    per_agent,
    population,
    real_build,
    unique,
    verdict_of,
)

CONFIG = {"output_root": ".leafcutter"}
# The compiler's per-agent placeholder-guarded injections (the test's oracle of
# what the compiler computes; the synthetic-third test covers any later one).
PER_AGENT_TOKENS = ("registry_phase_agents_table", "doc_type_reference_table", "project_paths_table",
                    "agent_priority_table", "doc_types_dispatch_table")


def _register(mod, e: dict) -> None:
    mod.register_preparation(e["preparation_name"], e["agent"], e["content"], e["destination_offered"])


def test_a_third_preparation_added_later_is_reported_with_no_gate_edit(tmp_path, monkeypatch, capsys):
    # covers: AR-300b-2
    # angle: seam
    """AR-300b-2: the REAL producer's registrations (a real in-process build) are
    piped into the REAL gate. A clean build is accepted (control, rc 0); then a
    never-before-seen preparation (unique name, registered through the public
    registration API, gate untouched) that reaches one agent and not another is
    reported by name and agent with exit 1, and its delivered twin for the other
    agent is not. Wrong versions caught: a gate naming today's two preparations,
    a gate that iterates a fixed kind list, a gate reading only the build's own
    registrations at build time."""
    built = fresh_build(tmp_path, monkeypatch)
    mod = built.mod
    assert mod.refuse_on_undelivered_preparations(
        built.project, CONFIG, False, expected_prompt_count=built.expected) == 0, "control: clean build refused"
    third = unique("zz-third")
    append_block(built.roots, ["zz-holder-c"], block_for(third, "zz-holder-c"))
    _register(mod, entry(third, "zz-holder-b", block_for(third, "zz-holder-b")))
    _register(mod, entry(third, "zz-holder-c", block_for(third, "zz-holder-c")))
    found = per_agent(mod.verify_preparations_delivered(built.roots, expected_prompt_count=built.expected))
    assert {(f["agent"], f["preparation"]) for f in found} == {("zz-holder-b", third)}
    assert len(found) == len(built.roots)
    capsys.readouterr()
    rc = mod.refuse_on_undelivered_preparations(built.project, CONFIG, False, expected_prompt_count=built.expected)
    out = capsys.readouterr()
    assert rc == 1 and third in out.out + out.err and "zz-holder-b" in out.out + out.err


def test_covered_set_is_derived_from_registered_preparations_not_a_name_list(tmp_path, monkeypatch):
    # covers: AR-300b-2
    # angle: criterion
    """AR-300b-2: the covered set equals the set of preparation names registered
    on the run, EXACTLY: starting empty it is empty; registering two unique
    names covers those two; adding a third adds it; removing a registration
    (reset, re-register fewer) removes it. Names are unique per run, so no
    literal list in the gate can produce the sets asserted. Wrong version
    caught: a covered set built from a list of names."""
    built = fresh_build(tmp_path, monkeypatch)
    mod = built.mod
    a, b, c = unique("zz-kind-a"), unique("zz-kind-b"), unique("zz-kind-c")

    def covered() -> list[str]:
        return mod.verify_preparations_delivered(built.roots, expected_prompt_count=built.expected)[
            "preparation_kinds"]

    mod.reset_preparations()
    assert covered() == []
    for name in (a, b):
        append_block(built.roots, ["zz-holder-a"], block_for(name, "zz-holder-a"))
        _register(mod, entry(name, "zz-holder-a", block_for(name, "zz-holder-a")))
    assert covered() == sorted([a, b])
    append_block(built.roots, ["zz-holder-b"], block_for(c, "zz-holder-b"))
    _register(mod, entry(c, "zz-holder-b", block_for(c, "zz-holder-b")))
    assert covered() == sorted([a, b, c])
    mod.reset_preparations()
    _register(mod, entry(a, "zz-holder-a", block_for(a, "zz-holder-a")))
    assert covered() == [a]


def test_all_registered_preparation_kinds_are_counted_and_reported(tmp_path, monkeypatch):
    # covers: AR-300b-2
    # angle: boundary
    """AR-300b-2: three kinds registered across five entries (two kinds repeat
    over agents) are counted as exactly 3 and the rendered report states that
    number; a run recognising ZERO kinds is not ok, states 0 kinds and an
    empty preparations population -- it is never reported as a run with no
    failures. Wrong versions caught: counting entries instead of kinds, counting
    nothing, an all-clear on an empty derivation."""
    built = fresh_build(tmp_path, monkeypatch)
    names = [unique("zz-count-a"), unique("zz-count-b"), unique("zz-count-c")]
    stems = ["zz-holder-a", "zz-holder-b"]
    entries = []
    for name in names[:2]:
        entries += [entry(name, s, block_for(name, s)) for s in stems]
    entries.append(entry(names[2], stems[0], block_for(names[2], stems[0])))
    for e in entries:
        append_block(built.roots, [e["agent"]], e["content"])
    verdict = verdict_of(built.mod, built.roots, entries, built.expected)
    assert verdict["ok"] is True, verdict["findings"]
    assert verdict["inspected_preparation_kinds"] == 3 and len(entries) == 5
    assert COUNTS_RE.search(built.mod.render_preparation_verdict(verdict)).group(1) == "3"

    empty = verdict_of(built.mod, built.roots, [], built.expected)
    assert empty["ok"] is False and empty["inspected_preparation_kinds"] == 0
    assert [f["side"] for f in population(empty, "empty-population")] == ["preparations"]


def test_every_placeholder_guarded_injection_type_registers_itself(tmp_path, monkeypatch):
    # covers: AR-300b-2
    # angle: real_artifact
    """AR-300b-2: after the REAL ``build_agents`` over the actual templates,
    every (injection, agent) pair the compiler computes -- a placeholder token
    present in a real template -- is registered under the token's name, with a
    destination offered and non-empty content; and the registered kinds are
    MORE than those tokens (the declared-skills preparation is covered by the
    same registry, not only the placeholder-guarded ones). Wrong version
    caught: a registry that covers only the two known-dead preparations, or
    only the abilities section."""
    built = real_build(tmp_path, monkeypatch)
    expected = set()
    for tpl in source_templates():
        text = tpl.read_text(encoding="utf-8")
        expected |= {(tok, tpl.stem) for tok in PER_AGENT_TOKENS if "{{" + tok + "}}" in text}
    tokens = {tok for tok, _stem in expected}
    assert len(tokens) >= 3 and len(expected) >= 4, f"control: real templates use too few injections {tokens}"
    registered = {(p["preparation_name"], p["agent"]): p for p in built.preparations}
    missing = sorted(expected - set(registered))
    assert not missing, f"computed injections that never registered: {missing[:6]}"
    for pair in expected:
        assert registered[pair]["destination_offered"] is True and registered[pair]["content"].strip(), pair
    kinds = {p["preparation_name"] for p in built.preparations}
    assert tokens < kinds, f"only the placeholder-guarded kinds registered: {sorted(kinds)}"


def test_a_preparation_computed_without_registering_is_itself_reported(tmp_path, monkeypatch):
    # covers: AR-300b-2
    # angle: failure
    """AR-300b-2 (forgot-to-register is not a silent hole): a preparation computed
    through the computation ledger (``compute_preparation``) whose content
    reaches the prompt but which is never registered is reported by name and
    agent with cause ``unregistered``; the builder ran exactly once and its text
    is returned unchanged; the same computation, once registered, is clean.
    Wrong version caught: a gate that only audits what was registered."""
    built = fresh_build(tmp_path, monkeypatch)
    mod = built.mod
    name, calls = unique("zz-forgot"), []

    def builder() -> str:
        calls.append(1)
        return block_for(name, "zz-holder-a")

    content = mod.compute_preparation(name, "zz-holder-a", builder)
    assert content == block_for(name, "zz-holder-a") and calls == [1]
    append_block(built.roots, ["zz-holder-a"], content)
    found = per_agent(mod.verify_preparations_delivered(built.roots, expected_prompt_count=built.expected))
    assert {(f["agent"], f["preparation"], f["cause"]) for f in found} == {("zz-holder-a", name, "unregistered")}
    _register(mod, entry(name, "zz-holder-a", content))
    clean = mod.verify_preparations_delivered(built.roots, expected_prompt_count=built.expected)
    assert per_agent(clean) == [] and clean["ok"] is True
