"""
MODULE: unit_tests/workflows/_tq500g1viii_fixtures.py
GOAL: Shared stubs and readers for the TQ-500g-1-viii workflow tests: driving the TEMPLATE
    templates/workflows-js/build-epic.js (never a deployed copy) through its new drive-head recover, its
    per-ticket gate marker, and the one-ticket-per-chunk rule for a batch that owes wrong-version runs.
BUSINESS CONTEXT: build-epic.js hands every ticket to ticket-supervisor, which drives the phases up to and
    including commit. The new command steps (recover, close-all, open, close) go to ``command-step-runner`` as
    ``JSON.stringify({step, command, target: {workspace, run_id}})`` and are answered with the executor's
    ``{exit_status, stdout, stderr}``. The engine harness, its concurrent parallel() and the reply builders are
    REUSED from the TQ-500g-1-vi fixtures; this module adds only the epic table, the pinned labels and commands.
PINNED DISPATCH LABELS (AC TQ-500g-1-viii): ``be-wv-recover`` and ``be-gate-marker-close-all`` once at the drive
    head, ``be-gate-marker-open`` before and ``be-gate-marker-close`` after each ticket-supervisor dispatch.
PINNED COMMANDS (AC, word for word; ``{{config.output_root}}`` is left as the template has it):
    python "<root>"/{{config.output_root}}/scripts/build_orchestration/<script>.py <args>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import workflows._tq500g1v_fixtures as v  # noqa: E402
import workflows._tq500g1vi_fixtures as vi  # noqa: E402

BUILD_EPIC = vi.JS_DIR / "build-epic.js"
WT = "/tmp/wv-viii-worktree"
EPIC = "tickets/00_inbox/epics/EPIC-WvViii"
RECOVER, CLOSE_ALL, OPEN, CLOSE = "be-wv-recover", "be-gate-marker-close-all", "be-gate-marker-open", "be-gate-marker-close"
PLANNER = "epic-planner"
EXECUTOR = v.EXECUTOR
SENTINEL = vi.SENTINEL
SCRIPTS = '{{config.output_root}}/scripts/build_orchestration'
RECORDS = "gate_verdict_records"


def command(script: str, args: str, root: str = WT) -> str:
    return f'python "{root}"/{SCRIPTS}/{script}.py {args}'


def open_command(key: str, path: str, root: str = WT) -> str:
    return command(RECORDS, f'open --worktree "{root}" --ticket-key "{key}" --ticket-path "{path}"', root)


def close_command(key: str, root: str = WT) -> str:
    return command(RECORDS, f'close --worktree "{root}" --ticket-key "{key}"', root)


def close_all_command(root: str = WT) -> str:
    return command(RECORDS, f'close --all --worktree "{root}"', root)


def recover_command(root: str = WT) -> str:
    return command("wrong_version_runner", "recover", root)


def ticket(n: int, source_ac=SENTINEL, *, stem: str | None = None) -> dict:
    """A planner item; ``source_ac`` SENTINEL omits the key (the planner forgot it)."""
    item = {"path": f"{WT}/{EPIC}/0{n}_{stem or f'wv_ticket_{n}'}.md", "status": "todo"}
    if source_ac is not SENTINEL:
        item["source_ac"] = source_ac
    return item


def key_of(item: dict) -> str:
    return Path(item["path"]).stem


def opened(ok: bool = True) -> dict:
    return v.ran({"opened": ok, "ticket_key": "x", "marker": "open.json"}, 0 if ok else 1)


def labels(batches: list[list[dict]], overrides: dict | None = None) -> dict:
    """Label table for one drive of *batches*: every command step passes, every ticket-supervisor answers ok."""
    table = {
        PLANNER: {"epic_path": EPIC, "title": "EPIC-WvViii",
                  "batches": [{"batch_number": n + 1, "tickets": items} for n, items in enumerate(batches)]},
        RECOVER: v.recover_reply(),
        CLOSE_ALL: v.ran({"closed": [], "ok": True}),
        OPEN: opened(),
        CLOSE: v.ran({"closed": True}),
    }
    for items in batches:
        for item in items:
            table[f"ticket:{item['path']}"] = {"status": "ok", "message": "committed", "ticket_path": item["path"]}
    table.update(overrides or {})
    return table


def run_epic(batches: list[list[dict]], overrides: dict | None = None):
    return vi.run_script(BUILD_EPIC, labels(batches, overrides), {"epic_path": EPIC, "worktree_path": WT})


labels_of, calls, command_of, request_of = vi.labels_of, vi.calls, vi.command_of, vi.request_of


def executor_calls(result) -> list:
    return [c for c in result.agent_calls if c.agent_type == EXECUTOR]


def supervisor_calls(result) -> list:
    return [c for c in result.agent_calls if c.agent_type == "ticket-supervisor"]


def index_of(result, label: str, key: str | None = None) -> int:
    """Index of the dispatch under *label* whose executor request names run_id *key* (any when None)."""
    for i, c in enumerate(result.agent_calls):
        if c.label == label and (key is None or request_of(c)["target"]["run_id"] == key):
            return i
    msg = f"no {label!r} dispatch for {key!r}; recorded labels: {labels_of(result)}"
    raise AssertionError(msg)


def prompt_field(call, name: str) -> str | None:
    """The value of a ``name: value`` field in a dispatch prompt (stops at whitespace or a full stop at end)."""
    match = re.search(rf"\b{name}:\s*([^\s]+?)\.?(?:\s|$)", str(call.prompt))
    return match.group(1) if match else None


def blocked_keys(result) -> dict:
    out = result.result or {}
    return {k: out.get(k) for k in ("status", "gate", "wrong_version_step", "wrong_version_detail", "marker_step", "marker_detail")}


def halted(result) -> list[dict]:
    return list((result.result or {}).get("halted_tickets") or [])
