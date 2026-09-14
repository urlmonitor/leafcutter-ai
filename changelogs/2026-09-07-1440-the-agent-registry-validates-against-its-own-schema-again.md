---
title: The agent registry validates against its own schema again
date: "2026-09-07"
time: "14:40"
type: manual
components:
  - agent_registry
summary: "71 schema errors to 0 on config/agent_registry.json, run as a pilot for the wider question of whether unset metadata fields should be forbidden. 13 of 14 forbidden keys were adopted into the schema, one was deleted as genuinely dead, and a regression that deleted load-bearing data to satisfy the schema was caught and reverted."
description: "The registry had drifted from its own schema in both directions: 14 keys present that additionalProperties forbade, and one schema field no agent has ever used. The direction of the fix was settled by a single fact — requires_verification, the field with the best track record in the repository, was among the forbidden ones. A schema that rejects the field that works is the thing that is wrong."
---

## Entry

`config/agent_registry.json` did not validate against `config/agent_registry.schema.json`: **71 errors** — 60 `additionalProperties`, 5 `type`, 3 `enum`, 2 `required`, 1 `oneOf`.

This was run deliberately as a **pilot** for a broader question — whether "no metadata field may be absent" is a good rule — on the one surface where the field list is closed, there are only 60 records, and there are no YAML block scalars to corrupt.

### The direction was settled before any work started

`requires_verification` — the field with the best track record in this repository, enforced bidirectionally by `registry_validator.py` against each template's own `tools:` line, failing `build.py`, backed by a unit test, zero defects ever — was **among the 14 keys the schema forbade**.

A schema that rejects the field that works is the thing that is wrong. So conflicts were resolved by teaching the schema, and deletion required proof the key was dead.

- **13 of 14 adopted**, each with a verified reader: `description` (`knowledge_query.py`), `category` (`registry_validator`), `components` (`check_component_vocab`), `doc_links` and `behavioral_patterns` (`generate_agent_cards`), `skills_invoked` and `knowledge_channels` (the `build_phases` self-description guard), `legacy_only` (asserted by a unit test), `requires_verification`, the three `conditional*` keys, and `owns_file_extensions_rationale` (adopted as an audit-trail companion and documented as read by nothing).
- **1 deleted, confirmed dead**: `invocation_surface` — zero readers across `scripts/`, `templates/`, `unit_tests/`, `tests/`; set by 1 of 60 agents; asserted by no test.

### A regression was caught, and it is the pilot's most useful result

Three agents had `conditional` / `conditional_field` / `conditional_field_legacy` deleted to satisfy `additionalProperties: false`. Removing `conditional: true` from `documentation-verifier` **breaks `test_bo_2200b_1.py`** (`BO-2200b-1`) — a live, mechanically-enforced test.

That is exactly the failure this pilot existed to look for: satisfying a schema by deleting data that is still load-bearing. All three were restored and adopted instead.

### The other eleven errors

`tier: "standalone"` was missing from the enum (3). `priority` was typed `integer`, but five agents use **fractional** priorities by design — 11.5, 11.7, 11.8, 11.9, the documented insert-without-renumbering pattern (5). Two `onboard` agents lacked the required `skills_used` (2). `trigger_condition` rejected the `source`/`routing` keys one agent carries (1).

### `llm_ambiguity_comment` kept

It was flagged as possibly dead because **0 of 60** agents set it. It has a real reader at `registry_validator.py:551`, a documented writer procedure in `llm-expert.md`, and `BO-510-4-i`/`ADR-007` behind it. Zero population is the *expected* steady state: it is a transient flag raised when `produces` is null and cleared once a human resolves the ambiguity. "Nobody uses it" and "nothing reads it" are different claims.

### The pilot's finding

Splitting all 21 fields by whether their value is checkable against something real gives **7** that clear the bar — `id`, `tier`, `portable`, `template_path`, `skills_used`, `produces`, `requires_verification` — and 14 that do not.

The sharper distinction is between a **general** mechanism that verifies every instance and a **named** assertion covering the two or three records someone happened to write a test for. `legacy_only` and `conditional` are only checked for specific agents by name, so a new agent setting either is unaudited. **A field earns "mandatory" only under the general form.**

No sparse optional field was mass-populated. `permits_shell` remains at 2 of 60 deliberately: its only reader gates on `=== true`, so absent and `false` already take the same branch and backfilling would write values nobody decided.
