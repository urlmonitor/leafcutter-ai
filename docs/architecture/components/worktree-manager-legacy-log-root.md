---
title: "Worktree Manager — Log Root Inherited from the Main Install (Legacy Bootstrap)"
description: "How the legacy setup_ticket_worktree.py bootstrap hands a worktree the main install's durable log root (ADR-069); legacy until BO-4300f-2."
flight_level: L3-Component
diagram_type: component
status: active
type: reference
created: 2026-10-15
last_updated: 2026-10-15
parent: docs/architecture/components/worktree-manager.md
components:
  - worktree_manager
related_adrs:
  - docs/architecture/adrs/ADR-069-durable-log-root-for-workspaces.md
related_docs:
  - docs/architecture/components/worktree-manager.md
  - docs/architecture/components/feedback-collector.md
  - docs/architecture/feedback-lifecycle.md
---

# Log root inherited from the main install (ADR-069) — legacy bootstrap

Parent: [Worktree Manager](worktree-manager.md). This section was split out of the parent
component page to keep it under the document length limit; no content was dropped.

**Legacy until BO-4300f-2.** This section describes how `setup_ticket_worktree.py` hands a
worktree its log root. ADR-070 keeps the rule (a workspace inherits the main install's
durable log root through its own build). As of 2026-10-14, though, the maker's build step
(`_build` in `workspace/workspace_create.py`) passes only `--target-dir` and `--config-path`
to the workspace's `build.py`, with no `--log-root`. So a maker-made workspace does not yet
get the inherited root that the bootstrap below provides.

A worktree is deleted when its drive ends, so its logs must not live in it. The bootstrap
(`_bootstrap` step 5 in `scripts/setup_ticket_worktree.py`) runs the worktree's own
`build.py --target-dir <worktree>` and hands it the log root the main install already
recorded. AC [INF-500d-4-iii](../../acceptance-criteria/infrastructure/INF-500-operational-observability/INF-500d-4-iii.yaml);
decision: [ADR-069](../adrs/ADR-069-durable-log-root-for-workspaces.md).

- **Read, never derived.** `_inherited_log_root_args()` reads
  `<main_repo>/.leafcutter/config/knowledge_sink.json` and takes `operational_log_root`, or,
  for an older declaration, the parent directory of `knowledge_emission_sink`. It never
  computes a root from `main_repo`'s own path, and it does not call git or walk upward.
  The build is called with `--log-root <that root>`. `build_log_root.py` records it exactly
  as given. A relative `--log-root` is refused before anything is written.
- **Unreadable main declaration.** If the file is absent, unreadable, keyless or names a
  relative root, the bootstrap prints a `WARNING` naming the path it tried and saying that
  logs written in this worktree will not survive its removal. It then passes
  `--no-log-root`, so the build records an empty declaration (`{}`) and every writer refuses.
  No declaration names the worktree's own root.
- **Older worktree `build.py`.** A branch whose `build.py` predates the flags exits 2 with
  `unrecognized arguments`. The bootstrap retries once without the flag and warns that the
  worktree has no durable log root. This case does not raise `missing_config`.
- **Symlinked `.leafcutter`.** When the worktree ends up with no `.leafcutter` of its own,
  `_establish_pre_commit_config()` links the main install's `.leafcutter`. Through that link
  the worktree reads the main install's declaration, which names the same root.
- **Three rules stay separate.** Configuration still resolves to the worktree's own
  `.leafcutter/config` and commit guards to the worktree toplevel. Only the value inside the
  declaration points at the enduring root.

A bare `build.py --target-dir <worktree>` run by hand, with neither flag, still declares
the worktree's own `debugging/logs`. It prints the operational log root it declared and a
NOTE that this working directory gets its own, second sink (INF-400c-4-v). Writers and readers
of the shared directory are described in
[Feedback Collector](feedback-collector.md#component-diagram--where-a-drives-logs-end-up)
and [Feedback Lifecycle](../feedback-lifecycle.md#where-every-log-is-kept--one-declared-log-root-adr-069).
