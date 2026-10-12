---
title: "Done-Proof Reachability Gates — Sequence Diagram"
description: "L3 sequence diagram continuing c3-done-proof-evaluation-sequence.md from its eligible: True pass/fail output. Covers the mechanical entry-point reachability gate (BO-2900a-1) that refuses a proof reaching the code by direct import when the unit has a real way in, and the sibling no-entry-point-anywhere gate (BO-2900a-3) that refuses a unit no way of running the product can reach at all, to the final per-AC eligible/blocked verdict."
type: architecture
diagram_type: sequence
flight_level: L3-Component
status: active
created: 2026-09-27
last_updated: 2026-09-27
components:
  - build_orchestration
  - testing_quality
  - ac_store
related_docs:
  - docs/architecture/diagrams/c3-done-proof-evaluation-sequence.md
  - docs/architecture/components/build-orchestration.md
  - docs/architecture/components/phantom-done-prevention.md
  - docs/how-to/done-proof-enforcement.md
  - docs/how-to/done-proof-reachability-gates.md
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900a-1.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900a-3.yaml
  - docs/acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900d.yaml
related_code:
  - scripts/ac_store/done_proof.py
  - scripts/ac_store/_done_proof_entry_point_gate.py
  - scripts/ac_store/_done_proof_automation_gate.py
  - scripts/commit_guardian/_reachability_inventory.py
  - scripts/commit_guardian/_reachability_invocation_collector.py
---

# Done-Proof Reachability Gates — Sequence Diagram

> **Parent document:** [c3-done-proof-evaluation-sequence.md](c3-done-proof-evaluation-sequence.md)

This diagram continues
[c3-done-proof-evaluation-sequence.md](c3-done-proof-evaluation-sequence.md) from its
own `eligible: True` output (Phases 1-5, the incumbent `BO-2500a-3` pass/fail rule
already satisfied). It covers `verify_done_eligible()`'s (`scripts/ac_store/done_proof.py`)
two mechanical reachability gates: the entry-point reachability gate (Phase 6,
`BO-2900a-1`) and the sibling no-entry-point-anywhere gate (Phase 6.5, `BO-2900a-3`),
through to the final per-AC eligible or blocked verdict returned to the caller.

> **Scope of this diagram (BO-2900a-1 and BO-2900a-3).** The mechanical
> entry-point reachability gate (Phase 6, Section 3 below) is evaluated only
> after the incumbent pass/fail gate diagrammed in the parent document already
> returned `eligible: True`. It never changes the "no linked test" or "linked
> test failed" verdicts documented there. A separate, disjoint rule — the
> no-entry-point-anywhere gate (Phase 6.5, Section 4 below;
> `_apply_reachability_gate`, `refusal_cause: "no_entry_point_reaches_code"`)
> — runs immediately after Phase 6, on Phase 6's own output, for the case
> where NO linked test's module exposes a way in at all. Both gates are
> diagrammed in full below (see the scope-fence note in step 9, and Section 4
> for Phase 6.5's own mechanism).

---

```mermaid
sequenceDiagram
    autonumber
    actor Gate as Mechanical Gate<br/>(check_done_proof.py / fast_lane.py)
    participant VDE as verify_done_eligible<br/>(done_proof.py)
    participant Runner as Reachability observer<br/>(fresh subprocess, sys.setprofile)
    participant Reg as Exemption &amp; invocation seam<br/>(config/reachability_exemptions.yaml,<br/>_reachability_inventory.py<br/>re-exports collected_invocations)

    Note over Gate,Reg: Continued from c3-done-proof-evaluation-sequence.md — every<br/>covers-linked test already PASSED there (Phases 1-5); this diagram<br/>begins from that eligible: True verdict.

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

    Note over VDE: Phase 6.5 — No-entry-point-anywhere gate (BO-2900a-3, sibling, always runs next)<br/>_apply_reachability_gate() GUARDS on verdict["eligible"] first: an already-refused<br/>Phase-6 verdict returns unchanged — it is never overwritten with this gate's own,<br/>independently-computed "no_entry_point_reaches_code" verdict for the same unit.
    alt Phase 6 already refused (verdict["eligible"] is False)
        Note over VDE,Gate: Phase 6's verdict passes through completely unchanged.
    else Phase 6 verdict still eligible — evaluate the sibling gate
        loop For each linked Python test's directly-imported modules
            VDE->>VDE: _find_no_entry_point_unit(linked_tests, project_root, test_root)<br/>Per candidate module: (1) _has_entry_point_of_its_own — AST/text check for an<br/>`if __name__ == "__main__":` guard in the candidate's OWN source; (2)<br/>_is_imported_elsewhere — walks every other *.py file (excluding test_root) and<br/>checks module_name against that file's AST-derived _local_import_module_names(),<br/>the SAME seam Phase 6 uses to resolve cross-file candidates — never a regex<br/>text scan (BO-2900a-3 fix: a regex previously matched a docstring MENTION of<br/>the import spelling as if it were a real ast.Import/ast.ImportFrom node).
        end
        alt Every candidate has an entry point of its own, or is genuinely imported elsewhere
            Note over VDE,Gate: Verdict from Phase 6 returned unchanged — no unreachable unit found.
        else A unit exists with no entry point of its own AND no genuine importer<br/>(conditions 1 and 2 both hold against the unit — condition 3 checked next)
            VDE->>Reg: load_exemptions(config/reachability_exemptions.yaml)<br/>is_exempt(unit, exemptions) — exact string-equality match only,<br/>non-blank `reason` required to count as "in force"
            Reg-->>VDE: exemptions list / exempt: bool
            VDE->>Reg: collected_invocations(automation-script candidates)<br/>_done_proof_automation_gate.unit_is_invoked_by_automation —<br/>project-scoped *.py scan (excludes test_root and excluded dirs),<br/>matches an Invocation.surface to unit's resolved path by EXACT<br/>string equality, never a glob/prefix/basename match
            Reg-->>VDE: invocations list
            alt condition 3 fails — unit IS invoked by automation as a program
                Note over VDE,Gate: Verdict from Phase 6 returned unchanged — automation already<br/>runs this unit, so "no automation runs it as a program" does not<br/>hold; fires regardless of whether an exemption is ALSO recorded.
            else condition 3 holds — no automation invokes the unit
                alt unit is exempt
                    Note over VDE,Gate: Verdict from Phase 6 returned with exemption attached —<br/>never silently absorbed.
                    VDE-->>Gate: {..., exemption: {item: unit, reason: "<recorded reason>"}}
                else unit is not exempt
                    Note over VDE,Gate: BLOCKED — no way of running the product reaches this unit,<br/>however many tests pass over it. Adding another passing test cannot<br/>change this verdict — no term above reads test count, presence,<br/>outcome, or coverage (the anti-ritual clause).
                    VDE-->>Gate: {eligible: False,<br/>reason: "no way of running the product reaches &lt;unit&gt; (refusal_cause:<br/>no_entry_point_reaches_code) for &lt;ac_id&gt;",<br/>refusal_cause: "no_entry_point_reaches_code",<br/>unit: "&lt;repo-relative path&gt;",<br/>clearing_actions: ["give the unit an entry point", "record an exemption"],<br/>passing_tests: [...], failing_tests: [], dangling_tags: [...]}
                end
            end
        end
    end

    Note over VDE,Gate: ELIGIBLE — every covers-linked test PASSED, every one whose resolved<br/>module exposes a way in had its own run enter it, and the no-entry-point-anywhere<br/>gate found no unit with no way in at all (or granted a recorded exemption)
    VDE-->>Gate: {eligible: True,<br/>reason: "",<br/>passing_tests: [...],<br/>failing_tests: [],<br/>dangling_tags: [...]}
```

---

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

## 4. The no-entry-point-anywhere gate (BO-2900a-3)

Phase 6.5 runs unconditionally, immediately after Phase 6, on Phase 6's own
output. When Phase 6 already refused, `_apply_reachability_gate` returns that
verdict unchanged (see the composition note above) — the steps below describe
only the branch where Phase 6's verdict is still `eligible: True`.

12. **Candidate resolution, per linked Python test.** `_find_no_entry_point_unit`
    inspects the bare module names each linked test imports directly and
    resolves each to a candidate file via `_resolve_candidate_unit` — the
    same resolver Phase 6 uses. For each resolved candidate, two AST/text
    checks decide whether it "has a way in":
    - `_has_entry_point_of_its_own(candidate)` — does the candidate's own
      source contain an `if __name__ == "__main__":` guard?
    - `_is_imported_elsewhere(module_name, candidate, project_root, test_root)`
      — does any OTHER project file outside the test tree genuinely import
      the candidate? This is resolved via `_local_import_module_names`
      (AST-parsed import graph) against every other `*.py` file under the
      project root — **never** a regex scan of file text. Before this AC,
      `_is_imported_elsewhere` used exactly that forbidden regex shape
      (`re.compile(rf"import\s+{module_name}\b|from\s+{module_name}\s+
      import\b")`), and a docstring or comment that merely *mentioned* an
      import spelling — with no real `ast.Import`/`ast.ImportFrom` node
      behind it — was indistinguishable from a genuine import. The fix
      routes this check through the same `_local_import_module_names` seam
      Phase 6 already used for its own cross-file resolution, so both gates
      now agree on what "imports" means.

13. **A candidate with neither property is the refused unit.** The first such
    candidate found (scanning linked tests, then each test's imports, in
    order) is returned as the unreachable `unit`, expressed as a path
    relative to the inferred project root (the common ancestor of `ac_root`
    and `test_root`) when possible. Conditions 1 and 2 from the AC's Gherkin
    now both hold against this candidate; condition 3 — "no automation runs
    that unit as a program" — is checked next, in step 14.

14. **Condition 3 and the exemption check — the two release valves, condition
    3 checked first.** Before building a refusal, `_apply_reachability_gate`
    imports the shared seam `scripts/commit_guardian/_reachability_inventory.py`
    and calls `load_exemptions(project_root / "config" / "reachability_exemptions.yaml")`
    then `is_exempt(unit, exemptions)` — matching is exact string equality
    against `item`, and only entries with a non-blank `reason` count as "in
    force" (`exemptions_in_force`). If the seam import itself fails (e.g. a
    packaging layout that has not deployed `_reachability_inventory.py`), a
    warning is printed to stderr and the unit is treated as unexempted
    (fail-closed) rather than silently passed. It then calls
    `_done_proof_automation_gate.unit_is_invoked_by_automation(unit,
    project_root, test_root, collected_invocations)` — the SAME
    already-imported `collected_invocations` function this seam import also
    provides, so no second import path into `commit_guardian` is opened.
    That function scans a project-scoped set of `.py` files (every file under
    the project root except those under an excluded scan directory or under
    `test_root` — the same convention `_is_imported_elsewhere` uses) through
    `collected_invocations(scripts)`, and matches an `Invocation.surface`
    against `unit`'s own resolved path by **exact string equality only**,
    never a glob, prefix, or basename match. If the seam import failed above,
    `collected_invocations` is `None` and the automation check fails closed
    to `False` (no automation found) rather than granting a pass.

15. **Verdict — automation checked before exemption.** A unit invoked by
    real automation is spared regardless of whether an exemption is *also*
    recorded for it:
    - Unit **is** invoked by automation as a program (condition 3 fails to
      hold) → Phase 6's `eligible: True` verdict is returned unchanged,
      exactly like the "no unreachable candidate" outcome below.
    - Unit is **not** invoked by automation, and **is** exempt → the verdict
      is Phase 6's verdict, unmodified, plus an `exemption: {item, reason}`
      field naming the recorded reason. The exemption is announced on the
      verdict, never silently absorbed.
    - Unit is **not** invoked by automation, and is **not** exempt →
      `eligible: False`, `refusal_cause: "no_entry_point_reaches_code"`,
      `reason` naming the unit in plain language, `unit` carrying the
      resolved path, and `clearing_actions:
      ["give the unit an entry point", "record an exemption"]` — a literal,
      machine-readable list built once by
      `_done_proof_automation_gate.build_no_entry_point_refusal` from its
      module-level `CLEARING_ACTIONS` constant, so `check_done_proof.py` and
      BO-2900e-1's future refusal message read the two clearing actions
      directly off the verdict rather than re-deriving their own wording. No
      linked test's pass/fail counts, tag count, or presence appear anywhere
      in this predicate — the **anti-ritual clause**: adding a further
      passing test over the same unreachable unit cannot change this
      verdict, because the predicate never reads test-derived facts at all.
    - No unreachable candidate found (step 13 never fired) → Phase 6's
      `eligible: True` verdict is returned unchanged, and evaluation reaches
      the final `ELIGIBLE` return shown at the bottom of the diagram above.

### The regression this gate is calibrated against

This is the gate that catches the PR-411 regression shape: a unit with no
registered capability, no caller, and passing tests anyway. Phase 6
(BO-2900a-1) passes vacuously on such a unit — it has no `main` to check
reachability into in the first place — so it was never widened to cover this
case; Phase 6.5 is the dedicated, disjoint check for it.

## Key invariant: the scope fence between the two reachability refusal causes

`refusal_cause: "proof_not_through_entry_point"` (Phase 6, Section 3 above) and
`refusal_cause: "no_entry_point_reaches_code"` (Phase 6.5, Section 4 above) are
deliberately two disjoint values rather than one merged "unreachable" verdict —
each names a different fact and clears a different way. As the composition note
above spells out, both gates always run, in this fixed order, on every eligible
verdict; disjointness is enforced by the Phase 6.5 gate's own eligibility guard,
not by the two gates being mutually exclusive in when they run:

| `refusal_cause` | Fires when | Clearing action |
|---|---|---|
| `proof_not_through_entry_point` | A linked test's own module, or a module it imports, defines `main`, but that test's own run never entered it | Rewrite the proof to invoke the detected entry point |
| `observation_unavailable` | A `main` was detected but the execution-derived observation itself could not be made, or its isolated re-run did not pass | Investigate the observation subprocess failure — fails closed, not read as a refusal |
| `no_entry_point_reaches_code` | Phase 6 did not refuse (its verdict was still `eligible: True`), AND no linked test's imported module — by Phase 6.5's own, independently-computed AST-import-graph check — has a way in (own `main` guard or a genuine outside importer), AND no automation script runs the unit as a program (`collected_invocations()`-derived, checked before the exemption below), AND the unit has no recorded exemption | Named on the verdict's own `clearing_actions` field: give the unit an entry point (including being run by real automation), or record a reasoned exemption in `config/reachability_exemptions.yaml` (BO-2900d) |

## Cross-References

- [Done-Proof Evaluation — Sequence Diagram](c3-done-proof-evaluation-sequence.md) —
  the parent diagram (Phases 1-5, the incumbent pass/fail rule) this diagram continues
  from.
- [Build Orchestration — Component Overview](../components/build-orchestration.md) — the
  component that owns `done_proof.py` and the pre-commit gate that invokes it.
- [How to understand proof-of-done enforcement](../../how-to/done-proof-enforcement.md) —
  the task-oriented explanation of the two-layer (pre-commit / CI) enforcement strategy.
- [How to understand the done-proof reachability axes](../../how-to/done-proof-reachability-gates.md) —
  the task-oriented explanation of the Phase 6 and Phase 6.5 gates diagrammed above.
- [BO-2900a-1 acceptance criterion](../../acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900a-1.yaml) —
  the AC this Phase 6 addition implements.
- [BO-2900a-3 acceptance criterion](../../acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900a-3.yaml) —
  the AC this Phase 6.5 addition implements.
- [BO-2900d acceptance criterion](../../acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900d.yaml) —
  the exemption registry Phase 6.5 hands off to rather than deciding the helper-module
  case itself.
- [BO-2900b-3 acceptance criterion](../../acceptance-criteria/build-orchestration/BO-2900-runtime-reachability-guard/BO-2900b-3.yaml) —
  the `collected_invocations(script_paths)` seam Phase 6.5's condition-3 automation
  check (step 14 above) delegates to, via `scripts/ac_store/_done_proof_automation_gate.py`.
- [BO-2500a-3 acceptance criterion](../../acceptance-criteria/build-orchestration/BO-2500-mechanical-done-proof/BO-2500a-3.yaml) —
  the incumbent pass/fail rule (Phases 1-5, parent diagram) that BO-2900a-1 and
  BO-2900a-3 both narrow, not restate.
- [Phantom-Done Prevention — Component Overview](../components/phantom-done-prevention.md) —
  the L2 container page grouping this diagram alongside the related BP-1100f gates.
