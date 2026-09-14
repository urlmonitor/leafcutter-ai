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

## How this register is stored

This file is an **index**. Each known issue is its own file under [`changelog/`](changelog/), named `<status>-<severity>-<ki-id>.md`, so the directory listing answers "is anything open, and how bad" without opening anything:

```
ls docs/known-issues/changelog/open-blocker-*   # anything critical open?
ls docs/known-issues/changelog/open-*           # everything still live
```

Severity in the **filename** is a three-level index bucket (`blocker` / `high` / `low`). The original grading is preserved verbatim on each entry's own `**Severity:**` line — the bucket never overwrites it. `critical` indexes as `blocker`; `medium` indexes as `low`.

Fixed issues move to [`changelog/resolved/`](changelog/resolved/) and are no longer listed as open. They are kept, not deleted.

**Open: 2** (0 blocker, 1 high, 1 low) · **Resolved: 0**

## Open

| Severity | Issue | File |
|---|---|---|
| `high` | KI-CL-002 — No build drive can produce a changelog entry: `changelog-agent` is in neither the phase order nor any generated agents map, so every code-touching drive lands a PR that cannot merge | [open-high-ki-cl-002.md](changelog/open-high-ki-cl-002.md) |
| `low` | KI-CL-001 — Nothing validates the shape of a changelog entry: CI checks only that a file exists, no pre-commit hook looks at one, and the emitter's own output is an empty body | [open-low-ki-cl-001.md](changelog/open-low-ki-cl-001.md) |

## Resolved

None yet.
