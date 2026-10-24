"""
MODULE: scripts/evals/produced_tests_mode.py
GOAL: The produced-tests scoring mode of the shared agent-eval runner: run (or, with
    --score-gold, replay) a test-writing agent on each row of its set and score what it
    produced, tests and report.
BUSINESS CONTEXT: TQ-200d-1. Neither label nor artifact mode fits an agent whose output is
    test files plus a report. Every result of this mode is a LOCAL result: the CI eval gate has
    never evaluated an agent (KI-TQ-20260907), so the payload carries run_context "local", the
    printed report says so, and eval_selector keeps a ``local_only`` agent out of CI.
ARCHITECTURE: ``run_produced_tests_mode`` is dispatched by run_agent_eval.main(), which passes
    its own module as ``harness`` (check_eval_set_complete, write_results, resolve_trigger_shas,
    invoke_agent_writer, choose_backend), so there is no import cycle. Scoring lives in
    produced_tests_scoring.py, execution in produced_tests_runs.py. A live row runs the agent in
    a git sandbox (the fixture plus the scripts the template names, ``{{config.output_root}}``
    rendered to the sandbox), exports the test files it wrote as ``*.py.recorded`` beside its
    reply as report.md, and scores them exactly like a recorded gold output. Gold mode makes no
    model call.
"""

from __future__ import annotations

import argparse
import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any

import produced_tests_runs as runs
import produced_tests_scoring as scoring

logger = logging.getLogger("run_agent_eval")
OUTPUT_ROOT_PLACEHOLDER = "{{config.output_root}}"
LOCAL_NOTE = "LOCAL RUN: scored on this machine only; the CI eval gate has not run this eval."


def render_prompt(system_prompt: str, sandbox: Path) -> str:
    """Render the template's output-root placeholder to the sandbox so no path leaves it (OQ-3)."""
    return system_prompt.replace(OUTPUT_ROOT_PLACEHOLDER, sandbox.as_posix())


def changed_paths(sandbox: Path, base: str) -> list[str]:
    """Every file added or changed since *base*: committed or not, tracked or untracked (H-6)."""
    tracked = runs.git(sandbox, "diff", "--name-only", "-z", base).split("\0")
    untracked = runs.git(sandbox, "ls-files", "-o", "--exclude-standard", "-z").split("\0")
    skip = ("__pycache__", ".pytest_cache")
    return sorted({p for p in (*tracked, *untracked) if p and not set(Path(p).parts) & set(skip) and (sandbox / p).is_file()})


def export_outputs(sandbox: Path, base: str, reply: str, out_dir: Path) -> None:
    """Write every file the agent added or changed (relative paths kept, under ``files/``) and its reply (report.md)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for rel in changed_paths(sandbox, base):
        target = out_dir / runs.FILES_DIR / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((sandbox / rel).read_bytes())
    (out_dir / "report.md").write_text(reply, encoding="utf-8")


def support_for(agent_cfg: dict, repo_root: Path) -> tuple[tuple[Path, str], ...]:
    """The ``(source dir, relative dir)`` scripts the agent's template names; both sandboxes hold them."""
    return tuple((repo_root / rel, rel) for rel in agent_cfg.get("support_scripts", []))


def live_output(row: dict, agent_cfg: dict, system_prompt: str, repo_root: Path, work_dir: Path, harness: ModuleType, timeout: int) -> Path:
    """Run the agent on *row* in a git sandbox and return the directory of what it produced (model call).

    The agent's sandbox sits at the very path the scoring sandbox will have, so the rendered
    ``{{config.output_root}}`` the agent wrote into its tests resolves when they are scored.
    """
    expected = row[agent_cfg.get("expected_field", "expected")]
    agent_box = work_dir / "score" / runs.SANDBOX_NAME
    base = runs.build_sandbox(repo_root / expected["fixture"], agent_box, runs.hold_back_dirs(expected.get("assertions", [])),
                              support_for(agent_cfg, repo_root))
    try:
        reply = harness.invoke_agent_writer(render_prompt(system_prompt, agent_box), row[agent_cfg.get("input_field", "input")],
                                            agent_cfg.get("model", "sonnet"), timeout, agent_box, agent_cfg.get("tools", "Read,Write,Edit,Bash"))
        out_dir = work_dir / "produced"
        export_outputs(agent_box, base, reply, out_dir)
    finally:
        runs.remove_tree(agent_box)
    return out_dir


def score_one(row: dict, agent_cfg: dict, system_prompt: str, repo_root: Path, harness: ModuleType, *, score_gold: bool, timeout: int) -> dict[str, Any]:
    """Score one row; a harness or sandbox failure is a failed row carrying its error, never a skip."""
    field_name = agent_cfg.get("expected_field", "expected")
    expected = row.get(field_name, {})
    with tempfile.TemporaryDirectory(prefix="produced-tests-") as tmp:
        work_dir = Path(tmp)
        try:
            if score_gold:
                output_dir = repo_root / expected["gold_output"]
            else:
                output_dir = live_output(row, agent_cfg, system_prompt, repo_root, work_dir, harness, timeout)
            return scoring.score_row(row, output_dir, work_dir / "score", repo_root=repo_root, expected_field=field_name,
                                     support=support_for(agent_cfg, repo_root))
        except (runs.SandboxError, harness.EvalHarnessError, OSError, KeyError) as exc:
            logger.warning("row %s could not be scored: %r", row.get("id"), exc)
            record = {"passed": False, "assertions": [], "judge": None}
            return {"id": row.get("id", "?"), "negative": bool(expected.get("negative")), "score": record, "error": repr(exc)}


def aggregate(rows: list[dict]) -> dict[str, Any]:
    """Pass rate and per-assertion-kind tallies. Pure."""
    passed = sum(1 for r in rows if r["score"]["passed"])
    kinds: dict[str, dict[str, int]] = {}
    for r in rows:
        for a in r["score"]["assertions"]:
            bucket = kinds.setdefault(a["kind"], {"pass": 0, "total": 0})
            bucket["total"] += 1
            bucket["pass"] += int(a["passed"])
    return {"rows": len(rows), "passed": passed, "accuracy": round(passed / len(rows), 4) if rows else 0.0,
            "per_assertion": dict(sorted(kinds.items()))}


def print_report(agent: str, mode: str, rows: list[dict], agg: dict) -> None:
    """Human-readable report; it always says this was a local run."""
    print(f"\n=== Agent eval: {agent}  (mode={mode}) ===")
    print(f"  {LOCAL_NOTE}")
    for r in rows:
        print(f"  [{'PASS' if r['score']['passed'] else 'FAIL'}] {r['id']}{' [negative]' if r.get('negative') else ''}")
        if r.get("error"):
            print(f"         error: {r['error']}")
        for a in r["score"]["assertions"]:
            print(f"         [{'ok ' if a['passed'] else 'XXX'}] {a['kind']}: {a['detail']}")
    print(f"\n  --- Aggregate ---\n  rows={agg['rows']} passed={agg['passed']} accuracy={agg['accuracy']:.2%}")


def select_rows(rows: list[dict], args: argparse.Namespace) -> list[dict]:
    """Apply --row and --limit; completeness was already checked on the full set."""
    if args.row:
        rows = [r for r in rows if r.get("id") in set(args.row)]
    return rows[: args.limit] if args.limit else rows


def run_produced_tests_mode(args: argparse.Namespace, agent_cfg: dict, rows: list[dict], system_prompt: str,
                            repo_root: Path, harness: ModuleType) -> int:
    """Run the mode for one agent; return the process exit code (0 pass, 1 below threshold, 2 harness error)."""
    complete, msg = harness.check_eval_set_complete(rows, agent_cfg.get("expected_field", "expected"))
    if not complete:
        logger.error("Eval set INCOMPLETE for %s: %s", args.agent, msg)
        return 2
    selected = select_rows(rows, args)
    timeout = args.timeout or int(agent_cfg.get("timeout", 900))
    scored = [score_one(r, agent_cfg, system_prompt, repo_root, harness, score_gold=args.score_gold, timeout=timeout) for r in selected]
    if not scored:
        logger.error("No produced-tests rows were scored")
        return 2
    agg = aggregate(scored)
    print_report(args.agent, f"produced_tests{' (score-gold)' if args.score_gold else ''}", scored, agg)
    threshold = float(agent_cfg.get("threshold", 0.0))
    payload = {
        "agent": args.agent, "mode": "produced_tests", "run_context": "local", "score_gold": args.score_gold,
        "backend": None if args.score_gold else harness.choose_backend(), "model": None if args.score_gold else agent_cfg.get("model"),
        "eval_set": agent_cfg["eval_set"], "threshold": threshold, "timestamp": datetime.now(timezone.utc).isoformat(),
        "aggregate": agg, "rows": scored,
        "trigger_shas": harness.resolve_trigger_shas(repo_root, agent_cfg.get("triggers") or []),
    }
    default = f"{args.agent}{'-scoregold' if args.score_gold else ''}.json"
    path = Path(args.results_file) if args.results_file else repo_root / "scripts/evals/results" / default
    harness.write_results(path, payload)
    print(f"\n  results -> {path}")
    ok = agg["accuracy"] >= threshold
    print(f"\n  GATE: {'PASS' if ok else 'FAIL'} - score {agg['accuracy']:.2%} vs threshold {threshold:.2%} (local run)")
    return 0 if ok else 1
