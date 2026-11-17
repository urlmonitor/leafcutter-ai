"""AR-400c -- nothing that is not a fault is reported, and the faults the noise hid are fixed (composite-closure
contract; zero build.py runs of its own).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/AR-400c.yaml (test_spec).

Test 1 drives the real registry validator CLI over a copied package slice with every message severity in scope
(AR-400c-4's real-build check filters on warnings only). Test 2 reads the shared deployed layout
(``shared_layout_reader``) and generalises AR-400c-3 beyond llm-expert.

HONEST SCOPE: the redundant hand-off entry in test 1 needs the AR-400f-1 gate (slice 3c); the other two faults and
the unmentioned-grant silence hold today.

INTERPRETATION: "exactly one delivered abilities section" cannot mean one for a specialist that grants nothing
(AR-300a-3 forbids a section for an ungranted specialist), so it is asserted as one delivered heading where the
definition declares a listed grant and none where it declares none, together with the build's own single-account
delivery verdict over every prompt.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400a_1_support as H  # noqa: E402
import _ar400_3a_fixtures as F  # noqa: E402
import _ar400_3c_fixtures as X  # noqa: E402
import _ar400_parent_support as P  # noqa: E402

UNMENTIONED = "probe-unmentioned"


def _plant_three_faults_and_a_quiet_grant(root) -> None:
    """Nonexistent ability, ungranted ability, redundant hand-off entry -- and a granted ability the
    specialist's instructions never mention (the obsolete 'granted but unmentioned' direction)."""
    F.plant(root, "probe-nx", [H.GHOST_SENTENCE])
    F.plant(root, "probe-ug", ["Load the `knowledge-query` skill first."])
    X.plant_redundant(root)
    F.plant(root, UNMENTIONED, [H.FILLER], grants=("signoff",))


def test_ar_400c_three_planted_faults_and_one_unmentioned_grant_yield_exactly_three_lines():
    # covers: AR-400c
    # angle: discrimination
    # must_catch: the obsolete 'granted but never mentioned' direction is kept as a quieter message (info or notice) instead of being removed
    # must_catch: the noise is removed by suppressing all ability output, so a real fault beside it is silenced too
    """In a copy of the package: one nonexistent-ability instruction, one ungranted-ability instruction, one
    redundant hand-off entry and one granted ability the specialist never mentions. The validator CLI exits
    non-zero; its ability and hand-off output holds exactly three finding lines, one per real fault (each naming
    its own specialist), and no line of any severity names the specialist whose grant is merely unmentioned."""
    rc, out = F.slice_cli(_plant_three_faults_and_a_quiet_grant)
    lines = list(dict.fromkeys(F.findings(out) + X.hand_off_hits(out)))
    errors = list(dict.fromkeys(ln.strip() for ln in out.splitlines() if ln.startswith("ERROR")))
    assert len(lines) == 3 and len(errors) == 3, f"expected exactly three finding lines:\n{out[-1800:]}"
    mine = {name: [ln for ln in lines if F.names(ln, name)] for name in ("probe-nx", "probe-ug", X.SUP)}
    assert [len(v) for v in mine.values()] == [1, 1, 1], mine
    assert F.NONEXIST in mine["probe-nx"][0].lower() and F.UNGRANTED in mine["probe-ug"][0].lower(), mine
    assert X.REDUNDANT in mine[X.SUP][0].lower() and F.names(mine[X.SUP][0], "llm-expert"), mine
    assert [ln for ln in out.splitlines() if UNMENTIONED in ln] == [], "the unmentioned grant is still reported"
    assert rc != 0, out[-800:]


@pytest.mark.shared_layout_reader
def test_ar_400c_every_deployed_prompt_has_one_abilities_section_and_no_dead_grant(shared_reference_layout):
    # covers: AR-400c
    # angle: deployed
    # must_catch: authoring guidance still asks for a hand-written abilities section, so some specialist other than llm-expert compiles with two
    """Every compiled prompt, in every platform root, carries exactly one delivered abilities section where its
    definition declares a listed grant and none where it declares none (and the build's delivery verdict finds one
    account per prompt); the compiled adr-author does not offer doc-enforcer and the compiled product-owner does
    not offer signoff. Controls: the population holds both granting and non-granting specialists, adr-author still
    offers signoff and product-owner still offers its other grants, and a prompt with a second delivered heading
    appended is counted as two."""
    decl, hidden = P.definitions(), P.hidden_grants()
    installed = P.deployed_skill_ids(shared_reference_layout)
    roots = P.prompts_by_root(shared_reference_layout)
    assert len(roots) >= 2, sorted(roots)
    wanted = {a: 1 if g - hidden.get(a, set()) else 0 for a, g in decl.items()}
    assert set(wanted.values()) == {0, 1}, "control: the population must hold granting and non-granting specialists"
    for where, prompts in roots.items():
        counted = {a: P.delivered_headings(t) for a, t in prompts.items()}
        assert counted == wanted, f"{where}: {[(a, n, wanted.get(a)) for a, n in sorted(counted.items()) if n != wanted.get(a)]}"
        offered = {a: set(P.prompt_view({a: prompts[a]}, decl, hidden, installed).abilities[a])
                   for a in ("adr-author", "product-owner")}
        assert "doc-enforcer" not in offered["adr-author"] and "signoff" in offered["adr-author"], offered
        assert "signoff" not in offered["product-owner"] and offered["product-owner"] == decl["product-owner"], offered
    verdict, expected = P.delivery_verdict(shared_reference_layout)
    assert (verdict["ok"], verdict["findings"], verdict["inspected_count"]) == (True, [], expected), verdict["findings"][:3]
    doubled = roots[sorted(roots)[0]]["adr-author"] + "\n\n## Your Available Skills\n\n| Skill | Mode |\n|---|---|\n"
    assert P.delivered_headings(doubled) == 2
