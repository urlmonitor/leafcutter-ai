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

---

### KI-DS-003 — Nothing resolves the paths in `pre_flight_reads`, so an agent can require a file that has never existed

- **Severity:** high
- **Status:** open — the one instance found is fixed; the class is not
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/build_phases.py:1934` (`_REQUIRED_FRONTMATTER`) — validates that the
  `pre_flight_reads` **key is present**, never that any `source:` in it resolves to a file

`documentation-expert` declared a pre-flight read of `docs/README.md` and called it, in its
body, *"the single source of truth for where each genre lands in the project."* **That file
has never existed** — `git log --oneline --all -- docs/README.md` is empty, and it was
already absent from the day-one extraction tree (`11dbd26b`). The reference was inherited
from the monorepo this package was extracted from and arrived orphaned. No AC, ticket, ADR,
changelog entry or known-issue ever asked for it to be written.

**Why it survived.** Three independent gaps, none of which is about this file:

1. `build_phases.py:1934` checks the key, not the paths. Any agent in the package can declare
   a pre-flight read of a nonexistent file and pass the build.
2. `check_doc_links.py` validates `DOC_LINKS` in **Python and SQL** files only, and is
   advisory-only by design (`Exit Codes: 0 — Always`). It does not walk markdown links.
3. `readme_read_guard.py` — the load-bearing-README mechanism — has `"docs"` in its
   `SKIP_LIST`, so `docs/README.md` is explicitly outside it.

**One check does resolve doc paths, and its limit is the interesting part.**
`check-doc-frontmatter` validates every `related_docs` entry and fails on a broken one — but
it is a pre-commit hook, so it only ever sees **staged** files. A dead pointer in a file
nobody is currently editing is never looked at. Proof arrived while fixing this issue: the
moment these three agent reference docs were staged for an unrelated one-line change, the
hook immediately failed on **five** long-dead `related_docs` paths it had never had occasion
to check —

    docs/how-to/documentation/write-how-to.md          (KI-DS-001, never existed)
    docs/how-to/documentation/write-explanation.md     (KI-DS-001, never existed)
    tickets/09_done/EPIC-CodingAgents/20_documentation_expert.md
    tickets/09_done/EPIC-CodingAgents/21_how_to_author.md
    tickets/09_done/EPIC-CodingAgents/25_explanation_author.md

all five dating from 2026-05-07 and all five invisible for three and a half months. The
checking logic is not missing; its **trigger** is. A staged-files-only gate cannot find rot
in files that are not changing, which is precisely where rot accumulates. The five entries
were removed as part of the KI-DS-003 fix — note that dropping the two `write-*.md` pointers
removes a signal that those conventions *should* exist, which is why KI-DS-001 remains the
record of that gap.

**And the frontmatter contradicted the body**, which is what made it silent rather than loud:
the frontmatter said `required: false` / `condition: when present` while the body called the
read mandatory and authoritative. With no absent-file posture stated, the agent improvised
the genre mapping — producing a confidently misfiled document rather than an error. This is
the same failure shape KI-DS-001 closes with ("a mandatory read whose absent-file behaviour
is unspecified is what produced the original silent-improvisation half of this issue").

**What was fixed (2026-08-25).** All 19 live references repointed and the file retired as a
concept, not authored. The content it was supposed to hold already existed in two places, so
authoring it would have created a third source of truth for a mapping that already had two:

- **Genre mapping** → `config/doc_types.json`, whose own `_comment` calls it *"Single source
  of truth for the doc type frontmatter enum and doc-author agent routing"*, and which
  already carries `description`, `writer_agent` and `default_path` per genre, resolving
  against `config/paths.json`.
- **Navigation index** → `docs/INDEX.md`. `generate_doc_index.py:77` has
  `_ALWAYS_EXCLUDE = {"README.md", "INDEX.md"}` — the generator deliberately writes `INDEX.md`
  and treats `README.md` as a thing to exclude, so the index role was consciously assigned
  away from `README.md` already.

`documentation-expert`'s read is now `required: true` on `config/doc_types.json` with an
explicit stop-and-blocker posture, and both it and `how-to-author` carry a short note saying
the file never existed and must not be reintroduced.

**What is still open — the class, not the instance.** A validator that resolves
`pre_flight_reads[].source` for every agent template would catch this whole family at once,
and is the higher-leverage fix; it is plausibly also what would have caught KI-DS-001's five
missing conventions. Related and unfixed: there is **no link-checker for relative markdown
links under `docs/`**, which is why `docs/agents/README.md` currently carries **32 broken
links out of 38** in its `coding/` family table — that table hardcodes a `coding/` prefix for
every agent regardless of the folder its doc actually lives in (`sql-coder` is in `sql/`,
`commit` in `git/`, `business-analyst` in `ticket-creation/`), and about 8 of the targets have
no reference doc anywhere.

**Fix direction.** Extend the self-description validator in `build_phases.py` to resolve every
`pre_flight_reads[].source` that looks like a repo-relative path, and fail the build on a
miss. Treat non-path sources (`ticket_path` and friends, which are input names rather than
files) as an explicit allowlist rather than by guessing at the string shape. Separately, add a
relative-link check for markdown under `docs/` — advisory first, then required once the
existing 32 are cleared.

Put both in a **repo-wide** run, not only a staged-files hook. The `related_docs` evidence
above is the argument: the validation existed and was correct, and still let five dead paths
sit for three and a half months, because a pre-commit hook is only ever handed the files
someone happens to be touching. A once-per-build or CI sweep over the whole tree is what
turns these from checks that *could* fail into checks that *do*.

**Pattern:** `docs/reference/false-green-mechanisms.md` → a validator that checks a key exists
rather than that its contents resolve. The check ran on every build for months and could never
have failed.

