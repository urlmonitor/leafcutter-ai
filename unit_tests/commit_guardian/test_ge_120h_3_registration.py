"""
MODULE: unit_tests/commit_guardian/test_ge_120h_3_registration.py
COVERS: GE-120h-3 -- arms 1, 2 and the registration-integrity guard.

BACKFILL (backfill: true). Arms 1 and 2 landed in 5d0792d1 (PR #808) and were
OBSERVED passing, never asserted; the AC's coverage note requires them to be
"covered by attempting real commits and asserting the outcome". These tests
are expected to be GREEN on first run -- the behaviour already exists. Each
was shown able to go red in a disposable broken copy (see the sign-off).

EVIDENCE STRENGTH, STATED PLAINLY:
  - Entries 1 and 2 run a REAL ``git commit`` (and, for the post-merge check,
    a real ``git merge --no-ff``) in a scratch repo wired by a real
    ``pre-commit install``. The scratch ``.pre-commit-config.yaml`` is not
    hand-typed: each of the five hook stanzas is copied from the
    ``.pre-commit-config.yaml`` that build.py generated into the shared
    deployed layout (ids, names, entry, stages, always_run). The ONLY edit is
    pointing the script path tokens at that layout's deployed scripts by
    absolute path. The other ~60 hooks are deliberately left out (unrelated
    to this AC, and several fail in a nested build target).
  - Evidence is the hook-run status line pre-commit prints per hook, not the
    manifest text.

MARKERS: the layout is only READ (copied-from / validated), never altered, so
    tests are ``shared_layout_reader``; no private build is spawned.

NO OVERRIDES: the tests always read the real shared layout, the real guardian
    dir and the real repo root. (Env-var redirect levers were removed: when set
    they pointed the tests at another tree and asserted nothing about the
    real one. The can-it-fail evidence is in the ticket's test-writer comment.)
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_120h_3_fixture as fx  # noqa: E402

FOUR_PRE_COMMIT = (
    "check-folder-density",
    "check-test-fixture-bloat",
    "check-sql-complexity",
    "check-debug-scripts",
)
POST_MERGE = "check-ac-done-on-merge"
FIVE = (*FOUR_PRE_COMMIT, POST_MERGE)

_HOOK_TIMEOUT = 180
_ENV = {**os.environ, "COMMIT_AGENT_MODE": "1"}


def _generated_hooks(layout: Path) -> dict[str, dict]:
    """Every hook stanza of the build-generated .pre-commit-config.yaml, by id."""
    config = yaml.safe_load((layout / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    return {h["id"]: h for repo in config["repos"] for h in repo["hooks"]}


def _assert_entry_runs_its_script(hook_id: str, hook: dict) -> None:
    """A stanza whose entry runs something else is registered in name only."""
    script = hook_id.replace("-", "_") + ".py"
    assert script in hook["entry"], f"{hook_id} entry never names {script}: {hook['entry']!r}"


def _point_at_deployed(entry: str, layout: Path) -> str:
    """Rewrite script-path tokens of a generated entry to the layout's deployed files."""
    out = []
    for token in entry.split():
        marker = "scripts/commit_guardian/"
        if marker in token:
            tail = token[token.index(marker):]
            target = layout / tail
            if not target.exists():
                target = layout / ".leafcutter" / tail
            assert target.exists(), f"generated entry names {token!r}; not deployed at {target}"
            token = str(target)
        out.append(token)
    return " ".join(out)


def _scratch_repo_with_five(layout: Path, tmp_path: Path) -> tuple[Path, dict[str, dict]]:
    """Real git repo, pre-commit installed for pre-commit + post-merge, carrying
    the five generated stanzas ONLY."""
    hooks = _generated_hooks(layout)
    missing = [h for h in FIVE if h not in hooks]
    assert not missing, f"generated .pre-commit-config.yaml lacks {missing}"
    stanzas = []
    for hook_id in FIVE:
        h = dict(hooks[hook_id])
        _assert_entry_runs_its_script(hook_id, h)
        h["entry"] = _point_at_deployed(h["entry"], layout)
        stanzas.append(h)
    repo = tmp_path / "scratch"
    repo.mkdir()
    fx.init_repo(repo)
    fx.git(["checkout", "-q", "-b", "main"], repo)
    (repo / ".pre-commit-config.yaml").write_text(
        yaml.safe_dump({"repos": [{"repo": "local", "hooks": stanzas}]}), encoding="utf-8"
    )
    for hook_type in ("pre-commit", "post-merge"):
        done = subprocess.run(
            ["pre-commit", "install", "--hook-type", hook_type],
            cwd=str(repo), capture_output=True, text=True, timeout=60, check=False,
        )
        assert done.returncode == 0, f"pre-commit install {hook_type}: {done.stdout}{done.stderr}"
    return repo, {h["id"]: h for h in stanzas}


def _ordinary_commit(repo: Path, message: str) -> subprocess.CompletedProcess:
    """A plain `git commit -m` -- nothing invoked by hand, no flag but -m."""
    return subprocess.run(
        ["git", "commit", "-m", message], cwd=str(repo), capture_output=True, text=True,
        timeout=_HOOK_TIMEOUT, check=False, env=_ENV,
    )


def _ran_and_passed(output: str, name: str) -> bool:
    """True when pre-commit's own status line shows *name* ... Passed."""
    pattern = re.escape(name) + r"[.\s]*Passed"
    return re.search(pattern, output) is not None


def _stage_ordinary_content(repo: Path) -> None:
    (repo / "README.md").write_text("# scratch\n\nordinary prose\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "mod.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "db").mkdir()
    (repo / "db" / "simple.sql").write_text("SELECT 1;\n", encoding="utf-8")
    fx.git(["add", "-A", "--", ".", ":!.pre-commit-config.yaml"], repo)


@pytest.mark.shared_layout_reader
def test_ge120h3_all_five_run_on_an_ordinary_commit(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: GE-120h-3
    # angle: deployed
    """A real ``git commit`` runs each of the four pre-commit checks, and a real
    ``git merge`` runs check-ac-done-on-merge, each evidenced by the hook's own
    status line from that run -- not by manifest text."""
    layout = shared_reference_layout
    repo, stanzas = _scratch_repo_with_five(layout, tmp_path)
    _stage_ordinary_content(repo)

    commit = _ordinary_commit(repo, "ordinary change")
    output = commit.stdout + commit.stderr
    for hook_id in FOUR_PRE_COMMIT:
        assert _ran_and_passed(output, stanzas[hook_id]["name"]), (
            f"{hook_id} did not report a run on an ordinary commit. Output: {output!r}"
        )
    assert POST_MERGE not in output and stanzas[POST_MERGE]["name"] not in output, (
        f"the post-merge check must not run at commit time. Output: {output!r}"
    )

    fx.git(["checkout", "-q", "-b", "feature"], repo)
    (repo / "feature.txt").write_text("feature work\n", encoding="utf-8")
    fx.git(["add", "feature.txt"], repo)
    assert _ordinary_commit(repo, "feature work").returncode == 0
    fx.git(["checkout", "-q", "main"], repo)
    (repo / "main_side.txt").write_text("main work\n", encoding="utf-8")
    fx.git(["add", "main_side.txt"], repo)
    assert _ordinary_commit(repo, "main work").returncode == 0
    merge = subprocess.run(
        ["git", "merge", "--no-ff", "-m", "merge feature", "feature"], cwd=str(repo),
        capture_output=True, text=True, timeout=_HOOK_TIMEOUT, check=False, env=_ENV,
    )
    merged = merge.stdout + merge.stderr
    assert merge.returncode == 0, merged
    assert _ran_and_passed(merged, stanzas[POST_MERGE]["name"]), (
        f"check-ac-done-on-merge did not report a run on a real merge. Output: {merged!r}"
    )


@pytest.mark.shared_layout_reader
def test_ge120h3_previously_acceptable_content_still_commits(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: GE-120h-3
    # angle: criterion
    """Ordinary acceptable content (prose, a small .py, a trivial .sql) commits
    with rc 0 while all five checks are registered and installed."""
    layout = shared_reference_layout
    repo, _ = _scratch_repo_with_five(layout, tmp_path)
    _stage_ordinary_content(repo)

    commit = _ordinary_commit(repo, "acceptable content")

    assert commit.returncode == 0, (
        f"acceptable content was refused. Output: {commit.stdout + commit.stderr!r}"
    )
    assert fx.git(["rev-parse", "--verify", "HEAD"], repo, check=False).returncode == 0
    assert "Failed" not in commit.stdout + commit.stderr


def test_ge120h3_preexisting_over_density_directories_do_not_refuse(tmp_path: Path) -> None:
    # covers: GE-120h-3
    # angle: real_artifact
    """A folder ALREADY over max_files_per_folder before the commit, with one
    more file staged into it: check_folder_density.py (driven through
    run_hook.py against a real git repo) exits 0 and reports the folder as
    PRE-EXISTING, not as a violation."""
    guardian = fx.GUARDIAN_DIR
    repo = tmp_path / "density"
    repo.mkdir()
    fx.init_repo(repo)
    crowded = repo / "crowded"
    crowded.mkdir()
    for i in range(20):
        (crowded / f"f{i}.txt").write_text(f"content {i}\n", encoding="utf-8")
    fx.commit_all(repo, "already over the limit")
    (crowded / "one_more.txt").write_text("one more\n", encoding="utf-8")
    fx.stage_all(repo)

    result = subprocess.run(
        [sys.executable, str(guardian / "run_hook.py"), str(guardian / "check_folder_density.py")],
        cwd=str(repo), capture_output=True, text=True, timeout=60, check=False,
    )
    output = result.stdout + result.stderr

    assert result.returncode == 0, f"pre-existing state refused the commit: {output!r}"
    assert "PRE-EXISTING" in output and "crowded" in output, (
        f"the existing state must be reported by name. Got: {output!r}"
    )
    assert "FOLDER TOO DENSE" not in output, f"reported as a violation: {output!r}"


@pytest.mark.shared_layout_reader
def test_ge120h3_registration_leaves_precommit_generation_and_hook_parity_intact(
    shared_reference_layout: Path,
) -> None:
    # covers: GE-120h-3
    # angle: seam
    """build_precommit's generated config (producer) names all five, is accepted
    by pre-commit's own validator (consumer), and the hook-parity check run
    against the repository reports zero violations."""
    layout = shared_reference_layout
    config_path = layout / ".pre-commit-config.yaml"
    hooks = _generated_hooks(layout)

    for hook_id in FIVE:
        assert hook_id in hooks, f"generated config does not name {hook_id}"
        _assert_entry_runs_its_script(hook_id, hooks[hook_id])
    for hook_id in FOUR_PRE_COMMIT:
        assert hooks[hook_id]["stages"] == ["pre-commit"], hooks[hook_id]
        assert hooks[hook_id].get("always_run") is True and "files" not in hooks[hook_id]
    assert hooks[POST_MERGE]["stages"] == ["post-merge"], hooks[POST_MERGE]

    valid = subprocess.run(
        ["pre-commit", "validate-config", str(config_path)],
        cwd=str(layout), capture_output=True, text=True, timeout=60, check=False,
    )
    assert valid.returncode == 0, f"generated config invalid: {valid.stdout}{valid.stderr}"

    parity = subprocess.run(
        [sys.executable, str(fx.GUARDIAN_DIR / "check_hook_parity.py")],
        cwd=str(fx.REPO_ROOT), capture_output=True, text=True, timeout=60, check=False,
    )
    assert parity.returncode == 0, f"hook parity violations: {parity.stdout}{parity.stderr}"
    assert "BLOCKED" not in parity.stdout + parity.stderr


_TAGGED_DEBUG_SCRIPT = (
    '"""\nDEBUG SCRIPT: yes\nCATEGORY: misc\n'
    "DESCRIPTION: scratch script for the GE-120h-3 commit-path test\n"
    'TABLES: none\n"""\nprint("hi")\n'
)


def _ran_and_failed(output: str, name: str) -> bool:
    """True when pre-commit's own status line shows *name* ... Failed."""
    return re.search(re.escape(name) + r"[.\s]*Failed", output) is not None


def _commit_debug_script(layout: Path, tmp_path: Path, content: str):
    tmp_path.mkdir(parents=True, exist_ok=True)
    repo, stanzas = _scratch_repo_with_five(layout, tmp_path)
    scripts_dir = repo / "debugging" / "scripts" / "misc"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "probe_script.py").write_text(content, encoding="utf-8")
    fx.git(["add", "debugging"], repo)
    return stanzas, _ordinary_commit(repo, "add a debug script")


@pytest.mark.shared_layout_reader
def test_ge120h3_untagged_debug_script_is_refused_by_a_real_git_commit(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: GE-120h-3
    # angle: failure
    """A refusable input (untagged debugging/scripts file) through the real
    ``git commit`` path: rc != 0, Check Debug Scripts shows Failed in
    pre-commit's per-hook output, and the file is named. Control in the same
    test: a correctly tagged script commits with rc 0 (so the refusal is
    caused by the missing tags, not by the scratch setup)."""
    stanzas, refused = _commit_debug_script(
        shared_reference_layout, tmp_path / "bad", fx.make_untagged_debug_script()
    )
    output = refused.stdout + refused.stderr
    assert refused.returncode != 0, f"untagged debug script committed. Output: {output!r}"
    assert _ran_and_failed(output, stanzas["check-debug-scripts"]["name"]), (
        f"check-debug-scripts not shown Failed. Output: {output!r}"
    )
    assert "probe_script.py" in output, f"offending file not named. Output: {output!r}"

    _, accepted = _commit_debug_script(
        shared_reference_layout, tmp_path / "good", _TAGGED_DEBUG_SCRIPT
    )
    good_output = accepted.stdout + accepted.stderr
    assert accepted.returncode == 0, f"tagged script was refused. Output: {good_output!r}"
