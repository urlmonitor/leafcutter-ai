---
title: "Reference: Shared Block Install Failures"
description: "Lookup for route authors: every shared-block install failure with its exact message and fix."
type: reference
status: active
created: 2026-10-23
last_updated: 2026-10-23
components:
  - build_orchestration
  - documentation_system
related_docs:
  - docs/reference/shared-blocks.md
  - docs/reference/shared-commit-step.md
  - docs/how-to/add-a-shared-workflow-block.md
  - docs/architecture/adrs/ADR-030-dual-engine-workflow-support.md
  - docs/acceptance-criteria/build-orchestration/BO-4500-fix-once-every-route/BO-4500b.yaml
  - docs/acceptance-criteria/build-orchestration/BO-4500-fix-once-every-route/BO-4500b-4.yaml
---

# Install Failures

Lets the author of a workflow route look up what each shared-block install failure prints and how to fix it. The marker rules these failures refer to are in [Shared Blocks: Marker Convention](shared-blocks.md#marker-convention); the post-install drift check is in [Shared Blocks: Identity Check](shared-blocks.md#identity-check).

---

## Overview

The install validates every route template and every block source in one pass and collects every problem before writing any route. Each problem is printed to standard error as `[ERROR] shared blocks: <message>`, followed by a raised error whose text opens with this head line and lists every message:

```text
N shared-block problem(s) found; no workflow route was installed
```

Messages are quoted from the real validation run against failing fixtures. Route paths are relative to the package root and `<line>` is the 1-based line of the start marker. One cause can print more than one message (noted per failure).

---

### Unknown block name

<a id="unknown-block-name"></a>

A route holds an empty marker pair whose `NAME` has no `_shared/<name lowercased>.js` source.

```text
templates/workflows-js/route-a.js:1: unknown block ZETA-ANSWER; known blocks: ALPHA-ANSWER
```

`known blocks` lists the names of the sources found, sorted. Fix: correct the name in the route to a listed block, or add the source file for the new block.

### Empty source

<a id="empty-source"></a>

A source file in `_shared/` holds nothing but spaces, tabs or newlines.

```text
ALPHA-ANSWER: the source _shared/alpha-answer.js is empty; needed by templates/workflows-js/route-a.js
```

`needed by` lists the routes that mark the block, or `(no route yet)`. Fix: write the block into the source, or delete the source and the markers that use it.

### Unused source

<a id="unused-source"></a>

A source exists, no route marks a place for it, and it is not declared awaiting adoption.

```text
ALPHA-ANSWER: a source exists but no route uses it; mark a place for it in a route, or declare it awaiting adoption in _shared/awaiting-adoption.json
```

Fix: add an empty marker pair for the block to a route, or add the block name to `_shared/awaiting-adoption.json` with the records that will adopt it. This message also accompanies an unknown-name, unpaired-start and unpaired-end failure whenever the misspelt or broken marker was the only use of the block.

### Stale awaiting-adoption declaration

<a id="stale-awaiting-adoption-declaration"></a>

`_shared/awaiting-adoption.json` names a block that a route now uses.

```text
ALPHA-ANSWER: the awaiting-adoption declaration is stale because templates/workflows-js/route-a.js uses the block; remove it from _shared/awaiting-adoption.json
```

Fix: remove the block's key from the declaration. A declared block with no source prints `<NAME>: declared awaiting adoption in _shared/awaiting-adoption.json but has no source`; a malformed file prints `must hold one object mapping a block name to a list of adopting record ids`.

### Text between markers

<a id="text-between-markers"></a>

A route template's marker pair holds text, or holds only blank lines.

```text
templates/workflows-js/route-a.js:1: the ALPHA-ANSWER marker pair holds text; the marker pair in a route template must be empty (the install fills it from _shared/alpha-answer.js)
```

```text
templates/workflows-js/route-a.js:1: the ALPHA-ANSWER marker pair holds only whitespace; the marker pair in a route template must be empty (the install fills it from _shared/alpha-answer.js)
```

Fix: delete everything between the two marker lines. A change belongs in the source file.

### Nested blocks

<a id="nested-blocks"></a>

A start marker appears between another block's start and end markers.

```text
templates/workflows-js/route-a.js:2: BETA-ANSWER (start marker line 2) is marked inside ALPHA-ANSWER (start marker line 1); marker pairs must not nest
```

The outer pair also prints the [text between markers](#text-between-markers) message, because the inner markers sit between its markers. Fix: move the inner pair outside the outer pair.

### Overlapping blocks

<a id="overlapping-blocks"></a>

Two blocks open and close in crossed order (`A-START`, `B-START`, `A-END`, `B-END`).

```text
templates/workflows-js/route-a.js:2: ALPHA-ANSWER (start marker line 1) and BETA-ANSWER (start marker line 2) overlap; close BETA-ANSWER before ALPHA-ANSWER
```

Each pair also prints the [text between markers](#text-between-markers) message. Fix: end the inner block before the outer block ends, then put the pairs side by side.

### Unpaired or mismatched markers

<a id="unpaired-or-mismatched-markers"></a>

A start marker has no end marker of the same name after it, or an end marker has no start marker of the same name before it. A start and end carrying different names (`ALPHA-ANSWER-START` closed by `BETA-ANSWER-END`) print one message of each kind, one per name.

```text
templates/workflows-js/route-a.js:1: ALPHA-ANSWER-START has no matching ALPHA-ANSWER-END after it; add the end marker
```

```text
templates/workflows-js/route-a.js:2: ALPHA-ANSWER-END has no matching ALPHA-ANSWER-START before it; add the start marker or remove this end marker
```

Fix: add the missing marker with the same `NAME`, or remove the stray one. The [unused source](#unused-source) message can follow when the broken pair was a block's only use.

### Unresolvable config placeholder

<a id="unresolved-config-placeholder"></a>

A block source holds a `{{config.<key>}}` placeholder that neither the build configuration nor `config/commit_step.json` supplies.

```text
templates/workflows-js/_shared/alpha-answer.js:1: placeholder {{config.no_such_key}} cannot be resolved; set it in skills_config.json or remove it
```

Fix: set the key in `skills_config.json`, or remove the placeholder. When `config/commit_step.json` cannot be read, or its `max_transient_retries`, `answer_version` or `reason_codes` is missing or malformed, the message is `<path>: the commit step values it needs cannot be loaded: <cause>`.

### Undeclared hand-filled pair

<a id="undeclared-hand-filled-pair"></a>

A route holds a marker pair with text and no `_shared` source exists for the name, and the name is not in `_shared/hand-kept.json`. An empty pair with no source prints the [unknown block name](#unknown-block-name) message instead.

```text
templates/workflows-js/route-a.js:1: unknown block HAND-X; known blocks: ALPHA-ANSWER; or declare it hand-kept in _shared/hand-kept.json
```

Fix: add the name to `_shared/hand-kept.json` with a reason if the copy is deliberate, or move the text into a new `_shared` source and empty the pair.

---

## See Also

- [Shared Blocks](shared-blocks.md) — the marker convention, the identity check and the COMMIT-ANSWER caller contract.
- [Add a Shared Workflow Block](../how-to/add-a-shared-workflow-block.md) — the task that produces these failures when done wrong.
- [ADR-030](../architecture/adrs/ADR-030-dual-engine-workflow-support.md) — workflow bodies have no `require`, so sharing happens at build time.
- `scripts/build_shared_validation.py` — the install-time validation and its messages.
