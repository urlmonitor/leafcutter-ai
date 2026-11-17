---
title: "KI-BP-20261116-tracked-sink-declaration-stays-stale — a consumer that already committed config/knowledge_sink.json keeps shipping one machine's log root to every checkout, so every feedback and telemetry write is refused while the location query answers OK"
description: "high — DIAGraph committed .leafcutter/config/knowledge_sink.json naming the devcontainer root /workspaces/dia-graph/debugging/logs. INF-500d-4-x only adds the file to config/.gitignore, which does not untrack a file git already tracks, so every checkout and clone gets the stale root. submit_feedback.py and emit_event.py refuse it as stale, so every sign-off records feedback-id: (submit-failed). sink_resolution.py --print-location feedback still prints the stale path with exit 0, and the workspace maker passes the stale root on as --log-root."
type: reference
category: reference
status: active
created: '2026-11-16'
last_updated: '2026-11-16'
components:
  - build_pipeline
  - knowledge_management
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
  - docs/architecture/adrs/ADR-069-durable-log-root-for-workspaces.md
  - docs/known-issues/feedback-collector/resolved/resolved-low-ki-fc-001.md
  - docs/known-issues/build-orchestration/resolved/resolved-high-ki-bo-20261009-bo100d-probe-pins-a-relative-telemetry-path.md
---

# KI-BP-20261116-tracked-sink-declaration-stays-stale — an already-committed `knowledge_sink.json` keeps shipping a dead log root

> Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below.

- **Severity:** high. Every feedback record and telemetry event from the install and from every clone of it is refused, and the pre-drive location query reports the sink as fine. Agents fall back to `feedback-id: (submit-failed)` and `|| true`, so the corpus goes quiet with no signal at the place that is meant to catch it.
- **Status:** open, no AC.
- **Occurrences:** 1 (DIAGraph, 2026-11-16) · **First seen:** 2026-11-16 · **Last seen:** 2026-11-16
- **Where:** `scripts/build_phases_knowledge.py` (build engine, not deployed): `_ensure_declaration_gitignored()` (`:246-275`) and `build_knowledge_sink_declaration()` (`:278-418`). `scripts/knowledge/sink_resolution.py` (deployed `.leafcutter/scripts/knowledge/sink_resolution.py`): `read_usable_stream()` (`:190-224`) and `handle_print_location()` (`:239-268`). `templates/scripts/worktree_log_root.py` (deployed `.leafcutter/scripts/worktree_log_root.py`): `_recorded_root()` (`:31-44`). The refusal is in `templates/scripts/feedback/feedback_sink.py` `_failure()` (`:93-97`).

## Mechanism

1. The declaration holds per-machine absolute paths by design. A plain build records `<target-dir>/debugging/logs` (`build_log_root.declaration_values`, `:90`).
2. INF-500d-4-x (`152a2375d`, 2026-10-22) keeps the file out of git only by adding a line to `config/.gitignore` (`:268-273`). A `.gitignore` rule does nothing for a file git already tracks. Nothing runs `git rm --cached`, and nothing warns that the declaration is tracked. The INF-500d-4-x test (`unit_tests/portability/test_inf_500d_4_x.py:45`) checks `check-ignore` on an untracked file only.
3. So a repo that committed the file before 2026-10-22 keeps the committed value. Every checkout and clone gets the committing machine's root.
4. The writers refuse it as stale, because the enduring root does not exist on this machine (`feedback_sink._failure`, `:93-97`; `emit_event._declared_stream`, `:231-232`).
5. The location query does not check staleness. `handle_print_location()` accepts any stream that `read_usable_stream()` accepts, and that function checks only that the paths are absolute and that the stream sits directly under the root. It never calls `enduring_root_exists()`. The query prints the stale path with exit 0.
6. The workspace maker propagates the stale root. `_recorded_root()` checks only `is_absolute()` (`:42`), so every new workspace is built with `--log-root <stale root>`.

## Seen

- `.leafcutter/config/knowledge_sink.json` is tracked in DIAGraph (`git ls-files`). It was added in `7e1ea4546` (2026-09-10) and last changed in `81ef814ce` (2026-10-21). In the main checkout and in the clone `/home/henzeh/projects/worktrees/srf-commit-clone` (same blob, `b8a519b8f`), it reads `"operational_log_root": "/workspaces/dia-graph/debugging/logs"`, with the feedback, telemetry and knowledge streams under that root. `/workspaces` does not exist on this host.
- DIAGraph has no `.leafcutter/config/.gitignore`, so its pin also predates INF-500d-4-x. On current main the build would add the ignore line, but the file would stay tracked.
- Writer refusal in the clone (transcript `feeb7c15…jsonl`, line 3952): `[submit_feedback] ERROR: destination could not be written: ... (stale: /workspaces/dia-graph (the enduring root that should hold /workspaces/dia-graph/debugging/logs) no longer exists ...)`. The session's agent brief (line 4746) then made `feedback-id: (submit-failed)` the standing fallback for every comment.
- `python3 /home/henzeh/projects/DIAGraph/.leafcutter/scripts/knowledge/sink_resolution.py --print-location feedback` prints `/workspaces/dia-graph/debugging/logs/feedback.jsonl` and exits 0. That deployed copy matches `origin/main` (`8d76d670a`) apart from line endings (`diff --strip-trailing-cr` is empty).

## Fix direction

- **Untrack, not just ignore.** When the build finds the declaration tracked (`git ls-files --error-unmatch`), it should say so loudly and give the `git rm --cached` command. Or it should refuse to finish until the file is untracked. Running `git rm` itself is the consumer's call.
- **Make the location query check staleness.** `handle_print_location()` should refuse when `enduring_root_exists()` is false, as the writers already do. Then the "Feedback sink reachable" pre-drive check fails on the query itself, without needing the manual `test -w` step.
- **Do not inherit a dead root.** `_recorded_root()` should reject a root whose enduring holder does not exist. It should then fall through to the existing `--no-log-root` warning path instead of passing the root on.
