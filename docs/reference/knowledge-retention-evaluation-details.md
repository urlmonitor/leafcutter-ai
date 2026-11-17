---
title: "Reference: Knowledge Retention Evaluation Details"
description: "Lookup for the detailed parts of the retention evaluation result: the active generation, reclaimable bases, entity-node reconciliation, the assessment outcome and the read-only condition."
type: reference
status: active
created: 2026-10-15
last_updated: 2026-10-15
components:
  - knowledge_management
  - decision_kernel
related_docs:
  - docs/reference/knowledge-retention-bound.md
  - docs/how-to/run-knowledge-retrieval.md
  - docs/architecture/components/knowledge-retrieval.md
  - docs/architecture/adrs/ADR-062-standalone-knowledge-retrieval.md
---

# Knowledge Retention Evaluation Details

Detail sections for the result returned by `evaluate_retention`. The function signature, the result keys, the per-generation verdict, the reason vocabulary, the refusals and the `retention` command are in [Knowledge Retention Bound](knowledge-retention-bound.md). This page holds the parts the result keys link to: active generation (AC `KM-400f-1-iii`), reclaimable bases (`KM-400f-1-iv`), entity-node reconciliation (`KM-400f-1-v`), assessment outcome and read-only condition (`KM-400f-1-vi`).

The evaluation changes nothing. It reclaims no generation, moves no active pointer and expires no continuation.

---

## Active generation

AC `KM-400f-1-iii`. The generation the active pointer references is never reclaimable, whatever its publication outcome. It is identified from the pointer alone: the `active` column of `retention_facts`, true when the repository's `active` pointer equals the generation's key. Neither `publication_status` nor creation order is used to find or protect it.

`active_generation_verdict(facts)` in `knowledge/adapters/neo4j_retention.py` computes this from the `retention_facts` rows and is the function `evaluate_retention` calls. It returns:

| Key | Type | Meaning |
|---|---|---|
| `identified` | boolean | `true` when a row is flagged active. |
| `generation_id` | string or null | The active generation; `null` when unidentified. |
| `publication_completed` | boolean or null | `true` when the active generation's `publication_status` is `ready`; `false` for any other value; `null` when unidentified. |
| `finding` | string or null | The statement reported in `findings`, or `null` when the active generation's publication completed. |

The two findings:

| Finding | When |
|---|---|
| `the active pointer references a generation whose publication did not complete` | The active generation's status is not `ready`. The verdict is unchanged: it stays `reclaimable: false`, `reason: active_generation`. |
| `no active generation could be identified` | No row is flagged active. |

When no active generation is identified, every generation is reported `reclaimable: false` with reason `active_generation_unidentified`, `reclaimable` is empty, and `active_generation` is `null`. The most recently created generation is not treated as active in place of the absent pointer, and the count, age and pin checks are not applied. This holds for a repository with no `Repository` node as well as one whose pointer is unset. If more than one row is flagged active, the first row returned is reported as the active generation.

The age basis is stated on every verdict (`age_basis`, `age_seconds`, `absent_times`; AC `KM-400f-1-ii`). A generation that was never retired is aged from `created_at`; one carrying `retired_at` is aged from it, never from its creation time. A generation carrying neither time is still reported, with `age_basis` `undetermined`, a `null` age and reason `age_undetermined`; an undetermined age never satisfies the minimum, so it is not reclaimable. It sorts after all dated generations in the count rank.

The age basis is operator-visible: an operator reading a `reclaimable` verdict can see which clock produced it. The 24-hour minimum and the count bound declared by the parent (`KM-400f-1`) are unchanged; only the measuring basis is fixed here. Pinning stays the superior constraint (`KM-400b-3`): a stated age basis never makes a generation with an unexpired continuation reclaimable. KM-400f-4's operator listing is a consumer of `age_basis`, `age_seconds` and `absent_times` and reports them rather than recomputing them.

Grounding: on the live store on 2026-10-12 every generation record was a failed publication and none was ready, so before this change the evaluation reported zero generations while the store was full.

---

## Reclaimable bases

AC `KM-400f-1-iv`. Routine retention and accumulated failed publications call for different operator responses, so each reclaimable generation names why.

| Basis | Holds when |
|---|---|
| `outside_count_bound` | The generation is outside the declared count bound. |
| `publication_failed` | The generation records a failed publication (status `failed`). |

A generation holding both lists both, whatever the input order. `reclaimable_by_basis` counts a generation under each basis it holds, so the counts may overlap and must not be read as a total; the length of `reclaimable` is the total.

Count rank is taken over generations whose publication did not fail. A failed generation never occupies a count slot; it is outside the bound when at least `generation_limit` non-failed generations are newer than it. A failed generation inside the bound is still reclaimable on the `publication_failed` basis once the age, pin and active checks pass. The `retention` command output carries the same fields.

---

## Entity-node reconciliation

AC `KM-400f-1-v`. Entity nodes tagged with a generation are reconciled against the generation records in the same evaluation, so nodes that no record accounts for are counted rather than assumed absent.

| Item | Definition |
|---|---|
| Source of counts | `entity_node_counts(db, repository_id)` in `knowledge/adapters/neo4j_retention.py`, exposed as `Neo4jBackend.entity_node_counts`. Read-only. Returns one `{"generation_key", "nodes"}` row per distinct non-null `generation_key` carried by entity nodes of the repository. |
| Reconciliation | `_reconcile_nodes` matches each row's key against `scope_key(repository_id, generation_id)` for every row of `retention_facts`, the full record set with failed publications included. |
| Attributed | A node whose key matches a record is counted in that generation's `entity_nodes`. Per-generation counts plus `unaccounted_nodes` equal the store's count of generation-tagged entity nodes. |
| Unaccounted | A node whose key matches no record. Counted in `unaccounted_nodes`, named in `unaccounted_generation_keys`. |
| Empty generation | A record with no nodes reports `entity_nodes: 0`. It is not unaccounted. |

Unaccounted nodes appear in no verdict, are never listed in `reclaimable` and are not counted in `reclaimable_by_basis`. Every generation that has a record still receives its own verdict. The figure rises and falls with the unaccounted population (400 nodes then 200 more reports 600).

When `db` has no `entity_node_counts`, the figures are the string `"undetermined"`, never a false `0`.

The figure is the only signal that reclaiming every reclaimable generation would still leave nodes behind. It is consumed by KM-400f-3 (headroom measurement) and KM-400f-4 (operator surface), which report it rather than recompute it.

Not established: the live test (`tests/knowledge_live/test_km_400f_1_v.py`) skips when Neo4j is unreachable, so the count query has not been run against a real database in this change.

---

## Assessment outcome

AC `KM-400f-1-vi`. `evaluate_retention` catches a `BackendUnavailable` refusal from each backend request and reports it instead of raising it or reading it as an empty store. The helpers are in `knowledge/adapters/retention/assessment.py`; `evaluate_retention` attaches their result as `assessment`.

| `assessment` key | Type | Description |
|---|---|---|
| `status` | string | `assessed`, `partial` or `could_not_assess`. See the table below. |
| `refusals` | list of objects | One `{"part", "message"}` per refused request, in order. `message` is the backend's own refusal text, unchanged. Empty when `status` is `assessed`. |
| `succeeded` | list of strings | Parts of the assessment that completed. Empty when `status` is `could_not_assess`. |
| `could_not_complete` | list of strings | Parts that could not be completed. Empty when `status` is `assessed`. |

| `status` | Refused request | Meaning |
|---|---|---|
| `assessed` | none | Every generation record was assessed and the entity-node counts were read. An empty `reclaimable` here means nothing is reclaimable. |
| `partial` | per-generation entity-node count (`entity_node_counts`) | The generation records were read and every record received its verdict. `entity_nodes` on each verdict, `unaccounted_nodes` and `unaccounted_generation_keys` are `"undetermined"`, never `0`. |
| `could_not_assess` | generation-record listing (`retention_facts`) | No verdict was made. The population is unknown. |

Part names used in `succeeded`, `could_not_complete` and `refusals[].part`:

| Part | Request it serves |
|---|---|
| `generation_records` | `retention_facts`, the list of generation records. |
| `entity_node_counts` | `entity_node_counts`, the count of entity nodes per generation. |

A refused generation-record listing makes the node count moot, so `could_not_complete` names `generation_records` alone.

Report shape when `status` is `could_not_assess` (`could_not_assess_report`):

| Key | Value |
|---|---|
| `assessed` | `"undetermined"` (not `0`) |
| `reclaimable` | `"undetermined"` (not `[]`) |
| `reclaimable_by_basis` | `"undetermined"` |
| `active_generation` | `"undetermined"` |
| `unaccounted_nodes`, `unaccounted_generation_keys` | `"undetermined"` |
| `generations` | `[]` |
| `findings` | `["the generation population could not be assessed; no verdict was made"]` |
| `bound` | The declared bound, unchanged. |

A consumer tells this result from "assessed every generation record and found none reclaimable" by `assessment.status`, and by `assessed` and `reclaimable` being the string `"undetermined"` rather than `0` and `[]`. KM-400f-3 (headroom verdict) and KM-400f-4 (operator surface) relay the status and must not flatten `could_not_assess` or `partial` into a clean report.

---

## Read-only condition

AC `KM-400f-1-vi`. `read_only_condition` reports a latched backend when any refusal message contains `read-only`, `readonly` or `read only` (case-insensitive).

| `read_only` key | Value |
|---|---|
| `latched` | `true` |
| `reclaim_blocked` | `true` |
| `detail` | `the backend has latched read-only and refuses changes; reclaiming space is blocked while it holds, and this is not an absence of generations` |

The `read_only` key is omitted when no refusal names a read-only latch; any other refusal is reported through `assessment` only and is not described as read-only. The latch is reported alongside `assessment`, never in place of it; only a refused request can name it, so `read_only` is never present on an `assessed` result.

Not established: the read-only latch is recognised by matching the refusal text, not by an error code. A backend that words the refusal without one of the three markers is reported as an ordinary refusal.

---

## See Also

- [Knowledge Retention Bound](knowledge-retention-bound.md) - Settings, result keys, reason vocabulary, refusals and the `retention` command.
- [Knowledge retrieval how-to](../how-to/run-knowledge-retrieval.md) - Procedures for running knowledge retrieval.
- [Artifact knowledge graph data map](artifact-knowledge-graph-data-map.md) - Node identities and generation tagging the reconciliation counts against.
- [KM-400f-1](../acceptance-criteria/knowledge-management/KM-400-trustworthy-project-knowledge/KM-400f-1.yaml) - Parent AC declaring the retention bound.
- [KM-400f-4](../acceptance-criteria/knowledge-management/KM-400-trustworthy-project-knowledge/KM-400f-4.yaml) - Operator listing and sweep; reports these figures rather than recomputing them.
- [KM-400b-3](../acceptance-criteria/knowledge-management/KM-400-trustworthy-project-knowledge/KM-400b-3.yaml) - Pinning constraint that outranks the age basis.
- `knowledge/adapters/neo4j_retention.py` - `evaluate_retention`, `retention_facts`, `active_generation_verdict`, `_reconcile_nodes`.
- `knowledge/adapters/retention/assessment.py` - Assessment and read-only helpers.
