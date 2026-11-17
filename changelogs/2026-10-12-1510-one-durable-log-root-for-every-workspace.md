---
title: "One durable log root for every workspace: feedback, telemetry and knowledge logs no longer die with the worktree (INF-500d-4)"
date: "2026-10-12"
time: "15:10"
type: manual
components: 
  - feedback_collector
  - agent_telemetry
  - knowledge_system
  - build_pipeline
  - worktree_manager
summary: "Every log in debugging/logs now goes to one absolute operational_log_root recorded at build time in config/knowledge_sink.json. Per-drive worktrees inherit the main install's root instead of declaring their own, writers refuse rather than fall back to the working directory, and readers default to the declared sinks and say which file they read. Fixes KI-FC-001 on the branch: 787 feedback records had been scattered across 18 per-worktree sinks."
description: "Epic EPIC-OneDurableLogRootForEveryWorkspace, ADR-069 (Proposed). Build and provisioning (01bf0610a, 2a222cb54, INF-500d-4-iii): new scripts/build_log_root.py adds build.py --log-root <abs-dir> and --no-log-root; build_knowledge_sink_declaration writes operational_log_root and feedback_sink beside the two existing keys; setup_ticket_worktree.py (templates/ and the scripts/ mirror) passes the root the main install recorded, and warns and passes --no-log-root when it cannot read one; sink_resolution.py gains --print-location {root|feedback|telemetry|knowledge} and an enduring-root staleness rule; check_sink_parity.py rejects a missing, relative or split log root. Writers (3f356b815, 81dbae3b2, 6dc2df06c, aaffaf70b, INF-500d-4-i and -iv): submit_feedback.py writes only to feedback_sink or refuses with one 'destination could not be written' line and exit 1, through the new feedback_sink.py and feedback_validation.py modules, and its __file__ walk is removed; emit_event.py reads its own install's declaration instead of searching cwd ancestors; inline_work_guard.py and plan-feature.js write under the declared root; a stream counts only directly under an absolute operational_log_root. Readers (abb24ba8f, 6dc2df06c, 59ed536f8, INF-500d-4-v): the feedback readers (via the new feedback_reader.py), generate_health_report.py, trend_report.py, extract_epic_facts.py (6dc2df06c) and weekly_health.py (59ed536f8) default to the declared sink, print what they read, and exit 1 without a usable declaration. Prompts (eede17c6c, 9ce8d8052, INF-500d-4-vi): shipped agent and skill prompts drop their --jsonl / --log overrides and ask the location query instead. Review-fix round (59ed536f8): first write on a fresh install, Gemini copies resolve the install, rewrites back the sink up first, and the bootstrap retries an older worktree build once without the flag. Docs (b99967157, 638640e3f, 4d6c1f80f, INF-500d-4-vii/-viii): feedback-lifecycle.md, feedback-collector.md (diagram), agent-telemetry.md, build-telemetry.md, CLAUDE.md pre-drive check, KI-FC-001 amendment. Tests: 18 new test files. Migrates nothing; existing installs must be rebuilt."
commits: 
  - 01bf0610a
  - 4b960db2f
  - 3f356b815
  - 81dbae3b2
  - 4aab2764a
  - abb24ba8f
  - 40e98ffe7
  - eede17c6c
  - b99967157
  - 638640e3f
  - 728a1d0e7
  - 6dc2df06c
  - 41629443c
  - 2a222cb54
  - 2ffae6473
  - 59ed536f8
  - ac71e674c
  - 65f6b41d7
  - aaffaf70b
  - 9ce8d8052
  - 4d6c1f80f
breaking: true
---

## Entry

Feedback, telemetry and knowledge logs were written into whichever worktree the drive ran
in, and were deleted with it. KI-FC-001 counted 787 feedback records across 18 sinks, with
1 in the sink people read. The knowledge sink had the same defect in drives, because every
worktree bootstrap rebuilt the package and declared the worktree's own root.

- **One declared root** (INF-500d-4-iii, `01bf0610a`, `2a222cb54`).
  `config/knowledge_sink.json` now records `operational_log_root` and `feedback_sink`
  beside `knowledge_emission_sink` and `operational_telemetry_stream`, all absolute.
  `build.py --log-root <abs-dir>` records a given root and `--no-log-root` records an empty
  declaration. The worktree bootstrap passes the main install's recorded root.
  `sink_resolution.py --print-location {root|feedback|telemetry|knowledge}` prints a
  location without creating anything. `check_sink_parity.py` rejects a missing, relative or
  split root.
- **Writers refuse instead of guessing** (INF-500d-4-i, -iv; `3f356b815`, `81dbae3b2`,
  `6dc2df06c`, `aaffaf70b`). `submit_feedback.py` writes only to `feedback_sink`, or exits 1
  with one `destination could not be written` line and no id. `emit_event.py`,
  `inline_work_guard.py` and `plan-feature.js` write under the declared root.
- **Readers say what they read** (INF-500d-4-v, `abb24ba8f`). The feedback readers, the
  health reports and `extract_epic_facts.py` default to the declared sink and print
  `read N records from <path>`, or exit 1 without a usable declaration.
- **Prompts carry no destination** (INF-500d-4-vi, `eede17c6c`, `9ce8d8052`).
- **Review fixes** (`59ed536f8`): first write on a fresh install, Gemini copies, a backup
  before a rewrite, and a retry for an older worktree `build.py`.
- **Docs** (INF-500d-4-vii, -viii): ADR-069, the feedback lifecycle, the feedback-collector
  diagram, the telemetry reference, the CLAUDE.md pre-drive check and a KI-FC-001 amendment.
- **AC store reconciled** in the commit that adds this entry. INF-500d-4-i, -iii, -iv, -v and
  -vi are now `done`, and so are the reopened INF-400c-4-i, -iii and -v. INF-500d-4-vii and
  -viii and INF-500d-4 stay `todo`. INF-400c-4 also stays `todo`, because check-done-proof
  counts its superseded child INF-400c-4-ii as unproven. Tickets 01-05 record what ran but
  stay `todo`. Their review and gate phases were never dispatched, and check-ticket-signoff-parity
  refuses `done` while a phase is `needed`. The same commit corrects the `scripts/retrospective/` and `scripts/knowledge/`
  READMEs, which still described a working-directory-relative log path.

**Breaking for existing installs.** An install built before this change has a two-key
declaration with no `operational_log_root`, and writers now refuse it. Rebuild every install
(`./build-self.sh`, or `python leafcutter-ai/scripts/build.py --target-dir .`). Nothing is
migrated. The one-off rescue of the older records is `reports/feedback-snapshots/`.
