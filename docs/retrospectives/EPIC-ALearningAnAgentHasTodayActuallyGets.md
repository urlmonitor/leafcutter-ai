---
title: 'Retrospective: EPIC-ALearningAnAgentHasTodayActuallyGets'
type: retro
status: active
created: 2026-10-25
epic: EPIC-ALearningAnAgentHasTodayActuallyGets
source_ac: INF-700b
components:
- knowledge_system
- infrastructure
last_updated: '2026-10-25'
description: 'Overview of Retrospective: EPIC-ALearningAnAgentHasTodayActuallyGets.'
---

# Retrospective: EPIC-ALearningAnAgentHasTodayActuallyGets
Date: 2026-10-25
Epic duration: 2026-10-16 to 2026-10-25 (from ticket dates and feedback timestamps; `extract_epic_facts.py` reported no git dates because the epic folder has no commits in this close-out worktree)
Commits: not available from the script (reported 0). The work merged to main as 8 PRs: #1283, #1303, #1308, #1319, #1331, #1328, #1336, #1358.

## Summary
AC composite INF-700b made agent learning capture observable and trustworthy. Each sign-off now records a `capture_attempt` ledger entry, whether it recorded a learning or had nothing to record (ticket 02 / PR #1283). Failed captures get their own section (#1303). A commit-time check refuses skill references that resolve to nothing (ticket 04 / #1319). A consumer-layout test proves the check fires from the deployed layout (#1328). A capture-health report counts attempts per period (#1336). Docs and doc tests landed in #1358. Two side fixes shipped: `knowledge_sink.json` is now gitignored (#1308) and a build timeout was raised (#1331, BP-100k-4-iii).

The drive was clean on phase sign-offs. No phase recorded a `failed` sign-off. The friction was elsewhere: stale ticket premises, test isolation leaking into the shared install, and CI details around composites and signoff bash blocks.

Caveats on the data. `extract_epic_facts.py` shows `completed_ticket_count: 0` and `git_commit_count: 0`. Both are artifacts of closing from a fresh worktree where the tickets are still in `00_inbox` and the epic has no commits, so the counts below are not completion measures. All 8 tickets merged per the PR list.

## Metrics
Source: `extract_epic_facts.py` (8 tickets). Phases with 0 signed off in every column are omitted below: commit, pull-request, frontend-coder, sql-coder and user-surface-smoker were all `not_needed` on all 8.

| Phase | Signed Off | Failed | Needed |
|-------|-----------|--------|--------|
| architect-review | 6 | 0 | 0 |
| test-writer | 6 | 0 | 0 |
| python-coder | 4 | 0 | 0 |
| llm-expert | 3 | 0 | 0 |
| adr-author | 3 | 0 | 0 |
| documentation-expert | 2 | 0 | 0 |
| documentation-verifier | 2 | 0 | 0 |
| architecture-diagram-author | 1 | 0 | 0 |
| test-runner | 6 | 0 | 0 |
| pr-reviewer | 6 | 0 | 0 |
| ac-validator | 6 | 0 | 0 |
| ac-fulfillment-gate | 6 | 0 | 0 |

`failed` is 0 everywhere, but the ticket comments hold 3 blocker comments (in ticket files 01, 06 and 08). Blockers were raised and resolved by rework within the phase, so they do not show as a final `failed` state. A final `failed` state undercounts friction here.

## Category Breakdown (Feedback System)
`aggregate.py` stated: read 162 records from `/home/henzeh/projects/leafcutter/debugging/logs/feedback.jsonl`. It also noted 154 older records in `.leafcutter/debugging/logs/feedback.jsonl` that predate the declaration and were not read. The 162 are the whole corpus. 72 belong to this epic (filtered on the ticket path containing INF-700b).

| Category | Count (epic) |
|----------|-------|
| complete | 51 |
| knowledge-gap | 10 |
| tooling-issue | 4 |
| blocker | 3 |
| success-pattern | 2 |
| quality-concern | 1 |
| convention-ambiguity | 1 |

## Epic Facts
| Metric | Value |
|--------|-------|
| Ticket count | 8 |
| Completed tickets (script) | 0 (artifact: tickets not yet moved; all 8 merged) |
| Git commits (script) | 0 (artifact; 8 merged PRs) |
| Blocker comments | 3 |
| Handoff comments | 0 |
| Telemetry events attributed to epic by script | capture_attempt: 1 (of 36 records read) |

Capture-health report for the drive window (2026-10-16 to 2026-10-26): attempts=34, recorded=17, nothing-to-record=17, failed=0, malformed=0, unrecognised=2. Verdict: learnings-recorded. The report's own limits A2.4 and A2.6 apply: a failure that also breaks the telemetry writer, or an `emit_event.py` subprocess that cannot run, leaves no record.

## What Went Well
- No phase ended `failed` across 8 tickets and about 60 phase sign-offs.
- Reviewers found real defects before merge. pr-reviewer on ticket 01 caught unescaped double-quoted `--text` in the signoff section 7 command and an ADR A1.4 claim the code did not honour. pr-reviewer on ticket 06 caught a surviving string-compare-of-timestamps mutation, and the test was strengthened.
- Good verification patterns were recorded as `success-pattern`: ac-validator ran the deployed section 7 command through a real shell with backtick, apostrophe, `$(...)` and newline (2026-10-20); pr-reviewer ran 4 mutations in a private worktree copy against the built hook (2026-10-23).
- architect-review repeatedly reconciled stale ticket scope instead of building obsolete designs (tickets 01, 03, 04, 05, 06, 08). This avoided redundant code, such as a new checker made obsolete by ticket 04.
- The ledger works. `failed=0`, `malformed=0` over 34 attempts, and adr-author and other phases ran the nothing-to-record step.

## Friction Points
Each driver-reported item was checked against ticket comments, feedback and CI/PR data where available. Status shown per item.

1. **test-runner skipped the nothing-to-record step (driver: twice). Partly verified.** The ledger has 34 attempts. Across the 8 tickets there are 6 test-runner sign-offs, 6 test-writer, and many other phases, so 34 is well below the number of sign-offs. That is consistent with some phases not recording. I did not attribute individual attempts to agents (the telemetry `phase` split is not exposed by the report), so "twice, test-runner only" is the driver's account, not something I confirmed. The consequence is real by the report's own definition: quiet sign-offs are undercounted, so `nothing-to-record=17` is a floor.
2. **Test spawned build.py into a make_build_package copy and leaked into the shared install. Verified.** Feedback `fb_2026-10-23` (test-writer, tooling-issue, tags test-isolation, build-py, symlinked-copy): the copy symlinks `.leafcutter` and `.claude`, so `build.py --target-dir <copy>` deploys through them and clobbered the shared `knowledge_sink.json`. Cleanup and rebuild were manual. This also breaks the existing CLAUDE.md rule that tests should not spawn their own `build.py`, and the memory note on `make_build_package` leaks.
3. **CI flakes from 30s subprocess timeouts (BP-100k-4-iii, UXP-700d-3-i). Partly verified.** PR #1331 (BP-100k-4-iii timeout) merged in the epic's window. I did not retrieve CI logs for UXP-700d-3-i, which is a different epic, so I cannot confirm it. See friction 8 for a caution.
4. **#1283 CI failed BO-210c-1-iii on `|| true` in a signoff bash block, conflicting with INF-500d-4-vi. Partly verified.** Ticket 01 carries a blocker comment (pr-reviewer, 2026-10-20) and feedback `fb_2026-10-21` (architect-review, tag adr-amendment-gap) records "found the signoff inline-command constraint". `gh pr view 1283` shows no currently failing check on the final state, consistent with the failure being fixed on the branch (4 commits). The resolution (signoff section 7 points at a named agent-telemetry section, ADR-034 A2.8) is as the driver described.
5. **Closing the composite tripped the untagged-done ratchet (240 to 241). Not independently verified** (no CI log retrieved). It matches the known project rule that a done AC without a `# covers:` tag fails CI pytest, composites included.
6. **Review and doc-gate findings. Verified.** pr-reviewer mutation survivor on ticket 06 is in the feedback (`blocker`, test-gap, 2026-10-23). documentation-verifier blocked ticket 08 (feedback, `blocker`, 2026-10-25) on a placeholder HTML comment at line 190 and `leafcutter/templates/...` paths that do not resolve. documentation-expert recorded the mermaid parent issue (`convention-ambiguity`, parent-doc-root-flag): `agent_knowledge_system.md` had no `parent:`/`root:` (pre-existing ARCH-PARENT-MISSING), fixed by adding `root: true` and `children:`. Also: the doc exceeded the 300-line limit so two sections were split out; `new_arch_doc.py` scaffold was absent and `check_doc_links` only recognises a `Doc Links:` marker in `.md`.
7. **python-coder used an inline python file edit. Not verified from the data I read.** No feedback entry or ticket comment I scanned names it. Treat as driver-observed.
8. **Driver misdiagnosed a post-merge red as a timeout flake. Not verifiable here, but it is a process finding.** The red was a real correctness-lane failure already fixed on main. This matches the memory rule "mass-failure story hides a regression" and "read the post-merge verdict JSON, not the log".

Additional friction found in the data and not on the driver's list:
- **Stale ticket premises, six occurrences** (feedback tags stale-ticket, stale-ticket-premise, stale-ticket-assumptions, stale-ticket-notes, adr-amendment-gap): tickets 01, 03, 04, 05, 06, 08. Causes: text field and retired-name strike already on HEAD via PR 722; ticket 03 scope stale after ticket 02; `ability_reference_verdict` already gated build/CI when ticket 04 assumed it did not; ticket 05's generated design obsolete after ticket 04; ticket 06 assumed a 3-verdict partition and a 28/4/1 stream, but the live stream differs and the unit is attempts, not runs; ticket 08 notes predated INF-700a wiring and ADR-069. architect-review caught each, but only after tickets had been generated.
- **Test helpers modelled the old mechanism** (ticket 01, test-writer, third pass): helpers covered only the harvester path, not `emit_knowledge.py`.
- **ac-validator accepted a proxy proof** on ticket 02 (period-count clause proven only through ledger content; the reader is ticket 06).
- **ADR doc hooks read the git index only.** `check_adr_cross_reference` and `check-doc-length` could not check unstaged ADR edits; adr-author called the analysis functions directly. In a worktree, `REPO_ROOT` also resolves through the symlinked `.leafcutter` to the main install.
- **Shared-worktree stash** (python-coder, 2026-10-20, but on a different epic's ticket path): another ticket's pre-commit stashed unstaged edits. Listed for completeness; it belongs to EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace.

## Knowledge Gaps Found
- Ticket premise staleness has no preflight. Six of 8 tickets needed scope reconciliation by architect-review.
- Signoff section 7 constraint: inline bash blocks in signoff text must not contain `|| true` (INF-500d-4-vi), and the capture command must survive real-shell quoting (backtick, `$(...)`, quotes). Neither was written down where the ticket author would see it. Now covered by ADR-034 A1/A2.8.
- `make_build_package` copies symlink the shared install; building into one writes through. Documented only in memory, not in the test-authoring docs.
- A done composite AC needs its own `# covers:` tag. Known from memory; absent from the epic close checklist.
- `check_doc_links` marker format (`Doc Links:` in `.md`), the missing `new_arch_doc.py` scaffold, and `ARCH-PARENT-MISSING` for mermaid docs without `parent:`/`root:` are not documented in the diagram how-to.
- Sixteen knowledge-gap feedback entries across the corpus are unresolved (10 belong to this epic).

## Subagent Quality Trends
`aggregate.py --category subagent-quality` returned 1 entry corpus-wide, from 2026-09-29 (test-writer, cross-agent-rework, a different epic). Nothing for this drive.

> No supervisor feedback entries found for this epic (supervisors may pre-date EPIC-SupervisorFeedback or no adjudication events occurred during this drive).

## Unresolved Feedback

There are at least 16 unresolved feedback entries in feedback.jsonl (count taken from a `--category knowledge-gap` run; the all-category unresolved total was not retrieved). Run `/feedback-review` to triage them before closing the epic branch.

## Proposed Improvements
Proposals only. None applied. The `route-knowledge` skill was not invoked as a loaded skill in this run, so routing below follows the classification the repo's CLAUDE.md already uses for pre-drive and implementation conventions, and the caller should confirm it. `.agents/rules/` is being retired; no proposal targets it.

### KI-1: Verify ticket premises against HEAD before authoring or driving
Six of 8 tickets in this epic had stale premises. Proposed text:

> Before a ticket generated from an AC is driven, and again at the architect-review phase, check each "current state" claim in the ticket against `origin/main` (fetched). If the premise is stale, reconcile the ticket first. Do not dispatch coders against a design written before the upstream sibling tickets merged.

Routing: CLAUDE.md "Pre-Drive Checklist" (candidate path `/home/henzeh/projects/leafcutter/worktrees/inf-700b/CLAUDE.md`), because it is a pre-drive habit.

### KI-2: Capture step is not optional at quiet sign-offs
> The nothing-to-record capture-attempt step at sign-off runs for every phase agent, including test-runner, test-writer and gates, even with no learning. An attempt count lower than the sign-off count means some phases skipped it, and `nothing-to-record` is then a floor.

Routing: `signoff` skill section 7 (`templates/skills/signoff/SKILL.md`, a template/package surface). Add a one-line reminder, and consider a supervisor-side check that compares capture attempts to sign-offs per ticket.

### KI-3: Tests must not build into a make_build_package copy
> `H.make_build_package` copies symlink `.leafcutter` and `.claude`. `build.py --target-dir <copy>` writes through those symlinks into the shared install. A test that must build uses a separate empty target directory, or reads the `shared_reference_layout` fixture.

Routing: extends the existing "Tests must not spawn their own build.py" section in CLAUDE.md, same file as KI-1.

### Rule Update: composite AC close needs its own `# covers:` tag
```diff
 ### AC-store commits — stage the parent alongside the child
 ...
+When closing a composite AC as done, add a `# covers:` tag for the composite itself.
+A done composite with no tag raises the untagged-done ratchet (INF-700b: 240 to 241)
+and fails CI pytest. Never raise the ratchet mark.
```
Routing: CLAUDE.md, same section.

### Rule Update: signoff bash blocks must stay free of `|| true`
```diff
- Signoff section 7 embeds the capture command inline.
+ Signoff section 7 points at the named agent-telemetry section (ADR-034 A2.8) and
+ carries no inline bash block with `|| true` (INF-500d-4-vi / BO-210c-1-iii).
```
Routing: `signoff` skill and ADR-034 A2.8 cross-reference; the change is already landed, so this is a documentation note only. Consider declining if A2.8 already states it.

### KI-4: Diagnose post-merge red from the verdict JSON before blaming a flake
> A post-merge red is read from `post-merge-verdict.json` (`failing` field), not from the log summary, and any "timeout flake" claim is checked by re-running against main first.

Routing: this is already in the maintainer's memory notes. Suggest it as a `building-epics` / finalize-feature note instead of a new memory entry, so agents see it too (`templates/skills/building-epics/SKILL.md`).

### KI-5: Document the doc-gate traps hit on ticket 08
> `check_doc_links` only recognises a `Doc Links:` marker in `.md` files. A mermaid doc without `parent:` or `root: true` fails ARCH-PARENT-MISSING. `documentation-verifier` rejects the word "Placeholder" and paths under `leafcutter/templates/`. `check-doc-length` and `check_adr_cross_reference` read only the git index.

Routing: `docs/how-to/documentation/` (how-to for architecture docs). Not applied.

### Noted, not proposed
- python-coder inline python edit: the rule already exists in the user's global CLAUDE.md and the project hook `block file mutation`. Without an entry in the data, I propose no new rule; the driver may file feedback with the agent and ticket if it recurs.
- UXP-700d-3-i timeout flake: belongs to another epic, so no proposal.
