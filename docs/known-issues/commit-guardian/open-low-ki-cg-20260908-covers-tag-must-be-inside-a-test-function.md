---
title: "KI-CG-20260908-covers-tag-must-be-inside-a-test-function — the pre-commit done-proof gate accepts a Python `# covers:` tag anywhere in the file while CI's oracle counts it only inside a test function, so a tag can pass locally and fail the required check with two different accounts of the same file"
description: "medium — does not corrupt state and cannot produce a false *green*; it costs a full push/CI round-trip per occurrence and, until diagnosed, reads as \"CI disagrees with my passing local hook\" rather than as a placement rule. Every AC newly l"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260908-covers-tag-must-be-inside-a-test-function — the pre-commit done-proof gate accepts a Python `# covers:` tag anywhere in the file while CI's oracle counts it only inside a test function, so a tag can pass locally and fail the required check with two different accounts of the same file

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium — does not corrupt state and cannot produce a false *green*; it costs a full push/CI round-trip per occurrence and, until diagnosed, reads as "CI disagrees with my passing local hook" rather than as a placement rule. Every AC newly linked to an existing Python test can hit it.
- **Status:** open — no AC. Worked around per-occurrence by moving the tag inside the test functions.
- **Occurrences:** 1
- **First seen:** 2026-09-08 (`GE-127b-2`, PR #750) · **Last seen:** 2026-09-08
- **Where:** `scripts/ac_store/done_proof.py:873-879` — `_scan_single_test_file` builds `lineno_to_function` and then `function = lineno_to_function.get(lineno)` / `if function is None: continue`, so `COVERS_TAG_RE` is never even applied to a line outside a function body. Contrast `_scan_single_ts_file` (`:958-968`), which applies the same regex to **every** line of a `.ts`/`.tsx` file with no enclosing-function requirement — so the rule this entry describes is Python-only, and the two scanners in the same module disagree with each other as well.

**Symptom.** `GE-127b-2` was linked to an existing test by adding `# covers: GE-127b-2` immediately below that file's module docstring — the natural place, next to the `MODULE:`/`COVERS:` header the file already carried. The pre-commit gate passed:

```text
Check Done Proof (BO-2500b — covers-tag presence gate)...................Passed
```

The commit was pushed and the required CI check failed:

```text
[check-done-proof] GE-127b-2: no linked test found for GE-127b-2
```

Same tag, same file, same AC, two verdicts. Moving the tag inside three test functions made both pass with no other change.

**Mechanism.** The two gates are different code answering different questions. The pre-commit hook asks whether the tag text is *present*. CI's oracle asks which *tests* to run as proof, so it needs a nodeid — and it gets one by mapping each tag's line number to its enclosing function, discarding any line that has none. That is a defensible design: a module-level tag names no test to run. The defect is not the requirement, it is that the requirement is **enforced silently by one gate and not stated by the other**. Nothing in the pre-commit output, in the hook's name ("covers-tag presence gate"), or in the CI failure text ("no linked test found") says *the tag exists but is in the wrong place*. The CI message in particular actively misleads: the linked test does exist and is named in the AC's own `covered_by`.

**Why this is medium and not high.** It fails closed. A misplaced tag makes an AC look *unproven*, never proven — so it cannot let phantom-done through, which is the failure mode this whole family exists to prevent. It is the local gate being too permissive relative to CI, not CI being too permissive. The cost is a wasted round-trip and a confusing diagnosis, not a wrong belief about the codebase.

**Fix direction.** Two independent parts, and the second matters more than the first.

1. Make the messages name the real cause. When `_collect_linked_tests` finds no tags for an AC, the oracle already has `all_tags`; it does not currently look for tags it *discarded*. Have `_scan_single_test_file` retain out-of-function tags as a distinct kind and report "found `# covers: <id>` at `<file>:<line>` but it is not inside a test function, so it names no test to run" instead of "no linked test found". That converts a five-step diagnosis into a one-line read.
2. Make the pre-commit gate ask the same question as CI, or say that it does not. A local gate whose pass does not imply the required check's pass is worth less than its name suggests — this is the same shape as the composite done-proof / `ac-fulfillment-gate` disagreement quick-fixed on 2026-09-08: two surfaces judging one fact by different rules, with only one of them required.

Also worth settling while in the code: the Python and TypeScript scanners genuinely differ here, and it is not clear the difference is deliberate. If a module-level tag in a `.ts` file counts, either it should count in Python too or the TS scanner is over-accepting.

**A second, unrelated thing the same investigation surfaced, recorded so it is not lost.** The descriptors in that test file carry `# covers: KI-CG-20260908-file-size-ratchet-refuses-merge-commits` — a KI id, not an AC id, and one no register contains (see the entry above). The oracle's `_collect_dangling_tags` exists precisely to report tags pointing at nonexistent ACs, yet the build is green with three of them present. Either dangling tags are collected and not acted on, or KI-shaped ids are silently tolerated. Not investigated here; flagged as the next thing to pull on.

**Diagnostic note — the check exits 0 when it checks nothing.** Run from the wrong working directory, `check_done_proof.py --mode ci-changed --base origin/main` resolves an empty changed-set and prints only `[check-done-proof] exemptions in force: 0`, exit 0 — byte-identical to a run that evaluated the AC and passed. During this investigation the first local reproduction "passed" for exactly that reason. Use `env --chdir=<worktree> python scripts/...` and treat a silent pass as unproven until the run has named something. This is `docs/reference/false-green-mechanisms.md`'s "a check that examined nothing must not look like a check that found nothing" in the same file this entry is about.

**Related.**
- `KI-CG-20260908-ratchet-reads-pre-merge-head` (above) — same PR, same day; that one is about which ref the ratchet reads, this one about where a tag may sit. They share only the commit that surfaced both.
- `docs/reference/false-green-mechanisms.md` — the diagnostic note above is an instance of the "checked nothing" mechanism catalogued there.

**Pattern:** two gates over one fact, where the cheap local one is more permissive than the required remote one, and neither states the rule that separates them.

---
