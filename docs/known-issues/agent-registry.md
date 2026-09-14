---
title: "Known issues — agent-registry"
description: "Open, observed defects in the agent-registry component: config/agent_registry.json, its JSON Schema, and scripts/registry_validator.py — the declared contract for what each agent is and who may spawn it. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-18
components:
  - agent_registry
related_docs:
  - docs/architecture/components/agent-registry.md
  - docs/architecture/components/supervisor-spawn-topology.md
---


# Known issues — agent-registry

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-AR-NNN` section using the next free number.
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

This file is an **index**. Each known issue is its own file under [`agent-registry/`](agent-registry/), named `<status>-<severity>-<ki-id>.md`, so the directory listing answers "is anything open, and how bad" without opening anything:

```
ls docs/known-issues/agent-registry/open-blocker-*   # anything critical open?
ls docs/known-issues/agent-registry/open-*           # everything still live
```

Severity in the **filename** is a three-level index bucket (`blocker` / `high` / `low`). The original grading is preserved verbatim on each entry's own `**Severity:**` line — the bucket never overwrites it. `critical` indexes as `blocker`; `medium` indexes as `low`.

Fixed issues move to [`agent-registry/resolved/`](agent-registry/resolved/) and are no longer listed as open. They are kept, not deleted.

**Open: 3** (0 blocker, 0 high, 3 low) · **Resolved: 0**

## Open

| Severity | Issue | File |
|---|---|---|
| `low` | `agent_registry.schema.json` is inert: nothing validates the registry against it | [open-low-ki-ar-001.md](agent-registry/open-low-ki-ar-001.md) |
| `low` | `_EXTERNAL_CALLERS` is a hardcoded two-item set, so documenting a real spawn relationship fails the build | [open-low-ki-ar-002.md](agent-registry/open-low-ki-ar-002.md) |
| `low` | `skills_invoked` still declares `signoff` for two agents whose sign-off obligation was removed, and the resulting mismatch is advisory only | [open-low-ki-ar-003.md](agent-registry/open-low-ki-ar-003.md) |

## Resolved

None yet.
