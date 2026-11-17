---
title: "Reference: Knowledge Publication Capacity Headroom"
description: "Lookup for the capacity headroom gate that runs before a knowledge publication's first write: flags, ordering, what is measured, the result report and verdicts, refusal and read-only messages, and the workflow values."
type: reference
status: active
created: 2026-10-20
last_updated: 2026-10-20
components:
  - knowledge_management
related_docs:
  - docs/reference/knowledge-publication-reclamation.md
  - docs/reference/knowledge-retention-bound.md
---

# Knowledge Publication Capacity Headroom

Defined in `knowledge/adapters/retention/capacity.py` (AC `KM-400f-3`), called by `publish` in `knowledge/adapters/neo4j_projection.py` and declared by `sync` in `knowledge/cli_sync.py`. The gate measures whole-database usage and refuses a publication that does not fit the declared ceiling before anything is written.

```python
async enforce_headroom(db: Neo4jBackend, snapshot_nodes: int, snapshot_edges: int, ceiling: CapacityCeiling | None, generation_key: str | None = None) -> None
async refuse_if_read_only(db: Neo4jBackend, ceiling: CapacityCeiling | None = None) -> None
async prepare_writable(db: Neo4jBackend, ceiling: CapacityCeiling | None = None) -> None
```

---

## Entry points

| Surface | Signature or flag | Behaviour |
|---|---|---|
| `publish` | `publish(db, snapshot, expected_generation, retention_bound=None, capacity=None)` | Runs the gate when called; `capacity=None` means the ceiling is unknown. |
| `sync` | `sync(root, repository_id, revision, backend, surfaces=None, retention_bound=None, capacity=None)` | Adds `capacity` to the result. |
| `resolve_capacity` | `resolve_capacity(max_nodes, max_relationships, refuse_percent, warn_percent, *, source) -> CapacityCeiling or None` | Returns `None` when all four are `None`; raises `ValueError` on a partial or out-of-range declaration. |
| `CapacityCeiling` | `max_nodes`, `max_relationships`, `refuse_percent`, `warn_percent`, `source` (all `int` except `source`, `str`) | The declared ceiling. |

---

## Flags

All four flags belong to the `sync` command. They are integers with no built-in value and are declared all together or not at all.

| Flag | Type | Meaning | Range |
|---|---|---|---|
| `--capacity-max-nodes` | integer | Node ceiling of the database. | At least 1. |
| `--capacity-max-relationships` | integer | Relationship ceiling of the database. | At least 1. |
| `--capacity-refuse-percent` | integer | Percent of the ceiling above which publication is refused. | `1 <= warn <= refuse <= 100`. |
| `--capacity-warn-percent` | integer | Percent of the ceiling above which publication warns. | `1 <= warn <= refuse <= 100`. |

| Declaration | Result |
|---|---|
| None of the four | No ceiling; the verdict is `unknown`; usage is still measured. |
| All four, in range | `CapacityCeiling` with `source` `command line (--capacity-max-nodes, --capacity-max-relationships, --capacity-refuse-percent, --capacity-warn-percent)`. |
| Some of the four | `ValueError` naming each missing flag and the source, ending `declare all four capacity settings or none`. |
| A ceiling below 1 | `ValueError`: `capacity ceiling must be at least 1 node and 1 relationship`. |
| Percentages out of order or range | `ValueError`: `capacity percentages must satisfy 1 <= warn <= refuse <= 100`. |

The `ValueError` is raised before `writer_backend` is called, so no network access happens, and the command exits with status 2.

---

## Publication ordering

| Step | Effect |
|---|---|
| 0 | The `sync` command runs `prepare_writable` before anything else: the read-only preflight (`refuse_if_read_only`) first, then `setup()` (its schema writes `CREATE CONSTRAINT` / `CREATE INDEX`). |
| 1 | `db.publication_capacity` is set to `None`; no headroom is reported until usage is measured. |
| 2 | Identical edges are collapsed, the snapshot is validated, and the repository control-record check runs. |
| 3 | `enforce_headroom` runs: usage is measured, then this generation's record is read. Nothing has been written yet. |
| 4 | The first write (the `Snapshot` record `MERGE`) runs through `first_write`. |
| 5 | The generation is built, validated, and the pointer switched; reclamation follows as in [Knowledge Publication Reclamation](knowledge-publication-reclamation.md#publication-ordering). |

A read-only refusal at step 0, a refusal at step 3, or a read-only classification at step 4 stops the publication. It reclaims nothing (`0 generations reclaimed`), switches no pointer, and leaves the previous active generation in place.

---

## What is measured

| Item | Value |
|---|---|
| Scope | The whole database, not the one repository named in the publication. |
| Node usage | `MATCH (n) RETURN count(n) AS count` |
| Relationship usage | `MATCH ()-[r]->() RETURN count(r) AS count` |
| Snapshot size | Entity records (`len(snapshot.nodes)`) and distinct relationships (`len(snapshot.edges)` after collapse). |
| Generation record | `MATCH (g:Snapshot {key:$key}) RETURN g.status AS status`, a read before any write. Status `validated` or `ready`: the records are already in the measured usage, so the snapshot adds 0 on both axes. Status `building` (partially written) or no record: the full snapshot is counted (conservative, since a partial build's share of usage is unknown). |
| Basis | `measured`; usage is read from the backend, never estimated. |

A rerun of the same revision, or a resume after a failed pointer switch, therefore needs only the switch and is not refused for a shortfall it does not cause.

---

## Headroom report

Stored as `Neo4jBackend.publication_capacity`; returned as `capacity` by `sync` (`None` when the publication failed before measurement).

| Key | Type | Description |
|---|---|---|
| `verdict` | string | `within_headroom`, `warning`, `refused`, `unknown`, or `read_only`. |
| `basis` | string | Always `measured`. |
| `ceiling_known` | boolean | `False` when no ceiling was declared. |
| `satisfied` | boolean | `True` for `within_headroom` and `warning`; `False` for `unknown`, `refused`, and `read_only`. |
| `warnings` | list of strings | One entry per axis when the verdict is `warning`; empty otherwise. Each is also logged at WARNING. |
| `statement` | string | The result in words. `unknown` names the measured node and relationship usage; an already-stored snapshot adds `snapshot already stored, so it adds 0 to the measured usage`. |
| `snapshot_already_stored` | boolean | `True` when this generation was `validated` or `ready` and the snapshot figures below are therefore 0; `False` otherwise. Absent from a `read_only` report raised by the preflight. |
| `nodes` | object | Per-axis figures for nodes. |
| `relationships` | object | Per-axis figures for relationships. |

### Per-axis figures

| Key | Type | Description |
|---|---|---|
| `usage` | integer | Measured whole-database count. |
| `ceiling` | integer or `None` | Declared ceiling; `None` when unknown. |
| `snapshot` | integer | Records the publication will ADD on this axis: the prepared snapshot size, or 0 when `snapshot_already_stored`. |
| `shortfall` | integer or `None` | `max(0, ceil(usage + snapshot - refuse_percent * ceiling / 100))`. `None` when the ceiling is unknown. |
| `remaining` | integer or `None` | `max(0, floor(refuse_percent * ceiling / 100 - (usage + snapshot)))`. `None` when the ceiling is unknown. |

### Verdicts

Thresholds compare `(usage + snapshot) * 100` against `percent * ceiling` and are strictly greater: a total exactly at a threshold does not cross it. Either axis crossing is enough.

| Verdict | Condition | `satisfied` | Effect |
|---|---|---|---|
| `within_headroom` | Neither axis exceeds `warn_percent`. | `True` | Publication proceeds. |
| `warning` | An axis exceeds `warn_percent`, none exceeds `refuse_percent`. | `True` | Publication proceeds; warnings logged and reported. |
| `refused` | An axis exceeds `refuse_percent`. | `False` | `ValueError` before any write. |
| `unknown` | No ceiling declared. | `False` | Publication proceeds; the report states no headroom check was satisfied. |
| `read_only` | The backend is read-only. | `False` | `BackendUnavailable` before or at the first write. |

An unknown ceiling is never counted as a fit and never refuses a publication. `read_only` replaces any other verdict, including `refused`, because the access check runs before the refusal check.

Example, with ceiling 200,000 nodes, refuse 90, warn 75, usage 189,950 nodes and a snapshot of 100 nodes: threshold 180,000, total 190,050, `shortfall` 10,050, `remaining` 0, verdict `refused`.

---

## Messages

| Condition | Exception | Message content |
|---|---|---|
| Refused | `ValueError` | Begins `publication refused before any write: capacity headroom is insufficient (usage figures were measured from the backend, not estimated)`. Per axis: `measured usage`, `ceiling`, `snapshot`, `shortfall`; ends `0 generations reclaimed`. An unknown ceiling prints as `undetermined`. |
| Read-only | `BackendUnavailable` | Begins `backend is read-only, a capacity condition: the store accepts no writes, so this is not a result about knowledge`; carries the backend's rejection text in parentheses when classified from a write; states `usage measured from the backend` with node and relationship counts; ends `0 generations reclaimed`. |
| Warning | log record | `capacity headroom warning, usage measured from the backend;` then, per axis, usage, ceiling, snapshot, and remaining headroom. |

---

## Read-only detection

| Order | Mechanism | Detail |
|---|---|---|
| 1 | `SHOW DATABASE $name YIELD access` against the `system` database | Run by `database_access`: first by the CLI preflight (`refuse_if_read_only`, before `setup()`), then by `enforce_headroom` before the first write. `access` equal to `read-only` raises the read-only refusal; the preflight measures usage with the two count queries (reads still work) and sets `db.publication_capacity` to a `read_only` report. |
| 2 | Fallback: classify the rejection of a write | Used when `SHOW DATABASE` is refused or returns no row (a `BackendUnavailable` is logged at WARNING and `database_access` returns `None`). `prepare_writable` classifies a rejected `setup()` and `first_write` the first publication write: each re-raises the `BackendUnavailable` as the read-only refusal, chaining the original, when its text, lowercased, contains `read-only`, `readonly`, `read only`, or `no write operations`. |

Any other rejection of `setup()` or of the first write propagates unchanged.

---

## Workflow values

`.github/workflows/knowledge-sync.yml` declares the ceiling and passes it as the four flags.

| Environment variable | Flag | Value |
|---|---|---|
| `KNOWLEDGE_CAPACITY_MAX_NODES` | `--capacity-max-nodes` | `200000` |
| `KNOWLEDGE_CAPACITY_MAX_RELATIONSHIPS` | `--capacity-max-relationships` | `400000` |
| `KNOWLEDGE_CAPACITY_REFUSE_PERCENT` | `--capacity-refuse-percent` | `90` |
| `KNOWLEDGE_CAPACITY_WARN_PERCENT` | `--capacity-warn-percent` | `75` |

The values are the Aura Free limits per database (200,000 nodes, 400,000 relationships). The workflow job runs only when the repository variable `KNOWLEDGE_SYNC_ENABLED` is `true`; the workflow stays disabled.

The ceiling is declared rather than read because Neo4j does not report it over Bolt.

---

## Operator status and sweep reclamation

`status` and the new `reclaim` command (AC `KM-400f-4`, `knowledge/cli_generations.py`) take the optional `--retention-max-generations` / `--retention-min-age-seconds` pair and the four `--capacity-*` flags (all four or none; a partial or out-of-range declaration is refused before any network access). `status` writes nothing.

| `status` field | Content |
|---|---|
| `retention_bound` | The declared bound the verdicts were evaluated against, or the statement `no retention bound declared`. |
| `generations` | One entry per retained generation: `generation_id`, `source_sha`, `retired_at` (null when never retired; `age_basis` states what the age is measured from), `reclaimable`, `reason`, `age_basis`, `age_seconds`. Verdicts come from `evaluate_retention`, unrecomputed. Without a bound, `reclaimable` and `reason` are `undetermined (no retention bound declared)`. |
| `retained_count`, `exceeding_bound_count` | Generations listed, and how many exceed the declared count limit (`undetermined (no retention bound declared)` without a bound). |
| `capacity` | `ceiling_known`, `verdict`, `statement`, and `repository` / `backend` by `nodes` / `relationships`: `usage`, `ceiling` and `remaining`. An undeclared ceiling is the string `unknown`, never omitted. Backend usage is the two whole-database counts; repository usage counts records tagged with this repository's generation keys plus its Snapshot records. |

`reclaim` has no `--generation-id` and requires the retention bound (refused before network access otherwise). It runs the read-only preflight, then `reclaim_superseded` once, and returns `status` (`ok`, or `error` when the evaluation could not be assessed), `reclaimed`, `retained`, `reclaimed_generations` and `retained_generations` (each with its `reason`). Nothing reclaimable is `ok` with `reclaimed: 0`. The active generation and any generation with an unexpired pin are retained.

---

## See Also

- [Knowledge Publication Reclamation](knowledge-publication-reclamation.md) - Reclamation after the pointer switches; the gate runs before it.
- [Knowledge Retention Bound](knowledge-retention-bound.md) - The retention bound declared alongside the ceiling.
- `knowledge/adapters/retention/capacity.py` - Gate, report, and messages.
- `knowledge/adapters/neo4j_projection.py` - `publish` call site.
- `knowledge/cli_sync.py` - The `--capacity-*` flags and the `capacity` result key.
