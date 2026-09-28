---
title: "KI-CG-20260914-doc-length-blocks-registers — RETRACTED: \"check-doc-length tests absolute size and refuses any register edit\" — tested and disproved; it ratchets, and the append it refused was a real growth"
description: "KI-CG-20260914-doc-length-blocks-registers — RETRACTED: the gate ratchets on growth rather than blocking on absolute size, and the append-heavy register problem was removed independently by the one-file-per-issue split."
type: reference
category: reference
status: active
created: '2026-09-14'
last_updated: '2026-09-15'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260914-doc-length-blocks-registers — RETRACTED: "check-doc-length tests absolute size and refuses any register edit" — tested and disproved; it ratchets

> One known issue. Index: [commit-guardian.md](../../commit-guardian.md).
> Filename severity is the three-level index bucket (`low` — retracted before
> it was ever acted on); the original grading was `high` and is preserved below.

- **Severity:** n/a — retracted. Originally filed `high`.
- **Status:** **closed — hypothesis disproved by experiment**, 2026-09-15. Kept as a record so
  the same wrong diagnosis is not filed again; the *observation* that prompted it is real and
  is explained correctly below.
- **Occurrences:** 1
- **First seen:** 2026-09-14 · **Retracted:** 2026-09-15

## What was originally claimed

That `check-doc-length`, flipped from warn to refuse in PR #801 against a 300-line limit, tests
**absolute size rather than growth**, and therefore refuses *any* commit touching a
known-issues register — *"including a pure deletion"* — making the project's own defect-recording
surface uneditable.

## Why it is wrong

The gate **ratchets**, exactly as `check-file-size` does for code. Measured directly against
`docs/reference/ac-schema.md` (989 lines, far over the 300-line limit), staged and run through
`check_doc_length.py`:

```text
shrink  989 -> 985 lines (still 685 over the limit)   -> exit 0, PASS
grow    974 -> 978 lines                              -> exit 1, BLOCKED
        "Already over its limit and grew further in this commit (lines 974 -> 978)."
```

A doc already over its limit may not **grow**; shrinking or holding steady always passes. The
config's own `_comment` says so plainly, and says why: *"Blocking is survivable only because the
gate now ratchets … 59 of 339 tracked docs are already over, and an absolute block would freeze
every one of them including the append-heavy registers."* The retracted entry asserted the
opposite of both the documented design and the measured behaviour.

**The observation was real; the diagnosis was not.** The commit that hit this was appending three
new entries to two registers — a genuine growth of an already-oversized file, which is precisely
what the ratchet exists to refuse. The gate did its job. "It blocked me" was promoted to "it
blocks everything" without running the deletion case that would have separated the two.

## The underlying concern was real, and was removed independently

Append-only registers do sit badly with a growth ratchet: every new entry is growth by
construction. That tension was resolved the same day by PR #817, which split
`docs/known-issues/` into one file per issue. The `commit-guardian` index dropped from 4,536
lines to 159, and each entry is its own small file — so a new entry is a **new file**, not growth
of an existing one, and the ratchet never fires. No exemption and no ratchet change is needed.

## One observation worth keeping

`check-doc-length` is **pre-commit-only**. `.github/workflows/ci.yml` runs just the six AC hooks
through `pre-commit`, so this gate runs in no CI job. The warn → refuse flip was therefore
invisible to every pull request and could only surface as a local commit failure. That is a
general property of the hook set, not a defect of this gate, and it is the reason a change in
enforcement level can land without any check reporting the new blast radius.

## How this got filed wrong

The refusal and the register's size were observed together and a mechanism was inferred from
them, without running the one-minute experiment — edit an oversized doc *downward* and re-run —
that distinguishes "blocks on size" from "blocks on growth". The entry then stated the stronger,
more alarming claim ("including a pure deletion") as fact, having tested neither direction. It
was filed by the same author, in the same session, as the two entries it was written to explain
being unable to file.

**Pattern:** a gate's refusal read as evidence for a mechanism the refusal does not distinguish —
the same shape as `KI-CG-20260826-1334`, where a WARNING and an `exit: 0` in one output stream
were linked causally without the A/B that separates them.
