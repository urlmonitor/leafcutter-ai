---
title: "Criteria for a guard that has never said no"
date: "2026-09-01"
time: 1930
type: manual
components: 
  - guardrail_engine
  - build_pipeline
  - commit_guardian
summary: "Sixteen critical-priority acceptance criteria for the defect class this repository keeps shipping — a check that is right on every input it is ever given because its refusal branch is unreachable — plus a new false-green mechanism entry for the shape."
description: "Authors a new L1 (GE-120f, 'A guard that has never said no is not counted as protection') with five L2s and four L3s, alongside six sibling criteria under GE-126b, GE-126c and BP-100n. All sixteen are priority critical, readiness draft. The worked example is templates/hooks/readme_read_guard.py: registered, correctly wired, running on every Edit and Write, and unable to refuse anything — three of its four gated prefixes resolve out from under themselves through symlinks and the fourth names a directory this repository does not have. Existing defences verify that a guard's verdict is correct; none verifies that a guard is capable of saying no. The regime specified: every check declares one known-bad input, the declaration is machine-read, and the rejection is demonstrated by feeding that input through the entry point the protected surface actually uses. Also adds M9 to the false-green mechanism catalogue, with two sub-variants, and corrects a stale freeze rule in the guardrail-engine PROJECT_CONTEXT that had been cited as current for eight days after it expired."
breaking: false
---

## Entry

Existing defences ask whether a guard's verdict is **correct**. None asks whether the guard is
capable of saying **no**.

The worked example is `templates/hooks/readme_read_guard.py`. It blocks Edit and Write until the
folder README has been read. It is registered in `.claude/settings.json`, correctly wired, and
runs on **every** Edit and Write in the repository. Its `GATED_PREFIXES` constant is greppable
and reads correct. Measured with the guard's own `_is_gated`:

```
.claude/hooks/x.py        gated=False   → <root>/.leafcutter/hooks/x.py
.claude/agents/x.md       gated=False
.claude/skills/x/SKILL.md gated=False
alembic/versions/x.py     gated=True    ← and alembic/ does not exist in this repository
```

Three prefixes resolve out from under themselves through symlinks. The fourth names a directory
that is not here. The guard has never refused anything in its life, and nothing in the system
could tell it apart from one that refuses correctly.

A grep-based review confirms it is configured. Only execution shows it cannot fire.

## What is specified

**`GE-120f` — "A guard that has never said no is not counted as protection."** Under `GE-120`
("trust that a green check actually checked something"), which is the sentence this defect
violates most directly. Five L2s and four L3s:

- the refusal is established by putting the declared known-bad input through **the entry point
  the protected surface uses**, and the record states what was *observed*, not what was declared
- which entry point was used is itself stated — a refusal produced by reaching inside the check
  is not a demonstration
- **a check that also refuses the work it is meant to accept has demonstrated nothing.** This was
  not in the original sketch and is the regime's own off switch: on day one the cheapest way to
  quieten a not-demonstrated finding is to widen a guard until it refuses everything, which
  satisfies every other clause in the tree while protecting less than before
- a check whose declared rejection was not observed is named and fails; one never asked to refuse
  is never counted among the things keeping the work safe
- the run states how many checks it actually put an input through, that figure moves when the
  population moves in **either** direction, and a run that put an input through none fails as
  unresolved
- a check joins the protected family only by declaring what it must refuse, read from where it is
  registered — prose does not satisfy it

Six siblings under `GE-126b`, `GE-126c` and `BP-100n` carry the per-check report leg: the datum
and its four-value state vocabulary, which copy a proof actually loaded and whether a verdict
moved, and a declaration that contradicts the file it describes.

## Built on vocabulary the repository already had

`config/verification_flow.schema.json` already states the principle — *"The known-bad input that
MUST be rejected. A check without one can pass on dead code"* — models the
`not_applicable` + reason hatch, and records an unrun control as `unverified` rather than
omitting it. It has **zero code readers**. The schema, one instance document, two changelogs and
a handful of AC records are the only files that mention it repo-wide.

So this is not a new concept. It is the reader for one the repository designed and never built,
and every record says explicitly never to mint a second vocabulary beside it.

## Boundaries, so four adjacent trees do not absorb it

`BP-100n-4` owns enumeration (which guards are in the set at all). `BP-100k-4` owns reachability
for a registered gate whose trigger can never match. `GE-120c-6` owns a deployed guard nothing
invokes. `TQ-500` owns falsifiability of *tests*; this owns falsifiability of *guards*.

`readme_read_guard` passes all four — registered, enumerated, invoked, reachable, running on
every edit — and still cannot refuse. None of the four may be closed as a duplicate of this, nor
the reverse.

## M9, and a stale rule corrected

`docs/reference/false-green-mechanisms.md` gains **M9 — a guard whose refusal path has never been
exercised**, with two sub-variants: the constant that reads correctly and never matches, and the
falsification proof applied to a copy the verifier does not load. M1, M5 and M8 all describe a
check reaching a *wrong or empty* verdict; M9 is a check that is right every time and useless
every time. M1–M8 body prose is byte-unchanged; M5 gains a cross-reference to the verification
schema.

`guardrail-engine/PROJECT_CONTEXT.md` gains a dated correction. It stated that a byte-identity
guard forbids adding records to the `GE-120` folder. That guard was amended to an id-stability
check on 2026-08-18 — eight days before the note citing it was written — and its docstring now
says adding a record is "ordinary growth … and must not fail." Verified by writing the record and
running the guard: 6 passed. The general rule is recorded with it: the freeze note and the guard
test drift apart, and only the guard test is binding.

## Deliberately absent

**No criterion states how many instances of this defect exist.** Records authored the same day
disagreed on the figure, so it was recorded as disputed and forbidden below `GE-120f`. A
population is what a census measures, not what a criterion asserts — and this tree specifies the
census.

All sixteen records are `readiness: draft`. Approval is not the authoring pipeline's to give.
