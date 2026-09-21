---
title: "KI-BO-019 — The context bundle is passed through an agent's JSON return value, so a large bundle arrives as a file path and the fail-closed gate halts a run whose bundle was fine"
description: "blocker — the fast lane cannot complete an end-to-end run on a real target"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-019 — The context bundle is passed through an agent's JSON return value, so a large bundle arrives as a file path and the fail-closed gate halts a run whose bundle was fine

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** blocker — the fast lane cannot complete an end-to-end run on a real target
- **Status:** open. The mitigation that shipped is the third fix option below, and the
  second occurrence **disproves** it — see "Second occurrence" at the end of this entry.
- **Occurrences:** 2
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-31
- **Where:** `templates/workflows-js/fast-lane-ship.js` — the `fastlane-context-bundle`
  dispatch and the `contextBundleUsable` gate that reads it (the `CACHE_BREAKPOINT_MARKER`
  constant and the `contextBundle.includes(...)` check)

**Symptom.** The lane asks its bundle agent to return
`{"bundle": "<the command's stdout, verbatim>", "obtained": true, ...}`. On a real target the
bundle is ~149 KB. The agent assembled it correctly, wrote it to disk, and returned a
**pointer** instead of the content:

```json
{"bundle": "file:/tmp/bo2400f13-bundle/bundle_output.txt", "obtained": true,
 "message": "Bundle assembled successfully (exit 0, no stderr) ... read that file to get the exact bundle text"}
```

The gate then evaluates `contextBundle.includes("<!-- CACHE_BREAKPOINT -->")` against a
47-character path, finds no marker, and halts the run (BO-2400c-1-iii).

**The gate is not the bug — it did exactly the right thing.** The bundle on disk is
well-formed: 148,891 bytes, 2,232 lines, five layers, with the breakpoint marker present at
line 958. Every check the gate performs is correct and the fail-closed posture is correct.
What failed is the **transport**: the contract says "return 149 KB of text as a JSON string
field", and that is not a contract an agent reliably honours. Note the message is not evasive
either — the agent said plainly what it had done and where the content was. It simply
answered a different question than the one the schema asked.

**Why this is structural rather than a retry-able flake.** The E2 workflow engine has **no
filesystem access**, so the lane physically cannot follow the pointer it was handed. The
bundle must arrive in-band or not at all. That puts two requirements in direct tension:
the bundle is large by design (it is a prompt-cache payload — that is the point), and the
only channel into the workflow is an agent's return value. Re-running may happen to succeed
if the agent echoes verbatim, which would make this look intermittent; it is not. The
contract is unsound at this size and will fail again on any comparably sized target.

**Evidence.** Run `wf_bd4984e8-438`, target `BO-2400f-13`. Five agents completed, none
errored. Worktree created (`worktrees/bo-2400f-13`, `fast-lane/bo-2400f-13`), set resolved to
the correct five ids, all five claimed, bundle assembled — then halt at `context-bundle`. The
halt payload's own `Detail` reads `"obtained": true` and `"Bundle assembled successfully"`
while the run is classified `blocked`, which is the tell: the lane's own message contradicts
its verdict because `obtained` and *usable* are being conflated in the operator-facing text.

**Fix direction.** Three shapes, and the choice is a real design decision:

- *Have the Python side do the check.* `assemble-bundle` already knows whether it inserted
  the marker. Return a small verdict (`{"ok": true, "bytes": N, "marker": true, "path": ...}`)
  and let the lane gate on the verdict rather than on the text, so the payload crossing the
  agent boundary stays small. This changes what "obtained" means, so BO-2400c-1-iii's wording
  needs revisiting alongside it.
- *Accept a pointer explicitly*, and give the lane a way to read it. That needs an fs
  primitive the engine does not have today, so it is the largest change.
- *Keep the verbatim contract and enforce it*, by making the agent's schema reject a value
  that looks like a path and by stating the size expectation in the prompt. Cheapest, and the
  least robust — it fights the model rather than the design.

**Second occurrence, 2026-08-31 — and it disproves the option that shipped.**

The third option above is what landed: `fast-lane-ship.js`'s bundle prompt now states
`SIZE EXPECTATION: the assembled bundle is roughly twenty kilobytes (~20 KB)` and refuses a
reply that "names where the text can be found instead of containing the text". Run
`wf_22fae0b9-291`, target `BP-900g-9-i`, failed anyway — in a **new and worse way**.

The agent did not return a path this time. It returned the content **in-band, and altered**:

```
&amp;lt;!-- CACHE_BREAKPOINT --&amp;gt;        <-- what arrived
<!-- CACHE_BREAKPOINT -->              <-- what assemble-bundle emits
```

The whole payload had been HTML-escaped in transit — every `-->` in the architecture doc's
mermaid arrived as `--&gt;` — and the marker, which contains `<`, was escaped twice. The
source doc on disk contains **zero** HTML entities, confirmed by grep, so the escaping is
introduced by the transport and not present in the input.

Three things follow, and each is worse than the first occurrence.

**The reference-rejection guard cannot see this.** It was added precisely for occurrence 1
and it is working correctly — the reply *is* content, not a pointer. Mangled content passes
every check that distinguishes content from a reference, because it is content.

**The size hypothesis is wrong.** Occurrence 1 was 149 KB and this entry concluded "the
contract is unsound at this size and will fail again on any comparably sized target". The
agent reported `"bytes": 18190` for occurrence 2 — **18 KB, under the ~20 KB the prompt
itself names as the expectation**. It failed at the size the design targets. The contract is
not unsound at 149 KB; it is unsound at any size, because byte-exact reproduction of markup
is not something a model does reliably however short the text.

**Only the marker check caught it.** Nothing else in the lane compares what arrived against
what was assembled. Had the bundle contained no marker-shaped token, silently corrupted
context would have been handed to the test-writer and coder dispatches as though intact, and
the run would have completed green on a mangled prompt. The gate that saved this run exists
for cache correctness, not integrity — it caught an integrity failure by luck of shape.

**What this does to the fix calculus.** Option three is no longer "least robust"; it has been
tried and has failed at its design size, in a way its own new guard cannot detect. Option one
(let the Python side emit a small verdict and gate on that, keeping the payload off the agent
boundary) is the only remaining shape that does not require an fs primitive the engine lacks.
Whatever is chosen, the lane needs an integrity check comparing what arrived against what was
assembled — a byte count or digest returned by `assemble-bundle` and re-derived on the
received text — because "it looks like content" is demonstrably not the same as "it is the
content", and that distinction is currently unmade.

**Operational consequence right now: the fast lane cannot complete a run on any target.**
Both occurrences halted at the same phase, five to six agents in, after creating a worktree
and claiming the build set. The worktree is left behind.

Whichever is chosen, the operator-facing message must stop saying "was not obtained" when
`obtained` was true. Distinguish *not obtained* from *obtained but unusable, because X* —
the current text sent a reader looking for an assembly failure that had not happened.

**Update, 2026-08-25 — the fix direction above is superseded, and the layer's premise is
false.** A Product Owner pass on the transport question found that the thing the transport
exists to protect does not exist. Three findings, each verified independently:

- `grep -rn "cache_control" templates/ scripts/ config/` returns **zero hits**. No provider
  cache breakpoint is set anywhere in the product. `<!-- CACHE_BREAKPOINT -->` is a literal
  HTML comment inside a prompt string, and nothing consumes it but this gate.
- The two consumers **cannot share a cached prefix even under automatic provider caching**.
  Line 561 dispatches `agentType: "test-writer"`; line 635 dispatches `agentType:
  "python-coder"`. Different agents, different system prompts. A prompt cache matches an
  exact prefix from the *start of the request*, system prompt first, so the two requests
  diverge long before the bundle appears in the user message. The bundle's "stable prefix"
  is not a prefix of anything the cache sees.
- The stable layer is **not stable across runs**. The bundle prompt names
  `docs/architecture/README.md`, which does not exist, and tells the agent to substitute
  "the nearest architecture index" — so that layer is composed by agent judgement and two
  runs at one target need not produce the same bytes. `BO-2400c-1-iv` only asserts
  byte-identity *within* one run, which is a triviality of interpolating one JS variable
  twice.

`BO-2400c-2.yaml:113` and `BO-2400c.yaml:33` already conceded the first point in writing on
2026-08-18/19. Work continued against the old claim regardless, which is the part worth
remembering.

**The payload is 87% duplicate — measured.** `conventions.md` is 38,291 B and
**byte-identical** to the worktree `CLAUDE.md` (`diff -q` exits 0), which the harness already
injects into every agent dispatched into that worktree. `acs.yaml` is 90,887 B of AC records
that the test-writer prompt (line 548) *already instructs the agent to read from
`${acStoreRoot}`*. Together 129,178 of 148,891 bytes are a second copy of something the agent
already has. Genuinely additive: architecture + high_level + prior_tests ≈ **20 KB**.

So the transport failure is a symptom and the payload is the disease. **Chosen direction:**
split on the *duplicate-vs-additive* line rather than stable-vs-volatile — pass only the
~20 KB the agent does not otherwise have, drop the conventions and acs layers entirely, and
keep the reference-rejection and a stated size expectation as a cheap belt on a payload
already small by construction rather than as the mechanism. Specified in the
`BO-2400c-1-iii` amendment and the new `BO-2400c-1-vi`; `BO-2400c-1-iii` is reset from
`done` to `in_progress` because its gate half works and its transport half never did.

Two consequences recorded rather than left implicit. **The CLI signature changes:**
`injection_builders.py` marks `--architecture`, `--conventions`, `--high-level`, `--acs` and
`--prior-tests` all `required=True` (lines 654-670), so dropping two layers changes what
`assemble-bundle` accepts, not just what the lane passes — a call-site audit in the removal
direction. **And the L1 is overclaiming:** `BO-2400c`'s "spend less time and money on every
build" is not what this layer delivers. Until `BO-2400c-2` exists and reports, no cost claim
belongs in a doc, a PR body, or a release note; if it reports no shared cache, the L1 should
be re-framed from *cost* to *consistency* — the layer's real remaining benefit is that every
agent starts from the same complete, named context instead of whatever it decides to read.

**Keep the fail-closed gate exactly as it is.** It is the one part of this family with a
demonstrated win: on its first live run against a real target it caught a genuine transport
defect and refused to proceed.

---
