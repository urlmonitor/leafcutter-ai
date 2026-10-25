"""
MODULE: _acd300g2_support
GOAL: Shared real-artifact fixtures + a driver for the ACD-300g-2 / -2-i / -2-ii
    stage-commit tests (test_acd_300g_2*.py).
BUSINESS CONTEXT: plan-feature.js's commitStageOutput() hands a `commit` agent a
    prompt that decides which AC files a stage commit stages. These helpers build
    the REAL on-disk situation that prompt must handle (a real git repository, AC
    YAML written by yaml.safe_dump, a real porcelain status) and drive the REAL
    commitStageOutput() to capture the prompt it produces.
ARCHITECTURE: git via subprocess; commitStageOutput() driven through
    unit_tests/_plan_feature_e2_runner.run_isolated_e2.
"""
from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import yaml

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_REPO_ROOT / "unit_tests") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "unit_tests"))

from unit_tests._plan_feature_e2_runner import run_isolated_e2  # noqa: E402

AC_STORE = "docs/acceptance-criteria"
HOOK_SCRIPT = _REPO_ROOT / "scripts" / "commit_guardian" / "check_ac_parent_covered_by.py"


def git(repo: Path, *args: str) -> str:
    done = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return done.stdout


def _ac(ac_id: str, covered_by=None, depends_on=None, level="L2") -> dict:
    return {
        "id": ac_id,
        "level": level,
        "readiness": "draft",
        "origin_agent": "business-analyst-v3",
        "criteria": "Given x\nWhen y\nThen z\n",
        "depends_on": list(depends_on or []),
        "covered_by": list(covered_by or []),
    }


def write_ac(repo: Path, ac: dict) -> Path:
    path = repo / AC_STORE / "build-orchestration" / f"{ac['id']}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(ac, sort_keys=False), encoding="utf-8")
    return path


def make_parent_covered_by_repo(tmp: Path) -> dict:
    """Real repo reproducing ACD-300g-2-ii's Given: child BO-2600a-6 new, parent
    BO-2600a edited on disk (covered_by += child), sibling BO-2600a-5 untouched,
    config/commit_guardian.json modified outside the AC store. An earlier stage's
    file (BO-2600a-0) is already committed.
    """
    repo = tmp / "repo"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "ac-authoring/x")
    git(repo, "config", "user.email", "t@example.com")
    git(repo, "config", "user.name", "t")
    (repo / "config").mkdir()
    (repo / "config" / "commit_guardian.json").write_text('{"a": 1}\n', encoding="utf-8")
    write_ac(repo, _ac("BO-2600a", covered_by=["BO-2600a-0", "BO-2600a-5"], level="L1"))
    write_ac(repo, _ac("BO-2600a-0", depends_on=["BO-2600a"]))
    write_ac(repo, _ac("BO-2600a-5", depends_on=["BO-2600a"]))
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "baseline")
    # the stage's work on disk
    write_ac(repo, _ac("BO-2600a-6", depends_on=["BO-2600a"]))
    write_ac(
        repo,
        _ac("BO-2600a", covered_by=["BO-2600a-0", "BO-2600a-5", "BO-2600a-6"], level="L1"),
    )
    (repo / "config" / "commit_guardian.json").write_text('{"a": 2}\n', encoding="utf-8")
    return {
        "repo": repo,
        "child": f"{AC_STORE}/build-orchestration/BO-2600a-6.yaml",
        "parent": f"{AC_STORE}/build-orchestration/BO-2600a.yaml",
        "sibling": f"{AC_STORE}/build-orchestration/BO-2600a-5.yaml",
        "previous_stage": f"{AC_STORE}/build-orchestration/BO-2600a-0.yaml",
        "outside": "config/commit_guardian.json",
    }


def porcelain(repo: Path) -> dict:
    out = git(repo, "status", "--porcelain", "--untracked-files=all")
    return {line[3:]: line[:2] for line in out.splitlines() if line.strip()}


def run_parent_hook_on_staged(repo: Path, staged_paths: list[str]) -> subprocess.CompletedProcess:
    """Stage exactly `staged_paths`, then run the REAL check-ac-parent-covered-by
    hook the way pre-commit does: unstaged edits are stashed away (--keep-index)
    so the hook sees only what the commit would contain. Restores the tree after.
    """
    git(repo, "add", "--", *staged_paths)
    git(repo, "stash", "push", "--keep-index", "-q")
    try:
        return subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)], cwd=str(repo),
            capture_output=True, text=True, timeout=30,
        )
    finally:
        git(repo, "stash", "pop", "-q")
        git(repo, "reset", "-q")


def drive_commit_stage_output(
    written: list[str], *, extra_paths=None, stage: str = "itpo", worktree: str = "/wt",
    branch: str = "ac-authoring/x",
) -> dict:
    """Run the real commitStageOutput(); return {res, prompts}."""
    driver = textwrap.dedent(f"""
        const prompts = [];
        const agent = async (prompt, opts) => {{
            const label = (opts && opts.label) || '';
            if (label === 'branch-check') {{
                return {{ output: {json.dumps(branch)}, exit_code: 0 }};
            }}
            if (label === 'commit-stage-output') {{
                prompts.push(prompt);
                return {{ status: 'committed', commit_answer: {{ status: 'committed', reason_code: null, reason: null, sha: 'abc1234' }} }};
            }}
            return {{ status: 'ok' }};
        }};
        commitStageOutput({json.dumps(written)}, {json.dumps(stage)}, 'build-orchestration',
            false, 'run-300g2', {json.dumps(AC_STORE)}, {json.dumps(worktree)},
            {json.dumps(extra_paths)})
            .then(res => {{ process.stdout.write(JSON.stringify({{ res, prompts }})); }})
            .catch(err => {{ process.stderr.write(String(err)); process.exit(1); }});
    """)
    return json.loads(run_isolated_e2(["commitStageOutput", "stageDisplayName", "parseAgentJson"], driver))


def step_paths(prompt: str) -> list[str]:
    """The exact path list a stage-commit prompt passes to the shared commit step (BO-4500a-5-ii).

    The paths follow `--run <run-id>` on the one line that runs commit_changes.py.
    """
    line = next(ln for ln in prompt.splitlines() if "commit_changes.py" in ln)
    tokens = line.split(" --supervised --run ", 1)[1].split()
    return tokens[1:]


def run_full_workflow_to_commit(written: list[str], commit_reply: dict, run_id: str = "r300g2",
                                records_to_commit: list[str] | None = None):
    """Production entry point: plan-feature.js's own top-level body (technical
    route -> it-po stage -> stage commit) through the E2 harness.

    `records_to_commit` is what the it-po stage's rule check reports (every record file the stage changed,
    repaired parents included); it is the path list the stage commit hands to the shared step.
    """
    from _workflow_engine_harness import run_workflow_under_e2  # noqa: WPS433

    labels = {
        "stage-0-triage": {"route": "technical", "existing_acs": []},
        "stage-itpo-author": {"status": "ok", "acs_written": written},
        "commit-stage-output": commit_reply,
    }
    if records_to_commit is not None:
        report = {"verdict": "passed", "location": AC_STORE, "records_checked": len(records_to_commit),
                  "findings": [], "records_to_commit": records_to_commit}
        labels["rule-check-itpo"] = {"output": json.dumps(report), "exit_code": 0, "stderr": ""}
    return run_workflow_under_e2(
        _REPO_ROOT / "templates" / "workflows-js" / "plan-feature.js",
        timeout=60,
        label_responses=labels,
        args={"workspace_setup_permission": {"permits": True}, "run_id": run_id},
    )


def commit_prompt_of(result) -> str:
    calls = [c for c in result.agent_calls if c.label == "commit-stage-output"]
    assert len(calls) == 1, [c.label for c in result.agent_calls]
    return calls[0].prompt or ""
