---
title: "Known issues — documentation-system"
description: "Open, observed defects in the documentation-system component: the Diataxis routing agents, their canonical authoring conventions, and the doc surfaces they write. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-18
components:
  - documentation_system
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/how-to/documentation/write-reference.md
---

# Known issues — documentation-system

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-DS-NNN` section using the next free number.
Nothing here is generated — edit it by hand. Fill in what you actually know; an issue
recorded with a thin `Evidence` line is far better than one not recorded.

**Hitting an existing issue.** Increment `Occurrences` and update `Last seen`. Do not
add a duplicate entry. Occurrences is an escalator, not the score — a blocker seen once
outranks an annoyance seen ten times.

**Severity** is `blocker` (work cannot land) / `high` (silent wrong behaviour) /
`medium` (real but survivable) / `low` (noise, dead code, cosmetics).

**Closing an issue.** When the fix lands, delete the section and reference the issue id
in the commit message. If it earns real work, author an AC for it and note the AC id in
`Status` — this file is a capture surface, not a replacement for the AC store.

---

### KI-DS-001 — Four of the five Diataxis authoring conventions have never existed

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `docs/how-to/documentation/` — only `write-reference.md` is present

**Symptom.** Each Diataxis specialist is instructed to load a canonical convention
before writing, named as its **single source of truth** for heading hierarchy, section
structure, the Location Decision Rule, and a copy-pasteable skeleton. Four of the five
targets do not exist:

| Cited convention | Cited by | Exists |
|---|---|---|
| `write-reference.md` | `reference-author` | **yes** |
| `write-how-to.md` | `how-to-author` | no |
| `write-adr.md` | `adr-author` | no |
| `write-explanation.md` | `explanation-author` | no |
| `write-architecture-doc.md` | `architecture-author` | no |

The agents do not fail on the missing load — they improvise from the fragments quoted in
their own templates. So every how-to, ADR, explanation and architecture doc in this repo
was authored without the convention that governs its genre, and `documentation-expert`
routes to four specialists whose stated source of truth is absent.

**Evidence.** Found 2026-08-18 by a `how-to-author` invocation that hit the missing
dependency and reported it instead of silently continuing; the remaining three came from
sweeping every `docs/how-to/documentation/*.md` path cited under `templates/agents/` and
`docs/agents/` (39 references across the five names). Confirmed by history, not just by
absence: `git log --all` returns **nothing** for `write-how-to.md`, `write-adr.md`,
`write-explanation.md` and `write-architecture-doc.md` — none has ever been committed —
while `write-reference.md` traces to `d3661dcb3` (PR #378). So this is not rot; the four
were never written.

`docs/agents/documentation/how-to-author.md:196` is a relative markdown link to one of
the missing targets that the doc-link checker has not flagged — worth checking whether
that hook covers `docs/agents/`.

**Fix direction.** Write the four conventions; `write-reference.md` is the working model
and the sibling genre, so the shape is established. Until then, a specialist whose
convention is absent should fail loudly rather than improvise — a silent fallback is what
let this survive unnoticed across every doc the pipeline has produced.

