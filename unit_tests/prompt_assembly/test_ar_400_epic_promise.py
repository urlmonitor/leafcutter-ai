"""AR-400 (the goal) -- a clean build means every specialist's setup is coherent: the validator's verdict on
every specialist AND the prompt each specialist actually receives, over the checked-out tree and the shared
deployed layout (composite-closure contract; zero build.py runs of its own).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/AR-400.yaml (test_spec).
Each "nothing found" half sits beside a control that must fire in the same test: a copy with one ungranted
instruction and one redundant hand-off entry is refused by the real validator CLI, and a compiled prompt with a
row removed or a foreign row added is reported by the same comparison that passes on the real prompts.

HONEST SCOPE: the redundant-hand-off control needs the AR-400f-1 gate (slice 3c); until it lands this test
fails on that control, and only on it.
"""

from __future__ import annotations

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400a_1_support as H  # noqa: E402
import _ar400_3a_fixtures as F  # noqa: E402
import _ar400_3c_fixtures as X  # noqa: E402
import _ar400_parent_support as P  # noqa: E402


def _validator_controls_fire() -> tuple[int, str]:
    """A copy holding one ungranted instruction and one redundant hand-off entry: (exit, output)."""
    def plant(root):
        F.plant(root, "probe-ug", ["Load the `knowledge-query` skill first."])
        X.plant_redundant(root)

    return F.slice_cli(plant)


def _row_of(text: str, ability: str) -> str:
    return next(ln for ln in text.splitlines() if re.match(rf"^\|\s*{re.escape(ability)}\s*\|", ln))


def _prompt_controls(prompts: dict[str, str], decl, hidden, installed) -> tuple[list[str], list[str]]:
    """(problems when a row is removed, problems when a foreign row is added) for one real prompt."""
    agent = next(a for a, g in sorted(decl.items()) if g - hidden.get(a, set()))
    sid = sorted(decl[agent] - hidden.get(agent, set()))[0]
    row = _row_of(prompts[agent], sid)
    foreign = sorted(installed - decl[agent])[0]
    dropped = prompts[agent].replace(row + "\n", "", 1)
    added = prompts[agent].replace(row, f"{row}\n| {foreign} | always | planted |", 1)
    assert dropped != prompts[agent] and added != prompts[agent], "control edits changed nothing"
    mine = {agent: decl[agent]}
    return (P.account_problems({agent: dropped}, mine, hidden, installed),
            P.account_problems({agent: added}, mine, hidden, installed))


@pytest.mark.shared_layout_reader
def test_ar_400_real_tree_setup_is_coherent_and_every_prompt_lists_its_declared_abilities(shared_reference_layout):
    # covers: AR-400
    # angle: real_artifact
    # must_catch: the checks pass because they examined no specialists
    # must_catch: the validator is clean but a compiled prompt offers an ability its specialist does not declare, or omits one it does
    """Real tree: the validator CLI exits 0 with zero ability and hand-off findings and reports a non-zero
    examined count equal to the specialist definitions under templates/agents; every specialist's compiled
    prompt, in every platform root, lists exactly the abilities its own definition declares (a project-supplied
    one the package does not ship is stated as not installed, never listed). Controls: planted faults are
    refused by the same CLI, and a prompt with a row removed or a foreign row added is reported."""
    decl, hidden = P.definitions(), P.hidden_grants()
    installed = P.deployed_skill_ids(shared_reference_layout)
    rc, out = F.real_cli()
    assert (rc, F.findings(out), X.hand_off_hits(out)) == (0, [], []), out[-1500:]
    examined = X.definitions_in_tree(F.REPO_ROOT)
    assert examined == len(decl) > 0 and set(H.reported(out, "definition")) == {examined}, (examined, out[-500:])

    roots = P.prompts_by_root(shared_reference_layout)
    assert len(roots) >= 2, f"expected both platform roots, got {sorted(roots)}"
    for where, prompts in roots.items():
        assert len(prompts) == examined, f"{where}: {len(prompts)} compiled prompts, {examined} definitions"
        assert P.account_problems(prompts, decl, hidden, installed) == [], where
    assert hidden, "control: the real tree must carry a project-supplied grant for the not-installed half"
    verdict, expected = P.delivery_verdict(shared_reference_layout)
    assert (verdict["ok"], verdict["findings"], verdict["inspected_count"]) == (True, [], expected), verdict["findings"][:3]
    assert expected == examined * len(roots), (expected, examined, len(roots))

    removed, added = _prompt_controls(roots[sorted(roots)[0]], decl, hidden, installed)
    assert len(removed) == 1 and len(added) == 1, (removed, added)

    c_rc, c_out = _validator_controls_fire()
    assert len(F.of_kind(c_out, F.UNGRANTED, "knowledge-query", "probe-ug")) == 1, c_out[-1200:]
    assert len(X.hand_off_hits(c_out, X.REDUNDANT)) == 1 and c_rc != 0, c_out[-1200:]
