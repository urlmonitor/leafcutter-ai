---
title: "Known issues — documentation-system"
description: "Open, observed defects in the documentation-system component: the Diataxis routing agents, their canonical authoring conventions, and the doc surfaces they write. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-25
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

### KI-DS-002 — The doc conventions the specialists require are repo documentation, not templates, so none of them is deployed to an adopter

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** `docs/how-to/documentation/write-reference.md` (exists, not shipped) · no
  corresponding path under `templates/` · no build phase referencing it
- **Reported by:** adopter repo DIAGraph (`roche-sandbox/dia-graph`), against pin `54356a92`

**Symptom.** Every Diataxis specialist opens with a mandatory read of
`docs/how-to/documentation/write-<genre>.md`, named as its single source of truth. KI-DS-001
covers four of those files never having been written. This is the other half, and it applies
to the one that *was*: `write-reference.md` lives in this repo's `docs/` tree, which is
package documentation about the package. It is not a template, so `build.py` never deploys it,
and an adopter's `docs/how-to/documentation/` is empty on a fresh install.

The consequence is that closing KI-DS-001 would fix this repo and change nothing for any
adopter. All five specialists would still be non-functional everywhere the package is
installed, for a different reason, with an identical symptom — the kind of gap that gets
closed twice and reported three times.

**Evidence.** `find templates -name "write-*.md"` returns nothing.
`grep -rn "how-to/documentation\|write-reference" scripts/build_phases.py scripts/build.py`
returns nothing — no phase deploys the path and no phase mentions it. Reported by DIAGraph as
"leafcutter ships no `write-*.md` templates anywhere under `templates/` (searched)", which is
accurate, and independently confirmed here.

**Fix direction.** Ship the conventions as templates —
`templates/docs/how-to/documentation/write-*.md`, deployed **write-if-absent**. That posture
already exists in the build: `build_vision` materialises `docs/vision.md` from
`templates/vision/VISION.template.md` and always passes `force=False`, so a human-curated file
is never clobbered. The conventions want exactly that contract — working defaults on install,
freely editable, never overwritten by a later build.

Weaker alternatives, in descending order: have `/onboard` scaffold them (helps new installs
only, and leaves every existing adopter where they are); or, at minimum, have `package-audit`
report the specialists as non-functional when their convention file is missing, so the gap is
visible before someone dispatches an agent that cannot run.

Note that the fix lands in the **build pipeline** while the defect presents in the
documentation system — the two registers meet here, and a fix filed under only one of them
will look complete from that side.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2, in its never-deployed form: the
package's own tree has the file, so every check run inside the package passes, and no check
runs anywhere else.

