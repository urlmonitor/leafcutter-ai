---
title: "Known issues — build-orchestration"
description: "Open, observed defects in the build-orchestration component: the fast-lane build loop, its gates, and the AC lifecycle transitions it performs. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-09-23
components:
  - build_orchestration
related_docs:
  - docs/architecture/components/build-orchestration.md
  - docs/how-to/fast-lane-build.md
---


# Known issues — build-orchestration

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-BO-YYYYMMDD-HHMM` section, using the UTC time you
filed it (`date -u "+%Y%m%d-%H%M"`). Nothing here is generated — edit it by hand. Fill in what
you actually know; an issue recorded with a thin `Evidence` line is far better than one not
recorded.

**Why datetime ids and not the next free number.** Sequential ids collide whenever two
sessions file at once, which happens constantly here. On 2026-08-26 alone: two different
defects both landed as `KI-CG-012`, a branch's `KI-BP-010`/`KI-BO-016`/`KI-BO-017` all had to
be renumbered at merge because main had independently minted the same numbers, and a
changelog ended up describing `KI-CG-012` using what became `KI-CG-013`'s text. Renumbering is
worse than it sounds — inbound references do not disambiguate, so a rename can silently
repoint a citation at the wrong defect. A UTC timestamp cannot collide and needs no lookup of
"the next free number", which is itself a read of a file another session is editing. Existing
`KI-BO-NNN` entries keep their ids; do not renumber them. This change is what `KI-BO-024`
asked for — it recorded the same defect in the convention itself, and predicted the duplicate
that then shipped to `main`.

**Hitting an existing issue.** Increment `Occurrences` and update `Last seen`. Do not
add a duplicate entry. Occurrences is an escalator, not the score — a blocker seen once
outranks an annoyance seen ten times.

**Severity** is `blocker` (work cannot land) / `high` (silent wrong behaviour) /
`medium` (real but survivable) / `low` (noise, dead code, cosmetics).

**Closing an issue.** When the fix lands, delete the section and reference the issue id
in the commit message. If it earns real work, author an AC for it and note the AC id in
`Status` — this file is a capture surface, not a replacement for the AC store.

---

## How this register is stored

This file is an **index**. Each known issue is its own file under [`build-orchestration/`](build-orchestration/), named `<status>-<severity>-<ki-id>.md`, so the directory listing answers "is anything open, and how bad" without opening anything:

```
ls docs/known-issues/build-orchestration/open-blocker-*   # anything critical open?
ls docs/known-issues/build-orchestration/open-*           # everything still live
```

Severity in the **filename** is a three-level index bucket (`blocker` / `high` / `low`). The original grading is preserved verbatim on each entry's own `**Severity:**` line — the bucket never overwrites it. `critical` indexes as `blocker`; `medium` indexes as `low`.

Fixed issues move to [`build-orchestration/resolved/`](build-orchestration/resolved/) and are no longer listed as open. They are kept, not deleted.

**Open: 50** (7 blocker, 26 high, 17 low) · **Resolved: 10**

## Open

| Severity | Issue | File |
|---|---|---|
| `blocker` | KI-BO-018 — `/plan-feature` halts on a false `worktree-agent` permission verdict, caused by a truncated agent-relayed config read rather than anything wrong with the agent's charter | [open-blocker-ki-bo-018.md](build-orchestration/open-blocker-ki-bo-018.md) |
| `blocker` | KI-BO-019 — The context bundle is passed through an agent's JSON return value, so a large bundle arrives as a file path and the fail-closed gate halts a run whose bundle was fine | [open-blocker-ki-bo-019.md](build-orchestration/open-blocker-ki-bo-019.md) |
| `blocker` | KI-BO-20260831-1930 — The driver deliberately drops the `pull-request` phase for an epic member, the generator emits it as `needed`, and nothing reconciles them — so every epic ticket halts the drive at completion | [open-blocker-ki-bo-20260831-1930.md](build-orchestration/open-blocker-ki-bo-20260831-1930.md) |
| `blocker` | KI-BO-20260901-1000 — The per-ticket phase list is frozen before the first phase runs, so a phase that a later phase declares necessary can never be dispatched — and `architect-review`, whose job is to declare exactly that, is ordered after the phases it gates | [open-blocker-ki-bo-20260901-1000.md](build-orchestration/open-blocker-ki-bo-20260901-1000.md) |
| `blocker` | KI-BO-20260901-1045 — Every handoff halts the drive: the driver routes on a `handoff_target` field that no agent template tells any agent to emit | [open-blocker-ki-bo-20260901-1045.md](build-orchestration/open-blocker-ki-bo-20260901-1045.md) |
| `blocker` | KI-BO-20260921-build-feature-abandons-the-epic-worktree-branch — a re-run switches the worktree onto a fresh branch off main, drives the epic from the MAIN checkout, and re-runs tickets that are already committed | [open-blocker-ki-bo-20260921-build-feature-abandons-the-epic-worktree-branch.md](build-orchestration/open-blocker-ki-bo-20260921-build-feature-abandons-the-epic-worktree-branch.md) |
| `blocker` | KI-BO-20260921-fastlane-worktree-agent-acts-on-leaked-conversation — the fast lane's worktree phase executed destructive git operations from the parent session's conversation, then asked for the authorization afterwards | [open-blocker-ki-bo-20260921-fastlane-worktree-agent-acts-on-leaked-conversation.md](build-orchestration/open-blocker-ki-bo-20260921-fastlane-worktree-agent-acts-on-leaked-conversation.md) |
| `high` | KI-BO-007 — `build-feature` counts a phase as completed when the agent halted without doing it, yielding `status: ok` with no PR | [open-high-ki-bo-007.md](build-orchestration/open-high-ki-bo-007.md) |
| `high` | KI-BO-20260921-worktree-base-resolver-defaults-to-cwd — build-feature calls the worktree-base resolver with no start path, so in the self-hosting layout it resolves against a directory outside the repository and every epic drive aborts | [open-high-ki-bo-20260921-worktree-base-resolver-defaults-to-cwd.md](build-orchestration/open-high-ki-bo-20260921-worktree-base-resolver-defaults-to-cwd.md) |
| `high` | KI-BO-011 — A grep-only test aimed at an orphaned file kept a superseded criterion looking satisfied, hiding a direct contradiction between two `done` ACs | [open-high-ki-bo-011.md](build-orchestration/open-high-ki-bo-011.md) |
| `high` | KI-BO-012 — The fast lane emits no telemetry, so the lane-comparison report can never contain fast-lane data | [open-high-ki-bo-012.md](build-orchestration/open-high-ki-bo-012.md) |
| `high` | KI-BO-013 — A documentation-only AC anywhere in a resolved build set jams the fast lane at commit, because `test_required: false` is honoured by nothing | [open-high-ki-bo-013.md](build-orchestration/open-high-ki-bo-013.md) |
| `high` | KI-BO-014 — `goal_to_epic`'s `--ac` entry path never received the BO-2600a-5 hygiene fixes, so it writes absolute `implemented_by` and untranslated `depends_on` | [open-high-ki-bo-014.md](build-orchestration/open-high-ki-bo-014.md) |
| `high` | KI-BO-017 — A fast-lane re-run whose worktree was pruned silently rebuilds on the old branch tip instead of the latest `origin/main` | [open-high-ki-bo-017.md](build-orchestration/open-high-ki-bo-017.md) |
| `high` | KI-BO-022 — A CRLF acceptance-criterion record is rewritten LF end-to-end by a single `work_status` flip, and every value-level check still passes | [open-high-ki-bo-022.md](build-orchestration/open-high-ki-bo-022.md) |
| `high` | KI-BO-023 — `_update_ac_work_status` raises `ValueError`, all three call sites catch only `OSError`, and the escape strands acceptance criteria in `in_progress` permanently | [open-high-ki-bo-023.md](build-orchestration/open-high-ki-bo-023.md) |
| `high` | KI-BO-025 — `/build-feature` plans only the first ready wave, so an epic with any dependency depth cannot be driven to completion in one run | [open-high-ki-bo-025.md](build-orchestration/open-high-ki-bo-025.md) |
| `high` | KI-BO-028 — Six `done` acceptance criteria in this component are falsified by defects already recorded in this register | [open-high-ki-bo-028.md](build-orchestration/open-high-ki-bo-028.md) |
| `high` | KI-BO-030 — `build.py` never creates two of the four namespace roots, so registering the uniqueness gate would make the package uninstallable | [open-high-ki-bo-030.md](build-orchestration/open-high-ki-bo-030.md) |
| `high` | KI-BO-032 — `/fast-lane-build` silently builds a different batch when the AC you named is not `readiness: approved` | [open-high-ki-bo-032.md](build-orchestration/open-high-ki-bo-032.md) |
| `high` | KI-BO-20260831-1331 — A half-created fast-lane worktree is invisible to `git worktree`, so it cannot be cleaned up and its symptom reads as store-wide corruption | [open-high-ki-bo-20260831-1331.md](build-orchestration/open-high-ki-bo-20260831-1331.md) |
| `high` | KI-BO-20260831-1520 — The fast lane's green gate runs only the AC's own tests, so a build that breaks unrelated suites reaches review — and now a PR — reporting "gates green" | [open-high-ki-bo-20260831-1520.md](build-orchestration/open-high-ki-bo-20260831-1520.md) |
| `high` | KI-BO-20260831-1931 — Ticket completeness is judged from the newest per-agent COMMENT, and the driver halts before dispatching, so a stale comment blocks every future run and the record cannot heal itself | [open-high-ki-bo-20260831-1931.md](build-orchestration/open-high-ki-bo-20260831-1931.md) |
| `high` | KI-BO-20260901-0920 — The commit-phase serialization lock is specified, its helper script was never written, and the workflow that inherited the responsibility does not take a lock at all — so N tickets commit concurrently into one shared index | [open-high-ki-bo-20260901-0920.md](build-orchestration/open-high-ki-bo-20260901-0920.md) |
| `high` | KI-BO-20260901-1052 — `python-coder` signals a test handoff exactly as its template prescribes, and the driver rejects it for omitting a field the template never mentions — so the documented delegation path dead-ends every ticket that uses it | [open-high-ki-bo-20260901-1052.md](build-orchestration/open-high-ki-bo-20260901-1052.md) |
| `high` | KI-BO-20260901-1620 — `permits_shell` is a three-state field read as two, so the fix for KI-BO-020 picked an agent the schema also calls read-only — and three shell dispatches still go to the one agent that explicitly forbids it | [open-high-ki-bo-20260901-1620.md](build-orchestration/open-high-ki-bo-20260901-1620.md) |
| `high` | KI-BO-20260907-0850 — `build-ticket.js` is the declared twin of the driver just fixed: one defect is unfixed there and the other handler is a generation behind, so `/build-ticket` still loses the ticket in ways `/build-feature` no longer does | [open-high-ki-bo-20260907-0850.md](build-orchestration/open-high-ki-bo-20260907-0850.md) |
| `high` | KI-BO-20260907-0955 — The fast lane cannot complete any AC whose tests build a real clone, because its green gate runs before its commit phase | [open-high-ki-bo-20260907-0955.md](build-orchestration/open-high-ki-bo-20260907-0955.md) |
| `high` | KI-BO-20260907-resume-replays-cached-resolver — `resumeFromRunId` replays the resolve step's cached `agent()` result instead of re-running it, and the fresh-run alternative is itself blocked by the failed run's leftover worktree | [open-high-ki-bo-20260907-resume-replays-cached-resolver.md](build-orchestration/open-high-ki-bo-20260907-resume-replays-cached-resolver.md) |
| `high` | KI-BO-20260908-1030 — The fast lane guards its verdicts against fabrication and passes the pointers to their evidence through unchecked, so `tests_written` can name a file that does not contain the tests | [open-high-ki-bo-20260908-1030.md](build-orchestration/open-high-ki-bo-20260908-1030.md) |
| `high` | KI-BO-20260909-worktrees-go-stale-within-minutes — a branch cut from `origin/main` is behind before the work finishes, and nothing rebases it; only a manual audit stands between that and a push that deletes other people's merged work | [open-high-ki-bo-20260909-worktrees-go-stale-within-minutes.md](build-orchestration/open-high-ki-bo-20260909-worktrees-go-stale-within-minutes.md) |
| `high` | KI-BO-20260914-autofix-re-dispatch-is-specified-at-a-depth-that-cannot-execute — the commit agent is told to spawn the originating coder, and ADR-019 says that call is silently dropped | [open-high-ki-bo-20260914-autofix-re-dispatch-is-specified-at-a-depth-that-cannot-execute.md](build-orchestration/open-high-ki-bo-20260914-autofix-re-dispatch-is-specified-at-a-depth-that-cannot-execute.md) |
| `high` | KI-BO-20260907-0804 — The epic planner omits only `done`, so a parked ticket is re-scheduled every run and halts the drive again | [open-high-ki-bo-20260907-0804.md](build-orchestration/open-high-ki-bo-20260907-0804.md) |
| `low` | KI-BO-008 — A structural test makes code comments load-bearing | [open-low-ki-bo-008.md](build-orchestration/open-low-ki-bo-008.md) |
| `low` | KI-BO-009 — The harness default stub is generically positive, so a new gate silently breaks older fixtures | [open-low-ki-bo-009.md](build-orchestration/open-low-ki-bo-009.md) |
| `low` | KI-BO-021 — TODO: `BO-2400e-4` is closed on two of its four specified tests, and the two missing ones are the pair that would survive a writer swap | [open-low-ki-bo-021.md](build-orchestration/open-low-ki-bo-021.md) |
| `low` | KI-BO-024 — "Append the next free number" is not a workable id convention under concurrent agents, and on 2026-08-25 it finally shipped a duplicate to `main` | [open-low-ki-bo-024.md](build-orchestration/open-low-ki-bo-024.md) |
| `low` | KI-BO-026 — Work the planner never selected is reported as work "added to the epic after the plan was fixed" | [open-low-ki-bo-026.md](build-orchestration/open-low-ki-bo-026.md) |
| `low` | KI-BO-027 — `/build-feature`'s target resolution returns the epic folder as the worktree path | [open-low-ki-bo-027.md](build-orchestration/open-low-ki-bo-027.md) |
| `low` | KI-BO-029 — The fast lane stages with `git add -A` into a worktree its own bootstrap already dirtied, so every fast-lane PR silently carries unrelated generated diff | [open-low-ki-bo-029.md](build-orchestration/open-low-ki-bo-029.md) |
| `low` | KI-BO-031 — `check_doc_frontmatter.py` tells the operator to consult a spec file that does not exist | [open-low-ki-bo-031.md](build-orchestration/open-low-ki-bo-031.md) |
| `low` | KI-BO-20260826-1332 — The fast lane reads `work_status: todo` as "nobody has built this", but it only means "not on main", so it silently rebuilds work that already exists on an unmerged branch | [open-low-ki-bo-20260826-1332.md](build-orchestration/open-low-ki-bo-20260826-1332.md) |
| `low` | KI-BO-20260826-1900 — The done-proof gate collects parametrized pytest ids and then cannot match one, so a covers-tagged parametrized test reads as "not run" and blocks the merge | [open-low-ki-bo-20260826-1900.md](build-orchestration/open-low-ki-bo-20260826-1900.md) |
| `low` | KI-BO-20260831-1332 — The fast lane's roster is python-coder + test-writer, so it refuses a third of the ready queue with no upstream signal | [open-low-ki-bo-20260831-1332.md](build-orchestration/open-low-ki-bo-20260831-1332.md) |
| `low` | KI-BO-20260831-1932 — The completion guard refuses one ticket and passes another on identical conditions | [open-low-ki-bo-20260831-1932.md](build-orchestration/open-low-ki-bo-20260831-1932.md) |
| `low` | KI-BO-20260901-1450 — The fast lane shares exactly one process-level surface with its siblings: `$GIT_COMMON_DIR/config`. Two other suspected surfaces were measured and are isolated. | [open-low-ki-bo-20260901-1450.md](build-orchestration/open-low-ki-bo-20260901-1450.md) |
| `low` | KI-BO-20260907-0851 — Two agent templates use `(status: handoff)` to mean "stop, I need human authorization", so a deliberate halt is reported to the operator as a malformed result | [open-low-ki-bo-20260907-0851.md](build-orchestration/open-low-ki-bo-20260907-0851.md) |
| `low` | KI-BO-20260914-a-cached-bad-path-makes-a-workflow-run-permanently-unresumable — resume replays the poisoned agent result in 32ms, so the only escape from a caught hallucination is a fresh run id | [open-low-ki-bo-20260914-a-cached-bad-path-makes-a-workflow-run-permanently-unresumable.md](build-orchestration/open-low-ki-bo-20260914-a-cached-bad-path-makes-a-workflow-run-permanently-unresumable.md) |
| `low` | KI-BO-20260914-commit-agent-rewrites-co-author-trailer — the commit agent replaces the caller's `Co-Authored-By` trailer with its own model name, so a commit misattributes which model did the work | [open-low-ki-bo-20260914-commit-agent-rewrites-co-author-trailer.md](build-orchestration/open-low-ki-bo-20260914-commit-agent-rewrites-co-author-trailer.md) |
| `low` | KI-BO-20260907-0803 — `blocked` and `deferred` are valid ticket statuses that no transition can reach, so the only way to park a ticket is to bypass the tool | [open-low-ki-bo-20260907-0803.md](build-orchestration/open-low-ki-bo-20260907-0803.md) |

## Resolved

| Severity | Issue | File |
|---|---|---|
| `low` | KI-BO-002 — moved to `ac-store` | [resolved-low-ki-bo-002.md](build-orchestration/resolved/resolved-low-ki-bo-002.md) |
| `low` | KI-BO-006 — `fast-lane-build.js` is deployed but orphaned | [resolved-low-ki-bo-006.md](build-orchestration/resolved/resolved-low-ki-bo-006.md) |
| `high` | KI-BO-010 — `/quick-fix`'s divergence gate was a first-token substring match with a looping remedy; both were replaced on 2026-08-26 and the entry was never closed | [resolved-high-ki-bo-010.md](build-orchestration/resolved/resolved-high-ki-bo-010.md) |
| `high` | KI-BO-015 — `_worktree_exists` does not know the `fast-lane/` prefix, so a fast-lane run cannot recognise its own workspace and aborts at phase one | [resolved-high-ki-bo-015.md](build-orchestration/resolved/resolved-high-ki-bo-015.md) |
| `high` | KI-BO-016 — Resolving a one-criterion build set takes ~3 minutes, because every traversal re-parses the entire AC store | [resolved-high-ki-bo-016.md](build-orchestration/resolved/resolved-high-ki-bo-016.md) |
| `high` | KI-BO-020 — The fast lane's release-on-failure path is dead: it dispatches `status-checker`, which refuses the role, so aborted runs strand their claims | [resolved-high-ki-bo-020.md](build-orchestration/resolved/resolved-high-ki-bo-020.md) |
| `blocker` | KI-BO-20260826-1214 — The fast lane cannot complete: its context-bundle gate demands a 1359-line document inlined into a JSON field, and the agent returns a pointer instead | [resolved-blocker-ki-bo-20260826-1214.md](build-orchestration/resolved/resolved-blocker-ki-bo-20260826-1214.md) |
| `high` | KI-BO-20260826-1333 — Nine of a file's ten tests asserted only that strings were present in the source they covered — so the AC looked comprehensively covered because coverage was measured by count | [resolved-high-ki-bo-20260826-1333.md](build-orchestration/resolved/resolved-high-ki-bo-20260826-1333.md) |
| `blocker` | KI-BO-20260831-1330 — The fast lane invokes `assemble-bundle` with two flags that were deliberately deleted, so its context-bundle gate can never be satisfied | [resolved-blocker-ki-bo-20260831-1330.md](build-orchestration/resolved/resolved-blocker-ki-bo-20260831-1330.md) |
| `high` | KI-BO-20260907-1555 — `failed` is a terminal phase state: the dispatcher filters it out, so a phase that exhausted its retries can never be re-run by any later drive | [resolved-high-ki-bo-20260907-1555.md](build-orchestration/resolved/resolved-high-ki-bo-20260907-1555.md) |
