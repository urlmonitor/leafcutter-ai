"""AR-400e-3 -- proposing a specialist's self-description changes its own declaration, never the derived
list (TDD red phase).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/AR-400e-3.yaml.
The proposer is run through its REAL entry point (``scripts/propose_agent_self_description.py`` in a
subprocess) from a COPY of ``scripts/`` inside a copied package, so what it writes lands in the copy.
Contract assumed (see ``_ar400_3c_fixtures``): abilities are proposed under ``proposed_frontmatter.skills``;
no key named ``skills_invoked`` appears anywhere in a proposal; ``config/`` and ``templates/`` are untouched.

Today the proposer writes ``proposed_registry.skills_invoked`` from three private regexes and adds
``signoff`` whenever the frontmatter says ``signoff: true``.
"""

from __future__ import annotations

import functools
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar400_3c_fixtures as X  # noqa: E402

PROBE = "probe-loader"
LOAD_DOC_ENFORCER = ["Before you finish, load the `doc-enforcer` skill and follow it."]
GUARDED = ("config", "templates")


def _proposal(root, agent: str = PROBE) -> dict:
    found = X.proposals(root, agent)
    assert len(found) == 1, f"expected one proposal for {agent}, found {len(found)}"
    return found[0]


class TestProposerRetargeted(unittest.TestCase):
    def _run(self, *, signoff: bool):
        root = X.proposer_package()
        X.plant_probe(root, PROBE, LOAD_DOC_ENFORCER, signoff=signoff)
        before = X.digest(root, *GUARDED)
        cp = X.run_proposer(root, "--agent", PROBE)
        self.assertEqual(cp.returncode, 0, cp.stdout + cp.stderr)
        self.assertEqual(X.digest(root, *GUARDED), before, "the proposer wrote a file it was not asked to")
        return root

    def test_proposer_proposes_declaration_change_not_registry_edit(self):
        # covers: AR-400e-3
        # angle: criterion
        """The fixture's instructions say 'load the `doc-enforcer` skill' and its `skills:` grants
        nothing. The proposal puts exactly doc-enforcer under the specialist's own `skills:`
        declaration, carries no `skills_invoked` anywhere, and config/agent_registry.json is
        byte-identical afterwards."""
        root = self._run(signoff=False)
        doc = _proposal(root)
        self.assertEqual(X.proposed_frontmatter_ids(doc), {"doc-enforcer"}, doc.get("proposed_frontmatter"))
        self.assertFalse(X.has_key(doc, "skills_invoked"), "the proposal still targets the derived registry field")

    def test_proposer_adds_no_default_signoff(self):
        # covers: AR-400e-3
        # angle: discrimination
        # must_catch: the default-signoff branch is left in place (it only fires when signoff: true, so a fixture without it would pass vacuously)
        """Same fixture, now with `signoff: true` in its frontmatter and no instruction to load signoff.
        The proposal still proposes doc-enforcer (so it is not simply empty) and no ability id anywhere
        in it -- the declaration change or any registry field -- is signoff."""
        root = self._run(signoff=True)
        doc = _proposal(root)
        self.assertEqual(X.proposed_frontmatter_ids(doc), {"doc-enforcer"}, doc.get("proposed_frontmatter"))
        self.assertNotIn("signoff", X.ability_ids_anywhere(doc))

    def test_applied_proposal_regenerates_to_matching_skills_invoked(self):
        # covers: AR-400e-3
        # angle: seam
        """Take the real proposer's output for the fixture, apply it to the template's `skills:`
        declaration, and run the real commit-time transform: the registry entry's `skills_invoked`
        equals the new declaration (ids and modes), and is not what it was before."""
        root = self._run(signoff=False)
        skills = (_proposal(root).get("proposed_frontmatter") or {}).get("skills")
        self.assertTrue(skills, "the proposal contains no `skills:` declaration change to apply")
        entries = [{"skill_id": s, "mode": "always"} if isinstance(s, str) else dict(s, mode=s.get("mode") or "always")
                   for s in skills]
        before = X.registry_pairs(root, PROBE)
        X.set_frontmatter(root, PROBE, skills=entries)
        self.assertEqual(X.E.run_hook(root).returncode, 0)
        after = X.registry_pairs(root, PROBE)
        self.assertEqual(after, X.declared_pairs(root, PROBE))
        self.assertNotEqual(after, before)
        self.assertEqual([i for i, _ in after], ["doc-enforcer"])


@functools.lru_cache(maxsize=1)
def _real_tree_run():
    """The proposer over EVERY real template, written into a copy (one run per process)."""
    root = X.proposer_package()
    cp = X.run_proposer(root)
    assert cp.returncode == 0, cp.stdout + cp.stderr
    return root


def _recognised_instruction_ids(root, text: str, self_id: str) -> set[str]:
    """Canonical ability ids the reference gate's shared recognition rule treats as instructions
    (not citations, not agents, not unknown), read through the rule's own entry point."""
    import skill_ref_recognition as rule

    skills = root / "templates" / "skills"
    known = {d.name for d in skills.iterdir() if d.is_dir()}
    agents = {a["id"] for a in X.H._registry(root)["agents"]}
    refs = rule.recognise(text, known, agents, self_id)
    return {r["canonical_id"] for r in refs if r["canonical_id"] and not r["citation"] and not r["names_agent"]}


def test_proposer_and_gate_recognise_the_same_instructions():
    # covers: AR-400e-3
    # angle: real_artifact
    """For every real agent template, the ability ids the proposer lists under ``proposed_frontmatter.skills``
    equal, as a set, the canonical ids the reference check recognises as instructions in that template
    (the whole recognised set, granted or not: the real tree is clean, so an additions-only reading
    would be empty on every template and prove nothing). A proposer with its own regexes proposes
    grants the gate rejects or misses ones it requires."""
    root = _real_tree_run()
    by_agent = {d.get("agent_id"): d for d in X.proposals(root)}
    mismatched, nonempty = [], 0
    for path in sorted((root / "templates" / "agents").glob("*.md")):
        if path.name.startswith("_"):
            continue
        fm, _ = X.parse_frontmatter(path.read_text(encoding="utf-8"))
        agent = fm.get("name") or path.stem
        recognised = _recognised_instruction_ids(root, path.read_text(encoding="utf-8"), agent)
        proposed = X.proposed_frontmatter_ids(by_agent[agent]) if agent in by_agent else None
        nonempty += bool(recognised)
        if proposed != recognised:
            mismatched.append((agent, sorted(proposed or []), sorted(recognised)))
    assert nonempty >= 10, f"control: only {nonempty} templates have recognised instructions to compare"
    assert mismatched == [], f"{len(mismatched)} template(s) where proposer and gate disagree:\n" + "\n".join(map(str, mismatched[:8]))


if __name__ == "__main__":
    unittest.main()
