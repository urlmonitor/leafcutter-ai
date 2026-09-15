---
title: "KI-DS-001 — Four of the five Diataxis authoring conventions have never existed"
description: "KI-DS-001 — Four of the five Diataxis authoring conventions have never existed"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - documentation_system
related_docs:
  - docs/known-issues/documentation-system.md
  - docs/known-issues/README.md
---

# KI-DS-001 — Four of the five Diataxis authoring conventions have never existed

> One known issue, split out of `docs/known-issues/documentation-system.md` on
> 2026-09-14. Index: [documentation-system.md](../documentation-system.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 2
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-19
- **Where:** `docs/how-to/documentation/` — only `write-reference.md` is present; and no
  build phase ships any of them to an adopter

**Second occurrence, 2026-08-19 — reported from a consumer install, where the count is
five of five, not four of five.** DIAGraph (`roche-sandbox/dia-graph`, pin `54356a92`)
found `reference-author`, `how-to-author`, `explanation-author` and `adr-author` all
non-functional out of the box. Two facts this adds to the entry below:

- **The behaviour has changed since first recording, and the entry's "they improvise"
  is now only half true.** `reference-author.md:122` and `explanation-author.md:112-118`
  now instruct a hard stop — *"If `docs/how-to/documentation/write-reference.md` does not
  exist, surface this gap in the response payload and stop — do not invent a reference
  convention from scratch."* `how-to-author` (`:61`, `:114`) and `adr-author` (`:72`) still
  only mandate the read without stating a failure posture. So the agents now split: some
  stop, some are free to improvise. The fail-closed half is the **right** design — this is
  not a regression to undo — but it converts a silent quality problem into four visibly
  dead agents.
- **Even the one convention that exists never reaches an adopter.** `write-reference.md`
  lives in `docs/how-to/documentation/` in *this* repo, which is package documentation, not
  a template. `find templates -name "write-*.md"` returns nothing and no build phase
  references the path. So the fix below ("write the four conventions") is necessary and not
  sufficient: writing them into `docs/` fixes this repo and leaves every adopter exactly
  where they are.

The adopter-delivery half is filed separately as **KI-DS-002**, so it can be picked up on
its own — writing the four conventions into `docs/` does not put them anywhere an adopter's
agents will look, and closing this entry alone would leave every install exactly as broken.

Whatever ships, apply the fail-closed wording uniformly to all five specialists in the same
change — a mandatory read whose absent-file behaviour is unspecified is what produced the
original silent-improvisation half of this issue.

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

Necessary and not sufficient — see KI-DS-002 for why writing them does not deliver them.

---
