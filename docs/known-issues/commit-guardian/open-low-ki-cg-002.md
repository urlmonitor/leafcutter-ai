---
title: "KI-CG-002 — The diagram-type guard silently swaps its enum source when its declaring file is unreachable"
description: "KI-CG-002 — The diagram-type guard silently swaps its enum source when its declaring file is unreachable"
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

# KI-CG-002 — The diagram-type guard silently swaps its enum source when its declaring file is unreachable

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/scripts/commit_guardian/diagram_type_validators.py:35-55` (`_find_diagram_types_json`) and `_load_diagram_types()`

**Corrected 2026-08-25 — the original wording overstated the trigger.** This was recorded
as "the diagram-type enum silently narrows from 11 values to 8", severity `high`. That is
wrong. A single resolution failure narrows nothing. The count drops only on a **second,
independent** failure. What is real is the silent substitution, and it is `medium`. The
correction is made in place because the overstated version was merged and read.

**Symptom.** `_find_diagram_types_json()` walks ancestors of its own `__file__` looking for
`leafcutter/config/diagram_types.json` or `config/diagram_types.json`. When neither
resolves it returns `None`, and `_load_diagram_types()` falls back **without any warning**
to `DOC_FM_DIAGRAM_TYPE_VALUES`. The guard changes which file it draws its authority from
and says nothing — which is exactly the fact an operator needs in order to judge whether
to trust the verdict.

**Evidence — the fallback is not narrower.** `DOC_FM_DIAGRAM_TYPE_VALUES` is not a
hardcoded constant. `config.py:190` reads it from `commit_guardian.json` →
`doc_frontmatter.diagram_type_values`, and that key lists **all 11** values. The 8-value
list written inline at `config.py:190-192` is only the `_get()` default, reached when the
key is absent. Measured by importing the module and forcing `_find_diagram_types_json()` to
return `None`: the enum stays at 11 and is the **identical set** to
`config/diagram_types.json`'s — `agent_flow, component, container, context, data_flow,
dataflow, erd, none, sequence, state, user_flow`. Nothing that would otherwise pass is
rejected.

Narrowing needs a second, independent failure: `commit_guardian.json` present but *missing*
the `doc_frontmatter.diagram_type_values` key. Removing that one key from a copy of the hook
directory, with resolution also forced to fail, does drop the enum to 8 and does lose
`agent_flow`, `data_flow`, `user_flow`. Deleting `commit_guardian.json` outright narrows
nothing either — `config.py` raises `FileNotFoundError` at import, so the hook dies loudly.

**And the first failure does not currently occur here.** The ancestor walk resolves
`config/diagram_types.json` from both the source layout (`templates/scripts/commit_guardian/`)
and the deployed layout (`.leafcutter/scripts/commit_guardian/`), returning 11 values from
each. The 2026-07-14 rewrite that replaced the broken `parents[2]` path with the walk is what
fixed that. A resolution failure is still reachable in a consumer layout where neither
candidate exists — `KI-BP-003`'s second occurrence is that shape for the sibling `doc_types`
resolver — but even there the result is substitution, not narrowing.

**`GE-105` is genuinely satisfied, not phantom.** That AC (`work_status: done`,
`readiness: approved`) requires the canonical values to be accepted, and names the effective
enum source explicitly: *"commit_guardian.json -> doc_frontmatter.diagram_type_values, used
as the runtime fallback when diagram_types.json is not deployed"*. Its covering test
(`test_commit_guardian_imports.py::TestGE105CanonicalEnumValuesAccepted`) asserts acceptance
against the module, and the config carries the values. The original entry implied a live
rejection of canonical values that GE-105 had left unfixed; there is none.

**Fix direction.** Two things, neither of them the value count. First, make the substitution
observable: log at WARNING, naming the candidates searched, when the walk fails and the
config fallback is taken, so a fallback verdict is never indistinguishable from a normal one.
`GE-118c` removed exactly this silence from the sibling `doc_type_validators.py` on
2026-08-18, on the stated grounds that "a guard that quietly answers a different question
than the one it was configured with is enforcing a rule nobody wrote." (That requirement was
tracked as `GE-120` until 2026-08-18, when the id was found to collide with an unrelated
goal-level tree and the record was renumbered to `GE-118c` under `GE-118`.)
`diagram_type_validators.py` is the file GE-118c copied its ancestor-walk pattern *from*, and
it still carries the silence that was removed. Second, the two lists live in two files, agree
today, and nothing checks that they still will — derive the config key from
`diagram_types.json` at build time, or assert parity between them. A divergence would be
invisible for precisely the reason this entry exists.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2 (a guardrail that cannot reach a
file it depends on), in its benign-today form — the substitution is unobservable, so on the
day the two sources disagree, nothing will say so.

---
