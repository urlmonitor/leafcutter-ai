---
title: "KI-BO-20260930-fast-lane-ship-is-649-lines-over-and-cannot-grow — fast-lane-ship.js stands at 1649 counted lines against a 1000 limit, so the size ratchet refuses every commit that adds a line to the fast lane, and the usual remedy is blocked by the workflow bundling rule"
description: "high — the ratchet refuses ANY growth on an over-limit file, so every change to the fast lane that is not a pure shrink needs a documented skip. 'Extract, don't compress' is the standing answer, but workflow scripts must be self-contained bundles, so the extraction needs its own design rather than a helper module."
type: reference
category: reference
status: active
created: '2026-09-30'
last_updated: '2026-09-30'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-20260930-fast-lane-ship-is-649-lines-over-and-cannot-grow — fast-lane-ship.js stands at 1649 counted lines against a 1000 limit, so the size ratchet refuses every commit that adds a line to the fast lane

> Index: [build-orchestration.md](../../build-orchestration.md).

- **Severity:** high. Not a runtime defect — nothing misbehaves. It is a standing tax on the fast lane: any change that is not a pure shrink is refused at commit time and needs a `SKIP=check-file-size` with a written justification. That makes the skip routine, which is the part that matters, because a gate routinely skipped stops being read.
- **Status:** open — no AC. Deferred deliberately (user decision, 2026-09-30) to a session of its own rather than bundled into an unrelated change.
- **Occurrences:** every non-shrinking commit to the file. Most recently `BO-2400a-1-v`, which grew it 1649 → 1673 and was committed with an authorised skip.
- **First seen:** 2026-09-30 (as a recorded entry; the file has been over the limit for far longer) · **Last seen:** 2026-09-30
- **Where:** `templates/workflows-js/fast-lane-ship.js`, measured by `check-file-size` (`GE-127a-1` crossing refusal + `GE-127b-1` ratchet).

## The measurement

```
❌ FILE GREW WHILE ALREADY OVER ITS LIMIT:
   templates/workflows-js/fast-lane-ship.js
   Previous length: 1649 lines
   New length: 1673 lines
   Limit: 1000 lines
```

The measure "discards content inside triple-quoted strings and block comments; counts
every remaining line". For this file that means the JSDoc narrative — which is
substantial and is the file's established place for rationale — is **free**. The 1649 is
executable code. So the usual first move, "move the prose out of the way", has already
been taken and cannot be taken again.

## Why the standing remedy does not directly apply

`CLAUDE.md` and the gate's own output both say *extract, don't compress*, and that is
the right instinct: 1649 lines of control flow in one file is the actual problem, not
the number.

The complication is that workflow scripts are **self-contained bundles**. A shared
helper imported by a workflow has broken isolation tests before, and the engine gives
workflow bodies no module system to rely on. So "move these functions into
`_fast_lane_helpers.js`" is not a free refactor here — it needs a design decision about
how a workflow may be composed at all, which is why this is filed rather than fixed in
passing.

## What was measured, and what it rules out

During `BO-2400a-1-v` the reclaimable slack was measured rather than guessed:

- The added `CLAIM_RUNNER_SCHEMA` object is ~15 lines of declarative documentation with
  no enforcement (no `required`, no `additionalProperties`). Reducing it to a bare
  `{ type: "object" }` saves about 14.
- `interpretClaimRunnerReply` is ~13 lines and is the fix itself.

So even deleting the schema's documentation value entirely still leaves growth. Net-zero
is not reachable by trimming an individual change; only a structural split moves the
number.

## Suggested fix

1. Decide how a workflow script may be decomposed given the bundling rule — whether the
   build inlines a helper at deploy time, or the engine gains an import mechanism, or
   the lane is split into more than one workflow with an explicit hand-off. This is the
   real decision and it belongs in an ADR, not in a refactor commit.
2. Only then split. A mechanical extraction that ignores step 1 will either break
   isolation tests or produce a deployed artifact that cannot resolve its own helper —
   the deployed-layout no-op shape this register already documents elsewhere.
3. Until then, every skip on this file should say what grew and by how much, so the
   pattern stays visible instead of becoming background noise.

**Pattern:** a gate that is correct, naming debt that predates the change in front of
it, where the sanctioned remedy is blocked by a second constraint from a different
layer — so the honest outcome is a recorded skip and a separate piece of work, not a
quiet absorption.
