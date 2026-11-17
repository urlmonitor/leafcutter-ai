---
title: "KI-BO-20261012-documentation-expert-phase-cannot-dispatch-doc-specialists — /build-feature runs documentation-expert as a depth-1 phase agent, where it has no Agent tool, so it cannot dispatch the leaf author and the phase can never produce a doc"
description: "high — on run wf_ce79f3ce-861 (TICKET-20261012-GE-132a-1) documentation-expert returned a blocker twice: the Agent tool is not available in this phase, so reference-author and explanation-author could not be dispatched, and it may not author docs itself. documentation-verifier then failed on the missing doc and the commit phase refused. The doc was written by dispatching reference-author from the main loop."
type: reference
category: reference
status: active
created: '2026-10-12'
last_updated: '2026-10-12'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260914-autofix-re-dispatch-is-specified-at-a-depth-that-cannot-execute.md
  - docs/known-issues/build-orchestration/open-blocker-ki-bo-20260925-1309.md
  - docs/architecture/adrs/ADR-019-build-feature-inline-phase-dispatch.md
---

# KI-BO-20261012-documentation-expert-phase-cannot-dispatch-doc-specialists — the documentation-expert phase can never produce a doc

> One known issue, filed on sight during the GE-132a-1 build (PR #1155, merged as
> `08879303`). Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the original grading is the
> `**Severity:**` line below.

- **Severity:** high. The ticket cannot reach commit through the driver. The phase that owns the
  doc cannot write it, the verifier then correctly fails, and the commit phase correctly refuses.
  Nothing wrong lands, but no ticket whose contract names a documentation file can finish through
  `/build-feature` without someone writing the doc by hand.
- **Status:** open, no AC.
- **Occurrences:** 1 run, 2 blockers (2026-10-12, run `wf_ce79f3ce-861`, ticket
  `TICKET-20261012-GE-132a-1`).
- **First seen:** 2026-10-12 · **Last seen:** 2026-10-12
- **Where:** the `documentation-expert` phase dispatch in `templates/workflows-js/build-feature.js`.
  `documentation-expert` is an orchestrator: its job is to dispatch leaf authors
  (`reference-author`, `how-to-author`, `explanation-author`, `adr-author`, ...). Phase agents run
  at depth 1 (`ADR-019`), where the Agent tool is not available.

## Symptom

`documentation-expert` returned a blocker, twice:

```text
The Agent tool is not available in this phase, so reference-author and explanation-author ...
could not be dispatched, and documentation-expert may not author docs itself.
```

`documentation-verifier` then failed on the missing doc, and the commit phase refused.

## Resolution on this run

By hand. `reference-author` was dispatched from the main loop and wrote
`docs/reference/remedy-declarations.md`.

## Detection

A `documentation-expert` blocker that names the Agent tool as unavailable, followed by a
`documentation-verifier` failure that names the same doc as missing from the diff.

## Workaround

From the main loop (depth 0), dispatch the leaf author the contract needs, let it write the doc,
then re-run the ticket so `documentation-verifier` sees the doc in the diff.

## Suggested fix

- Dispatch the leaf author (`reference-author`, `how-to-author`, and so on) directly as the phase
  agent, routed by the genre the ticket's documentation contract names. The leaf authors already
  appear in `phaseOrder` at priority 10, on the same line as `documentation-expert`
  (`build-feature.js` on origin/main `b68d29679`, :434).
- Or let the depth-0 driver run the dispatch `documentation-expert` would have made, with
  `documentation-expert` returning which author to run instead of trying to run it.

**Related.** No existing entry records this documentation-expert depth limit. The nearest is
`KI-BO-20260914-autofix-re-dispatch-is-specified-at-a-depth-that-cannot-execute`: the same
depth-1 cap from `ADR-019`, there on the commit agent's re-dispatch of a coder. Its fix direction,
having the depth-0 driver make the dispatch, is the second option above.
`KI-BO-20260925-1309` is a different failure of the same phase: `documentation-expert` wrapping
its reply in one `input` string.

**Pattern:** an orchestrator agent placed in a slot that can only run leaves.
