"""
MODULE: unit_tests/commit_guardian/test_bp_1300e_1_v.py
COVERS: BP-1300e-1-v -- a linter whose version differs from the one CI installs
    refuses the commit, naming both versions; a verdict from a different linter
    is never shown as passed.

Versions other than the real 0.15.15 come from a STUB `ruff` module on the hook
    interpreter's path that answers `--version` and delegates everything else to
    the real linter: the environment is manipulated for real and the
    module-first discovery path runs exactly as in use. The commit-path tests
    assert on pre-commit's own status word as well as the hook's text.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bp_1300e_lint_gate_fixture as fx  # noqa: E402

PIN = "0.15.15"
MISMATCH = "linter_version_mismatch"


def _load_fixture(name: str):
    spec = importlib.util.spec_from_file_location("_bp_1300e_tests_conftest", fx.REPO_ROOT / "tests" / "conftest.py")
    assert spec is not None and spec.loader is not None, "tests/conftest.py could not be loaded"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.load_fixture(name)


def _clean_staged(tmp_path: Path, layout: Path, **kwargs):
    repo, work = fx.setup(tmp_path, layout, **kwargs)
    fx.stage_files(repo, {"scripts/a.py": fx.CLEAN})
    return repo, work


def _mismatch_refusal(repo, work, local: str, required: str) -> str:
    before = fx.commit_count(repo)
    proc = fx.commit(repo, work, ruff=f"stub:{local}")
    text = fx.out(proc)
    assert proc.returncode != 0 and fx.commit_count(repo) == before, text
    assert local in text and required in text, f"both versions must be named: {text!r}"
    assert "RESULT: could_not_check" in text, text
    assert fx.hook_status(text, repo.stanza["name"]) == "Failed", text
    return text


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_v_older_ruff_refuses_clean_commit_naming_both_versions_and_install_command(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-v
    # angle: criterion
    """Stub ruff reports 0.15.14, fixture pin is 0.15.15, a clean in-scope .py is staged: refused,
    both versions named, an install command pinning ruff==0.15.15, RESULT: could_not_check with reason
    linter_version_mismatch, hook line Failed. Wrong versions: warns but exits 0; install hint unpinned."""
    layout = shared_reference_layout
    repo, work = _clean_staged(tmp_path, layout)

    text = _mismatch_refusal(repo, work, "0.15.14", PIN)

    assert re.search(r"-m pip install ruff==0\.15\.15\b", text), f"install command must pin the version: {text!r}"
    assert not re.search(re.escape(repo.stanza["name"]) + r"[.\s]*Passed", text), text
    proc, payload = fx.gate_json(layout, repo.root, env=fx.hook_env(work, ruff="stub:0.15.14"))
    assert proc.returncode != 0 and payload["outcome"] == "could_not_check" and payload["reason"] == MISMATCH, payload


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_v_mismatch_with_e741_presents_no_finding(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-v
    # angle: discrimination
    """Same 0.15.14 stub; the staged file carries E741 at line 12: refused for the version mismatch,
    output has neither 'E741' nor ':12:', and --json findings is []. Wrong version caught: running
    ruff under the mismatched version and listing its findings beside the mismatch."""
    layout = shared_reference_layout
    repo, work = fx.setup(tmp_path, layout)
    fx.stage_files(repo, {"scripts/e.py": fx.e741_source(12)})

    text = _mismatch_refusal(repo, work, "0.15.14", PIN)
    proc, payload = fx.gate_json(layout, repo.root, env=fx.hook_env(work, ruff="stub:0.15.14"))

    assert "E741" not in text and ":12:" not in text, f"no finding may be presented: {text!r}"
    assert payload["findings"] == [] and payload["reason"] == MISMATCH, payload


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_v_newer_patch_version_is_refused(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: BP-1300e-1-v
    # angle: boundary
    """Stub reports 0.15.16, a clean in-scope file is staged: refused naming 0.15.16 and 0.15.15.
    Wrong versions caught: accepting any version >= the pin; comparing major.minor only."""
    repo, work = _clean_staged(tmp_path, shared_reference_layout)

    _mismatch_refusal(repo, work, "0.15.16", PIN)


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_v_matching_version_commits_and_names_it(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: BP-1300e-1-v
    # angle: criterion
    """Stub reports 0.15.15 and the fixture pin is 0.15.15: a clean staged file commits, the output
    names 0.15.15 as the version used, and --json version_check is 'matched'."""
    layout = shared_reference_layout
    repo, work = _clean_staged(tmp_path, layout)
    _, payload = fx.gate_json(layout, repo.root, env=fx.hook_env(work))

    proc = fx.commit(repo, work, "matching version")
    text = fx.out(proc)

    assert payload["version_check"] == "matched" and payload["ruff_version"] == PIN, payload
    assert payload["required_ruff_version"] == PIN and payload["version_source"] == "requirements-dev.txt", payload
    assert proc.returncode == 0 and "matching version" in fx.subjects(repo), text
    assert PIN in text and "RESULT: ok" in text, f"the version used must be named: {text!r}"
    assert fx.hook_status(text, repo.stanza["name"]) == "Passed", text


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_v_changing_only_the_ci_install_file_moves_the_required_version(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-v
    # angle: criterion
    """Edit ONLY requirements-dev.txt from 0.15.15 to 0.15.16 and stage it (plus one clean in-scope file):
    stub 0.15.15 is refused naming 0.15.15 local and 0.15.16 required; stub 0.15.16 completes; no other
    fixture file changes between the runs. Wrong version caught: a second copy of the version string."""
    layout = shared_reference_layout
    repo, work = fx.setup(tmp_path, layout)
    fx.stage_files(repo, {"requirements-dev.txt": "ruff==0.15.16\n", "scripts/a.py": fx.CLEAN})
    others = ("ruff.toml", "leafcutter-lint.json", ".pre-commit-config.yaml", "scripts/a.py")
    snapshot = lambda: {rel: (repo.root / rel).read_bytes() for rel in others}  # noqa: E731
    declaration_text = (repo.root / "leafcutter-lint.json").read_text(encoding="utf-8")
    assert "0.15" not in declaration_text, "the declaration may carry a version SOURCE path, never a version"

    refused = _mismatch_refusal(repo, work, PIN, "0.15.16")
    after_refusal = snapshot()
    allowed = fx.commit(repo, work, "bump pin", ruff="stub:0.15.16")

    assert allowed.returncode == 0 and "bump pin" in fx.subjects(repo), fx.out(allowed)
    assert snapshot() == after_refusal, "only requirements-dev.txt may differ between the two runs"
    assert "RESULT: ok" in fx.out(allowed) and "0.15.16" in fx.out(allowed), (refused, fx.out(allowed))


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_v_nothing_in_scope_commits_without_consulting_version(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-v
    # angle: criterion
    """Stub reports 0.15.14; a docs-only change commits with RESULT: nothing_to_inspect, no version
    mismatch text and no 'inspected <N>' with N > 0."""
    repo, work = fx.setup(tmp_path, shared_reference_layout)
    fx.stage_files(repo, {"docs/guide.md": "# guide\n"})

    proc = fx.commit(repo, work, "docs only", ruff="stub:0.15.14")
    text = fx.out(proc)

    assert proc.returncode == 0 and "docs only" in fx.subjects(repo), text
    assert "RESULT: nothing_to_inspect" in text, text
    lowered = text.lower()
    assert MISMATCH not in lowered and "differs" not in lowered and "0.15.14" not in text, text
    assert not re.search(r"inspected[^\n]*\b[1-9]\d*\b", lowered), text


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_v_adopter_pin_governs_not_the_packages(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: BP-1300e-1-v
    # angle: deployed
    """Adopter on the shared deployed layout, requirements-dev.txt pinning ruff==0.14.2 and no
    linter_version_source key; stub reports 0.15.15 (this package's own pin): refused naming 0.15.15 local
    and 0.14.2 as the project's declared version. Wrong version caught: reading the package's own
    requirements or a version baked into the deployed script (it would accept 0.15.15)."""
    layout = shared_reference_layout
    repo, work = fx.setup(tmp_path, layout, name="adopter", declaration=None, trees=False,
                          ruff_toml='[lint]\nselect = ["E", "F"]\n', requirements="ruff==0.14.2\n")
    fx.stage_files(repo, {"src/a.py": fx.CLEAN})

    text = _mismatch_refusal(repo, work, PIN, "0.14.2")
    _, payload = fx.gate_json(layout, repo.root, env=fx.hook_env(work))

    assert payload["required_ruff_version"] == "0.14.2" and payload["ruff_version"] == PIN, payload
    assert payload["reason"] == MISMATCH and payload["version_source"] == "requirements-dev.txt", (payload, text)


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_v_adopter_without_exact_pin_is_told_no_version_check_applied(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-v
    # angle: deployed
    """Two adopter fixtures on the deployed layout -- (a) no requirements-dev.txt, (b) ruff>=0.15; stub
    reports 0.15.15: a clean staged file commits in both; the output states no exact linter version is
    declared so no version check was applied, names 0.15.15, and --json version_check is 'not_declared'."""
    layout = shared_reference_layout
    for name, requirements in (("no-requirements-file", None), ("range-only", "ruff>=0.15\n")):
        repo, work = fx.setup(tmp_path / name, layout, name="adopter", declaration=None, trees=False,
                              ruff_toml='[lint]\nselect = ["E", "F"]\n', requirements=requirements)
        fx.stage_files(repo, {"src/a.py": fx.CLEAN})
        _, payload = fx.gate_json(layout, repo.root, env=fx.hook_env(work))

        proc = fx.commit(repo, work, "no exact pin")
        text = " ".join(fx.out(proc).lower().split())

        assert payload["version_check"] == "not_declared" and payload["outcome"] == "ok", (name, payload)
        assert proc.returncode == 0 and "no exact pin" in fx.subjects(repo), (name, text)
        assert "no exact linter version is declared" in text, (name, text)
        assert "no version check was applied" in text and PIN in text, (name, text)


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_v_declared_but_missing_version_source_is_could_not_check(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-v
    # angle: failure
    """leafcutter-lint.json sets linter_version_source to tools/missing.txt, which does not exist; a staged
    in-scope file is refused as could_not_check, linter_version_source_unreadable, naming tools/missing.txt.
    Wrong version caught: treating an explicitly declared but missing source as 'no version declared'."""
    layout = shared_reference_layout
    declaration = {**fx.real_declaration(), "linter_version_source": "tools/missing.txt"}
    repo, work = _clean_staged(tmp_path, layout, declaration=declaration)
    before = fx.commit_count(repo)

    proc = fx.commit(repo, work)
    _, payload = fx.gate_json(layout, repo.root, env=fx.hook_env(work))

    assert proc.returncode != 0 and fx.commit_count(repo) == before, fx.out(proc)
    assert "tools/missing.txt" in fx.out(proc) and "RESULT: could_not_check" in fx.out(proc), fx.out(proc)
    assert payload["outcome"] == "could_not_check" and payload["reason"] == "linter_version_source_unreadable", payload


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_v_requirements_parser_exactness_table(shared_reference_layout: Path, tmp_path: Path) -> None:
    # covers: BP-1300e-1-v
    # angle: boundary
    """What counts as an exact pin, observed through `--mode files --json` over a table of requirements
    files (rows live in tests/fixtures/bp_1300e_1_v/requirements_exactness_table.json)."""
    layout = shared_reference_layout
    rows = _load_fixture("bp_1300e_1_v/requirements_exactness_table")
    work = tmp_path / "work"
    work.mkdir()
    wrong = []
    for index, row in enumerate(rows):
        repo = fx.make_repo(tmp_path / f"row{index}", layout, requirements=row["requirements"], install=False,
                            files={"scripts/a.py": fx.CLEAN, **row["extra_files"]})
        _, payload = fx.gate_json(layout, repo.root, "--mode", "files", "--files", "scripts/a.py",
                                  env=fx.hook_env(work))
        want = {k: v for k, v in row.items() if k in ("outcome", "version_check", "reason")}
        got = {k: payload.get(k) for k in want}
        if got != want:
            wrong.append((row["label"], want, got))

    assert len(rows) == 10 and not wrong, wrong


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_v_staged_pin_bump_is_judged_from_the_index(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-v
    # angle: discrimination
    """The index holds requirements-dev.txt pinning 0.15.15 while the unstaged working copy says 0.15.16;
    local ruff is 0.15.15 and a clean file is staged: the commit completes. Wrong version caught: reading
    the version source from the working tree in staged mode. (Gate run directly as well: pre-commit stashes
    the unstaged edit, which would hide the difference from a plain commit.)"""
    layout = shared_reference_layout
    repo, work = _clean_staged(tmp_path, layout)
    fx.write(repo.root, "requirements-dev.txt", "ruff==0.15.16\n")  # unstaged

    proc, payload = fx.gate_json(layout, repo.root, env=fx.hook_env(work))
    commit = fx.commit(repo, work, "index pin")

    assert payload["required_ruff_version"] == PIN and payload["version_check"] == "matched", payload
    assert proc.returncode == 0 and payload["outcome"] == "ok", payload
    assert commit.returncode == 0 and "index pin" in fx.subjects(repo), fx.out(commit)


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_v_files_and_full_modes_apply_the_same_check(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-v
    # angle: reachability
    """`--mode files --json` (BO-570-3's contract) and `--mode full` (run_ci_local.py and CI): with the 0.15.14
    stub both report could_not_check, linter_version_mismatch, required 0.15.15, exit non-zero, no findings;
    with a 0.15.15 stub both report version_check 'matched'."""
    layout = shared_reference_layout
    repo, work = fx.setup(tmp_path, layout, files={"scripts/a.py": fx.CLEAN})
    modes = {"files": ("--mode", "files", "--files", "scripts/a.py"), "full": ("--mode", "full")}

    for name, args in modes.items():
        proc, payload = fx.gate_json(layout, repo.root, *args, env=fx.hook_env(work, ruff="stub:0.15.14"))
        assert proc.returncode != 0 and payload["outcome"] == "could_not_check", (name, payload)
        assert payload["reason"] == MISMATCH and payload["required_ruff_version"] == PIN, (name, payload)
        assert payload["findings"] == [], (name, payload)
        proc, payload = fx.gate_json(layout, repo.root, *args, env=fx.hook_env(work))
        assert proc.returncode == 0 and payload["version_check"] == "matched", (name, payload)


def test_bp_1300e_1_v_ci_lint_job_installs_from_the_declared_version_source_only() -> None:
    # covers: BP-1300e-1-v
    # angle: seam
    """Parse the REAL .github/workflows/ci.yml and the REAL leafcutter-lint.json: the lint job's install
    step is `pip install -r <F>` with <F> equal to the resolved version source; the gate step follows it
    in the same job; no lint-job step installs ruff any other way and 'ruff==' appears nowhere in ci.yml."""
    declaration = fx.real_declaration()
    source = declaration.get("linter_version_source", "requirements-dev.txt")
    ci_text = (fx.REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    steps = yaml.safe_load(ci_text)["jobs"]["lint"]["steps"]
    runs = [str(step.get("run", "")) for step in steps]

    installs = [i for i, run in enumerate(runs) if "pip install" in run]
    gates = [i for i, run in enumerate(runs) if "check_lint_gate.py" in run]
    declared = [i for i in installs if re.search(rf"pip install -r {re.escape(source)}(\s|$)", runs[i])]

    assert source == "requirements-dev.txt", f"this repository installs CI's linter from requirements-dev.txt: {source}"
    assert len(declared) == 1 and installs == declared, f"only the declared source may be installed from: {runs}"
    assert len(gates) == 1 and gates[0] > declared[0], f"the gate step must follow the install step: {runs}"
    assert "--mode full" in runs[gates[0]], runs[gates[0]]
    assert not any(re.search(r"\bruff\b", runs[i]) for i in installs), "no step may install ruff directly"
    assert "ruff==" not in ci_text, "ci.yml must carry no version string of its own"
    assert json.dumps(declaration).count("0.15") == 0, "the declaration holds a path, never a version"
