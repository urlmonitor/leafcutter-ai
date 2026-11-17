"""AR-300b-1-i -- a build in which every per-agent preparation reached its agent
reports no delivery failure, STILL states how many preparation kinds it checked
and across how many compiled prompts (a clean result is distinguishable from a
check that did not run), and does not fire on the real repository population.

Source of truth: .../AR-300b-1-i.yaml. Contract: _ar_300b_support.py (A-D). The
clean path emits the SAME verdict object as the failure path (empty findings,
counts populated).

RED BASELINE: scripts/agent_preparation_delivery.py does not exist (absence red
on every test); the real-build test fails because the build prints no counts.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_300ad_support import real_declarations, source_templates  # noqa: E402
from _ar_300b_support import (  # noqa: E402
    COUNTS_RE,
    abilities_preps,
    fresh_build,
    norm,
    per_agent,
    real_build,
    run_real_build,
    verdict_of,
)


@pytest.mark.shared_layout_mutator
def test_fully_delivered_build_reports_no_delivery_failure(shared_reference_layout, tmp_path, monkeypatch):
    # covers: AR-300b-1-i
    # angle: deployed
    """AR-300b-1-i: rebuilding a private deployed copy of the real tree with the
    real build.py (nothing broken) completes with exit 0, and its OWN output
    states the counts -- the number of preparation kinds checked and the number
    of compiled prompts (every agent template x both platform roots) -- so a
    clean build is distinguishable from one whose delivery check did not run.
    Wrong versions caught: a gate that blocks a correct build, a clean path that
    prints nothing, a clean path that omits either count."""
    reference = real_build(tmp_path / "ref", monkeypatch)
    kinds = len({p["preparation_name"] for p in reference.preparations})
    assert kinds >= 1 and reference.expected > 0, "control: the reference build registered nothing"

    proc = run_real_build(shared_reference_layout, tmp_path, strip_compiled_abilities=False)
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, f"a fully delivered build was refused: {out[-600:]}"
    stated = COUNTS_RE.findall(out)
    assert stated, f"the clean build states no 'K preparation kinds checked across N compiled prompts': {out[-600:]}"
    assert (str(kinds), str(reference.expected)) in stated, (stated, kinds, reference.expected)


def test_clean_run_still_states_both_counts(tmp_path, monkeypatch, capsys):
    # covers: AR-300b-1-i
    # angle: criterion
    """AR-300b-1-i: the clean verdict carries both counts as exact numbers -- the
    prompts read (agents x roots) and the distinct preparation kinds covered --
    with an empty findings list; the build seam prints them and returns 0.
    Wrong version caught: a clean path that skips the traversal and reports 0 /
    omits a count (counts must come from the same traversal as a failure)."""
    built = fresh_build(tmp_path, monkeypatch)
    names = sorted({p["preparation_name"] for p in built.preparations})
    assert names, "control: nothing registered"
    verdict = verdict_of(built.mod, built.roots, built.preparations, built.expected)
    assert verdict["ok"] is True and verdict["findings"] == []
    assert verdict["inspected_prompt_count"] == built.expected == 8
    assert verdict["inspected_preparation_kinds"] == len(names)
    assert verdict["preparation_kinds"] == names
    assert verdict["population_source"]
    line = built.mod.render_preparation_verdict(verdict).splitlines()[0]
    assert COUNTS_RE.search(line).groups() == (str(len(names)), "8"), line

    capsys.readouterr()
    rc = built.mod.refuse_on_undelivered_preparations(
        built.project, {"output_root": ".leafcutter"}, False, expected_prompt_count=built.expected)
    out = capsys.readouterr()
    assert rc == 0
    assert COUNTS_RE.search(out.out + out.err), "the clean seam run states no counts"


def test_clean_run_is_distinguishable_from_a_run_that_examined_nothing(tmp_path, monkeypatch):
    # covers: AR-300b-1-i
    # angle: boundary
    """AR-300b-1-i: within ONE test (no second-run comparison of the same
    state) the clean verdict and the nothing-to-examine verdict differ in ok,
    findings and rendered text: the clean one states its counts and never says
    'nothing to examine'; the empty one says it and is not ok. Wrong version
    caught: both states producing an empty findings list with no other
    difference."""
    built = fresh_build(tmp_path, monkeypatch)
    clean = verdict_of(built.mod, built.roots, built.preparations, built.expected)
    nothing = verdict_of(built.mod, built.roots, [], built.expected)
    assert clean["ok"] is True and nothing["ok"] is False
    assert clean["findings"] == [] and nothing["findings"], "an empty population produced no finding"
    clean_text = built.mod.render_preparation_verdict(clean).lower()
    nothing_text = built.mod.render_preparation_verdict(nothing).lower()
    assert "nothing to examine" in nothing_text and "nothing to examine" not in clean_text
    assert COUNTS_RE.search(clean_text) and clean_text != nothing_text


def test_gate_does_not_fire_on_the_real_repository_population(tmp_path, monkeypatch, capsys):
    # covers: AR-300b-1-i
    # angle: real_artifact
    """AR-300b-1-i: the REAL ``build_agents`` over a copy of the actual
    templates/agents tree gives a clean verdict with a non-zero examined
    population -- every agent template in both roots -- and every granted real
    agent has a registered preparation whose content is, by an independent
    whitespace-normalised read, in each of its compiled prompts. Wrong version
    caught: a gate that fires on every real build (switched off within a day),
    or one that is clean because it examined nothing."""
    built = real_build(tmp_path, monkeypatch)
    assert built.expected >= 2 and built.preparations, "control: empty real population"
    verdict = verdict_of(built.mod, built.roots, built.preparations, built.expected)
    assert per_agent(verdict) == [] and verdict["ok"] is True, verdict["findings"][:5]
    assert verdict["inspected_prompt_count"] == built.expected == len(source_templates()) * 2
    assert verdict["inspected_preparation_kinds"] >= 1
    for stem, entries in sorted(real_declarations().items()):
        first = entries[0]["skill_id"] if isinstance(entries[0], dict) else entries[0]
        assert abilities_preps(built.preparations, stem, first), f"{stem}: granted but nothing registered"
    for root in built.roots:
        for p in built.preparations:
            text = norm((root / f"{p['agent']}.md").read_text(encoding="utf-8"))
            assert norm(p["content"]) in text, f"{p['preparation_name']} not in {p['agent']} ({root})"
    capsys.readouterr()
    rc = built.mod.refuse_on_undelivered_preparations(
        built.project, {"output_root": ".leafcutter"}, False, expected_prompt_count=built.expected)
    assert rc == 0
