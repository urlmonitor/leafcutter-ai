---
title: The bundle stops carrying a second copy of what the agent already has
date: "2026-08-26"
time: "17:20"
type: manual
components: 
  - build_orchestration
  - injection_builder
summary: "The fast lane's context bundle drops the two layers that duplicated content the receiving agent already had, taking it from 149 KB to about 20 KB."
description: "BO-2400c-1-vi. 87% of the context bundle was a second copy of things the receiving agent could already see: the conventions layer was byte-identical to the CLAUDE.md the harness injects into every dispatch, and the acs layer was the full text of records sitting in the run's own workspace store. Both layers are REMOVED from assemble_context_bundle() and from the assemble-bundle CLI - not defaulted, removed - and replaced by an instruction, now carried by both context-carrying dispatches, to read each record from the store. The architecture layer is pinned to one verified-existing path with no fallback. Measured on real files: 20,645 bytes against 148,891. Also fixes an empty-layer detection gap in BO-2400c-1-iii's guard that this change made reachable."
---

## Entry

The fast lane's context bundle had grown to 148,891 bytes and could no longer cross an
agent boundary as text in a return value. `BO-2400c-1-iii` made that failure honest — it
now says the bundle came back as a reference rather than blaming the assembling step. This
is the other half: making the bundle small enough that the situation does not arise.

The interesting part is what the 149 KB was made of. Measured on the run that failed:

- **conventions — 38,291 bytes**, and byte-identical to the worktree's `CLAUDE.md`. The
  harness already injects that file into every agent dispatched into the workspace, so the
  bundle was carrying a second copy of text the receiving agent is handed anyway.
- **acs — 90,887 bytes**, the full YAML of five records that live in the run's own isolated
  workspace, where any agent working there can simply open them.

Together 129,178 of 148,891 bytes — **87%** — was duplicate. What remains is what the agent
genuinely does not otherwise have: the architecture overview, the high-level parent criteria
for the target, and the prior tests for the area.

Both layers are **removed** from `assemble_context_bundle()` and from the `assemble-bundle`
CLI, rather than made optional. That distinction is the point. An optional layer defaulting
to `None` would have been backwards-compatible and wrong: it leaves a live path by which the
largest duplicate in the payload gets reintroduced by a caller who does not know better. When
a structure duplicates a source the receiver already has, the fix is to delete the duplicate,
not to make it opt-in. Because the flags are gone from argparse rather than ignored, an agent
that tries to pass one now gets a hard rejection instead of a silently re-inflated bundle.

The content that left the bundle is replaced by an **instruction** — read each id's record
from the run's own store — and that instruction is now carried by *both* context-carrying
dispatches. It already existed in the test-writer prompt. It had never existed in the coder
prompt, so the coder had been reasoning about records it was neither given nor told to go and
read. Nothing failed loudly when that instruction was missing, which is exactly why it went
unnoticed.

**The size is compositional, not capped.** There is no byte limit, no truncation step, no
summarisation, no chunking. Roughly 20 KB is simply what this layer set weighs. That ordering
matters: the transport check in `-iii` is a belt over an already-small payload, and a cap here
would have inverted the two.

Verified by running the real CLI over real on-disk files rather than fixtures — architecture
11,468 + high_level 4,145 + prior_tests ~5,000 → a **20,645-byte** bundle, with the workspace
`CLAUDE.md` text absent, the build set's own AC text absent, and exactly one structural
breakpoint marker present.

### The architecture layer stops being chosen by judgement

The bundle prompt used to name `docs/architecture/README.md` and tell the agent to fall back
to "the nearest architecture index if that exact path does not exist". That file does not
exist and never did, so the layer's content depended on which document an agent happened to
pick that day — and two runs aimed at the same target need not have produced the same bundle.
It is now pinned to `docs/architecture/diagrams/c1-001-command-map.md`, the L1 system-context
diagram, with no fallback, no glob, and no nearest-match clause anywhere.

The more relevant document for this lane would have been `agent_delivery_workflows.md`, and it
was rejected on size alone: at 103,895 bytes it would have blown the 20 KB target single-
handedly and re-created the exact failure being fixed.

### A hole this change opened in the guard it sits next to

`-iii` detects an empty layer by looking for a run of four or more newlines — what two
back-to-back joins produce. That only ever catches an *interior* empty layer. Before this
change the last-position case was unreachable, because `acs` always sat between the marker and
`prior_tests`.

Removing `acs` makes `prior_tests` the entire volatile suffix, so emptying it leaves a single
trailing blank line that the newline rule cannot see. And `prior_tests` is precisely the layer
most likely to arrive empty, because the bundle prompt tells the agent a short placeholder is
fine when no prior tests exist yet. The gate now also checks that the text after the marker is
non-empty. Shipping the layer removal without that would have quietly widened a hole `-iii`
had just closed.

### Known divergence

`docs/reference/fast-lane-prompt-caching.md` still documents the eight-parameter signature, a
layer table naming both removed layers, and three worked examples whose command lines pass
`--conventions` and `--acs`. All of it now contradicts the code. A reference page is
documentation-expert's surface, so it is flagged here rather than silently absorbed — a
companion documentation record should be raised. A reference doc describing a signature that no
longer exists is how the next reader reintroduces the layers.
