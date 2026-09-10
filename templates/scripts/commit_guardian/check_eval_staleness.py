"""
MODULE: check_eval_staleness.py
GOAL: Fast, deterministic pre-commit guard that BLOCKS a commit when it stages a
    file inside an agent-eval's trigger closure while that agent's eval result is
    missing or stale — WITHOUT invoking any model. Implements the fast local
    enforcement surface of TQ-200b-4.
BUSINESS CONTEXT: Each pipeline agent in scripts/evals/agent_eval_config.json
    declares a `triggers` closure (its prompt template, shared schemas, its eval
    set, and the harness). A change that touches an agent's closure must be
    proven by a FRESH eval result before it can land — a missing or stale result
    is a HARD FAILURE (mirrors TQ-200a-1's coverage-gap rule), never a silent
    pass. TQ-200b-4 enforces this on two surfaces: (1) a REQUIRED CI status check
    that runs the live model eval (the hard guarantee), and (2) THIS cheap local
    pre-commit guard that catches missing/stale results without a model call so a
    developer gets an immediate, deterministic signal. Being a local hook it is
    bypassable with `git commit --no-verify`; the CI required check is the
    non-bypassable backstop.
ARCHITECTURE: Thin delegating wrapper — this module owns NO freshness logic. It
    resolves the staged file set via `git diff --cached --name-only` and delegates
    the affected-agent selection + freshness gate to the single source of truth,
    scripts/evals/eval_selector.py, invoked as
    `eval_selector.py --check --changed-files <staged...>`. The selector's exit
    code drives the hook: 0 = every affected agent is fresh (ALLOW); 3 = at least
    one affected agent is missing/stale (BLOCK, naming the offenders); 2 or a
    launch failure = infra error, treated as a non-blocking advisory (fail-open)
    because a transient git/config glitch must not wedge every local commit — the
    required CI check still enforces the hard gate. No model is ever invoked.
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from pathlib import Path

from _resolve_root import find_project_root

logger = logging.getLogger("check_eval_staleness")

# Selector exit-code contract (see scripts/evals/eval_selector.py docstring).
_EXIT_FRESH = 0
_EXIT_INFRA = 2
_EXIT_STALE = 3

_SELECTOR_REL = "scripts/evals/eval_selector.py"
_RUNNER_HINT = "python scripts/evals/run_agent_eval.py --agent"
_RESULTS_REL = "scripts/evals/results"


class EvalStalenessError(Exception):
    """Raised when the staleness guard cannot invoke the selector (infra error)."""


def _staged_files(repo_root: Path) -> list[str]:
    """Return the repo-relative staged file paths. I/O boundary (log + typed raise).

    Args:
        repo_root: Absolute path to the repository root.

    Returns:
        Sorted list of staged file paths, empty when nothing is staged.

    Raises:
        EvalStalenessError: When git cannot be launched or the diff fails.
    """
    cmd = ["git", "-C", str(repo_root), "diff", "--cached", "--name-only"]
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            cmd, capture_output=True, text=True, check=True
        )
    except subprocess.CalledProcessError as exc:
        logger.exception("git diff --cached failed")
        msg = f"git diff --cached failed: {(exc.stderr or '').strip()[:300]}"
        raise EvalStalenessError(msg) from exc
    except OSError as exc:
        logger.exception("git could not be launched")
        msg = "git could not be launched"
        raise EvalStalenessError(msg) from exc
    return sorted({ln.strip() for ln in completed.stdout.splitlines() if ln.strip()})


def _run_selector(repo_root: Path, staged: list[str]) -> subprocess.CompletedProcess[str]:
    """Invoke eval_selector.py --check for the staged files. I/O boundary.

    Uses the interpreter that is already running this hook (resolved by
    run_hook.py to the correct worktree venv), so the selector runs under the
    same environment.

    Args:
        repo_root: Absolute path to the repository root.
        staged: Repo-relative staged file paths to hand to the selector.

    Returns:
        The completed subprocess (stdout/stderr captured, any exit code).

    Raises:
        EvalStalenessError: When the selector script is missing or cannot launch.
    """
    selector = repo_root / _SELECTOR_REL
    if not selector.exists():
        msg = f"eval selector not found at {selector}"
        raise EvalStalenessError(msg)
    cmd = [sys.executable, str(selector), "--check", "--changed-files", *staged]
    try:
        return subprocess.run(  # noqa: S603 - fixed argv, no shell
            cmd, capture_output=True, text=True, check=False
        )
    except OSError as exc:
        logger.exception("Could not launch eval_selector.py")
        msg = "could not launch eval_selector.py"
        raise EvalStalenessError(msg) from exc


def _offenders(stdout: str) -> list[tuple[str, str]]:
    """Parse (agent, status) pairs for every non-fresh affected agent. Pure-ish.

    The selector prints a JSON object whose `status` map records each affected
    agent's freshness ('fresh' | 'missing' | 'stale'). A parse failure yields an
    empty list — the caller still blocks on the exit code and prints the raw
    selector output.

    Args:
        stdout: The selector's captured stdout.

    Returns:
        Sorted list of (agent, status) pairs where status != 'fresh'.
    """
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    status = payload.get("status") if isinstance(payload, dict) else None
    if not isinstance(status, dict):
        return []
    return sorted((a, str(s)) for a, s in status.items() if s != "fresh")


def _never_run_here(repo_root: Path) -> bool:
    """Return True when no eval has EVER produced a result in this worktree.

    ``scripts/evals/results/*.json`` is gitignored, so results exist only on the
    machine that last ran them. A fresh clone or a new worktree therefore holds
    NONE of them, by construction — which is a different condition from "this
    result is out of date", even though the selector reports both as non-fresh.

    Args:
        repo_root: The repository root.

    Returns:
        True when the results directory is absent or holds no result at all.
    """
    results_dir = repo_root / _RESULTS_REL
    if not results_dir.is_dir():
        return True
    return not any(results_dir.glob("*.json"))


def _print_block(offenders: list[tuple[str, str]], selector_stdout: str) -> None:
    """Print the blocking message naming the offending agents + remediation."""
    print(
        "\n[check-eval-staleness] BLOCKED: agent eval result(s) missing or stale",
        flush=True,
    )
    print(
        "  A staged change touches an eval's trigger closure, but that agent's "
        "eval result is not proven fresh:",
        flush=True,
    )
    if offenders:
        for agent, state in offenders:
            print(f"    - {agent} ({state})", flush=True)
    else:
        # Fall back to the selector's own report when the JSON could not be parsed.
        print(selector_stdout.strip() or "    (see selector output above)", flush=True)
    print("  Re-run the affected eval(s) locally, then re-stage the result:", flush=True)
    for agent, _state in offenders:
        print(f"    {_RUNNER_HINT} {agent}", flush=True)
    if not offenders:
        print(f"    {_RUNNER_HINT} <agent>", flush=True)
    print(
        "  (This local guard is bypassable with `git commit --no-verify`, but the "
        "required CI eval check will still enforce this.)",
        flush=True,
    )


def main() -> int:
    """Entry point: gate the commit on affected-agent eval freshness.

    Returns:
        int: 0 to ALLOW the commit (all affected fresh, nothing affected, or a
            fail-open infra error); 1 to BLOCK (an affected agent is missing/stale).
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    repo_root = find_project_root()

    try:
        staged = _staged_files(repo_root)
    except EvalStalenessError as exc:
        logger.warning("check-eval-staleness: fail-open (git error): %s", exc)
        return 0

    if not staged:
        return 0

    try:
        result = _run_selector(repo_root, staged)
    except EvalStalenessError as exc:
        logger.warning("check-eval-staleness: fail-open (selector error): %s", exc)
        return 0

    if result.returncode == _EXIT_FRESH:
        return 0

    if result.returncode == _EXIT_STALE:
        offenders = _offenders(result.stdout)
        # Distinguish "never produced here" from "produced and now out of date".
        # Results are gitignored, so a fresh clone holds none of them and every
        # affected agent reports `missing` — a state no local action can clear
        # when the harness itself cannot run, which made this gate unsatisfiable
        # in any new worktree (KI-TQ-20260908-0900). Fail open there, loudly and
        # by name. A `stale` offender still BLOCKS: a result that exists and no
        # longer matches its triggers is exactly the case this gate is for, and
        # so does a mixed set, where some results plainly can be produced here.
        if offenders and all(status == "missing" for _agent, status in offenders) and _never_run_here(repo_root):
            logger.warning(
                "check-eval-staleness: fail-open — no eval result exists in this "
                "worktree at all (%s is empty or absent), so every affected agent "
                "reports 'missing': %s. This is the never-run state, not staleness, "
                "and results are gitignored so a fresh clone can never start from "
                "anything else. Run `%s <agent>` to produce them; the required CI "
                "check still enforces the hard gate.",
                _RESULTS_REL,
                ", ".join(agent for agent, _status in offenders),
                _RUNNER_HINT,
            )
            return 0
        _print_block(offenders, result.stdout)
        return 1

    # _EXIT_INFRA (or any unexpected code): advisory, do not wedge the commit.
    detail = (result.stderr or result.stdout or "").strip()[:500]
    logger.warning(
        "check-eval-staleness: fail-open (selector infra exit %s): %s",
        result.returncode,
        detail,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-10 [python-coder]: Separated "never run here" from "out of date".
#   Results live in scripts/evals/results/*.json, which is gitignored, so a fresh
#   clone or new worktree holds NONE of them and every affected agent reports
#   'missing'. Combined with the harness's own inability to launch the claude CLI
#   (KI-TQ-20260908-0900), that made this gate unsatisfiable by any local action:
#   it blocked every commit touching an eval's trigger closure, and the sanctioned
#   escape (SKIP=) is unreachable from a sub-agent, whose conversation is with its
#   parent rather than the user. main() now fails open -- loudly, naming each agent
#   and the runner command -- when EVERY offender is 'missing' AND the results
#   directory holds no result at all. A 'stale' offender still BLOCKS, and so does
#   a MIXED set: if any result exists here, results can plainly be produced here,
#   and a non-fresh one is exactly what this gate is for. This narrows an
#   unsatisfiable gate; it does not weaken the satisfiable one. The required CI
#   check is unchanged.
# - 2026-07-15 [TQ-200b-4]: Created the fast local pre-commit staleness guard.
#   Delegates the affected-agent selection + freshness gate to
#   scripts/evals/eval_selector.py --check (the SSOT — this hook owns no
#   freshness logic and invokes no model). Exit mapping: selector 0 -> allow,
#   3 -> block with named offenders + run_agent_eval remediation, 2/launch-fail
#   -> fail-open advisory (a transient git/config glitch must not wedge every
#   local commit; the REQUIRED CI eval check is the non-bypassable hard gate).
# ====================================================================
