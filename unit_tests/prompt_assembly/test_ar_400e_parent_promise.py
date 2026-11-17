"""AR-400e -- every VIEW of a specialist's abilities (the prompt it receives, the published card, the architecture
diagram, the knowledge graph, the registry) agrees with the specialist's own declaration (composite-closure
contract; zero build.py runs of its own).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/AR-400e.yaml (test_spec).
AR-400e-1 checks the same equality through the producing functions over the source tree; this test checks what
ships, from the reader's side.

VIEWS NOT IN THE SHARED LAYOUT, READ FROM THE REAL TREE (no extra build):
  * published cards: the layout holds no ``docs/agents/cards``; the committed cards of the checked-out tree are read;
  * architecture diagram: the layout holds no generator; the real ``scripts/generate_agent_diagram.py`` CLI is run
    against the DEPLOYED registry copy.
The knowledge graph is the deployed ``knowledge_query.py`` CLI over the deployed install's own ``config/paths.json``.
"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400e_support as E  # noqa: E402
import _ar400_parent_support as P  # noqa: E402


def _views(layout, tmp_path, decl, hidden) -> dict[str, E.View]:
    installed = P.deployed_skill_ids(layout)
    views = {f"prompt[{where}]": P.prompt_view(prompts, decl, hidden, installed)
             for where, prompts in P.prompts_by_root(layout).items()}
    views.update({"registry": P.registry_view(layout), "diagram": P.diagram_view(layout, tmp_path / "diagram"),
                  "graph": P.graph_view(layout), "card": P.committed_card_view(decl)})
    return views


def _expected(view_name: str, decl: dict[str, set[str]], hidden: dict[str, set[str]]) -> dict[str, set[str]]:
    """The prompt states a project-supplied ability the package does not ship as 'not installed' (never a row), and
    the graph holds edges only to ability nodes that exist (AR-400d); every other view lists the whole declaration."""
    if view_name.startswith("prompt") or view_name == "graph":
        return {a: ids - hidden.get(a, set()) for a, ids in decl.items()}
    return decl


@pytest.mark.shared_layout_reader
def test_ar_400e_deployed_views_list_exactly_each_specialists_declared_abilities(shared_reference_layout, tmp_path):
    # covers: AR-400e
    # angle: deployed
    # must_catch: a view still reads the retired skills_used field, so the specialists that were only in skills_invoked show no abilities there
    # must_catch: a view reads the union of both fields and so lists an ability the declaration dropped
    # must_catch: a specialist with no grant is missing from some views instead of appearing with none
    """For every specialist defined under templates/agents: the abilities in its compiled prompt (both platform
    roots), its published card, the diagram, the knowledge graph (through its CLI) and the deployed registry are each
    exactly the set its own definition declares; the deployed registry carries no ``skills_used`` field; and every
    view's population of specialists equals the number of definitions. Controls: the comparison reports an emptied
    view, a union-reading view and a view missing an empty-grant specialist; the population holds granting and
    empty-grant specialists."""
    decl, hidden = P.definitions(), P.hidden_grants()
    assert len(decl) > 0 and any(not g for g in decl.values()) and sum(1 for g in decl.values() if g) > 20
    views = _views(shared_reference_layout, tmp_path, decl, hidden)
    assert len(views) == 6, sorted(views)
    problems = [m for name, view in views.items() for m in E.mismatches(name, view, _expected(name, decl, hidden))]
    assert problems == [], f"{len(problems)} disagreement(s):\n" + "\n".join(problems[:20])
    assert {v.examined for v in views.values()} == {len(decl)}, {n: v.examined for n, v in views.items()}
    retired = [r["id"] for r in P.deployed_registry(shared_reference_layout)["agents"] if "skills_used" in r]
    assert retired == [], f"the deployed registry still carries skills_used for {retired[:5]}"
    assert P.wrong_views_caught(decl) == [True, True, True]
