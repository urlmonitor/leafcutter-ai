---
title: A blank line in a layer stops meaning the layer is empty
date: "2026-08-31"
time: "07:10"
type: manual
components: 
  - build_orchestration
  - injection_builder
summary: "The fast lane refused a complete 16,442-byte bundle because a markdown layer ended in a blank line. Emptiness is now decided at assembly time, where the layer boundaries still exist."
description: "A live run halted as obtained_but_incomplete on a bundle that was correct in every respect - marker present exactly once, every layer populated. The gate inferred emptiness from formatting, testing for a run of 4+ newlines on the theory that only an empty layer produces one. A markdown document ending in a blank line produces one too. The check moves to injection_builders.py, which refuses an empty required layer at assembly time and names it; the lane keeps only transport checks that are unambiguous on real content. Regression tests use real layer content with real trailing blank lines, which is what the original synthetic fixtures missed."
---

## Entry

A fast-lane run halted with:

> The context bundle was obtained but is incomplete: the cache breakpoint marker is absent,
> or one of its layers is empty.

The bundle was 16,442 bytes, the marker was present exactly once, and every layer had
content. Nothing was empty.

The gate was inferring an **assembly-time** fact from **transport-time** bytes.
`assemble_context_bundle()` joins layers with `"\n\n"`, so an empty layer collapses two
joins into four consecutive newlines — and the gate tested `/\n{4,}/`, with a comment
asserting such a run *"never occurs when every layer is non-empty"*.

That premise is false. A layer whose own content ends in a blank line produces the same
run. The architecture layer is a markdown document ending in an HTML comment and a trailing
blank line; joined to the next layer it yielded **five** consecutive newlines at offset
10642, and the run was refused.

`BO-2400c-1-vi` is what turned this from possible into certain. It pinned the architecture
layer to `docs/architecture/diagrams/c1-001-command-map.md` — so every run now carries a
real markdown document in that slot, and every run would have hit this.

### The fix is a boundary, not a better pattern

No textual rule in the lane can be sound here, because the signal is genuinely ambiguous:
once the layers are concatenated the boundaries are gone, and an empty layer and a
blank-line-terminated one are byte-identical in their effect. Tightening the regex would
just move the false positive.

So the question moves to where it can be answered. `injection_builders.py` still has the
layers as separate strings, so it refuses an empty required layer there and **names it**:

```
injection_builders assemble-bundle: required layer 'high_level' at '…' is empty
```

The lane keeps only checks that are unambiguous on real content:

- **the marker is present** — catches truncation before or across the breakpoint;
- **something follows the marker** — catches truncation immediately after it. This is not
  the empty-layer rule renamed: assembly now *guarantees* a non-empty `prior_tests` layer
  after the marker, so an empty suffix can only mean the text was cut in transit.

Each check now sits where its evidence is, and neither can fire on a healthy bundle.

### On the tests

The original tests passed throughout because their fixtures were short synthetic strings
(`"STABLE_ARCH_FOR_…"`) that no markdown document resembles. The regression tests here use
real layer content with real trailing blank lines, and one of them reads the actual pinned
architecture document off disk rather than standing in for it.

Both halves were verified as genuine red baselines rather than assumed. With the Python fix
reverted, the two empty-layer tests fail. With the JavaScript fix reverted, the blank-line
test fails with the live run's exact signature — the lane reaching
`release-on-context-bundle-fail` instead of the test-writer.

One test deliberately asserts its own fixture still contains the 4+ newline run it exists to
reproduce, so the guard cannot quietly stop guarding.

### Scope

The halt message keeps the word "incomplete". An earlier draft of this change reworded it to
"did not arrive intact", which read better and broke `BO-2400c-1-iii`'s actual promise — that
each state's message names its own state. The wording now does both.
