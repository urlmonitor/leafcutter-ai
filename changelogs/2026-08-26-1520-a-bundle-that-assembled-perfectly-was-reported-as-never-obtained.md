---
title: A bundle that assembled perfectly was reported as never obtained
date: "2026-08-26"
time: "15:20"
type: manual
components: 
  - build_orchestration
summary: "The fast lane now tells you which of three things went wrong with its context bundle, instead of blaming the one that did not happen."
description: "BO-2400c-1-iii. The context-bundle gate had two outcomes: usable, or one shared not-obtained halt. A live run assembled a 141,933-byte bundle perfectly and was told the bundle was never obtained. Replaces that with four disjoint states - usable, not_obtained, obtained_but_a_reference, obtained_but_incomplete - each with a self-naming halt message. The reference halt states that assembly SUCCEEDED, echoes the reported size and location, and says the lane cannot follow a reference because it cannot read a filesystem. Reference detection uses three independent signals so it does not depend on the producer cooperating with the schema. JavaScript half only; shrinking the bundle is BO-2400c-1-vi."
---

## Entry

A fast-lane run assembled its context bundle perfectly — 141,933 bytes, exit 0, empty
stderr, the breakpoint marker present exactly once in the file on disk — and the lane
halted saying **the context bundle was not obtained**. That message was not merely
unhelpful; it named the one thing that had not happened, and it sent anyone reading it
to look for a failure in the assembling step, which had succeeded.

The cause was that the gate had only two outcomes. Either the reply was usable, or it
took a single shared halt whose text listed every way a bundle can go wrong — failed,
declined, empty, marker missing — without saying which. Anything that was not usable
came out sounding like nothing came back.

What actually happened is the third case, and it is the interesting one. The bundle was
too large to inline in an agent's JSON reply, so the producer did the sensible thing:
it returned a truncated preview and told the lane where the full text was on disk. The
lane cannot follow that pointer — the workflow body has no filesystem access, which is
the whole reason the bundle is fetched through an agent in the first place. So a
perfectly good bundle became unreachable, and the lane blamed the wrong step.

`BO-2400c-1-iii` replaces the two-way gate with four disjoint states:

- **usable** — content, marker present; sent verbatim as the prefix of every
  build-context-carrying dispatch.
- **not_obtained** — nothing came back, or the reply is unparseable.
- **obtained_but_a_reference** — the assembly SUCCEEDED and the halt says so, echoing
  the reported size and location, and explaining that the lane cannot follow a
  reference because it cannot read a filesystem.
- **obtained_but_incomplete** — real content, but the marker is absent or a layer empty.

Each failure halts with the context-bundle phase named and a message naming that state
and only that state. None falls back to a prompt composed some other way, so a lane
that is not assembling its context stays visibly different from one that is — which is
how the original defect went unnoticed for a month.

Reference detection deliberately does not depend on the producer cooperating. Three
independent signals feed it: the returned string is itself a locator; the reply carries
a `location` field (added to the schema here, alongside `bytes`); or the returned text
is a truncated preview that names a path in prose. That third signal exists because the
reply actually observed had **none** of the first two — `location` did not exist yet, and
the preview opened with real bundle content rather than a path, so both cooperative
signals missed. A schema is a request, not a guarantee.

That third signal is a heuristic, and it is worth being explicit about why that is
acceptable here: it runs only after the usable check has already failed. A reply
carrying the marker never reaches it. Every reply it sees is halting the run regardless,
so the only thing at stake is which failure name it is given — a false positive
relabels a doomed reply and can never dispatch an unbundled prompt or turn a failure
into a pass.

One trap is covered explicitly. In the observed preview the marker appears HTML-escaped
while the prose discusses the marker itself. The obvious "fix" — unescape, then look for
the marker — would let a preview that merely *mentions* the marker satisfy the gate and
send a truncated bundle downstream as though it were complete. A dedicated test pins
that such a preview is still a reference and still refused.

**This does not make the lane work on an oversized bundle.** It makes the failure
honest. The criterion says so in its own text: the refusal is a check on an
already-small payload, never the thing that makes it small. Shrinking the bundle — the
~87% of it that is duplicated content the receiving agent already has — is the separate
Python-side record `BO-2400c-1-vi`. This change is the JavaScript half only, and the
split is deliberate: doing both in one pass would make a later regression impossible to
attribute to the right record.
