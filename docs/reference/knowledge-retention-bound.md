---
title: "Reference: Knowledge Retention Bound"
description: "Lookup for the declared generation retention bound of the knowledge graph: its two settings, the resolved bound, the read-only evaluation report, the reason vocabulary, the refusals and the retention command."
type: reference
status: active
created: 2026-10-12
last_updated: 2026-10-14
components:
  - knowledge_management
  - decision_kernel
related_docs:
  - docs/how-to/run-knowledge-retrieval.md
  - docs/reference/knowledge-retrieval-answers.md
  - docs/architecture/components/knowledge-retrieval.md
  - docs/architecture/adrs/ADR-062-standalone-knowledge-retrieval.md
---

# Knowledge Retention Bound

Names, types, result shapes, reason values and refusal messages for the declared retention bound that decides which retained knowledge-graph generations may be reclaimed (AC `KM-400f-1`).

The evaluation changes nothing. It reclaims no generation, moves no active pointer and expires no continuation. Reclamation is a separate criterion, `KM-400f-2`, that is not built.

---

## Bound settings

Two settings in the `knowledge` section of the kernel configuration. Both are required together. Neither has a fallback value; `null` means undeclared.

| Field | Type | Required | Default | Description |
|---|---|---|---|---|
| `retention_max_generations` | integer or null | Yes, with `retention_min_age_seconds` | `null` | Count limit. Must be at least 1 once declared. |
| `retention_min_age_seconds` | integer or null | Yes, with `retention_max_generations` | `null` | Minimum seconds since retirement. Must be 0 or greater once declared; `0` is a declared value. |

Declared in:

| Surface | Location |
|---|---|
| Python model | `KnowledgeConfig` in `knowledge/config.py` |
| Defaults | `knowledge` section of `config/kernel_config.default.json` (both `null`) |
| Schema | `KnowledgeBindingConfig` in `config/kernel_config.schema.json` (both properties listed in `required`, type integer or null) |
| Field descriptions | `_DESCRIPTIONS` in `integrations/knowledge_config.py` |

Not established: no code in this change reads the two settings from a kernel configuration file and passes them to `resolve_retention_bound`. The only caller confirmed is the `retention` command, which builds the configuration from command-line flags.

Not established: **the pin source is not populated, so `pinned_continuation_unexpired` never fires against a real store.** The verdict reads `pinned_until` from the `Snapshot` node, and nothing in `knowledge/` writes that property — real continuation pinning lives in the retrieval path (`knowledge/retrieval_steps.py`), not on the node. Against a live database every generation therefore reports a null pin, so one holding an unexpired continuation is reported `reclaimable: true`. The unit tests prove the precedence only against a hand-supplied `pinned_until` fixture.

This is harmless while the evaluation only reports. It is **not** harmless to a caller that deletes what the evaluation calls reclaimable: doing so would reclaim a generation a retrieval is still pinned to, which is the guarantee `KM-400b-3` makes. A reclaiming caller must either read a populated pin source or treat an absent one as "pin state unknown" and decline to reclaim — never as "not pinned".

---

## resolve_retention_bound

```python
resolve_retention_bound(config: KnowledgeConfig, *, source: str) -> RetentionBound
```

Defined in `knowledge/config.py`. Performs no network access.

| Parameter | Type | Description |
|---|---|---|
| `config` | `KnowledgeConfig` | Carries the two settings. |
| `source` | `str` | Keyword-only. Inspectable name of where the bound was read from; copied unchanged to the result. |

### Resolved bound (`RetentionBound`)

| Field | Type | Taken from |
|---|---|---|
| `generation_limit` | integer | `retention_max_generations` |
| `minimum_age_seconds` | integer | `retention_min_age_seconds` |
| `source` | string | The `source` argument. |

The resolved bound uses different field names from the configuration settings.

---

## evaluate_retention

```python
async evaluate_retention(db: Neo4jBackend, repository_id: str, bound: object, now: float | None = None) -> dict
```

Defined in `knowledge/adapters/neo4j_projection.py`. Read-only. `now` is an optional clock value (seconds); the current time is used when omitted.

| Parameter | Type | Description |
|---|---|---|
| `db` | `Neo4jBackend` | Scoped adapter. |
| `repository_id` | `str` | Repository namespace for all reads. |
| `bound` | `RetentionBound` | Must be a `RetentionBound`; any other value is refused before anything is read. |
| `now` | `float` or `None` | Clock for the age and pin-expiry checks. |

### Evaluation result

| Key | Type | Description |
|---|---|---|
| `bound` | object | The reported bound: `generation_limit`, `minimum_age_seconds`, `source`. |
| `assessed` | integer | Count of generation records evaluated. Equals the length of `generations`. |
| `generations` | list of verdicts | One entry per generation record, whatever its publication outcome, newest first by `created_at`, ties by `generation_id` ascending. |
| `reclaimable` | list of strings | `generation_id` of each verdict whose `reclaimable` is `true`. |

### Per-generation verdict

| Key | Type | Description |
|---|---|---|
| `generation_id` | string | Generation identifier. |
| `reclaimable` | boolean | Whether the bound permits reclaiming the generation. |
| `reason` | string | One value from the reason vocabulary. |
| `age_basis` | string | The recorded time the age was measured from: `retired_at` when the generation carries a retirement time, else `created_at`, else `undetermined`. Every generation never retired is aged from `created_at`, the same basis for all of them. |
| `age_seconds` | number or null | Age in seconds measured from `age_basis`; `null` when `age_basis` is `undetermined`. |
| `absent_times` | list of strings | Empty when the age is determined. `["retired_at", "created_at"]` when the generation carries neither time. |

### Generation facts read

`retention_facts` (`knowledge/adapters/neo4j_projection.py`, exposed as `Neo4jBackend.retention_facts`) returns one row per `Snapshot` record for the repository. It applies no status filter: every generation is assessed, whatever its publication outcome.

| Column | Meaning |
|---|---|
| `generation_id` | Generation identifier. |
| `publication_status` | The Snapshot's `status`: `ready`, `validated`, `building` or `failed`. |
| `active` | `true` when the generation is the repository's active one. |
| `created_at` | Creation time; orders the count rank. |
| `retired_at` | Retirement time; `created_at` is used when it is null. A failed generation has no `retired_at`, so it is aged from `created_at`, and the verdict says so. |
| `pinned_until` | Expiry of a pinned continuation; null when none is pinned. |

The active-generation verdict keeps precedence (reason order 1), so an active generation whose publication never completed is still reported not reclaimable.

The age basis is stated on every verdict (`age_basis`, `age_seconds`, `absent_times`; AC `KM-400f-1-ii`). A generation that was never retired is aged from `created_at`; one carrying `retired_at` is aged from it, never from its creation time. A generation carrying neither time is still reported, with `age_basis` `undetermined`, a `null` age and reason `age_undetermined`; an undetermined age never satisfies the minimum, so it is not reclaimable. It sorts after all dated generations in the count rank.

The age basis is operator-visible: an operator reading a `reclaimable` verdict can see which clock produced it. The 24-hour minimum and the count bound declared by the parent (`KM-400f-1`) are unchanged; only the measuring basis is fixed here. Pinning stays the superior constraint (`KM-400b-3`): a stated age basis never makes a generation with an unexpired continuation reclaimable. KM-400f-4's operator listing is a consumer of `age_basis`, `age_seconds` and `absent_times` and reports them rather than recomputing them.

Grounding: on the live store on 2026-10-12 every generation record was a failed publication and none was ready, so before this change the evaluation reported zero generations while the store was full.

---

## Reason vocabulary

`_verdict` in `knowledge/adapters/neo4j_projection.py` applies the checks in the order below and returns the first that matches.

| Order | `reason` | `reclaimable` | Condition |
|---|---|---|---|
| 1 | `active_generation` | `false` | The generation is active. |
| 2 | `inside_count_bound` | `false` | Zero-based newest-first rank is less than `generation_limit`. The active generation occupies one rank slot. |
| 3 | `age_undetermined` | `false` | Neither `retired_at` nor `created_at` is recorded. |
| 4 | `younger_than_minimum_age` | `false` | `age_seconds` (from `age_basis`) is less than `minimum_age_seconds`. |
| 5 | `pinned_continuation_unexpired` | `false` | `pinned_until` is set and later than `now`. |
| 6 | `reclaimable` | `true` | None of the above applies. |

---

## Refusals

| Trigger | Raised by | Error | Message |
|---|---|---|---|
| `retention_max_generations` is `None` | `resolve_retention_bound` | `ValueError` | `retention bound is unset: retention_max_generations is not declared in configuration (source: <source>); no built-in value is used` |
| `retention_min_age_seconds` is `None` (count declared) | `resolve_retention_bound` | `ValueError` | `retention bound is unset: retention_min_age_seconds is not declared in configuration (source: <source>); no built-in value is used` |
| `retention_max_generations` below 1 | `resolve_retention_bound` | `ValueError` | `retention_max_generations must be at least 1` |
| `retention_min_age_seconds` below 0 | `resolve_retention_bound` | `ValueError` | `retention_min_age_seconds must be nonnegative` |
| `bound` is not a `RetentionBound` | `evaluate_retention` | `TypeError` | `retention bound is not declared; evaluation refused` |

When both settings are undeclared, the message names `retention_max_generations`. Undeclared is tested with `is None`, so `0` for `retention_min_age_seconds` is accepted.

Adjacent change in the same ticket: `cleanup` (`knowledge/adapters/neo4j_projection.py`) and `Neo4jBackend.cleanup` no longer default `retention_seconds` to 3600; `None` raises `ValueError` with `retention bound is unset: retention_seconds must be declared by the caller; no built-in value is used`. The `cleanup` command in `knowledge/cli_sync.py` gained `--retention-seconds` (default none). This path is not the `retention_max_generations` / `retention_min_age_seconds` bound.

---

## retention command

Defined in `knowledge/cli_retention.py`, registered in `knowledge/__main__.py`. Resolves the bound before any network access, then evaluates.

| Flag | Type | Default | Description |
|---|---|---|---|
| `--backend` | `none` or `neo4j` | `none` | Evaluation requires `neo4j`; with `none` the command raises `InvalidRequest` (`retention evaluation requires the neo4j backend`) after the bound resolves. |
| `--repository-id` | string | `leafcutter` | Repository namespace. |
| `--retention-max-generations` | integer | none | Count limit. |
| `--retention-min-age-seconds` | integer | none | Minimum retirement age. |

The `source` reported by this command is the constant `BOUND_SOURCE`: `command line (--retention-max-generations, --retention-min-age-seconds)`.

Output: `{"status": "ok", "bound": {...}, "assessed": N, "generations": [...], "reclaimable": [...]}`, the evaluation result with `status` added.

---

## Failed publication removal

Defined by `publish` in `knowledge/adapters/neo4j_projection.py` (AC `KM-400b-5-i`, `docs/acceptance-criteria/knowledge-management/KM-400-trustworthy-project-knowledge/KM-400b-5-i.yaml`).

When a publication fails after its build has started (a count-check failure or an unavailable backend), the same operation removes the nodes and relationships tagged with that attempt's own generation key. Removal never matches on failed status, so other repositories and older generations are untouched. The generation record stays, with status `failed`.

The failure keeps its original cause. The message appends one of:

| Removal result | Appended message |
|---|---|
| Removed | `failed generation removed: N entity records, M relationships` |
| Both deletes refused | `failed generation not removed: repository <repo> generation <gen>; refused: <refusal>; <remaining>` |
| One delete refused | `failed generation partially removed (<kinds> remain): repository <repo> generation <gen>; refused: <refusal>; <remaining>` |

Both deletes (relationships, then nodes) are attempted whatever happens to the first. `<remaining>` is recounted after the refusal: `N entity records, M relationships remain`, or `remaining amount undetermined` when the store also refuses the count. It is never stated as 0 for lack of a count (AC `KM-400b-5-ii`).

The outcome is recorded on the backend as `publication_removal`:

| `outcome` | Shape | Meaning |
|---|---|---|
| `removed` | `{"outcome": "removed", "nodes": N, "relationships": M}` | Figures are counted before deleting (`"undetermined"` if that count was refused). |
| `partially_removed` | `{"outcome", "repository_id", "generation_id", "refusal", "remaining", "remaining_kinds"}` | One delete was refused; `remaining_kinds` names it. |
| `not_removed` | `{"outcome", "repository_id", "generation_id", "refusal", "remaining"}` | Both deletes were refused; the publication failure is still the one raised. |
| `nothing_stored` | `{"outcome": "nothing_stored"}` | The publication failed before anything was written; no removal was attempted. |

`remaining` is `{"nodes": N, "relationships": M}` or `"undetermined"`.

This removal is separate from retention reclaiming. A failed publication reclaims no retained generation. A generation left behind stays out of readers' view, and the retention evaluation assesses it with every other generation, failed ones included. Reporting it as reclaimable on a failed-publication basis is specified by KM-400f-1-iv and not yet built, so nothing removes a left-behind generation automatically yet. A read-only refusal has to be resolved first, because removal needs writes.

---

## See Also

- [Knowledge retrieval how-to](../how-to/run-knowledge-retrieval.md) - Procedures for running knowledge retrieval.
- [Knowledge Retrieval Answers](knowledge-retrieval-answers.md) - Sibling reference for the retrieval surfaces.
- [Knowledge retrieval component](../architecture/components/knowledge-retrieval.md) - Ownership and integration boundaries.
- [ADR-062](../architecture/adrs/ADR-062-standalone-knowledge-retrieval.md) - Immutable standalone projection decision.
- [AC schema reference](ac-schema.md) - Schema of the acceptance-criteria records cited here.
- [KM-400f-1](../acceptance-criteria/knowledge-management/KM-400-trustworthy-project-knowledge/KM-400f-1.yaml) - Parent AC declaring the retention bound.
- [KM-400b-3](../acceptance-criteria/knowledge-management/KM-400-trustworthy-project-knowledge/KM-400b-3.yaml) - Pinning constraint that outranks the age basis.
- `knowledge/config.py` - Settings, `RetentionBound`, `resolve_retention_bound`.
- `knowledge/adapters/neo4j_projection.py` - `evaluate_retention`, `retention_facts`, `_verdict`.
- `knowledge/cli_retention.py` - The `retention` command.
