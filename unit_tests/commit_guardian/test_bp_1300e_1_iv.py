"""
MODULE: unit_tests/commit_guardian/test_bp_1300e_1_iv.py
COVERS: BP-1300e-1-iv -- the lint check judges the working copy you commit from:
    in a worktree by the worktree's own configuration and scope, and in an
    adopter's project by the adopter's own rules and declared scope.

The worktree arms only prove something when the worktree's declaration DIFFERS
    from the install location's, so the hook entry goes through a symlinked
    `.leafcutter` into the shared install outside the worktree, as in real use.
    The adopter arms run against the BUILT install in a separate fixture project.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bp_1300e_lint_gate_fixture as fx  # noqa: E402

ADOPTER_SCOPE = {"version": 1, "steps": [{"name": "adopter-rules", "paths": ["src"]}]}
BOTH = [("kernel/y.py", 30, "BLE001"), ("unit_tests/x.py", 12, "E741")]


def _worktree(main: fx.Repo, parent: Path, name: str = "wt") -> fx.Repo:
    """`git worktree add`, with the same symlinked install and an untracked hook config."""
    root = parent / name
    added = fx.git(["worktree", "add", "-q", str(root), "-b", name], main.root)
    assert added.returncode == 0, fx.out(added)
    (root / ".leafcutter").symlink_to(main.layout / ".leafcutter")
    (root / ".pre-commit-config.yaml").write_bytes((main.root / ".pre-commit-config.yaml").read_bytes())
    return fx.Repo(root, main.layout, main.stanza)


def _via_install_link(repo: fx.Repo) -> Path:
    return repo.root / ".leafcutter" / "scripts" / "commit_guardian" / "check_lint_gate.py"


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_iv_worktree_is_judged_by_its_own_declaration_not_the_install_locations(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-iv
    # angle: discrimination
    """A worktree whose staged leafcutter-lint.json adds tools/ refuses a staged tools/ violation, and
    the files inspected are the worktree's own. Wrong versions caught: resolving the declaration or
    ruff config from __file__ / the .leafcutter symlink target; using _resolve_root.find_project_root()
    with its __file__ fallback (the install's declaration does not include tools/)."""
    layout = shared_reference_layout
    main, work = fx.setup(tmp_path, layout, name="main", via_symlink=True)
    wt = _worktree(main, tmp_path)
    before = fx.commit_count(wt)
    fx.stage_files(wt, {"leafcutter-lint.json": json.dumps(fx.widened(fx.real_declaration(), "tools")),
                        "tools/v.py": fx.e741_source(9)})
    assert not (layout / "tools" / "v.py").exists()

    _, payload = fx.gate_json(layout, wt.root, env=fx.hook_env(work), script=_via_install_link(wt))
    proc = fx.commit(wt, work, "worktree change")

    assert payload["outcome"] == "refused", payload
    assert payload["files_inspected"] == ["tools/v.py"], payload
    assert fx.finding_keys(payload) == [("tools/v.py", 9, "E741")], payload["findings"]
    assert proc.returncode != 0 and fx.commit_count(wt) == before, fx.out(proc)
    assert fx.mentions_finding(fx.out(proc), "tools/v.py", 9, "E741"), fx.out(proc)
    assert fx.git(["status", "--porcelain", "--", "tools"], main.root).stdout.strip() == "", "main copy touched"


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_iv_same_content_same_verdict_in_main_copy_and_worktree(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-iv
    # angle: criterion
    """Identical staged content and configuration give the same outcome and findings in both copies."""
    layout = shared_reference_layout
    main, work = fx.setup(tmp_path, layout, name="main", via_symlink=True)
    wt = _worktree(main, tmp_path)
    content = {"unit_tests/x.py": fx.e741_source(12), "kernel/y.py": fx.ble001_source(30)}
    verdicts = {}
    for label, repo in (("main", main), ("worktree", wt)):
        fx.stage_files(repo, content)
        before = fx.commit_count(repo)
        _, payload = fx.gate_json(layout, repo.root, env=fx.hook_env(work), script=_via_install_link(repo))
        proc = fx.commit(repo, work, f"{label} change")
        assert proc.returncode != 0 and fx.commit_count(repo) == before, fx.out(proc)
        verdicts[label] = (payload["outcome"], fx.finding_keys(payload))

    assert verdicts["main"] == verdicts["worktree"] == ("refused", BOTH), verdicts


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_iv_adopter_rules_select_only_f401(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-iv
    # angle: deployed
    """Adopter project on the built install, its own ruff.toml selecting only F401 and its own
    leafcutter-lint.json: a staged E741-only file commits; a staged F401 file is refused naming
    path, line and F401."""
    repo, work = fx.setup(tmp_path, shared_reference_layout, name="adopter", declaration=ADOPTER_SCOPE,
                          ruff_toml='[lint]\nselect = ["F401"]\n', requirements=None, trees=False)
    fx.stage_files(repo, {"src/e.py": fx.e741_source(3)})

    accepted = fx.commit(repo, work, "e741 only")
    text = fx.out(accepted)
    assert accepted.returncode == 0, f"the adopter's rules do not select E741: {text!r}"
    assert "e741 only" in fx.subjects(repo)
    assert "RESULT: ok" in text and "src/e.py" in text, f"the gate must have run and inspected it: {text!r}"

    before = fx.commit_count(repo)
    fx.stage_files(repo, {"src/f.py": "VALUE = 1\nOTHER = 2\nimport os\n"})
    refused = fx.commit(repo, work, "unused import")
    assert refused.returncode != 0 and fx.commit_count(repo) == before, fx.out(refused)
    assert fx.mentions_finding(fx.out(refused), "src/f.py", 3, "F401"), fx.out(refused)


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_iv_adopter_without_declaration_gets_whole_project_minus_excludes(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-iv
    # angle: deployed
    """Adopter with no leafcutter-lint.json: a violating staged file in an arbitrary subdirectory is
    refused; one under a directory the adopter's ruff config excludes commits."""
    repo, work = fx.setup(tmp_path, shared_reference_layout, name="adopter", declaration=None,
                          ruff_toml='extend-exclude = ["vendored"]\n[lint]\nselect = ["E", "F"]\n',
                          requirements=None, trees=False)
    before = fx.commit_count(repo)
    fx.stage_files(repo, {"pkg/sub/v.py": fx.e741_source(4)})

    refused = fx.commit(repo, work, "arbitrary subdirectory")
    assert refused.returncode != 0 and fx.commit_count(repo) == before, fx.out(refused)
    assert fx.mentions_finding(fx.out(refused), "pkg/sub/v.py", 4, "E741"), fx.out(refused)

    assert fx.git(["reset", "-q"], repo.root).returncode == 0
    fx.stage_files(repo, {"vendored/w.py": fx.e741_source(4)})
    allowed = fx.commit(repo, work, "excluded directory")
    assert allowed.returncode == 0, f"the adopter's own exclude must be honoured: {fx.out(allowed)!r}"
    assert "excluded directory" in fx.subjects(repo)
    assert "RESULT:" in fx.out(allowed), "the gate must have run"


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_iv_adopter_ci_full_mode_follows_the_declaration_change(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-iv
    # angle: criterion
    """Change the adopter's declared scope: `check_lint_gate.py --mode full` from the install and the
    commit-time check both apply the new scope to the same content."""
    layout = shared_reference_layout
    repo, work = fx.setup(tmp_path, layout, name="adopter", declaration=ADOPTER_SCOPE,
                          ruff_toml='[lint]\nselect = ["E", "F"]\n', requirements=None, trees=False)
    env = fx.hook_env(work)
    fx.stage_files(repo, {"lib/v.py": fx.e741_source(4)})
    narrow_staged, _ = fx.gate_json(layout, repo.root, env=env)
    narrow_full, _ = fx.gate_json(layout, repo.root, "--mode", "full", env=env)
    assert narrow_staged.returncode == 0 and narrow_full.returncode == 0, "lib/ is not yet in scope"

    widened = fx.widened(ADOPTER_SCOPE, "lib")
    fx.stage_files(repo, {"leafcutter-lint.json": json.dumps(widened)})
    before = fx.commit_count(repo)
    staged, staged_payload = fx.gate_json(layout, repo.root, env=env)
    full, full_payload = fx.gate_json(layout, repo.root, "--mode", "full", env=env)
    commit = fx.commit(repo, work, "widen scope")

    assert staged.returncode != 0 and full.returncode != 0
    assert fx.finding_keys(staged_payload) == fx.finding_keys(full_payload) == [("lib/v.py", 4, "E741")]
    assert commit.returncode != 0 and fx.commit_count(repo) == before, fx.out(commit)
    assert fx.mentions_finding(fx.out(commit), "lib/v.py", 4, "E741"), fx.out(commit)


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_iv_non_repository_with_empty_git_dir_is_could_not_check(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-iv
    # angle: failure
    """Run the deployed gate with cwd at a directory that is NOT a repository but holds an empty .git/
    and a CLAUDE.md (the KI-CG-20260925 reproduction): non-zero, RESULT: could_not_check, no_repository."""
    layout = shared_reference_layout
    not_a_repo = tmp_path / "notrepo"
    (not_a_repo / ".git").mkdir(parents=True)
    (not_a_repo / "CLAUDE.md").write_text("# not a repository\n", encoding="utf-8")
    work = tmp_path / "work"
    work.mkdir()
    env = {**fx.hook_env(work), "GIT_CEILING_DIRECTORIES": str(tmp_path)}

    proc, payload = fx.gate_json(layout, not_a_repo, env=env)
    human = fx.run_gate(layout, not_a_repo, env=env)

    assert proc.returncode != 0 and human.returncode != 0, "must never exit 0 outside a repository"
    assert payload["outcome"] == "could_not_check" and payload["reason"] == "no_repository", payload
    assert "RESULT: could_not_check" in fx.out(human), fx.out(human)


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_iv_config_above_the_project_is_could_not_check(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-iv
    # angle: boundary
    """A project with no ruff config of its own, nested inside a directory holding a ruff.toml: a staged
    in-scope file yields could_not_check naming the outer ruff.toml as outside the project."""
    layout = shared_reference_layout
    repo, work = fx.setup(tmp_path, layout, name="outer/proj", declaration=None, ruff_toml=None,
                          requirements=None, trees=False, files={"pkg/__init__.py": ""})
    (tmp_path / "outer" / "ruff.toml").write_text('[lint]\nselect = ["E", "F"]\n', encoding="utf-8")
    before = fx.commit_count(repo)
    fx.stage_files(repo, {"pkg/a.py": fx.CLEAN})

    _, payload = fx.gate_json(layout, repo.root, env=fx.hook_env(work))
    proc = fx.commit(repo, work, "nested project")
    text = fx.out(proc)

    assert payload["outcome"] == "could_not_check", payload
    assert payload["reason"] == "ruff_config_outside_project", payload
    assert proc.returncode != 0 and fx.commit_count(repo) == before, text
    assert "RESULT: could_not_check" in text and "ruff.toml" in text and "outside" in text.lower(), text
