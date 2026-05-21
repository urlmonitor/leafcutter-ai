# leafcutter/scripts/feedback

## Purpose

Scripts for the Central Feedback Collection System (EPIC-FeedbackCollection).
These scripts form the feedback data pipeline: `submit_feedback.py` is the
single write chokepoint for `debugging/logs/feedback.jsonl`, while `aggregate.py`
and `list_tags.py` are read-only query tools over that file.

## Key Files

| File | Purpose |
|------|---------|
| `submit_feedback.py` | Single write chokepoint. Validates category, writer, and tag shape; generates `feedback_id`; appends one JSON line to `feedback.jsonl`; prints `feedback_id` to stdout. Called by signoff skill agents and by `emit_hook_finding.py`. |
| `aggregate.py` | Read-only query script. Filters `feedback.jsonl` by ticket, category, phase, date range, and source. Outputs filtered rows and summary counts in JSON or table format. |
| `list_tags.py` | Tag frequency discovery. Counts tags per category and returns top-N sorted by frequency. Used by the signoff skill to surface common tags. |
| `emit_hook_finding.py` | Thin Python helper for commit_guardian hooks. Calls `submit_feedback.main()` in-process with `--source hook` semantics. Never raises — returns `False` on failure. |

## Critical Context

- **`submit_feedback.py` is append-only** — it never reads or rewrites the JSONL.
  The file is the single source of truth; `aggregate.py` is a pure read function.
- **Hook mode**: when called with `--source hook`, `submit_feedback.py` skips the
  `allowed_writers` check (hooks are not listed as agents). It requires `--hook-name`
  and `--outcome` instead of `--ticket`. The `ticket` key is omitted from the JSONL
  line entirely (not written as null) when absent.
- **Tag shape rule**: tags must match `^[a-z][a-z0-9-]{0,39}$`. The script rejects
  uppercase, spaces, or leading hyphens — it does NOT auto-lowercase before validation.
- **Categories closed list**: live in `config/feedback_categories.yaml` (relative to the
  project root). `build.py` deploys this file alongside the scripts. PRs that
  add or remove categories must be reviewed. Do not edit the YAML without a PR.
- **JSONL path default**: `debugging/logs/feedback.jsonl` (relative to the project root,
  discovered by walking up from the script to find the `.claude/` directory).
  The `--jsonl` flag overrides.
- **Backward compatibility**: existing JSONL entries without a `source` field are treated
  as `source=agent` by `aggregate.py`.

## Maintenance

- To run tests: `poetry run python -m pytest unit_tests/feedback/ -v`
- To query feedback: `python scripts/feedback/aggregate.py --format table`
- To add a new category: edit `config/feedback_categories.yaml` via PR, then update
  `docs/how-to/feedback-collection.md` and the allowed_writers list.
- The `emit_hook_finding.py` helper is the preferred entry point for commit_guardian
  hooks (avoids subprocess overhead). Direct calls to `submit_feedback.py` via CLI
  are also valid.
