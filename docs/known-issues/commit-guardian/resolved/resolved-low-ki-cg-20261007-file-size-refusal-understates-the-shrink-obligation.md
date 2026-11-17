---
title: "KI-CG-20261007-file-size-refusal-understates-the-shrink-obligation — the grown-file refusal tells the author that removing as many lines as they add is enough, while the gate it belongs to requires twice that"
description: "medium — the verdict is correct and the Required length figure printed one line above it is correct; what is wrong is the prose advice attached to them, which describes a one-for-one rule where the gate enforces two-for-one."
type: reference
category: reference
status: active
created: '2026-10-07'
last_updated: '2026-10-07'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20261007-file-size-refusal-understates-the-shrink-obligation — the grown-file refusal tells the author that removing as many lines as they add is enough, while the gate it belongs to requires twice that

> One known issue. Index: [commit-guardian.md](../../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium — no wrong verdict and no wrong number. The refusal correctly refuses, and the `Required length:` figure it prints is correct. What fails is the one sentence telling the author what to do about it, and it fails in the direction that costs the most: it understates the obligation, so an author who follows it exactly is refused again.
- **Status:** RESOLVED 2026-10-07 — the two misleading sentences are replaced with wording that states the two-for-one obligation and defers to the already-printed `Required length:` figure for the cap. Prose only: `max(limit, previous_length - added)` is byte-for-byte unchanged in both `_print_grown_file` and `_classify_file`, and every printed figure is unchanged. PR #1038.
- **Covered by:** `GE-127f-4` ("The refusal states the two-for-one obligation it actually enforces, not a one-for-one one the author can satisfy and still be refused"), an L2 under `GE-127f`, with `unit_tests/commit_guardian/test_ge_127f_4.py`. All three arms drive a real `git commit` through the real installed hook and assert on the captured refusal text. Proven by mutation: red with the fix reverted, green with it applied.
- **Does NOT close `GE-127f`.** That L1 still has `GE-127f-3` outstanding (the outcome stating how much must leave the file, and whether the author or a restructuring specialist removes it). One sentence corrected is not the economic rule delivered; `GE-127f` stays `work_status: todo`.
- **Occurrences:** structural — true of every grown-file refusal the gate has emitted since `GE-127f-1` landed on 2026-09-30. Observed cost on first encounter: three commit cycles.
- **First seen:** 2026-10-07 · **Last seen:** 2026-10-07
- **Where:** `templates/scripts/commit_guardian/check_file_size.py`, `_print_grown_file` — the three-line closing advice block, immediately after `_print_file_description`

**Symptom.** A real captured refusal, for a 500-line file with a 400-line limit changed by +10/−10 so it stands at 500:

```text
❌ FILE GREW WHILE ALREADY OVER ITS LIMIT:
   oversized.py
   Previous length: 500 lines
   New length: 500 lines
   Limit: 400 lines
   This change added 10 measured line(s).
   Required length: 490 lines or below (...)
   ...
   An already-oversized file may still be worked on, but a change
   that puts more measured lines into it than it takes out is
   refused. Shrink it, or add no more than you remove, to commit this edit.
```

The author removed exactly as many lines as they added — precisely what the last sentence asks for — and was refused.

**Mechanism.** The enforced rule is `lines > max(limit, previous - added)`, where `added` is the GROSS measured lines the change put into the file (`GE-127f-2`), not the amount the file grew. Below the cap, "end at or below `previous - A`" means taking out `2A`: one `A` to undo what you added, a second `A` to pay down the overage. The prose describes the refusal threshold as `A > R` and the remedy as `R >= A`. Both are the same error, off by a factor of two.

Two sentences carried it, not one. The middle sentence ("a change that puts more measured lines into it than it takes out is refused") is the same claim stated as a threshold; correcting only the final sentence would have left the contradiction in place one line higher.

**Why this one is worse than a plainly wrong message.** The block contradicts itself rather than simply misinforming. `Required length: 490` is correct and sits two lines above advice that, if followed, lands at 500. An author who trusts the prose is refused; an author who trusts the number succeeds but has no idea why the sentence disagreed. There is nothing in the block that lets them tell which half to believe, so the natural read is that they mis-measured — which is why the cost was three cycles rather than one.

**The trap for whoever fixes it.** Reading `check_file_size.py` alone, the opposite conclusion is easy and wrong: `required = previous - added` looks like it could be an off-by-one-factor slip, and "add no more than you remove" looks like the intended rule. It is settled the other way by two independent records. `GE-127f`'s criteria states the obligation in plain words — "it gets smaller by about twice what the change adds to it" — and `GE-127f-2`'s Implementation Notes name net growth (`lines > previous`) as "the single most likely wrong implementation". The arithmetic is intended; the sentence was not.

Because that wrong fix is the likely one, two of the three covering tests are deliberately **green on arrival** and exist only as a scope fence: one asserts +10/−20 is accepted, the other asserts every printed figure is unchanged. Both go red if the arithmetic is touched. The red baseline for `GE-127f-4` is the first arm alone — do not cite the fence arms as evidence the prose changed.

**Related.**
- `KI-CG-20260908-file-size-refusal-advises-a-dead-command` (resolved) — same gate, same block, same class: the verdict is right and the attached advice is not. Third time this refusal's guidance has been the defect rather than its arithmetic.
- `GE-127e`'s notes — the argument that what destroys a size standard is the cost of complying at the moment you are blocked. Advice that is wrong by a factor of two raises exactly that cost, which is why this is filed rather than left as wording.

**Pattern:** a refusal that prints a correct number and an incorrect explanation of it, so following the words and following the figure lead to different places and the reader cannot tell which is authoritative.

---
