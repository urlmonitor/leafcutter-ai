"""
MODULE: unit_tests/commit_guardian/test_bp_1300e_1_i.py
COVERS: BP-1300e-1-i -- the commit-time lint check and CI read ONE definition of
    what is linted and by which rules (leafcutter-lint.json), so changing it in
    one place changes every verdict.

The anti-list arms change the declaration and NOTHING else, then execute every
    runner: the commit hook, the lint job's step as read from the real ci.yml,
    scripts/run_ci_local.py and `--mode files --json`. Excluded-tree arm stages a
    violating file under an EXCLUDED tree (templates/), the only input that
    exercises the --force-exclude trap.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bp_1300e_lint_gate_fixture as fx  # noqa: E402

WHOLE_PROJECT = {"version": 1, "steps": [{"name": "repository-rules", "paths": ["."]}]}


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_i_violation_in_excluded_templates_tree_is_not_refused(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-i
    # angle: discrimination
    """Declaration '.' + ruff.toml excluding templates/: a staged templates/z.py with E741 commits.

    Wrong versions caught: staged paths handed to ruff without --force-exclude; filtering by
    declared paths only and ignoring the configuration's exclude list. Control row: the same
    violation under scripts/ (not excluded) IS refused, so E741 is detectable in this fixture.
    """
    repo, work = fx.setup(tmp_path, shared_reference_layout, declaration=WHOLE_PROJECT)
    assert "templates" in (fx.REPO_ROOT / "ruff.toml").read_text(encoding="utf-8")
    fx.stage_files(repo, {"templates/z.py": fx.e741_source(3)})

    proc = fx.commit(repo, work, "excluded tree")
    text = fx.out(proc)

    assert proc.returncode == 0, f"CI never lints templates/; refusing it disagrees with CI: {text!r}"
    assert "excluded tree" in fx.subjects(repo), "the commit must exist"
    assert fx.hook_status(text, repo.stanza["name"]) == "Passed" and "RESULT:" in text, text
    git_reset = fx.git(["reset", "-q"], repo.root)
    assert git_reset.returncode == 0

    before = fx.commit_count(repo)
    fx.stage_files(repo, {"scripts/z.py": fx.e741_source(3)})
    control = fx.commit(repo, work, "control")
    assert control.returncode != 0 and fx.commit_count(repo) == before, fx.out(control)
    assert fx.mentions_finding(fx.out(control), "scripts/z.py", 3, "E741"), fx.out(control)


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_i_root_file_outside_declared_trees_is_not_refused(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-i
    # angle: criterion
    """Using the repository's real leafcutter-lint.json, a staged repo-root z.py with E741 commits."""
    repo, work = fx.setup(tmp_path, shared_reference_layout)
    fx.stage_files(repo, {"z.py": fx.e741_source(5)})

    proc = fx.commit(repo, work, "root file")
    text = fx.out(proc)

    assert proc.returncode == 0, f"a root file is outside every declared tree: {text!r}"
    assert "root file" in fx.subjects(repo)
    assert "RESULT: nothing_to_inspect" in text, f"the gate must say it had nothing to inspect: {text!r}"
    fx.git(["reset", "-q"], repo.root)
    before = fx.commit_count(repo)
    fx.stage_files(repo, {"unit_tests/z.py": fx.e741_source(5)})
    control = fx.commit(repo, work, "control")
    assert control.returncode != 0 and fx.commit_count(repo) == before, "control row: a declared tree is judged"


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_i_widening_the_declaration_widens_commit_time_and_ci_verdicts_together(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-i
    # angle: criterion
    """Add tools/ to the declaration and nothing else: a staged tools/ violation is refused at
    commit AND the lint job's step, read from the real ci.yml and executed, exits non-zero on it.

    Wrong version caught: the hook or the CI step holds its own tree list. Control repo (the
    real, unwidened declaration) lets the same file commit and CI exit 0.
    """
    layout = shared_reference_layout
    wide, work = fx.setup(tmp_path, layout, name="wide", declaration=fx.widened(fx.real_declaration(), "tools"))
    before = fx.commit_count(wide)
    fx.stage_files(wide, {"tools/v.py": fx.e741_source(7)})

    proc = fx.commit(wide, work)
    assert proc.returncode != 0 and fx.commit_count(wide) == before, fx.out(proc)
    assert fx.mentions_finding(fx.out(proc), "tools/v.py", 7, "E741"), fx.out(proc)
    ci = fx.run_ci_lint(wide, work)
    assert ci.returncode != 0, f"CI's lint step must also fail on the widened scope: {fx.out(ci)!r}"
    assert fx.mentions_finding(fx.out(ci), "tools/v.py", 7, "E741"), fx.out(ci)

    narrow, work2 = fx.setup(tmp_path / "ctl", layout)
    fx.stage_files(narrow, {"tools/v.py": fx.e741_source(7)})
    assert fx.commit(narrow, work2, "outside scope").returncode == 0
    assert fx.run_ci_lint(narrow, work2).returncode == 0, "CI must agree with the commit-time verdict"


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_i_dropping_try_from_the_second_step_relaxes_both_verdicts(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-i
    # angle: criterion
    """Declaration's kernel step select becomes [E722, BLE001]: a staged TRY-only violation under
    kernel/ commits and the executed ci.yml lint command exits 0 on the same content. Control: with
    the real declaration the same content is refused naming TRY300."""
    layout = shared_reference_layout
    relaxed = fx.real_declaration()
    kernel_step = next(s for s in relaxed["steps"] if "select" in s)
    kernel_step["select"] = [code for code in kernel_step["select"] if code != "TRY"]
    assert kernel_step["select"], "the real declaration's second step must select something besides TRY"

    control, work = fx.setup(tmp_path, layout, name="control")
    before = fx.commit_count(control)
    fx.stage_files(control, {"kernel/t.py": fx.try_only_source()})
    refused = fx.commit(control, work)
    assert refused.returncode != 0 and fx.commit_count(control) == before, fx.out(refused)
    assert fx.mentions_finding(fx.out(refused), "kernel/t.py", 4, "TRY300"), fx.out(refused)

    repo, work2 = fx.setup(tmp_path / "relaxed", layout, declaration=relaxed)
    fx.stage_files(repo, {"kernel/t.py": fx.try_only_source()})
    proc = fx.commit(repo, work2, "try only")
    assert proc.returncode == 0, f"neither verdict may refuse TRY once it is dropped: {fx.out(proc)!r}"
    assert "try only" in fx.subjects(repo)
    ci = fx.run_ci_lint(repo, work2)
    assert ci.returncode == 0, f"CI's second step must relax with the declaration: {fx.out(ci)!r}"


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_i_run_ci_local_and_files_mode_follow_the_declaration_without_their_own_edit(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-i
    # angle: reachability
    """scripts/run_ci_local.py's lint gate and `--mode files --json` (BO-570-3's contract) both apply
    a changed declaration; neither file is edited between the runs."""
    layout = shared_reference_layout
    repo, work = fx.setup(tmp_path, layout, link_template_source=True)
    fx.write(repo.root, "tools/v.py", fx.e741_source(4))
    env = fx.hook_env(work)
    files_args = ("--mode", "files", "--files", "tools/v.py")
    run_local = [fx.PYTHON, str(fx.REPO_ROOT / "scripts" / "run_ci_local.py"), "--repo-root", str(repo.root)]

    _, before = fx.gate_json(layout, repo.root, *files_args, env=env)
    local_before = fx.sh(run_local, repo.root, env=env, timeout=fx.HOOK_TIMEOUT)
    assert before["outcome"] in ("ok", "nothing_to_inspect"), before
    assert re.search(r"\[PASS\] lint", fx.out(local_before)), fx.out(local_before)

    (repo.root / "leafcutter-lint.json").write_text(
        json.dumps(fx.widened(fx.real_declaration(), "tools")), encoding="utf-8")
    proc, after = fx.gate_json(layout, repo.root, *files_args, env=env)
    local_after = fx.sh(run_local, repo.root, env=env, timeout=fx.HOOK_TIMEOUT)

    assert after["outcome"] == "refused" and proc.returncode != 0, after
    assert fx.finding_keys(after) == [("tools/v.py", 4, "E741")], after["findings"]
    assert re.search(r"\[FAIL\] lint", fx.out(local_after)), fx.out(local_after)
    assert fx.mentions_finding(fx.out(local_after), "tools/v.py", 4, "E741"), fx.out(local_after)


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_i_malformed_declaration_refuses_naming_the_file_and_key(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-i
    # angle: failure
    """leafcutter-lint.json with an unknown key 'path' is staged with a CLEAN in-scope file: the
    commit is refused as could_not_check naming leafcutter-lint.json and 'path'.

    Wrong version caught: falling back to the default scope when the declaration is unreadable
    (the default scope would accept this clean file, so only a real refusal passes).
    """
    repo, work = fx.setup(tmp_path, shared_reference_layout)
    broken = fx.real_declaration()
    broken["steps"][0]["path"] = ["tools"]
    before = fx.commit_count(repo)
    fx.stage_files(repo, {"leafcutter-lint.json": json.dumps(broken), "scripts/a.py": fx.CLEAN})

    proc = fx.commit(repo, work)
    text = fx.out(proc)

    assert proc.returncode != 0 and fx.commit_count(repo) == before, text
    assert "RESULT: could_not_check" in text, text
    assert "leafcutter-lint.json" in text and re.search(r"\bpath\b", text), text
    assert fx.hook_status(text, repo.stanza["name"]) == "Failed", text


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_i_template_source_and_deployed_runner_report_identical_findings(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-i
    # angle: deployed
    """`--mode full --json` from templates/scripts/commit_guardian/ and from the shared layout's
    deployed copy over the same fixture give equal outcome and findings (CI runs the template)."""
    layout = shared_reference_layout
    repo, work = fx.setup(tmp_path, layout)
    fx.write(repo.root, "unit_tests/x.py", fx.e741_source(12))
    fx.write(repo.root, "kernel/y.py", fx.ble001_source(30))
    env = fx.hook_env(work)

    template_run, from_template = fx.gate_json(
        layout, repo.root, "--mode", "full", env=env, script=fx.TEMPLATE_GUARDIAN / "check_lint_gate.py")
    deployed_run, from_deployed = fx.gate_json(layout, repo.root, "--mode", "full", env=env)

    assert from_template["outcome"] == from_deployed["outcome"] == "refused"
    assert template_run.returncode != 0 and deployed_run.returncode != 0
    expected = [("kernel/y.py", 30, "BLE001"), ("unit_tests/x.py", 12, "E741")]
    assert fx.finding_keys(from_template) == fx.finding_keys(from_deployed) == expected
