---
name: glossary-bootstrap
description: Full-repo glossary bootstrap. Scans all .md/.py/.sql files for novel
  jargon candidates, dispatches the glossary-triage agent in parallel batches,
  applies decisions to docs/glossary.md and docs/glossary_blacklist.md, and commits
  the result. Run once after initial install or after a significant codebase merge.
allowed-tools: Bash, Read, Agent
portable: true
---

# /glossary-bootstrap — Full-Repo Glossary Bootstrap

## When to Run

Run `/glossary-bootstrap` once after initial install or after a significant
codebase merge. For incremental per-commit coverage, the `check-glossary-coverage`
pre-commit hook handles it automatically.

> **NEW_PROJECT_SETUP**: After adding leafcutter to a new project, run
> `/glossary-bootstrap` as the first step to seed `docs/glossary.md` from the
> existing codebase. This eliminates the backlog of unclassified jargon terms before
> the per-commit hook takes over.

## What It Does

Scans all tracked `.md`, `.py`, `.sql` files for novel jargon candidates, dispatches
the `glossary-triage` haiku agent in parallel batches to classify each term, then
applies the decisions to `docs/glossary.md` and `docs/glossary_blacklist.md` and
commits the result.

The script is split into two composable CLI modes that Claude orchestrates:

- `--list-candidates --output <path>` — pure read phase; no mutations.
- `--apply-decisions <path>` — write phase; idempotent.

## Claude Orchestration Recipe (six steps)

Follow these steps in order. Do not skip or reorder them.

### Step 1 — List candidates (read-only)

```bash
python leafcutter/templates/scripts/glossary_bootstrap.py \
  --list-candidates --output /tmp/glossary_candidates.json
```

This scans every `.md/.py/.sql` file, deduplicates jargon candidates by term,
filters already-known terms from `docs/glossary.md` and `docs/glossary_blacklist.md`,
and writes a JSON array to `/tmp/glossary_candidates.json`.

Each element has the shape:
```json
{ "term": "<str>", "occurrences": [["line_before", "line_with_term", "line_after"], ...] }
```

No glossary files are modified. No git commit is made.

### Step 2 — Read candidates

```python
import json
candidates = json.loads(open("/tmp/glossary_candidates.json").read())
```

Read `/tmp/glossary_candidates.json` into memory. If the file is empty (`[]`),
the glossary is already up to date — skip to Step 6 and report 0 terms added.

### Step 3 — Batch-dispatch glossary-triage in parallel

Group `candidates` into batches of 10. For each batch, dispatch one `glossary-triage`
Agent call per term **in a single message** (all calls in the batch go out simultaneously
as parallel Agent tool calls).

Each `glossary-triage` invocation receives:
```json
{
  "term": "<str>",
  "occurrences": [["line", ...], ...],
  "existing_glossary_context": "<first 200 chars of docs/glossary.md or empty string>"
}
```

Each agent returns a `TriageResult` JSON:
```json
{
  "term": "<str>",
  "action": "add_to_glossary" | "add_to_blacklist" | "false_positive",
  "reason": "<one sentence>",
  "draft_entry": "### term\n\nDefinition text.",
  "blacklist_row": "| term | reason |"
}
```

Collect all results across all batches.

### Step 4 — Collect results

Assemble all `TriageResult` objects from all batches into a single list.
Write the full array to `/tmp/glossary_decisions.json`:

```python
import json
json.dump(all_results, open("/tmp/glossary_decisions.json", "w"), indent=2)
```

### Step 5 — Apply decisions

```bash
python leafcutter/templates/scripts/glossary_bootstrap.py \
  --apply-decisions /tmp/glossary_decisions.json
```

This reads each decision and applies it to `docs/glossary.md` or
`docs/glossary_blacklist.md`:

- `add_to_glossary` → appends `### <term>` entry to glossary (idempotent: skips if heading already present).
- `add_to_blacklist` / `false_positive` → appends table row to blacklist (idempotent: skips if term row already present).

Stages both files and commits automatically with the standard message:
`chore(glossary): bootstrap glossary — N terms added, M blacklisted`.

Pass `--no-commit` to write files without committing (useful for preview).

### Step 6 — Inspect and commit

Run `git diff docs/glossary.md docs/glossary_blacklist.md` to confirm the changes
look correct. Unless `--no-commit` was used in Step 5, the commit is already done.
If `--no-commit` was used, stage and commit manually:

```bash
git add docs/glossary.md docs/glossary_blacklist.md
git commit -m "chore(glossary): bootstrap glossary — N terms added, M blacklisted"
```

## Two-Mode CLI Reference

| Mode | Command | Effect |
|------|---------|--------|
| List candidates | `--list-candidates --output /tmp/candidates.json` | Read-only; writes JSON; no git commit |
| Apply decisions | `--apply-decisions /tmp/decisions.json` | Writes glossary files; commits (unless `--no-commit`) |
| No subcommand | _(no flags)_ | Raises `RuntimeError`; exits non-zero |

The no-subcommand path always fails loudly — this prevents accidental silent
blacklisting of every term when the script is invoked without Claude orchestration.

## Files Created or Modified

| File | Action |
|------|--------|
| `docs/glossary.md` | New entries appended (created if absent) |
| `docs/glossary_blacklist.md` | New rows appended (created if absent) |

## Error Behaviour

- If `detect_candidates` fails on an individual file, the file is skipped with a
  warning and the run continues.
- If the triage agent fails for an individual term, the term is skipped with a
  warning and the run continues.
- Partial results are always written to disk immediately — an interrupted run
  preserves all decisions applied so far.
- If the final git commit fails, the files are still written. Stage and commit
  manually: `git add docs/glossary.md docs/glossary_blacklist.md` then `git commit`.
- Running `--apply-decisions` twice with the same file is safe — idempotency
  guards skip already-present entries.

## Relationship to Other GlossaryAutomation Components

| Component | Role |
|-----------|------|
| `glossary_detector.py` | Pattern-based jargon detection (ticket 01) |
| `glossary-triage` agent | Haiku classifier: add_to_glossary / add_to_blacklist / false_positive (ticket 02) |
| `/glossary-bootstrap` | **This skill** — full-repo entry point (ticket 03) |
| `check-glossary-coverage` hook | Incremental per-commit entry point (ticket 04) |
| `documentation-expert` | Auto-runs coverage lint after each doc file written (ticket 06) |
