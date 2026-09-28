---
title: 'Retrospective: EPIC-StartingNewWorkTheProperWayAlways'
type: retro
status: active
created: 2026-09-14
epic: EPIC-StartingNewWorkTheProperWayAlways
source_ac: ACD-2100
components:
- ac_driven_dev
last_updated: '2026-09-14'
description: 'Overview of Retrospective: EPIC-StartingNewWorkTheProperWayAlways.'
---

# Retrospective: EPIC-StartingNewWorkTheProperWayAlways
Date: 2026-09-14
Epic duration: 2026-08-26 (scaffold + first fix commit) to 2026-09-14 (final how-to landed) — 19 calendar days, active on 7 of them (2026-08-26, 08-31, 09-01, 09-07, 09-08, 09-09, 09-14), with three `Merge origin/main into EPIC-StartingNewWorkTheProperWayAlways` catch-up merges during the gaps.
Commits: `extract_epic_facts.py` reported `git_commit_count: 0` / `git_first_commit_date: null` for this epic (see "Data-source caveats" below — treat as a script limitation, not a fact about the epic). Reconstructed directly via `git log --grep="ACD-2100"`: **62** commits reference ACD-2100, of which 25 are the per-ticket "commit phase sign-off" commits (one per ticket) plus feature/fix/doc/spec/known-issues commits interleaved with unrelated epics on this shared long-lived branch.

## Summary

This epic closed out `/plan-feature`'s three original startup-reliability gaps (ADR-012's mandated entry point): working-directory sensitivity of the setup/registry/pause-store paths (`a`-series, 6 tickets), a startup check that could not distinguish an unreadable registry from a denied agent (`b`-series, 6 tickets), decisions the route recorded as the user's that no user actually made (`c`-series, 6 tickets), parity between the source and installed copies of the route (`d`-series, 5 tickets), and the documentation closing the loop — a sequence diagram and a resume how-to (`e`-series, 2 tickets). All 25 tickets are `status: done` and committed.

The epic's own `Master_Plan.md` records that `goal_to_epic.py` crashed mid-generation on 2026-08-26 and left the plan and 11 `depends_on` edges broken (repaired by hand before any ticket work began — KI-ACD-018 reproduced exactly, plus a second, previously-unseen defect where every Roman-suffix `-i` ticket's sibling dependency was silently dropped). That repair-before-work pattern, plus the density of independently-confirmed defects below, makes this one of the more instructive drives to retrospect on: the mechanical gates worked as designed on several genuinely dangerous near-misses, and the friction points below are mostly about what still depends on convention rather than enforcement.

## Metrics

### Phase sign-off counts (`extract_epic_facts.py`, ticket-frontmatter sign-off blocks)

| Phase | Signed Off | Failed | Needed (unresolved) | Not Needed |
|-------|-----------|--------|----------------------|------------|
| architect-review | 10 | 0 | 0 | 1 |
| test-writer | 22 | 0 | 0 | 0 |
| python-coder | 22 | 0 | 0 | 0 |
| test-runner | 22 | 0 | 0 | 0 |
| pr-reviewer | 22 | 0 | 0 | 0 |
| ac-validator | 23 | 0 | 0 | 0 |
| ac-fulfillment-gate | 23 | 0 | 0 | 0 |
| documentation-expert | 7 | 0 | 0 | 18 |
| documentation-verifier | 3 | 0 | 0 | 22 |
| architecture-diagram-author | 1 | 0 | 0 | 0 |
| llm-expert | 1 | 0 | 0 | 0 |
| commit | 25 | 0 | 0 | 0 |
| pull-request | 0 | 0 | 0 | 25 |
| frontend-coder / sql-coder / user-surface-smoker | 0 | 0 | 0 | 1 each |

`failed`/`needed` are 0 across every phase in the frontmatter sign-off model — this epic never left a phase stuck in an unresolved retry loop; every blocker below was worked through to a subsequent `(status: ok)` on the same ticket. `pull-request` shows 25/25 `not_needed`: this drive committed directly to the long-lived epic branch rather than opening a PR per ticket (consistent with the shared-branch, multi-epic commit history observed in `git log`).

### Feedback category breakdown (164 entries, 100% ticket-scoped to this epic — `debugging/logs/feedback.jsonl` in this worktree contains no other epic's entries)

| Category | Count |
|----------|-------|
| complete | 129 |
| blocker | 15 |
| quality-concern | 12 |
| tooling-issue | 4 |
| convention-ambiguity | 3 |
| knowledge-gap | 1 |
| **Total** | **164** |

By phase: pr-reviewer=31, commit=27, python-coder=27, test-runner=24, test-writer=24, architect-review=11, documentation-expert=8, documentation-verifier=8, architecture-diagram-author=2, llm-expert=1, status-checker=1.

**Note on the blocker-count discrepancy:** `extract_epic_facts.py`'s `blocker_comment_count` (text-matching `(status: blocker)` across all ticket Comments) reports **20**, while the feedback-category count above is **15**. The gap is explained by ticket 15 (`ACD-2100c-3`), whose commit phase alone cites three sibling blockers in its own refusal text (a re-quote, not a new independent finding) plus a second later blocker cascade — comment-text scanning double-counts cross-referencing quotes that the structured feedback log does not. Trust the feedback-log figure (15) for "independent blocker findings"; the comment-count figure (20) for "how many times a blocker was read/re-cited in the record."

### Subagent Quality Trends

```
python /home/henzeh/projects/leafcutter/worktrees/EPIC-StartingNewWork/scripts/feedback/aggregate.py --jsonl .../feedback.jsonl --category subagent-quality --format json
```
returned `"total": 0`. No supervisor-emitted `subagent-quality` feedback entries exist for this epic — either no adjudication events of that shape occurred, or the supervisors on this drive pre-date EPIC-SupervisorFeedback's tagging convention. `--source hook` also returned `"total": 0` — no hook-emitted feedback entries exist for this epic (all 164 entries are agent-submitted).

### Epic Facts

| Metric | Value |
|--------|-------|
| Ticket count | 25 |
| Completed tickets | 25 |
| Git commits (ACD-2100-referencing, reconstructed) | 62 (25 are per-ticket commit-phase commits) |
| Blocker comments (text-scan) | 20 |
| Blocker findings (feedback log) | 15 |
| Handoff comments | 6 |
| Unresolved feedback entries | 164 (see "Unresolved Feedback" below) |

### Data-source caveats

- `extract_epic_facts.py` reported `git_commit_count: 0`, `git_first_commit_date: null`, `git_last_commit_date: null`, and `telemetry_events: {}` for this epic. No `debugging/logs/agent_telemetry.jsonl` file exists in this worktree at all (only `feedback.jsonl` is present under `debugging/logs/`), which accounts for the empty telemetry read; the zeroed git fields appear to be a script limitation against this branch's topology (a single long-lived epic branch interleaved with many other epics' commits, rather than one commit range cleanly attributable to the epic) rather than a real absence of commits — the `git log --grep` reconstruction above found 62 directly-referencing commits. This is worth a bug report against `extract_epic_facts.py` separately from this retrospective's own findings.

## What Went Well

- **The mechanical gate stack caught two genuinely dangerous defects that the ticket's own tests missed**, both on `ACD-2100c-3`: `pr-reviewer`, `ac-validator`, and `ac-fulfillment-gate` independently confirmed (14:01–14:30 on 2026-09-08) that a `clear-pause-record` dispatch result was read nowhere (so AC-4's "no record remains on disk" guarantee was unverified on the failure path) and a duplicate-AC-id bug in multi-stage resume — **neither exercised by the ticket's own passing test suite**. `commit` correctly refused three consecutive unaddressed blocker verdicts rather than landing a green-tests-but-broken change. This is exactly the "commit over unaddressed blockers is phantom-done one layer up" posture this repo's tooling is designed around, and it worked.
- **`test-runner` independently re-derived, rather than trusted, every "these N failures are pre-existing" claim** — e.g. on ACD-2100c-3 it re-ran the 22 baseline failures via a file-copy restore (not `git stash`, to avoid disturbing worktree state) rather than accepting python-coder's `git stash` claim at face value.
- **The provenance-refusal gate (`ACD-2100c-4`) caught its own near-miss inside the same ticket.** `test-writer` correctly classified 16 newly-red sibling tests as `test_drift` rather than weakening the new provenance check, and `python-coder` disclosed the cross-ticket blast radius explicitly rather than quietly patching around it (see "Friction Points" below for the deeper issue this exposed).
- **AC-driven authoring and repair discipline held up under a botched generator run.** The hand-repaired `Master_Plan.md` (11 dangling `depends_on` edges + 4 dropped `-i` sibling edges) was verified bidirectionally (every edge resolves to a real file; every AC-to-AC edge the store declares is present in ticket frontmatter) before any ticket work started — a real application of the "two-directional check" discipline this repo's known-issues registers repeatedly call for elsewhere.
- **No phase entered an unresolved retry loop.** Every one of the 15 independently-confirmed blockers in the feedback log was worked to a subsequent `(status: ok)` on the same ticket; zero tickets required brainstorm-lead escalation or a halt.

## Friction Points

- **A handoff whose premise was wrong nearly shipped an unreachable accept path (`ACD-2100c-4`, ticket 17).** `python-coder` implemented the provenance gate honouring a resume answer only when `channel === "person"`, correctly reclassified the resulting 16 sibling-test failures as `test_drift`, and both that reading and the alternative ("nothing ever sets channel: person") predict the identical 16 red tests. Only checking for a real producer distinguishes them. **Nothing in the shipped system mechanically constructs a `resume_answer` with `channel: "person"`** — `templates/commands/plan-feature.md` is a one-line `Workflow("plan-feature", { userInput: $ARGUMENTS })` dispatch with no resume/channel wiring at all; the only place `channel: "person"` is specified is prose the same ticket added to `templates/skills/plan-feature/SKILL.md` ("§RS.3 the provenance obligation"), instructing whichever agent relays a real human decision to set the field itself. The gate's entire security property now rests on an LLM agent following a documented convention, with no runtime check that it did. This was caught only because the drive had independently stalled on a separate, unrelated blocker (a missing `handoff_target` field) that forced a closer look before the 16 tests could be silently rewritten green — see "Proposed Improvements" below.
- **Guard tools reported confidently wrong answers when invoked from outside the worktree root, and the failures were reported as findings rather than as errors.** Per the coordinator's own observation of this drive (not separately visible in ticket Comments): `verify_precommit_active.py` returned `git_hook: false` three times on three different agents purely from a cwd issue (already filed as `KI-CG-20260901-precommit-probe-reports-false-where-it-means-could-not-look`); `check_identifier_uniqueness` and `validate_ac_schema` returned `FAILED (0 inspected)` from the workspace parent; 9 of 11 `commit_guardian` failures were a stale deployment (`ModuleNotFoundError: No module named '_reachability_inventory'`, fixed by `build.py` for 10 of 11); and `ticket_frontmatter_guard` false-fired on every ticket edit in this worktree. This is the mirror image of a pattern this repo's own `CLAUDE.md` already documents three times ("a check that examined nothing must not look like a check that found nothing") — these checks examined the *wrong place* and reported a confident failure rather than a confident pass. No existing rule tells an agent to verify working-directory/deployment-freshness before trusting a guard's *failure* output, only before trusting its *pass* output.
- **A ticket-mandated artifact path went stale over the epic's own multi-week, gap-heavy execution window (`ACD-2100e-1`, ticket 24).** The Implementation Notes (authored 2026-08-26) asserted "c3-005 is the highest c3 number, so c3-006 is free." By the time the ticket executed (2026-09-14, 19 days and two intervening `origin/main` catch-up merges later), c3-006 and c3-007 had both landed on `main` from unrelated epics (PR #495, PR #702), and `check-identifier-uniqueness` is `always_run: true` — committing at the stale path would have blocked every commit in the repo, not just this ticket's. `architecture-diagram-author` correctly refused to pick a replacement number unilaterally (it touches files outside the ticket's declared `files_touched`) and escalated for adjudication; publishing at the allocator's actual answer (c3-008) resolved it. The general risk — any ticket-authoring-time computation of a shared numbered/sequential resource (diagram IDs, migration numbers, port allocations) can go stale by execution time on a long-lived branch — is not yet captured as a standing rule.
- **The malformed pipe-delimited `Agent Contracts` → `### documentation-expert` AC-1 line recurred across at least 5 of the 25 tickets** (01, 02, 12, 20, 23), each caught only at `documentation-verifier` time and requiring a re-dispatch of whatever agent authored/refined the ticket. Already tracked in `docs/known-issues/ac-driven-dev.md` and `docs/known-issues/build-pipeline.md` — flagging here only because of the recurrence rate within a single epic (20% of tickets), which suggests the authoring-time template/skill guidance for that block is still easy to get wrong, not just occasionally wrong.
- **Two known, already-filed AC-tooling gaps surfaced live inside this epic's own last ticket.** `ACD-2100e-2` (`test_required: false`, an L2 AC whose deliverable is a how-to guide) cannot be marked done by `mark_ac_done.py --test-root` per the composite/`test_required` handling gaps already tracked in `docs/known-issues/ac-store.md` (the D-1/D-2 defects in `_verify_composite_eligible`). No new information here beyond confirming the already-filed gap is live and not hypothetical.
- **Cost.** Per the coordinator's own accounting of this drive (not independently re-derivable here — no `debugging/logs/agent_telemetry.jsonl` exists in this worktree to audit token spend against), the epic consumed roughly 13M subagent tokens across 25 tickets, with several individual tickets running close to 2M tokens each. The heaviest tickets by comment volume in this retrospective's own review were the ones with cascading blocker chains (ticket 15 alone: 6 blocker entries plus 3 independent re-reviews) — consistent with, but not proof of, token cost being concentrated in blocker/re-review cycles rather than first-pass implementation. Worth a dedicated look at whether full-suite regression re-runs (several tickets ran 500+ test full-suite sweeps per phase, per test-runner comments) are a major contributor.

## Knowledge Gaps Found

- **`doc_links` status drift is invisible by construction.** Per the coordinator's observation, 35 `doc_links` entries across 26 AC records sat at `status: planned` for up to two weeks after their target documents actually shipped. Nothing validates a markdown-to-markdown cross-link or reconciles a `doc_links` entry's `status` field against whether the target file exists — this is a distinct gap from the already-filed `files_touched`-derived-from-`doc_links` checks in `docs/known-issues/ac-store.md`, which check presence in `files_touched`, not the `status` field's truthfulness. Not yet filed under this shape.
- **The provenance-gate producer contract is convention-only.** See the ticket-17 friction point above. `SKILL.md` now documents the obligation in prose; nothing mechanically distinguishes an agent that actually relayed a human's typed decision from one that fabricated `channel: "person"` to get past the gate. This is a gap in the *class* of AC this repo authors ("a discriminator whose content must not be inspected, only its provenance") — the discriminator's provenance is itself unverified.
- **Route-learning is retired but this retrospective's own protocol still names it.** While preparing the Proposed Improvements section below, `templates/skills/signoff/SKILL.md` §7 was found to state plainly that `route-learning` and `capture-learning` "are retired... neither has ever existed under `templates/skills/` or `.claude/skills/`, and re-introducing either name (under any spelling) is the defect this step exists to close" (ADR-034 §2 item 3). This retrospective agent's own instructions direct it to "load `.claude/skills/route-learning/SKILL.md` and apply the 11-step decision tree" — that file does not exist in this repository. This retrospective substitutes the live `templates/skills/route-knowledge/SKILL.md` decision tree (steps 0–17) for routing the proposals below, and flags the mismatch rather than silently working around it. This is the same class of defect as the epic's own subject matter (a written instruction referencing something that no longer exists) — recommend fixing the retrospective-agent's own protocol separately.

## Unresolved Feedback

There are 164 unresolved feedback entries in feedback.jsonl.
Run `/feedback-review` to triage them before closing the epic branch.

(All 164 entries in this worktree's `feedback.jsonl` belong to this epic and none carry a `resolved_at` value — this may simply mean this worktree has never run `/feedback-review`, not that all 164 need individual triage. Flagging per protocol regardless.)

## Proposed Improvements

### KI-1: Provenance/discriminator ACs must verify a real producer exists, not just consumer logic

**Proposed known-issues entry** (new entry in `docs/known-issues/ac-driven-dev.md`, appended as an addendum note to the existing `KI-ACD-005` "Fix landed" section — **not applied**, `check-doc-length` refuses commits touching this file at its current 1900–4500 line range against a 300-line limit):

```diff
--- a/docs/known-issues/ac-driven-dev.md
+++ b/docs/known-issues/ac-driven-dev.md
@@ KI-ACD-005 (after the "Fix landed 2026-09-14" bullet list)
+
+**Residual gap, not yet filed as its own entry.** The incoming-provenance half's
+entire security property is that `resolveGate()` only honours `resume_answer.channel
+=== "person"`. Nothing in the shipped system *produces* that field mechanically:
+`templates/commands/plan-feature.md` is a one-line `Workflow("plan-feature", {
+userInput: $ARGUMENTS })` dispatch with no resume/channel wiring, and the only
+construction site is prose in `templates/skills/plan-feature/SKILL.md` §RS.3
+instructing an agent to set `channel: "person"` only when genuinely relaying a real
+human's decision. No runtime check distinguishes an agent that followed that
+instruction from one that fabricated the field to pass the gate. During
+`ACD-2100c-4`'s own build, `python-coder` and `test-writer` both correctly reasoned
+about the consumer side and reclassified 16 newly-red sibling tests as `test_drift`
+— but nothing in either agent's reasoning checked whether a producer existed at all,
+and the drive would have shipped this way had it not independently stalled on an
+unrelated blocker first. Recommend: a mechanical companion check (e.g. a
+reachability/producer-audit test asserting at least one real, non-test call site
+constructs `resume_answer.channel` before a ticket closing a provenance-discriminator
+AC is allowed to sign off `ac-fulfillment-gate`).
```

**Also proposed — a general process rule** (new subsection under `## Implementation Conventions` in the worktree-root `CLAUDE.md`, matching this file's existing "Source, sourced-by-date" citation style):

```diff
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ ## Implementation Conventions
+
+### Discriminator ACs — Verify the Producer, Not Just the Consumer
+
+When an AC's Gherkin turns on a field whose *content must not be inspected, only its
+provenance* (e.g. "honour this only when it truly came from the person"), a
+red-to-green test pass on the consumer side is not sufficient evidence the AC is safe
+to ship. Before signing off, confirm a real, already-wired producer sets that field
+under the exact condition the AC requires — grep is not enough; trace the call site.
+Two readings of "the consumer logic is correct" can predict identical test results
+while one of them describes an unreachable accept path with no real producer at all.
+
+**Why this matters:** `ACD-2100c-4` added a `channel === "person"` gate and correctly
+reclassified 16 newly-red sibling tests as test drift — but no code path in the
+shipped system ever constructs `resume_answer.channel: "person"`; the only place it is
+specified is prose in a SKILL.md instructing an agent to add it by hand. Both "this is
+correctly gated" and "this is an unreachable accept path with a convention-only
+producer" predict the same 16 red tests. The gap was caught only because the drive had
+independently stalled on an unrelated blocker first, not because anything in the
+ticket's own verification asked whether a producer existed.
+(Source: EPIC-StartingNewWorkTheProperWayAlways retrospective, 2026-09-14.)
```

Routing: `route-learning` (the skill named in this retrospective agent's own instructions) is retired per ADR-034 §2 item 3 and does not exist under any name in this repository (`templates/skills/signoff/SKILL.md` §7 states this explicitly). Substituting the live `route-knowledge` decision tree (`templates/skills/route-knowledge/SKILL.md`, steps 0–17): the process-rule half matches Step 4/5 ("short-to-medium universal project rule"); this repo's *actual, demonstrated* convention (dozens of existing "## Implementation Conventions" entries, each a full paragraph with a "Why this matters" citation) inlines rules of this length directly rather than spinning off a linked doc, so `CLAUDE.md-inline` is chosen over the generic `CLAUDE.md-toc` threshold. The known-issues-register half has no matching `target_surface` in `route-knowledge`'s 16-value taxonomy at all — known-issues registers are this repo's own established defect-tracking convention, not one `route-knowledge` currently models; flagging that taxonomy gap separately rather than forcing a bad fit.

### KI-2: Guard-tool failures need a working-directory/deployment-freshness sanity check before being trusted as findings

**Proposed CLAUDE.md addendum** (extends the existing "Post-origin/main-merge diff audit" section's closing paragraph, which already documents the *pass*-side version of this pattern three times):

```diff
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ (end of the "Post-origin/main-merge diff audit" section)
+
+**The mirror image also occurred, and is not yet covered by the paragraph above.**
+During EPIC-StartingNewWorkTheProperWayAlways (2026-09-14), `verify_precommit_active.py`
+returned `git_hook: false` on three separate agent dispatches purely because it was
+invoked from outside the worktree root (KI-CG-20260901); `check_identifier_uniqueness`
+and `validate_ac_schema` returned `FAILED (0 inspected)` from the workspace parent; and
+9 of 11 `commit_guardian` failures traced to a stale deployment
+(`ModuleNotFoundError: No module named '_reachability_inventory'`), not real merge
+damage. Each was reported and initially read as a real finding, not as "the check
+couldn't look here." Before acting on a guard tool's FAILURE (not just before trusting
+its pass), confirm it ran from the worktree root against a freshly-built deployment —
+the same discipline this section already prescribes for a clean-looking audit result.
+(Source: EPIC-StartingNewWorkTheProperWayAlways retrospective, 2026-09-14.)
```

Routing: `CLAUDE.md-inline`, same section as the existing pattern it mirrors (Step 4/5 per `route-knowledge`; this repo's demonstrated convention of extending an existing named section rather than creating a new one, since the content is a direct addendum to an already-open "the third time this pattern has appeared" narrative).

### KI-3: Ticket-authored numbered/sequential resource paths must be re-verified at execution time, not trusted from authoring time

**Proposed CLAUDE.md addendum** (new subsection under `## Implementation Conventions`):

```diff
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ ## Implementation Conventions
+
+### Ticket-Mandated Sequential Resource Paths Go Stale on Long-Lived Branches
+
+When a ticket's Implementation Notes hardcode a shared numbered/sequential resource
+(a diagram id, a migration number, an allocated port) computed at ticket-authoring
+time, re-verify the allocation is still free immediately before publishing — do not
+trust the authoring-time computation, especially on an epic that spans multiple
+`origin/main` catch-up merges. Re-run the actual allocator (e.g.
+`scripts/next_diagram_seq.py`) rather than re-reading the ticket's stated number.
+
+**Why this matters:** `ACD-2100e-1`'s Implementation Notes (written 2026-08-26)
+asserted diagram id c3-006 was free. The ticket executed 19 days and two
+`origin/main` merges later (2026-09-14), by which point c3-006 and c3-007 had both
+landed from unrelated epics. `check-identifier-uniqueness` is `always_run: true`,
+so committing at the stale path would have blocked every commit in the repo, not
+just this ticket's. Caught only because `architecture-diagram-author` independently
+re-measured against the real tree before publishing rather than trusting the notes.
+(Source: EPIC-StartingNewWorkTheProperWayAlways retrospective, 2026-09-14.)
```

Routing: `CLAUDE.md-inline`, `## Implementation Conventions` (Step 4/5 per `route-knowledge`, same reasoning as KI-1 — local convention inlines rules of this length).

### KI-4: `doc_links.status` has no validator — proposed new known-issues entry

**Proposed new entry** (new entry in `docs/known-issues/ac-store.md` — **not applied**, same `check-doc-length` block as KI-1):

```diff
--- a/docs/known-issues/ac-store.md
+++ b/docs/known-issues/ac-store.md
@@ (new entry, alongside the existing doc_links / files_touched entries)
+
+### KI-ACS-doc_links-status-not-validated — an AC's `doc_links[].status` field is
+never reconciled against whether its target document actually exists or shipped
+
+- **Severity:** medium
+- **Where:** the AC YAML schema's `doc_links` list (`status: planned` / presumably
+  `delivered` or similar); no validator in `scripts/ac_store/` reads this field.
+- **Symptom.** 35 `doc_links` entries across 26 AC records under
+  EPIC-StartingNewWorkTheProperWayAlways sat at `status: planned` for up to two
+  weeks after their target documents actually shipped. Nothing validates a
+  markdown-to-markdown cross-link or reconciles a `doc_links` entry's `status`
+  against the target file's existence — this class of drift is invisible by
+  construction, the same shape as the AC-store hygiene gaps already filed in this
+  register, but on a field none of those checks read.
+- **Distinct from:** the existing `files_touched`-has-N-paths-from-`doc_links`
+  checks in this same file, which verify presence in `files_touched`, not the
+  truthfulness of the `status` field itself.
+(Source: EPIC-StartingNewWorkTheProperWayAlways retrospective, 2026-09-14.)
```

Routing: no clean `route-knowledge` surface match (known-issues registers are not in its 16-value taxonomy). Following this repo's own established convention (dozens of precedent entries in `docs/known-issues/ac-store.md`), not a generic `route-knowledge` step. Flagging the taxonomy gap: `route-knowledge`'s decision tree should probably gain a `known-issues` surface given how central this convention is to the project.

### Process note: this retrospective's own protocol names a retired skill

Not a diff to apply, but worth surfacing to whoever maintains the `retrospective-agent` template: its Step 5 instructs loading `.claude/skills/route-learning/SKILL.md` and applying an "11-step decision tree." That file does not exist in this repository (confirmed via `find`), and `templates/skills/signoff/SKILL.md` §7 states `route-learning` was retired by ADR-034 and never existed under `templates/skills/` or `.claude/skills/` under any spelling. This retrospective substituted `route-knowledge`'s live 18-step (0–17) tree instead and flagged every routing decision above accordingly. Recommend updating `retrospective-agent`'s own template to name `route-knowledge` (or whatever surface succeeds it) directly.
