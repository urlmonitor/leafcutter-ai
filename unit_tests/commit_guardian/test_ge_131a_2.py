"""
MODULE: unit_tests/commit_guardian/test_ge_131a_2.py
COVERS: GE-131a-2 -- the complexity check is registered on the ordinary commit
    path, lets existing offenders through, and is shown refusing a grown and a
    new function through a real commit with a refusal that says what to do.

GOAL: Behavioural proof through a REAL ``git commit``. The scratch repo is wired
    by a real ``pre-commit install``; the ``check-complexity`` stanza is copied
    from the ``.pre-commit-config.yaml`` that build.py generated into the shared
    deployed layout (never hand-typed), with only the script path tokens
    re-pointed at that layout's deployed scripts. Running the DEPLOYED scripts
    also proves the ratchet helper is deployed beside the check.

    Evidence is the hook-run status line pre-commit prints per hook, the commit's
    exit code, and whether HEAD moved -- never manifest text.

MARKERS: the layout is only READ, so tests are ``shared_layout_reader``; no
    private build.py is spawned.

REACHABILITY ENTRY POINT (resolved, BP-1100g-2 Step 1.2): the registered
    pre-commit hook -- ``git commit`` -> pre-commit -> generated stanza ->
    deployed run_hook.py -> deployed check_complexity.py.

SCORING: a generated function with N-1 independent ``if`` statements scores N
    under the shipped counting rule (base 1, +1 per ``if``).

The 'smaller by exactly one' half of arm 4 is the EXISTING
    test_no_unregistered_hook_scripts_beyond_baseline in
    test_hook_registration_inventory.py, whose UNREGISTERED_BASELINE no longer
    lists check_complexity.py (it goes red until the entry is registered).

DECISION HISTORY
- 2026-10-09 [GE-131a-2/test-writer]: Initial RED authoring, one test per arm
    plus a reachability test through the real commit path.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARDIAN_DIR = REPO_ROOT / "templates" / "scripts" / "commit_guardian"
HOOK_ID = "check-complexity"
HOOK_TIMEOUT = 180
GIT_TIMEOUT = 60
ENV = {**os.environ, "COMMIT_AGENT_MODE": "1"}


def _git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=GIT_TIMEOUT, check=check
    )


def _func(name: str, score: int) -> str:
    """Source for a function whose complexity score is exactly *score*."""
    body = "".join(f"    if x == {i}:\n        pass\n" for i in range(score - 1))
    return f"def {name}(x):\n{body}    return x\n"


def _module(**scores: int) -> str:
    return "\n\n".join(_func(name, score) for name, score in scores.items())


def _generated_hooks(layout: Path) -> dict[str, dict]:
    config = yaml.safe_load((layout / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    return {h["id"]: h for repo in config["repos"] for h in repo["hooks"]}


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


def _scratch_repo(layout: Path, root: Path, baseline: dict[str, str]) -> tuple[Path, dict]:
    """Real git repo holding *baseline* as its committed history, with the one
    generated check-complexity stanza installed as the pre-commit hook."""
    hooks = _generated_hooks(layout)
    assert HOOK_ID in hooks, (
        f"the generated .pre-commit-config.yaml has no {HOOK_ID} stanza; the check "
        f"is not registered in the package's default hook list. Has: {sorted(hooks)[:5]}..."
    )
    stanza = dict(hooks[HOOK_ID])
    assert "check_complexity.py" in stanza["entry"], f"stanza never runs the check: {stanza['entry']!r}"
    stanza["entry"] = _point_at_deployed(stanza["entry"], layout)

    root.mkdir(parents=True)
    _git(["init", "-q", "-b", "main"], root)
    _git(["config", "user.email", "ge131a2@example.com"], root)
    _git(["config", "user.name", "GE-131a-2 fixture"], root)
    for rel, text in baseline.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    _git(["add", "-A"], root)
    _git(["commit", "-q", "--no-verify", "-m", "baseline"], root)

    (root / ".pre-commit-config.yaml").write_text(
        yaml.safe_dump({"repos": [{"repo": "local", "hooks": [stanza]}]}), encoding="utf-8"
    )
    done = subprocess.run(
        ["pre-commit", "install", "--hook-type", "pre-commit"],
        cwd=str(root), capture_output=True, text=True, timeout=GIT_TIMEOUT, check=False,
    )
    assert done.returncode == 0, f"pre-commit install: {done.stdout}{done.stderr}"
    return root, stanza


def _head(root: Path) -> str:
    return _git(["rev-parse", "HEAD"], root).stdout.strip()


def _ordinary_commit(root: Path, message: str) -> subprocess.CompletedProcess:
    """A plain ``git commit -m`` -- nothing invoked by hand."""
    return subprocess.run(
        ["git", "commit", "-m", message], cwd=str(root), capture_output=True, text=True,
        timeout=HOOK_TIMEOUT, check=False, env=ENV,
    )


def _status(output: str, name: str, verdict: str) -> bool:
    return re.search(re.escape(name) + r"[.\s]*" + verdict, output) is not None


def _lines_naming(output: str, name: str) -> list[str]:
    pattern = re.compile(r"(?<![\w.])" + re.escape(name) + r"(?![\w])")
    return [line for line in output.splitlines() if pattern.search(line)]


def _has_number(text: str, number: int) -> bool:
    return re.search(rf"(?<!\d){number}(?!\d)", text) is not None


def _score_of(source: str, function: str) -> int:
    """Measure a function with the shipped counting rule (never hard-coded)."""
    spec = importlib.util.spec_from_file_location("_ge131a2_cc", GUARDIAN_DIR / "check_complexity.py")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(GUARDIAN_DIR))  # the check imports its sibling helpers
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(GUARDIAN_DIR))
    scores = dict(module.calculate_complexities(source))
    assert function in scores, f"{function} not found; saw {sorted(scores)[:5]}"
    return scores[function]


@pytest.mark.shared_layout_reader
def test_ge131a2_real_offender_file_commits_through_registered_check(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: GE-131a-2
    # angle: real_artifact
    """Arm 1. The baseline holds the REAL tracked scripts/build_helpers.py, whose
    _compute_output_mappings is measured over the limit at test time. Staging
    one appended comment line: pre-commit shows the check Passed and HEAD
    advances.

    Must implement: a check-complexity stanza in hooks_manifest.hooks (RED
    TODAY: no stanza), carrying the GE-131a-1 ratchet.
    """
    real = (REPO_ROOT / "scripts" / "build_helpers.py").read_text(encoding="utf-8")
    offender_score = _score_of(real, "_compute_output_mappings")
    limit = 15
    assert offender_score > limit, f"fixture is not an offender any more: {offender_score}"

    repo, stanza = _scratch_repo(shared_reference_layout, tmp_path / "arm1", {"scripts/build_helpers.py": real})
    before = _head(repo)
    (repo / "scripts" / "build_helpers.py").write_text(real + "\n# one appended comment line\n", encoding="utf-8")
    _git(["add", "scripts/build_helpers.py"], repo)

    commit = _ordinary_commit(repo, "touch an existing offender file")
    output = commit.stdout + commit.stderr

    assert _status(output, stanza["name"], "Passed"), f"check did not run and pass on the commit: {output!r}"
    assert commit.returncode == 0, f"existing offender file was refused: {output!r}"
    assert _head(repo) != before, "HEAD did not advance"


def _refusal_case(layout: Path, root: Path, baseline: dict[str, str], staged: dict[str, str]):
    repo, stanza = _scratch_repo(layout, root, baseline)
    before = _head(repo)
    for rel, text in staged.items():
        (repo / rel).write_text(text, encoding="utf-8")
        _git(["add", rel], repo)
    commit = _ordinary_commit(repo, "change a function")
    return repo, stanza, before, commit


@pytest.mark.shared_layout_reader
def test_ge131a2_commit_refuses_grown_function_with_actionable_message(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: GE-131a-2
    # angle: failure
    """Arm 2. plan_batches 30 -> 31: the commit fails and HEAD does not move.
    Output names scripts/planner.py, plan_batches, 31, ceiling 30 (not 15),
    'grew', the complexity-reduction skill and SKIP=check-complexity.

    Wrong versions this catches: a registered copy that never refuses an
    existing offender (blanket exemption), a refusal that states the ceiling as
    15, and a refusal that omits the move/rename escape hatch.
    """
    repo, stanza, before, commit = _refusal_case(
        shared_reference_layout, tmp_path / "arm2",
        {"scripts/planner.py": _module(plan_batches=30)},
        {"scripts/planner.py": _module(plan_batches=31)},
    )
    output = commit.stdout + commit.stderr

    assert commit.returncode != 0, f"grown function was committed: {output!r}"
    assert _head(repo) == before, "HEAD moved on a refused commit"
    assert _status(output, stanza["name"], "Failed"), f"check not shown Failed: {output!r}"
    assert "scripts/planner.py" in output, output
    named = _lines_naming(output, "plan_batches")
    assert named, f"plan_batches not named: {output!r}"
    line = "\n".join(named)
    assert _has_number(line, 31), f"score 31 not stated: {output!r}"
    assert _has_number(line, 30), f"ceiling 30 not stated: {output!r}"
    assert not _has_number(line, 15), f"ceiling stated as the plain limit 15: {output!r}"
    assert re.search(r"\bgrew\b", output), f"reason 'grew' missing: {output!r}"
    assert "complexity-reduction" in output, f"skill not named: {output!r}"
    assert "SKIP=check-complexity" in output, f"move/rename escape hatch not stated: {output!r}"


@pytest.mark.shared_layout_reader
def test_ge131a2_commit_refuses_new_function_over_limit(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: GE-131a-2
    # angle: failure
    """Arm 3. A new parse_rules scoring 16: the commit fails and HEAD does not
    move. Output names the file, parse_rules, 16, ceiling 15, 'new' and the
    complexity-reduction skill. Control in the same test: a new function scoring
    exactly 15 commits, so the refusal is caused by the score and not the setup.
    """
    baseline = {"scripts/planner.py": _module(load_rules=12)}
    repo, stanza, before, commit = _refusal_case(
        shared_reference_layout, tmp_path / "arm3", baseline,
        {"scripts/planner.py": _module(load_rules=12, parse_rules=16)},
    )
    output = commit.stdout + commit.stderr

    assert commit.returncode != 0, f"new over-limit function was committed: {output!r}"
    assert _head(repo) == before, "HEAD moved on a refused commit"
    assert _status(output, stanza["name"], "Failed"), f"check not shown Failed: {output!r}"
    assert "scripts/planner.py" in output, output
    named = _lines_naming(output, "parse_rules")
    assert named, f"parse_rules not named: {output!r}"
    line = "\n".join(named)
    assert _has_number(line, 16), f"score 16 not stated: {output!r}"
    assert _has_number(line, 15), f"ceiling 15 not stated: {output!r}"
    assert re.search(r"\bnew\b", output, re.IGNORECASE), f"reason 'new' missing: {output!r}"
    assert "complexity-reduction" in output, f"skill not named: {output!r}"

    # Control row: the same new function at exactly the limit is accepted.
    (repo / "scripts" / "planner.py").write_text(_module(load_rules=12, parse_rules=15), encoding="utf-8")
    _git(["add", "scripts/planner.py"], repo)
    ok = _ordinary_commit(repo, "new function at the limit")
    assert ok.returncode == 0, f"new function at the limit was refused: {ok.stdout + ok.stderr!r}"
    assert _head(repo) != before


@pytest.mark.shared_layout_reader
def test_ge_131a_2_reachable_from_entry_point(
    shared_reference_layout: Path, tmp_path: Path
) -> None:
    # covers: GE-131a-2
    # angle: reachability
    """Entry point: the registered pre-commit hook. An ordinary ``git commit``
    (nothing invoked by hand) fires the generated stanza through the deployed
    run_hook.py, the check runs (its own status line appears), and its verdict
    is consumed: the commit is blocked and HEAD does not move."""
    repo, stanza, before, commit = _refusal_case(
        shared_reference_layout, tmp_path / "reach",
        {"scripts/planner.py": _module(plan_batches=30)},
        {"scripts/planner.py": _module(plan_batches=31)},
    )
    output = commit.stdout + commit.stderr

    assert "run_hook.py" in stanza["entry"], f"stanza does not use the hook runner: {stanza['entry']!r}"
    assert stanza["name"] in output, f"the registered hook never ran on the commit: {output!r}"
    assert commit.returncode != 0 and _head(repo) == before, f"verdict not consumed: {output!r}"


def test_ge131a2_reachability_census_no_longer_declares_check_withheld(tmp_path: Path) -> None:
    # covers: GE-131a-2
    # angle: seam
    """Arm 4, registration-data half. The REAL reachability census (the existing
    consumer of the exemption registry and the hooks manifest), run as a
    subprocess through run_hook.py over a copy of the real guardian directory,
    prints neither 'DECLARED-NON-GATE: check_complexity.py' nor 'REDUNDANT
    NON-GATE RECORD: check_complexity.py', and the script is not UNREFERENCED.

    RED TODAY: the exemption registry still declares it withheld. Control: the
    census did run (it printed its RESULT line) over a registry that still
    declares other scripts, so silence is not an empty run.
    """
    repo = tmp_path / "census"
    repo.mkdir()
    _git(["init", "-q", "-b", "main"], repo)
    _git(["config", "user.email", "ge131a2@example.com"], repo)
    _git(["config", "user.name", "GE-131a-2 fixture"], repo)
    gate_dir = repo / "commit_guardian_copy"
    shutil.copytree(GUARDIAN_DIR, gate_dir, ignore=shutil.ignore_patterns("__pycache__"))
    _git(["add", "-A"], repo)
    _git(["commit", "-q", "--no-verify", "-m", "copy of the real guardian directory"], repo)

    result = subprocess.run(
        [sys.executable, str(gate_dir / "run_hook.py"), str(gate_dir / "check_hook_trigger_reachability.py")],
        cwd=str(repo), capture_output=True, text=True, timeout=GIT_TIMEOUT, check=False,
    )
    output = result.stdout + result.stderr

    assert re.search(r"check-hook-trigger-reachability:\s*RESULT", output), f"census did not run: {output!r}"
    assert re.search(r"DECLARED-NON-GATE:", output), f"control: no other declared script seen: {output!r}"
    assert not re.search(r"DECLARED-NON-GATE:\s*\S*check_complexity\.py", output), (
        f"check_complexity.py is still declared withheld: {output!r}"
    )
    assert "REDUNDANT NON-GATE RECORD: check_complexity.py" not in output, output
    assert not re.search(r"UNREFERENCED[^\n]*check_complexity\.py", output), output
