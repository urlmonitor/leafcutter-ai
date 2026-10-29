"""
MODULE: unit_tests/portability/test_bp_1500g_2_ii.py
GOAL: AC BP-1500g-2-ii -- a collision kept for the adopter is carried only to
    a surface that really holds the same capability.
AC: docs/acceptance-criteria/build_pipeline/BP-1500-honest-builds/BP-1500g-2-ii.yaml

DEFECT UNDER TEST (reproduced 2026-10-25 on origin/main 411b87761): a
plain ``build.py`` over a workspace the maker built with
``LEAFCUTTER_SHIM_STRATEGY=copy`` finds ``.claude/workflows`` as a real,
non-empty directory. It merges into it by name, and keeps all nine
``*.js`` workflow scripts as adopter collisions. ``_propagate_winner_to_
siblings`` then copies each one into ``<output_root>/gemini/workflows/``.
That directory is antigravity's copy of the commands-family workflow
markdown, not a mirror of the JS workflows. The next copy build copies
``.leafcutter/gemini`` into ``.gemini``. check-output-drift then reports 9
GAPs that no rebuild clears, which blocks every commit.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

_WORKTREE_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = _WORKTREE_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build_capability_merge as bcm  # noqa: E402

_BUILD_SCRIPT = _SCRIPTS_DIR / "build.py"
_GAP_RE = re.compile(r"^UNCOMPARABLE: GAP (?P<path>\S+)", re.MULTILINE)


def _minted(prefix: str) -> str:
    """A name no package template carries, minted at run time."""
    return f"{prefix}-{uuid.uuid4().hex[:10]}"


def test_bp_1500g_2_ii_a_contested_workflow_script_is_not_carried_into_the_gemini_workflows_family(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-2-ii
    # angle: criterion
    """A contested ``.claude/workflows/<name>.js`` is kept for the adopter,
    and is NOT copied into ``gemini/workflows``, a different family whose
    package output never held that name."""
    output_root = tmp_path / ".leafcutter"
    name = _minted("wf") + ".js"
    (output_root / "workflows").mkdir(parents=True)
    (output_root / "workflows" / name).write_text("// package version\n", encoding="utf-8")
    gemini_workflows = output_root / "gemini" / "workflows"
    gemini_workflows.mkdir(parents=True)
    (gemini_workflows / "unrelated-command.md").write_text("# a command\n", encoding="utf-8")

    canonical = tmp_path / ".claude" / "workflows"
    canonical.mkdir(parents=True)
    (canonical / name).write_text("// copy-strategy leftover\n", encoding="utf-8")

    result = bcm.merge_capability_items(
        canonical, output_root / "workflows", ".claude/workflows", "workflows",
        dry_run=False, output_root=output_root,
    )

    assert result["method"] == "merged (0 item(s), 1 collision(s))", result
    assert not (gemini_workflows / name).exists(), (
        f"{name} was carried into gemini/workflows, where the package never "
        "wrote it; the copy shim then lands it in .gemini/workflows as a "
        "check-output-drift GAP no rebuild clears."
    )
    assert sorted(p.name for p in gemini_workflows.iterdir()) == ["unrelated-command.md"]


def test_bp_1500g_2_ii_a_contested_skill_is_still_carried_to_its_real_gemini_mirror(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-2-ii
    # angle: failure
    """Over-correction control. BP-1500g-2-i's adopter-wins carry must still
    reach the antigravity skills surface, which really mirrors the item."""
    output_root = tmp_path / ".leafcutter"
    name = _minted("skill")
    for family in ("skills", "gemini/skills"):
        item = output_root / family / name
        item.mkdir(parents=True)
        (item / "SKILL.md").write_text("package version\n", encoding="utf-8")

    canonical = tmp_path / ".claude" / "skills"
    (canonical / name).mkdir(parents=True)
    adopter_bytes = f"adopter's own {name}\n".encode()
    (canonical / name / "SKILL.md").write_bytes(adopter_bytes)

    bcm.merge_capability_items(
        canonical, output_root / "skills", ".claude/skills", "skills",
        dry_run=False, output_root=output_root,
    )

    assert (canonical / name / "SKILL.md").read_bytes() == adopter_bytes
    assert (output_root / "gemini" / "skills" / name / "SKILL.md").read_bytes() == adopter_bytes, (
        "The adopter's winning skill was not carried to gemini/skills, so the "
        "antigravity surface still runs the package version while the run "
        "declares 'resolves to adopter'."
    )


def _build(target: Path, strategy: str | None) -> subprocess.CompletedProcess[str]:
    """One real build.py run; *strategy* None is the plain everyday command."""
    env = {k: v for k, v in os.environ.items() if k != "LEAFCUTTER_SHIM_STRATEGY"}
    if strategy is not None:
        env["LEAFCUTTER_SHIM_STRATEGY"] = strategy
    return subprocess.run(
        [sys.executable, str(_BUILD_SCRIPT), "--target-dir", str(target), "--no-log-root"],
        cwd=str(target), env=env, capture_output=True, text=True, timeout=600, check=False,
    )


def _drift_gaps(target: Path) -> tuple[list[str], str]:
    """Run the DEPLOYED check-output-drift hook the way pre-commit does."""
    cg = target / ".leafcutter" / "scripts" / "commit_guardian"
    proc = subprocess.run(
        [sys.executable, str(cg / "run_hook.py"), str(cg / "check_output_drift.py")],
        cwd=str(target), capture_output=True, text=True, timeout=600, check=False,
    )
    out = proc.stdout + proc.stderr
    assert "check-output-drift: RESULT" in out, f"hook did not run to a RESULT:\n{out}"
    return _GAP_RE.findall(out), out


@pytest.mark.shared_layout_mutator
def test_bp_1500g_2_ii_a_maker_layout_rebuilt_after_a_plain_build_has_no_gemini_workflows_gap_but_a_foreign_file_is_still_one(
    tmp_path: Path,
) -> None:
    # covers: BP-1500g-2-ii
    # angle: reachability
    """The reported sequence: the maker's copy build, a plain build, and the
    maker's copy build again. The deployed hook then reports no GAP under
    .gemini/workflows, and a hand-planted foreign file there is still one."""
    target = tmp_path / "adopter_project"
    target.mkdir()
    subprocess.run(["git", "init", "-q", str(target)], check=True, timeout=60)

    first = _build(target, "copy")
    assert first.returncode == 0, f"maker-way build failed:\n{first.stdout}\n{first.stderr}"
    plain = _build(target, None)
    # Premise: the plain build took the real-container merge path for the
    # workflow scripts. Without it this test would pass vacuously.
    assert ".claude/workflows: merged" in plain.stdout, (
        f"premise broken: plain build did not merge into .claude/workflows:\n{plain.stdout}"
    )
    again = _build(target, "copy")
    assert again.returncode == 0, f"maker-way rebuild failed:\n{again.stdout}\n{again.stderr}"

    gaps, out = _drift_gaps(target)
    gemini_gaps = [g for g in gaps if g.startswith(".gemini/workflows/")]
    assert gemini_gaps == [], f"check-output-drift reports build-made files as GAPs:\n{out}"

    foreign = f".gemini/workflows/{_minted('foreign')}.js"
    (target / foreign).write_text("// not the build's\n", encoding="utf-8")
    gaps, out = _drift_gaps(target)
    assert foreign in gaps, f"a genuinely foreign file is no longer reported as a GAP:\n{out}"
