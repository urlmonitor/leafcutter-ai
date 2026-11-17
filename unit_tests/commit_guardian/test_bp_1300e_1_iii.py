"""
MODULE: unit_tests/commit_guardian/test_bp_1300e_1_iii.py
COVERS: BP-1300e-1-iii -- when the linter cannot run, the commit is refused with
    the reason and how to fix it; it is never shown as passed.

The load-bearing observable is pre-commit's OWN status word for the hook: an
    exit-0 fail-open writes an honest line beneath a "Passed" banner, so every
    cannot-run arm asserts "Failed" on that banner, not only on the hook's text.
    Environments are manipulated for real (PATH, an unimportable module, a stub
    module, a git wrapper), never by patching the locator.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _bp_1300e_lint_gate_env as envmod  # noqa: E402
import _bp_1300e_lint_gate_fixture as fx  # noqa: E402


def _assert_blocked_not_passed(proc, repo, before: int) -> str:
    text = fx.out(proc)
    assert proc.returncode != 0 and fx.commit_count(repo) == before, text
    assert "RESULT: could_not_check" in text, text
    assert fx.hook_status(text, repo.stanza["name"]) == "Failed", f"pre-commit must print Failed: {text!r}"
    return text


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_iii_ruff_not_installed_refuses_with_install_instruction_and_no_passed_banner(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-iii
    # angle: failure
    """Hook interpreter cannot import ruff and PATH has no ruff executable; a clean in-scope .py is
    staged: refused, stating ruff is not installed with the install instruction, and pre-commit's
    line for the hook ends Failed. Wrong version caught: exiting 0 with a warning when ruff is missing."""
    repo, work = fx.setup(tmp_path, shared_reference_layout)
    before = fx.commit_count(repo)
    fx.stage_files(repo, {"scripts/a.py": fx.CLEAN})

    proc = fx.commit(repo, work, ruff="blocked", path="strip")

    text = _assert_blocked_not_passed(proc, repo, before)
    assert "not installed" in text.lower(), text
    assert "pip install -r requirements-dev.txt" in text, f"install instruction missing: {text!r}"
    assert not re.search(re.escape(repo.stanza["name"]) + r"[.\s]*Passed", text), text


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_iii_ruff_that_cannot_start_refuses_naming_the_startup_error(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-iii
    # angle: failure
    """A stub ruff writes 'boom: cannot start' to stderr and exits 2 before reading input: the commit
    is refused and the output contains that text."""
    repo, work = fx.setup(tmp_path, shared_reference_layout)
    before = fx.commit_count(repo)
    fx.stage_files(repo, {"scripts/a.py": fx.CLEAN})

    proc = fx.commit(repo, work, ruff="boom")

    text = _assert_blocked_not_passed(proc, repo, before)
    assert envmod.BOOM_TEXT in text, text


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_iii_malformed_ruff_config_refuses_and_never_uses_default_rules(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-iii
    # angle: discrimination
    """ruff.toml is invalid TOML and the staged file is clean under ruff's defaults: still refused as
    could_not_check naming ruff.toml as unreadable. Wrong version caught: retrying with --isolated or
    without the configuration (that retry would find nothing and let the commit through)."""
    layout = shared_reference_layout
    repo, work = fx.setup(tmp_path, layout, ruff_toml="this is = = not [valid toml\n")
    before = fx.commit_count(repo)
    fx.stage_files(repo, {"scripts/a.py": fx.CLEAN})

    proc = fx.commit(repo, work)
    direct, payload = fx.gate_json(layout, repo.root, env=fx.hook_env(work))

    text = _assert_blocked_not_passed(proc, repo, before)
    assert "ruff.toml" in text, text
    assert re.search(r"could not be read|unreadable|failed to parse", text.lower()), text
    assert "RESULT: ok" not in text, text
    assert payload["outcome"] == "could_not_check" and payload["reason"] == "ruff_config_unreadable", payload
    assert direct.returncode != 0 and payload["findings"] == [], payload


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_iii_nothing_in_scope_commits_and_says_nothing_to_inspect_even_without_ruff(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-iii
    # angle: criterion
    """Docs-only staged change, ruff absent: the commit completes; visible output contains
    RESULT: nothing_to_inspect and the 'nothing to inspect' line, never 'inspected' with a count."""
    repo, work = fx.setup(tmp_path, shared_reference_layout)
    fx.stage_files(repo, {"docs/guide.md": "# guide\n"})

    proc = fx.commit(repo, work, "docs only", ruff="blocked", path="strip")
    text = fx.out(proc)

    assert proc.returncode == 0, text
    assert "docs only" in fx.subjects(repo)
    assert "RESULT: nothing_to_inspect" in text, text
    assert "nothing to inspect" in text.lower(), text
    assert not re.search(r"inspected[^\n]*\b[1-9]\d*\b", text.lower()), text
    assert fx.hook_status(text, repo.stanza["name"]) == "Passed", text


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_iii_internal_defect_says_could_not_check_and_is_never_shown_as_passed(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-iii
    # angle: failure
    """A `git` wrapper that heads the hook's PATH (via GIT_EXEC_PATH) delegates everything to real git except
    `diff --cached`, which exits 128: output says the lint check could not check this commit and why,
    RESULT: could_not_check, and pre-commit's line for the hook is Failed, not Passed."""
    repo, work = fx.setup(tmp_path, shared_reference_layout)
    before = fx.commit_count(repo)
    fx.stage_files(repo, {"scripts/a.py": fx.CLEAN})
    wrapper = envmod.git_wrapper_dir(work, "diff", "--cached")

    proc = fx.commit(repo, work, git_wrapper=wrapper)

    text = _assert_blocked_not_passed(proc, repo, before)
    assert re.search(r"could[ _]not[ _]check", text.lower()), text
    assert "simulated failure" in text or "128" in text or "diff" in text.lower(), f"no reason given: {text!r}"


def _edit_time_hook_says_installed(layout: Path, clean_py: Path, env: dict) -> bool:
    hook = layout / ".claude" / "hooks" / "check_exception_handling_hook.py"
    assert hook.is_file(), f"{hook} is not deployed"
    payload = json.dumps({"tool_input": {"file_path": str(clean_py)}})
    proc = fx.sh([fx.PYTHON, str(hook)], clean_py.parent, env=env, stdin=payload)
    not_found = "ruff not found" in proc.stderr
    assert (proc.returncode == 2) == not_found, f"edit-time hook gave an unexpected answer: {fx.out(proc)!r}"
    return not not_found


def _gate_says_installed(layout: Path, repo, env: dict) -> bool:
    _, payload = fx.gate_json(layout, repo.root, "--mode", "files", "--files", "scripts/a.py", env=env)
    if payload.get("reason") == "ruff_not_installed":
        assert not payload.get("ruff_version"), payload
        return False
    assert payload.get("ruff_version"), f"the gate never probed a ruff version: {payload}"
    return True


@pytest.mark.shared_layout_reader
def test_bp_1300e_1_iii_edit_time_hook_and_lint_gate_agree_on_whether_ruff_is_installed(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: BP-1300e-1-iii
    # angle: seam
    """Run the DEPLOYED edit-time exception hook and the DEPLOYED lint gate as subprocesses in three
    real environments (module only; executable only; neither): both report installed in the first two
    and not installed in the third."""
    layout = shared_reference_layout
    repo, work = fx.setup(tmp_path, layout)
    clean_py = fx.write(repo.root, "scripts/a.py", fx.CLEAN)
    environments = {
        "module_only": dict(ruff="real", path="strip"),
        "executable_only": dict(ruff="blocked", path="exe_only"),
        "neither": dict(ruff="blocked", path="strip"),
    }

    observed = {}
    for name, spec in environments.items():
        env = fx.hook_env(work, **spec)
        observed[name] = (
            _edit_time_hook_says_installed(layout, clean_py, env),
            _gate_says_installed(layout, repo, env),
        )

    assert observed == {
        "module_only": (True, True),
        "executable_only": (True, True),
        "neither": (False, False),
    }, observed
