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

1. Enumerates all `.md`, `.py`, `.sql` files tracked by git (respects `.gitignore`).
2. Calls `detect_candidates(file_path)` from `glossary_detector.py` for each file.
3. Deduplicates candidates by term (keeps up to 5 context windows per term).
4. Loads `docs/glossary.md` (existing `### <term>` headings) and
   `docs/glossary_blacklist.md` (existing table rows) to filter already-known terms.
5. For each remaining novel candidate, dispatches the `glossary-triage` agent
   in batches of 10 (configurable via `--batch-size`).
6. Applies decisions:
   - `add_to_glossary`: appends a `### <term>` entry to `docs/glossary.md`.
   - `add_to_blacklist` / `false_positive`: appends a table row to
     `docs/glossary_blacklist.md`.
7. Commits the result: `chore(glossary): bootstrap glossary — N terms added, M blacklisted`.
8. Prints a summary table to stdout.

## Files Created or Modified

| File | Action |
|------|--------|
| `docs/glossary.md` | New entries appended (created if absent) |
| `docs/glossary_blacklist.md` | New rows appended (created if absent) |

The commit is automatic. Both files are staged and committed at the end of the run.
The commit message makes the change obvious and fully revertible via `git revert`.

## Invocation

```
/glossary-bootstrap
```

Or with options:

```bash
python leafcutter/templates/scripts/glossary_bootstrap.py \
  --repo-root <path> \
  --batch-size 10
```

## Relationship to Other GlossaryAutomation Components

| Component | Role |
|-----------|------|
| `glossary_detector.py` | Pattern-based jargon detection (ticket 01) |
| `glossary-triage` agent | Haiku classifier: add_to_glossary / add_to_blacklist / false_positive (ticket 02) |
| `/glossary-bootstrap` | **This skill** — full-repo entry point (ticket 03) |
| `check-glossary-coverage` hook | Incremental per-commit entry point (ticket 04) |
| `documentation-expert` | Auto-runs coverage lint after each doc file written (ticket 06) |

## Error Behaviour

- If `detect_candidates` fails on an individual file, the file is skipped with a
  warning and the run continues.
- If the triage agent fails for an individual term, the term is skipped with a
  warning and the run continues.
- Partial results are always written to disk immediately — an interrupted run
  preserves all decisions applied so far.
- If the final git commit fails, the files are still written. Stage and commit
  manually: `git add docs/glossary.md docs/glossary_blacklist.md && git commit`.
