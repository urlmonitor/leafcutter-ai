---
title: 'Agent Reference: test-breaker'
type: reference
status: active
created: 2026-10-14
last_updated: 2026-10-14
components:
- testing_quality
related_docs:
- docs/agents/conventions.md
- docs/agents/coding/test-writer.md
- docs/architecture/adrs/ADR-033-agent-model-tiers.md
related_code:
- templates/agents/test-breaker.md
description: 'Overview of Agent Reference: test-breaker.'
---
# Agent Reference: `test-breaker`

Visibility class: **internal** — dispatched by build routes, never by the user.
Implementing agent: `test-breaker` (Sonnet, tools: `Read` only).
Family: `coding/`. Registry category: `research`. Not a ticket phase; no sign-off duty.

## 1. When to Use

A build route (`fast-lane-ship.js`, `build-feature.js`, `build-ticket.js`, or
`ticket-supervisor`) dispatches it after the code and the tests are finished, to
prepare the named wrong versions (the `must_catch` strings) before the shared
wrong-version runner. It wrote neither the code nor the tests, which is why it is
neither `python-coder` nor `test-writer`.

## 2. Inputs

| Input | Type | Meaning |
|-------|------|---------|
| `work_key` | string | Copied into the reply as given |
| `repo_root` | absolute path | Working-tree root (the agent cannot ask git) |
| `requirement_ids` | list of string | The AC ids the wrong versions belong to |
| `wrong_versions` | list of `{name, files}` | Each `must_catch` string verbatim, with in-scope repo-relative POSIX source paths |

## 3. Outputs

Exactly one JSON value. Success:
`{work_key, entries: [{name, status: prepared|could_not_prepare, reason|null, replacements: [{path, old, new}]}], anomalies: [str]}`.
Failure: `{status: "failed", blocker_summary, anomalies}`.

The writer step (TQ-500g-1-ix, code, not an agent) validates the reply, makes the
altered copies outside the working tree, computes every diff and writes the
alterations manifest. The runner (TQ-500g-1-i) then applies each alteration.

## 4. Behaviour

- One entry per dispatched name, under that exact spelling; names are merged only when identical strings.
- A name that describes behaviour the code does not have, or is too vague, is `could_not_prepare` with a one-line reason; it is never dropped.
- `revert the fix` and `the fix undone` get no entry (noted in `anomalies`).
- Each alteration changes only what its name says; each name is applied to the code as written, never on top of another.

## 5. Constraints

- Read-only: no Write, Edit, Bash, Agent or search tools; `requires_verification: false`, `permits_shell: false`.
- Never runs tests and never says whether a test would catch a wrong version; the runs decide.
- Reply carries no diff, no altered copy and no outcome claim.

## 6. See Also

- Template: `templates/agents/test-breaker.md`
- Registry entry: `config/agent_registry.json` (id `test-breaker`; reciprocal entry in `ticket-supervisor.spawn_allowlist`)
- Card: `docs/agents/cards/test-breaker.card.md` (generated)
- AC: `TQ-500g-1-iv`; writer `TQ-500g-1-ix`
