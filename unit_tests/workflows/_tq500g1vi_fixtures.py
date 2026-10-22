"""
MODULE: unit_tests/workflows/_tq500g1vi_fixtures.py
GOAL: Shared stubs and readers for the TQ-500g-1-vi workflow tests: driving the TEMPLATES
    templates/workflows-js/build-feature.js and build-ticket.js (never a deployed copy) through the
    wrong-version steps that sit right before the commit dispatch.
BUSINESS CONTEXT: Same sequence as TQ-500g-1-v's fast lane (recover, list, test-breaker, one finish), made by
    the two heavy-lane twins. Reply builders, verdict builders and the real-shell here-document check are
    REUSED from _tq500g1v_fixtures.py; this module adds only what the twins need: the route table, the
    per-route label tables, worktree-fact variants, an epic table, and a harness bootstrap that serves
    ``{"__sequence__": [...]}`` replies in order and runs parallel() thunks concurrently (as the real engine).
PINNED DISPATCH LABELS (AC TQ-500g-1-vi): ``bf-wv-{recover,list,test-breaker,finish}`` in build-feature.js,
    ``bt-wv-*`` in build-ticket.js; phase ``Wrong-Version Runs``; the command steps go to ``command-step-runner``
    as ``JSON.stringify({step, command, target: {workspace, run_id}})`` and are answered with the executor's
    ``{exit_status, stdout, stderr}``; test-breaker is dispatched as agentType ``test-breaker``.
PINNED BEYOND THE AC (the coder must conform; each is the fast lane's own shape):
    * the heavy-lane ticket planner reports ``source_ac`` as an array (the key is omitted when there is none);
    * a recover halt in build-feature.js returns {status: "blocked", gate, wrong_version_step, wrong_version_detail}
      at the TOP LEVEL of the drive's result, with no ticket dispatched (the AC says "the whole drive returns blocked");
    * the epic planner's ticket items carry ``source_ac`` (array, [] when none), as the AC says.
"""

from __future__ import annotations

import json
import re
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest import mock

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import _workflow_engine_harness as harness  # noqa: E402
import workflows._tq500g1v_fixtures as v  # noqa: E402
from unit_tests.workflows import _bo4000_fixtures as bfx  # noqa: E402

JS_DIR = v.REPO_ROOT / "templates" / "workflows-js"
WT = "/tmp/wv-vi-worktree"
STEM = "07_wv_ticket"
AC = v.AC
EPIC = "tickets/00_inbox/epics/EPIC-WvVi"
PHASE = "Wrong-Version Runs"
DEFAULT_PHASES = ("pr-reviewer", "commit")
SENTINEL = object()  # "no override": distinguishes it from an explicit None (a null reply)


@dataclass(frozen=True)
class Route:
    key: str  # "bf" (build-feature.js) | "bt" (build-ticket.js)
    script_name: str

    @property
    def script(self) -> Path:
        return JS_DIR / self.script_name

    def label(self, suffix: str) -> str:
        return f"{self.key}-wv-{suffix}"

    @property
    def recover(self) -> str:
        return self.label("recover")

    @property
    def list(self) -> str:
        return self.label("list")

    @property
    def breaker(self) -> str:
        return self.label("test-breaker")

    @property
    def finish(self) -> str:
        return self.label("finish")

    def args(self, ticket: str, wt: str) -> dict:
        return {"target": ticket} if self.key == "bf" else {"ticket_path": ticket, "worktree_path": wt}


BF, BT = Route("bf", "build-feature.js"), Route("bt", "build-ticket.js")
ROUTES = (BF, BT)
COMMIT, REVIEWER, PLANNER, EPIC_PLANNER = "commit", "pr-reviewer", "ticket-planner", "epic-planner"
STAGE, OBSERVE = "knowledge-routing-step", "knowledge-routing-observe"
SPECIALIST = "restructuring-specialist"


def ticket_path(wt: str = WT, stem: str = STEM, sub: str = "tickets/01_todo") -> str:
    return f"{wt}/{sub}/{stem}.md"


def planner_reply(wt: str, phases, source_ac, stem: str = STEM) -> dict:
    """The heavy-lane ticket planner's reply; ``source_ac`` None omits the key (the planner's convention)."""
    reply: dict = {"ticket_path": ticket_path(wt, stem), "title": "TQ-500g-1-vi fixture ticket",
                   "files_touched": ["scripts/stub_impl.py"], "has_test_requirements": True, "existing_test_files": [],
                   "ordered_phases": [{"agent": a, "status": "needed"} for a in phases]}
    if source_ac is not None:
        reply["source_ac"] = list(source_ac)
    return reply


def wv_replies(route: Route, *, recover=SENTINEL, list_=SENTINEL, breaker=SENTINEL, finish=SENTINEL) -> dict:
    """The four wrong-version replies, all answering "nothing owed / gate passed" unless overridden."""
    pick = lambda given, default: default if given is SENTINEL else given  # noqa: E731
    return {
        route.recover: pick(recover, v.recover_reply()),
        route.list: pick(list_, v.list_reply([])),
        route.breaker: pick(breaker, {"work_key": STEM, "entries": [], "anomalies": []}),
        route.finish: pick(finish, v.finish_reply(v.verdict_f1())),
    }


def green(route: Route, *, wt: str = WT, phases=DEFAULT_PHASES, source_ac=(AC,), stem: str = STEM) -> dict:
    """Label table that drives one ticket (already in an existing worktree) to commit with every step passing."""
    ticket = ticket_path(wt, stem)
    labels: dict[str, Any] = {
        PLANNER: planner_reply(wt, phases, source_ac, stem),
        "signoff-readback": {"readable": True, "lifecycle_status": "todo", "needed_phases": [], "depends_on": [],
                             "signoffs": [], "signed_off_agents": []},
        REVIEWER: {"status": "ok", "message": "clean"},
        COMMIT: {"status": "ok", "message": "committed"},
        **wv_replies(route),
    }
    if route.key == "bf":
        labels["resolve-target"] = {"target_type": "ticket", "ticket_path": ticket, "worktree_path": wt}
        labels["worktree-facts-resolved"] = bfx.envelope(bfx.facts())
    return labels


def worktree_case(kind: str) -> tuple[str, dict]:
    """``(worktree root, label overrides)`` for how build-feature.js comes by its worktree.

    resolved / occupied / setup_reused are RESUMED drives (an existing worktree is reused); created is fresh.
    """
    if kind == "resolved":
        return WT, {}
    base = "/tmp/wv-vi-wtbase"
    identity = f"{STEM}.md"  # the last segment of the ticket target, which names the worktree
    root = f"{base}/{identity}"
    out: dict[str, Any] = {"resolve-target": {"target_type": "ticket", "ticket_path": ticket_path(root), "worktree_path": None},
                           "worktree-base": bfx.base_response(base),
                           "worktree-facts-location": bfx.envelope({"exists": False}),
                           "branch-standing": bfx.branch_standing(exists=False),
                           "worktree-setup": bfx.open_worktree_response(root, "created")}
    if kind == "occupied":  # scenario 2: the location holds a worktree of this repo on the target's own branch
        out["worktree-facts-location"] = bfx.envelope(bfx.facts(branch=identity))
    elif kind == "setup_reused":
        out["worktree-setup"] = bfx.open_worktree_response(root, "reused")
    elif kind != "created":
        raise ValueError(kind)
    return root, out


def epic_labels(items: list[dict], *, phases=DEFAULT_PHASES, ticket_source_ac=(), wt: str = WT) -> dict:
    """Label table for build-feature.js driving one epic batch of *items* ({path, status, source_ac?})."""
    labels = green(BF, wt=wt, phases=phases, source_ac=ticket_source_ac)
    labels["resolve-target"] = {"target_type": "epic", "epic_path": EPIC, "ticket_path": None, "worktree_path": wt}
    labels[EPIC_PLANNER] = {"epic_path": EPIC, "title": "EPIC-WvVi", "already_done": [],
                            "enumerated": [i["path"] for i in items],
                            "batches": [{"batch_number": 1, "tickets": items}]}
    labels["epic-recheck"] = {"readable": True, "epic_path": EPIC, "tickets": [], "ticket_paths": []}
    return labels


def epic_item(n: int, source_ac=SENTINEL, wt: str = WT) -> dict:
    item = {"path": f"{wt}/{EPIC}/0{n}_wv_ticket_{n}.md", "status": "todo"}
    if source_ac is not SENTINEL:
        item["source_ac"] = source_ac
    return item


_SEQ_NEEDLE = "response = __labelResponses__[label];"
_PAR_NEEDLE = "async function parallel(thunksArg, ...rest) {"
_SEQUENCE_JS = (" if (response && typeof response === 'object' && Array.isArray(response.__sequence__))"
                " { var _q = response.__sequence__; response = _q.length > 1 ? _q.shift() : _q[0]; }")
_CONCURRENT_JS = (" if (Array.isArray(thunksArg)) { return await Promise.all(thunksArg.map(async function (fn) {"
                  " try { return await fn(); } catch (_err) { return null; } })); }")


@contextmanager
def engine_like_harness():
    """The E2 harness's agent mock serves ``{"__sequence__": [...]}`` in order (the last repeats) and its
    parallel() starts every thunk at once, as the real engine does (the stock mock awaits them one by one)."""
    src = harness._BOOTSTRAP_SOURCE_JS
    assert _SEQ_NEEDLE in src and _PAR_NEEDLE in src, "harness agent/parallel mock changed shape"
    patched = src.replace(_SEQ_NEEDLE, _SEQ_NEEDLE + _SEQUENCE_JS).replace(_PAR_NEEDLE, _PAR_NEEDLE + _CONCURRENT_JS)
    with mock.patch.object(harness, "_BOOTSTRAP_SOURCE_JS", patched):
        yield


def run_script(script: Path, labels: dict, args: dict, *, timeout: int = 90) -> harness.HarnessResult:
    with engine_like_harness():
        result = harness.run_workflow_under_e2(script, timeout=timeout, label_responses=labels, args=args)
    assert not result.error, result.error
    return result


def run_route(route: Route, overrides: dict | None = None, *, wt: str = WT, phases=DEFAULT_PHASES,
              source_ac=(AC,), stem: str = STEM, case: str | None = None) -> harness.HarnessResult:
    """Run one ticket through *route*'s TEMPLATE with the green table plus *overrides* (label -> reply)."""
    extra: dict = {}
    if case is not None:  # how build-feature.js comes by its worktree (see worktree_case)
        wt, extra = worktree_case(case)
    labels = green(route, wt=wt, phases=phases, source_ac=source_ac, stem=stem)
    labels.update(extra)
    labels.update(overrides or {})
    return run_script(route.script, labels, route.args(ticket_path(wt, stem), wt))


# --- readers over the recorded dispatches ------------------------------------------------------
labels_of, calls, command_of, flag, breaker_input = v.labels_of, v.calls, v.command_of, v.flag, v.breaker_input


def request_of(call) -> dict:
    """The executor request a command step carries: {step, command, target}."""
    return json.loads(call.prompt)


def index_of(result, label: str, nth: int = 0) -> int:
    found = [i for i, c in enumerate(result.agent_calls) if c.label == label]
    assert len(found) > nth, f"no dispatch #{nth} under {label!r}, recorded labels: {labels_of(result)}"
    return found[nth]


def mentions(result, path: str) -> list[int]:
    """Indices of the dispatches whose prompt names *path*."""
    return [i for i, c in enumerate(result.agent_calls) if isinstance(c.prompt, str) and path in c.prompt]


def suffixes(result, route: Route) -> list[str]:
    """The wrong-version dispatch labels recorded, with the route prefix removed (the twins' parity view)."""
    prefix = f"{route.key}-wv-"
    return [c.label[len(prefix):] for c in result.agent_calls if (c.label or "").startswith(prefix)]


def halt_keys(result) -> dict:
    out = result.result or {}
    return {k: out.get(k) for k in ("status", "gate", "wrong_version_step", "wrong_version_detail", "classification")}


def command_script_paths(result) -> list[str]:
    """The repo-relative script paths (``<output root>/scripts/build_orchestration/<x>.py``) the commands name."""
    paths = []
    for c in result.agent_calls:
        if c.agent_type == v.EXECUTOR:
            paths += re.findall(r"(\.[\w-]+/scripts/build_orchestration/\w+\.py)", command_of(c))
    return paths
