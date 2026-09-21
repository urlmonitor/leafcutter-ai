---
title: "KI-DS-003 — Nothing resolves the paths in `pre_flight_reads`, so an agent can require a file that has never existed"
description: "KI-DS-003 — Nothing resolves the paths in `pre_flight_reads`, so an agent can require a file that has never existed"
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

# KI-DS-003 — Nothing resolves the paths in `pre_flight_reads`, so an agent can require a file that has never existed

> One known issue, split out of `docs/known-issues/documentation-system.md` on
> 2026-09-14. Index: [documentation-system.md](../documentation-system.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

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

---
