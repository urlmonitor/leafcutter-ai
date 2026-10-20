"""AR-400b-4 -- the registry validator and the build give the SAME verdict on a specialist's ability
references: one computation, two doors (TDD red phase).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/AR-400b-4.yaml.
Doors under test, all REAL: the validator CLI (fresh subprocess), ``scripts/build.py --target-dir``
(fresh subprocess over a full package copy, which refuses BEFORE any deploy phase once the gate is
wired -- cheap when green, slow only while red), the deployed ``check-agent-registry`` commit hook
run from a built layout, and ``build._validate_all`` (the decision ``build.py main()`` aborts on).

The fixture holds one instance of each fault kind in four specialists. Real-tree assertions allow no
exceptions: sql-coder's postgres / sql-test are cleared by AR-400d-1-i (``provided_by: project``).
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400a_1_support as H  # noqa: E402
import _ar400_3a_fixtures as F  # noqa: E402

FOUR = {  # specialist -> (body line, fault kind)
    "probe-nx": ("Load `.claude/skills/ghost-ability/SKILL.md` and follow it", F.NONEXIST),
    "probe-ug": ("Load the `knowledge-query` skill first.", F.UNGRANTED),
    "probe-case": ("Step 1 -- Load the Write-C4-Diagram Skill", F.CASE),
    "probe-ag": ("Use the `sql-query` skill if available to scaffold the object", F.AGENT),
}


def plant_four(root: Path) -> None:
    """One instance of each fault kind, in four different specialists."""
    for name, (line, _kind) in FOUR.items():
        F.plant(root, name, [line], grants=("signoff",) if name == "probe-ug" else ())


def unique_in_order(lines: list[str]) -> list[str]:
    """Finding lines in print order, de-duplicated (a door printing one twice is not 'two findings')."""
    return list(dict.fromkeys(lines))


class TestOneComputationTwoDoors(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def _assert_four(self, lines: list[str], root: Path, where: str) -> None:
        self.assertEqual(len(lines), 4, f"{where}: expected exactly the four fixture findings, got {lines}")
        for name, (line, kind) in FOUR.items():
            mine = [ln for ln in lines if name in ln]
            self.assertEqual(len(mine), 1, f"{where}: {name} -> {mine}")
            self.assertIn(kind, mine[0].lower(), f"{where}: wrong kind for {name}: {mine[0]}")
            self.assertTrue(H.names_line(mine[0], F.agent_rel(name), F.line_of(root / F.agent_rel(name), line)), mine[0])

    @pytest.mark.shared_layout_mutator
    def test_validator_and_build_report_identical_findings_and_counts(self):
        # covers: AR-400b-4
        # angle: seam
        # must_catch: the build calls a second implementation that drifts from the validator
        # must_catch: one door prints findings as warnings and exits 0
        """Fixture package with one instance of each fault kind in four specialists. The validator
        CLI and ``scripts/build.py --target-dir <tmp>`` both fail; each prints exactly the four
        finding lines (same specialist, ability, file, line, kind); the four lines are IDENTICAL
        between the two outputs, in the same order; and the examined counts are identical."""
        root = H.make_build_package(self._tmp.name + "/full")
        plant_four(root)
        v_rc, v_out = H.cli(root)
        target = Path(self._tmp.name) / "target"
        target.mkdir()
        cp = subprocess.run([sys.executable, str(root / "scripts" / "build.py"), "--target-dir", str(target)],
                            capture_output=True, text=True, timeout=600, check=False)
        b_out = cp.stdout + "\n" + cp.stderr
        v_lines, b_lines = unique_in_order(F.findings(v_out)), unique_in_order(F.findings(b_out))
        self._assert_four(v_lines, root, "validator door")
        self._assert_four(b_lines, root, "build door")
        self.assertEqual(v_lines, b_lines, "the two doors disagree on the findings (or their order)")
        self.assertNotEqual(v_rc, 0, v_out[-800:])
        self.assertNotEqual(cp.returncode, 0, "the build must refuse (non-zero), not warn")
        for word in ("definition", "guide"):
            self.assertTrue(H.reported(v_out, word), f"validator printed no {word} count")
            self.assertEqual(set(H.reported(v_out, word)), set(H.reported(b_out, word)), f"{word} counts differ")
        self.assertEqual([p.name for p in target.rglob("*.md")], [], "build deployed agents despite the findings")


@pytest.mark.shared_layout_reader
def test_commit_hook_door_fails_on_the_same_fixture(shared_reference_layout, tmp_path):
    # covers: AR-400b-4
    # angle: deployed
    """The DEPLOYED check-agent-registry hook (a build output, copied from the shared reference
    layout), run with cwd at a git repo whose staged registry belongs to the same four-fault fixture
    package, exits non-zero printing the same four findings the validator CLI prints. Proves every
    module the validator now imports is reachable from the deployed hook, not only from the source
    tree."""
    root = H.make_build_package(tmp_path / "full")
    plant_four(root)
    hook = F.deploy_hook_from_layout(shared_reference_layout, root)
    F.stage_registry(root)
    cp = subprocess.run([sys.executable, str(hook)], cwd=str(root), capture_output=True, text=True,
                        timeout=300, check=False)
    out = cp.stdout + "\n" + cp.stderr
    assert "ModuleNotFoundError" not in out and "could not import" not in out, out[-1200:]
    cli_lines = unique_in_order(F.findings(H.cli(root)[1]))
    assert len(cli_lines) == 4, f"validator CLI must report the four fixture findings, got {cli_lines}"
    assert unique_in_order(F.findings(out)) == cli_lines, f"deployed hook and validator disagree: {out[-1500:]}"
    assert cp.returncode == 1, out[-1200:]


def test_real_tree_passes_through_both_doors():
    # covers: AR-400b-4
    # angle: real_artifact
    """On the checked-out package the validator CLI and the build's validation decision
    (``build._validate_all``) each report zero findings and exit 0, and state the same examined counts, equal to the counts derived
    independently from the tree. Control row: the same two doors over a copy holding ONE ungranted
    instruction fail with that finding, so a pass here cannot be a gate that never looks."""
    v_rc, v_out = F.real_cli()
    b_rc, b_out = H.build_door(F.REPO_ROOT)
    for where, rc, out in (("validator", v_rc, v_out), ("build", b_rc, b_out)):
        assert F.findings(out) == [], f"{where} door: {F.findings(out)}"
        assert rc == 0, f"{where} door: exit {rc} on a tree that must pass"
    defs, guides = H.expected_counts(F.REPO_ROOT)
    for word, want in (("definition", defs), ("guide", guides)):
        assert want in H.reported(v_out, word) and want in H.reported(b_out, word), (word, want)
    with tempfile.TemporaryDirectory() as tmp:
        root = H.make_slice(tmp)
        F.plant(root, "probe-ug", ["Load the `knowledge-query` skill first."], grants=("signoff",))
        c_rc, c_out = H.cli(root)
        d_rc, d_out = H.build_door(root)
    for where, rc, out in (("validator", c_rc, c_out), ("build", d_rc, d_out)):
        assert len(F.of_kind(out, F.UNGRANTED, "knowledge-query", "probe-ug")) == 1, (
            f"{where} door missed the control finding: {out[-800:]}")
        assert rc != 0, f"{where} door passed a tree that holds a finding"


if __name__ == "__main__":
    unittest.main()
