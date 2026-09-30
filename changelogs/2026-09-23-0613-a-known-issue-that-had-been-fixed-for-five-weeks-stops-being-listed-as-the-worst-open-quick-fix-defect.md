---
title: "A known issue that had been fixed for five weeks stops being listed as the worst open quick-fix defect"
date: "2026-09-23"
time: "06:13"
type: manual
components:
  - build_orchestration
  - build_pipeline
summary: "KI-BO-010 recorded two real defects in /quick-fix's root-cause divergence gate: the comparison was a first-token substring match, and the halt told the operator to re-run with the same args, which recomputed the same verdict and halted again. Both were replaced eight days after the entry was filed. Nothing closed the entry, so for five more weeks it sat as the highest-severity open quick-fix issue in the register, with a stale line anchor and a fix direction arguing for roughly the design that had already shipped. It is now in resolved/, with the original report preserved and the replacement verified by running it rather than by reading the diff."
description: "Moves docs/known-issues/build-orchestration/open-high-ki-bo-010.md to resolved/resolved-high-ki-bo-010.md and updates the build-orchestration index (open row to resolved row, counts 49/9 to 48/10, last_updated). The fix being recorded landed in f1726aef (2026-08-26, PR #602): the first-token substring test became a stopworded content-word comparison that warns only on total disjointness (comparable && sharedWords === 0), and the halt gained a divergence_decision: 'continue' argument that is read at the branch and named in the halt message. Verified behaviourally at 9f783a26 — unit_tests/workflows/test_bp600e2_divergence_behavioral.py executes the real quick-fix.js in a Node subprocess via run_workflow_under_e2 and covers exactly the three behaviours the entry named; 3 passed under AC_ENFORCE_STRICT=1. BP-600e-2 deliberately stays work_status: todo, because its it_requirements ask for an LLM-based comparison and what shipped is lexical. No code changes."
commits:
  - 8494ee22
breaking: false
---

## Entry

### What the entry said, and what is there now

`KI-BO-010` was filed on 2026-08-18 against `/quick-fix`'s root-cause divergence gate, and
it was right about both things it said.

The comparison was this:

```js
const divergenceCheck = failureMsg.length > 0 &&
  !failureMsg.toLowerCase().includes(root_cause.toLowerCase().split(' ')[0])
```

— the **first whitespace-delimited token** of a prose diagnosis, looked for in pytest output.
A diagnosis opening `` `handoff` `` carried its backticks into the token and never matched;
one opening "The …" produced `the`, which matches essentially any pytest output, so the gate
passed unconditionally. Which way it failed was decided by the first word's punctuation.

And the halt's own remedy did not work: the message said to re-run with the same args, but
the check was a pure function of the diagnosis and the failure text with no confirmation
flag, so the re-run recomputed the same verdict and halted identically.

Both were replaced on 2026-08-26 in `f1726aef` (PR #602). The gate now reduces both texts to
their content vocabulary — stoplist, short fragments dropped, common inflections stripped —
and warns only on **total disjointness**, `comparable && sharedWords === 0`. Where there is
nothing to compare it says so in a log line rather than inventing a verdict. And
`divergence_decision` is destructured from the args, read at the branch, and named in the
halt message, so the remedy the message offers is reachable.

### Verified by running it

The evidence for this closure is not that the diff looks right.
`unit_tests/workflows/test_bp600e2_divergence_behavioral.py` executes the real
`quick-fix.js` in a Node subprocess through `run_workflow_under_e2()` and records the agent
dispatches. Its three tests are named for the three defects, because they were written as the
red baseline for them. At `9f783a26` under `AC_ENFORCE_STRICT=1`, all three pass.

That distinction is the point of the file's existence: the four tests that originally covered
this AC were source greps — `assert "divergence" in js.lower()` and similar — and every one
of them passed on the broken check unchanged.

### One thing this does not close

`BP-600e-2` stays `work_status: todo`. Its `it_requirements` ask for *"LLM-based comparison
of diagnosed root_cause text with actual test failure output"*, and what shipped is lexical.
The implementation is candid about it: one incidental shared word suppresses the warning,
*"the honest ceiling of a lexical comparison and the reason BP-600e-2's it_requirements ask
for a semantic one."*

The entry's two claims are fixed. The AC's stricter claim is not. Closing both off this
evidence would repeat the phantom-done move that reopened the AC on 2026-08-25, so the
resolution records the gap instead — including that the AC's own `notes` still quote the old
`:568-569` code as if it were current.

### Why it stayed open

The fix landed in a commit that fixed eight unrelated defects and named none of them by KI
id. The register's documented close step — delete the section, reference the id in the commit
message — is author discipline with no gate behind it. The entry then rode through the
one-file-per-issue split (#817) verbatim, because that migration moved files rather than
re-reading them.

The cost is directional. A register that is wrong about something being **outstanding** sends
the next person to rebuild working code; the 48 entries still open in this component are
competing for that attention. This is the second entry in a fortnight to be closed for
outliving its own truth, after the doc-length retraction in #824.
