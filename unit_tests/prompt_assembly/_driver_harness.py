"""Shared helpers for the behavioral driver tests.

Every test that uses this module EXECUTES a real workflow driver script
(templates/workflows-js/build-feature.js or build-ticket.js) through
``harness_build_ticket_guard.mjs`` and asserts on what the run did:
which agents it dispatched, which records it read back, and what the
ticket .md files on disk say afterwards.

This module deliberately provides no assertion helpers that read the
driver *source*. Per CLAUDE.md "Gate / Workflow ACs — Verify Behaviorally,
Not by Grep", a source-reading assertion passes on a guard that is computed
and then ignored, which is the exact failure this repository shipped in
fast-lane-build.js.

Ticket records are REAL files: the frontmatter is produced by
``yaml.safe_dump`` (the real serializer), not hand-typed, per the
fixture-authenticity rule in CLAUDE.md.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile

import yaml

from _driver_outcome_readers import *  # noqa: F403 -- re-export of the outcome readers

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))

HARNESS = os.path.join(_THIS_DIR, "harness_build_ticket_guard.mjs")
BUILD_FEATURE_JS = os.path.join(
    REPO_ROOT, "templates", "workflows-js", "build-feature.js"
)
BUILD_TICKET_JS = os.path.join(
    REPO_ROOT, "templates", "workflows-js", "build-ticket.js"
)

#: The two twin drivers. Their file headers declare them twins that must stay
#: in sync, so an AC whose it_requirements names ``n_location_rule: 2`` is
#: asserted against both.
TWIN_DRIVERS = {
    "build-feature.js": BUILD_FEATURE_JS,
    "build-ticket.js": BUILD_TICKET_JS,
}


# ---------------------------------------------------------------------------
# Canonical phase set — parsed from the driver so a newly added gate is picked
# up automatically. This is PARAMETERIZATION, not an assertion: nothing here
# is asserted against the source text; the values only decide which phases the
# scenario drives.
# ---------------------------------------------------------------------------

def canonical_phase_order(script_path: str = BUILD_FEATURE_JS) -> list[str]:
    """Return the driver's phaseOrder array, used to parameterize scenarios."""
    with open(script_path, encoding="utf-8") as fh:
        source = fh.read()
    match = re.search(r"const phaseOrder = \[(.*?)\n\];", source, re.DOTALL)
    if not match:
        return []
    return re.findall(r'"([a-z0-9-]+)"', match.group(1))


#: Phases that are dispatchable as ordinary gates in a scenario. Excludes
#: pull-request (dropped for epic members by selectDispatchPhases) and
#: status-checker (the planner's own agentType).
def dispatchable_gates(script_path: str = BUILD_FEATURE_JS) -> list[str]:
    return [
        p
        for p in canonical_phase_order(script_path)
        if p not in {"status-checker", "pull-request"}
    ]


# ---------------------------------------------------------------------------
# Real ticket records
# ---------------------------------------------------------------------------

SIGNOFF_RE = re.compile(
    r"^###\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}\s+—\s+([A-Za-z0-9_-]+)\s+"
    r"\(status:\s*([A-Za-z_]+)\s*\)\s*$",
    re.MULTILINE,
)


def write_ticket_record(
    worktree_dir: str,
    name: str,
    phases,
    *,
    title: str | None = None,
    status: str = "todo",
    seeded_signoffs=(),
    subdir: str = os.path.join("tickets", "01_todo"),
    agent_statuses=None,
    omit_agents: bool = False,
    extra_frontmatter=None,
) -> str:
    """Write a real ticket .md and return its absolute path.

    ``phases`` are recorded in the frontmatter agents: map as ``needed``.
    ``agent_statuses`` overrides that per agent (e.g. ``signed_off``), which is
    how a scenario expresses a ticket that carries no needed phase at all.
    ``seeded_signoffs`` is an iterable of ``(agent, status)`` pairs already
    present in the record before the drive starts. An entry may instead be a
    3-tuple ``(agent, status, handoff_target)`` (BO-400e-1-i) to additionally
    emit a ``handoff_target: <name>`` line in that entry's own comment body —
    the on-disk shape ``harness_build_ticket_guard.mjs``'s ``parseRecord()``
    reads back and attaches to that specific signoff entry. Omit the third
    element (or pass a falsy value for it) for an entry that names no
    recipient; every existing 2-tuple caller emits byte-identical output to
    before this was added.

    ``omit_agents`` (BO-400a-2-iv) leaves the ``agents:`` key OUT of the
    frontmatter entirely, which is the on-disk shape of a ticket that names no
    list of phases at all. It is distinct from ``phases=[]`` (an ``agents: {}``
    map — an empty list rather than no list), and a refusal written against one
    shape does not cover the other. Default False, so every existing caller
    produces the same bytes as before.

    ``extra_frontmatter`` (BO-1900a-4-ii) is an ordered mapping of additional
    frontmatter keys written AFTER the agents: map. Default None, so every
    existing caller produces the same bytes as before.

    It exists because of a fidelity limit in harness_build_ticket_guard.mjs:
    its parseRecord() collects the agents: block with
    ``/^agents:\\n([\\s\\S]*?)(?=^\\S|\\Z)/m``, and JavaScript has no ``\\Z``
    escape — ``\\Z`` there matches a literal "Z". The lookahead therefore only
    terminates on a following line that starts at column 0, so an agents: map
    that is the LAST key in the frontmatter is not matched at all and the
    record reports ``needed_phases: []`` to the driver. A test that needs the
    driver to actually SEE a record naming needed phases must place a key after
    the map. Real tickets always do (component, files_touched, source_ac, …),
    so the trailing key is authentic rather than a workaround artifact.

    Fixing the .mjs regex instead would change what every pre-existing scenario
    presents to the driver — their records would start naming needed phases
    where today they name none — so it is deliberately NOT done here.

    The frontmatter is serialized by yaml.safe_dump — the real producer —
    so the record the driver reads back has authentic on-disk shape.
    """
    target_dir = os.path.join(worktree_dir, subdir)
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, name)

    overrides = agent_statuses or {}
    agent_map = {agent: overrides.get(agent, "needed") for agent in phases}
    # Annotated: the agents map and any extra_frontmatter values are dicts, so
    # inference from these two str values alone would reject them.
    frontmatter: dict = {
        "title": title or name,
        "status": status,
    }
    if not omit_agents:
        frontmatter["agents"] = agent_map
    for key, value in (extra_frontmatter or {}).items():
        frontmatter[key] = value
    fm_text = yaml.safe_dump(frontmatter, sort_keys=False, default_flow_style=False)

    body = [
        "---",
        fm_text.rstrip("\n"),
        "---",
        "",
        f"# {title or name}",
        "",
        "## Sign-offs",
        "",
    ]
    for agent in phases:
        if agent_map[agent] == "signed_off":
            body.append(f"- [x] {agent} — 2026-08-18 09:00")
        else:
            body.append(f"- [ ] {agent}")
    body.extend(["", "## Comments", ""])
    for seeded in seeded_signoffs:
        agent, agent_status, *rest = seeded
        handoff_target = rest[0] if rest else None
        body.append(f"### 2026-08-18 09:00 — {agent} (status: {agent_status})")
        body.append("pre-existing sign-off from an earlier drive")
        if handoff_target:
            body.append(f"handoff_target: {handoff_target}")
        body.append("")

    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(body) + "\n")
    return path


def read_record(path: str) -> dict:
    """Read a ticket record back off disk — the real-artifact round trip."""
    if not os.path.exists(path):
        return {"exists": False, "lifecycle_status": None, "signoffs": []}
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    fm_match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    lifecycle_status = None
    agents: dict[str, str] = {}
    if fm_match:
        try:
            data = yaml.safe_load(fm_match.group(1)) or {}
        except yaml.YAMLError:
            data = {}
        lifecycle_status = data.get("status")
        agents = data.get("agents") or {}
    signoffs = [
        {"agent": m.group(1), "status": m.group(2)} for m in SIGNOFF_RE.finditer(text)
    ]
    return {
        "exists": True,
        "lifecycle_status": lifecycle_status,
        "agents": agents,
        "signoffs": signoffs,
        "signed_off_agents": [s["agent"] for s in signoffs],
        "text": text,
    }


def signoff_count(path: str, agent: str) -> int:
    return sum(1 for s in read_record(path).get("signoffs", []) if s["agent"] == agent)


# ---------------------------------------------------------------------------
# Running a driver
# ---------------------------------------------------------------------------


class HarnessError(RuntimeError):
    """The harness could not execute the driver, or emitted unusable output.

    Carries the full node stdout/stderr so a failing test names the real cause
    instead of a bare non-zero exit.
    """

    summary = "the driver harness failed"

    def __init__(self, script_path="", stdout="", stderr="", returncode=None):
        super().__init__(
            f"{self.summary} (exit {returncode})\n"
            f"  driver: {os.path.basename(script_path) if script_path else '<unknown>'}\n"
            f"  stdout: {stdout}\n"
            f"  stderr: {stderr}"
        )


class HarnessExitError(HarnessError):
    """node exited non-zero — the driver threw before printing observations."""

    summary = "the driver harness exited non-zero"


class HarnessOutputError(HarnessError):
    """node printed something that was not the observation JSON."""

    summary = "the driver harness printed output that was not JSON"


def node_available() -> bool:
    return shutil.which("node") is not None


def run_driver(script_path: str, scenario: dict, timeout: int = 120) -> dict:
    """Execute a real driver script under stubbed workflow globals.

    Returns the harness observation dict:
    ``{dispatched, dispatches, readbacks, writes, enumerations, logs,
       records, result, error}``.
    """
    fd, scenario_path = tempfile.mkstemp(suffix=".json", prefix="driver_scenario_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(scenario, fh)
        proc = subprocess.run(
            ["node", HARNESS, script_path, "@" + scenario_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    finally:
        if os.path.exists(scenario_path):
            os.unlink(scenario_path)

    if proc.returncode != 0:
        raise HarnessExitError(script_path, proc.stdout, proc.stderr, proc.returncode)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - diagnostic path
        raise HarnessOutputError(
            script_path, proc.stdout, proc.stderr, proc.returncode
        ) from exc


# ---------------------------------------------------------------------------
# Scenario builders
# ---------------------------------------------------------------------------


def ready_workspace_reply(worktree_dir: str, branch: str = "feature/harness") -> dict:
    """The shell-runner reply to the ONE ``workspace-ensure`` step (BO-4300c-3): the maker's ok answer as the
    stdout STRING of ``{command, exit_status, stdout, stderr}``, exactly as the real engine delivers it."""
    answer = {
        "schema_version": 1, "status": "ok", "code": "OK", "verb": "ensure",
        "workspace_path": worktree_dir, "worktree_path": worktree_dir, "branch": branch,
        "created": False, "message": "workspace ready (test)",
    }
    return {
        "command": "python3 worktree.py ensure (test)",
        "exit_status": 0,
        "stdout": json.dumps(answer),
        "stderr": "",
    }


def single_ticket_scenario(worktree_dir: str, ticket_path: str, ticket_cfg: dict) -> dict:
    """A scenario that drives ONE ticket, runnable against either twin.

    ``args`` carries both ``target`` (build-feature.js) and ``ticket_path``
    (build-ticket.js) so the same scenario object drives either driver.
    """
    return {
        "record_dir": worktree_dir,
        "args": {
            "target": ticket_path,
            "ticket_path": ticket_path,
            "worktree_path": worktree_dir,
        },
        "resolve": {
            "target_type": "ticket",
            "epic_path": None,
            "ticket_path": ticket_path,
            "worktree_path": worktree_dir,
        },
        "workspace_ensure": ready_workspace_reply(worktree_dir),
        "tickets": {ticket_path: ticket_cfg},
    }


def epic_scenario(
    worktree_dir: str,
    epic_path: str,
    tickets: dict,
    reads: list,
    *,
    title: str = "EPIC-Harness",
) -> dict:
    """A scenario that drives an epic through build-feature.js.

    ``reads`` is the ordered list of epic enumerations: the first is the one
    the plan is built from, any later one is a completion-time re-read.
    """
    return {
        "record_dir": worktree_dir,
        "args": {"target": epic_path, "worktree_path": worktree_dir},
        "resolve": {
            "target_type": "epic",
            "epic_path": epic_path,
            "ticket_path": None,
            "worktree_path": worktree_dir,
        },
        "workspace_ensure": ready_workspace_reply(worktree_dir),
        "epic": {"path": epic_path, "title": title, "reads": reads},
        "tickets": tickets,
    }


def phase_results(spec: dict) -> dict:
    """Expand a compact ``{phase: bool_records}`` map into results entries.

    ``True``  → the phase reports ok AND appends its sign-off (healthy gate)
    ``False`` → the phase reports ok and writes NOTHING (the BUG-23 gate)
    """
    out = {}
    for phase, records in spec.items():
        entry = {"status": "ok", "record": bool(records)}
        if phase == "test-writer":
            entry["tests_written"] = ["unit_tests/harness/test_stub.py"]
            entry["red_baseline_verified"] = True
        out[phase] = entry
    return out


def phase_dispatch_labels(observation: dict) -> list[str]:
    """Phase-agent dispatches only (planner / classifier / record I/O excluded)."""
    return list(observation.get("dispatched") or [])


def phase_dispatches(observation: dict) -> list:
    """Every phase-agent dispatch the run made, with its full prompt and opts.

    Entries carry ``prompt`` (the verbatim dispatch string), ``opts_keys`` and
    ``opts_ticket_path``. Planner, classifier and record-I/O dispatches are not
    included — the harness routes those before this list is appended to.
    """
    return list(observation.get("dispatches") or [])


def readback_count_for(observation: dict, ticket_path: str) -> int:
    return sum(
        1
        for rb in observation.get("readbacks") or []
        if rb.get("ticket_path") == ticket_path
    )


def writes_for(observation: dict, ticket_path: str) -> list:
    return [
        w for w in observation.get("writes") or [] if w.get("ticket_path") == ticket_path
    ]


def harness_parsed_record(observation: dict, ticket_path: str) -> dict:
    """The record as the HARNESS parsed it — what the driver was actually told.

    Distinct from ``read_record()``, which parses the same file with PyYAML.
    The two can disagree: the harness's agents-map regex cannot see a map that
    is the last key in the frontmatter (see ``write_ticket_record``'s
    ``extra_frontmatter``), so a fixture whose .md plainly names needed phases
    can still present the driver with an empty needed set. A scenario that
    depends on the driver seeing needed phases must assert on THIS view.
    """
    return (observation.get("records") or {}).get(ticket_path) or {}


def plan_replies(observation: dict) -> list:
    """Every per-ticket planner reply the harness served, in dispatch order.

    Entries carry ``mode``, ``reply_type``, ``has_ordered_phases`` (an
    own-property check, so an omitted list is distinguishable from an empty
    one) and ``ordered_phases``. Used to prove the reply under test really
    carried the shape the test claims, before asserting what the drive did
    with it.
    """
    return list(observation.get("plan_replies") or [])


ACCEPTED_READBACK_LABELS = (
    "signoff-readback (canonical) — also any label matching read-back / "
    "signoff-verify / verify-signoff / record-check / record-verify / record-read"
)
ACCEPTED_WRITE_LABELS = (
    "ticket-completion-write (canonical) — also any label matching completion / "
    "status-write / mark-done / ticket-done / lifecycle-write / record-done"
)
