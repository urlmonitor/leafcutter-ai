---
title: "KI-ACS-002 — `--verify` passes `files_touched` on a path count, not on correctness"
description: "KI-ACS-002 — `--verify` passes `files_touched` on a path count, not on correctness"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
---

# KI-ACS-002 — `--verify` passes `files_touched` on a path count, not on correctness

> One known issue, split out of `docs/known-issues/ac-store.md` on
> 2026-09-14. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 6
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-26
- **Where:** `scripts/ac_store/generate_ticket_from_ac.py` — the `--verify` readiness report

**2026-08-26 — four more, consecutively, on one AC chain.** Every ticket generated for the
`BP-1100g` chain needed its surface corrected by hand before it could be dispatched, and in each
case the generated `files_touched` was non-empty, so the readiness check passed:

| ticket | generated surface | what was missing |
|---|---|---|
| `BP-1100g-1` | 1 path | named the **deployed** `.claude/agents/test-writer.md`; the source is `templates/` |
| `BP-1100g-3` | 1 path | the entire **prompt** surface — `llm-expert` sat in the agents map with no file to edit — plus both test files |
| `BP-1100g-3-i` | 1 path | named `done_proof.py`, the one file that AC's `n_location_rule: 0` **forbids** touching, and gave the tests nowhere to land |
| `BP-1100g-4` | 1 path | the new hook module, the deploy-manifest entry, and the test file — see **KI-ACS-014**, the path it *did* name is untracked |

The `BP-1100g-3-i` case is the sharpest: `reference_file_path` is the file the tests **observe**,
and the generator copies it into `files_touched` as the file the ticket **edits**. On a negative
control those are opposites, so the readiness report passed a surface that instructed the
implementer to do the one thing the AC prohibits.

**Symptom.** The readiness report's surface check asserts only that *some* paths were
derived. Its output reads `[PASS] files_touched has N path(s) from doc_links` — N > 0 is
the whole test. An AC whose derived surface omits the file the work changes, and includes
a file the AC's own criteria forbid touching, passes it and the report concludes `READY`.
The provenance label is misleading too: paths that came from the prose fallback are
reported as coming from `doc_links`.

**Evidence.** `python scripts/ac_store/generate_ticket_from_ac.py --ac BO-2400g-2 --verify`
on `main` at `439b9076f` exits 0 and prints:

```
=== Ticket readiness report for BO-2400g-2: READY ===
  [PASS] files_touched has 4 path(s) from doc_links
```

The four paths are `scripts/build.py`, `templates/agents/change-scope-reviewer.md`,
`templates/agents/pr-reviewer.md` and `unit_tests/_workflow_engine_harness.py`. The file
that AC exists to change — `templates/workflows-js/fast-lane-ship.js` — is absent, because
its `doc_link` is tagged `describes`. `change-scope-reviewer.md` is a file that AC's
criteria explicitly forbid touching, and `scripts/build.py` came from the prose scan, not
from a `doc_link` at all.

This is the check people reach for when they want reassurance that a generated ticket is
sane, so a count dressed as a verdict is worse here than elsewhere.

**Fix direction.** Compare the derived surface against something independent — at minimum
warn when an AC has edit-surface `doc_links` for files that did not make the list, or when
a path arrived only via the prose fallback. Report provenance per path honestly. A check
that cannot assess correctness should report `INFO`, not `PASS`. Related: the prose
fallback itself is `BP-1100a-4`, and the authoring-side rule is documented in
`docs/how-to/ac-traceability-store.md`.

**Second occurrence, 2026-08-25 — the prose fallback can name a BUILD OUTPUT as the
edit surface, and the sentence it scrapes may be one warning against exactly that.**
Found on the first ticket generated after the test-contract fix, `BP-1100g-1`. Report:

```
[PASS] files_touched has 3 path(s) from doc_links
```

The three were `docs/testing/test-angles.md`, `templates/agents/test-writer.md`, and
`.claude/agents/test-writer.md`. The third is not one of that AC's five `doc_links`
— it came from the prose fallback, scraped out of the it_requirement sentence *"The
taught set must be present in the DEPLOYED copy (`.claude/agents/test-writer.md`), not
only in `templates/`"*. That sentence exists to say the deployed copy is the
**assertion target**; the derivation read it as an **edit target**. And
`.claude/agents` is a symlink to `.leafcutter/agents`, so it is a build output that
`build.py` regenerates from `templates/`.

This occurrence is worth recording separately from the first because the consequence is
not a merely-inaccurate list — it is a live phantom-done trap, on the AC whose whole
purpose is preventing phantom-done:

1. `BP-1100g-1`'s fourth `test_spec` entry is a **reachability** test that runs
   `build.py` and then reads the DEPLOYED `.claude/agents/test-writer.md`, deliberately,
   because the agent runtime loads the built copy.
2. An implementer following `files_touched` edits the deployed copy. That test passes
   immediately.
3. `templates/` is untouched, so the next `build.py` overwrites the deployed copy and
   the work disappears.
4. The ticket has already closed green.

Also, in the same report, the directory where all four tests land
(`unit_tests/prompt_assembly/`) was **absent** from `files_touched`, which would have
made the actual deliverable read as unexpected scope to `change-scope-reviewer`. So the
derived surface was wrong in both directions at once, and the count-based check called
it `PASS`.

Worked around on the ticket by hand (correct `files_touched`, plus an `out_of_scope`
naming `.claude/agents/` and `.leafcutter/` so a diff there is a hard violation), not
fixed at source.

**Sharpened fix direction.** Beyond reporting provenance honestly: the derivation should
never emit a path under a known build-output root as an edit surface. Those roots are
already knowable — `.leafcutter/` and everything symlinked into it from `.claude/` — so
this is a filter, not a judgement. A path that resolves inside a build output is either
an assertion target or a mistake, and in both cases it does not belong in
`files_touched`.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M8.

---
