---
title: "Reference: Knowledge Routing Step"
description: "Lookup for where the knowledge-routing step runs, which completion paths carry it, what its reported outcome and figures mean to the caller, and what the routing-run recency answer reports versus the waiting count and capture-health figures."
type: reference
status: active
created: 2026-10-08
last_updated: 2026-10-09
components:
  - knowledge_system
  - infrastructure
related_docs:
  - docs/architecture/agent_knowledge_system.md
  - docs/architecture/adrs/ADR-034-knowledge-write-ownership.md
  - docs/architecture/adrs/ADR-040-knowledge-write-publication-rides-completion-commit.md
  - docs/architecture/adrs/ADR-011-learning-emission-sink.md
  - docs/architecture/components/knowledge-system.md
---

# Knowledge Routing Step

Describes what the knowledge-routing step does today: the point at which a completion path runs it, the report it returns, and the status answer that says whether it has run in a tree. The step is dispatched by a workflow as two agents, labelled `knowledge-routing-step` and `knowledge-routing-observe`. They run the two subcommands of `scripts/knowledge/completion_routing_cli.py`, which drives `scripts/knowledge/harvest_learnings.py` (the harvester); see [Durable routing](#durable-routing).

This page owns the trigger point and the run report. It does not define which records may be written or how the waiting count is computed; both are defined in [Agent Knowledge System](../architecture/agent_knowledge_system.md) §5 (Write Eligibility and the Waiting Count), which is also the source of the exit-code enumeration used below.

---

## Completion paths

The authority for which completion paths carry the routing step is the `knowledge_routing_wiring` section of `config/guardrail_gates.yaml` (lists `wired` and `excluded`, each exclusion with a `reason`). This page does not own that list. The table below is a snapshot derived from it and from the workflow files named; if they disagree, the config section and the workflow files are correct.

The list is guarded at build time: `check_knowledge_routing_wiring` (`scripts/build_phases_knowledge.py`) takes its candidate set from the files in `templates/workflows-js/*.js`, not from the config, and `build.py` aborts when a file is named in neither `wired` nor `excluded`.

| Completion path | Carries the step | Where it runs | Reason, when not carried |
|---|---|---|---|
| `fast-lane-ship.js` | Yes | `stage` after the test, coder, review and changelog phases, immediately before the `fastlane-commit` agent; `observe` (label `knowledge-routing-observe`) immediately after it, on the success and the commit-failure path alike. | — |
| `quick-fix.js` | Yes | `stage` after the mutation proof, immediately before the `commit` phase (the fix commit, not the changelog commit); its manifest becomes extra numbered entries in the fix commit's stage list. `observe` immediately after the fix commit, on the success and the blocked path alike. | — |
| `build-epic.js` | No | — | No commit follows the step; move the step into the building-epics skill (ADR-040 §3). It was removed from the workflow on 2026-10-08. |
| `build-ticket.js` | No | — | Its commit and pull-request phases are dispatched inside a dynamic loop driven by the ticket's own phase list, so a correct insertion point needs its own design. |
| `finalize-feature.js` | No | — | Its publish step sits inside a nine-step, confirmation-gated sequence with its own halt semantics; wiring needs its own design. |
| `build-feature.js` | No | — | Resolves to `build-epic.js` or `build-ticket.js` and completes nothing itself. |
| `plan-feature.js` | No | — | Produces AC specifications, not built work; the work is completed later by whichever path builds the AC. |
| `create-ticket.js` | No | — | Produces a ticket specification, not built work; completed later by whichever path builds the ticket. |

Effect on the reader: work completed through the two carrying paths is routed automatically as part of that run. Work completed through any other route (`build-epic.js`, `build-ticket.js`, `finalize-feature.js`, or a commit made outside a workflow) is not routed by that completion; its emitted records wait until the next carrying path runs or the harvester is run by hand (see [Manual run](#manual-run)).

---

## Routing outcome

Each carrying path returns the step's result in its terminal payload under the key `knowledge_routing`. The outcome is decided by one enumerated field, `case`, built in a single function (`classifyKnowledgeRouting`) that each of the two workflow files carries a copy of. The payload is the post-commit observation, settled by `settleKnowledgeRouting` (see [Durable routing](#durable-routing)). It also appears on the payload of a run that halts at or after the commit.

| `case` value | Meaning |
|---|---|
| `completed` | The step ran to completion. |
| `could_not_complete` | The step ran and could not finish: the sink could not be read, the state file was corrupt, a destination write failed, or the commit's contents could not be observed. |
| `did_not_run` | The step was not run or its reply was not usable: no sink declaration and no `--sink`, the command could not be run, the reply was missing or unparseable, or `case` was not one of the two values above. |

Rules enforced by `classifyKnowledgeRouting`:

- Only a reply whose `case` is exactly `completed` or `could_not_complete` is trusted. Anything else is reported as `did_not_run`.
- `did_not_run` is a distinct `case` value. It is never reported as `completed` with zero figures; its `read`, `written` and `unwritten` are `0` and its `detail` is `null`, and the `case` field is what separates it from a completed run that handled nothing.
- None of the three values changes the unit of work's own outcome or exit status. The workflow files contain no halt, retry or branch on `knowledge_routing`; its uses are merging it into the returned payload and naming the staged paths in the commit prompt.

### Report fields

| Field | Type | Meaning |
|---|---|---|
| `case` | enum | One of the three values above. The only required field. |
| `read` | integer | Text-bearing sink records the stage read. `0` when not a number or when `case` is `did_not_run`. |
| `written` | integer | Learnings the path's own commit was observed to carry. Same coercion. |
| `unwritten` | integer | Learnings not carried: left out, not committed, or not routable by the harvester. Same coercion. This is one run's report, not the waiting count; for that see the §5 reference above. |
| `detail` | string or null | What could not be done. A string only when `case` is `could_not_complete`; `null` otherwise. |
| `manifest` | list of strings | The paths the commit was observed to carry, relative to the worktree. In the stage's reply, the paths the commit must stage by name. Paths that are not plain relative paths inside the worktree are dropped. |
| `unwritten_records` | list of objects | One entry per learning that did not reach the commit: `destination`, `text`, `reason` and `eligible` (see below). |
| `waiting` | object or null | `present` and `read` sink records, their `difference`, the `records` emitted after the stage read the sink, and a `note` saying they wait for the next completed unit of work. |

The figures are produced by the CLI and relayed verbatim by the dispatched agent; the workflow code validates `case` and coerces the numbers, and does not recompute them. The CLI always exits `0`. A harvester exit `1` or `2` (sink unreadable, state corrupt; see §5) is reported as `could_not_complete`, and so is a destination write failure. An absent sink is the no-work state: `completed` with zero figures. The completion path reports `could_not_complete` and `did_not_run` in `knowledge_routing` and carries on; neither fails the work.

---

## Durable routing

A learning counts as written only once the unit of work's own commit carries it (INF-700a-5, [ADR-040](../architecture/adrs/ADR-040-knowledge-write-publication-rides-completion-commit.md)). Both carrying paths split the step across that commit with two subcommands of `completion_routing_cli.py`. Each prints one JSON line and exits `0`.

| Subcommand | When | What it does |
|---|---|---|
| `stage --working-dir <worktree>` | Before the path's own commit | Claims, in the state file, every record whose text is already on `origin/main` (fetched first). Then runs the harvester with its writes redirected into the worktree and its state write held back (`harvest(persist_state=False)`). Records the run in the worktree's private git dir, where no commit can carry it, and updates the last-run marker. |
| `observe --working-dir <worktree> --commit-status ok\|failed` | After that commit, on both outcomes | Read-only. Asks git whether `HEAD` holds each staged text, and recounts the sink. Its reply is the terminal `knowledge_routing`. |

Rules:

- No record is marked routed when it is written or committed. The mark is written by a later `stage`, once the text is on `origin/main`. A record staged on a branch that never merges stays eligible and is staged again by the next run.
- Two runs that stage the same record before either merges both carry it. The designed failure is a duplicate in the merged tree, never a learning lost while marked routed.
- If the observation cannot be obtained, `settleKnowledgeRouting` counts nothing as written: every staged write is reported unwritten and `case` is `could_not_complete`.
- `--sink` defaults to the build-time declaration. With no declaration and no `--sink`, the reply is `did_not_run`. `--state` and `--marker` take the harvester's own defaults (`harvest_cli.apply_state_defaults`: `harvest_state.json` beside the sink), so the step and a manual harvester run share one state file.

`unwritten_records[].reason` values:

| `reason` | Meaning |
|---|---|
| `conflicts_with_merged_tree` | `origin/main` changed the destination since the branch left it. The write was left out so the work still publishes. |
| `publication_refused` | The commit phase failed. |
| `left_out_of_commit` | The commit succeeded but does not contain the text. |
| `stopped_before_publication` | No commit ran. |
| `outside_working_directory` | The destination resolves outside the worktree, so it was refused. |
| `write_failed` | The destination file could not be written. |

`eligible` is `true` while the record is not marked routed, which is always the case for a write that was not published.

---

## Routing-run recency answer

`harvest_learnings.py --status` answers one question: has the routing step run in this tree, and over which sink.

```bash
python3 scripts/knowledge/harvest_learnings.py --status
```

| Field | Type | Meaning |
|---|---|---|
| `last_run` | string | `never-run` when the last-run marker has never been written in this tree; otherwise the ISO-8601 UTC time of the last completed ordinary run. A marker that cannot be read or parsed is reported as `never-run`. |
| `sink` | string | Absolute path of the sink resolved for the query. |
| `sink_exists` | boolean | Existence of that path, checked at answer time. Not inferred from a past run. |

Properties:

- Prints one JSON line and exits `0` always, including for `never-run`.
- Side-effect free: does not create the marker, the marker's directory, or the sink's directory.
- The marker is `harvest_last_run.json` in the directory of `--state` unless `--marker` is given.
- An ordinary run writes the marker once `harvest()` returns, regardless of `--dry-run` and of exit `0`, `3` or `4`. A run that ends in exit `1` or `2` does not write it.
- A completed run over an absent sink writes the marker, so `last_run` can be a timestamp while `sink_exists` is `false`.

Example, from a run against a sink that does not exist (explicit temporary `--sink` and `--state` paths):

```text
$ harvest_learnings.py --status --sink <tmp>/none/sink.jsonl --state <tmp>/state/harvest_state.json
{"last_run": "never-run", "sink": "<tmp>/none/sink.jsonl", "sink_exists": false}
$ harvest_learnings.py --sink <tmp>/none/sink.jsonl --state <tmp>/state/harvest_state.json
0 learnings routed: none; 0 outstanding        (exit 0)
$ harvest_learnings.py --status --sink <tmp>/none/sink.jsonl --state <tmp>/state/harvest_state.json
{"last_run": "2026-10-08T17:57:49.591607+00:00", "sink": "<tmp>/none/sink.jsonl", "sink_exists": false}
```

### Which answer to read

| Question | Answer to read | Counts |
|---|---|---|
| Has the routing step completed in this tree, and over which sink? | `--status` (this page) | One timestamp and a path. No records, no agent runs. |
| How many records are waiting to be written? | The waiting count, defined in §5 of [Agent Knowledge System](../architecture/agent_knowledge_system.md); reported as `outstanding` in the harvester's summary line | Records. Zero for a healthy loop and for a loop that has never run. |
| How are capture attempts going? | The capture-health report's reached / recorded / failed figures, described in the same §5 | Agent invocations reaching the sign-off capture step. |

The three answers use different denominators and never share a figure. A zero waiting count does not show that the step has run; `last_run` does.

---

## Manual run

The harvester can be run by hand from the repository root: `python3 scripts/knowledge/harvest_learnings.py` (add `--dry-run` to read and classify without writing). It is the only way to route emitted records after work completed through a path that does not carry the step. Records it has written are hashed into the state file, so running it again, including after a carrying path has already run it, does not write them twice, except after exit `4` caused by a failed state persist, which §5 enumerates and which makes the next run re-route them.

A captured learning reaches its surface without a manual run only when the work is completed through one of the two carrying paths above and the records are on the declared sink at that time. This page makes no claim about the capture half (emission); see [ADR-034](../architecture/adrs/ADR-034-knowledge-write-ownership.md) and the capture-step reference in [Agent Knowledge System](../architecture/agent_knowledge_system.md).

The sink the harvester reads when `--sink` is not given is the build-time declaration; `harvest_learnings.py --print-sink` prints it. The routing step runs `completion_routing_cli.py` without `--sink`, so it reads the same declared sink, and without `--state`, so it shares the harvester's state file beside that sink.

---

## See Also

- [Confirm or route a captured learning](../how-to/confirm-or-route-a-captured-learning.md) — the task-oriented walkthrough that uses this page.
- [Agent Knowledge System](../architecture/agent_knowledge_system.md) — §5 holds the eligibility rule, the waiting count and the exit-code enumeration this page consumes.
- [ADR-034: Knowledge Write Ownership](../architecture/adrs/ADR-034-knowledge-write-ownership.md) — the harvester writes, agents only emit; no automatic wording without a caller.
- [ADR-040: Knowledge-Write Publication Rides the Completion Commit](../architecture/adrs/ADR-040-knowledge-write-publication-rides-completion-commit.md) — the placement rule for the step.
- [ADR-011: Learning Emission Sink](../architecture/adrs/ADR-011-learning-emission-sink.md) — the sink the harvester reads.
- [Knowledge System component](../architecture/components/knowledge-system.md) — component overview.
- `config/guardrail_gates.yaml` (`knowledge_routing_wiring`) — authoritative wired and excluded lists.
- `templates/workflows-js/fast-lane-ship.js`, `quick-fix.js` — the two carrying paths and their `classifyKnowledgeRouting`.
- `scripts/knowledge/harvest_learnings.py`, `scripts/knowledge/harvest_status.py` — the harvester and the `--status` implementation.
- `scripts/knowledge/completion_routing_cli.py`, `completion_routing.py` — the `stage` / `observe` durability step.
