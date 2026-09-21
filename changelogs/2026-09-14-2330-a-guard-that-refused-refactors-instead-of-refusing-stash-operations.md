---
title: "A guard that refused refactors instead of refusing stash operations"
date: "2026-09-14"
time: "23:30"
type: manual
components:
  - build_pipeline
summary: "quick-fix.js was 1093 content lines against a 1000-line limit, so the workflow body blocked its own commit. Reducing it stalled two lines under the limit because its own guard test pinned the source's physical layout: the test sliced the raw JS between two literal anchors, so moving a literal into a function argument broke a test that nothing had actually broken. The slice is gone and the guard now scans the whole file, which is strictly stronger and cannot be defeated by moving code; with the anchor removed the blocked extractions applied and the file reached 944."
description: "templates/workflows-js/quick-fix.js 1093 -> 944 content lines via five extractions that remove duplication rather than relocate bulk: schema(properties, required) for the status/message envelope repeated across eleven *_SCHEMA consts; blocked(phase, message, extra) for every status:'blocked' construction; blockedOnFailure() for nine near-identical null-or-blocked guards; strictFlagMissingBlock/unrunnableTestBlock for the Red and Green phases' near-identical strict-flag and outcome:'error' checks; and mutationProofBlock, the extraction the old test anchor had rejected. unit_tests/test_quickfix_mutation_proof_stash_free.py drops _slice_between for the JS half and scans the whole file, still matching stash OPERATIONS rather than the bare string so the file's own prohibition prose does not trip it, and still asserting git show HEAD: so deleting the revert cannot pass vacuously."
commits:
  - 912338b02
breaking: false
---

## Entry

### The gap, and where it actually was

`check-file-size` caps `.js` at 1000 content lines. `quick-fix.js` was at 1093, so the
workflow body could not be committed.

The first reduction pass stopped at **998** — two lines of margin, which is no margin at
all: the next edit to the file would be refused. The reason it stopped there is the part
worth recording, because it was not a property of the file.

`unit_tests/test_quickfix_mutation_proof_stash_free.py` — the guard added earlier the
same day to stop `/quick-fix` ever reaching for `git stash` again — checked the workflow
by regex-slicing the raw source between `const mutationResult = await agent(` and the
literal `halt_reason: 'mutation_proof_failed'`. Moving that literal into a function
argument, which is an ordinary extraction that changes nothing observable, made the
anchor unfindable and turned the test red.

So the guard was refusing **refactors**, not refusing **stash operations**. It had
quietly become a pin on the source's physical layout.

### Fixing the guard rather than working around it

The slice is deleted. The guard now scans the entire file for a stash operation.

That is strictly stronger than what it replaced: it catches `git stash` anywhere in the
workflow rather than only inside the mutation-proof block, and no rearrangement of code
can move an operation out of its view. Two properties are deliberately preserved:

- It matches stash **operations** (`push`, `pop`, `list`, …), not the bare string. The
  file legitimately contains prose forbidding the command, and a bare match would fire on
  the prohibition itself — a trap hit while first writing this test.
- The positive `git show HEAD:` assertion stays, so deleting the revert step entirely
  fails rather than passing vacuously.

`_slice_between` survives for the two `SKILL.md` tests, where scoping to fenced command
blocks reflects real prose structure rather than an accident of layout.

### What the removed anchor unblocked

With the pin gone, five extractions applied, each removing duplication rather than
relocating bulk:

- `schema(properties, required)` — eleven `*_SCHEMA` consts had spelled out an identical
  `status`/`message` envelope; each now declares only its own fields.
- `blocked(phase, message, extra)` — one envelope for every `status: 'blocked'` return.
- `blockedOnFailure(...)` — nine near-identical `if (!x || x.status === 'blocked')` guards.
- `strictFlagMissingBlock` / `unrunnableTestBlock` — the Red and Green phases each carried
  a near-identical strict-flag check and `outcome: 'error'` check differing by one
  sentence, now a parameter.
- `mutationProofBlock` — the one the old anchor had rejected.

Final: **944 of 1000**, 56 lines of headroom instead of 2.

### Proving the rewritten guard can still fail

Rewriting a guard's matching logic is exactly when it silently stops guarding, and a
green run proves nothing about that. So the guard was shown to fail: a `git stash push`
was injected into the mutation-proof prompt, the test went **RED**, and restoring from a
`/tmp` backup returned it **GREEN** with a byte-identical `diff -q`.

### Behaviour is unchanged, and that was checked

- `grep -o "phase('...')"` on HEAD's copy versus the refactor diffs **empty** — the phase
  sequence is byte-identical.
- The `meta` block diffs empty and remains a pure literal, as its own contract gate
  requires.
- No phase added, removed, reordered, or given new halt conditions.
- `templates/skills/quick-fix/SKILL.md` is untouched. Its header says a behavioural change
  must land in both surfaces; wanting to edit it would have meant this was not a refactor.

### Verification

- `node --check`: exit 0.
- `test_quick_fix_workflow.py` + the stash guard under `AC_ENFORCE_STRICT=1`: 96 passed.
- Full blast radius in one process — `unit_tests/workflows/`,
  `test_workflow_variant_transform`, `test_workflow_dual_engine`, `test_build_workflows`,
  `test_build_workflow_phase`, plus the guard: 686 passed, 1 pre-existing xfailed,
  25 subtests.
- Sizes: `quick-fix.js` 944/1000, the guard 188/400.

Before each extraction, `unit_tests/` was swept for `_slice_between`, literal
`halt_reason:` anchors, `js.find(` and `phase: '` patterns, to confirm no other
static source-inspection test pinned the sites being moved. That sweep is the reason only
one such coupling existed to fix — and the reason to expect others if this pattern spreads.
