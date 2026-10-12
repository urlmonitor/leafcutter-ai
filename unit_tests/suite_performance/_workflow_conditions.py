"""The ``if:`` / ``${{ }}`` expression evaluator of the TQ-600a-13 workflow executor.

Split out of ``_workflow_jobs.py`` (file-size limit). Test infrastructure, not a test.

Grammar: ``always()``, ``success()``, ``failure()``, ``cancelled()``, ``!`` negation,
``==`` / ``!=`` against a literal, ``&&`` / ``||`` (no parentheses), over the contexts
``steps.<id>.outputs.<k>``, ``steps.<id>.outcome|conclusion``, ``needs.<job>.result``,
``needs.<job>.outputs.<k>``, ``github.<sha|ref|event_name|run_id|repository>``, ``github.event.<path>`` (read from the event file),
``runner.name``, ``env.<K>``, ``job.status``. Anything outside it FAILS with
:class:`HarnessError`; the evaluator never guesses.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

_STATUS_FUNCTIONS = ("always()", "success()", "failure()", "cancelled()")
_EXPRESSION = re.compile(r"\$\{\{\s*(.*?)\s*\}\}", re.S)
_COMPARISON = re.compile(r"^(\S+)\s*(==|!=)\s*(.+)$")
_GITHUB_KEYS = {
    "sha": "GITHUB_SHA",
    "ref": "GITHUB_REF",
    "event_name": "GITHUB_EVENT_NAME",
    "run_id": "GITHUB_RUN_ID",
    "repository": "GITHUB_REPOSITORY",
    "api_url": "GITHUB_API_URL",  # TQ-600a-13-vi: the hold job reads these three from env, never from event text
    "token": "GITHUB_TOKEN",
    "event_path": "GITHUB_EVENT_PATH",
}


class HarnessError(AssertionError):
    """The harness could not do what it was asked -- distinct from the code under test being wrong."""


def _fail(message, cause=None):
    raise HarnessError(message) from cause


@dataclass
class _Context:
    env: dict
    steps: dict = field(default_factory=dict)
    needs: dict = field(default_factory=dict)
    status: str = "success"
    cancelled: bool = False  # the whole run was cancelled: only status-agnostic steps (always(), cancelled()) still run


def _event_field(keys, ctx):
    """``github.event.<a>.<b>...`` read from the JSON event file at ``GITHUB_EVENT_PATH`` (TQ-600a-13-xvi: the head SHA)."""
    try:
        node = json.loads(Path(ctx.env.get("GITHUB_EVENT_PATH", "")).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return _fail(f"github.event.{'.'.join(keys)}: the event file is unreadable: {exc}", exc)
    for key in keys:
        node = node.get(key) if isinstance(node, dict) else None
    return "" if node is None else node


def _lookup(path, ctx):
    parts = path.split(".")
    head = parts[0]
    if head == "github" and len(parts) > 2 and parts[1] == "event":
        return _event_field(parts[2:], ctx)
    if head == "steps" and len(parts) in (3, 4):
        step = ctx.steps.get(parts[1])
        if step is None:
            return ""
        if parts[2] == "outputs" and len(parts) == 4:
            return step["outputs"].get(parts[3], "")
        if parts[2] in ("outcome", "conclusion") and len(parts) == 3:
            return step[parts[2]]
    elif head == "needs" and len(parts) in (3, 4):
        need = ctx.needs.get(parts[1])
        if need is None:
            _fail(f"expression reads needs.{parts[1]} but that job is not a declared dependency")
        if parts[2] == "result" and len(parts) == 3:
            return need.conclusion
        if parts[2] == "outputs" and len(parts) == 4:
            return need.outputs.get(parts[3], "")
    elif head == "github" and len(parts) == 2 and parts[1] in _GITHUB_KEYS:
        return ctx.env.get(_GITHUB_KEYS[parts[1]], "")
    elif head == "runner" and parts[1:] == ["name"]:
        return ctx.env.get("RUNNER_NAME", "")
    elif head == "env" and len(parts) == 2:
        return ctx.env.get(parts[1], "")
    elif head == "job" and parts[1:] == ["status"]:
        return ctx.status
    return _fail(f"the executor cannot evaluate the context expression {path!r}")


def _expand(text, ctx):
    return _EXPRESSION.sub(lambda m: str(_lookup(m.group(1), ctx)), str(text))


def _literal(token):
    token = token.strip()
    if len(token) >= 2 and token[0] == token[-1] == "'":
        return token[1:-1]
    if token in ("true", "false", "null"):
        return {"true": "true", "false": "false", "null": ""}[token]
    if re.fullmatch(r"-?\d+(\.\d+)?", token):
        return token
    return _fail(f"the executor cannot evaluate the literal {token!r} in an if: expression")


def _atom(text, ctx):
    text = text.strip()
    if text.startswith("!"):
        return not _atom(text[1:], ctx)
    if text == "always()":
        return True
    if text == "success()":
        return ctx.status == "success"
    if text == "failure()":
        return ctx.status == "failure"
    if text == "cancelled()":
        return ctx.cancelled
    match = _COMPARISON.match(text)
    if match:
        equal = str(_lookup(match.group(1), ctx)) == _literal(match.group(3))
        return equal if match.group(2) == "==" else not equal
    if re.fullmatch(r"[A-Za-z_][\w.]*", text):
        return str(_lookup(text, ctx)) not in ("", "false", "0")
    return _fail(f"the executor cannot evaluate the if: expression fragment {text!r}")


def condition_holds(condition, ctx):
    """Evaluate an ``if:``; like the hosting service, an ``if`` with no status function implies ``success()``."""
    if condition is None:
        return ctx.status == "success"
    expr = str(condition).strip()
    wrapped = re.fullmatch(r"\$\{\{(.*)\}\}", expr, re.S)
    if wrapped:
        expr = wrapped.group(1).strip()
    if "(" in expr.replace("always()", "").replace("success()", "").replace("failure()", "").replace("cancelled()", ""):
        _fail(f"the executor does not support parentheses in the if: expression {expr!r}")
    result = any(all(_atom(a, ctx) for a in part.split("&&")) for part in expr.split("||"))
    has_status = any(fn in expr for fn in _STATUS_FUNCTIONS)
    return result if has_status else (result and ctx.status == "success")
