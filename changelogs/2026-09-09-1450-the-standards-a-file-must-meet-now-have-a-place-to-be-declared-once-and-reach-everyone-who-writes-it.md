---
title: "The standards a file must meet now have a place to be declared once and reach everyone who writes it"
date: "2026-09-09"
time: "14:50"
type: manual
components:
  - infrastructure
  - ac_store
summary: "Specifies a capability that does not exist yet: declare a standard once, per kind of file, and every specialist that owns that kind of file is told about it thereafter — including for guardrails added later. Today exactly one cell of that grid works (Python line limits reaching python-coder), every other file type and every other specialist is told nothing, and each new value needs its own hand-written injector."
description: "New L0 INF-1200 in infrastructure with six L1s, thirteen L2s and two L3s — no code. build.py's _inject_file_size_limit reads file_size.line_limits['.py'] and injects it into python-coder.md, which is correct and preserved (INF-1200f-2 exists to protect it); nothing tells anyone about .sql, no other agent template references any standard, and agent_registry.json's owns_file_extensions is never joined to commit_guardian.json's thresholds. Placed in infrastructure rather than under INF-1100 (readiness: approved — widening its promise would rewrite what was approved) or GE-127 (which owns whether a file is refused, not whether the author was told). Twenty-one named mutations carried verbatim into eighty descriptors, most with a mixed-outcome shape where named sibling records must STAY GREEN. Two defects found while specifying and recorded rather than fixed: build.py's silent fallback to a literal 400, and the fact that only file_size declares which file types it governs."
commits:
  - a92a9a1a0
breaking: false
---

## Entry

### The gap: told after, or not told at all

Being refused at commit time and being told beforehand are different goods, and this
repo only has the first. `GE-127` refuses a file that is too long. Nothing tells the
person about to write it what the limit is — except in one case.

That case works and is worth preserving: `build.py` reads the Python line limit out of
`commit_guardian.json` at build time and injects it into `python-coder`'s instructions,
where it appears in five places including a stop-and-ask trigger. The figure an agent is
told is the figure the gate enforces, from one source.

It is one cell of a grid. `.sql` has a declared limit of 600 and nothing mentions it.
`frontend-coder` and `sql-coder` reference no standard at all. And the injector is a
bespoke function sitting beside another bespoke function, so every new value needs
someone to remember to write one *and* to hand-edit the right templates. Three further
guardrails — complexity, SQL complexity, folder density — have thresholds configured and
no audience whatsoever.

### What the tree specifies

Six L1s, split along two axes that are deliberately kept apart: **every specialist that
owns a file type** (`INF-1200c`) and **every standard, including ones added later**
(`INF-1200d`). Merged, an implementer takes whichever axis is cheaper — which is exactly
how the grid ended up with one filled cell.

The keystone is `INF-1200b`: covering a new kind of file is *one statement*, and the
change set contains nothing else. A design where each template still names the value it
wants, auto-filled at build, satisfies the fidelity criterion and fails this one — that
is today's design generalised.

`INF-1200e` makes an uninformed specialist a **countable** condition. Today an agent
told nothing looks identical to an agent for which no rule exists.

### The mutations are the load-bearing part

Twenty-one named mutations, carried verbatim into eighty descriptors. Most have a
deliberate mixed-outcome shape: some arms must go red **while named sibling records stay
green**, and that green half is the evidence the records are not one insight written
twice. `INF-1200d-1`'s mutation must leave all of `c-1` green — which is what proves the
two axes are genuinely independent. Each such descriptor states its own failure
condition: an injection that reddens every arm is a *failure* of that descriptor, not a
stronger result.

One stuck answer — "give every specialist every standard" — would satisfy four records
at once and silently empty `INF-1200e`'s census, because nobody is ever uninformed. A
single broadcast injection now has to redden six named arms across five records
together.

### A tension neither L1 states, costed on both records

`INF-1200b-2` requires that no hand-authored instruction carry a standard. `INF-1200f-2`
requires the one working pairing's several in-context references to survive at no fewer
points, including a trigger embedded mid-instruction. Both hold only if the mechanism
can place content at multiple, semantically-chosen points inside one brief — materially
harder than injecting a single block. The cheap build satisfies the first, quietly fails
the second, and every count improves while it does.

### Two defects found while specifying

`build.py`'s injector catches `OSError`, `JSONDecodeError`, `TypeError` and `ValueError`
and falls back to the literal `400` with a bare `pass`. If the config becomes unreadable,
every agent is told 400 regardless of what is declared, with no signal — a second figure
by another name, and a Rule 3 violation.

And only `file_size` declares *which* kinds of file it governs. Complexity, SQL
complexity and folder density declare thresholds with no applicability at all — it lives
only in each script's filename — so a generic walk cannot derive their audience today.
That is a precondition for the whole capability and is recorded in `INF-1200d-1`.

Both are recorded in `it_requirements`, not fixed here.

### Note

`declares_side_effect` was authored `true` on twelve records and corrected to `false`:
`check_ac_schema` derives the value from each record's own Then clause and blocked the
commit. These criteria assert what a brief *says*, observed by reading it; the build's
incidental file writes are not what the clause claims. Worth knowing that
`validate_ac_schema.py` passed all 4008 records with the wrong value in place — only the
commit hook derives and compares, so a clean standalone validation is not evidence on
that field.
