---
title: "Known issues — feedback-collector"
description: "Open, observed defects in the feedback-collector component: submit_feedback.py's sink and config resolution, the feedback.jsonl corpus it appends to, and the sidecar fallback agents use to recover a feedback id. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-25
last_updated: 2026-08-26
components:
  - feedback_collector
related_docs:
  - docs/architecture/components/feedback-collector.md
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/supervisor-system.md
---


# Known issues — feedback-collector

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-FC-NNN` section using the next free number.
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

This file is an **index**. Each known issue is its own file under [`feedback-collector/`](feedback-collector/), named `<status>-<severity>-<ki-id>.md`, so the directory listing answers "is anything open, and how bad" without opening anything:

```
ls docs/known-issues/feedback-collector/open-blocker-*   # anything critical open?
ls docs/known-issues/feedback-collector/open-*           # everything still live
```

Severity in the **filename** is a three-level index bucket (`blocker` / `high` / `low`). The original grading is preserved verbatim on each entry's own `**Severity:**` line — the bucket never overwrites it. `critical` indexes as `blocker`; `medium` indexes as `low`.

Fixed issues move to [`feedback-collector/resolved/`](feedback-collector/resolved/) and are no longer listed as open. They are kept, not deleted.

**Open: 3** (0 blocker, 0 high, 3 low) · **Resolved: 0**

## Open

| Severity | Issue | File |
|---|---|---|
| `low` | KI-FC-001 — The sink is resolved from `__file__` while callers pass a CWD-relative override, so one drive splits its feedback across two corpora | [open-low-ki-fc-001.md](feedback-collector/open-low-ki-fc-001.md) |
| `low` | KI-FC-002 — The sidecar id-recovery fallback is keyed on whole seconds and shares one stderr file, so parallel agents can read each other's feedback id | [open-low-ki-fc-002.md](feedback-collector/open-low-ki-fc-002.md) |
| `low` | KI-FC-003 — `ac-validator` is in no category's `allowed_writers`, so it has never submitted a single feedback record | [open-low-ki-fc-003.md](feedback-collector/open-low-ki-fc-003.md) |

## Resolved

None yet.
