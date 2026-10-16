"""AR-400d-3 -- every surface that reads a grant understands the ``provided_by: project`` marking
the same way: the declaration-shape check, the commit-time registry regeneration, the reference
check, the done verdict and the prompt compile (TDD red phase).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/AR-400d-3.yaml.
Each surface is RUN, never inspected: the shape check and verdict through their real scripts/ entry
points (``agent_ability_gate.ability_errors`` is what the build's refusal calls;
``agent_ability_verdict.verify_abilities`` is the done verdict), the hook as the real script, the
reference check as the validator CLI, the compile as a real ``build.py`` over a scratch consumer.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

import _ar_400a_1_support as H  # noqa: E402
import _ar400_3a_fixtures as F  # noqa: E402
import _ar400_3b_fixtures as G  # noqa: E402
from agent_ability_gate import ability_errors  # noqa: E402
from agent_ability_verdict import normalize_entries, verify_abilities  # noqa: E402

HOOK = F.REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "transform_agent_registry.py"
SYNC = F.REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "_agent_ability_sync.py"
BLOCKING = ("unresolved", "divergent", "declaration-only", "record-only")
PROBE = "probe-coder"


def _sync_module():
    spec = importlib.util.spec_from_file_location("_agent_ability_sync_d3", SYNC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    return yaml.safe_load(text[3:text.find("\n---", 3)])


def run_hook(root: Path) -> None:
    cp = subprocess.run([sys.executable, str(HOOK), "--package-root", str(root)],
                        capture_output=True, text=True, timeout=300, check=False)
    assert cp.returncode == 0, f"transform hook exited {cp.returncode}: {cp.stderr[-600:]}"


def _registry(root: Path) -> dict:
    return json.loads((root / "config" / "agent_registry.json").read_text(encoding="utf-8"))


def run_surfaces(sc: G.Scenario) -> dict:
    """Run all five classifications over the scenario's probe-coder; return what each decided."""
    tpl = sc.root / F.agent_rel(PROBE)
    run_hook(sc.root)  # (2) commit-time regeneration FIRST, so the later surfaces read the derived copy
    reg = _registry(sc.root)
    entry = next(a for a in reg["agents"] if a["id"] == PROBE)
    grant = next(e for e in entry["skills_invoked"] if e["skill_id"] == "postgres")
    declared = _frontmatter(tpl)["skills"]
    shape = [m for m in ability_errors(sc.root) if "malformed" in m]                          # (1)
    _, cli_out = H.cli(sc.root)                                                              # (3)
    verdict = verify_abilities({PROBE: declared}, reg["agents"], packaged_skills_root=sc.root / "templates" / "skills",
                               project_root=sc.project)                                        # (4)
    blocking = [f for f in verdict["findings"] if f["agent"] == PROBE and f["kind"] in BLOCKING]
    rc, out = G.build(sc)                                                                    # (5)
    return {"shape": shape, "provided_by": grant.get("provided_by"), "cli": cli_out, "blocking": blocking, "rc": rc, "out": out}


def _drop_marking(sc: G.Scenario) -> None:
    """Change ONLY the marking: remove ``provided_by`` from probe-coder's own grant."""
    path = sc.root / F.agent_rel(PROBE)
    text = path.read_text(encoding="utf-8")
    end = text.find("\n---", 3)
    head = yaml.safe_load(text[3:end])
    for entry in head["skills"]:
        entry.pop("provided_by", None)
    path.write_text("---\n" + yaml.safe_dump(head, sort_keys=False) + text[end + 1:], encoding="utf-8")


class TestFiveSurfaces(unittest.TestCase):
    @pytest.mark.shared_layout_mutator
    def test_marking_flips_all_five_surfaces_together(self):
        # covers: AR-400d-3
        # angle: seam
        # must_catch: one surface ignores provided_by and keeps today's behaviour
        # must_catch: the verdict's comparison ignores provided_by so a dropped marking reads as agreement
        """probe-coder grants postgres ``provided_by: project`` in a project lacking it. Marked: shape
        ok, the regenerated entry keeps the marking, the validator reports no 'does not exist' / 'not
        granted', the verdict counts it declared (no blocking finding), and the compiled prompt says
        the ability is project-supplied and not installed. Remove ONLY the marking, rerun the same
        five: shape ok, entry unmarked, 'does not exist' from the validator, an 'unresolved' verdict
        finding, and the build refuses with no project-supplied statement."""
        sc = G.fresh("marked_absent")
        on = run_surfaces(sc)
        self.assertEqual(on["shape"], [], on["shape"])
        self.assertEqual(on["provided_by"], "project", "the regeneration dropped the marking")
        self.assertEqual(G.finding_lines(on["cli"], PROBE, "postgres"), [], on["cli"][-800:])
        self.assertEqual(on["blocking"], [], f"verdict counts the marked grant as missing/divergent: {on['blocking']}")
        self.assertEqual(on["rc"], 0, on["out"][-1200:])
        for root, text in G.compiled(sc.project, PROBE).items():
            said = [ln for ln in text.splitlines() if F.names(ln, "postgres") and "not installed" in ln.lower()
                    and "project" in ln.lower()]
            self.assertTrue(said, f"{root}: the prompt does not say the project-supplied postgres is not installed")
        _drop_marking(sc)
        off = run_surfaces(sc)
        self.assertEqual(off["shape"], [])
        self.assertIsNone(off["provided_by"], "an unmarked declaration must regenerate an unmarked entry")
        self.assertEqual(len(F.of_kind(off["cli"], F.NONEXIST, "postgres", PROBE)), 1, off["cli"][-800:])
        self.assertEqual([f["kind"] for f in off["blocking"]], ["unresolved"], off["blocking"])
        self.assertNotEqual(off["rc"], 0, "the unmarked build must refuse")
        self.assertEqual(G.info_lines(off["out"], PROBE, "postgres", r"not found|not installed"), [])

    def test_unknown_provided_by_value_is_refused_by_both_shape_copies(self):
        # covers: AR-400d-3
        # angle: failure
        """``provided_by: vendor`` is refused by the build's shape check (a finding naming the
        specialist, the grant and the value) and by the transform hook's copy of the check
        (MalformedDeclarationError naming the value)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = H.make_slice(tmp)
            grant = {"skill_id": "postgres", "mode": "always", "provided_by": "vendor"}
            F.plant(root, PROBE, [G.POSTGRES_BODY], grants=(grant,))
            malformed = [m for m in ability_errors(root) if "malformed" in m]
            self.assertEqual(len(malformed), 1, malformed)
            for needle in (PROBE, "postgres", "vendor"):
                self.assertIn(needle, malformed[0])
        sync = _sync_module()
        with self.assertRaises(sync.MalformedDeclarationError) as ctx:
            sync.normalize_declared(yaml.safe_load(yaml.safe_dump([grant])))
        self.assertIn("vendor", str(ctx.exception))

    def test_second_regeneration_is_byte_identical(self):
        # covers: AR-400d-3
        # angle: boundary
        """Running the transform hook twice over the marked fixture leaves config/agent_registry.json
        byte-identical, and the first run really wrote the marking (so identity is not vacuous)."""
        with tempfile.TemporaryDirectory() as tmp:
            root = H.make_slice(tmp)
            F.plant(root, PROBE, [G.POSTGRES_BODY], grants=(G.marked("postgres"),), registry_grants=())
            run_hook(root)
            first = (root / "config" / "agent_registry.json").read_bytes()
            entry = next(a for a in json.loads(first)["agents"] if a["id"] == PROBE)
            self.assertEqual([e.get("provided_by") for e in entry["skills_invoked"]], ["project"])
            run_hook(root)
            self.assertEqual((root / "config" / "agent_registry.json").read_bytes(), first)


def test_hook_and_scripts_parsers_agree_on_every_real_template():
    # covers: AR-400d-3
    # angle: real_artifact
    """For every real templates/agents/*.md ``skills:`` declaration, plus marked fixtures produced by
    the real serializer, the hook's ``normalize_declared`` and ``agent_ability_verdict.
    normalize_entries`` return identical lists (the hook is deployed alone and cannot share the parser)."""
    sync = _sync_module()
    cases = []
    for path in sorted((F.REPO_ROOT / "templates" / "agents").glob("*.md")):
        if path.name.startswith("_"):
            continue
        raw = _frontmatter(path).get("skills")
        if raw:
            cases.append((path.name, raw))
    assert len(cases) >= 40, f"too few real declarations to compare: {len(cases)}"
    fixtures = [G.marked("postgres"), "signoff", G.marked("sql-test", "conditional") | {"condition": "run the SQL tests"}]
    cases.append(("marked fixtures", yaml.safe_load(yaml.safe_dump(fixtures))))
    differ = [(name, sync.normalize_declared(raw), normalize_entries(raw)) for name, raw in cases
              if sync.normalize_declared(raw) != normalize_entries(raw)]
    assert differ == [], f"parsers disagree: {differ[:2]}"
    last = normalize_entries(cases[-1][1])
    assert [e.get("provided_by") for e in last] == ["project", None, "project"], "the shared parser dropped or invented a marking"


if __name__ == "__main__":
    unittest.main()
