---
title: "The four shipped descriptions of the emission record now agree, and a fifth cannot drift unnoticed"
date: "2026-08-31"
time: "13:01"
type: manual
components:
  - knowledge_system
  - infrastructure
summary: "signoff SKILL.md section 7 step 4 becomes the single normative definition of the knowledge_captured shape; the three v3 agent templates reference it instead of restating it. The parity check that enforces this derives its surface set from the agent registry rather than a hard-coded path list, so a fifth emission surface added later is discovered rather than silently divergent."
description: "INF-400b-2-ii. Four shipped surfaces each described the knowledge_captured record and disagreed: signoff/SKILL.md section 7 step 4 documented a record keyed on `ticket`, while the S9 blocks of product-owner.md, business-analyst.md and it-po.md documented `agent` + `component` and omitted `ticket` entirely. All 28 real records on disk use the v3 shape, so INF-400b-2's own 'structurally identical' clause has never held in the shipped artefacts and nothing detected it (KI-KM-010). THE FIX: section 7 step 4 is now the single normative definition and says so, carrying an explicit precedence rule -- if a template's emission block appears to disagree, the step is correct and the template is stale. Required of every producer: event, timestamp, agent, component, destination, entry_kind. Optional: `ticket`, present only when the emitting agent has a ticket path; phase agents do, the three v3 AC-authoring agents run outside any ticket and omit it, and absence is not an error. `ticket` is kept rather than dropped because phase agents genuinely have one, and that choice carries a load-bearing consumer guard stated in the same place: no consumer may key, group, count or dedupe on `ticket`, because depending on it for identity would reintroduce the _event_hash defect INF-400b-2-i exists to remove under a different field name. Conformance and any idempotency digest are defined over the required set only. The three v3 templates now carry a resolvable reference to the normative source rather than restating the field list -- restating is how they drifted apart. TESTS: six descriptors, five in unit_tests/agents/ and one in tests/knowledge/. The load-bearing one is test_a_newly_declared_emission_surface_is_discovered_not_ignored: a parity check that hard-codes today's four paths reproduces exactly the blindness being repaired, so discovery is declaration-driven -- discover_emission_surfaces() reads config/agent_registry.json for agents whose description names the v3 pipeline, and its test writes a real temporary registry with a genuine fifth entry pointing at a real temp template carrying a divergent block, passes it through the unmodified production seam, and asserts the fifth surface is found and reported. Three further anti-vacuity descriptors cover a planted divergence, an unparseable block and a missing file, each asserting failure rather than a silent skip. TDD ORDER WAS INVERTED and is recorded as such rather than presented as clean: the AC is assigned to llm-expert, whose template forbids editing .py files (the same reason the fast lane refuses this AC outright -- its roster is python-coder + test-writer only), so the implementation landed before the tests. A real red baseline was recovered by parking the production diff with `git stash push -- templates/`: 8 failed stashed, 126 passed restored, both under AC_ENFORCE_STRICT=1 because pytest_ac_enforcement otherwise downgrades AC-tagged failures to xfail and the baseline would be invisible. On the first attempt 4 of the 8 methods passed against unfixed code because they exercised only synthetic fixtures; those were rewritten to assert against the real unreconciled state first. Verified twice, once by the author and once independently. NOT IN THIS CHANGE: no `text` field (INF-700b-1 owns it and adding it here would collide); INF-400b-2's criteria untouched, its two pending amendments already recorded in its own amended_by for BA/PO; harvest_learnings.py untouched since INF-400b-2-i owns the _event_hash re-key and was blocked on this AC; and section 7 steps 2-3 still load route-learning / capture-learning, which do not exist -- that dead path belongs to INF-700b."
breaking: false
---

## Entry

Four shipped surfaces described the same record and disagreed.

| Surface | Shape |
|---|---|
| `signoff/SKILL.md` §7 step 4 | keyed on `ticket` |
| `product-owner.md`, `business-analyst.md`, `it-po.md` (S9) | `agent` + `component`, no `ticket` |
| The 28 records actually on disk | `agent` + `component`, no `ticket` |

So `INF-400b-2`'s own *"structurally identical"* clause has never held in the shipped artefacts, and nothing detected it.

### One normative source

`signoff/SKILL.md` §7 step 4 now defines the shape for the whole package, with a precedence rule: **if a template's emission block appears to disagree, the step is correct and the template is stale.**

Required: `event, timestamp, agent, component, destination, entry_kind`.
Optional: `ticket` — present only when the emitter has a ticket path.

`ticket` is kept rather than dropped, because phase agents genuinely have one. That comes with a guard stated in the same place:

> `ticket` MUST NOT be used by any consumer to key, group, count, or deduplicate `knowledge_captured` records.

Depending on it for identity would reintroduce the `_event_hash` defect `INF-400b-2-i` exists to remove, under a different field name.

### The test that matters

A parity check that hard-codes today's four paths reproduces the exact blindness being repaired — a fifth surface added later would diverge silently forever.

So `discover_emission_surfaces()` reads the agent registry instead. Its test writes a **real** temporary registry with a genuine fifth entry pointing at a real temp template carrying a divergent block, runs it through the unmodified production seam, and asserts the fifth surface is found.

### TDD order was inverted

Recorded rather than glossed. This AC belongs to `llm-expert`, which cannot edit `.py` — the same reason the fast lane refuses it outright. The implementation landed first; a red baseline was recovered by stashing the production diff.

**8 failed stashed → 126 passed restored.** On the first attempt 4 of 8 passed against unfixed code because they only touched synthetic fixtures; those were rewritten.
