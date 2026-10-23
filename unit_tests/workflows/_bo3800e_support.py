"""Shared helpers for the BO-3800e tests: only a refusal that asks for a craft
brings one in, and nothing else about a drive changes.

Every assertion in this tree is an EQUALITY AGAINST A BASELINE RUN, so the helpers
produce the baseline the way the AC's it_requirements demand: MEASURED from the
driver as it stood before the handoff capability, never reconstructed from
BO-210c's text and never a hand-written list of expected agents.

Baseline construction
---------------------
``baseline_script(driver)`` materialises the driver exactly as it was on the commit
BEFORE the first BO-3800 change to it (``git show <sha>^:<path>``), into a scratch
folder, and ``drive(...)`` runs it through the same harness, on the same fixture, as
the current driver. Between that commit and now only BO-3800b/c/d touched these two
files, so the difference between the two runs IS the capability. A baseline that
cannot be materialised raises (it is never skipped past), because a silently missing
baseline would make every equality below assert nothing.

Real producers
--------------
* The ticket record is a real .md written by ``yaml.safe_dump``.
* The remedy declaration is lifted verbatim from the real package seed routing table.
* ``real_handoff`` runs the REAL ``remedy_handoff.py`` as a subprocess over a real
  routing table and returns its stdout/exit code, so a refusal's payload is whatever
  the production helper actually produces, not a hand-typed dict.
"""

from __future__ import annotations

import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parent))

import _bo3800b_support as S  # noqa: E402

H = S.H
REPO = Path(H.REPO_ROOT)
TWINS = list(H.TWIN_DRIVERS)
SPECIALIST = S.SPECIALIST
HELPER = REPO / "templates" / "scripts" / "commit_guardian" / "remedy_handoff.py"
SEED_TABLE = S.SEED_TABLE
NAMED_FILE = "scripts/big_module.py"

#: The subject prefix of the first commit that gave the drivers the handoff capability.
CAPABILITY_COMMIT_SUBJECT = "feat(BO-3800b)"

_BASELINE_DIR: list[str] = []


class BaselineUnavailable(RuntimeError):
    """The pre-capability driver could not be materialised from history."""


def _git(*args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(REPO), *args], capture_output=True, text=True, timeout=60, check=False
    )
    if proc.returncode != 0:
        msg = f"git {' '.join(args)} failed: {proc.stderr.strip()}"
        raise BaselineUnavailable(msg)
    return proc.stdout


def capability_commit() -> str:
    """The sha of the commit that introduced the handoff capability into the drivers."""
    out = _git("log", "--format=%H", "--fixed-strings", f"--grep={CAPABILITY_COMMIT_SUBJECT}", "--", "templates/workflows-js/build-feature.js")
    shas = [s for s in out.split() if s]
    if not shas:
        msg = f"no commit with subject {CAPABILITY_COMMIT_SUBJECT!r} touches build-feature.js"
        raise BaselineUnavailable(msg)
    return shas[-1]


def baseline_script(driver: str) -> str:
    """Path of the driver as it was before the capability (materialised once)."""
    rel = f"templates/workflows-js/{driver}"
    if not _BASELINE_DIR:
        _BASELINE_DIR.append(tempfile.mkdtemp(prefix="bo3800e-baseline-"))
    dest = Path(_BASELINE_DIR[0]) / driver
    if not dest.exists():
        dest.write_text(_git("show", f"{capability_commit()}^:{rel}"), encoding="utf-8")
    return str(dest)


def current_script(driver: str) -> str:
    return H.TWIN_DRIVERS[driver]


# ---------------------------------------------------------------------------
# Scenario construction
# ---------------------------------------------------------------------------

PHASES = ["test-writer", "python-coder", "commit"]


def author_clears_decl(hook_id: str = "check-file-size") -> dict:
    """The real seed declaration for ``hook_id`` with only the disposition changed to
    the author-clearable one (and no specialist named)."""
    return S.declaration(hook_id, disposition="author-clears", agent=None, skills=[])


def refusal(decl: dict, demand: list, *, remedy="as-declared") -> dict:
    """A commit-phase refusal reply built from a declaration.

    ``remedy`` = "as-declared" keeps the real remedy record; ``None`` removes it (the
    shape every refusal had before this capability existed); any other value replaces it.
    """
    reply = S.refusal_reply(decl, demand)
    if remedy is None:
        reply.pop("remedy", None)
    elif remedy != "as-declared":
        reply["remedy"] = remedy
    return reply


def scenario_for(worktree: str, results: dict, decls: dict | None = None, phases=None):
    phases = phases or PHASES
    path = H.write_ticket_record(worktree, S.TICKET, phases, extra_frontmatter={"component": "build-orchestration"})
    cfg = {"title": "bo-3800e", "phases": phases, "has_test_requirements": True, "results": results}
    scenario = H.single_ticket_scenario(worktree, path, cfg)
    scenario["remedy_declarations"] = decls or {}
    return scenario, path


def historical_replies(worktree: str) -> dict:
    """The lookups the pre-capability driver made before the workspace maker existed (BO-4300 retired them
    from the current drivers and from the harness defaults), answered as the harness answered them then:
    the resolved working copy is reusable, so the baseline proceeds with no new location."""
    facts = {"exists": True, "is_git_toplevel": True, "is_linked_worktree": True, "is_main_checkout": False,
             "same_repository": True, "branch": "harness-default"}
    return {
        "worktree-facts-resolved": {"output": json.dumps(facts), "exit_code": 0},
        "worktree-setup": {"worktree_path": worktree, "status": "reused"},
    }


def run_script(script: str, scenario: dict) -> dict:
    if _BASELINE_DIR and Path(script).parent == Path(_BASELINE_DIR[0]):
        scenario = dict(scenario, historical_replies=historical_replies(scenario["record_dir"]))
    return H.run_driver(script, scenario)


@dataclass
class Run:
    """What a drive observably did, reduced to comparable data."""

    labels: list
    outcome: object
    completed: bool
    readbacks: int
    writes: int
    enumerations: int
    declaration_reads: list = field(default_factory=list)
    obs: dict = field(default_factory=dict)

    def comparable(self) -> dict:
        return {
            "labels": self.labels,
            "outcome": self.outcome,
            "completed": self.completed,
            "readbacks": self.readbacks,
            "writes": self.writes,
            "enumerations": self.enumerations,
        }


def _outcome(obs: dict):
    result = obs.get("result") or {}
    return H.outcome_status(result) if result else None


def reduce_run(obs: dict, path: str) -> Run:
    return Run(
        labels=S.labels(obs),
        outcome=_outcome(obs),
        completed=S.completed(path),
        readbacks=H.readback_count_for(obs, path),
        writes=len(H.writes_for(obs, path)),
        enumerations=len(obs.get("enumerations") or []),
        declaration_reads=list(obs.get("declaration_reads") or []),
        obs=obs,
    )


def drive(script: str, results_factory, decls_factory=None, *, phases=None) -> Run:
    """Run ``script`` once on a fresh worktree. ``results_factory`` and
    ``decls_factory`` build the scripted replies, so two scripts are driven over the
    same construction but never share a worktree."""
    wt = S.make_worktree("bo3800e-")
    try:
        scenario, path = scenario_for(wt, results_factory(), decls_factory() if decls_factory else None, phases)
        obs = run_script(script, scenario)
        return reduce_run(obs, path)
    finally:
        S.drop_worktree(wt)


def paired(driver: str, results_factory, decls_factory=None, *, phases=None):
    """(baseline_run, current_run) of the same fixture, same harness."""
    base = drive(baseline_script(driver), results_factory, decls_factory, phases=phases)
    cur = drive(current_script(driver), results_factory, decls_factory, phases=phases)
    return base, cur


def author_clearable_results(hook_id="check-file-size"):
    decl = author_clears_decl(hook_id)
    return {
        "commit": [refusal(decl, S.size_demand(path=NAMED_FILE, lines=20)), {"status": "ok"}],
        SPECIALIST: {"status": "ok"},
    }


def author_clearable_decls(hook_id="check-file-size"):
    decl = author_clears_decl(hook_id)
    return {hook_id: decl}


def accepted_results():
    return {"commit": {"status": "ok"}, SPECIALIST: {"status": "ok"}}


def median_seconds(fn, n: int = 5) -> float:
    samples = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t0)
    return statistics.median(samples)


# ---------------------------------------------------------------------------
# The real producer: remedy_handoff.py over a real routing table
# ---------------------------------------------------------------------------


def seed_table() -> dict:
    return json.loads(SEED_TABLE.read_text(encoding="utf-8"))


def table_without_gating(hook_id: str) -> dict:
    """The REAL seed table with ``hook_id`` removed from blocking_hook_ids only; its
    rule (declaration) is untouched, so the hook still DECLARES engage-specialist but
    no longer GATES a commit."""
    table = seed_table()
    table["blocking_hook_ids"] = [h for h in table["blocking_hook_ids"] if h != hook_id]
    return table


def real_handoff(table: dict, hook_id: str, refusal_output: str):
    """Run the production ``remedy_handoff.py`` from a scratch project root whose local
    routing table is ``table`` (written by json.dump). Returns the CompletedProcess."""
    root = Path(tempfile.mkdtemp(prefix="bo3800e-root-"))
    try:
        local = root / ".claude" / "precommit-autofix.json"
        local.parent.mkdir(parents=True)
        local.write_text(json.dumps(table), encoding="utf-8")
        guardian = HELPER.parent
        env = dict(os.environ, PYTHONPATH=str(guardian))
        return subprocess.run(
            [sys.executable, str(HELPER), "--hook-id", hook_id],
            input=refusal_output, cwd=str(root), capture_output=True, text=True,
            timeout=60, check=False, env=env,
        )
    finally:
        shutil.rmtree(root, ignore_errors=True)


def size_refusal_output(path=NAMED_FILE, lines=120) -> str:
    return "[check-file-size] refused\nFILE_SIZE_REFUSAL_RECORD: " + json.dumps([{"path": path, "lines_to_remove": lines}]) + "\n"


def node_available() -> bool:
    return H.node_available()


# ---------------------------------------------------------------------------
# Arms (predicates over a recorded Run, compared against its baseline Run) and the
# two NAMED MUTATIONS, applied to a REAL recorded run (the BO-3800a-1 construction).
# ---------------------------------------------------------------------------


def arm_nobody_extra_engaged(run: Run, base: Run) -> bool:
    """No restructuring specialist appears in the record, and the record is the
    baseline's, element for element and in order."""
    return SPECIALIST not in run.labels and run.labels == base.labels


def arm_same_as_baseline(run: Run, base: Run) -> bool:
    """Parties, order and delivery outcome are the baseline's."""
    return run.comparable() == base.comparable()


def arm_no_extra_work(run: Run, base: Run) -> bool:
    """No declaration read, and no read, write, enumeration or dispatch beyond the
    baseline's."""
    return (
        run.declaration_reads == []
        and run.readbacks == base.readbacks
        and run.writes == base.writes
        and run.enumerations == base.enumerations
        and run.labels == base.labels
    )


def mutate_over_broad_summons(run: Run) -> Run:
    """THE OVER-BROAD SUMMONS: on any refusal at delivery the specialist is engaged
    without reading the disposition. A run with no refusal in it is untouched, because
    there is nothing to trigger the summons."""
    import copy

    m = copy.deepcopy(run)
    commits = [i for i, v in enumerate(m.labels) if v == "commit"]
    if len(commits) >= 2:
        m.labels = m.labels[: commits[0] + 1] + [SPECIALIST] + m.labels[commits[0] + 1 :]
    return m


def mutate_eager_probe(run: Run) -> Run:
    """THE EAGER PROBE: at every delivery attempt the specialist is resolved (a
    declaration read) and engaged before the verdict is consulted."""
    import copy

    m = copy.deepcopy(run)
    commits = [i for i, v in enumerate(m.labels) if v == "commit"]
    for offset, i in enumerate(commits):
        m.labels.insert(i + offset, SPECIALIST)
        m.declaration_reads.append({"label": "remedy-declaration", "hook_id": None})
    return m


__all__ = [
    "S", "H", "TWINS", "SPECIALIST", "NAMED_FILE", "PHASES", "Run", "BaselineUnavailable",
    "baseline_script", "current_script", "author_clears_decl", "refusal", "scenario_for",
    "run_script", "historical_replies", "reduce_run", "drive", "paired", "author_clearable_results",
    "author_clearable_decls", "accepted_results", "median_seconds", "seed_table",
    "table_without_gating", "real_handoff", "size_refusal_output", "node_available",
    "capability_commit", "arm_nobody_extra_engaged", "arm_same_as_baseline", "arm_no_extra_work",
    "mutate_over_broad_summons", "mutate_eager_probe",
]
