"""AR-400a -- an instruction to use an ability that does not exist stops the build, in a specialist definition AND
in a shared guide, and nothing that ships tells its reader to load an ability that is not deployed
(composite-closure contract; one real build.py run, refused before any deploy).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/AR-400a.yaml (test_spec).

Test 1 reads the shared deployed layout (``shared_layout_reader``; no build of its own) and covers the surface no
child checks -- what actually ships. The "deployed view" is a scratch slice whose agents, abilities and registry are
the DEPLOYED copies, scanned with the build's own recognition rule and cross-checked through the real validator CLI.
Citations ("see `.claude/skills/x/SKILL.md`") are not instructions to load (AR-400b-2-iii): frontend-coder's
"Do NOT read .claude/skills/frontend-design/SKILL.md" (a legacy file the build deliberately does not deploy) is one.
Test 2 is the one build this parent pays for (``shared_layout_mutator``).
"""

from __future__ import annotations

import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400a_1_support as H  # noqa: E402
import _ar400_3a_fixtures as F  # noqa: E402
import _ar400_3c_fixtures as X  # noqa: E402
import _ar400_parent_support as P  # noqa: E402

README = "templates/skills/README.md"


def _plant_ghost_in_view(root, prompt: str, guide: str) -> None:
    """The ghost-ability sentence on a line of one deployed prompt and of one deployed guide."""
    H.put_line(root / "templates" / "agents" / f"{prompt}.md", 60, H.GHOST_SENTENCE)
    H.put_line(root / "templates" / "skills" / guide / "SKILL.md", 12, H.GHOST_SENTENCE)


@pytest.mark.shared_layout_reader
def test_ar_400a_every_ability_named_in_deployed_prompts_and_guides_is_deployed(shared_reference_layout, tmp_path):
    # covers: AR-400a
    # angle: deployed
    # must_catch: the source tree is clean but a dangling reference is reintroduced at deploy time (a guide or prompt fragment that only exists in the deployed layout)
    # must_catch: the check examines zero prompts or guides and so reports nothing
    """Over the deployed view: no instruction in a compiled prompt or deployed guide names an ability the deploy
    lacks (a project-supplied grant excepted); the prompts and guides examined are non-zero and equal the
    figures derived independently from the tree and reported by the validator CLI. Controls: a ghost sentence
    planted in one deployed prompt and one deployed guide is found by the scan AND by the CLI, and withdrawing
    a deployed ability (the shape of a deploy-manifest gap) makes the scan report its instructions."""
    supplied = P.hidden_grants()
    view = P.deployed_view(shared_reference_layout, tmp_path / "view")
    findings, n_defs, n_guides = P.dangling_instructions(view, supplied)
    assert findings == [], findings[:5]
    assert n_defs == len(P.definitions()) > 0, (n_defs, len(P.definitions()))
    deployed_md = sum(len(list((view / "templates" / sub).rglob("*.md"))) for sub in ("agents", "skills"))
    assert n_guides == deployed_md - len(P.definitions()) > 0, (n_guides, deployed_md)

    rc, out = H.cli(view)
    assert n_defs in H.reported(out, "definition") and H.expected_counts(view)[1] in H.reported(out, "guide"), out[-600:]

    _plant_ghost_in_view(view, "python-coder", "signoff")
    planted, _d, _g = P.dangling_instructions(view, supplied)
    assert len(planted) == 2 and all(H.GHOST in f for f in planted), planted
    assert len(F.of_kind(H.cli(view)[1], F.NONEXIST, H.GHOST)) == 2

    shutil.rmtree(view / "templates" / "skills" / "knowledge-query")
    gap, _d2, _g2 = P.dangling_instructions(view, supplied)
    assert {f.split()[-1] for f in gap} >= {"knowledge-query", H.GHOST}, "withdrawing a deployed ability was not seen"


@pytest.mark.shared_layout_mutator
def test_ar_400a_ghost_ability_in_a_definition_and_a_guide_stops_one_build_naming_both():
    # covers: AR-400a
    # angle: discrimination
    # must_catch: the build stops at the first finding and never reports the second
    # must_catch: only specialist definitions are checked, so the shared-guide instance passes
    # must_catch: the finding is printed as a warning and the build still deploys
    """A package copy holds one nonexistent-ability instruction in a specialist definition (line 40) and one in
    the shared ability catalogue (line 12). ONE real build.py run into a fresh target exits non-zero before any
    specialist is deployed, and prints exactly two findings, each naming its specialist or guide, the ability,
    the repo-relative file and the line, neither as a warning."""
    root = X.new_package()
    H.plant_agent(root, "probe-agent", sentence=H.GHOST_SENTENCE, line=40)
    H.put_line(root / README, 12, H.GHOST_SENTENCE)
    rc, out = X.run_build(root, root.parent)
    hits = list(dict.fromkeys(H.findings(out, H.GHOST)))
    by_file = {name: [h for h in hits if H.names_line(h, name, line)]
               for name, line in (("templates/agents/probe-agent.md", 40), (README, 12))}
    assert len(hits) == 2 and [len(v) for v in by_file.values()] == [1, 1], (hits, out[-1200:])
    assert "probe-agent" in by_file["templates/agents/probe-agent.md"][0], by_file
    assert [h for h in hits if "WARNING" in h.upper()] == [], hits
    assert rc != 0 and X.compiled_agent_roots(root.parent) == [], f"exit {rc}; the build deployed despite the findings"
