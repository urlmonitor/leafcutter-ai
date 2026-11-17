"""Behavioral tests for BO-100e-4 -- a halted ticket costs only the work behind it.

Covers:
  BO-100e-4 -- "One branch failing does not withhold the later layers of an
               unrelated branch" (ticket 04 of EPIC-BuildToolingRunsThrough,
               user decision F4 Option A).
  BO-100e-2 -- the number of looks stays bounded (the re-drive test).

Every test EXECUTES templates/workflows-js/build-feature.js's epic loop through
the shared driver harness and asserts on what the run dispatched and returned,
never on source text (CLAUDE.md "Gate / Workflow ACs -- Verify Behaviorally").
Ticket records are REAL files whose frontmatter comes from yaml.safe_dump.

The dirty-state read is answered by the harness from ``scenario["dirty"]``:
this file's ``drive()`` ALWAYS writes that key, and a missing ``dirty=`` argument
writes null, which the harness answers as UNREADABLE -- an absent value must
never read as a clean worktree. Only ``test_absent_dirty_key...`` removes the
key, to pin the harness's separate default for pre-existing halt fixtures.

Paths are forward-slashed before use because the driver reports normalised
paths and a backslashed Windows temp path would otherwise never compare equal.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(
    0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "prompt_assembly")
)

import _driver_harness as H  # noqa: E402

pytestmark = pytest.mark.skipif(
    not H.node_available(), reason="node is not available on PATH"
)

SCRIPT = Path(__file__).resolve().parents[2] / "templates" / "scripts" / "worktree_repo_facts.py"
GATES = ["test-runner", "commit"]
EPIC_SUBDIR = os.path.join("tickets", "00_inbox", "epics", "EPIC-Continue")
CLEAN = {"readable": True, "staged": [], "unstaged": [], "untracked": []}
ABSENT = object()  # drive(dirty=ABSENT) leaves the key out of the scenario
UNREADABLE_RE = re.compile(
    r"could not be read|cannot be read|unreadable|not readable|unable to read", re.I
)
COUNT_RE = re.compile(r"(\d+) piece\(s\) of work in total were not built: (.*)", re.S)

A, B, C, D = "01_a.md", "02_b.md", "03_c.md", "04_d.md"
# Two independent chains A->B and C->D, every ticket in its own batch.
CHAINS = {A: {"halts": True}, B: {"deps": [A]}, C: {}, D: {"deps": [C]}}
CHAIN_PLAN = [[A], [B], [C], [D]]


def _fwd(path: str) -> str:
    return path.replace("\\", "/")


@pytest.fixture
def wt():
    path = _fwd(tempfile.mkdtemp(prefix="bo100e4_"))
    yield path
    shutil.rmtree(path, ignore_errors=True)


def drive(wt, specs, looks, *, end=(), dirty=None):
    """Write real records for ``specs`` and run the epic. -> (obs, result, paths).

    ``specs``: name -> {halts, deps (names), files (files_touched)}.
    ``looks``: per look, a list of batches, each a list of names; batch numbers
    run 1.. within the look. ``end``: names whose record reads done at the end.
    ``dirty``: the scenario's dirty-state answer; omitted == null == UNREADABLE.
    """
    epic = _fwd(os.path.join(wt, EPIC_SUBDIR))
    os.makedirs(epic, exist_ok=True)
    paths = {n: _fwd(os.path.join(epic, n)) for n in specs}
    tickets = {}
    for name, spec in specs.items():
        frontmatter = {"component": "build-orchestration"}
        if spec.get("deps"):
            frontmatter["depends_on"] = [paths[d] for d in spec["deps"]]
        if spec.get("files"):
            frontmatter["files_touched"] = list(spec["files"])
        H.write_ticket_record(
            wt, name, GATES, title=name, subdir=EPIC_SUBDIR, extra_frontmatter=frontmatter
        )
        tickets[paths[name]] = {
            "title": name,
            "phases": GATES,
            "has_test_requirements": True,
            "files_touched": list(spec.get("files") or ["scripts/example.py"]),
            "results": (
                {"test-runner": {"status": "blocker", "record": False}}
                if spec.get("halts")
                else H.phase_results({g: True for g in GATES})
            ),
        }

    def present(done):
        return [{"path": paths[n], "status": "done" if n in done else "todo"} for n in specs]

    def batches(look):
        return [
            {
                "batch_number": number,
                "tickets": [{"path": paths[n], "status": "todo"} for n in names],
            }
            for number, names in enumerate(look, start=1)
        ]

    reads = [{"present": present(()), "batches": batches(looks[0])}]
    reads += [{"present": present(end), "batches": batches(look)} for look in looks[1:]]
    # The terminating look (offers nothing), then the completion-time re-read.
    reads += [{"present": present(end), "batches": []}, {"present": present(end)}]
    scenario = H.epic_scenario(wt, epic, tickets, reads, title="EPIC-Continue")
    if dirty is not ABSENT:
        scenario["dirty"] = dirty
    obs = H.run_driver(H.BUILD_FEATURE_JS, scenario)
    assert obs["error"] is None, f"the driver threw: {obs['error']}"
    assert isinstance(obs["result"], dict), f"no payload: {obs['result']!r}"
    return obs, obs["result"], paths


def touched(obs) -> set:
    """Every ticket a phase agent was dispatched for."""
    return {d["ticket_path"] for d in H.phase_dispatches(obs) if d.get("ticket_path")}


def entries(res, key) -> list:
    return [e for e in (res.get(key) or []) if isinstance(e, dict)]


def unbuilt_entry(res, path):
    return next((e for e in entries(res, "unbuilt") if e.get("ticket_path") == path), None)


def test_independent_later_batch_ticket_is_built_after_halt(wt):
    # covers: BO-100e-4
    # angle: criterion
    """A halts in batch 1 with a clean worktree: D (behind C, not A) is built in
    the same run, B (behind A) is never dispatched, and the run does not return
    at A's batch."""
    obs, res, p = drive(wt, CHAINS, [CHAIN_PLAN], end=[C, D], dirty=CLEAN)
    assert p[D] in touched(obs), f"D was never dispatched; touched={sorted(touched(obs))}"
    assert p[D] in H.completed_work_paths(res), f"D not completed: {H.output_text(res)}"
    assert p[B] not in touched(obs), "B is behind the halted A and must not be built"
    assert len(obs["dirty_reads"]) == 1, "one dirty read for the one batch that halted"
    assert "worktree_repo_facts.py dirty" in obs["dirty_reads"][0]["prompt"]


def test_dependant_of_halted_ticket_is_withheld_and_names_it(wt):
    # covers: BO-100e-4
    # angle: criterion
    """The unbuilt set is exactly the work behind A: B, withheld by A; C and D
    appear as completed and nothing else is withheld."""
    obs, res, p = drive(wt, CHAINS, [CHAIN_PLAN], end=[C, D], dirty=CLEAN)
    entry = unbuilt_entry(res, p[B])
    assert entry is not None, f"B missing from unbuilt: {res.get('unbuilt')!r}"
    assert entry.get("withheld_by") == [p[A]], entry
    assert [e["ticket_path"] for e in entries(res, "unbuilt")] == [p[B]], res.get("unbuilt")
    assert {p[C], p[D]} <= set(H.completed_work_paths(res)), H.output_text(res)
    assert not {p[A], p[B]} & set(H.completed_work_paths(res))


@pytest.mark.parametrize("kind", ["unstaged", "untracked"])
def test_ticket_sharing_a_dirty_file_is_withheld(wt, kind):
    # covers: BO-100e-4
    # angle: boundary
    """A halts leaving X modified. E (no dependency on A, lists X) is withheld and
    names X; the unrelated F is built. Untracked leftovers count like unstaged."""
    x = "src/shared_module.py"
    specs = {A: {"halts": True}, "02_e.md": {"files": [x]}, "03_f.md": {"files": ["src/other.py"]}}
    dirty = dict(CLEAN, **{kind: [x]})
    obs, res, p = drive(wt, specs, [[[A], ["02_e.md"], ["03_f.md"]]], end=["03_f.md"], dirty=dirty)
    assert p["02_e.md"] not in touched(obs), "E shares X with what A left behind"
    entry = unbuilt_entry(res, p["02_e.md"])
    assert entry is not None, f"E missing from unbuilt: {res.get('unbuilt')!r}"
    assert entry.get("withheld_by_shared_files") == [x], entry
    assert p["03_f.md"] in touched(obs), "F shares nothing with the leftovers"
    assert p["03_f.md"] in H.completed_work_paths(res)


def test_staged_leftovers_stop_the_run_and_name_paths(wt):
    # covers: BO-100e-4
    # angle: failure
    """A halts and the worktree has Y STAGED: the next commit would sweep Y in, so
    the run ends after A's batch and the return names Y."""
    y = "src/staged_by_the_halted_ticket.py"
    obs, res, p = drive(wt, CHAINS, [CHAIN_PLAN], end=[C, D], dirty=dict(CLEAN, staged=[y]))
    assert touched(obs) == {p[A]}, f"work continued past staged leftovers: {sorted(touched(obs))}"
    assert y in (res.get("staged_leftovers") or []), H.output_text(res)
    assert res.get("ended_because") == "halted"
    assert res.get("epic_complete") is False


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({}, id="builder_default_is_unreadable"),
        pytest.param({"dirty": None}, id="null_marker"),
        pytest.param({"dirty": "fatal: not a git repository"}, id="unparseable_text"),
        pytest.param({"dirty": {"readable": False, "error": "git status failed"}}, id="readable_false"),
        pytest.param({"dirty": {"readable": True, "staged": [], "unstaged": []}}, id="missing_untracked_key"),
        pytest.param({"dirty": dict(CLEAN, staged="a.py")}, id="staged_not_an_array"),
        pytest.param({"dirty": {"staged": [], "unstaged": [], "untracked": []}}, id="no_readable_flag"),
    ],
)
def test_unreadable_dirty_facts_stop_the_run(wt, kwargs):
    # covers: BO-100e-4
    # angle: failure
    """A halts and the dirty-state reply cannot be trusted (null, unparseable,
    readable false, a missing key, a non-array list, or no readable flag at all):
    the run fails closed after A's batch and says the state could not be read. A
    missing or malformed list is never read as an empty (clean) one."""
    obs, res, p = drive(wt, CHAINS, [CHAIN_PLAN], end=[C, D], **kwargs)
    assert touched(obs) == {p[A]}, f"work continued on unreadable facts: {sorted(touched(obs))}"
    assert UNREADABLE_RE.search(H.output_text(res)), (
        f"the return never says the worktree state could not be read: {H.output_text(res)}"
    )
    assert res.get("ended_because") == "halted"
    assert res.get("epic_complete") is False


def test_absent_dirty_key_answers_clean_for_legacy_halt_fixtures(wt):
    # covers: BO-100e-4
    # angle: boundary
    """The harness default for a scenario that declares no dirty facts is CLEAN
    (that is what keeps every pre-existing halt fixture's outcome); only an
    explicit null reads as unreadable. Both defaults are pinned: the null side by
    the parametrised test above."""
    obs, res, p = drive(wt, CHAINS, [CHAIN_PLAN], end=[C, D], dirty=ABSENT)
    assert p[D] in touched(obs), f"a scenario with no dirty key should read clean: {H.output_text(res)}"
    assert len(obs["dirty_reads"]) == 1


def test_halted_ticket_is_not_redriven_in_a_later_look(wt):
    # covers: BO-100e-4
    # covers: BO-100e-2
    # angle: boundary
    """The planner offers A again in look 2 after A halted in look 1. A's phases
    are dispatched once, and the run ends because look 2 released nothing new."""
    obs, res, p = drive(wt, {A: {"halts": True}}, [[[A]], [[A]]], dirty=CLEAN)
    runs = [d for d in H.phase_dispatches(obs) if d["ticket_path"] == p[A]]
    assert [d["attempt"] for d in runs] == [1], f"A was driven more than once: {runs}"
    assert res.get("looks") == 2, f"expected one further, terminating look; got {res.get('looks')}"


def test_withheld_ticket_is_not_redispatched_or_rereported_in_a_later_look(wt):
    # covers: BO-100e-4
    # covers: BO-100e-2
    # angle: boundary
    """B is withheld behind A in look 1 and re-offered in look 2: it is never
    dispatched and is reported exactly once (a withheld verdict is recorded)."""
    specs = {A: {"halts": True}, B: {"deps": [A]}}
    obs, res, p = drive(wt, specs, [[[A], [B]], [[B]]], dirty=CLEAN)
    assert p[B] not in touched(obs)
    assert [e["ticket_path"] for e in entries(res, "unbuilt")] == [p[B]], res.get("unbuilt")


def test_final_return_carries_halt_fields_and_epic_incomplete(wt):
    # covers: BO-100e-4
    # angle: seam
    """The run's one final return carries every halt field, and the real payload
    passes the outcome-value agreement check the callers apply to it."""
    obs, res, p = drive(wt, CHAINS, [CHAIN_PLAN], end=[C, D], dirty=CLEAN)
    assert [e["ticket_path"] for e in entries(res, "halted_tickets")] == [p[A]], res.get("halted_tickets")
    assert [e["ticket_path"] for e in entries(res, "unbuilt")] == [p[B]], f"unbuilt: {res.get('unbuilt')!r}"
    done = {n: b["batch_number"] for b in entries(res, "completed_batches") for n in b["tickets"]}
    assert (done.get(p[C]), done.get(p[D])) == (3, 4), f"post-halt batches missing: {done}"
    assert res.get("ended_because") == "halted"
    assert res.get("halted_at_batch") == 1
    assert res.get("epic_complete") is False
    assert res.get("status") == "blocked"
    count = COUNT_RE.search(str(res.get("message")))
    assert count and int(count.group(1)) == 2, f"BO-300d-1 count: {res.get('message')!r}"
    assert p[A] in count.group(2) and p[B] in count.group(2) and p[C] not in count.group(2)
    assert H.epic_outcome_disagreement(res) is None, H.epic_outcome_disagreement(res)


def test_all_work_behind_failed_prerequisite_ends_without_claiming_done(wt):
    # covers: BO-100e-4
    # angle: failure
    """Every other ticket is behind A (B directly, C behind B): nothing else is
    dispatched, the run ends, both are reported withheld, and it never claims
    the work finished."""
    specs = {A: {"halts": True}, B: {"deps": [A]}, C: {"deps": [B]}}
    obs, res, p = drive(wt, specs, [[[A], [B], [C]]], dirty=CLEAN)
    assert touched(obs) == {p[A]}, f"work ran behind the failed A: {sorted(touched(obs))}"
    assert {e["ticket_path"] for e in entries(res, "unbuilt")} == {p[B], p[C]}, f"unbuilt: {res.get('unbuilt')!r}"
    assert res.get("epic_complete") is False
    assert res.get("ended_because") == "halted"
    assert not H.is_success_outcome(res) and not H.claims_epic_complete(res)
    assert H.completed_work_paths(res) == []


def test_leftover_set_is_replaced_not_unioned_at_each_read(wt):
    # covers: BO-100e-4
    # angle: boundary
    """Dirty state is whole-worktree: each read REPLACES the leftover set. A leaves
    X, then G halts and the next read shows only Z (X was cleaned meanwhile), so
    H, which lists X, is built. A union (or a single read) would withhold it."""
    x = "src/was_cleaned_up.py"
    specs = {A: {"halts": True}, "02_g.md": {"halts": True}, "03_h.md": {"files": [x]}}
    dirty = [dict(CLEAN, unstaged=[x]), dict(CLEAN, unstaged=["src/z.py"])]
    obs, res, p = drive(wt, specs, [[[A], ["02_g.md"], ["03_h.md"]]], end=["03_h.md"], dirty=dirty)
    assert len(obs["dirty_reads"]) == 2, "one read per batch that halted"
    assert p["03_h.md"] in touched(obs), f"H was withheld on a stale leftover: {H.output_text(res)}"


def test_one_dirty_read_covers_every_halt_in_a_batch(wt):
    # covers: BO-100e-4
    # angle: boundary
    """Two tickets halt in the same batch: the worktree is read once, after the
    batch settled (never once per ticket), and the later batch is still built."""
    specs = {A: {"halts": True}, "02_a2.md": {"halts": True}, C: {}}
    obs, res, p = drive(wt, specs, [[[A, "02_a2.md"], [C]]], end=[C], dirty=CLEAN)
    assert len(obs["dirty_reads"]) == 1, f"{len(obs['dirty_reads'])} reads for one batch"
    assert p[C] in touched(obs)


def test_same_batch_sibling_sharing_the_leftover_file_is_not_withheld(wt):
    # covers: BO-100e-4
    # angle: boundary
    """S runs in A's own batch and lists the file A leaves behind. Same-batch
    siblings are never overlap-withheld: S is built and not reported unbuilt."""
    x = "src/shared_module.py"
    specs = {A: {"halts": True, "files": [x]}, "02_s.md": {"files": [x]}}
    obs, res, p = drive(wt, specs, [[[A, "02_s.md"]]], end=["02_s.md"], dirty=dict(CLEAN, unstaged=[x]))
    assert p["02_s.md"] in touched(obs)
    assert p["02_s.md"] in H.completed_work_paths(res)
    assert unbuilt_entry(res, p["02_s.md"]) is None


@pytest.mark.skipif(shutil.which("git") is None, reason="git is not on PATH")
@pytest.mark.parametrize("kind", ["staged", "unstaged"])
def test_real_dirty_script_output_drives_the_epic_loop(wt, kind):
    # covers: BO-100e-4
    # angle: seam
    """The REAL `dirty` subcommand's JSON for a REAL repository is piped into the
    real epic loop: a staged leftover stops the run and is named; an unstaged one
    lets it continue (no later ticket lists that file)."""
    repo = os.path.join(wt, "repo")
    os.makedirs(repo)

    def git(*args):
        subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=repo, check=True, capture_output=True)

    git("init", "-q")
    git("config", "user.email", "t@example.invalid")
    git("config", "user.name", "Test")
    Path(repo, "left_behind.txt").write_text("v1", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "initial")
    Path(repo, "left_behind.txt").write_text("v2", encoding="utf-8")
    if kind == "staged":
        git("add", "left_behind.txt")
    proc = subprocess.run([sys.executable, str(SCRIPT), "dirty", repo], capture_output=True, text=True, check=False)
    assert proc.returncode == 0, f"`dirty` failed: rc={proc.returncode} err={proc.stderr!r}"
    facts = json.loads(proc.stdout)
    obs, res, p = drive(wt, CHAINS, [CHAIN_PLAN], end=[C, D], dirty=facts)
    if kind == "staged":
        assert touched(obs) == {p[A]}, f"work continued over a real staged leftover: {sorted(touched(obs))}"
        assert "left_behind.txt" in (res.get("staged_leftovers") or []), H.output_text(res)
    else:
        assert p[D] in touched(obs), f"a real unstaged leftover must not stop the run: {H.output_text(res)}"
