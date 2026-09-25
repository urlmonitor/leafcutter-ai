---
title: "Done-Proof Evaluation — Sequence Diagram"
description: "L3 sequence diagram of verify_done_eligible — from collecting # covers tags and resolving them against the AC YAML store, through running pytest as a subprocess and classifying outcomes, through the mechanical entry-point reachability gate (BO-2900a-1) that refuses a proof reaching the code by direct import when the unit has a real way in, to the final per-AC eligible/blocked verdict emitted by the mechanical gate."
type: architecture
diagram_type: sequence
flight_level: L3-Component
status: active
created: 2026-07-21
last_updated: 2026-09-25
components:
  - build_orchestration
  - testing_quality
  - ac_store
related_docs:
  - docs/architecture/components/build-orchestration.md
  - docs/how-to/prove-ac-done.md
  - docs/how-to/done-proof-enforcement.md
  - docs/architecture/diagrams/c2-fast-vs-heavy-lane-phases.md
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900a-1.yaml
related_code:
  - scripts/ac_store/done_proof.py
  - scripts/ac_store/_done_proof_entry_point_gate.py
  - templates/scripts/commit_guardian/check_done_proof.py
---

# Done-Proof Evaluation — Sequence Diagram

This diagram documents the message-level interaction of `verify_done_eligible()` in
`scripts/ac_store/done_proof.py` — the authoritative eligibility oracle for the BO-2500
done-proof gate. It covers the full evaluation path from the gate invoking the oracle,
through AC-store resolution, test-tree scanning, pytest execution, outcome classification,
the mechanical entry-point reachability gate, and finally the per-AC eligible or blocked
verdict returned to the caller.

> **The gate, not the caller, emits the verdict.** `verify_done_eligible()` is the
> mechanical gate: it owns the evaluation logic and always returns a structured
> `{eligible, reason, passing_tests, failing_tests, dangling_tags, refusal_cause, unit,
> entry_point, offending_test}` dict. The caller (`check_done_proof.py` or `fast_lane.py`)
> decides what to do with that verdict — block the commit, emit a warning, or proceed.

> **Scope of this diagram (BO-2900a-1).** The mechanical entry-point reachability gate
> below is evaluated only after the incumbent pass/fail gate (Phases 1-5) already
> returned `eligible: True`. It never changes the "no linked test" or "linked test
> failed" verdicts documented in Phases 1-5. A separate, disjoint rule — the
> no-entry-point-anywhere gate (`_apply_reachability_gate`, `refusal_cause:
> "no_entry_point_reaches_code"`) — runs after this one for the case where NO linked
> test's module exposes a way in at all; that rule is out of this diagram's scope and
> is decided separately (see the scope-fence note in step 9 below).

---

```mermaid
sequenceDiagram
    autonumber
    actor Gate as Mechanical Gate<br/>(check_done_proof.py / fast_lane.py)
    participant VDE as verify_done_eligible<br/>(done_proof.py)
    participant ACS as AC YAML Store<br/>(docs/acceptance-criteria/**/*.yaml)
    participant TFS as Test File System<br/>(unit_tests/**/*.py)
    participant Pytest as pytest subprocess<br/>(python -m pytest -v)
    participant Runner as Reachability observer<br/>(fresh subprocess, sys.setprofile)

    Note over Gate,Pytest: Eligibility evaluation — invoked at commit-gate or pre-merge
    Gate->>VDE: verify_done_eligible(ac_id, ac_root=..., test_root=...)

    Note over VDE,ACS: Phase 1 — Build AC status map
    VDE->>ACS: _build_ac_status_map(ac_root)<br/>rglob *.yaml; read id + status fields per file
    Note over ACS: Unreadable files logged to stderr and skipped.<br/>Returns {} when ac_root does not exist.
    ACS-->>VDE: {ac_id: status} map<br/>(e.g. "active" / "deprecated" / "superseded")

    Note over VDE,TFS: Phase 2 — Scan test tree for # covers tags
    VDE->>TFS: _scan_test_root_for_covers_tags(test_root)<br/>rglob *.py → _scan_single_test_file per file
    Note over TFS: Per file: tracks most-recent def test_* as enclosing function.<br/>Extracts # covers:<id> tags inside that function scope.<br/>Tags before any def test_* are silently skipped.
    TFS-->>VDE: all_tags list<br/>[{ac_id, function, file, location}]

    Note over VDE: Phase 3 — Pure classification (no I/O, no try/except)
    VDE->>VDE: _collect_dangling_tags(all_tags, ac_status_map)<br/>Tags where ac_id absent from map or status != "active"<br/>→ dangling list [{id, location}]
    VDE->>VDE: _collect_linked_tests(ac_id, all_tags)<br/>Filter: tag["ac_id"] == queried ac_id<br/>→ linked_tests list

    alt No linked tests found for queried ac_id
        Note over VDE,Gate: BLOCKED — no # covers:<ac_id> tag exists anywhere under test_root
        VDE-->>Gate: {eligible: False,<br/>reason: "no linked test found for <ac_id>",<br/>passing_tests: [],<br/>failing_tests: [],<br/>dangling_tags: [...]}
    else Linked tests exist
        Note over VDE,Pytest: Phase 4 — Run pytest on linked test files (I/O boundary)
        VDE->>Pytest: _run_pytest_and_parse(test_files)<br/>python -m pytest -v --tb=no --no-header<br/>timeout: 60 s; capture_output=True
        Note over Pytest: Parses -v output lines:<br/>&lt;nodeid&gt; PASSED|FAILED|XFAIL|XPASS|SKIPPED|ERROR<br/>Returns {} on TimeoutExpired or OSError (logged to stderr).
        Pytest-->>VDE: {nodeid: outcome} mapping

        Note over VDE: Phase 5 — Classify outcomes (fail-closed)<br/>Only PASSED counts as passing.<br/>XFAIL / XPASS / SKIPPED / FAILED / ERROR → non-passing.<br/>Unlocated nodeid (not in pytest results) → non-passing.<br/>This prevents xfail-masking from satisfying the done gate.
        VDE->>VDE: _classify_outcomes(linked_tests, pytest_results)<br/>_find_nodeid_for_test: exact file+fn match, then fn-suffix fallback<br/>→ (passing_nodeids, failing_nodeids)

        alt Any failing_tests (non-empty)
            Note over VDE,Gate: BLOCKED — at least one covers-linked test did not PASS
            VDE-->>Gate: {eligible: False,<br/>reason: "linked test &lt;outcome&gt;: &lt;nodeid&gt;...",<br/>passing_tests: [...],<br/>failing_tests: [...],<br/>dangling_tags: [...]}
        else All covers-linked tests PASSED
            Note over VDE: Phase 6 — Mechanical entry-point reachability gate (BO-2900a-1)<br/>Evaluated only now that the pass/fail gate is satisfied.<br/>No new keyword argument — every real caller gets this unconditionally.
            loop For each linked Python test
                VDE->>VDE: _detect_module_entry_point(test_file, project_root, test_root)<br/>AST-only, checked in order: (1) test_file itself, then<br/>(2) each module test_file imports, resolved via the SAME<br/>_local_import_module_names / _resolve_candidate_unit pair<br/>the sibling no-entry-point-anywhere gate (below) already uses.<br/>Never filename, folder, docstring, or `if __name__` text match.
                alt No module-level main found in test_file OR any module it imports
                    Note over VDE: Scope fence — this rule does not fire for this test.<br/>Falls through to the no-entry-point-anywhere gate that always runs next (see below).
                else main found — resolved_module exposes a runtime way in<br/>(test_file itself, OR the first imported module found to define main)
                    VDE->>Runner: _observe_reachability(test_file, function, target_spec="", entry_spec="<resolved_module>:main")<br/>Re-executes the test under a call-stack profiler.
                    Note over Runner: Fresh subprocess, 30 s timeout.<br/>Records whether `main` was a live ancestor frame during this SAME<br/>execution (never read from source text), AND whether that isolated<br/>re-run itself passed — {entered_entry_point, observation_ok, passed}.
                    Runner-->>VDE: {entered_entry_point, observation_ok, passed}

                    alt observation_ok is False OR passed is False
                        Note over VDE,Gate: BLOCKED — observation subprocess failed, produced no parseable result,<br/>or its isolated re-run did not pass (bypasses pytest fixtures/conftest the<br/>original passing run used, so a failure here is not comparable to "did not enter")
                        VDE-->>Gate: {eligible: False,<br/>refusal_cause: "observation_unavailable",<br/>unit: resolved_module.stem,<br/>entry_point: "&lt;resolved_module&gt;:main",<br/>offending_test: "&lt;file&gt;::&lt;function&gt;"}
                    else entered_entry_point is False
                        Note over VDE,Gate: BLOCKED — proof reached the code by direct import, never through main
                        VDE-->>Gate: {eligible: False,<br/>reason: "...reached the code by direct import instead of through &lt;entry_point&gt;",<br/>refusal_cause: "proof_not_through_entry_point",<br/>unit: resolved_module.stem,<br/>entry_point: "&lt;resolved_module&gt;:main",<br/>offending_test: "&lt;file&gt;::&lt;function&gt;"}
                    else entered_entry_point is True
                        Note over VDE: Verdict unchanged — this test's proof drove the real way in.
                    end
                end
            end

            Note over VDE: Phase 6.5 — No-entry-point-anywhere gate (BO-2900a-3, sibling, always runs next)<br/>_apply_reachability_gate() now GUARDS on verdict["eligible"] first: an already-refused<br/>Phase-6 verdict returns unchanged — it is never overwritten with this gate's own,<br/>independently-computed "no_entry_point_reaches_code" verdict for the same unit.<br/>Full mechanism (exemption seam, etc.) is out of THIS diagram's scope — see the table below.

            Note over VDE,Gate: ELIGIBLE — every covers-linked test PASSED, every one whose resolved<br/>module exposes a way in had its own run enter it, and the no-entry-point-anywhere<br/>gate found no unit with no way in at all (or granted a recorded exemption)
            VDE-->>Gate: {eligible: True,<br/>reason: "",<br/>passing_tests: [...],<br/>failing_tests: [],<br/>dangling_tags: [...]}
        end
    end
```

---

## Evaluation walk-through (as implemented)

1. **Gate invokes the oracle.** `check_done_proof.py` (pre-commit hook) or `fast_lane.py`
   calls `verify_done_eligible(ac_id, ac_root=..., test_root=...)`. The gate owns no
   evaluation logic — it delegates entirely to the oracle and acts on the returned verdict.

2. **AC status map built.** `_build_ac_status_map` walks `ac_root.rglob("*.yaml")`,
   loading each file with `yaml.safe_load`. Files that cannot be read or parsed are logged
   to stderr and skipped. The resulting `{ac_id: status}` dict is used in two places:
   dangling-tag detection and (implicitly) confirming the queried AC itself is active.

3. **Test tree scanned for covers tags.** `_scan_test_root_for_covers_tags` calls
   `_scan_single_test_file` for every `*.py` file found via `rglob`. Within each file,
   the scanner tracks the most-recently-seen `def test_*` definition as the enclosing
   context. A `# covers:<id>` tag found before any `def test_*` line is silently ignored,
   so tags must be placed inside (or immediately after) a test function to be counted.

4. **Dangling tags collected.** `_collect_dangling_tags` flags every tag whose `ac_id`
   is absent from the status map (no YAML file found) or whose resolved status is not
   `"active"` (e.g. deprecated, superseded). These are surfaced in `dangling_tags` on
   every verdict — they are advisory, not blocking, but indicate stale cross-references.

5. **Linked tests filtered.** `_collect_linked_tests` returns only the tags where
   `tag["ac_id"] == ac_id`. If the result is empty, the oracle returns immediately with
   `eligible: False` and reason `"no linked test found for <ac_id>"` — no pytest is run.

6. **pytest run on linked files.** `_run_pytest_and_parse` builds the command
   `python -m pytest -v --tb=no --no-header` against the deduplicated set of test files.
   The `-v` flag is required; exit code alone cannot distinguish XFAIL/SKIP from PASSED.
   On `TimeoutExpired` (60 s cap) or `OSError`, a warning is printed to stderr and `{}`
   is returned — empty results cause all linked tests to classify as non-passing
   (fail-closed).

7. **Outcomes classified — fail-closed.** `_classify_outcomes` matches each linked test
   to its nodeid using `_find_nodeid_for_test` (exact file-basename + function-name match
   first, then function-name suffix fallback). Only `PASSED` is treated as passing.
   `XFAIL`, `XPASS`, `SKIPPED`, `FAILED`, `ERROR`, and any unlocated test all count as
   non-passing. This prevents xfail-masking: a test marked `@pytest.mark.xfail` that
   produces `XFAIL` does **not** satisfy the done gate.

8. **Pass/fail verdict computed.** If any `failing_tests` exist, `eligible: False` is
   returned immediately with a reason naming each non-passing nodeid and its outcome —
   Phase 6 below never runs in that case. If all linked tests passed, evaluation
   continues into Phase 6 rather than returning yet. In both branches `dangling_tags`
   is included so the gate can surface stale cross-references to the developer.

## 3. The mechanical entry-point reachability gate (BO-2900a-1)

9. **Entry-point detected per linked Python test — AST only, checked in two places.**
   For each linked Python test, `_detect_module_entry_point(test_file, project_root,
   test_root)` (`scripts/ac_store/_done_proof_entry_point_gate.py`) looks for a
   module-level `def main` or `async def main`, checked in order: (1) *test_file*
   itself — this AC family's single-file fixture convention, where the implementing
   function, `main`, and the covers-tagged proof test all live in one module — then
   (2) each bare module *test_file* imports, resolved the SAME way the sibling
   no-entry-point-anywhere gate resolves candidate units
   (`_local_import_module_names` / `_resolve_candidate_unit`, both in
   `scripts/ac_store/done_proof.py`) — the codebase's normal separate
   test/implementation layout (e.g. `fast_lane.main`,
   `scripts/build_orchestration/fast_lane.py:925`), which a same-file-only check would
   never catch. This is a structural AST check only — a filename, folder name,
   docstring, or `if __name__ == "__main__":` text match is never treated as evidence
   of a way in. No `main` found in *test_file* or any module it imports means Phase 6
   does not fire for that test at all: this is the **scope fence** — see the
   composition note after step 11 for what happens to that verdict next.

10. **Reachability observed by execution, never by source text.** When a `main` is
    found (in *test_file* itself, or in the first of its imports that has one —
    call this the *resolved module*), `_observe_reachability`
    (`scripts/ac_store/done_proof.py`) re-runs the covers-tagged test itself in a
    fresh subprocess with a call-stack profiler (`sys.setprofile`) installed, and
    records whether `main` was a live ancestor frame at any point during that single
    execution — plus whether that isolated re-run itself passed. The subprocess has
    a 30 s timeout; an `OSError` or unparseable result fails closed to
    `observation_ok: False` rather than being read as "did not enter".

11. **Verdict revised — only ever tightened, never loosened.** For each linked test
    with a detected entry point:
    - `observation_ok` is `False`, **or** the isolated re-run's own `passed` is
      `False` → `eligible: False`, `refusal_cause: "observation_unavailable"`. The
      `passed` check exists because the bare re-execution `_observe_reachability`
      performs bypasses the pytest fixtures/conftest/parametrize machinery the
      original, already-passing pytest run used — an isolated-run failure for an
      unrelated reason (e.g. a fixture-arg `TypeError`) must not be misreported as
      "direct import".
    - `observation_ok` is `True`, `passed` is `True`, and `entered_entry_point` is
      `False` → `eligible: False`, `refusal_cause: "proof_not_through_entry_point"`,
      with `reason` naming "direct import" and the verdict carrying `unit` (the
      *resolved module's* stem — the implementing module's own name when the
      cross-file branch fired, not always `test_file`'s), `entry_point`
      (`"<resolved module>:main"`), and `offending_test` (`"<file>::<function>"`).
    - `entered_entry_point` is `True` → the verdict from step 8 is returned
      unchanged for that test.
    The first linked test to fail this check short-circuits the loop; a Phase 6
    refusal can only ever turn an `eligible: True` verdict into `eligible: False` —
    it never grants eligibility on its own.

### Composition: Phase 6's output always feeds the no-entry-point-anywhere gate next

`verify_done_eligible` composes the two reachability gates unconditionally —
`_apply_reachability_gate(_apply_entry_point_reachability_gate(success_verdict, ...),
...)` — so the sibling no-entry-point-anywhere gate (BO-2900a-3,
`_apply_reachability_gate`, `scripts/ac_store/done_proof.py`) always runs
immediately after Phase 6, on Phase 6's *output*, never independently. That sibling
gate computes its own, different notion of "has a way in"
(`_has_entry_point_of_its_own` / `_is_imported_elsewhere`, both regex/import-graph
based rather than the AST `_module_defines_main` check Phase 6 uses) and, for a unit
its own check judges to have no way in, would otherwise build a *fresh* verdict dict
— discarding whatever Phase 6 already decided. `_apply_reachability_gate` therefore
opens with `if not verdict.get("eligible"): return verdict`: an already-refused
Phase-6 verdict is returned unchanged, never silently overwritten with the sibling
gate's own `refusal_cause: "no_entry_point_reaches_code"` for the same unit. This is
what keeps the two `refusal_cause` values disjoint in practice, not merely by the two
functions never being called together — see the invariant table below.

## Key invariant: fail-closed on every ambiguity

| pytest outcome | Counts as passing? | Notes |
|---|---|---|
| `PASSED` | Yes | Only outcome that satisfies the gate |
| `FAILED` | No | Test assertion failed |
| `XFAIL` | No | Expected failure — does not prove the AC works |
| `XPASS` | No | Unexpectedly passed — flag for review |
| `SKIPPED` | No | Test did not run — cannot prove coverage |
| `ERROR` | No | Collection/setup error — test did not run |
| Not in results | No | Unlocated nodeid — treated as non-passing |

## Key invariant: the scope fence between the two reachability refusal causes

`refusal_cause: "proof_not_through_entry_point"` (Phase 6, this diagram) and
`refusal_cause: "no_entry_point_reaches_code"` (the sibling no-entry-point-anywhere
gate, full mechanism out of this diagram's scope) are deliberately two disjoint
values rather than one merged "unreachable" verdict — each names a different fact
and clears a different way. As the composition note above spells out, both gates
always run, in this fixed order, on every eligible verdict; disjointness is enforced
by the no-entry-point-anywhere gate's own eligibility guard, not by the two gates
being mutually exclusive in when they run:

| `refusal_cause` | Fires when | Clearing action |
|---|---|---|
| `proof_not_through_entry_point` | A linked test's own module, or a module it imports, defines `main`, but that test's own run never entered it | Rewrite the proof to invoke the detected entry point |
| `observation_unavailable` | A `main` was detected but the execution-derived observation itself could not be made, or its isolated re-run did not pass | Investigate the observation subprocess failure — fails closed, not read as a refusal |
| `no_entry_point_reaches_code` (not diagrammed here) | Phase 6 did not refuse (its verdict was still `eligible: True`), AND no linked test's module — by the sibling gate's own, independently-computed check — has a way in anywhere | Give the unit an entry point, or record a reasoned exemption |

## Cross-References

- [Build Orchestration — Component Overview](../components/build-orchestration.md) — the
  component that owns `done_proof.py` and the pre-commit gate that invokes it.
- [Fast vs Heavy Lane Phases](c2-fast-vs-heavy-lane-phases.md) — the C2 container diagram
  showing where the done-proof gate sits in the overall build pipeline.
- [AC-Driven Pipeline](c2-001-ac-driven-pipeline.md) — the broader context in which
  the done-proof verdict feeds the `mark_ac_done.py` and status-promotion flows.
- [How to understand proof-of-done enforcement — section 3](../../how-to/done-proof-enforcement.md#3-the-third-eligibility-axis-did-the-proof-go-in-through-the-real-way-in-bo-2900a-1) —
  the task-oriented explanation of this same gate, including how to fix a refusal.
- [BO-2900a-1 acceptance criterion](../../acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900a-1.yaml) —
  the AC this Phase 6 addition implements.
- [BO-2500a-3 acceptance criterion](../../acceptance-criteria/build-orchestration/BO-2500-mechanical-done-proof/BO-2500a-3.yaml) —
  the incumbent pass/fail rule (Phases 1-5) that BO-2900a-1 narrows, not restates.
