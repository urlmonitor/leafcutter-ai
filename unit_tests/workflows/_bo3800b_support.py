"""Shared drive helpers for the BO-3800b tests (refusal -> restructuring specialist).

Every helper EXECUTES the real driver top-level body (build-feature.js /
build-ticket.js, the TWIN_DRIVERS) through the behavioral driver harness and
returns what the run actually dispatched. Nothing here reads driver source.

Fixture authenticity
--------------------
* The ticket record is a real .md written by ``yaml.safe_dump`` (``H.write_ticket_record``).
* The remedy declarations the run is given are lifted VERBATIM from the real
  package seed routing table ``templates/scripts/precommit-autofix.json`` (the
  table the shared GE-132a-1 loader reads), never hand-typed. Only the one
  field a scenario deliberately varies (disposition / agent) is overridden, and
  the override is named at the call site.

Contract the tests pin (decisions the coder must conform to)
-----------------------------------------------------------
* The commit phase reports a refusal as a PHASE_RESULT handoff:
  ``{status: "handoff", handoff_target: <declared party>, remedy: {hook_id,
  disposition, skills, demand}}`` (BO-3800a-2's payload). ``demand`` is a list of
  ``{path, function, score, ceiling, reason}`` (complexity) or
  ``{path, lines_to_remove}`` (file size).
* The depth-0 driver engages a refusal-originated target equal to the
  declaration's specialist even though it is not in the ticket's agents map.
* The specialist's dispatch carries a machine-readable ``opts.brief`` object
  ``{skills: [...], demand: [...]}`` (BO-3800b-3 / BO-3800c-2) that is also
  rendered into its prompt.
* A driver step that reads a remedy declaration uses a dispatch label matching
  ``/remedy|declaration/i``; the harness answers it from the scenario's
  ``remedy_declarations`` and does not count it as an engaged party.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "prompt_assembly"))
sys.path.insert(0, str(_HERE.parent))

import _driver_harness as H  # noqa: E402

SPECIALIST = "restructuring-specialist"
TICKET = "01_ticket.md"
SEED_TABLE = Path(H.REPO_ROOT) / "templates" / "scripts" / "precommit-autofix.json"


def seed_rule(hook_id: str) -> dict:
    """The real seed declaration for ``hook_id`` (read, never hand-typed)."""
    table = json.loads(SEED_TABLE.read_text(encoding="utf-8"))
    for rule in table["rules"]:
        if rule["hook_id"] == hook_id:
            return dict(rule)
    raise KeyError(hook_id)


def declaration(hook_id: str, **override) -> dict:
    """A remedy declaration from the real seed with named fields overridden."""
    rule = seed_rule(hook_id)
    rule.update(override)
    return {
        "hook_id": hook_id,
        "disposition": rule["disposition"],
        "agent": rule.get("agent"),
        "skills": list(rule.get("skills") or []),
        "instruction": rule.get("instruction", ""),
    }


def complexity_demand(function="plan_batches", score=31, ceiling=30, path="scripts/planner.py"):
    return [{"path": path, "function": function, "score": score, "ceiling": ceiling, "reason": "grew"}]


def size_demand(path="scripts/big_module.py", lines=120):
    return [{"path": path, "lines_to_remove": lines}]


def refusal_reply(decl: dict, demand: list, *, target: str | None = None) -> dict:
    """The commit phase's reply to a refusal, built from a declaration.

    ``target`` defaults to the declaration's named agent; a declaration naming
    none (author-clears) hands back to the originating coder, which is the route
    BO-3000a already honours today.
    """
    handoff_target = target or decl["agent"] or "python-coder"
    return {
        "status": "handoff",
        "handoff_target": handoff_target,
        "message": f"{decl['hook_id']} refused delivery",
        "record_handoff_target": handoff_target,
        "flips_signed_off": False,
        "remedy": {
            "hook_id": decl["hook_id"],
            "disposition": decl["disposition"],
            "skills": list(decl["skills"]),
            "demand": demand,
        },
    }


def drive(driver, worktree, decl, demand, *, coder="python-coder", reply=None, strip_remedy=False):
    """Drive one ticket whose commit is refused once, then accepted.

    Returns ``(observation, ticket_path)``. ``strip_remedy`` removes the remedy
    record from the refusal, which is the shape every refusal had before this
    capability existed (the baseline run for equality assertions).
    """
    phases = ["test-writer", coder, "commit"]
    refusal = dict(reply if reply is not None else refusal_reply(decl, demand))
    if strip_remedy:
        refusal.pop("remedy", None)
    path = H.write_ticket_record(
        worktree, TICKET, phases, extra_frontmatter={"component": "build-orchestration"}
    )
    cfg = {
        "title": "refusal case",
        "phases": phases,
        "has_test_requirements": True,
        "results": {"commit": [refusal, {"status": "ok"}], SPECIALIST: {"status": "ok"}},
    }
    scenario = H.single_ticket_scenario(worktree, path, cfg)
    scenario["remedy_declarations"] = {decl["hook_id"]: decl}
    return H.run_driver(H.TWIN_DRIVERS[driver], scenario), path


def labels(obs) -> list[str]:
    return H.phase_dispatch_labels(obs)


def between_refusal_and_retry(obs) -> list[str]:
    """Parties engaged after the first commit attempt and before the second."""
    ls = labels(obs)
    if "commit" not in ls:
        return []
    first = ls.index("commit")
    rest = ls[first + 1 :]
    return rest[: rest.index("commit")] if "commit" in rest else rest


def commit_attempts(obs) -> int:
    return labels(obs).count("commit")


def specialist_dispatches(obs) -> list:
    return [d for d in H.phase_dispatches(obs) if d["label"] == SPECIALIST]


def completed(path) -> bool:
    return H.read_record(path)["lifecycle_status"] == "done"


def make_worktree(prefix="bo3800b-") -> str:
    import tempfile

    return tempfile.mkdtemp(prefix=prefix)


def drop_worktree(path: str) -> None:
    import shutil

    shutil.rmtree(path, ignore_errors=True)


def node_available() -> bool:
    return H.node_available()


__all__ = [
    "H", "SPECIALIST", "declaration", "complexity_demand", "size_demand", "refusal_reply",
    "drive", "labels", "between_refusal_and_retry", "commit_attempts", "specialist_dispatches",
    "completed", "make_worktree", "drop_worktree", "node_available", "os",
]
