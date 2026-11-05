"""
MODULE: unit_tests/_shared/_bo4500b3_support.py
GOAL: Shared helpers for the BO-4500b-3 family: render the COMMIT-ANSWER block exactly as the
    install does, then evaluate its decision with node and NO workflow engine.

CONTRACT PINNED BY THESE TESTS (field names provisional in the AC; fixed here so the coder has one
target):
  * Block source:  templates/workflows-js/_shared/commit-answer.js
  * Marker pair:   ``// COMMIT-ANSWER-START`` / ``// COMMIT-ANSWER-END`` (same grammar as
                   WORKSPACE-ANSWER).
  * The filled block defines ``decideCommitAnswer(reply, history)`` and returns a decision object
        {decision, specialist, paths, message_file, status, reason_code, reason, hook_name,
         failing_files, answers, received, truncated, envelope_status, answer_status,
         contract_violation, offending_field, offending_value, message, history}
    where ``history`` is the NEXT attempt history. The function calls no engine primitive and
    reads no file: it is evaluated here with ``new Function`` so any ``agent``/``log``/``require``
    use raises and turns the decision into an error.
  * Attempt history: {first_paths, first_message_file, answers, transient_retries_used,
    specialist_engaged, specialist, specialist_reply}. ``specialist_reply`` is set (and ``reply``
    is null) when the decision follows the engaged specialist's report.
  * Install-time values: the install reads ``config/commit_step.json`` of the package root
    (answer_version, reason_codes, max_transient_retries) and resolves them into the block.
"""

from __future__ import annotations

import copy
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build_phases  # noqa: E402

BLOCK_SOURCE = REPO_ROOT / "templates" / "workflows-js" / "_shared" / "commit-answer.js"
REAL_CONFIG = REPO_ROOT / "config" / "commit_step.json"
START = "// COMMIT-ANSWER-START"
END = "// COMMIT-ANSWER-END"
ROUTE_TEMPLATE = f"// fixture route\n{START}\n{END}\nconsole.log('route');\n"
SPECIALIST = "code-refactoring-specialist"
FIRST_PATHS = ["scripts/x.py", "unit_tests/test_x.py"]
FIRST_MESSAGE_FILE = ".pending/commit-msg.txt"

_NODE_DRIVER = r"""
const fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const out = (o) => { process.stdout.write(JSON.stringify(o)); };
try {
  const a = input.text.indexOf(input.start);
  const b = input.text.indexOf(input.end);
  if (a === -1 || b === -1 || b < a) { out({decision: null, error: 'marker pair missing'}); process.exit(0); }
  const block = input.text.slice(a + input.start.length, b);
  if (!block.trim()) { out({decision: null, error: 'marker pair is empty (block not filled)'}); process.exit(0); }
  const fn = new Function(block + '\n;return (typeof decideCommitAnswer === "function") ? decideCommitAnswer : null;')();
  if (!fn) { out({decision: null, error: 'decideCommitAnswer is not defined by the block'}); process.exit(0); }
  const res = fn(input.reply, input.history);
  out(res === undefined ? {decision: null, error: 'decision was undefined'} : res);
} catch (e) {
  out({decision: null, error: 'block raised: ' + String(e && e.message || e)});
}
"""


@dataclass
class Installed:
    text: str | None
    error: BaseException | None
    target: Path
    template_text: str


def real_config() -> dict[str, Any]:
    """Load the shipped config/commit_step.json."""
    return json.loads(REAL_CONFIG.read_text(encoding="utf-8"))


def render_block(tmp_path: Path, monkeypatch, mutate: Callable[[dict], None] | None = None,
                 extra_config: dict[str, Any] | None = None) -> Installed:
    """Install a fixture route carrying an empty COMMIT-ANSWER pair via the REAL phase."""
    pkg = tmp_path / "pkg"
    wf = pkg / "templates" / "workflows-js"
    (wf / "_shared").mkdir(parents=True, exist_ok=True)
    (pkg / "config").mkdir(exist_ok=True)
    cfg = copy.deepcopy(real_config())
    if mutate is not None:
        mutate(cfg)
    (pkg / "config" / "commit_step.json").write_text(json.dumps(cfg, indent=2), encoding="utf-8")
    if BLOCK_SOURCE.is_file():
        (wf / "_shared" / "commit-answer.js").write_bytes(BLOCK_SOURCE.read_bytes())
    (wf / "commit-route.js").write_text(ROUTE_TEMPLATE, encoding="utf-8")
    monkeypatch.setattr(build_phases, "TEMPLATES_DIR", pkg / "templates")
    monkeypatch.setattr(build_phases, "PACKAGE_ROOT", pkg)
    monkeypatch.setenv("CLAUDE_CODE_VERSION", "2.5.0")
    target = tmp_path / "target"
    config: dict[str, Any] = {"workflows": {"enabled": True}}
    config.update(extra_config or {})
    error: BaseException | None = None
    try:
        build_phases.build_workflow_scripts(target, config, dry_run=False, force=True)
    except (Exception, SystemExit) as exc:  # noqa: BLE001 - the failure IS the observable
        error = exc
    route = target / "workflows" / "commit-route.js"
    text = route.read_text(encoding="utf-8") if route.is_file() else None
    return Installed(text=text, error=error, target=target, template_text=ROUTE_TEMPLATE)


def decide(installed_text: str | None, reply: Any, history: dict) -> dict:
    """Evaluate the installed block's decision with node and no engine."""
    if installed_text is None:
        return {"decision": None, "error": "no installed route"}
    payload = json.dumps({"text": installed_text, "start": START, "end": END,
                          "reply": reply, "history": history})
    try:
        done = subprocess.run(["node", "-e", _NODE_DRIVER], input=payload, capture_output=True,
                              text=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return {"decision": None, "error": f"node failed: {exc}"}
    try:
        out = json.loads(done.stdout)
    except ValueError:
        return {"decision": None, "error": f"unparseable node output: {done.stdout[:200]} {done.stderr[:200]}"}
    return out if isinstance(out, dict) else {"decision": None, "error": f"non-object decision: {out!r}"}


def fresh_history(paths: list[str] | None = None, message_file: str | None = FIRST_MESSAGE_FILE) -> dict:
    """Return the attempt history of a first attempt (nothing retried, nobody engaged)."""
    return {"first_paths": list(FIRST_PATHS if paths is None else paths),
            "first_message_file": message_file, "answers": [], "transient_retries_used": 0,
            "specialist_engaged": False, "specialist": None, "specialist_reply": None}


def commit_answer(status: str, reason_code: str | None = None, **over: Any) -> dict:
    """Build a commit_answer from the shipped answer_keys, with status/reason_code and overrides."""
    ca = copy.deepcopy(real_config()["answer_keys"])
    ca.update({"status": status, "reason_code": reason_code, "answer_version": 1})
    if status == "committed":
        ca.update({"sha": "a" * 40, "paths": list(FIRST_PATHS)})
    ca.update(over)
    return ca


def handoff_payload(target: str = SPECIALIST, disposition: str = "engage-specialist",
                    demand: Any = "default") -> dict:
    """Build a remedy_handoff.py-shaped handoff; ``demand`` defaults to a usable one-record list."""
    if isinstance(demand, str) and demand == "default":
        demand = [{"function": "f", "complexity": 31, "limit": 25}]
    return {"status": "handoff", "handoff_target": target, "record_handoff_target": "python-coder",
            "flips_signed_off": False, "message": "complexity over limit",
            "remedy": {"hook_id": "check-complexity", "disposition": disposition,
                       "skills": ["complexity-reduction"], "demand": demand}}


def hook_failed_with_handoff(target: str = SPECIALIST, disposition: str = "engage-specialist",
                             demand: Any = "default") -> dict:
    """Build a hook_failed commit_answer carrying a handoff (optionally not engageable)."""
    handoff = handoff_payload(target, disposition, demand)
    return commit_answer("hook_failed", "check_failed", reason="check-complexity failed",
                         hook_name="check-complexity", failing_files=["scripts/x.py"],
                         hook_output="complexity 31 > 25", handoff=handoff, remedy=handoff["remedy"])


def envelope(ca: dict) -> dict:
    """Wrap a commit_answer in the {status, commit_answer, earlier_answers} reply envelope."""
    if ca["status"] == "committed":
        status = "ok"
    elif ca["status"] == "hook_failed" and ca.get("handoff"):
        status = "handoff"
    else:
        status = "blocker"
    return {"status": status, "commit_answer": ca, "earlier_answers": []}


def run_sequence(text: str | None, answers: list[dict], history: dict | None = None) -> tuple[list[dict], dict]:
    """Feed envelopes of ``answers`` in turn, threading the history each decision returns."""
    hist = history if history is not None else fresh_history()
    decisions: list[dict] = []
    for ca in answers:
        d = decide(text, envelope(ca), hist)
        decisions.append(d)
        nxt = d.get("history")
        hist = nxt if isinstance(nxt, dict) else hist
    return decisions, hist


def names(decisions: list[dict]) -> list[Any]:
    """Return the decision name of each decision, in order."""
    return [d.get("decision") for d in decisions]
