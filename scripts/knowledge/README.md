# knowledge

Knowledge System scripts: the post-execution learning harvester and the
context-file maintenance helpers it writes through.

## Purpose

This package implements the write side of the Agent Knowledge System
(`docs/architecture/agent_knowledge_system.md`,
`docs/architecture/components/knowledge-system.md`): it drains
`knowledge_captured` events emitted during agent sign-off (`signoff` §7)
from a retained JSONL sink (ADR-011) and routes each to the appropriate
knowledge surface — without ever inventing content the emitting agent did
not actually write (ADR-034; INF-700c-1 / INF-700c-1-i).

## Key Files

| File | Purpose |
|------|---------|
| `harvest_learnings.py` | The harvester CLI/library. Reads unprocessed `knowledge_captured` events, applies the per-record eligibility rule (no learning text -> never written), routes eligible events by `entry_kind`, tracks processed events via a hash-based idempotency state file, and reports a five-bucket `HarvestResult` plus a line-level malformed-line count. |
| `context_file_maintenance.py` | Shared write helpers for component `README.md` and skill `PROJECT_CONTEXT.md` files: reverse-chronological entry append with date headings and agent attribution, plus threshold-triggered summary generation. **Not called by the harvester.** `harvest_learnings.py` contains zero references to this module — its `_default_capture` does a plain `fh.write(learning_text + "\n")` with no date heading, attribution or structure, for every `entry_kind` including `per-folder-readme` and `skill-context`. Its only in-tree caller is `init_component_readme.py`. Wiring the harvester's write phase through these helpers would be a real improvement; do not assume it has happened. |
| `init_component_readme.py` | Idempotent CLI to create a component AC directory `README.md` via `context_file_maintenance.create_readme`. |

## Critical Context

- The sink path (`debugging/logs/knowledge_emissions.jsonl` by default) has
  never existed on disk; the real, retained knowledge-emission stream lives
  at `debugging/logs/agent_telemetry.jsonl` (both under `debugging/logs/`,
  which is gitignored — see `.gitignore:60`). Callers must pass `--sink`
  explicitly to point at the real stream.
- `harvest_learnings.py` is a pure **reader** of its sink by design (ADR-011):
  it never repairs, rewrites, or line-deletes the input file, even for a
  malformed line or an ineligible (textless) record. This is what lets a
  corrected routing rule be re-run over history.
- Eligibility (INF-700c-1) is evaluated **before** `entry_kind` routing. A
  record that is both textless and unknown-kinded — the shape of every
  retained real record as of 2026-08-26 — must land in the
  `no_learning_text` bucket, not `skipped_unknown`, or the run's exit code
  is pinned non-zero forever. See the module docstring and inline comments
  in `harvest_learnings.py` for the full rationale.
- A malformed line (not JSON, or JSON but not an object) is a line-level
  condition tracked separately from the five record-level buckets and does
  not stop the read of subsequent lines.
- `_KNOWN_ENTRY_KINDS` in `harvest_learnings.py` is the extension seam for
  adding new routable `entry_kind` values (INF-400c-2-ii).

## Maintenance

- Tests live at `tests/knowledge/test_harvest_learnings.py` (unittest,
  filesystem-isolated via `tempfile.TemporaryDirectory`). Real-artifact
  behavioral cases use `tests/fixtures/harvest_learnings/unroutable_corpus_28.json`,
  a verbatim capture of the real retained corpus.
- Run with: `python -m unittest tests.knowledge.test_harvest_learnings`
- All tests must complete in under 5 seconds.
