"""Shared helpers for the BO-3800d tests (a restructuring handoff that cannot meet the
demand stops, accounts for itself, and is never quietly delivered).

Builds on ``_bo3800b_support``/``_bo3800c_support``: every run EXECUTES the real
build-feature.js and build-ticket.js (TWIN_DRIVERS) through the driver harness and
reads what the run actually dispatched, produced and recorded. Nothing here reads
driver source.

Scenario shape
--------------
The commit phase is refused (a remedy record naming the specialist), the specialist
runs, and the commit is attempted again. ``second`` is what the retried commit
reports: ``None`` means it lands (``{status: ok}``), a demand list means the standard
refused again on the same terms (the file is still short; the demand is the file's
NEW standing as the refusing check restates it).
"""

from __future__ import annotations

import re

import _bo3800c_support as C

S = C.S
H = S.H
TWINS = list(H.TWIN_DRIVERS)

#: What an account must say when the change was not delivered.
NOT_DELIVERED = re.compile(r"not\s+(?:been\s+)?delivered|nothing\s+was\s+delivered|undelivered", re.I)
#: What an account must say about the specialist's edits at the stop.
EDITS_REMAIN = re.compile(
    r"(?:remain|still\s+(?:in\s+place|there)|kept|retained|preserved|not\s+(?:been\s+)?(?:undone|reverted|rolled\s+back|discarded))",
    re.I,
)
#: The two ways the specialist can fail to produce a result at all.
MACHINERY = re.compile(r"could\s+not\s+be\s+engaged|not\s+be\s+engaged|nothing\s+usable|unusable|no\s+usable", re.I)

BOUNDARY_PATH = "scripts/big_module.py"


def size_decl():
    return S.declaration("check-file-size", agent=S.SPECIALIST, skills=[])


def drive_repeat(driver, worktree, decl, first_demand, second_demand, *, specialist=None):
    """Drive one ticket: commit refused, specialist engaged, commit attempted again.

    ``second_demand`` None -> the retry lands; a list -> the retry is refused again
    with that demand. ``specialist`` overrides the specialist's own reply.
    Returns ``(observation, ticket_path)``.
    """
    phases = ["test-writer", "python-coder", "commit"]
    first = S.refusal_reply(decl, first_demand)
    commit_replies = [first]
    commit_replies.append({"status": "ok"} if second_demand is None else S.refusal_reply(decl, second_demand))
    path = H.write_ticket_record(
        worktree, S.TICKET, phases, extra_frontmatter={"component": "build-orchestration"}
    )
    cfg = {
        "title": "bounded restructuring handoff",
        "phases": phases,
        "has_test_requirements": True,
        "results": {"commit": commit_replies, S.SPECIALIST: specialist or {"status": "ok"}},
    }
    scenario = H.single_ticket_scenario(worktree, path, cfg)
    scenario["remedy_declarations"] = {decl["hook_id"]: decl}
    return H.run_driver(H.TWIN_DRIVERS[driver], scenario), path


def stop_text(obs) -> str:
    return C.result_text(obs)


def dispatches_after_last_commit(obs) -> list[str]:
    ls = S.labels(obs)
    last = max((i for i, v in enumerate(ls) if v == "commit"), default=-1)
    return ls[last + 1 :]


__all__ = [
    "C", "S", "H", "TWINS", "NOT_DELIVERED", "EDITS_REMAIN", "MACHINERY", "BOUNDARY_PATH",
    "size_decl", "drive_repeat", "stop_text", "dispatches_after_last_commit",
]
