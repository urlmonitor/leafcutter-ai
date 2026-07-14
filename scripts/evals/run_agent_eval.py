"""
MODULE: run_agent_eval.py
GOAL: A shared, agent-generalizable eval harness for leafcutter pipeline agents.
    "Send data in -> get an expected-outcome score." It reads an agent's system
    prompt from its template, replays each row of a gold eval set through the
    model, parses the structured response, scores it against the row's expected
    labels (or, for artifact agents, deterministic assertions + an optional
    LLM-judge rubric), and emits a per-row pass/fail report plus an aggregate
    score. Exits non-zero when the aggregate falls below the agent's threshold,
    so the harness can become a CI gate.

BUSINESS CONTEXT: pt-classifier is the first consumer. Its gold set lives at
    docs/product-truth/classifier/eval.jsonl (schema
    docs/product-truth/schemas/classifier-eval.schema.json). The eval set is the
    documented standard the classifier is scored against; this harness turns that
    standard into a runnable, repeatable number instead of a manual read-through.
    The contract is deliberately agent-neutral: a row is {id, input, expected}
    where `expected` is either LABELS (exact-match) or ASSERTIONS + a judge RUBRIC
    (artifact/markup agents). New agents slot in via agent_eval_config.json.

ARCHITECTURE: Single-module script + importable functions.
    - CONFIG (scripts/evals/agent_eval_config.json) maps agent -> eval-set path,
      scoring mode, input field, model, and threshold. Paths resolve against the
      repo root (parents[2] of this file).
    - MODEL INVOCATION goes through the `claude` CLI in headless print mode
      (`claude -p ... --output-format json`). This was chosen after confirming, in
      this environment, that (a) no `anthropic` Python/Node SDK is importable,
      (b) `pip` is not used in this repo, (c) the proxy at $ANTHROPIC_BASE_URL
      returns 401 to an unauthenticated subprocess (no ANTHROPIC_API_KEY is
      exported and no credentials file exists), and (d) the workflow engine's
      agent() is a runtime-injected callback, not reachable from a standalone
      script. The `claude` CLI is the ONLY mechanism that already carries working
      auth into a subprocess here. The agent's own system prompt is injected via
      --system-prompt, tools are disabled (--tools "") so the run cannot read the
      gold answers in eval.jsonl (no leakage), and dynamic sections are excluded
      for determinism. A stub `invoke_via_api()` documents the direct-HTTP path
      for environments that DO export ANTHROPIC_API_KEY.
    - SCORING: label mode computes per-row exact-match accuracy over the label
      axes, per-axis precision/recall, and (optionally) derived-outcome accuracy.
      Artifact mode runs deterministic assertions and an optional LLM-judge; it is
      scaffolded and unit-safe but has no active consumer yet.
    - SELF-TEST mode feeds each row's OWN expected labels back through the scorer,
      proving the scoring/reporting pipeline end-to-end (expected 100%) without a
      model call — used when live model access is unavailable, and as a fast CI
      smoke of the harness itself.

Exit Codes:
    0 - Aggregate score >= threshold (or --self-test passed at 100%)
    1 - Aggregate score < threshold
    2 - Harness error (bad config, missing eval set, model invocation failure)

Usage:
    python scripts/evals/run_agent_eval.py --agent pt-classifier
    python scripts/evals/run_agent_eval.py --agent pt-classifier --self-test
    python scripts/evals/run_agent_eval.py --agent pt-classifier --limit 3 --json

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-07-14 [Explore/eval-harness]: Created module. Chose the `claude` CLI
#   headless path as the live model backend after ruling out the anthropic SDK
#   (not importable, no pip), a direct proxy POST (401, no key/creds in this
#   env), and the workflow engine's injected agent() (not callable standalone).
#   Tools are disabled on each run so pt-classifier cannot read the gold labels
#   in eval.jsonl (leakage guard) and scores purely from its system-prompt rules.
#   Label mode fully implemented for the classifier; artifact mode (deterministic
#   assertions + LLM-judge rubric) scaffolded for flow-author/mock-data-author so
#   adding them is config + eval-row wiring, not a redesign. Self-test mode proves
#   the scoring pipeline (100%) when live invocation is unavailable.
# ====================================================================
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("run_agent_eval")


# ---------------------------------------------------------------------------
# Typed exceptions (Error Handling Policy: wrap external I/O, log + raise typed)
# ---------------------------------------------------------------------------
class EvalHarnessError(Exception):
    """Base class for all harness errors."""


class EvalConfigError(EvalHarnessError):
    """Raised when the eval config or an agent entry is missing or malformed."""


class EvalDataError(EvalHarnessError):
    """Raised when an eval set or template file cannot be read or parsed."""


class ModelInvocationError(EvalHarnessError):
    """Raised when the model cannot be invoked or returns an unparseable reply."""


# ---------------------------------------------------------------------------
# Outcome derivation (pure) — mirrors OUTCOME_BY_COMBO in the classifier schema
# ---------------------------------------------------------------------------
# key = (needs_flow, needs_mock_data, needs_mockup)
OUTCOME_BY_COMBO: dict[tuple[bool, bool, bool], str] = {
    (True, True, True): "full-set",
    (False, True, True): "mockup+data",
    (False, False, True): "mockup-only",
    (False, True, False): "mock-data-only",
    (False, False, False): "none",
}


def derive_outcome(labels: dict[str, bool]) -> str:
    """Derive the routing outcome from the three classifier booleans.

    Pure function. Returns "inconsistent" for any combination the schema does not
    allow (the validator flags these; the harness records them rather than crash).
    """
    key = (
        bool(labels.get("needs_flow")),
        bool(labels.get("needs_mock_data")),
        bool(labels.get("needs_mockup")),
    )
    return OUTCOME_BY_COMBO.get(key, "inconsistent")


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------
def find_repo_root() -> Path:
    """Return the repo root (this file lives at <root>/scripts/evals/)."""
    return Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Loaders (external I/O — wrapped per policy)
# ---------------------------------------------------------------------------
def load_config(config_path: Path) -> dict[str, Any]:
    """Load the eval config JSON. Raises EvalConfigError on any I/O/parse error."""
    try:
        raw = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.exception("Cannot read eval config %s", config_path)
        msg = f"Cannot read eval config {config_path}"
        raise EvalConfigError(msg) from exc
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.exception("Eval config %s is not valid JSON", config_path)
        msg = f"Eval config {config_path} is not valid JSON"
        raise EvalConfigError(msg) from exc


def get_agent_config(config: dict[str, Any], agent: str) -> dict[str, Any]:
    """Return the config block for `agent`. Raises EvalConfigError if absent."""
    agents = config.get("agents")
    if not isinstance(agents, dict):
        msg = "Config has no 'agents' object"
        raise EvalConfigError(msg)
    entry = agents.get(agent)
    if not isinstance(entry, dict):
        known = ", ".join(sorted(agents)) or "(none)"
        msg = f"Unknown agent '{agent}'. Configured agents: {known}"
        raise EvalConfigError(msg)
    return entry


def load_eval_rows(eval_path: Path) -> list[dict[str, Any]]:
    """Read a JSONL eval set into a list of row dicts. Raises EvalDataError."""
    try:
        text = eval_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.exception("Cannot read eval set %s", eval_path)
        msg = f"Cannot read eval set {eval_path}"
        raise EvalDataError(msg) from exc

    rows: list[dict[str, Any]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            row = json.loads(stripped)
        except json.JSONDecodeError as exc:
            logger.exception("Malformed JSON in %s line %d", eval_path, lineno)
            msg = f"Malformed JSON in {eval_path} line {lineno}"
            raise EvalDataError(msg) from exc
        rows.append(row)
    if not rows:
        msg = f"Eval set {eval_path} contains no rows"
        raise EvalDataError(msg)
    return rows


def load_system_prompt(template_path: Path) -> str:
    """Return the agent's system prompt: the template body below YAML frontmatter."""
    try:
        text = template_path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.exception("Cannot read agent template %s", template_path)
        msg = f"Cannot read agent template {template_path}"
        raise EvalDataError(msg) from exc
    return _strip_frontmatter(text)


def _strip_frontmatter(text: str) -> str:
    """Strip a leading '---\\n...\\n---' YAML frontmatter block. Pure function."""
    if text.startswith("---"):
        parts = text.split("\n---", 1)
        if len(parts) == 2:
            body = parts[1]
            # Drop the newline immediately following the closing '---'.
            return body.lstrip("\n")
    return text


# ---------------------------------------------------------------------------
# Model invocation
# ---------------------------------------------------------------------------
def invoke_via_cli(
    system_prompt: str,
    user_input: str,
    model: str,
    timeout: int,
) -> str:
    """Invoke the model through the headless `claude` CLI and return its text reply.

    Tools are disabled so the agent cannot read the gold eval file (leakage guard),
    and dynamic system-prompt sections are excluded for determinism. Raises
    ModelInvocationError on any subprocess or output-parse failure.
    """
    cmd = [
        "claude",
        "-p",
        user_input,
        "--model",
        model,
        "--system-prompt",
        system_prompt,
        "--tools",
        "",
        "--exclude-dynamic-system-prompt-sections",
        "--output-format",
        "json",
    ]
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=True,
        )
    except subprocess.TimeoutExpired as exc:
        logger.exception("claude CLI timed out after %ss", timeout)
        msg = f"claude CLI timed out after {timeout}s"
        raise ModelInvocationError(msg) from exc
    except subprocess.CalledProcessError as exc:
        logger.exception("claude CLI exited %s", exc.returncode)
        msg = f"claude CLI exited {exc.returncode}: {(exc.stderr or '').strip()[:400]}"
        raise ModelInvocationError(msg) from exc
    except OSError as exc:
        logger.exception("claude CLI could not be launched")
        msg = "claude CLI could not be launched"
        raise ModelInvocationError(msg) from exc

    try:
        envelope = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        logger.exception("claude CLI returned non-JSON envelope")
        msg = "claude CLI returned non-JSON envelope"
        raise ModelInvocationError(msg) from exc

    result = envelope.get("result")
    if not isinstance(result, str):
        msg = "claude CLI envelope has no string 'result'"
        raise ModelInvocationError(msg)
    return result


def invoke_via_api(
    system_prompt: str,
    user_input: str,
    model: str,
    timeout: int,
) -> str:
    """Direct-HTTP backend for environments that export ANTHROPIC_API_KEY.

    Documented alternative to the CLI path. Not exercised in the current
    environment (the proxy returns 401 to an unauthenticated subprocess and no
    key is exported). Left as a thin, obvious wiring point.
    """
    msg = (
        "invoke_via_api is a documented stub; set ANTHROPIC_API_KEY and implement "
        "an HTTP POST to $ANTHROPIC_BASE_URL/v1/messages to enable it."
    )
    raise ModelInvocationError(msg)


def choose_backend() -> str:
    """Pick the live backend available in this environment. Reads env, no I/O."""
    if os.environ.get("ANTHROPIC_API_KEY") and os.environ.get("LEAFCUTTER_EVAL_USE_API"):
        return "api"
    return "cli"


# ---------------------------------------------------------------------------
# Response parsing (model output is untrusted text — parse defensively)
# ---------------------------------------------------------------------------
_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def extract_json_object(text: str) -> dict[str, Any]:
    """Extract the first JSON object from a model reply (handles ``` fences).

    Raises ModelInvocationError when no JSON object can be parsed.
    """
    candidate = _FENCE_RE.sub("", text).strip()
    # Fast path: the whole reply is a JSON object.
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        parsed = None
    if isinstance(parsed, dict):
        return parsed

    # Fallback: locate the first balanced {...} span.
    span = _first_balanced_object(candidate)
    if span is None:
        msg = "No JSON object found in model reply"
        raise ModelInvocationError(msg)
    try:
        parsed = json.loads(span)
    except json.JSONDecodeError as exc:
        logger.exception("Model reply span is not valid JSON")
        msg = "Model reply is not valid JSON"
        raise ModelInvocationError(msg) from exc
    if not isinstance(parsed, dict):
        msg = "Model reply JSON is not an object"
        raise ModelInvocationError(msg)
    return parsed


def _extract_labels(reply_obj: dict[str, Any], label_field: str | None) -> dict[str, Any]:
    """Pull the label axes out of a parsed model reply. Pure function.

    When `label_field` is set and names a dict sub-object, return it (the agent's
    output contract nests its labels there — e.g. pt-classifier's S4 "expected").
    Otherwise return the reply as-is (labels live at top level).
    """
    if label_field:
        nested = reply_obj.get(label_field)
        if isinstance(nested, dict):
            return nested
    return reply_obj


def _first_balanced_object(text: str) -> str | None:
    """Return the first balanced {...} substring, or None. Pure function."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for idx in range(start, len(text)):
        char = text[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    return None


# ---------------------------------------------------------------------------
# Scoring — label mode
# ---------------------------------------------------------------------------
def score_label_row(
    predicted: dict[str, Any],
    expected: dict[str, Any],
    axes: list[str],
) -> dict[str, Any]:
    """Score one label row. Pure function.

    Returns per-axis correctness plus a row-level `passed` (all axes exact-match).
    """
    per_axis: dict[str, dict[str, bool]] = {}
    all_correct = True
    for axis in axes:
        exp = bool(expected.get(axis))
        pred = bool(predicted.get(axis))
        correct = exp == pred
        all_correct = all_correct and correct
        per_axis[axis] = {"expected": exp, "predicted": pred, "correct": correct}
    return {"passed": all_correct, "per_axis": per_axis}


def aggregate_label(
    row_results: list[dict[str, Any]],
    axes: list[str],
    derive_outcome_flag: bool,
) -> dict[str, Any]:
    """Aggregate label-mode row results into accuracy + per-axis precision/recall.

    Pure function.
    """
    total = len(row_results)
    passed = sum(1 for r in row_results if r["score"]["passed"])
    accuracy = passed / total if total else 0.0

    per_axis_stats: dict[str, dict[str, float | int]] = {}
    for axis in axes:
        tp = fp = fn = tn = 0
        for r in row_results:
            cell = r["score"]["per_axis"][axis]
            exp, pred = cell["expected"], cell["predicted"]
            if pred and exp:
                tp += 1
            elif pred and not exp:
                fp += 1
            elif not pred and exp:
                fn += 1
            else:
                tn += 1
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        per_axis_stats[axis] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "tn": tn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }

    aggregate: dict[str, Any] = {
        "rows": total,
        "passed": passed,
        "accuracy": round(accuracy, 4),
        "per_axis": per_axis_stats,
    }
    if derive_outcome_flag:
        outcome_correct = sum(
            1
            for r in row_results
            if r.get("expected_outcome") is not None
            and r.get("predicted_outcome") == r.get("expected_outcome")
        )
        aggregate["outcome_accuracy"] = round(outcome_correct / total, 4) if total else 0.0
    return aggregate


# ---------------------------------------------------------------------------
# Scoring — artifact mode (scaffold; no active consumer yet)
# ---------------------------------------------------------------------------
def run_deterministic_assertions(artifact: str, assertions: list[dict[str, Any]]) -> list[dict]:
    """Run substring/regex/json-key assertions against a produced artifact.

    Pure function. Each assertion: {"kind": "contains|not_contains|regex|json_has_key",
    "value"|"pattern"|"key": ...}. Returns a per-assertion result list.
    """
    results: list[dict[str, Any]] = []
    for spec in assertions:
        results.append({"spec": spec, "passed": _check_assertion(artifact, spec)})
    return results


def _check_assertion(artifact: str, spec: dict[str, Any]) -> bool:
    """Evaluate a single deterministic assertion. Pure function."""
    kind = spec.get("kind")
    if kind == "contains":
        return str(spec.get("value", "")) in artifact
    if kind == "not_contains":
        return str(spec.get("value", "")) not in artifact
    if kind == "regex":
        return re.search(str(spec.get("pattern", "")), artifact) is not None
    if kind == "json_has_key":
        try:
            obj = json.loads(artifact)
        except json.JSONDecodeError:
            return False
        return isinstance(obj, dict) and spec.get("key") in obj
    return False


def run_llm_judge(
    artifact: str,
    rubric: str,
    model: str,
    timeout: int,
    backend: str,
) -> dict[str, Any]:
    """Score an artifact against a rubric using the model as judge.

    Returns {"verdict": "pass"|"fail", "score": float, "reasoning": str}. Uses the
    same live backend as agent invocation. Raises ModelInvocationError on failure.
    """
    judge_system = (
        "You are a strict evaluation judge. Given an ARTIFACT and a RUBRIC, decide "
        "whether the artifact satisfies the rubric. Reply with ONLY a JSON object: "
        '{"verdict":"pass"|"fail","score":<0..1 float>,"reasoning":"<one sentence>"}.'
    )
    user = f"RUBRIC:\n{rubric}\n\nARTIFACT:\n{artifact}"
    reply = _dispatch(backend, judge_system, user, model, timeout)
    parsed = extract_json_object(reply)
    verdict = parsed.get("verdict")
    if verdict not in ("pass", "fail"):
        msg = "Judge reply missing a valid 'verdict'"
        raise ModelInvocationError(msg)
    return {
        "verdict": verdict,
        "score": float(parsed.get("score", 0.0)),
        "reasoning": str(parsed.get("reasoning", "")),
    }


def score_artifact_row(
    artifact: str,
    expected: dict[str, Any],
    model: str,
    timeout: int,
    backend: str,
) -> dict[str, Any]:
    """Score one artifact row: deterministic assertions AND optional LLM-judge."""
    assertions = expected.get("assertions", [])
    det = run_deterministic_assertions(artifact, assertions)
    det_ok = all(a["passed"] for a in det)
    judge: dict[str, Any] | None = None
    rubric = expected.get("rubric")
    if rubric:
        judge = run_llm_judge(artifact, str(rubric), model, timeout, backend)
    judge_ok = judge is None or judge["verdict"] == "pass"
    return {"passed": det_ok and judge_ok, "assertions": det, "judge": judge}


# ---------------------------------------------------------------------------
# Dispatch helper
# ---------------------------------------------------------------------------
def _dispatch(
    backend: str,
    system_prompt: str,
    user_input: str,
    model: str,
    timeout: int,
) -> str:
    """Route to the chosen live backend."""
    if backend == "api":
        return invoke_via_api(system_prompt, user_input, model, timeout)
    return invoke_via_cli(system_prompt, user_input, model, timeout)


# ---------------------------------------------------------------------------
# Eval runner
# ---------------------------------------------------------------------------
def run_label_eval(
    rows: list[dict[str, Any]],
    system_prompt: str,
    agent_cfg: dict[str, Any],
    *,
    self_test: bool,
    timeout: int,
    backend: str,
) -> list[dict[str, Any]]:
    """Execute label-mode eval over rows and return per-row result records."""
    axes: list[str] = agent_cfg["label_axes"]
    input_field: str = agent_cfg["input_field"]
    expected_field: str = agent_cfg.get("expected_field", "expected")
    # The model's returned JSON may nest its label axes under a sub-object
    # (pt-classifier's S4 contract puts them under "expected"); None = top level.
    response_label_field: str | None = agent_cfg.get("response_label_field")
    model: str = agent_cfg["model"]
    derive_flag: bool = bool(agent_cfg.get("derive_outcome"))

    row_results: list[dict[str, Any]] = []
    for row in rows:
        row_id = row.get("id", "?")
        expected = row.get(expected_field, {})
        parse_error: str | None = None
        if self_test:
            # Feed the row's own expected labels back through the scorer.
            predicted: dict[str, Any] = {axis: bool(expected.get(axis)) for axis in axes}
        else:
            user_input = str(row.get(input_field, ""))
            # A single unparseable/failed model reply is a WRONG answer for that
            # row, not a reason to abort the whole eval. Record it and move on.
            try:
                reply = _dispatch(backend, system_prompt, user_input, model, timeout)
                raw = extract_json_object(reply)
                predicted = _extract_labels(raw, response_label_field)
            except ModelInvocationError as exc:
                logger.warning("Row %s: model invocation/parse failed: %s", row_id, exc)
                predicted = {}
                parse_error = str(exc)

        score = score_label_row(predicted, expected, axes)
        record: dict[str, Any] = {
            "id": row_id,
            "input": row.get(input_field, ""),
            "predicted": predicted,
            "score": score,
        }
        if parse_error:
            record["parse_error"] = parse_error
        if derive_flag:
            record["expected_outcome"] = derive_outcome(expected)
            record["predicted_outcome"] = derive_outcome(predicted)
        row_results.append(record)
    return row_results


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------
def print_report(agent: str, mode: str, row_results: list[dict], aggregate: dict) -> None:
    """Print a human-readable per-row + aggregate report to stdout."""
    print(f"\n=== Agent eval: {agent}  (mode={mode}) ===")
    for r in row_results:
        mark = "PASS" if r["score"]["passed"] else "FAIL"
        detail = ""
        if "predicted_outcome" in r:
            oc = "ok" if r["predicted_outcome"] == r["expected_outcome"] else "MISS"
            detail = f"  outcome[{oc}] exp={r['expected_outcome']} got={r['predicted_outcome']}"
        print(f"  [{mark}] {r['id']}{detail}")
        if not r["score"]["passed"]:
            for axis, cell in r["score"]["per_axis"].items():
                if not cell["correct"]:
                    print(f"         axis {axis}: expected {cell['expected']} got {cell['predicted']}")

    print("\n  --- Aggregate ---")
    print(f"  rows={aggregate['rows']} passed={aggregate['passed']} accuracy={aggregate['accuracy']:.2%}")
    if "outcome_accuracy" in aggregate:
        print(f"  outcome_accuracy={aggregate['outcome_accuracy']:.2%}")
    for axis, stats in aggregate.get("per_axis", {}).items():
        print(
            f"  axis {axis:16s} precision={stats['precision']:.2f} "
            f"recall={stats['recall']:.2f} f1={stats['f1']:.2f} "
            f"(tp={stats['tp']} fp={stats['fp']} fn={stats['fn']} tn={stats['tn']})"
        )


def write_results(results_path: Path, payload: dict[str, Any]) -> None:
    """Write the full results payload to JSON. Raises EvalDataError on I/O error."""
    try:
        results_path.parent.mkdir(parents=True, exist_ok=True)
        results_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    except OSError as exc:
        logger.exception("Cannot write results to %s", results_path)
        msg = f"Cannot write results to {results_path}"
        raise EvalDataError(msg) from exc


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a gold-set eval for a pipeline agent.")
    parser.add_argument("--agent", required=True, help="Agent key in agent_eval_config.json")
    parser.add_argument(
        "--config",
        default=None,
        help="Path to eval config (default: scripts/evals/agent_eval_config.json)",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Feed each row's own expected labels through the scorer (no model call); proves the pipeline.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Only run the first N rows (0 = all).")
    parser.add_argument("--timeout", type=int, default=120, help="Per-row model timeout (seconds).")
    parser.add_argument("--results-file", default=None, help="Where to write the JSON results file.")
    parser.add_argument("--json", action="store_true", help="Also print the raw results JSON to stdout.")
    return parser


def _load_run_inputs(args: argparse.Namespace, repo_root: Path) -> tuple[dict, list[dict], str]:
    """Load config, agent block, eval rows, and system prompt. Raises on failure."""
    config_path = (
        Path(args.config) if args.config else repo_root / "scripts/evals/agent_eval_config.json"
    )
    config = load_config(config_path)
    agent_cfg = get_agent_config(config, args.agent)
    eval_path = repo_root / agent_cfg["eval_set"]
    template_path = repo_root / agent_cfg["template"]
    rows = load_eval_rows(eval_path)
    if args.limit:
        rows = rows[: args.limit]
    system_prompt = load_system_prompt(template_path)
    return agent_cfg, rows, system_prompt


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    repo_root = find_repo_root()

    try:
        agent_cfg, rows, system_prompt = _load_run_inputs(args, repo_root)
    except EvalHarnessError:
        logger.exception("Setup failed")
        return 2

    mode = agent_cfg.get("scoring_mode", "label")
    backend = choose_backend()
    threshold = float(agent_cfg.get("threshold", 0.0))

    if mode != "label":
        logger.error(
            "scoring_mode '%s' is not runnable yet (artifact mode is scaffolded, no active consumer)",
            mode,
        )
        return 2

    try:
        row_results = run_label_eval(
            rows,
            system_prompt,
            agent_cfg,
            self_test=args.self_test,
            timeout=args.timeout,
            backend=backend,
        )
    except EvalHarnessError:
        logger.exception("Eval run failed")
        return 2

    aggregate = aggregate_label(
        row_results,
        agent_cfg["label_axes"],
        bool(agent_cfg.get("derive_outcome")),
    )

    label = f"{mode}{' (self-test)' if args.self_test else ''}"
    print_report(args.agent, label, row_results, aggregate)

    eval_rel = str((repo_root / agent_cfg["eval_set"]).relative_to(repo_root))
    payload = {
        "agent": args.agent,
        "mode": mode,
        "self_test": args.self_test,
        "backend": None if args.self_test else backend,
        "model": None if args.self_test else agent_cfg.get("model"),
        "eval_set": eval_rel,
        "threshold": threshold,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "aggregate": aggregate,
        "rows": row_results,
    }

    default_name = f"{args.agent}{'-selftest' if args.self_test else ''}.json"
    results_path = (
        Path(args.results_file)
        if args.results_file
        else repo_root / "scripts/evals/results" / default_name
    )
    write_results(results_path, payload)
    print(f"\n  results -> {results_path}")

    if args.json:
        print(json.dumps(payload, indent=2))

    score = aggregate["accuracy"]
    if score < threshold:
        print(f"\n  GATE: FAIL — accuracy {score:.2%} < threshold {threshold:.2%}")
        return 1
    print(f"\n  GATE: PASS — accuracy {score:.2%} >= threshold {threshold:.2%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
