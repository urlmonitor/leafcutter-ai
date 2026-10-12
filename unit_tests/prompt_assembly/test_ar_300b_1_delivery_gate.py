"""AR-300b-1 -- a per-agent preparation that does not reach its agent ends the
run in failure, judged from the COMPILED prompt (never from the point of
preparation), for the abilities section AND the spawn-allowlist section
independently, in every platform root the build wrote.

Source of truth: .../AR-300b-1.yaml. Contract: _ar_300b_support.py (A-D).
Trees are authentic: the REAL ``build_agents`` phase run in-process over a
planted package, or a real build.py run; the mutation breaks ONLY the compiled
artifact while the inputs stay correct.

RED BASELINE: scripts/agent_preparation_delivery.py does not exist, so every
test fails on its import (an absence red) -- the real-build test fails because
the build exits 0 over a stripped compiled prompt.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import real_declarations  # noqa: E402
from _ar_300b_support import (  # noqa: E402
    abilities_preps,
    copy_roots,
    deliver_spawn,
    fresh_build,
    per_agent,
    real_build,
    remove_text,
    run_real_build,
    strip_abilities,
    undelivered_names,
    verdict_of,
)


@pytest.mark.shared_layout_mutator
def test_build_fails_when_a_prepared_block_is_absent_from_the_compiled_prompt(
        shared_reference_layout, tmp_path, monkeypatch):
    # covers: AR-300b-1
    # angle: deployed
    """AR-300b-1: a real build.py run over a private deployed copy, with ONLY
    the compiled agent prompts broken (abilities section removed as they are
    written; templates, registry and the computation stay correct), exits
    non-zero, and its output names the agents and the preparation that did not
    reach them. Control: the fixture's own unmutated build of the same tree
    exited 0 (the fixture refuses a failing build), so the failure is caused by
    the broken artifact. Wrong versions caught: a build that reports success
    over undelivered content, a gate that reads the registration/preparation
    instead of the compiled prompt, a failure that does not name agent and
    preparation."""
    granted = sorted(real_declarations())
    assert granted, "0 templates declare a grant -- nothing prepared to lose"
    victim = granted[0]
    skill_id = next(iter(real_declarations()[victim]))
    skill_id = skill_id["skill_id"] if isinstance(skill_id, dict) else skill_id
    in_process = real_build(tmp_path / "ref", monkeypatch)
    names = {p["preparation_name"] for p in abilities_preps(in_process.preparations, victim, skill_id)}
    assert names, "control: the real compile registered no abilities preparation for the victim"

    proc = run_real_build(shared_reference_layout, tmp_path, strip_compiled_abilities=True)
    out = proc.stdout + proc.stderr
    assert proc.returncode != 0, f"build reported success over undelivered preparations: {out[-600:]}"
    assert victim in out and granted[-1] in out, "failure does not name the agents that went without"
    assert any(n in out for n in names), f"failure does not name the preparation {names}: {out[-600:]}"


def test_failure_names_the_agent_and_the_preparation(tmp_path, monkeypatch):
    # covers: AR-300b-1
    # angle: criterion
    """AR-300b-1: each finding carries the agent id and the preparation name as
    stated fields -- exactly the agent that lost its section and exactly the
    preparations that no longer appear in its compiled prompt (derived
    independently from the compiled text), one per platform root."""
    built = fresh_build(tmp_path, monkeypatch)
    victim = "zz-holder-a"
    assert abilities_preps(built.preparations, victim, "zz-alpha"), "control: nothing registered for the victim"
    strip_abilities(built.roots, [victim])
    expected = undelivered_names(built.preparations, victim, built.roots[0])
    assert expected, "control: the strip left every registered preparation in the prompt"
    found = per_agent(verdict_of(built.mod, built.roots, built.preparations, built.expected))
    assert {f["agent"] for f in found} == {victim}
    assert {f["preparation"] for f in found} == expected
    assert len(found) == len(expected) * len(built.roots)
    assert all(f["agent"] and f["preparation"] and f["platform_root"] for f in found)


def test_both_dead_preparations_are_reported_independently(tmp_path, monkeypatch):
    # covers: AR-300b-1
    # angle: real_artifact
    """AR-300b-1: the abilities section (real compile) and the spawn-allowlist
    section (content = the REAL ``build_per_agent_spawn_table`` output, delivered
    into the compiled prompts) are separate findings. Breaking only the
    abilities section reports abilities and not spawn; breaking only the spawn
    section reports spawn and not abilities (so repairing abilities alone still
    leaves spawn reported); breaking both reports both. Wrong version caught: a
    gate aimed at one preparation (fix one, the other stays silent)."""
    built = fresh_build(tmp_path, monkeypatch)
    spawn = deliver_spawn(built)
    preps = built.preparations + spawn
    stems = sorted(built.templates)
    granted = [s for s in stems if s != "zz-plain"]
    probe = _stripped_copy(built, tmp_path / "probe", granted)[0]
    ab_names = {n for s in granted for n in undelivered_names(built.preparations, s, probe)}
    assert ab_names, "control: no abilities preparation registered"

    only_ab = _stripped_copy(built, tmp_path / "ab", granted)
    names_ab = {f["preparation"] for f in per_agent(verdict_of(built.mod, only_ab, preps, built.expected))}
    assert ab_names <= names_ab and "zz-spawn-allowlist" not in names_ab, names_ab

    only_sp = copy_roots(built.roots, tmp_path / "sp")
    for e in spawn:
        remove_text(only_sp, [e["agent"]], e["content"])
    found_sp = per_agent(verdict_of(built.mod, only_sp, preps, built.expected))
    assert not ab_names & {f["preparation"] for f in found_sp}, "abilities reported though it was repaired"
    assert sum(f["preparation"] == "zz-spawn-allowlist" for f in found_sp) == len(stems) * len(only_sp)

    both = _stripped_copy(built, tmp_path / "both", granted)
    for e in spawn:
        remove_text(both, [e["agent"]], e["content"])
    names_both = {f["preparation"] for f in per_agent(verdict_of(built.mod, both, preps, built.expected))}
    assert ab_names | {"zz-spawn-allowlist"} <= names_both


def _stripped_copy(built, dst, stems):
    roots = copy_roots(built.roots, dst)
    strip_abilities(roots, stems)
    return roots


def test_verdict_is_derived_from_the_compiled_prompt_not_the_preparation(tmp_path, monkeypatch):
    # covers: AR-300b-1
    # angle: real_artifact
    """AR-300b-1 mutation proof: the preparation is computed correctly (every
    registered entry has non-empty content and a destination offered -- what a
    point-of-preparation check inspects, and which therefore PASSES) yet the
    compiled prompt lacks it, and the gate fails. Control: the unmutated tree is
    clean over the same registrations. Wrong version caught: a check at the
    point of preparation (passes this mutation, which is the defect)."""
    built = fresh_build(tmp_path, monkeypatch)
    clean = verdict_of(built.mod, built.roots, built.preparations, built.expected)
    assert clean["ok"] is True and not per_agent(clean), clean["findings"]
    strip_abilities(built.roots, ["zz-holder-a", "zz-holder-b"])
    assert built.preparations, "control: nothing registered"
    registered_ab = [p for p in built.preparations if p["agent"] in {"zz-holder-a", "zz-holder-b"}]
    assert registered_ab and all(p["content"].strip() and p["destination_offered"] for p in registered_ab), (
        "the preparation side is correct, so a preparation-side check would pass")
    assert built.mod.get_preparations() == built.preparations, "the strip changed what was registered"
    broken = verdict_of(built.mod, built.roots, built.preparations, built.expected)
    assert broken["ok"] is False
    assert {f["agent"] for f in per_agent(broken)} == {"zz-holder-a", "zz-holder-b"}


def test_gate_examines_every_platform_root_the_build_wrote(tmp_path, monkeypatch):
    # covers: AR-300b-1
    # angle: deployed
    """AR-300b-1: a preparation missing ONLY from the gemini platform root is
    still reported -- for every agent that lost it, in that root alone -- while
    the claude root (the one a hard-coded shim read would see) stays clean.
    Exact count: granted agents x undelivered preparations, one per agent."""
    built = fresh_build(tmp_path, monkeypatch)
    claude_root, gemini_root = built.roots
    granted = ["zz-holder-a", "zz-holder-b", "zz-holder-c"]
    strip_abilities([gemini_root], granted)
    expected = {(s, n) for s in granted for n in undelivered_names(built.preparations, s, gemini_root)}
    assert expected, "control: nothing undelivered in the gemini root"
    verdict = verdict_of(built.mod, built.roots, built.preparations, built.expected)
    found = per_agent(verdict)
    assert {(f["agent"], f["preparation"]) for f in found} == expected
    assert len(found) == len(expected), "a finding is duplicated or missing a root"
    assert all(os.path.realpath(f["platform_root"]) == os.path.realpath(gemini_root) for f in found)
    assert verdict["ok"] is False
