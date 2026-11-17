"""
MODULE: unit_tests/commit_guardian/test_bp_1300e_1_ii.py
COVERS: BP-1300e-1-ii -- each staged file is judged WHOLE, as it will be
    committed (index blob), so a touched file with older violations is refused
    just as CI would refuse it.

PRE-COMMIT STASHES UNSTAGED CHANGES before it runs hooks, so through a plain
    `git commit` the working copy always equals the index and cannot be told
    apart from it. Every arm that separates the two therefore ALSO runs the
    deployed gate directly (staged mode, --json) in the same dirty state -- the
    only observation that distinguishes "reads the index blob" from "reads the
    working tree".
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bp_1300e_lint_gate_fixture as fx  # noqa: E402


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_ii_unstaged_violating_file_is_not_inspected_and_count_is_one(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-ii
    # angle: criterion
    """scripts/a.py carries E741 unstaged; clean scripts/b.py is staged: the commit completes and the
    output names exactly scripts/b.py as inspected. Wrong version caught: linting the whole declared
    scope on every commit."""
    layout = shared_reference_layout
    repo, work = fx.setup(tmp_path, layout, files={"scripts/a.py": fx.CLEAN})
    fx.write(repo.root, "scripts/a.py", fx.e741_source(5))  # tracked, modified, NOT staged
    fx.stage_files(repo, {"scripts/b.py": fx.CLEAN})

    _, payload = fx.gate_json(layout, repo.root, env=fx.hook_env(work))
    proc = fx.commit(repo, work, "only b")
    text = fx.out(proc)

    assert payload["files_inspected"] == ["scripts/b.py"], payload
    assert proc.returncode == 0, text
    assert "only b" in fx.subjects(repo)
    assert "scripts/b.py" in text and "scripts/a.py" not in text, text


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_ii_preexisting_f841_in_touched_file_is_refused_with_predates_wording(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-ii
    # angle: discrimination
    """unit_tests/c.py is committed with F841 at line 40; a staged edit changes only line 90 cleanly:
    refused, naming line 40, F841 and the predates / whole-file / CI sentence.

    Wrong versions caught: filtering findings to changed lines or hunks; omitting the explanation.
    """
    layout = shared_reference_layout
    repo, work = fx.setup(tmp_path, layout, files={"unit_tests/c.py": fx.f841_source(0)})
    before = fx.commit_count(repo)
    fx.stage_files(repo, {"unit_tests/c.py": fx.f841_source(1)})

    _, payload = fx.gate_json(layout, repo.root, env=fx.hook_env(work))
    proc = fx.commit(repo, work, "edit line 90")
    text = fx.out(proc)

    assert fx.finding_keys(payload) == [("unit_tests/c.py", 40, "F841")], payload["findings"]
    assert payload["findings"][0]["predates_change"] is True, payload["findings"]
    assert proc.returncode != 0 and fx.commit_count(repo) == before, text
    assert fx.mentions_finding(text, "unit_tests/c.py", 40, "F841"), text
    lowered = text.lower()
    assert "predates this change" in lowered, text
    assert "modifies" in lowered, text
    assert "whichever change introduced it" in lowered, text


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_ii_newly_unused_variable_at_untouched_line_is_not_labelled_preexisting(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-ii
    # angle: boundary
    """Removing the only use of a variable creates F841 at an UNTOUCHED line: reported WITHOUT the
    predates label, because HEAD had no such finding (a hunk-based label would get this wrong)."""
    layout = shared_reference_layout
    repo, work = fx.setup(tmp_path, layout, files={"unit_tests/n.py": fx.used_variable_source("value")})
    fx.stage_files(repo, {"unit_tests/n.py": fx.used_variable_source("0")})
    env = fx.hook_env(work)

    proc, payload = fx.gate_json(layout, repo.root, env=env)
    human = fx.run_gate(layout, repo.root, env=env)

    assert payload["outcome"] == "refused" and proc.returncode != 0, payload
    assert fx.finding_keys(payload) == [("unit_tests/n.py", 6, "F841")], payload["findings"]
    assert payload["findings"][0]["predates_change"] is False, payload["findings"]
    assert fx.mentions_finding(fx.out(human), "unit_tests/n.py", 6, "F841"), fx.out(human)
    assert "predates" not in fx.out(human).lower(), fx.out(human)


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_ii_staged_violation_is_refused_although_working_copy_is_clean(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-ii
    # angle: discrimination
    """Stage a file with E741, then fix it in the working copy without staging: refused.
    Wrong version caught: reading the working-tree file instead of the index blob."""
    layout = shared_reference_layout
    repo, work = fx.setup(tmp_path, layout)
    before = fx.commit_count(repo)
    fx.stage_files(repo, {"unit_tests/e.py": fx.e741_source(12)})
    fx.write(repo.root, "unit_tests/e.py", fx.CLEAN)  # unstaged fix

    proc, payload = fx.gate_json(layout, repo.root, env=fx.hook_env(work))
    commit = fx.commit(repo, work, "staged violation")

    assert payload["outcome"] == "refused" and proc.returncode != 0, payload
    assert fx.finding_keys(payload) == [("unit_tests/e.py", 12, "E741")], payload["findings"]
    assert commit.returncode != 0 and fx.commit_count(repo) == before, fx.out(commit)
    assert fx.mentions_finding(fx.out(commit), "unit_tests/e.py", 12, "E741"), fx.out(commit)


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_ii_clean_staged_version_commits_although_working_copy_is_dirty(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-ii
    # angle: criterion
    """Stage a clean file, then add E741 in the working copy without staging: the commit completes."""
    layout = shared_reference_layout
    repo, work = fx.setup(tmp_path, layout)
    fx.stage_files(repo, {"unit_tests/f.py": fx.CLEAN})
    fx.write(repo.root, "unit_tests/f.py", fx.e741_source(12))  # unstaged violation

    proc, payload = fx.gate_json(layout, repo.root, env=fx.hook_env(work))
    commit = fx.commit(repo, work, "clean staged")

    assert payload["outcome"] == "ok" and proc.returncode == 0, payload
    assert payload["files_inspected"] == ["unit_tests/f.py"], payload
    assert commit.returncode == 0, fx.out(commit)
    assert "clean staged" in fx.subjects(repo)
    assert "RESULT: ok" in fx.out(commit), fx.out(commit)


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_ii_commit_with_pathspec_is_judged_on_the_temporary_index(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-ii
    # angle: boundary
    """`git commit -m x -- scripts/d.py` where d.py's working copy carries E741 but the default index
    holds a clean version: refused, because a pathspec commit judges the content it is committing.

    Wrong version caught: reading .git/index directly, or scrubbing GIT_INDEX_FILE from the child
    environment (either would see the clean default index and let the commit through).
    """
    repo, work = fx.setup(tmp_path, shared_reference_layout, files={"scripts/d.py": fx.CLEAN})
    before = fx.commit_count(repo)
    fx.write(repo.root, "scripts/d.py", fx.e741_source(12))  # modified, NOT staged

    proc = fx.commit(repo, work, "x", args=("--", "scripts/d.py"))
    text = fx.out(proc)

    assert proc.returncode != 0 and fx.commit_count(repo) == before, text
    assert fx.mentions_finding(text, "scripts/d.py", 12, "E741"), text
    assert fx.hook_status(text, repo.stanza["name"]) == "Failed", text


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_ii_deletion_only_commit_is_not_linted_and_does_not_error(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-ii
    # angle: criterion
    """A commit that only `git rm`s an in-scope .py completes; nothing to inspect, and no error."""
    repo, work = fx.setup(tmp_path, shared_reference_layout, files={"scripts/g.py": fx.CLEAN})
    removed = fx.git(["rm", "-q", "scripts/g.py"], repo.root)
    assert removed.returncode == 0, fx.out(removed)

    proc = fx.commit(repo, work, "remove g")
    text = fx.out(proc)

    assert proc.returncode == 0, text
    assert "remove g" in fx.subjects(repo)
    assert "RESULT: nothing_to_inspect" in text, text
    assert "Traceback" not in text and "could_not_check" not in text, text
    assert fx.hook_status(text, repo.stanza["name"]) == "Passed", text


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_ii_partially_staged_ruff_config_is_could_not_check(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-ii
    # angle: failure
    """ruff.toml has unstaged edits relative to its index version and a clean in-scope .py is staged:
    could_not_check, ruff_config_partially_staged, naming ruff.toml. (Observed by running the gate
    directly: a plain `git commit` stashes the unstaged edit first, so the state never reaches it.)"""
    layout = shared_reference_layout
    repo, work = fx.setup(tmp_path, layout)
    ruff_toml = repo.root / "ruff.toml"
    ruff_toml.write_text(ruff_toml.read_text(encoding="utf-8") + "\n# unstaged local edit\n", encoding="utf-8")
    fx.stage_files(repo, {"scripts/a.py": fx.CLEAN})
    env = fx.hook_env(work)

    proc, payload = fx.gate_json(layout, repo.root, env=env)
    human = fx.run_gate(layout, repo.root, env=env)

    assert proc.returncode != 0 and payload["outcome"] == "could_not_check", payload
    assert payload["reason"] == "ruff_config_partially_staged", payload
    assert "ruff.toml" in fx.out(human) and "RESULT: could_not_check" in fx.out(human), fx.out(human)
