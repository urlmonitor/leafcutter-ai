---
title: "Wrong-Version Run — Sequence Diagram"
description: "L3 sequence diagram of one wrong-version run as the code does it: the route dispatches wrong_version_gate.py finish (sweep check, then the writer, then the runner); the runner recovers, resolves the scope and runs the baseline on the code as written; then, for each wrong version, it prepares and compares, copies and journals, applies, makes one pytest run, reads it, puts the files and the test database back, and classifies the rows. The verdict goes back to the route, which halts before its commit on a survivor. Branches: not applied, could not be prepared, did not load, the re-deploy trap, cut short and hard kill, a failed put-back, and finish's sweep and write stops."
type: architecture
diagram_type: sequence
flight_level: L3-Component
status: draft
root: true
created: 2026-10-23
last_updated: 2026-10-23
source_ticket: null
components:
  - testing_quality
  - build_orchestration
related_docs:
  - docs/reference/wrong-version-runs.md
  - docs/architecture/diagrams/c2-fast-vs-heavy-lane-phases.md
  - docs/architecture/diagrams/c3-done-proof-evaluation-sequence.md
  - docs/architecture/components/build-orchestration.md
  - docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500g-5-ii.yaml
related_code:
  - scripts/build_orchestration/wrong_version_gate.py
  - scripts/build_orchestration/wrong_version_runner.py
  - scripts/build_orchestration/_wvr_gate.py
  - scripts/build_orchestration/_wvr_pytest.py
  - scripts/build_orchestration/_wvr_verdict.py
  - scripts/build_orchestration/_wvr_db.py
  - scripts/build_orchestration/_wvr_db_plugin.py
  - scripts/build_orchestration/_wvr_scope.py
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/build-ticket.js
tags:
  - wrong-version-runs
  - TQ-500g-5-ii
---

# Wrong-Version Run — Sequence Diagram

This page follows one wrong-version run from the build route's `finish` dispatch to the
verdict the route acts on. It is drawn from `wrong_version_gate.py`,
`wrong_version_runner.py` and its `_wvr_*` siblings as they are on main. The result words
and stop reasons in the labels are the ones the
[wrong-version runs reference](../../reference/wrong-version-runs.md) lists.

It has three diagrams:

1. **From the route to the verdict.** `finish`, the precondition block (recover, scope,
   baseline), the loop over the wrong versions, and the route's halt before commit.
2. **One cycle.** What happens to one wrong version: prepare and compare, copy and
   journal, apply, one pytest run, read, put back, classify.
3. **When a cycle goes wrong.** The database run and its re-deploy trap, a run cut short,
   a hard kill, and a put-back that fails.

> **The runner decides, the route obeys.** Every verdict is the runner's own JSON.
> `finish` prints it inside its own object without changing it. The route only parses
> `gate_passed` and halts when it is not `true`. It holds no rule of its own.

## Diagram 1 — From the route to the verdict

```mermaid
sequenceDiagram
    autonumber
    actor Route as Build route<br/>(fast-lane-ship / build-ticket / build-feature)<br/>through command-step-runner
    participant FIN as wrong_version_gate.py finish
    participant RUN as wrong_version_runner.py run
    participant GATE as RunGate (_wvr_gate)<br/>&lt;git-dir&gt;/leafcutter/wrong-version-runs/&lt;run-id&gt;/
    participant PY as pytest child<br/>(-p _kind_plugin)
    participant READ as shared reading<br/>(pytest_outcome_reader + kind rule)
    participant VER as _wvr_verdict

    Route->>FIN: finish --work-key K --reply - (the test-breaker reply on stdin)
    FIN->>FIN: consumer_sweep.py check, then wrong_version_writer.py write
    alt the sweep check did not pass
        FIN-->>Route: {gate_passed: false, stopped_at: "sweep"}
    else the writer stopped (written is not true, or no manifest_path)
        FIN-->>Route: {gate_passed: false, stopped_at: "write"}
    end
    Note over Route,FIN: In both stops the runner is never called and the route halts.
    FIN->>RUN: run --ac-ids ... --alterations &lt;manifest_path&gt;

    rect rgba(128, 128, 128, 0.12)
        Note over RUN,READ: Precondition block — before any wrong version
        RUN->>GATE: (0) recover_all: put back every file with an open journal.json
        GATE-->>RUN: RestoreResult (not ok: the run stops, see Diagram 3)
        RUN->>RUN: (1) resolve_scope from each test's test_spec entry, then the database gate
        RUN->>PY: (2) baseline: one run of every runnable test on the code as written
        PY-->>READ: verbose output and the kind plugin's file
        READ-->>RUN: PytestRun {status, outcome, kind}
        alt a test is not PASSED on the code as written
            RUN-->>FIN: gate_passed false, reason "failing on the code as written"
        end
    end

    loop each wrong version: the named versions, then the extras, then "the fix undone"
        RUN->>GATE: one cycle — Diagram 2 (branches in Diagram 3)
        GATE-->>RUN: the code is put back byte for byte
        RUN->>VER: classify_run(...)
        VER-->>RUN: the rows of this wrong version
    end

    RUN->>VER: assemble(rows)
    VER-->>RUN: {gate_passed, applicable, verified, outcome, reason, results,<br/>survivors, unfinished, non_blocking_survivors}
    RUN-->>FIN: one JSON object on stdout, exit 0 only when gate_passed
    FIN-->>Route: {gate_passed, stopped_at: null, sweep, writer, verdict}
    alt gate_passed true
        Route->>Route: go on to the commit dispatch
    else reason "survivor" (or "unfinished", or a stop reason)
        Route-->>Route: halt before the commit dispatch: status blocked, gate "wrong_version_gate"
    end
```

Parent: [Fast-Lane vs Heavy-Pipeline Phase Order — Component Diagram](c2-fast-vs-heavy-lane-phases.md)

## Diagram 2 — One cycle: apply, run, read, put back, classify

```mermaid
sequenceDiagram
    autonumber
    participant RUN as wrong_version_runner.py run
    participant GATE as RunGate (_wvr_gate)<br/>copies + journal.json
    participant WT as working tree
    participant PY as pytest child<br/>(-p _kind_plugin)
    participant READ as shared reading<br/>(pytest_outcome_reader + kind rule)
    participant VER as _wvr_verdict

    RUN->>RUN: _prepare: the manifest entry, or "the fix undone" from git at the base ref, then the scope check
    alt could not be prepared (no manifest entry, a bad entry, a file out of scope)
        RUN->>VER: row(..., "invalid", "wrong version could not be prepared: ...")
        Note over RUN,WT: Nothing is copied, applied or run.
    else the fix undone has no file to restore (every changed non-test file is new)
        RUN->>VER: row("", "the fix undone", "not_applicable", "every changed non-test file is new<br/>(&lt;n&gt; created)#59; the fix undone does not apply")
        Note over RUN,WT: Non-blocking. Nothing is copied, applied or run.
    end
    RUN->>WT: read each file to alter
    WT-->>RUN: the bytes as written
    alt the alteration is byte-identical to the code as written
        RUN->>VER: row(..., "not_applied", "wrong version not applied: it changes nothing")
        Note over RUN,PY: No copy is taken. Nothing is applied or run.
    end

    RUN->>GATE: apply(wrong version, files)
    GATE->>GATE: write copy-N-&lt;file&gt;, read it back, compare
    GATE->>GATE: write journal.json durably (temp file, fsync, atomic replace)
    GATE->>WT: only then write the altered bytes
    RUN->>PY: run_selected: the tests whose own entry names it<br/>(every in-scope test for "the fix undone")
    PY-->>READ: verbose output and the kind plugin's file
    READ-->>RUN: PytestRun: outcome per test, kind per failure (assertion | absence)
    RUN->>GATE: restore() — in a finally block, every time
    GATE->>WT: write the copy back where the bytes differ, re-read, byte-compare
    GATE->>GATE: close the journal (journal.json to journal.done), clear the run directory
    GATE-->>RUN: RestoreResult ok
    RUN->>VER: classify_run(ran, holders, run, name, is_undone)
    alt FAILED by an assertion
        VER-->>RUN: caught
    else FAILED by absence, or the test file failed to collect
        VER-->>RUN: did_not_load, "wrong version did not load: not a valid run" (run, never counted)
    else PASSED
        VER-->>RUN: survived, "passed under '...': the test did not notice it"
    else FAILED, but the kind could not be determined
        VER-->>RUN: invalid
    else no result, or neither passed nor failed
        VER-->>RUN: not_run
    end
```

See also: [Wrong-version runs — reference](../../reference/wrong-version-runs.md) for every
result word and stop reason.

## Diagram 3 — When a cycle goes wrong

```mermaid
sequenceDiagram
    autonumber
    actor Route as Build route
    participant RUN as wrong_version_runner.py run
    participant GATE as RunGate (_wvr_gate)<br/>copies + journal.json
    participant PY as pytest child<br/>(-p _kind_plugin -p _wvr_db_plugin)
    participant DB as test database

    Note over RUN,DB: A database run: a .sql file is altered over a requires_db test (_wvr_db.begin)
    RUN->>PY: run_selected with _wvr_db_plugin (config and findings in temp files)
    PY->>DB: pytest_sessionstart: install the wrong version's definitions
    PY->>DB: after each database test's call phase: read pg_proc on its own connection
    DB-->>PY: the body each object holds (findings file)
    RUN->>DB: after the file put-back, _wvr_db.finish: _wvr_db_plugin.py put-back<br/>(re-install the code as written, re-read the catalogue)
    alt _wvr_db.judge: the catalogue held the code as written (the suite re-installed it)
        Note over RUN: row invalid: "the suite put the correct code back before the tests ran:<br/>&lt;object&gt; held the code as written"
    else neither version, unreadable, or no capture
        Note over RUN: row not_run
    end

    alt cut short: timeout, crash, or interruption (SIGTERM/SIGBREAK become KeyboardInterrupt)
        RUN->>GATE: restore() runs first, in the finally block, before anything else
        Note over RUN: rows not_run "the run was cut short (...)". An interruption also ends the loop.
    else hard kill: the process dies with the wrong version on disk
        Note over GATE: journal.json stays open, with the copies beside it
        Route->>RUN: next run step (recover_all first) or the route's recover step on a resumed drive
        RUN->>GATE: put every open file back from its copy, then close the journal
        RUN-->>Route: {restored, ok, copy_dir} (ok false: the route halts)
    end

    alt the file put-back failed (still differs, or could not be put back or read)
        GATE-->>RUN: "the code may still be altered: &lt;path&gt; ... the copy of the code<br/>as written is kept at &lt;absolute path&gt;"
        RUN-->>Route: the drive stops: no later wrong version runs, reason names the kept copy
    else the database put-back failed
        RUN->>RUN: the put-back reports install_failed, mismatch, reread_failed or unreadable
        RUN-->>Route: the drive stops: "the database was not put back: &lt;objects&gt; ..."
    end
```

## Walk-through (as implemented)

1. **finish.** The route sends one command through `command-step-runner`:
   `wrong_version_gate.py finish`, with the test-breaker's reply on stdin. `finish` runs
   `consumer_sweep.py check` first. If that does not pass it returns `stopped_at: "sweep"`.
   It then runs the writer's `write` step. If the writer did not write, or gave no
   `manifest_path`, it returns `stopped_at: "write"`. In both cases the runner is never
   called. Otherwise it runs `wrong_version_runner.py run` with that manifest and prints
   `{gate_passed, stopped_at, sweep, writer, verdict}`, with the runner's verdict verbatim.
2. **Recover.** Every `run` begins with `recover_all` over
   `<git-dir>/leafcutter/wrong-version-runs/`. Any run directory that still has an open
   `journal.json` is put back from its copies first. If that fails, the run stops with the
   failure as its reason.
3. **Scope.** `resolve_scope` reads each covering test's `test_spec` entry. A problem in
   the scope gives an `invalid` row. A test whose entry names no wrong version is
   `not_in_scope`. With no test in scope, the runs are not applicable. If a `requires_db`
   test is in scope, the database gate (`check_test_db`, once) decides whether it runs.
   If it cannot run, it gets `not_run` rows.
4. **Baseline.** One pytest run of every runnable test on the code as written. On a
   database run the as-written SQL is installed first. A test that is not `PASSED` stops
   the run with reason `"failing on the code as written"`. A baseline that is cut short
   leaves the work `unfinished`.
5. **Each wrong version.** The named versions are taken in order, then the extras left
   "to run later", then "the fix undone". `_prepare` builds the alteration. If it cannot,
   the row is `invalid` and `unfinished` lists it as `could_not_prepare`. The alteration
   is compared with the working file. If the bytes are identical, the row is `not_applied`
   and nothing is copied or run.
6. **Apply.** `RunGate.apply` writes each copy, reads it back and compares it. It writes
   the journal durably, and only then alters the working file. A copy or journal that
   cannot be written means nothing is altered.
7. **One pytest run.** It runs the tests whose own entry names the wrong version, or
   every in-scope test for "the fix undone". `_kind_plugin` is loaded, plus
   `_wvr_db_plugin` on a database run. The outcomes come from the shared
   `pytest_outcome_reader`, and the failure kinds from the shared kind rule. Both are read
   from that same single run.
8. **Put back.** `restore()` runs in a `finally` block after every run, even one that was
   cut short. It writes each copy back, re-reads the file and byte-compares it, then
   closes the journal. On a database run, `_wvr_db.finish` then re-installs the
   as-written definitions and re-reads the catalogue. A put-back that fails stops the
   drive (Diagram 3).
9. **Classify.** A failure by assertion is `caught`. A failure by absence is
   `did_not_load`. A pass is `survived`. Anything else is `not_run` or `invalid`. On a
   database run, `_wvr_db.judge` then overrules the database tests' rows: if the
   catalogue held the code as written, the row is `invalid` (the re-deploy trap). If it
   held neither version, could not be read, or nothing was captured, the row is
   `not_run`. An extra's rows are made non-blocking.
10. **Verdict.** `assemble` puts a survivor before `unfinished` in `reason`.
    `gate_passed` is true only when there is no reason. The route halts before its commit
    on any `gate_passed` other than `true` (see below).

## Where each route halts on a survivor

| Route | Where the verdict is read | What a `gate_passed` false does |
|---|---|---|
| `/fast-lane-build` (`fast-lane-ship.js`) | the Wrong-Version Runs phase, before Phase 5 Commit | releases the claimed ACs, returns `blocked`, no PR is opened |
| `build-ticket.js` / `build-feature.js` | `wvRuns`, just before the commit phase agent is dispatched | returns `refuse(...)` with `gate: "wrong_version_gate"`, no commit agent is spawned |
| `/build-epic` | each ticket's run (as above) | no commit is spawned. The `check_build_epic_gate_verdicts.py` hook backstop blocks a commit that has no passing, fresh record |

The `recover` step (`wrong_version_runner.py recover`) runs at the head of `build-epic`
and `build-ticket`, and of `build-feature` on a resumed worktree. It also runs in the
fast lane when the workspace was not newly created, that is, on a resumed drive. That step is how a hard kill in an earlier drive
gets put back, if no `run` comes first.

## Legend

| Element | Meaning |
|---|---|
| Participant box | One party in the run: the route, `finish`, the runner, the gate files, the working tree, the pytest child, the shared reading, `_wvr_verdict`, the test database |
| Numbered solid arrow (`->>`) | A call, a dispatch or a write, in time order |
| Dashed arrow (`-->>`) | A reply, or a result going back |
| Arrow from a participant to itself | Work inside one process with no other party involved |
| `rect` block | The precondition block: recover, scope, baseline |
| `loop` block | Done once for each wrong version |
| `alt` / `else` block | Outcomes that exclude each other. Only one of them happens |
| `Note over` | A fact about the step, or the row it produces |

## Cross-Links

- Parent: [Fast-Lane vs Heavy-Pipeline Phase Order — Component Diagram](c2-fast-vs-heavy-lane-phases.md)
- Reference: [Wrong-version runs](../../reference/wrong-version-runs.md), with the result words, stop reasons and the put-back folder
- House style and sibling: [Done-Proof Evaluation — Sequence Diagram](c3-done-proof-evaluation-sequence.md)
- Component page: [Build Orchestration — Component Overview](../components/build-orchestration.md)
- Requirement: [TQ-500g-5-ii](../../acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500g-5-ii.yaml)

<!--
====================================================================
DECISION HISTORY
====================================================================
- 2026-10-23 [architecture-diagram-author, TQ-500g-5-ii]: Initial creation.
  The number 036 was pinned by the caller (035 goes to TQ-500g-5-i, written in
  parallel). scripts/next_diagram_seq.py was not run, as instructed. The
  scaffold scripts/scaffold/new_arch_doc.py does not exist in this repository.
  So the frontmatter and the Legend were written by hand under the standing
  scaffold-free pass dec-b10271ebb40b9eaa, following the shape of c3-034. Level 3,
  parent c2-fast-vs-heavy-lane-phases.md (user decision OQ-3, 2026-10-23). That
  parent is itself flight_level L3-Component, and check-mermaid-parent-link
  refuses an L3 parent for an L3 diagram (ARCH-LEVEL-ORDER). So this page sets
  root: true, as c3-034 does, and links the parent in prose only. It is not
  listed in the parent's children: (the parent page is left untouched, since
  it would fail the same L3-under-L3 rule). The continuation is drawn as Diagrams 2 and 3 on this
  same page instead of a second numbered file, because only 036 was reserved.
  Each block stays within 8 participants. Every message was checked against
  the code at 5437ab6ec (this branch's head; main ae3a1591c plus doc-only commits).
====================================================================
-->
