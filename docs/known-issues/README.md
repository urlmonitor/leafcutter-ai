---
title: "Reference: Known Issues Register"
description: "Index of known, reproduced defects that are not yet fixed: what each one is, how it was verified, who owns it, and what closing it requires. Use this to find whether a surprising behaviour is already a recorded defect before diagnosing it again."
type: reference
status: active
created: 2026-08-18
last_updated: 2026-08-18
components:
  - ac_store
  - build_orchestration
  - commit_guardian
related_docs:
  - docs/reference/fixture-policy.md
  - docs/architecture/adrs/ADR-012-retire-create-ticket-js.md
---

# Known Issues Register

Reproduced defects that are **not yet fixed**, recorded so the owning area can
pick them up and so the next person to hit one does not re-diagnose it from
scratch.

## What belongs here

An entry belongs here when all three hold:

1. The defect has been **reproduced**, with the command or evidence recorded.
2. It is **not fixed on `main`**.
3. Fixing it is **out of scope** for the branch that found it — usually because
   it belongs to a different area, or because it is a behaviour change to a
   contract and therefore needs an acceptance criterion authored first
   (CLAUDE.md, "New Work Goes Through ACs").

An entry does **not** belong here if it can simply be fixed. Fix it instead.

## What does not belong here

- Speculation. Every entry names the evidence that reproduces it.
- Anything already covered by an open AC or ticket — link to that instead.
- Work the finding branch could reasonably have done itself.

## Closing an entry

Delete the entry file in the same commit that fixes the defect, and reference
the entry filename in the commit message so the history connects the two. If a
fix is specified but not yet built, replace the "Owner / next step" section with
a link to the AC or ticket rather than deleting the entry.

## Open entries

| Entry | Area | Impact |
|-------|------|--------|
| [KI-001 — package-surface `it_requirements` blocks unrelated commits](KI-001-package-surface-it-requirements.md) | `ac_store` | Any commit touching one of 251 ACs is blocked by pre-existing debt it did not create |
| [KI-002 — done-proof gate defects](KI-002-done-proof-oracle-defects.md) | `build_orchestration` | ACs are reported unproven when they are covered, and three test-exempt ACs cannot be edited at all |
