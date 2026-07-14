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
      Artifact mode (mock-data-author, flow-author) copies the product-truth store
      into a throwaway /tmp sandbox, invokes the WRITE-capable agent there (cwd =
      sandbox, LEAFCUTTER_REPO_ROOT = sandbox, tools ENABLED, --append-system-prompt
      = the agent template, permissions bypassed) so every write lands in the
      sandbox, then scores the produced *.mock.json / *.flow.json with the
      deterministic assertions of TQ-200a-2-ii — schema-valid, entities-in-registry,
      EXTEND-not-duplicate (single canonical dataset; the product-truth validator
      does NOT check this), referenced-records-exist, one acceptance_scenario per
      step AND per branch, id path-stable — plus a DELTA validator gate (the run may
      introduce no NEW product-truth validator errors vs the reconciled baseline,
      robust to a store a concurrent session is mid-editing) and an optional per-row
      LLM-judge rubric. The sandbox is discarded after scoring. --score-gold feeds
      the gold artifact through the scorer without a model call (proves the scorer).
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
# - 2026-07-14 [artifact-mode]: Implemented ARTIFACT scoring end-to-end and wired
#   mock-data-author + flow-author into the config. Each row runs in a per-row /tmp
#   sandbox copy of docs/product-truth; the agent is invoked live via the `claude`
#   CLI with WRITE tools enabled and --append-system-prompt = its template (NOT
#   --system-prompt: replacing the base prompt strips the working-directory/env
#   context and the tool framing, so the agent's writes never land — the append
#   form keeps them and was the one real wiring fix needed). Deterministic
#   assertions (TQ-200a-2-ii) are the gate; extend-not-duplicate is checked here
#   because the product-truth validator does not. validator_clean is a DELTA gate
#   (no NEW errors vs the reconciled baseline) so a store mid-edited by a peer does
#   not false-fail a good run; the sandbox baseline registry is normalized to cover
#   entities already present so a peer's transient registry gap is not charged to
#   the agent. Live result: both agents 3/3 (golden + held-out + negative).
# ====================================================================
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("run_agent_eval")

# jsonschema is a HARD dependency for ARTIFACT scoring (schema-validity is a gate
# assertion in TQ-200a-2-ii). It is imported guarded so LABEL mode still runs on a
# host without it; artifact mode raises EvalConfigError up front when it is absent
# (never a silent warn-and-skip — a missing package must not disable a gate).
try:
    import jsonschema
except ImportError:
    jsonschema = None  # type: ignore[assignment]


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


# ===========================================================================
# ARTIFACT MODE — sandboxed live agent run + deterministic assertion scoring
# ===========================================================================
# These agents WRITE files (a *.mock.json / *.flow.json plus an index.json
# registration, then they regenerate derived data). A concurrent session may be
# editing the real store, so every row runs in a throwaway /tmp sandbox that is a
# COPY of the product-truth store: the agent's cwd is the sandbox and
# LEAFCUTTER_REPO_ROOT points at it, so all writes land in the sandbox and are
# scored there, then discarded. Nothing ever writes into the real worktree store.
#
# The gate is the deterministic assertions of TQ-200a-2-ii: schema-valid, every
# entity in the entity_registry, EXTEND-not-duplicate (no second canonical dataset
# for an entity a component already owns), referenced records resolve, one
# acceptance_scenario per step AND per branch, ids path-stable. An optional
# LLM-judge rubric is a secondary gate (row-level `rubric`), never a substitute.

_ARTIFACT_EXT = {"mock": ".mock.json", "flow": ".flow.json"}
_STORE_REL = "docs/product-truth"
_GENERATE_REL = "docs/product-truth/scripts/generate_product_truth.py"
_VALIDATE_REL = "docs/product-truth/scripts/validate_product_truth.py"


def _store_dir(sandbox: Path) -> Path:
    """The product-truth store root inside a sandbox. Pure path join."""
    return sandbox / _STORE_REL


def make_sandbox(repo_root: Path, copy_dirs: list[str]) -> Path:
    """Create a /tmp sandbox and copy each repo-relative dir into it. I/O boundary."""
    try:
        sandbox = Path(tempfile.mkdtemp(prefix="lc_eval_"))
    except OSError as exc:
        logger.exception("Cannot create sandbox tempdir")
        msg = "Cannot create sandbox tempdir"
        raise EvalDataError(msg) from exc
    for rel in copy_dirs:
        src = repo_root / rel
        dst = sandbox / rel
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        except OSError as exc:
            logger.exception("Cannot copy %s into sandbox", src)
            msg = f"Cannot copy {src} into sandbox"
            raise EvalDataError(msg) from exc
    return sandbox


def discard_sandbox(sandbox: Path) -> None:
    """Remove a sandbox tree, best-effort. I/O boundary (logs, never raises)."""
    try:
        shutil.rmtree(sandbox, ignore_errors=True)
    except OSError as exc:  # pragma: no cover - ignore_errors makes this rare
        logger.warning("Could not remove sandbox %s: %s", sandbox, exc)


def _run_pt_script(sandbox: Path, script_rel: str, args: list[str], timeout: int) -> subprocess.CompletedProcess:
    """Run a product-truth script inside the sandbox (cwd=sandbox). I/O boundary."""
    cmd = [sys.executable, str(sandbox / script_rel), *args]
    try:
        return subprocess.run(  # noqa: S603 - fixed argv, no shell
            cmd,
            capture_output=True,
            text=True,
            cwd=str(sandbox),
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        logger.exception("%s timed out after %ss", script_rel, timeout)
        msg = f"{script_rel} timed out after {timeout}s"
        raise ModelInvocationError(msg) from exc
    except OSError as exc:
        logger.exception("Could not launch %s", script_rel)
        msg = f"Could not launch {script_rel}"
        raise ModelInvocationError(msg) from exc


def reconcile_store(sandbox: Path, timeout: int = 180) -> None:
    """Run the generator once so the copied store's derived data is self-consistent.

    The real store may be mid-edit (a concurrent session), so its derived indexes
    can be stale. Reconciling gives a tight baseline for the delta-validator gate.
    A non-zero exit is tolerated (logged) — the delta check absorbs any residual.
    """
    proc = _run_pt_script(sandbox, _GENERATE_REL, ["--quiet"], timeout)
    if proc.returncode != 0:
        logger.info("reconcile generate returned %s (tolerated): %s", proc.returncode, (proc.stderr or "").strip()[:200])


def validator_errors(sandbox: Path, timeout: int = 180) -> set[str]:
    """Return the set of validator ERROR lines (the 'FAIL: ' payloads) for the store."""
    proc = _run_pt_script(sandbox, _VALIDATE_REL, ["--quiet"], timeout)
    prefix = "FAIL: "
    return {ln[len(prefix):] for ln in (proc.stderr or "").splitlines() if ln.startswith(prefix)}


def _read_json(path: Path) -> Any:
    """Read + parse a JSON file. I/O boundary (log + typed raise)."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        logger.exception("Cannot read %s", path)
        msg = f"Cannot read {path}"
        raise EvalDataError(msg) from exc
    except json.JSONDecodeError as exc:
        logger.exception("Invalid JSON in %s", path)
        msg = f"Invalid JSON in {path}"
        raise EvalDataError(msg) from exc


def _write_json(path: Path, obj: Any) -> None:
    """Write an object as pretty JSON. I/O boundary (log + typed raise)."""
    try:
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError as exc:
        logger.exception("Cannot write %s", path)
        msg = f"Cannot write {path}"
        raise EvalDataError(msg) from exc


def apply_sandbox_prep(sandbox: Path, prep: dict[str, Any]) -> None:
    """Apply per-row sandbox preparation (e.g. remove a gold artifact to reproduce).

    `remove_artifacts` deletes each named artifact's file AND drops its index
    `artifacts[]` entry, so a GOLDEN row can force the agent to reverse-engineer
    (recreate) an artifact from its inputs rather than find it already present.
    """
    remove_ids = list(prep.get("remove_artifacts", []))
    if not remove_ids:
        return
    store = _store_dir(sandbox)
    patterns = ("flows/**/*.flow.json", "mock-data/**/*.mock.json", "mockups/**/*.mockup.json")
    for pattern in patterns:
        for path in store.glob(pattern):
            obj = _read_json(path)
            if isinstance(obj, dict) and obj.get("id") in remove_ids:
                try:
                    path.unlink()
                except OSError as exc:
                    logger.exception("Cannot remove %s", path)
                    msg = f"Cannot remove {path}"
                    raise EvalDataError(msg) from exc
    index_path = store / "index.json"
    index = _read_json(index_path)
    index["artifacts"] = [a for a in index.get("artifacts", []) if a.get("id") not in remove_ids]
    _write_json(index_path, index)


def normalize_baseline_registry(store: Path) -> None:
    """Sandbox-only: ensure entity_registry covers every entity already in copied artifacts.

    The real store may be mid-edit by a concurrent session (an entity used by an
    artifact but not yet added to the registry). Without this, a PRE-EXISTING gap
    would fail the per-artifact `entities_in_registry` assertion for content the
    agent under test never touched — a false negative. This unions the entities
    already present in the copied mocks/flows into the registry so the BASELINE is
    self-consistent. It never removes anything and runs BEFORE the agent, so a
    genuinely agent-invented entity (absent from the baseline) is still caught.
    """
    index_path = store / "index.json"
    index = _read_json(index_path)
    registry = list(index.get("entity_registry", []))
    present = set(registry)
    for path in store.glob("mock-data/**/*.mock.json"):
        obj = _read_json(path)
        present.update(obj.get("entities", {}).keys())
    for path in store.glob("flows/**/*.flow.json"):
        obj = _read_json(path)
        present.update(obj.get("entities", []))
    missing = sorted(present - set(registry))
    if missing:
        index["entity_registry"] = registry + missing
        _write_json(index_path, index)
        logger.info("normalized baseline registry with %s", missing)


def snapshot_artifacts(store: Path) -> dict[str, str]:
    """Map each flow/mock file (store-relative) to a content hash. I/O boundary."""
    snap: dict[str, str] = {}
    for pattern in ("flows/**/*.flow.json", "mock-data/**/*.mock.json"):
        for path in store.glob(pattern):
            try:
                data = path.read_bytes()
            except OSError as exc:
                logger.exception("Cannot read %s", path)
                msg = f"Cannot read {path}"
                raise EvalDataError(msg) from exc
            snap[str(path.relative_to(store))] = hashlib.sha256(data).hexdigest()
    return snap


def load_store_view(store: Path) -> dict[str, Any]:
    """Load the artifacts the assertions reason over: mocks, flows, screens, registry."""
    mocks: dict[str, dict] = {}
    for path in store.glob("mock-data/**/*.mock.json"):
        obj = _read_json(path)
        mocks[obj["id"]] = obj
    flows: dict[str, dict] = {}
    for path in store.glob("flows/**/*.flow.json"):
        obj = _read_json(path)
        flows[obj["id"]] = obj
    screens: set[str] = set()
    for path in store.glob("mockups/**/*.mockup.json"):
        obj = _read_json(path)
        if obj.get("screen"):
            screens.add(obj["screen"])
    index = _read_json(store / "index.json")
    return {
        "mocks": mocks,
        "flows": flows,
        "screens": screens,
        "registry": set(index.get("entity_registry", [])),
    }


def invoke_agent_writer(
    system_prompt: str,
    user_input: str,
    model: str,
    timeout: int,
    sandbox: Path,
    tools: str,
) -> str:
    """Run a WRITE-capable agent headlessly in the sandbox and return its reply.

    Uses --append-system-prompt (NOT --system-prompt): the agent's template is
    appended to Claude Code's base prompt so the run keeps the working-directory /
    environment context and tool framing it needs to actually write files. cwd is
    the sandbox and LEAFCUTTER_REPO_ROOT points at it, so writes stay contained.
    Permissions are bypassed because the sandbox is a throwaway /tmp copy.
    """
    cmd = [
        "claude",
        "-p",
        user_input,
        "--model",
        model,
        "--append-system-prompt",
        system_prompt,
        "--tools",
        tools,
        "--permission-mode",
        "bypassPermissions",
        "--output-format",
        "json",
    ]
    env = dict(os.environ, LEAFCUTTER_REPO_ROOT=str(sandbox))
    try:
        completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(sandbox),
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        logger.exception("agent CLI timed out after %ss", timeout)
        msg = f"agent CLI timed out after {timeout}s"
        raise ModelInvocationError(msg) from exc
    except OSError as exc:
        logger.exception("agent CLI could not be launched")
        msg = "agent CLI could not be launched"
        raise ModelInvocationError(msg) from exc

    if completed.returncode != 0:
        msg = f"agent CLI exited {completed.returncode}: {(completed.stderr or '').strip()[:400]}"
        raise ModelInvocationError(msg)
    try:
        envelope = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        logger.exception("agent CLI returned non-JSON envelope")
        msg = "agent CLI returned non-JSON envelope"
        raise ModelInvocationError(msg) from exc
    result = envelope.get("result")
    if not isinstance(result, str):
        msg = "agent CLI envelope has no string 'result'"
        raise ModelInvocationError(msg)
    return result


def _parse_report(reply: str) -> dict[str, Any]:
    """Best-effort parse of the agent's completion-report JSON. Pure; never raises."""
    try:
        return extract_json_object(reply)
    except ModelInvocationError:
        return {}


def determine_target(
    snap_before: dict[str, str],
    snap_after: dict[str, str],
    artifact_type: str,
) -> dict[str, Any]:
    """Classify what the agent changed. Pure function.

    Returns the produced artifact's store-relative path + inferred action, plus the
    added/modified file lists (the ground truth for create-vs-extend and the
    extend-not-duplicate assertions). A matching-type ADDED file means CREATE; a
    matching-type MODIFIED file means EXTEND.
    """
    ext = _ARTIFACT_EXT[artifact_type]
    added = sorted(f for f in snap_after if f not in snap_before)
    modified = sorted(f for f in snap_after if f in snap_before and snap_after[f] != snap_before[f])
    matching_added = [f for f in added if f.endswith(ext)]
    matching_modified = [f for f in modified if f.endswith(ext)]
    target_rel: str | None = None
    action: str | None = None
    if matching_added:
        target_rel, action = matching_added[0], "create"
    elif matching_modified:
        target_rel, action = matching_modified[0], "extend"
    return {
        "target_rel": target_rel,
        "action": action,
        "added": added,
        "modified": modified,
        "matching_added": matching_added,
        "matching_modified": matching_modified,
    }


def _id_from_path(target_rel: str, ext: str) -> str:
    """Derive the path-stable id '<product>/<name>' from a store-relative file path."""
    parts = Path(target_rel).parts
    product = parts[-2] if len(parts) >= 2 else ""
    name = Path(target_rel).name[: -len(ext)]
    return f"{product}/{name}"


# ---- deterministic assertion checks (pure over the built context) ----------
def _a_schema_valid(ctx: dict, spec: dict) -> tuple[bool, str]:
    obj = ctx.get("target_obj")
    schema = ctx.get("schema")
    if obj is None:
        return False, "no artifact produced"
    if schema is None:
        return False, "no schema configured"
    try:
        jsonschema.validate(obj, schema)
    except jsonschema.ValidationError as exc:
        return False, f"schema: {exc.message}"
    return True, "schema-valid"


def _a_entities_in_registry(ctx: dict, spec: dict) -> tuple[bool, str]:
    obj, registry = ctx.get("target_obj"), ctx["registry"]
    if obj is None:
        return False, "no artifact produced"
    if ctx["artifact_type"] == "mock":
        names = list(obj.get("entities", {}).keys())
    else:
        names = list(obj.get("entities", []))
        for node in _iter_flow_nodes(obj):
            names.extend(node.get("reads", []) + node.get("writes", []))
    missing = sorted({n for n in names if n not in registry})
    return (not missing), ("all entities in registry" if not missing else f"not in registry: {missing}")


def _a_single_canonical_dataset(ctx: dict, spec: dict) -> tuple[bool, str]:
    entity, component = spec["entity"], spec["component"]
    owners = [
        mid
        for mid, mock in ctx["mocks"].items()
        if mock.get("component") == component and entity in mock.get("entities", {})
    ]
    ok = len(owners) == 1
    return ok, f"canonical {entity}@{component} datasets = {sorted(owners)}"


def _a_no_new_file(ctx: dict, spec: dict) -> tuple[bool, str]:
    added = ctx["matching_added"]
    return (not added), (f"no new {ctx['ext']} created" if not added else f"NEW file(s): {added}")


def _a_new_file_created(ctx: dict, spec: dict) -> tuple[bool, str]:
    added = ctx["matching_added"]
    return bool(added), (f"created {added}" if added else f"no new {ctx['ext']} was created")


def _a_id_equals(ctx: dict, spec: dict) -> tuple[bool, str]:
    obj = ctx.get("target_obj")
    if obj is None:
        return False, "no artifact produced"
    actual = obj.get("id")
    return (actual == spec["id"]), f"id={actual!r} expected {spec['id']!r}"


def _a_id_path_stable(ctx: dict, spec: dict) -> tuple[bool, str]:
    obj, target_rel = ctx.get("target_obj"), ctx.get("target_rel")
    if obj is None or target_rel is None:
        return False, "no artifact produced"
    expected = _id_from_path(target_rel, ctx["ext"])
    actual = obj.get("id")
    return (actual == expected), f"id={actual!r} vs path-derived {expected!r}"


def _a_referenced_records_exist(ctx: dict, spec: dict) -> tuple[bool, str]:
    obj = ctx.get("target_obj")
    if obj is None:
        return False, "no artifact produced"
    entities = obj.get("entities", {})
    plant_ids = {r.get("id") for r in entities.get("Plant", {}).get("records", [])}
    customer_ids = {r.get("id") for r in entities.get("Customer", {}).get("records", [])}
    order_ids = {r.get("id") for r in entities.get("Order", {}).get("records", [])}
    problems: list[str] = []
    for order in entities.get("Order", {}).get("records", []):
        if plant_ids and order.get("item") not in plant_ids:
            problems.append(f"Order {order.get('id')} item {order.get('item')!r} unresolved")
        if customer_ids and order.get("customer") not in customer_ids:
            problems.append(f"Order {order.get('id')} customer {order.get('customer')!r} unresolved")
    for pay in entities.get("Payment", {}).get("records", []):
        if order_ids and pay.get("order") not in order_ids:
            problems.append(f"Payment {pay.get('id')} order {pay.get('order')!r} unresolved")
    return (not problems), ("all FKs resolve" if not problems else "; ".join(problems))


def _iter_flow_nodes(flow: dict):
    """Yield every step and branch dict of a flow. Pure."""
    yield from flow.get("steps", [])
    yield from flow.get("branches", [])


def _a_scenario_per_node(ctx: dict, spec: dict) -> tuple[bool, str]:
    obj = ctx.get("target_obj")
    if obj is None:
        return False, "no artifact produced"
    node_ids = {node["id"] for node in _iter_flow_nodes(obj)}
    scenario_fors = [s.get("for") for s in obj.get("acceptance_scenarios", [])]
    covered = set(scenario_fors)
    missing = sorted(node_ids - covered)
    dangling = sorted(f for f in scenario_fors if f not in node_ids)
    if missing or dangling:
        return False, f"missing scenarios for {missing}; dangling scenario fors {dangling}"
    return True, f"one scenario per node ({len(node_ids)} nodes)"


def _a_steps_ordered(ctx: dict, spec: dict) -> tuple[bool, str]:
    obj = ctx.get("target_obj")
    if obj is None:
        return False, "no artifact produced"
    orders = [s.get("order") for s in obj.get("steps", [])]
    if any(not isinstance(o, int) for o in orders):
        return False, f"non-integer order values: {orders}"
    if len(set(orders)) != len(orders):
        return False, f"duplicate order values: {orders}"
    return True, f"steps uniquely ordered {sorted(orders)}"


def _a_screens_resolve(ctx: dict, spec: dict) -> tuple[bool, str]:
    obj = ctx.get("target_obj")
    if obj is None:
        return False, "no artifact produced"
    screens = ctx["screens"]
    unresolved = sorted(
        node["screen"]
        for node in _iter_flow_nodes(obj)
        if node.get("screen") and node["screen"] not in screens
    )
    return (not unresolved), ("all screens resolve" if not unresolved else f"unresolved screens: {unresolved}")


def _a_has_branch(ctx: dict, spec: dict) -> tuple[bool, str]:
    obj = ctx.get("target_obj")
    if obj is None:
        return False, "no artifact produced"
    count = len(obj.get("branches", []))
    minimum = int(spec.get("min", 1))
    return (count >= minimum), f"branches={count} (need >= {minimum})"


def _a_mock_data_ref_resolves(ctx: dict, spec: dict) -> tuple[bool, str]:
    obj = ctx.get("target_obj")
    if obj is None:
        return False, "no artifact produced"
    ref = obj.get("mock_data_ref")
    if not ref:
        return False, "no mock_data_ref set"
    return (ref in ctx["mocks"]), f"mock_data_ref {ref!r} {'resolves' if ref in ctx['mocks'] else 'MISSING'}"


def _a_validator_clean(ctx: dict, spec: dict) -> tuple[bool, str]:
    new_errors = ctx["validator_new_errors"]
    return (not new_errors), (
        "no new validator errors" if not new_errors else f"{len(new_errors)} NEW error(s): {sorted(new_errors)[:3]}"
    )


_ASSERTIONS = {
    "schema_valid": _a_schema_valid,
    "entities_in_registry": _a_entities_in_registry,
    "single_canonical_dataset": _a_single_canonical_dataset,
    "no_new_file": _a_no_new_file,
    "new_file_created": _a_new_file_created,
    "id_equals": _a_id_equals,
    "id_path_stable": _a_id_path_stable,
    "referenced_records_exist": _a_referenced_records_exist,
    "scenario_per_node": _a_scenario_per_node,
    "steps_ordered": _a_steps_ordered,
    "screens_resolve": _a_screens_resolve,
    "has_branch": _a_has_branch,
    "mock_data_ref_resolves": _a_mock_data_ref_resolves,
    "validator_clean": _a_validator_clean,
}


def evaluate_artifact_assertions(ctx: dict, assertions: list[dict]) -> list[dict]:
    """Run every configured deterministic assertion. Pure over the built context."""
    results: list[dict[str, Any]] = []
    for spec in assertions:
        kind = spec.get("kind")
        checker = _ASSERTIONS.get(kind)
        if checker is None:
            results.append({"kind": kind, "passed": False, "detail": f"unknown assertion kind {kind!r}"})
            continue
        passed, detail = checker(ctx, spec)
        results.append({"kind": kind, "passed": passed, "detail": detail})
    return results


def build_artifact_context(
    store: Path,
    artifact_type: str,
    schema: dict | None,
    target_info: dict,
    validator_new_errors: set[str],
) -> dict[str, Any]:
    """Assemble the read-only context the pure assertion checks reason over."""
    view = load_store_view(store)
    target_rel = target_info.get("target_rel")
    target_obj = None
    if target_rel is not None:
        target_obj = _read_json(store / target_rel)
    return {
        "artifact_type": artifact_type,
        "ext": _ARTIFACT_EXT[artifact_type],
        "schema": schema,
        "target_rel": target_rel,
        "target_obj": target_obj,
        "matching_added": target_info.get("matching_added", []),
        "matching_modified": target_info.get("matching_modified", []),
        "validator_new_errors": validator_new_errors,
        **view,
    }


def score_artifact_context(
    ctx: dict,
    expected: dict[str, Any],
    model: str,
    timeout: int,
    backend: str,
) -> dict[str, Any]:
    """Score a built artifact context: deterministic assertions AND optional judge."""
    assertions = expected.get("assertions", [])
    det = evaluate_artifact_assertions(ctx, assertions)
    det_ok = all(a["passed"] for a in det)
    judge: dict[str, Any] | None = None
    rubric = expected.get("rubric")
    if rubric and ctx.get("target_obj") is not None:
        artifact_text = json.dumps(ctx["target_obj"], indent=2, ensure_ascii=False)
        judge = run_llm_judge(artifact_text, str(rubric), model, timeout, backend)
    judge_ok = judge is None or judge["verdict"] == "pass"
    return {"passed": det_ok and judge_ok, "assertions": det, "judge": judge}


def check_eval_set_complete(rows: list[dict[str, Any]], expected_field: str) -> tuple[bool, str]:
    """TQ-200a-4 — an eval set is INCOMPLETE unless it has >= 1 negative case. Pure."""
    negatives = [r.get("id", "?") for r in rows if r.get(expected_field, {}).get("negative")]
    if negatives:
        return True, f"negative case(s): {negatives}"
    return False, "no negative/failure case (TQ-200a-4 requires >= 1)"


def run_artifact_row(
    row: dict[str, Any],
    system_prompt: str,
    agent_cfg: dict[str, Any],
    repo_root: Path,
    schema: dict | None,
    *,
    timeout: int,
    score_gold: bool,
) -> dict[str, Any]:
    """Execute (or gold-score) one artifact row in a fresh sandbox and score it."""
    input_field = agent_cfg["input_field"]
    expected_field = agent_cfg.get("expected_field", "expected")
    copy_dirs = agent_cfg.get("sandbox_copy", [_STORE_REL])
    expected = row.get(expected_field, {})
    row_id = row.get("id", "?")

    sandbox = make_sandbox(repo_root, copy_dirs)
    record: dict[str, Any] = {"id": row_id, "input": row.get(input_field, ""), "negative": bool(expected.get("negative"))}
    try:
        _populate_artifact_record(
            record,
            sandbox,
            row,
            expected,
            agent_cfg,
            schema,
            system_prompt,
            timeout=timeout,
            score_gold=score_gold,
        )
    except ModelInvocationError as exc:
        logger.warning("Row %s: %s", row_id, exc)
        record["score"] = {"passed": False, "assertions": [], "judge": None}
        record["error"] = str(exc)
    finally:
        discard_sandbox(sandbox)
    return record


def _populate_artifact_record(
    record: dict[str, Any],
    sandbox: Path,
    row: dict[str, Any],
    expected: dict[str, Any],
    agent_cfg: dict[str, Any],
    schema: dict | None,
    system_prompt: str,
    *,
    timeout: int,
    score_gold: bool,
) -> None:
    """Run (or gold-score) one row into `record`. Raises ModelInvocationError on run failure."""
    store = _store_dir(sandbox)
    artifact_type = agent_cfg["artifact_type"]
    model = agent_cfg["model"]
    if score_gold:
        record.update(_score_gold_row(sandbox, store, expected, artifact_type, schema, model, timeout))
        return

    tools = agent_cfg.get("tools", "Read,Write,Edit,Bash")
    user_input = str(row.get(agent_cfg["input_field"], ""))
    if expected.get("sandbox_prep"):
        apply_sandbox_prep(sandbox, expected["sandbox_prep"])
    normalize_baseline_registry(store)
    reconcile_store(sandbox)
    before_errors = validator_errors(sandbox)
    snap_before = snapshot_artifacts(store)

    reply = invoke_agent_writer(system_prompt, user_input, model, timeout, sandbox, tools)
    record["report"] = _parse_report(reply)

    snap_after = snapshot_artifacts(store)
    target_info = determine_target(snap_before, snap_after, artifact_type)
    new_errors = validator_errors(sandbox) - before_errors

    ctx = build_artifact_context(store, artifact_type, schema, target_info, new_errors)
    record["action"] = target_info.get("action")
    record["target"] = target_info.get("target_rel")
    record["score"] = score_artifact_context(ctx, expected, model, timeout, choose_backend())


def _score_gold_row(
    sandbox: Path,
    store: Path,
    expected: dict[str, Any],
    artifact_type: str,
    schema: dict | None,
    model: str,
    timeout: int,
) -> dict[str, Any]:
    """Scorer self-proof: score the row's GOLD artifact as if the agent produced it.

    Used only when live invocation is unavailable (or as an independent check of
    the scorer itself): a correct gold artifact should satisfy every file-intrinsic
    assertion (~100%). File-delta assertions (no_new_file / new_file_created) are
    not applicable without a run and are reported as skipped.
    """
    gold_rel = expected.get("gold_target")
    if not gold_rel:
        return {"score": {"passed": False, "assertions": [], "judge": None}, "skipped": "no gold_target"}
    normalize_baseline_registry(store)
    reconcile_store(sandbox)
    before_errors = validator_errors(sandbox)
    target_info = {
        "target_rel": gold_rel,
        "action": "gold",
        "matching_added": [],
        "matching_modified": [],
    }
    ctx = build_artifact_context(store, artifact_type, schema, target_info, set())
    ctx["validator_new_errors"] = validator_errors(sandbox) - before_errors
    delta_kinds = {"no_new_file", "new_file_created"}
    assertions = [a for a in expected.get("assertions", []) if a.get("kind") not in delta_kinds]
    det = evaluate_artifact_assertions(ctx, assertions)
    skipped = [a["kind"] for a in expected.get("assertions", []) if a.get("kind") in delta_kinds]
    return {
        "action": "gold",
        "target": gold_rel,
        "skipped_assertions": skipped,
        "score": {"passed": all(a["passed"] for a in det), "assertions": det, "judge": None},
    }


def run_artifact_eval(
    rows: list[dict[str, Any]],
    system_prompt: str,
    agent_cfg: dict[str, Any],
    repo_root: Path,
    *,
    timeout: int,
    score_gold: bool,
) -> list[dict[str, Any]]:
    """Execute artifact-mode eval over rows; each row runs in its own sandbox."""
    schema: dict | None = None
    schema_name = agent_cfg.get("schema")
    if schema_name:
        schema = _read_json(repo_root / _STORE_REL / "schemas" / schema_name)
    results: list[dict[str, Any]] = []
    for row in rows:
        if score_gold and not row.get(agent_cfg.get("expected_field", "expected"), {}).get("gold_target"):
            continue
        logger.info("Running artifact row %s ...", row.get("id", "?"))
        results.append(
            run_artifact_row(
                row,
                system_prompt,
                agent_cfg,
                repo_root,
                schema,
                timeout=timeout,
                score_gold=score_gold,
            )
        )
    return results


def aggregate_artifact(row_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate artifact rows: pass rate + per-assertion-kind tallies. Pure."""
    total = len(row_results)
    passed = sum(1 for r in row_results if r["score"]["passed"])
    per_kind: dict[str, dict[str, int]] = {}
    for r in row_results:
        for a in r["score"].get("assertions", []):
            bucket = per_kind.setdefault(a["kind"], {"pass": 0, "total": 0})
            bucket["total"] += 1
            if a["passed"]:
                bucket["pass"] += 1
    return {
        "rows": total,
        "passed": passed,
        "accuracy": round(passed / total, 4) if total else 0.0,
        "per_assertion": dict(sorted(per_kind.items())),
    }


def print_artifact_report(agent: str, mode: str, row_results: list[dict], aggregate: dict) -> None:
    """Human-readable artifact-mode report."""
    print(f"\n=== Agent eval: {agent}  (mode={mode}) ===")
    for r in row_results:
        mark = "PASS" if r["score"]["passed"] else "FAIL"
        neg = " [negative]" if r.get("negative") else ""
        extra = f" action={r.get('action')} target={r.get('target')}" if r.get("target") else ""
        print(f"  [{mark}] {r['id']}{neg}{extra}")
        if r.get("error"):
            print(f"         error: {r['error']}")
        for a in r["score"].get("assertions", []):
            amark = "ok " if a["passed"] else "XXX"
            print(f"         [{amark}] {a['kind']}: {a['detail']}")
        if r.get("skipped_assertions"):
            print(f"         skipped (gold mode): {r['skipped_assertions']}")
        if r["score"].get("judge"):
            j = r["score"]["judge"]
            print(f"         judge: {j['verdict']} ({j['score']}) — {j['reasoning']}")
    print("\n  --- Aggregate ---")
    print(f"  rows={aggregate['rows']} passed={aggregate['passed']} accuracy={aggregate['accuracy']:.2%}")
    for kind, stat in aggregate.get("per_assertion", {}).items():
        print(f"  assertion {kind:26s} {stat['pass']}/{stat['total']}")


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
    parser.add_argument(
        "--row",
        action="append",
        default=None,
        help="Only run the row(s) with these id(s) (repeatable). Completeness is still checked "
        "against the full set. Useful for cheaply re-running a single artifact row.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=0,
        help="Per-row timeout in seconds (0 = mode default: 120 label, config/900 artifact).",
    )
    parser.add_argument(
        "--score-gold",
        action="store_true",
        help="ARTIFACT mode: skip the agent run and score each row's gold_target artifact "
        "as if the agent produced it (proves the scorer; expects ~100%%).",
    )
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
    system_prompt = load_system_prompt(template_path)
    return agent_cfg, rows, system_prompt


def _emit_results(args: argparse.Namespace, repo_root: Path, payload: dict[str, Any], suffix: str) -> None:
    """Write the results payload and optionally echo it. Shared by both modes."""
    default_name = f"{args.agent}{suffix}.json"
    results_path = (
        Path(args.results_file) if args.results_file else repo_root / "scripts/evals/results" / default_name
    )
    write_results(results_path, payload)
    print(f"\n  results -> {results_path}")
    if args.json:
        print(json.dumps(payload, indent=2))


def _gate(score: float, threshold: float) -> int:
    """Print the CI gate line and return the process exit code. Pure-ish (prints)."""
    if score < threshold:
        print(f"\n  GATE: FAIL — score {score:.2%} < threshold {threshold:.2%}")
        return 1
    print(f"\n  GATE: PASS — score {score:.2%} >= threshold {threshold:.2%}")
    return 0


def _run_label_mode(args: argparse.Namespace, agent_cfg: dict, rows: list[dict], system_prompt: str, repo_root: Path) -> int:
    backend = choose_backend()
    threshold = float(agent_cfg.get("threshold", 0.0))
    timeout = args.timeout or 120
    if args.row:
        wanted = set(args.row)
        rows = [r for r in rows if r.get("id") in wanted]
    if args.limit:
        rows = rows[: args.limit]
    try:
        row_results = run_label_eval(
            rows, system_prompt, agent_cfg, self_test=args.self_test, timeout=timeout, backend=backend
        )
    except EvalHarnessError:
        logger.exception("Eval run failed")
        return 2
    aggregate = aggregate_label(row_results, agent_cfg["label_axes"], bool(agent_cfg.get("derive_outcome")))
    print_report(args.agent, f"label{' (self-test)' if args.self_test else ''}", row_results, aggregate)
    payload = {
        "agent": args.agent,
        "mode": "label",
        "self_test": args.self_test,
        "backend": None if args.self_test else backend,
        "model": None if args.self_test else agent_cfg.get("model"),
        "eval_set": agent_cfg["eval_set"],
        "threshold": threshold,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "aggregate": aggregate,
        "rows": row_results,
    }
    _emit_results(args, repo_root, payload, "-selftest" if args.self_test else "")
    return _gate(aggregate["accuracy"], threshold)


def _run_artifact_mode(args: argparse.Namespace, agent_cfg: dict, rows: list[dict], system_prompt: str, repo_root: Path) -> int:
    if jsonschema is None:
        logger.error(
            "jsonschema is required for ARTIFACT scoring (schema-validity is a gate assertion) "
            "but is not installed. Install it (pip install -r requirements-dev.txt). Refusing to run."
        )
        return 2
    expected_field = agent_cfg.get("expected_field", "expected")
    complete, msg = check_eval_set_complete(rows, expected_field)
    if not complete:
        # TQ-200a-4: an eval set with no negative case is reported INCOMPLETE, not passing.
        logger.error("Eval set INCOMPLETE for %s: %s", args.agent, msg)
        return 2
    logger.info("Eval set completeness OK: %s", msg)

    threshold = float(agent_cfg.get("threshold", 0.0))
    timeout = args.timeout or int(agent_cfg.get("timeout", 900))
    if args.row:
        wanted = set(args.row)
        rows = [r for r in rows if r.get("id") in wanted]
    if args.limit:
        rows = rows[: args.limit]
    try:
        row_results = run_artifact_eval(
            rows, system_prompt, agent_cfg, repo_root, timeout=timeout, score_gold=args.score_gold
        )
    except EvalHarnessError:
        logger.exception("Eval run failed")
        return 2
    if not row_results:
        logger.error("No artifact rows were scored (score-gold with no gold_target rows?)")
        return 2
    aggregate = aggregate_artifact(row_results)
    print_artifact_report(args.agent, f"artifact{' (score-gold)' if args.score_gold else ''}", row_results, aggregate)
    payload = {
        "agent": args.agent,
        "mode": "artifact",
        "score_gold": args.score_gold,
        "backend": choose_backend(),
        "model": agent_cfg.get("model"),
        "eval_set": agent_cfg["eval_set"],
        "threshold": threshold,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "aggregate": aggregate,
        "rows": row_results,
    }
    _emit_results(args, repo_root, payload, "-scoregold" if args.score_gold else "")
    return _gate(aggregate["accuracy"], threshold)


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
    if mode == "artifact":
        return _run_artifact_mode(args, agent_cfg, rows, system_prompt, repo_root)
    if mode == "label":
        return _run_label_mode(args, agent_cfg, rows, system_prompt, repo_root)
    logger.error("Unknown scoring_mode %r for agent %s", mode, args.agent)
    return 2


if __name__ == "__main__":
    sys.exit(main())
