"""
MODULE: unit_tests/commit_guardian/test_bp_1300e_1.py
COVERS: BP-1300e-1 -- a commit carrying a violation either step of CI's required
    lint check would reject is refused, naming the file, line and rule.

EVERY test drives an ordinary `git commit` through a real `pre-commit install`
    in a temporary repository whose `.pre-commit-config.yaml` carries
    `check-lint-gate` ALONE, pointed at the DEPLOYED scripts of the shared
    reference layout (read-only: ``shared_layout_reader``; no private build).
RED BASELINE: the gate does not exist yet, so each test fails on an assertion
    about the commit's observable result -- never on an import.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bp_1300e_lint_gate_fixture as fx  # noqa: E402


def _assert_refused(proc, repo, before: int) -> str:
    text = fx.out(proc)
    assert proc.returncode != 0, f"commit was not refused: {text!r}"
    assert fx.commit_count(repo) == before, "a refused commit must not create a commit"
    assert fx.hook_status(text, repo.stanza["name"]) == "Failed", text
    return text


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_e741_under_unit_tests_is_refused_naming_path_line_and_rule(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1
    # angle: criterion
    """Staged unit_tests/x.py with `l = 1` at line 12: refused, naming path, 12, E741."""
    repo, work = fx.setup(tmp_path, shared_reference_layout)
    before = fx.commit_count(repo)
    fx.stage_files(repo, {"unit_tests/x.py": fx.e741_source(12)})

    text = _assert_refused(fx.commit(repo, work), repo, before)

    assert fx.mentions_finding(text, "unit_tests/x.py", 12, "E741"), text


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_ble001_under_kernel_is_refused_naming_path_line_and_rule(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1
    # angle: criterion
    """Staged kernel/y.py with `except Exception:` at line 30: refused, naming path, 30, BLE001."""
    repo, work = fx.setup(tmp_path, shared_reference_layout)
    before = fx.commit_count(repo)
    fx.stage_files(repo, {"kernel/y.py": fx.ble001_source(30)})

    text = _assert_refused(fx.commit(repo, work), repo, before)

    assert fx.mentions_finding(text, "kernel/y.py", 30, "BLE001"), text


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_ble001_under_scripts_commits_because_step_two_is_kernel_only(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1
    # angle: discrimination
    """The same `except Exception:` staged under scripts/ commits (CI step 2 is kernel-only).

    Wrong versions this must catch: (a) the second step's rule set applied to every
    declared tree; (b) both steps merged into one ruff run with the union selection
    over all trees. Both would refuse; this asserts the commit EXISTS in git log, and
    that the gate demonstrably ran and inspected the file (so a hook that never ran,
    which also "commits", cannot satisfy it).
    """
    repo, work = fx.setup(tmp_path, shared_reference_layout)
    fx.stage_files(repo, {"scripts/s.py": fx.ble001_source(30)})

    proc = fx.commit(repo, work, "scripts handler")
    text = fx.out(proc)

    assert proc.returncode == 0, f"scripts/ must not be held to the kernel-only rules: {text!r}"
    assert "scripts handler" in fx.subjects(repo), "the commit must exist in git log"
    assert fx.hook_status(text, repo.stanza["name"]) == "Passed", text
    assert "RESULT: ok" in text and "scripts/s.py" in text, f"the gate must say what it inspected: {text!r}"


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_both_steps_findings_reported_in_one_refusal(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1
    # angle: criterion
    """One commit staging the E741 and BLE001 files is refused once, naming both findings.

    Wrong version caught: returning after the first step that finds anything.
    """
    repo, work = fx.setup(tmp_path, shared_reference_layout)
    before = fx.commit_count(repo)
    fx.stage_files(repo, {"unit_tests/x.py": fx.e741_source(12), "kernel/y.py": fx.ble001_source(30)})

    text = _assert_refused(fx.commit(repo, work), repo, before)

    assert fx.mentions_finding(text, "unit_tests/x.py", 12, "E741"), text
    assert fx.mentions_finding(text, "kernel/y.py", 30, "BLE001"), text


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_clean_change_commits_and_names_the_files_inspected(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1
    # angle: criterion
    """Clean staged files under scripts/ and kernel/ commit; the hook names them, RESULT: ok, Passed."""
    repo, work = fx.setup(tmp_path, shared_reference_layout)
    fx.stage_files(repo, {"scripts/a.py": fx.CLEAN, "kernel/b.py": fx.CLEAN})

    proc = fx.commit(repo, work, "clean change")
    text = fx.out(proc)

    assert proc.returncode == 0, text
    assert "clean change" in fx.subjects(repo)
    assert fx.hook_status(text, repo.stanza["name"]) == "Passed", text
    assert "RESULT: ok" in text, text
    assert "scripts/a.py" in text and "kernel/b.py" in text, f"inspected files must be named: {text!r}"


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_ordinary_commit_reaches_the_deployed_gate(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1
    # angle: reachability
    """With the hook installed by `pre-commit install` and no other command, an E741 commit is
    refused and the refusal comes from check_lint_gate.py in the shared DEPLOYED layout."""
    layout = shared_reference_layout
    repo, work = fx.setup(tmp_path, layout)
    deployed_gate = fx.deployed_dir(layout) / "check_lint_gate.py"
    assert deployed_gate.is_file(), f"{deployed_gate} is not deployed (deploy-manifest gap?)"
    assert str(deployed_gate) in repo.stanza["entry"], repo.stanza["entry"]
    assert (repo.root / ".git" / "hooks" / "pre-commit").is_file(), "pre-commit install did not run"
    before = fx.commit_count(repo)
    fx.stage_files(repo, {"unit_tests/x.py": fx.e741_source(12)})

    proc = fx.commit(repo, work)  # plain `git commit -m`: nothing invoked by hand
    text = _assert_refused(proc, repo, before)

    assert "RESULT: refused" in text, f"the refusal must carry the gate's own outcome line: {text!r}"
    assert fx.mentions_finding(text, "unit_tests/x.py", 12, "E741"), text
    direct, payload = fx.gate_json(layout, repo.root, env=fx.hook_env(work))
    assert direct.returncode != 0 and payload["outcome"] == "refused", payload
    assert (fx.finding_keys(payload) == [("unit_tests/x.py", 12, "E741")]), payload["findings"]
