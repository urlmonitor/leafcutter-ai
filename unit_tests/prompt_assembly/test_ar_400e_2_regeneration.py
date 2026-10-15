"""AR-400e-2 -- the central registry carries ONE derived list of a specialist's abilities
(``skills_invoked``), regenerated from the declaration by the commit-time hook (TDD red phase).

The hook is run through its REAL entry point (``transform_agent_registry.py --package-root``)
over a copy of the package (real registry + real templates), with three specialists planted
into the copy: ``probe-used-only`` (registry holds its population only in ``skills_used``),
``probe-provider`` (declares a ``provided_by`` marking) and ``probe-empty-both`` (empty
declaration, ``skills_used: []``). Expected records are computed independently from the
templates' own frontmatter, never by the production normaliser.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400e_support as H  # noqa: E402
from template_compiler import parse_frontmatter  # noqa: E402

logging.disable(logging.CRITICAL)
OWNED = {"skills_invoked", "skills_used", "spawn_allowlist"}


def _planted_root(base: Path, name: str = "pkg") -> Path:
    root = H.lean_root(base, name=name)
    H.plant_specialist(root, "probe-used-only",
                       [{"skill_id": "signoff", "mode": "always"},
                        {"skill_id": "knowledge-query", "mode": "conditional", "condition": "when probing"}],
                       used_only=["signoff"])
    H.plant_specialist(root, "probe-provider", [{"skill_id": "signoff", "mode": "always", "provided_by": "project"}],
                       used_only=[])
    H.plant_specialist(root, "probe-empty-both", [], used_only=[])
    return root


def _expected(root: Path, before: dict) -> dict[str, list[dict]]:
    """Per templated agent: declared grants (with condition / provided_by) + preserved descriptive entries."""
    out: dict[str, list[dict]] = {}
    for rec in before["agents"]:
        path = root / rec["template_path"]
        fm, _ = parse_frontmatter(path.read_text(encoding="utf-8"))
        grants = []
        for item in fm.get("skills") or []:
            raw = {"skill_id": item} if isinstance(item, str) else item
            entry = {"skill_id": raw["skill_id"], "mode": raw.get("mode") or "always"}
            for key in ("condition", "provided_by"):
                if raw.get(key):
                    entry[key] = raw[key]
            grants.append(entry)
        descriptive = [e for f in ("skills_used", "skills_invoked") for e in rec.get(f) or []
                       if isinstance(e, dict) and e.get("descriptive_only")]
        out[rec["id"]] = grants + descriptive
    return out


class TestHookRegeneration(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)

    def test_regeneration_writes_skills_invoked_for_every_declared_agent_and_no_skills_used(self):
        # covers: AR-400e-2
        # angle: criterion
        """Hook over the planted copy: every templated agent's skills_invoked equals its declaration
        (ids, modes, conditions, provided_by) followed by its preserved descriptive_only entries,
        and NO agent entry carries skills_used. Wrong versions: an agent that held only skills_used
        keeps that population (probe-used-only and the real older-field specialists); descriptive_only
        entries dropped (python-coder's run-tests, documentation-expert's direct-write must survive);
        provided_by dropped (probe-provider)."""
        root = _planted_root(self.base)
        before = H.registry(root)
        want = _expected(root, before)
        self.assertGreater(len(want), 62)
        self.assertEqual(H.run_hook(root).returncode, 0)
        after = H.registry(root)
        problems = []
        for rec in after["agents"]:
            if rec["id"] in want and rec.get("skills_invoked") != want[rec["id"]]:
                problems.append(f"{rec['id']}: skills_invoked {rec.get('skills_invoked')} != {want[rec['id']]}")
            if "skills_used" in rec:
                problems.append(f"{rec['id']}: still carries skills_used {rec['skills_used']}")
        self.assertEqual([a["id"] for a in after["agents"]], [a["id"] for a in before["agents"]])
        descriptive = {a: [e["skill_id"] for e in es if e.get("descriptive_only")] for a, es in want.items()}
        self.assertTrue(any(descriptive.values()), "control: descriptive_only entries must exist to be preserved")
        self.assertEqual(problems, [], f"{len(problems)} problem(s):\n" + "\n".join(problems[:15]))

    def test_regeneration_changes_no_other_byte_and_is_idempotent(self):
        # covers: AR-400e-2
        # angle: boundary
        """Only skills_invoked / skills_used (removed) / spawn_allowlist may differ between the
        input and the output; every other key and top-level field is identical; the output is
        written the one way the hook writes (4-space, UTF-8, final newline); a second run is
        byte-identical. Boundary population: empty (real + probe-empty-both), one and many grants
        must each be present and each end with exactly their declared grants and NO skills_used."""
        root = _planted_root(self.base)
        before = H.registry(root)
        want = _expected(root, before)
        self.assertEqual(H.run_hook(root).returncode, 0)
        first = (root / "config" / "agent_registry.json").read_bytes()
        after = json.loads(first)
        self.assertEqual(first.decode("utf-8"), H.dump(after))
        self.assertEqual(H.run_hook(root).returncode, 0)
        self.assertEqual(first, (root / "config" / "agent_registry.json").read_bytes(), "second run must be byte-identical")
        self.assertEqual({k: v for k, v in after.items() if k != "agents"}, {k: v for k, v in before.items() if k != "agents"})
        sizes = {len([e for e in es if not e.get("descriptive_only")]) for es in want.values()}
        self.assertTrue({0, 1} <= sizes and max(sizes) > 1, f"need empty/one/many populations, got {sorted(sizes)}")
        problems = _unowned_changes(before, after) + _grant_mismatches(after, want)
        self.assertEqual(problems, [], f"{len(problems)} problem(s):\n" + "\n".join(problems[:15]))


def _unowned_changes(before: dict, after: dict) -> list[str]:
    """Records whose keys outside the hook-owned fields changed, or that gained a key."""
    problems = []
    for old, new in zip(before["agents"], after["agents"]):
        for key in (set(old) | set(new)) - OWNED:
            if old.get(key) != new.get(key) or (key in old) != (key in new):
                problems.append(f"{old['id']}: unowned key {key} changed")
        if set(new) - set(old) - {"skills_invoked"}:
            problems.append(f"{old['id']}: gained keys {set(new) - set(old)}")
    return problems


def _grant_mismatches(after: dict, want: dict) -> list[str]:
    """Records that carry skills_used or whose grants are not exactly the declared ones."""
    problems = []
    for rec in after["agents"]:
        grants = [e for e in rec.get("skills_invoked", []) if not e.get("descriptive_only")]
        if "skills_used" in rec or [g["skill_id"] for g in grants] != [
                e["skill_id"] for e in want[rec["id"]] if not e.get("descriptive_only")]:
            problems.append(f"{rec['id']}: not exactly its declared grants without skills_used")
    return problems


def test_committed_registry_equals_hook_output(tmp_path):
    # covers: AR-400e-2
    # angle: real_artifact
    """Running the hook over a copy of the checked-out package (real registry + real templates)
    leaves config/agent_registry.json byte-identical: the committed file IS the hook's output
    and carries no skills_used. Red until the registry is regenerated and committed."""
    root = H.lean_root(tmp_path)
    committed = (root / "config" / "agent_registry.json").read_bytes()
    repo_registry = H.REPO_ROOT / "config" / "agent_registry.json"
    assert repo_registry.read_bytes() == committed, "the copy must start from the committed registry"
    assert H.run_hook(root).returncode == 0
    regenerated = (root / "config" / "agent_registry.json").read_bytes()
    carrying = [a["id"] for a in json.loads(regenerated)["agents"] if "skills_used" in a]
    assert not carrying, f"hook output still carries skills_used on {carrying[:5]}"
    assert regenerated == committed, f"committed {repo_registry} differs from the hook's output ({len(committed)} vs {len(regenerated)} bytes)"


if __name__ == "__main__":
    unittest.main()
