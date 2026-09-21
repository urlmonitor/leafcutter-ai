---
title: "KI-CG-010 — `check-roadmap-schema` never validates the roadmap, and two other guardrails require content the schema forbids"
description: "KI-CG-010 — `check-roadmap-schema` never validates the roadmap, and two other guardrails require content the schema forbids"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-010 — `check-roadmap-schema` never validates the roadmap, and two other guardrails require content the schema forbids

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/scripts/commit_guardian/check_roadmap_schema.py:27` — `SCHEMA_RELATIVE = "leafcutter/config/roadmap.schema.json"`

**Symptom, part one — the hook never runs.** It resolves its schema at
`<git-root>/leafcutter/config/roadmap.schema.json`. In this repository the git root **is**
the package, so the real path is `config/roadmap.schema.json` with no `leafcutter/` segment.
The file it looks for does not exist, so the hook takes its fail-open branch and reports an
advisory skip. Every commit touching `docs/roadmap.json` has passed a check that never ran.

**Symptom, part two — this is a guardrail-versus-guardrail contradiction.** Two live rules
govern the same file and disagree about its contents, and the disagreement has survived only
because one of them never executes:

| Rule | Says about `docs/roadmap.json` |
|------|--------------------------------|
| `check-surface-components-e3` (enabled, `files: ^(config/agent_registry\.json\|config/skill_registry\.json\|docs/roadmap\.json)$`) | every phase entry **must** carry a non-empty `components` list, or the commit is blocked by name |
| `config/roadmap.schema.json` (via `check-roadmap-schema`) | a phase item declares `additionalProperties: false` over six properties — `description`, `exit_criteria`, `id`, `status`, `tickets_advancing_outcome`, `title` — so `components` is **forbidden** |

The roadmap satisfies the rule that runs and violates the rule that does not. Repair the path
in isolation and the two rules meet for the first time: the enabled hook demands the key, the
newly-live schema rejects it, and `docs/roadmap.json` becomes uncommittable in both
directions at once. That is the substance of this entry — the dormant no-op is what has been
hiding it.

**Evidence.** Verified 2026-08-25. `ls <repo>/leafcutter/config/roadmap.schema.json` → no
such file; `config/roadmap.schema.json` exists. Validating the live roadmap against that
schema with `jsonschema` (installed — `requirements-dev.txt` pins `jsonschema>=4.0`, so the
hook takes its `jsonschema.validate` branch, not the laxer manual fallback) returns **8**
errors: one `components` rejection for each of the 7 phases, plus a top-level
`Additional properties are not allowed ('last_updated' was unexpected)` — the root object
also declares `additionalProperties: false`. So the schema is behind the file on two counts,
not one.

On the other side, `check-surface-components-e3` is registered with `"enabled": true` and its
`_comment` records the backfill that made it enforceable: *"ENABLED 2026-07-14 after all
registry entries were backfilled (agents 53/53, skills 36/36, roadmap 3/3)"*. All 7 phases
carry `components` today.

**Dropping `components` is not an available repair.** `KM-KGS-100e-3` — *"Registry-declared
items (agents, skills, roadmap) must declare a component too"* — is `work_status: done`,
`readiness: approved`, and its criteria name the roadmap explicitly as a
membership-declaring surface whose entries must be flagged and blocked when the membership is
absent. Its `implemented_by` is the enabled hook above. Removing the key would break a done,
approved AC and disconnect every phase from the knowledge graph's
`component_membership` edges, which is the whole point of that record.

**The third route, named and rejected on substance rather than on cost.** "Break a done AC"
is not by itself a reason — a done AC can be amended, and several were in the change that
recorded this entry. The reason is what the key *does*: `components` is what joins a phase to
the knowledge graph, so dropping it plus amending `KM-KGS-100e-3` to permit the absence would
leave the schema and the hook agreeing about a roadmap that no longer participates in the
graph. That trades a contradiction between two guardrails for the silent loss of the thing
both were protecting. The schema is behind the file; the file is not wrong.

This is also the same shape as `KI-BP-003` and `KI-CG-002` — a guardrail that cannot reach its
own declaring file in the self-hosted layout — and the third instance found. Unlike
`KI-CG-002`, which silently swaps its enum source for an equivalent one, this one skips the
check entirely.

**Fix direction.** **The schema must gain the key — that direction is forced.** Add
`components` (array of strings, non-empty) to the phase item's `properties`, and add
`last_updated` to the root object's, in the **same** change that repairs the path resolution.
Resolve the schema the way `KI-CG-009`'s repair does, from the running artifact's own
location rather than a hardcoded `leafcutter/` segment that assumes a consumer layout.
Sequencing matters: repairing the path first turns a dormant no-op into an immediate merge
blocker on the next unrelated roadmap edit.

Beyond the point fix, the two rules should not be able to drift apart again. Whatever declares
which registry surfaces must carry `components` (`config/paths.json` `edge_fields`, which the
enabled hook already reads) is the natural source for the schema's own answer. Note the
regression test must run with the CWD somewhere other than the layout under test, or it will
be green against both the broken and the fixed resolver.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M5 (a validator that reports
success having checked nothing) and M2 (a guardrail that cannot reach a file it depends on) —
with the aggravating twist that the dead validator is the only reason a live contradiction
between two guardrails has never been observed.

---
