"""
MODULE: test_inf_500d_4_e2e
GOAL: The composite acceptance tests for INF-500d-4 -- "a report written inside a
    temporary workspace is still readable after that workspace is gone" -- one test
    per scenario of the composite's own test_spec.
AC: INF-500d-4 (composite; its children -i .. -viii each prove one surface).

WHAT IS REAL: git (``git init``, plus adding and removing a linked checkout); a
    deployed install per worktree (``_inf_500d_4_helpers.deploy_install``); the
    declaration, written by the REAL build helper from the root the REAL
    ``inherited_log_root_args`` of the maker's log-root module returns for the main
    install; the writers (``submit_feedback.py``, ``emit_event.py``, the
    ``harvest_learnings.py --print-sink`` emit instruction) as subprocesses run
    from INSIDE a worktree; the readers (``aggregate.py``, ``harvest_learnings.py
    --print-sink``, ``extract_epic_facts.py``). Every durable-location read happens
    only AFTER the worktree has been removed, because reading first passes on the
    exact defect.

WHAT IS NOT: ``build.py`` is not spawned (one build is ~60s and the children
    already prove the build and the bootstrap's wiring of ``--log-root``); the
    maker's own ``inherited_log_root_args`` decides the inherited root here.
"""
# @ac-tag: INF-500d-4

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from unit_tests.feedback import _inf_500d_4_helpers as h
from unit_tests.portability import _inf_500d_4_e2e_helpers as e

_LOG_NAMES = ("feedback.jsonl", "agent_telemetry.jsonl", "knowledge_emissions.jsonl")


def _tmpdir(base: Path) -> Path:
    tmpdir = base / "tmpdir"
    tmpdir.mkdir(exist_ok=True)
    return tmpdir


def _is_under(path: Path, parent: Path) -> bool:
    return Path(os.path.realpath(path)).is_relative_to(os.path.realpath(parent))


def test_report_filed_in_a_bootstrapped_worktree_is_readable_after_the_worktree_is_removed(tmp_path):
    # covers: INF-500d-4
    # angle: real_artifact
    """First scenario. File a report from inside a worktree, capture the id from stdout, remove the worktree
    (clearing its linked checkout), then read the project's DECLARED feedback_sink and find that id there.
    Wrong versions caught: the worktree's declaration names the worktree's own root (the record leaves with
    it); a writer that ignores the declaration and writes beside ``__file__`` or the cwd."""
    tmpdir = _tmpdir(tmp_path)
    main, main_out = e.make_main_install(tmp_path, tmpdir)
    worktree, wt_out = e.add_worktree(main, tmp_path, "drive-one", tmpdir)
    declared = Path(h.read_declaration(main_out)["feedback_sink"])
    assert Path(h.read_declaration(wt_out)["feedback_sink"]) == declared, "the worktree declares a different sink"
    assert not _is_under(declared, worktree), "the declared sink lies inside the disposable worktree"

    feedback_id = e.submit(wt_out, worktree, tmpdir, "filed from inside the worktree")
    e.remove_worktree(main, worktree, tmpdir)

    assert declared.is_file(), f"the declared sink {declared} does not exist after the worktree was removed"
    stored = [r for r in h.read_records(declared) if r["feedback_id"] == feedback_id]
    assert len(stored) == 1, f"{feedback_id} is not stored exactly once in {declared}: {stored}"
    assert stored[0]["note"] == "filed from inside the worktree"
    # the id cited in a ticket resolves through the real reader, run from the surviving main install
    assert e.aggregate_ids(main_out, main, tmpdir) == [feedback_id]


def test_reports_from_two_removed_worktrees_are_both_in_the_one_durable_sink(tmp_path):
    # covers: INF-500d-4
    # angle: boundary
    """Second scenario. Two live worktrees of one project file reports (interleaved), both are removed, and
    every id from both is in the one declared feedback_sink with the earlier drive's lines byte-intact.
    Exact count (5), no duplicates, and a control: the first drive's bytes are a prefix of the final file."""
    tmpdir = _tmpdir(tmp_path)
    main, main_out = e.make_main_install(tmp_path, tmpdir)
    first, first_out = e.add_worktree(main, tmp_path, "drive-one", tmpdir)
    second, second_out = e.add_worktree(main, tmp_path, "drive-two", tmpdir)
    sink = Path(h.read_declaration(main_out)["feedback_sink"])
    assert Path(h.read_declaration(first_out)["feedback_sink"]) == sink == Path(
        h.read_declaration(second_out)["feedback_sink"]), "the two worktrees do not share one declared sink"

    first_ids = [e.submit(first_out, first, tmpdir, "drive one report 0"),
                 e.submit(first_out, first, tmpdir, "drive one report 1")]
    earlier_bytes = sink.read_bytes()
    second_ids = [e.submit(second_out, second, tmpdir, "drive two report 0")]
    first_ids.append(e.submit(first_out, first, tmpdir, "drive one report 2"))
    second_ids += [e.submit(second_out, second, tmpdir, "drive two report 1")]
    e.remove_worktree(main, first, tmpdir)
    e.remove_worktree(main, second, tmpdir)

    final_bytes = sink.read_bytes()
    assert final_bytes.startswith(earlier_bytes), "a later drive overwrote or displaced the earlier drive's lines"
    records = h.read_records(sink)
    ids = [r["feedback_id"] for r in records]
    assert len(ids) == 5 and len(set(ids)) == 5, f"expected exactly 5 distinct records, got {ids}"
    assert sorted(ids) == sorted([*first_ids, *second_ids])
    assert sorted(e.aggregate_ids(main_out, main, tmpdir)) == sorted(ids), "the reader does not see every drive's ids"


def test_config_guard_and_log_roots_hold_simultaneously_in_one_worktree(tmp_path):
    # covers: INF-500d-4
    # angle: seam
    """Third scenario, all three rules at once in one linked worktree: configuration -> the worktree's OWN
    .leafcutter/config (INF-100c-1-i); guard root -> the worktree toplevel (GE-113c-1-iv); log root -> the
    main install's declared root, outside the worktree and different from both.
    Wrong versions caught: a unified resolver moving config or guards to the main install (config/guard would
    equal main's); one leaving the logs on the worktree toplevel (log root would equal the guard root)."""
    tmpdir = _tmpdir(tmp_path)
    main, main_out = e.make_main_install(tmp_path, tmpdir)
    worktree, wt_out = e.add_worktree(main, tmp_path, "drive-one", tmpdir)
    probe = (
        "import importlib.util, json, sys\n"
        "def load(p, n):\n"
        "    s = importlib.util.spec_from_file_location(n, p)\n"
        "    m = importlib.util.module_from_spec(s); sys.modules[n] = m; s.loader.exec_module(m); return m\n"
        "fb = load(sys.argv[1], 'submit_feedback')\n"
        "rr = load(sys.argv[2], '_resolve_root')\n"
        "print(json.dumps({'config': str(fb._find_config_root().resolve()),"
        " 'guard': str(rr.find_project_root().resolve())}))\n"
    )
    proc = e.run([sys.executable, "-B", "-c", probe, str(h.submit_script(wt_out)),
                  str(wt_out / "scripts" / "commit_guardian" / "_resolve_root.py")], worktree, tmpdir)
    assert proc.returncode == 0, f"probe failed: {proc.stderr[-1500:]}"
    answers = json.loads(proc.stdout.strip().splitlines()[-1])
    query = e.run([sys.executable, "-B", str(wt_out / "scripts" / "knowledge" / "sink_resolution.py"),
                   "--print-location", "root"], worktree, tmpdir)
    assert query.returncode == 0, f"location query failed: {query.stderr[-800:]}"
    log_root = query.stdout.strip()

    assert answers["config"] == str((wt_out / "config").resolve()), "configuration left the worktree"
    assert answers["guard"] == str(worktree.resolve()), "the guard root is not the worktree toplevel"
    main_root = h.read_declaration(main_out)["operational_log_root"]
    assert log_root == main_root, f"the log root {log_root} is not the main install's {main_root}"
    assert not _is_under(Path(log_root), worktree), "the log root lies inside the worktree"
    assert len({answers["config"], answers["guard"], log_root}) == 3, "two of the three roots collapsed into one"
    assert answers["config"] != str((main_out / "config").resolve()), "config resolved to the main install"
    assert answers["guard"] != str(main.resolve()), "the guard root resolved to the main checkout"


def test_every_operational_log_lands_under_the_one_declared_root(tmp_path):
    # covers: INF-500d-4
    # angle: criterion
    """Fourth scenario. From inside a worktree: file a report, emit a telemetry event with no --log, append a
    knowledge record at the path ``harvest_learnings.py --print-sink`` returns (the shipped emit instruction);
    remove the worktree; all three logs sit under the one declared operational_log_root, are read back by the
    real readers, and none was ever created under the worktree."""
    tmpdir = _tmpdir(tmp_path)
    main, main_out = e.make_main_install(tmp_path, tmpdir)
    worktree, wt_out = e.add_worktree(main, tmp_path, "drive-one", tmpdir)
    root = Path(h.read_declaration(main_out)["operational_log_root"])
    epic = main / "tickets" / "00_inbox" / "epics" / "EPIC-Probe"
    epic.mkdir(parents=True)
    before = h.snapshot(worktree)

    feedback_id = e.submit(wt_out, worktree, tmpdir, "criterion four report")
    emit = e.run([sys.executable, "-B", str(h.emit_script(wt_out)), "--event", "agent_start", "--agent",
                  "ticket-supervisor", "--ticket", str(epic / "01_t.md"), "--phase", "python-coder"],
                 worktree, tmpdir)
    assert emit.returncode == 0, emit.stderr
    sink = e.run([sys.executable, "-B", str(wt_out / "scripts" / "knowledge" / "harvest_learnings.py"),
                  "--print-sink"], worktree, tmpdir)
    assert sink.returncode == 0 and sink.stdout.strip(), f"--print-sink refused: {sink.stderr!r}"
    knowledge = Path(sink.stdout.strip())
    record = {"event_type": "knowledge_captured", "text": "criterion four knowledge"}
    with open(knowledge, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")
    assert h.snapshot(worktree) == before, "a writer created something under the worktree"
    e.remove_worktree(main, worktree, tmpdir)

    for name in _LOG_NAMES:
        assert (root / name).is_file(), f"{name} is not under the declared root {root} after removal"
    assert sorted(p.name for p in root.iterdir() if p.suffix == ".jsonl") == sorted(_LOG_NAMES), \
        f"unexpected log set under {root}: {sorted(p.name for p in root.iterdir())}"
    assert knowledge == root / "knowledge_emissions.jsonl", f"--print-sink named {knowledge}, not the declared root"
    assert [r["feedback_id"] for r in h.read_records(root / "feedback.jsonl")] == [feedback_id]
    assert [r["event_type"] for r in h.read_records(root / "agent_telemetry.jsonl")] == ["agent_start"]
    assert h.read_records(root / "knowledge_emissions.jsonl") == [record]
    # the real readers, run from the surviving main install, find them where the worktree wrote them
    assert e.aggregate_ids(main_out, main, tmpdir) == [feedback_id]
    facts = e.run([sys.executable, "-B", str(main_out / "scripts" / "retrospective" / "extract_epic_facts.py"),
                   str(epic)], main, tmpdir)
    assert facts.returncode == 0, facts.stderr
    assert json.loads(facts.stdout)["telemetry_events"].get("agent_start") == 1
    main_sink = e.run([sys.executable, "-B", str(main_out / "scripts" / "knowledge" / "harvest_learnings.py"),
                       "--print-sink"], main, tmpdir)
    assert Path(main_sink.stdout.strip()) == knowledge, "main and the removed worktree disagree on the knowledge sink"
