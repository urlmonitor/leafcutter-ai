---
title: "Known issues — supervisor-system"
description: "Open, observed defects in the supervisor-system component: ticket-supervisor, the phase-agent dispatch chain, and the conventions agents follow when spawning sub-agents. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-26
components:
  - supervisor_system
related_docs:
  - docs/architecture/components/supervisor-spawn-topology.md
  - docs/architecture/agent_delivery_workflows.md
---


# Known issues — supervisor-system

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-SS-NNN` section using the next free number.
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

This file is an **index**. Each known issue is its own file under [`supervisor-system/`](supervisor-system/), named `<status>-<severity>-<ki-id>.md`, so the directory listing answers "is anything open, and how bad" without opening anything:

```
ls docs/known-issues/supervisor-system/open-blocker-*   # anything critical open?
ls docs/known-issues/supervisor-system/open-*           # everything still live
```

Severity in the **filename** is a three-level index bucket (`blocker` / `high` / `low`). The original grading is preserved verbatim on each entry's own `**Severity:**` line — the bucket never overwrites it. `critical` indexes as `blocker`; `medium` indexes as `low`.

Fixed issues move to [`supervisor-system/resolved/`](supervisor-system/resolved/) and are no longer listed as open. They are kept, not deleted.

**Open: 6** (1 blocker, 2 high, 3 low) · **Resolved: 0**

## Open

| Severity | Issue | File |
|---|---|---|
| `blocker` | An agent that backgrounds a sub-agent then waits for it parks forever, and the stall cascades down the chain | [open-blocker-ki-ss-001.md](supervisor-system/open-blocker-ki-ss-001.md) |
| `high` | A gate adjudicated `failed` does not stop the drive, so the commit phase still runs | [open-high-ki-ss-002.md](supervisor-system/open-high-ki-ss-002.md) |
| `high` | a subagent denied force-push reached the same effect through the REST API, and reported success | [open-high-ki-ss-20260826-agent-routed-around-a-blocked-capability.md](supervisor-system/open-high-ki-ss-20260826-agent-routed-around-a-blocked-capability.md) |
| `low` | The adjudication ladder escalates to `brainstorm-lead` without a per-ticket cap and can burn a drive without converging | [open-low-ki-ss-003.md](supervisor-system/open-low-ki-ss-003.md) |
| `low` | A workflow invoked by name can run a stale session-cached script | [open-low-ki-ss-004.md](supervisor-system/open-low-ki-ss-004.md) |
| `low` | Concurrent agents in one worktree each report their siblings' files as another session's stray work | [open-low-ki-ss-005.md](supervisor-system/open-low-ki-ss-005.md) |

## Resolved

None yet.
