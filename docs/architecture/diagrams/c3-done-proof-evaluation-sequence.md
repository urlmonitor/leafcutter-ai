---
title: "Done-Proof Evaluation — Sequence Diagram"
description: "L3 sequence diagram of verify_done_eligible — from collecting # covers tags and resolving them against the AC YAML store, through running pytest as a subprocess and classifying outcomes, to the final per-AC eligible/blocked verdict emitted by the mechanical gate."
type: architecture
diagram_type: sequence
flight_level: L3-Component
status: active
created: 2026-07-21
last_updated: 2026-07-21
components:
  - build_orchestration
  - testing_quality
related_docs:
  - docs/architecture/components/build-orchestration.md
  - docs/how-to/prove-ac-done.md
  - docs/how-to/done-proof-enforcement.md
  - docs/architecture/diagrams/c2-fast-vs-heavy-lane-phases.md
related_code:
  - scripts/ac_store/done_proof.py
  - templates/scripts/commit_guardian/check_done_proof.py
---

# Done-Proof Evaluation — Sequence Diagram

This diagram documents the message-level interaction of `verify_done_eligible()` in
`scripts/ac_store/done_proof.py` — the authoritative eligibility oracle for the BO-2500
done-proof gate. It covers the full evaluation path from the gate invoking the oracle,
through AC-store resolution, test-tree scanning, pytest execution, outcome classification,
and finally the per-AC eligible or blocked verdict returned to the caller.

> **The gate, not the caller, emits the verdict.** `verify_done_eligible()` is the
> mechanical gate: it owns the evaluation logic and always returns a structured
> `{eligible, reason, passing_tests, failing_tests, dangling_tags}` dict. The caller
> (`check_done_proof.py` or `fast_lane.py`) decides what to do with that verdict — block
> the commit, emit a warning, or proceed.

---

```mermaid
sequenceDiagram
    autonumber
    actor Gate as Mechanical Gate<br/>(check_done_proof.py / fast_lane.py)
    participant VDE as verify_done_eligible<br/>(done_proof.py)
    participant ACS as AC YAML Store<br/>(docs/acceptance-criteria/**/*.yaml)
    participant TFS as Test File System<br/>(unit_tests/**/*.py)
    participant Pytest as pytest subprocess<br/>(python -m pytest -v)

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
            Note over VDE,Gate: ELIGIBLE — every covers-linked test produced a PASSED outcome
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

8. **Verdict emitted.** If any `failing_tests` exist, `eligible: False` is returned with
   a reason naming each non-passing nodeid and its outcome. If all linked tests passed,
   `eligible: True` is returned with an empty reason. In both cases `dangling_tags` is
   included so the gate can surface stale cross-references to the developer.

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

## Cross-References

- [Build Orchestration — Component Overview](../components/build-orchestration.md) — the
  component that owns `done_proof.py` and the pre-commit gate that invokes it.
- [Fast vs Heavy Lane Phases](c2-fast-vs-heavy-lane-phases.md) — the C2 container diagram
  showing where the done-proof gate sits in the overall build pipeline.
- [AC-Driven Pipeline](c2-001-ac-driven-pipeline.md) — the broader context in which
  the done-proof verdict feeds the `mark_ac_done.py` and status-promotion flows.
