# leafcutter/scripts/feedback

## Purpose

Scripts for the Central Feedback Collection System (EPIC-FeedbackCollection).
These scripts form the feedback data pipeline: `submit_feedback.py` is the
single write chokepoint for the install's declared `feedback_sink`, while
`aggregate.py` and `list_tags.py` are read-only query tools over that file.

The sink is the `feedback_sink` value recorded at build time in
`<install>/config/knowledge_sink.json` (`<install>` is the `.leafcutter/` directory
two levels above these scripts). It is `<operational_log_root>/feedback.jsonl`, a
location that outlives any one worktree, and every worktree of the install shares it.

## Key Files

| File | Purpose |
|------|---------|
| `submit_feedback.py` | Single write chokepoint. Validates category, writer, and tag shape; generates `feedback_id`; appends one JSON line to `feedback.jsonl`; prints `feedback_id` to stdout. Called by signoff skill agents and by `emit_hook_finding.py`. |
| `aggregate.py` | Read-only query script. Filters `feedback.jsonl` by ticket, category, phase, date range, and source. Outputs filtered rows and summary counts in JSON or table format. |
| `list_tags.py` | Tag frequency discovery. Counts tags per category and returns top-N sorted by frequency. Used by the signoff skill to surface common tags. |
| `emit_hook_finding.py` | Thin Python helper for commit_guardian hooks. Calls `submit_feedback.main()` in-process with `--source hook` semantics. Never raises — returns `False` on failure. |
| `feedback_sink.py` | Resolves the declared `feedback_sink` for `submit_feedback.py`, or builds its one-line refusal. Creates nothing. |
| `feedback_reader.py` | Shared by the readers: resolves the declared path, prints the `read N records from <path>` line, and does locked, backed-up rewrites. |
| `link_feedback.py`, `resolve_feedback.py` | Rewrite entries in the sink under the same exclusive lock `submit_feedback.py` takes. |

## Critical Context

- **`submit_feedback.py` is append-only** — it never reads or rewrites the JSONL.
  The file is the single source of truth; `aggregate.py` is a pure read function.
- **Hook mode**: when called with `--source hook`, `submit_feedback.py` skips the
  `allowed_writers` check (hooks are not listed as agents). It requires `--hook-name`
  and `--outcome` instead of `--ticket`. The `ticket` key is omitted from the JSONL
  line entirely (not written as null) when absent.
- **Tag shape rule**: tags must match `^[a-z][a-z0-9-]{0,39}$`. The script rejects
  uppercase, spaces, or leading hyphens — it does NOT auto-lowercase before validation.
- **Categories closed list**: live in `config/feedback_categories.yaml`, found two
  directory levels above the script (`<install>/config/`). `build.py` deploys this file
  alongside the scripts. PRs that add or remove categories must be reviewed. Do not edit
  the YAML without a PR.
- **JSONL path default**: the declared `feedback_sink`. Nothing walks up for `.claude/` and
  nothing is resolved from the working directory. `--jsonl` overrides and is used as given.
- **The sink must be usable.** It counts only when the declaration also records an absolute
  `operational_log_root` and the sink sits directly under it. A build with `--no-log-root`
  records an empty declaration, so there is no sink to use.
- **Refusal**: when the declaration is absent, unreadable, unparseable, missing a key, holds a
  relative value, puts the sink outside the root, or is stale, `submit_feedback.py` prints
  one `[submit_feedback] ERROR: destination could not be written: ...` line on stderr. That
  line names the declaration and the failed condition. Stdout is empty, the exit code is 1,
  and nothing is created. Stale means the enduring root that holds the log directory is gone
  (its parent, or the project above `debugging`). A log directory that is merely missing
  under a live root is a fresh install: the first write creates it.
- **Readers say what they read.** `aggregate.py`, `list_tags.py`, `link_feedback.py` and
  `resolve_feedback.py` print `[<script>] read N records from <absolute path>` on stderr.
  When they read the default sink, the same line names any populated pre-declaration
  `debugging/logs/feedback.jsonl` that differs from it; that file is not read or moved. With
  no usable declaration and no `--jsonl`, a reader prints one ERROR line and exits 1.
- **Rewrites back the sink up first.** Before `link_feedback.py` or `resolve_feedback.py`
  rewrites the sink in place, it copies it to `<sink>.bak-<UTC timestamp>`. The copy is
  removed when the rewrite succeeds and named in the error when it fails.
- **Where the sink is**: `python <install>/scripts/knowledge/sink_resolution.py
  --print-location feedback` prints it without creating anything, or refuses with exit 1.
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
