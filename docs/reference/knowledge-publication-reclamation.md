---
title: "Reference: Knowledge Publication Reclamation"
description: "Lookup for how a successful knowledge publication reclaims superseded generations: entry points, ordering, result keys, retained reasons, guards including the pin rule, and failure results."
type: reference
status: active
created: 2026-10-16
last_updated: 2026-10-16
components:
  - knowledge_management
related_docs:
  - docs/reference/knowledge-retention-bound.md
  - docs/reference/knowledge-retention-evaluation-details.md
  - docs/acceptance-criteria/knowledge-management/KM-400-trustworthy-project-knowledge/KM-400f-2.yaml
---

# Knowledge Publication Reclamation

> **Parent document:** [Knowledge Retention Bound](knowledge-retention-bound.md)

Defined in `knowledge/adapters/retention/reclaim.py` (AC `KM-400f-2`), invoked by `publish` in `knowledge/adapters/neo4j_projection.py`. The policy is not recomputed: `reclaim_superseded` calls `evaluate_retention` and acts on its verdicts.

```python
async reclaim_superseded(db: Neo4jBackend, repository_id: str, bound: RetentionBound) -> dict
```

---

## Entry points

| Surface | Signature or flag | Behaviour |
|---|---|---|
| `publish` | `publish(db, snapshot, expected_generation, retention_bound=None)` | Reclaims only when `retention_bound` is given and the active pointer switched. |
| `Neo4jBackend.publish` | `publish(snapshot, expected_generation=None, retention_bound=None)` | Forwards `retention_bound`. |
| `sync` | `sync(root, repository_id, revision, backend, surfaces=None, retention_bound=None)` in `knowledge/cli_sync.py` | Adds `reclamation` to the result. |
| `sync` command | `--retention-max-generations`, `--retention-min-age-seconds` | Both integers, declared together; no built-in value. Neither given: no reclamation. Only one given: `ValueError` before any network access. |

The `source` of the bound built by `sync` is `command line (--retention-max-generations, --retention-min-age-seconds)`. Without a bound, the publication reclaims nothing and `reclamation` reports an explicit zero with `assessment_status` `not_attempted`.

---

## Publication ordering

| Step | Effect |
|---|---|
| 1 | `db.publication_reclamation` is set to the explicit-zero report before anything is built. |
| 2 | The generation is built and its counts checked; failure here raises without reclaiming. |
| 3 | `switch_active` compare-and-swaps the pointer. A refused swap returns `False` (status `stale`). |
| 4 | Only when step 3 returned `True` and a bound was given, `reclaim_superseded` runs and replaces `db.publication_reclamation`. |

The new active generation and the generation it superseded are not reclaimed: the active generation has verdict `active_generation` and the superseded one falls inside the count bound.

---

## Reclamation result

Stored as `Neo4jBackend.publication_reclamation`; returned as `reclamation` by `sync`.

| Key | Type | Description |
|---|---|---|
| `reclaimed` | integer | Count of generations reclaimed. Always an explicit integer; `0` is stated, never omitted. |
| `retained` | integer or string | Count of generations retained. `"undetermined"` when the assessment is `could_not_assess`. |
| `reclaimed_generations` | list of strings | `generation_id` of each reclaimed generation. |
| `retained_generations` | list of objects | One `{"generation_id", "reason"}` per retained generation. |
| `assessment_status` | string | `assessed`, `partial`, `could_not_assess`, or `not_attempted` (no bound declared, or publication did not switch). |

Scope: both counts cover the one repository named in the publication. Generations of another repository in the same database are neither counted nor touched.

---

## Retained reasons

`retained_generations[].reason` is the verdict `reason` from the [reason vocabulary](knowledge-retention-bound.md#reason-vocabulary), or one of the values below when reclamation declined a generation the verdict called reclaimable.

| `reason` | Condition |
|---|---|
| `pin_state_unknown` | `pinned_until` is not a number (and not absent), the age is undetermined, or the generation record could not be re-read. |
| `continuation_may_be_live` | `pinned_until` is absent and the generation is not older than `CONTINUATION_LIFETIME_SECONDS`. |
| `pinned_continuation_unexpired` | `pinned_until` is a number later than now (the guard repeats the verdict's check). |
| `publication_in_progress` | The generation's `publication_status` is `building` or `validated`. |
| `reclaim_refused` | A delete was refused by the store; the Snapshot record is left for a later pass. |

---

## Reclamation guards

| Guard | Rule |
|---|---|
| Assessment first | Reclaims only when `assessment.status` is `assessed` and `reclaimable` is a list. Otherwise nothing is reclaimed and the report states `reclaimed` as `0`. `reclaimable` is the string `"undetermined"` in a could-not-assess report and is never iterated. |
| Pin rule | A numeric `pinned_until` in the future keeps the generation; in the past, it may be reclaimed. An absent one (the real-store case) allows reclaiming only when `age_seconds` exceeds `CONTINUATION_LIFETIME_SECONDS` (3600, `knowledge/cursors.py`), measured from `retired_at` else `created_at`. That constant is the one `knowledge/disclosure.py` uses for every continuation's expiry (kept from the first issue), so no continuation outlives it. Any other value declines as `pin_state_unknown`. |
| Workflow bound | `.github/workflows/knowledge-sync.yml` declares `KNOWLEDGE_RETENTION_MAX_GENERATIONS=3` and `KNOWLEDGE_RETENTION_MIN_AGE_SECONDS=7200` (2 h, above the lifetime; a test fails if the lifetime ever exceeds it) and passes them as the two flags. At about 2 merges an hour that holds roughly 7-8 generations (~200k relationships), under the Aura Free 400k cap. |
| Unfinished publication | `building` and `validated` generations are never reclaimed. |
| Own key | Each generation is deleted by `scope_key(repository_id, generation_id)`, never by status. Relationships and nodes are deleted first, the Snapshot record last, then the vector indexes the record names are dropped. A failed index drop is logged, not raised. |
| Re-read | Generation records are re-read through `retention_facts` immediately before deleting; an unreadable store reports `could_not_assess` with zero reclaimed. |

A backend refusal or unexpected stored type after the pointer switched is logged at WARNING and reported (`could_not_assess`, or `reclaim_refused` per generation); the publication stays successful.

A reclaimed generation whose continuation is later resumed is answered by `knowledge.retrieval_steps.load_generation` with the warning `pinned generation expired`, not the `no published generation` warning of a missing-data result.

---

## Failure and stale results

| Situation | `db.publication_reclamation` | Notes |
|---|---|---|
| Publication fails before the pointer switches | `reclaimed` `0`, `assessment_status` `not_attempted` | The previous generation stays active; no generation of any repository is reclaimed. |
| Pointer swap refused (`stale`) | `reclaimed` `0`, `assessment_status` `not_attempted` | `sync` returns `status` `stale`. |
| Every generation inside the bound | `reclaimed` `0`, assessed | Zero is reported explicitly. |

The failure message of a build failure appends the reclaimed figure after the removal statement: `; 0 generations reclaimed` when the failed generation was removed, `; no generations reclaimed` when its removal was refused. The refused-removal wording avoids a bare digit so the undetermined figures in the removal statement stay unambiguous (AC `KM-400b-5-ii`).

---

## See Also

- [Knowledge Retention Bound](knowledge-retention-bound.md) - Bound settings, the evaluation, the reason vocabulary and failed publication removal.
- [Knowledge Retention Evaluation Details](knowledge-retention-evaluation-details.md) - Active generation, reclaimable bases, reconciliation and assessment outcome.
- [Knowledge Publication Capacity Headroom](knowledge-publication-capacity.md) - The gate that runs before the first write; a refusal reclaims nothing.
