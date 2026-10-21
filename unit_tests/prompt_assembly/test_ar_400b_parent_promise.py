"""AR-400b -- every ability a specialist is told to use is in that specialist's OWN declared grant, and the check
recognises an instruction correctly (composite-closure contract; one real build.py run, refused before deploy).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/AR-400b.yaml (test_spec).

Test 1 reads the shared deployed layout (``shared_layout_reader``; no build of its own). The comparison side is read
from each definition under templates/agents -- compiled prompts do not carry the declaration and the derived
registry copy is never consulted. The scan uses the build's own recognition rule (``skill_ref_recognition``).
Test 2 is the one build this parent pays for (``shared_layout_mutator``): one true instruction beside three
sentences that only look like one, so a check that is simply loose, or that only warns, fails.
"""

from __future__ import annotations

import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar400_3a_fixtures as F  # noqa: E402
import _ar400_3c_fixtures as X  # noqa: E402
import _ar400_parent_support as P  # noqa: E402

PROBE = "probe-agent"
GENUINE = "Load the `knowledge-query` skill first."
NEGATED = "You do not invoke the `route-knowledge` skill."
OTHER_SUBJECT = ("**Note:** `frontend-coder` may invoke the `webapp-testing` skill internally as part of "
                 "its own phase.")
CITATION = ("This shape is normatively defined in `templates/skills/signoff/SKILL.md` section 7 -- the field set "
            "below must match that definition.")


def _rotated(grants: dict[str, set[str]]) -> dict[str, set[str]]:
    """Every specialist given the NEXT specialist's grant: an instruction satisfied by another's grant."""
    names = sorted(grants)
    return {a: grants[names[(i + 1) % len(names)]] for i, a in enumerate(names)}


@pytest.mark.shared_layout_reader
def test_ar_400b_every_deployed_instruction_is_in_the_specialists_own_grant(shared_reference_layout):
    # covers: AR-400b
    # angle: deployed
    # must_catch: the comparison is made against the derived central registry copy instead of the specialist's own declaration
    # must_catch: an instruction is satisfied by a grant to a different specialist
    """Every ability a compiled prompt tells its specialist to use is in the grant declared by that specialist's own
    definition and is named in the prompt's delivered abilities section (a project-supplied one is stated as not
    installed); the number of specialists examined equals the definitions in the tree and the instructions seen
    are non-zero. Control: the same scan with every grant rotated to the NEXT specialist reports many problems,
    so an instruction satisfied by another specialist's grant would not pass."""
    grants, hidden = P.definitions(), P.hidden_grants()
    known = P.deployed_skill_ids(shared_reference_layout)
    agent_ids = {a["id"] for a in P.deployed_registry(shared_reference_layout)["agents"]}
    roots = P.prompts_by_root(shared_reference_layout)
    assert len(roots) >= 2, sorted(roots)
    for where, prompts in roots.items():
        problems, examined, seen = P.instruction_problems(prompts, grants, hidden, known, agent_ids)
        assert problems == [], f"{where}: {problems[:5]}"
        assert examined == len(grants) > 0, (where, examined, len(grants))
        assert seen >= 20, f"{where}: only {seen} instructions seen -- the scan is not looking"
    prompts = roots[sorted(roots)[0]]
    rotated, _n, rotated_seen = P.instruction_problems(prompts, _rotated(grants), hidden, known, agent_ids)
    assert len(rotated) >= 10 and rotated_seen >= 20, (len(rotated), rotated_seen)
    assert all(re.search(r"told to use [\w-]+, its own definition grants", p) for p in rotated), rotated[:3]


@pytest.mark.shared_layout_mutator
def test_ar_400b_one_real_mismatch_among_non_instructions_stops_one_build_naming_both_sides():
    # covers: AR-400b
    # angle: discrimination
    # must_catch: every mention of an ability name is treated as an instruction, giving four findings instead of one
    # must_catch: the mismatch is reported as a warning and the build passes
    # must_catch: the finding names only one side (the ability) and not the specialist's grant
    """One specialist holds one genuine instruction to use an existing ability it is not granted (knowledge-query)
    beside a negated sentence, a sentence about what another specialist uses, and a citation of an ability's file.
    ONE real build.py run exits non-zero before deploying anything and prints exactly ONE finding, naming the
    specialist, the ability and that the specialist's own definition grants nothing."""
    root = X.new_package()
    F.plant(root, PROBE, [GENUINE, NEGATED, OTHER_SUBJECT, CITATION], described=True)
    rc, out = X.run_build(root, root.parent)
    every = list(dict.fromkeys(F.findings(out)))
    mine = list(dict.fromkeys(F.about(out, PROBE)))
    assert every == mine and len(mine) == 1, f"expected exactly the one genuine finding: {every}"
    line = mine[0]
    assert F.UNGRANTED in line.lower() and F.names(line, "knowledge-query"), line
    assert re.search(rf"{PROBE} grants:\s*nothing", line), f"the finding does not name the specialist's own grant: {line}"
    assert [o for o in ("route-knowledge", "webapp-testing", "signoff") if F.names(line, o)] == [], line
    assert "WARNING" not in line.upper() and rc != 0, f"exit {rc}; a mismatch must refuse, not warn"
    assert X.compiled_agent_roots(root.parent) == [], "the build deployed despite the finding"
