"""
MODULE: _plan_feature_gate_harness
GOAL: Shared ADR-024 / ACD-2100b-5 pause-resume gate-testing scaffolding for
    the plan-feature.js E2 migration test family. Sibling of
    ``_workflow_engine_harness.py`` (which stubs the whole E2 engine) and of
    ``_plan_feature_e2_runner.py`` (which drives the E2 body itself) — this
    module holds the scaffolding those two do NOT already provide: the
    workspace-setup pre-flight verdict, the registry-permission lookups, the
    scratch git-repo fixtures, and the ADR-024 pause/resume hop-chaining
    driver.
BUSINESS CONTEXT: Six test files were migrated (separately, by different
    agents) from the retired live-gate answer path to the ADR-024
    pause/resume protocol. Each one independently grew a near-identical copy
    of:
      1. ``real_preflight_verdict`` / ``granted_workspace_setup_permission``
         — run the REAL, on-disk
         ``scripts/worktree/check_workspace_setup_permission.py`` as a
         subprocess and return its parsed verdict (2h.2 Fixture Authenticity
         Rule: never a hand-typed stand-in for that shape).
      2. Real-registry lookups (``load_real_registry`` / ``permits_shell``)
         and scratch git-repo fixtures (``make_repo_fixture`` /
         ``init_scratch_repo`` / ``run_git``) used to build isolated
         repositories the pre-flight script or the E2 body can run against.
      3. A ``HarnessResult``-introspection pair (``worktree_setup_calls`` /
         ``halt_message``) for files driving the workflow via
         ``_workflow_engine_harness.run_workflow_under_e2``.
      4. Side-channel (``run_plan_feature_e2``-style ``(result, side)``)
         introspection helpers (``agent_types_in`` / ``labels_in`` /
         ``agent_type_order`` / ``merge_side``), and the ADR-024
         pause/resume hop-chaining driver (``HopDriver``) that resolves a
         scenario across as many chained process invocations as it needs.
    That is one mechanism, implemented six times. This module is the ONE
    place it lives now; the six call sites import from here.
ARCHITECTURE: Pure-Python helper module, no test classes of its own. Lives
    directly under ``unit_tests/`` (a sibling of ``_workflow_engine_harness.py``)
    so files under ``unit_tests/`` import it directly, and files under
    ``unit_tests/workflows/`` reach it via the same ``sys.path.insert(0,
    <unit_tests dir>)`` convention those files already use to import
    ``_workflow_engine_harness``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Shared paths / constants
# ---------------------------------------------------------------------------

WORKTREE_ROOT = Path(__file__).resolve().parent.parent
PREFLIGHT_SCRIPT = WORKTREE_ROOT / "scripts" / "worktree" / "check_workspace_setup_permission.py"
REAL_REGISTRY_PATH = WORKTREE_ROOT / "config" / "agent_registry.json"
DEFAULT_PREFLIGHT_TIMEOUT = 30


class SourceParseError(Exception):
    """Raised when JS/source text cannot be parsed as a helper expects."""


class NodeScriptError(Exception):
    """Raised when a Node.js subprocess exits non-zero unexpectedly."""


class GitCommandError(Exception):
    """Raised when a git sub-process command exits non-zero."""


# ---------------------------------------------------------------------------
# Pre-flight verdict — real subprocess, never a hand-typed stand-in.
# ---------------------------------------------------------------------------


def run_preflight(
    agent_id: str = "worktree-agent",
    *,
    cwd: Path | None = None,
    timeout: int = DEFAULT_PREFLIGHT_TIMEOUT,
) -> subprocess.CompletedProcess:
    """Run the REAL, on-disk check_workspace_setup_permission.py as a real
    subprocess with `cwd` set to `cwd` (defaulting to this repository's own
    root), returning the raw CompletedProcess so a caller can assert on
    stdout/exit_code directly, before any JSON parsing.
    """
    return subprocess.run(
        [sys.executable, str(PREFLIGHT_SCRIPT), "--agent-id", agent_id],
        cwd=str(cwd if cwd is not None else WORKTREE_ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def real_preflight_verdict(
    agent_id: str = "worktree-agent",
    *,
    cwd: Path | None = None,
    timeout: int = DEFAULT_PREFLIGHT_TIMEOUT,
) -> dict:
    """Run the real pre-flight script and return its parsed verdict.

    ACD-2100b-5 moved the Pre-Stage-0 workspace-setup permission gate in
    templates/workflows-js/plan-feature.js out of the workflow body (which
    the E2 engine sandbox has no filesystem primitive for) and into this
    external pre-flight, consumed via `args.workspace_setup_permission`.
    Every caller of this function needs a real verdict to get past that gate
    and reach the behavior actually under test — never a hand-typed verdict
    literal (2h.2 Fixture Authenticity Rule).
    """
    proc = run_preflight(agent_id, cwd=cwd, timeout=timeout)
    if not proc.stdout.strip():
        raise AssertionError(
            "Pre-flight script produced no stdout.\n"
            f"returncode={proc.returncode}\nstderr={proc.stderr[:2000]!r}"
        )
    return json.loads(proc.stdout)


def granted_workspace_setup_permission(
    *, cwd: Path | None = None, agent_id: str = "worktree-agent"
) -> dict:
    """The real, granted verdict for THIS repository's own root (or `cwd`) —
    sourced from actually running the real pre-flight script rather than a
    fabricated literal.
    """
    return real_preflight_verdict(agent_id, cwd=cwd if cwd is not None else WORKTREE_ROOT)


# ---------------------------------------------------------------------------
# Real config/agent_registry.json lookups.
# ---------------------------------------------------------------------------


def load_real_registry() -> dict:
    """Read the REAL config/agent_registry.json from disk (not a fixture)."""
    text = REAL_REGISTRY_PATH.read_text(encoding="utf-8")
    return json.loads(text)


def permits_shell(registry: dict, agent_id: str) -> bool | None:
    """Look up `permits_shell` for `agent_id` in a registry dict.

    Returns None when the agent id is not found or the registry has no
    `agents` list.
    """
    agents = registry.get("agents") if isinstance(registry, dict) else None
    if not isinstance(agents, list):
        return None
    for entry in agents:
        if isinstance(entry, dict) and entry.get("id") == agent_id:
            value = entry.get("permits_shell")
            return value if isinstance(value, bool) else None
    return None


# ---------------------------------------------------------------------------
# Scratch git-repo fixtures.
# ---------------------------------------------------------------------------


def run_git(args: list[str], cwd: str | Path, timeout: int = 10) -> subprocess.CompletedProcess:
    """Run a git command in `cwd`, raising GitCommandError on a non-zero exit."""
    result = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if result.returncode != 0:
        msg = f"git {' '.join(args)} failed (exit {result.returncode}): {result.stderr!r}"
        raise GitCommandError(msg)
    return result


def init_scratch_repo(tmpdir: str | Path) -> None:
    """Initialise a scratch git repo in tmpdir with one baseline commit.

    The initial commit seeds the repo so that git porcelain commands work
    correctly (an empty repo has no HEAD and some commands misbehave).
    """
    tmpdir = str(tmpdir)
    run_git(["init", "-b", "main"], cwd=tmpdir)
    run_git(["config", "user.email", "test@test.com"], cwd=tmpdir)
    run_git(["config", "user.name", "Test"], cwd=tmpdir)
    sentinel = Path(tmpdir) / ".gitkeep"
    try:
        sentinel.write_text("", encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Failed to write sentinel file: {sentinel}") from exc
    run_git(["add", ".gitkeep"], cwd=tmpdir)
    run_git(["commit", "-m", "init"], cwd=tmpdir)


def write_text_file(path: str | Path, content: str) -> None:
    """Write `content` to `path`, creating parent dirs as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Failed to write fixture file: {path}") from exc


_AGENT_REGISTRY_RELATIVE_PATH = Path(".leafcutter") / "config" / "agent_registry.json"


def make_repo_fixture(tmp_path: Path, *, agents: list[dict] | None = None) -> Path:
    """Build a real, isolated git repository, optionally with its own
    `.leafcutter/config/agent_registry.json`.

    When `agents` is None, NO registry file is written at all — pointing the
    pre-flight script's repo-root resolution at this fixture then produces a
    GENUINE read failure (a real FileNotFoundError inside its own registry
    loader), not a contrived stand-in for one.
    """
    repo_dir = tmp_path / "project"
    repo_dir.mkdir(parents=True)
    run_git(["init", "-b", "main", str(repo_dir)], cwd=WORKTREE_ROOT)
    run_git(["config", "user.email", "test@example.com"], cwd=repo_dir)
    run_git(["config", "user.name", "Test"], cwd=repo_dir)
    write_text_file(repo_dir / "README.md", "seed\n")
    run_git(["add", "README.md"], cwd=repo_dir)
    run_git(["commit", "-m", "seed"], cwd=repo_dir)
    if agents is not None:
        registry_path = repo_dir / _AGENT_REGISTRY_RELATIVE_PATH
        write_text_file(registry_path, json.dumps({"agents": agents}))
    return repo_dir


# ---------------------------------------------------------------------------
# HarnessResult introspection (files driving via _workflow_engine_harness).
# ---------------------------------------------------------------------------


def worktree_setup_calls(result: Any, label: str = "worktree-setup") -> list:
    """Return every agent() call on `result` whose label matches `label`."""
    return [c for c in result.agent_calls if c.label == label]


def halt_message(result: Any) -> str:
    """Extract the halt message from a HarnessResult's top-level return value.

    plan-feature.js's Pre-Stage-0 gate is written at the script's top level
    (E2 canonical form), so its `return { status: "error", message: ... }` is
    captured by the harness as `result.result` — the script's own resolved
    terminal payload, not an inference from which agent() calls fired.
    """
    assert result.result is not None, (
        "Expected plan-feature.js to return a terminal payload (its top-level "
        f"`return` value) but the harness captured None. stderr: {result.stderr!r}"
    )
    assert isinstance(result.result, dict), (
        f"Expected the terminal payload to be a dict, got {type(result.result)}: {result.result!r}"
    )
    return str(result.result.get("message", ""))


# ---------------------------------------------------------------------------
# Side-channel ((result, side) dict pairs from run_plan_feature_e2).
# ---------------------------------------------------------------------------


def agent_types_in(side: dict) -> list[str]:
    return [c["agentType"] for c in side.get("allCalls", [])]


def labels_in(side: dict) -> list[str]:
    return [c.get("label") for c in side.get("allCalls", [])]


def agent_type_order(side: dict, allowed: set[str] | tuple[str, ...]) -> list[str]:
    """Distinct-stage dispatch order among `allowed` agent types, collapsing
    ADJACENT repeats.

    ADR-024's pause/resume chaining inevitably re-dispatches a stage's author
    across a hop boundary (a "discovery" dispatch that pauses without
    approving, then a genuine approving dispatch on the next hop) — that
    repeat is always adjacent in the merged call sequence and carries no
    information a caller asserting on DISTINCT engaged stages cares about.
    """
    order = [c["agentType"] for c in side.get("allCalls", []) if c["agentType"] in allowed]
    deduped: list[str] = []
    for agent_type in order:
        if not deduped or deduped[-1] != agent_type:
            deduped.append(agent_type)
    return deduped


def merge_side(accum: dict, side: dict) -> None:
    """Accumulate one hop's side-channel arrays onto `accum`, in place."""
    for key in ("allCalls", "commitCalls", "restoreCalls", "deleteCalls"):
        accum.setdefault(key, [])
        accum[key].extend(side.get(key, []))


# ---------------------------------------------------------------------------
# ADR-024 pause/resume hop-chaining driver.
# ---------------------------------------------------------------------------


class HopDriver:
    """Drives the E2 plan-feature body to its terminal result, chaining as
    many ADR-024 pause/resume round-trips as a scenario needs.

    ACD-2100c-1 removed the live gate-answer dispatch entirely: resolveGate()
    (templates/workflows-js/plan-feature.js) never asks an agent for a
    decision any more — it checks `args.resume_answer` (matched by
    `gate_id`) BEFORE any live attempt, and when there is no match it pauses,
    returning a terminal payload that NAMES the gate_id awaiting an answer.
    The only way back in is a FRESH process invocation carrying a
    `resume_answer` for that exact gate_id. A scenario that spans several
    gates therefore requires several chained "hops" — each one a separate
    `run_plan_feature_e2()` call, mirroring a real resumed run.

    Between hops this driver grows `cfg['committedLog']` from the real
    commit-call subjects observed so far, exactly mirroring what a real
    `git log` would show after a real resumed run committed that stage — this
    is what lets scanCommittedStages() (plan-feature.js's own crash-resume
    mechanism) skip re-authoring a stage a PRIOR hop already got approved.
    When `flow_artifact_path` is supplied, it does the same for
    `cfg['flowRefLog']` (recoverFlowRefFromCommit()'s own real `git log
    --name-only --format=%H%x00%s` shape) for every FLOW-stage commit
    observed so far.
    """

    def __init__(
        self,
        *,
        run_hop: Callable[..., tuple[dict, dict]],
        workspace_setup_permission: dict,
        commit_subject_re: Any,
        flow_artifact_path: str | None = None,
        default_gate_answer: Callable[[str, dict], dict] | None = None,
    ) -> None:
        self._run_hop = run_hop
        self._workspace_setup_permission = workspace_setup_permission
        self._commit_subject_re = commit_subject_re
        self._flow_artifact_path = flow_artifact_path
        self._default_gate_answer = default_gate_answer or self._default_answer

    @staticmethod
    def _default_answer(gate_id: str, cfg: dict) -> dict:
        if gate_id == "final-gate":
            return {"type": "priority_choice", "action": "approve", "priority": "high"}
        if gate_id.startswith("pt-gate-"):
            stage = gate_id[len("pt-gate-"):]
            if cfg.get("cancelStage") == stage:
                return {"type": "single_choice", "action": "cancel"}
            return {"type": "single_choice", "action": "approve"}
        return {"type": "single_choice", "action": "approve"}

    def _committed_log_from_calls(self, commit_calls: list[dict]) -> str:
        lines = []
        for i, call in enumerate(commit_calls):
            match = self._commit_subject_re.search(call.get("instructions", "") or "")
            if match:
                lines.append(f"{i:07x} plan-feature({match.group(1)}): ux-prototyping")
        return "\n".join(lines)

    def _flow_ref_log_from_calls(self, commit_calls: list[dict]) -> str:
        lines = []
        for i, call in enumerate(commit_calls):
            if "plan-feature(FLOW)" in (call.get("instructions", "") or ""):
                lines.append(f"{i:07x}\x00plan-feature(FLOW): ux-prototyping\n\n{self._flow_artifact_path}")
        return "\n".join(lines)

    def _one_hop(self, cfg: dict, extra_args: dict | None, user_input: str, timeout: int) -> tuple[dict, dict]:
        merged_extra_args = {"workspace_setup_permission": self._workspace_setup_permission}
        if extra_args:
            merged_extra_args.update(extra_args)
        return self._run_hop(cfg, extra_args=merged_extra_args, user_input=user_input, timeout=timeout)

    def run(
        self,
        cfg: dict,
        user_input: str = "add a checkout screen",
        timeout: int = 30,
        max_hops: int = 12,
    ) -> tuple[dict, dict]:
        cfg = dict(cfg)
        baseline_committed_log = cfg.get("committedLog", "")
        baseline_flow_ref_log = cfg.get("flowRefLog", "")
        accum: dict = {"allCalls": [], "commitCalls": [], "restoreCalls": [], "deleteCalls": []}

        extra_args: dict | None = None
        if cfg.get("editStage") and "editFeedback" in cfg:
            extra_args = {
                "resume_answer": {
                    "gate_id": f"pt-gate-{cfg['editStage']}",
                    "type": "single_choice",
                    "action": "edit",
                    "feedback": cfg["editFeedback"],
                    "channel": "person",
                },
            }
        elif cfg.get("acEditStage") and "acEditFeedback" in cfg:
            extra_args = {
                "resume_answer": {
                    "gate_id": f"gate-{cfg['acEditStage']}",
                    "type": "single_choice",
                    "action": "edit",
                    "feedback": cfg["acEditFeedback"],
                    "channel": "person",
                },
            }

        result: dict = {}
        for _hop in range(max_hops):
            result, side = self._one_hop(cfg, extra_args, user_input, timeout)
            merge_side(accum, side)

            if result.get("status") != "paused_awaiting_input":
                return result, accum

            new_lines = self._committed_log_from_calls(accum["commitCalls"])
            parts = [p for p in (baseline_committed_log.strip("\n"), new_lines) if p]
            cfg["committedLog"] = "\n".join(parts)

            if self._flow_artifact_path is not None:
                new_flow_ref_lines = self._flow_ref_log_from_calls(accum["commitCalls"])
                flow_ref_parts = [p for p in (baseline_flow_ref_log.strip("\n"), new_flow_ref_lines) if p]
                cfg["flowRefLog"] = "\n".join(flow_ref_parts)

            gate_id = result.get("gate_id")
            if not gate_id:
                return result, accum
            answer = self._default_gate_answer(gate_id, cfg)
            answer["gate_id"] = gate_id
            answer["channel"] = "person"
            extra_args = {"resume_answer": answer}

        return result, accum
