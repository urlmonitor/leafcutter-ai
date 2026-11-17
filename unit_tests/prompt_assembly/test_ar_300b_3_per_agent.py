"""AR-300b-3 -- a preparation that reaches some agents and not others is reported
for EACH agent it missed: judged once per (agent, preparation, platform root),
over the agents it was REGISTERED FOR rather than the prompts it was found in.

Source of truth: .../AR-300b-3.yaml. Contract: _ar_300b_support.py (B). Today
both undelivered preparations fail for all agents at once, so every test
constructs the partial-delivery state deliberately: a preparation registered for
twelve agents of a real in-process build, delivered into chosen compiled prompts.

RED BASELINE: scripts/agent_preparation_delivery.py does not exist (absence red).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import agent_fm  # noqa: E402
from _ar_300b_support import (  # noqa: E402
    BODY,
    append_block,
    block_for,
    copy_roots,
    entry,
    fresh_build,
    per_agent,
    population,
    unique,
    verdict_of,
)

N = 12


def _twelve(tmp_path, monkeypatch):
    templates = {f"zz-many-{k:02d}": (agent_fm(f"zz-many-{k:02d}"), BODY) for k in range(N)}
    built = fresh_build(tmp_path, monkeypatch, templates)
    stems = sorted(templates)
    name = unique("zz-partial")
    preps = [entry(name, s, block_for(name, s)) for s in stems]
    return built, stems, name, preps


def _deliver(roots, name, stems) -> None:
    for s in stems:
        append_block(roots, [s], block_for(name, s))


def test_preparation_missing_from_a_subset_of_agents_reports_each_missed_agent(tmp_path, monkeypatch):
    # covers: AR-300b-3
    # angle: criterion
    """AR-300b-3: prepared for twelve agents, present in ten compiled prompts
    (both roots): exactly two agents are reported, each as its own finding per
    platform root (4 findings), not one summary finding, and the ten that
    received it are not named. Wrong versions caught: a per-kind summary, only
    the first missed agent, a finding for agents that did receive it."""
    built, stems, name, preps = _twelve(tmp_path, monkeypatch)
    missed = [stems[3], stems[8]]
    _deliver(built.roots, name, [s for s in stems if s not in missed])
    verdict = verdict_of(built.mod, built.roots, preps, built.expected)
    found = per_agent(verdict)
    assert sorted((f["agent"], f["platform_root"]) for f in found) == sorted(
        (s, str(r)) for s in missed for r in built.roots)
    assert {f["preparation"] for f in found} == {name} and verdict["ok"] is False
    assert verdict["affected_agent_counts"][name] == 2


def test_presence_in_other_prompts_does_not_satisfy_the_missed_agents(tmp_path, monkeypatch):
    # covers: AR-300b-3
    # angle: failure
    """AR-300b-3: however many OTHER prompts carry the preparation (1, 6 or 11 of
    12), the agent that lacks it stays reported, and the reported set is exactly
    the agents without it. Wrong version caught: a gate cleared by finding the
    preparation in any number of other prompts."""
    built, stems, name, preps = _twelve(tmp_path, monkeypatch)
    lacking = stems[-1]
    for delivered_count in (1, 6, 11):
        roots = copy_roots(built.roots, tmp_path / f"variant_{delivered_count}")
        _deliver(roots, name, stems[:delivered_count])
        found = per_agent(verdict_of(built.mod, roots, preps, built.expected))
        reported = {f["agent"] for f in found}
        assert lacking in reported, f"{delivered_count} other prompts cleared {lacking}"
        assert reported == set(stems[delivered_count:]), (delivered_count, sorted(reported))
        assert len(found) == len(reported) * len(roots)


def test_judgement_is_per_agent_not_per_preparation_kind(tmp_path, monkeypatch):
    # covers: AR-300b-3
    # angle: criterion
    """AR-300b-3: ONE example of the preparation landing (in a single prompt of
    twelve) does not mark the kind delivered: the other eleven agents are each
    reported and the affected-agent count says 11. Wrong version caught: the
    cheap check that confirms each kind landed somewhere."""
    built, stems, name, preps = _twelve(tmp_path, monkeypatch)
    _deliver(built.roots, name, [stems[0]])
    verdict = verdict_of(built.mod, built.roots, preps, built.expected)
    assert {f["agent"] for f in per_agent(verdict)} == set(stems[1:])
    assert verdict["ok"] is False and verdict["affected_agent_counts"][name] == N - 1


def test_iteration_is_over_the_prepared_for_set_not_the_found_set(tmp_path, monkeypatch):
    # covers: AR-300b-3
    # angle: boundary
    """AR-300b-3: an agent the preparation was registered for whose compiled
    prompt does not exist in the gemini root at all (so the preparation is found
    nowhere there) is still discovered, in that root only; its claude-root
    prompt, which carries the block, is clean. Wrong version caught: iterating
    only over prompts containing the preparation (vacuously true for exactly the
    agents it was meant to protect)."""
    built, stems, name, preps = _twelve(tmp_path, monkeypatch)
    claude_root, gemini_root = built.roots
    ghost = stems[5]
    _deliver(built.roots, name, [s for s in stems if s != ghost])
    append_block([claude_root], [ghost], block_for(name, ghost))
    (gemini_root / f"{ghost}.md").unlink()
    verdict = verdict_of(built.mod, built.roots, preps, built.expected)
    found = per_agent(verdict)
    assert [(f["agent"], f["platform_root"], f["preparation"]) for f in found] == [
        (ghost, str(gemini_root), name)], found
    assert population(verdict, "short-population"), "a missing prompt also shortens the examined population"
