---
title: "Known issues — changelog"
description: "Open, observed defects in the changelog component: emit_entry.py's payload validation and file emission, the changelogs/ corpus it writes, and the gates that are supposed to check an entry before it reaches main. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-26
last_updated: 2026-08-26
components:
  - changelog
related_docs:
  - docs/architecture/components/changelog.md
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/build-pipeline.md
---

# Known issues — changelog

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-CL-NNN` section using the next free number.
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

### KI-CL-001 — Nothing validates the shape of a changelog entry: CI checks only that a file exists, no pre-commit hook looks at one, and the emitter's own output is an empty body

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `scripts/changelog/emit_entry.py:361` (the emitted body);
  `.github/workflows/ci.yml:268-295` (the `changelog-presence` job);
  `scripts/release/check_changelog_presence.py` (`_has_added_changelog`);
  `.pre-commit-config.yaml` (no changelog hook of any kind)

**Symptom.** A changelog entry can reach `main` with a well-formed frontmatter block and a
completely empty body, and every gate passes.

**What each layer actually checks.** Three layers look plausible and only one of them reads an
entry at all:

- **CI `changelog-presence` (BLOCKING).** Runs
  `check_changelog_presence.py --base origin/<base_ref>`, whose whole job is
  `_has_added_changelog` — was a file **added** under `changelogs/`. It never opens it. A
  one-byte file passes.
- **Pre-commit.** Nothing. A grep for `changelog` across `.pre-commit-config.yaml` returns no
  hook. The only mention anywhere in commit-guardian config is `"^changelogs/"` in
  `commit_scope.hook_artefact_patterns` — an **exclusion** that tells the warn-only scope guard
  to ignore changelog files.
- **`emit_entry.py` (write time only).** This is the one real check, and it is good as far as
  it goes: `validate_payload` enforces `REQUIRED_FIELDS` (`title`, `date`, `time`, `type`,
  `components`, `summary`, `description`) and raises `ValueError` on several more conditions.
  But it validates the **payload**, not the file, and only when the tool is used. A
  hand-written entry never meets it.

**The body is empty by construction.** `emit_entry.py:361` writes
`content = frontmatter + "\n## Entry\n"` — the tool's documented output is frontmatter plus a
bare `## Entry` heading as a placeholder. Filling it in is a convention nothing enforces. So the
default artefact of the sanctioned path is precisely the artefact no gate rejects.

**Evidence.** The changelog entry in the `docs/ki-epic-drive-findings` work carries a bare
`## Entry` body, with the whole narrative compressed into the one-line YAML `description` field
— unlike its same-day siblings, which have real bodies. It passed the blocking CI gate, because
that gate only counted the file.

**Why medium rather than low.** The changelog is not decoration here: `release.yml` computes the
next SemVer from these entries, and a production tag is cut **only** when a `changelogs/` entry
exists since the last tag. So the file is load-bearing for versioning while its contents are
unchecked. The failure is also self-concealing in the usual way — an empty body renders as a
heading with nothing under it, which reads as a formatting quirk rather than a missing record,
and the information it should have carried is gone by the time anyone reads the release notes.

**Fix direction.** A format check is cheap and belongs at both layers, but the ordering matters:

1. **Pre-commit hook first**, over staged `changelogs/*.md` only. Assert the frontmatter parses,
   carries every `REQUIRED_FIELDS` key, and — the part that catches this — that the body below
   `## Entry` is non-empty after stripping whitespace. Local, fast, fixable in the moment.
2. **Then widen the CI gate** from presence to presence-and-shape, reusing the same checker so
   the two cannot drift. Worth doing even with the hook in place, since worktrees routinely run
   with hooks unestablished (see the pre-drive checklist in `CLAUDE.md`) and a silently-skipped
   hook is exactly how this class of gap survives.

One caution for whoever builds it: do **not** implement the body check by reusing
`validate_payload`. That function reads a payload dict, not a file, so pointing it at
`changelogs/*.md` would require re-deriving the payload from the frontmatter — at which point
the body, the only thing actually unchecked today, is still not being read. The new check must
open the file.

Consider also making `emit_entry.py` stop writing a bare `## Entry`: either require body text in
the payload, or write a visible `<!-- TODO: fill in -->` marker the new hook rejects, so an
unfinished entry fails loudly instead of looking finished.

**Cross-component note.** The defect is filed here because the changelog component owns entry
emission and the `changelogs/` corpus, and because the root cause — the emitter's own empty-body
output — is its code. But the two missing gates live elsewhere: the pre-commit hook would be a
`commit_guardian` artefact and the widened check a CI job alongside `release_manager`'s. Whoever
fixes it will touch all three.

**Pattern:** three gates that appear to cover a surface, where one is an exclusion, one checks
existence, and the only real validator runs before the artefact exists.
