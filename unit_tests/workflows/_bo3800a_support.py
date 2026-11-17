"""Shared helpers for the BO-3800a tests (a change turned away at delivery is held
while the file is put right, and lands once it is).

Builds on ``_bo3800d_support``: every run EXECUTES the real build-feature.js and
build-ticket.js (TWIN_DRIVERS) through the driver harness. Nothing here reads driver
source.

A run is reduced to a plain ``Run`` record (what was dispatched, in order, with the
prompts; the author's working tree before and after; what the ticket record says).
The arms of BO-3800a-1 are predicates over that record. Because they are predicates
over data, the three NAMED MUTATIONS can be executed: a real recorded run is altered
the way the wrong build would alter it, and each predicate must go red or stay green
exactly as the AC lists.

Scenario shape
--------------
test-writer, python-coder, commit, pull-request (pull-request is ordered AFTER
delivery, so "nothing that follows delivery runs" is observable). The commit is
refused by check-file-size (a demand of 120 lines against one named file), the
restructuring step is a STAND-IN supplied by the scenario (never a named party's
behaviour), and the commit is attempted again. ``second_demand`` None -> the retry
lands; a demand list -> the standard refuses again.
"""

from __future__ import annotations

import copy
import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path

import _bo3800d_support as D

C, S, H, TWINS = D.C, D.S, D.H, D.TWINS

NAMED_FILE = "scripts/big_module.py"
AFTER_DELIVERY = "pull-request"
PHASES = ["test-writer", "python-coder", "commit", AFTER_DELIVERY]

#: An instruction to put the working tree back, set it aside, or re-derive it.
TREE_MUTATION = re.compile(
    r"git\s+(?:-C\s+\S+\s+)?(?:reset|stash|checkout|clean|restore|revert)\b|--hard\b|"
    r"re-?(?:author|stage|derive|write)\s+the\s+(?:change|work)",
    re.I,
)
#: A way of getting a change past the standard that refused it.
PAST_THE_STANDARD = re.compile(
    r"SKIP=|--no-verify|\boverride\b|\bbypass\b|\bwaive[ds]?\b|\bexempt(?:ed|ion)?\b|"
    r"allowlist|raise\s+the\s+(?:limit|ceiling)",
    re.I,
)


def author_change(worktree: str) -> None:
    """Leave the author's change standing in the working tree: one real, large file."""
    target = Path(worktree) / NAMED_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(f"def f{i}(x):\n    return x + {i}\n\n" for i in range(220)), encoding="utf-8")


def tree_digest(worktree: str) -> dict[str, str]:
    """sha256 of every file the author could have left, i.e. everything but the ticket
    record (whose bytes the run legitimately rewrites when it records completion)."""
    root = Path(worktree)
    out = {}
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root).as_posix()
        if p.is_file() and not rel.startswith("tickets/") and "__pycache__" not in rel:
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


@dataclass
class Run:
    """What a drive actually did, reduced to data the arms can be asked about."""

    labels: list[str]
    prompts: list[tuple[str, int, str]]  # (label, attempt, prompt)
    tree_before: dict
    tree_after: dict
    completed: bool
    second_accepted: bool
    applied_completion_writes: int
    result: dict = field(default_factory=dict)

    @property
    def commit_attempts(self) -> int:
        return self.labels.count("commit")

    def retried_commit_prompts(self) -> list[str]:
        return [p for (lab, att, p) in self.prompts if lab == "commit" and att > 1]


def drive_hold(driver: str, worktree: str, second_demand, *, hook_id="check-file-size"):
    """Drive one ticket: author's change standing, commit refused, stand-in
    restructuring step, commit attempted again. Returns ``(Run, observation, path)``."""
    author_change(worktree)
    before = tree_digest(worktree)
    decl = S.declaration(hook_id, agent=S.SPECIALIST, skills=[])
    first = S.refusal_reply(decl, S.size_demand(path=NAMED_FILE, lines=120))
    second = {"status": "ok"} if second_demand is None else S.refusal_reply(decl, second_demand)
    path = H.write_ticket_record(worktree, S.TICKET, PHASES, extra_frontmatter={"component": "build-orchestration"})
    cfg = {
        "title": "held refusal",
        "phases": PHASES,
        "has_test_requirements": True,
        "results": {"commit": [first, second], S.SPECIALIST: {"status": "ok"}},
    }
    scenario = H.single_ticket_scenario(worktree, path, cfg)
    scenario["remedy_declarations"] = {decl["hook_id"]: decl}
    obs = H.run_driver(H.TWIN_DRIVERS[driver], scenario)
    run = Run(
        labels=S.labels(obs),
        prompts=[(d["label"], d["attempt"], d["prompt"]) for d in H.phase_dispatches(obs)],
        tree_before=before,
        tree_after=tree_digest(worktree),
        completed=S.completed(path),
        second_accepted=second_demand is None,
        applied_completion_writes=sum(1 for w in H.writes_for(obs, path) if w.get("applied")),
        result=obs.get("result") or {},
    )
    return run, obs, path


# ---------------------------------------------------------------------------
# The arms of BO-3800a-1, as predicates over a Run. Each returns True when the arm
# HOLDS. Nothing here is a source scan.
# ---------------------------------------------------------------------------


def arm_change_intact(run: Run) -> bool:
    """The change is still present and exactly what it was; nobody was told to put
    the tree back."""
    told = any(TREE_MUTATION.search(p) for (_, _, p) in run.prompts)
    return run.tree_after == run.tree_before and bool(run.tree_before) and not told


def arm_not_recorded_completed(run: Run) -> bool:
    """The refused attempt does not complete delivery: the ticket is recorded done
    only after a second delivery attempt actually took place."""
    return (not run.completed) or run.commit_attempts >= 2


def arm_nothing_after_delivery_runs(run: Run) -> bool:
    """No phase ordered after delivery is dispatched before delivery has landed."""
    if AFTER_DELIVERY not in run.labels:
        return True
    last_commit = max((i for i, v in enumerate(run.labels) if v == "commit"), default=-1)
    return run.second_accepted and run.labels.index(AFTER_DELIVERY) > last_commit and run.commit_attempts >= 2


def arm_second_attempt_carries_change(run: Run) -> bool:
    """Delivery was attempted a second time, over the very tree the author left."""
    return run.commit_attempts == 2 and run.tree_after == run.tree_before and bool(run.tree_before)


def arm_judged_by_same_standard(run: Run) -> bool:
    """The second attempt is a plain delivery dispatch: nothing suppressed, skipped,
    waived or overridden."""
    retried = run.retried_commit_prompts()
    return len(retried) == 1 and not any(PAST_THE_STANDARD.search(p) for p in retried)


def arm_completes_because_standard_met(run: Run) -> bool:
    """The ticket is recorded done exactly when the standard accepted the retry."""
    return run.completed == run.second_accepted and (run.applied_completion_writes == 1) == run.completed


def arm_reoffer_follows_restructuring(run: Run) -> bool:
    """No second delivery attempt precedes the restructuring step; when delivery was
    re-offered at all, the stand-in step sits between the two attempts."""
    ls = run.labels
    if ls.count("commit") < 2:
        return True
    first, second = [i for i, v in enumerate(ls) if v == "commit"][:2]
    return S.SPECIALIST in ls[first + 1 : second]


ARMS = {
    "intact": arm_change_intact,
    "not_completed": arm_not_recorded_completed,
    "nothing_after": arm_nothing_after_delivery_runs,
    "second_attempt": arm_second_attempt_carries_change,
    "same_standard": arm_judged_by_same_standard,
    "completes_because": arm_completes_because_standard_met,
    "order": arm_reoffer_follows_restructuring,
}


def verdicts(run: Run) -> dict[str, bool]:
    return {name: fn(run) for name, fn in ARMS.items()}


# ---------------------------------------------------------------------------
# The three named mutations, applied to a REAL recorded run.
# ---------------------------------------------------------------------------


def mutate_discard(run: Run) -> Run:
    """(1) THE DISCARD: the tree is reset before anyone is asked, so the restructuring
    starts from a clean file. The author's change is gone afterwards."""
    m = copy.deepcopy(run)
    m.tree_after = {}
    m.prompts = [
        (lab, att, p + "\nFirst run git reset --hard so you start from a clean file.")
        if lab == S.SPECIALIST else (lab, att, p)
        for (lab, att, p) in m.prompts
    ]
    return m


def mutate_forced_pass(run: Run) -> Run:
    """(2) THE FORCED PASS: the second attempt is delivered without consulting the
    standard that refused: it carries a skip, and the ticket is recorded done."""
    m = copy.deepcopy(run)
    m.prompts = [
        (lab, att, p + "\nRun it as SKIP=check-file-size git commit.") if lab == "commit" and att > 1 else (lab, att, p)
        for (lab, att, p) in m.prompts
    ]
    m.completed = True
    m.applied_completion_writes = 1
    return m


def mutate_dropped_retry(run: Run) -> Run:
    """(3) THE DROPPED RETRY: the change is held and the specialist is asked, then the
    run ends there. Delivery is never re-offered."""
    m = copy.deepcopy(run)
    last_commit = max(i for i, v in enumerate(m.labels) if v == "commit")
    m.labels = m.labels[:last_commit]
    m.prompts = [t for t in m.prompts if not (t[0] == "commit" and t[1] > 1) and t[0] != AFTER_DELIVERY]
    m.completed = False
    m.applied_completion_writes = 0
    return m


__all__ = [
    "C", "S", "H", "D", "TWINS", "NAMED_FILE", "AFTER_DELIVERY", "PHASES", "Run", "ARMS",
    "drive_hold", "verdicts", "author_change", "tree_digest", "mutate_discard",
    "mutate_forced_pass", "mutate_dropped_retry", "TREE_MUTATION", "PAST_THE_STANDARD",
]
