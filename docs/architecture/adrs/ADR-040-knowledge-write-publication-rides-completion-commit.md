---
title: "ADR-040: Knowledge-Write Publication Rides the Completion Path's Own Commit"
description: "A routed knowledge write is published by the completion path's own existing commit, in the normal worktree PR alongside the work that produced it. The decision is forced by INF-700a-5's commit-count acceptance test, not selected on preference."
type: "adr"
status: "active"
created: "2026-09-07"
last_updated: "2026-09-07"
deciders:
  - BrainCandy
components:
  - knowledge_system
  - infrastructure
  - build_pipeline
  - finalize
related_docs:
  - docs/architecture/adrs/ADR-011-learning-emission-sink.md
  - docs/architecture/adrs/ADR-034-knowledge-write-ownership.md
  - docs/architecture/agent_knowledge_system.md
  - docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-5.yaml
  - docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-1.yaml
related_code:
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/quick-fix.js
  - templates/workflows-js/finalize-feature.js
  - scripts/knowledge/harvest_learnings.py
  - templates/agents/knowledge-harvester.md
---

# ADR-040: Knowledge-Write Publication Rides the Completion Path's Own Commit

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-09-07 |
| Deciders | BrainCandy |
| Author | Written during the INF-700 knowledge-loop plumbing spec pass of 2026-09-07 |
| Supersedes | None |
| Context ADRs | [ADR-011](ADR-011-learning-emission-sink.md) (emission sink) and [ADR-034](ADR-034-knowledge-write-ownership.md) (write ownership) — this ADR fills a gap both left open; it supersedes neither |
| Forced by | [`INF-700a-5`](../../acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-5.yaml) — see §Revisiting this decision |

## Context

Three questions have to be answered before a captured learning is durable: **where is it
emitted**, **who writes it**, and **how does that write reach the tree a human will read it
in**. The first two are on the record. The third was not, and its absence was invisible
because the two ADRs that surround it each stop just short of it.

- **[ADR-011 — Learning Emission Sink](ADR-011-learning-emission-sink.md)** decided the
  emission *sink*: `debugging/logs/knowledge_emissions.jsonl` rather than reusing
  `agent_telemetry.jsonl`. It is silent on publication. It says nothing about how a routed
  write reaches the merged tree.
- **[ADR-034 — Knowledge Write Ownership](ADR-034-knowledge-write-ownership.md)** decided
  *who writes*: the harvester (`scripts/knowledge/harvest_learnings.py`), not the emitting
  agent. It is explicitly silent on how that write reaches `main`. Its own §2
  "Consequences that follow mechanically" flags the gap in one line — *"The harvester needs
  a caller. Until it has one, it is manual-invoke"* — without specifying how the caller's
  writes get published.

The gap survived three months and a full spec pass across both ADRs. It was answered only
**by implication**, in the prose of an acceptance criterion:
[`INF-700a-5`](../../acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-5.yaml),
via its second test descriptor
`test_a_unit_of_work_produces_the_same_number_of_commits_with_and_without_records_to_route`
(verified present in that file's `test_spec` at line 95). Nobody had weighed the consequence
directly until asked.

The reasoning is no longer local to one AC. It governs how **five** different completion-path
workflow scripts must be wired, and it is already being cited as precedent by sibling ACs —
[`INF-700a-1`](../../acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-1.yaml)'s
amendment history references it directly. A cross-cutting rule that five scripts must obey
and that siblings already cite belongs in a citable architectural record, not in an AC's
`notes` field.

**The cost of not deciding** is therefore already being paid: each of the five completion
paths would otherwise be wired by a different implementer reasoning independently about the
same question, and four of them have no merge step of their own to fall back on.

## Decision

### 1. Knowledge writes MUST ride the completion path's own existing commit

A routed knowledge write MUST be published by the commit the completion path already makes.
Learnings therefore land in the **normal worktree PR, alongside the work that produced
them**. The routing step MUST NOT create a separate commit, MUST NOT create a separate
branch, and MUST NOT open a separate pull request.

"Written" means **published**, not written-somewhere: a routing write that is not carried by
a commit that reaches the merged tree does not count as written, and the record MUST remain
eligible for a later run.

### 2. The dispatch surface is `templates/workflows-js/`, not the deployed copies

The routing/harvest dispatch MUST be wired into the workflow sources under
`templates/workflows-js/`. It MUST NOT be wired into the deployed `.claude/workflows/`
copies, which `build.py` overwrites. Per `INF-700a-1`'s `it_requirements`, the templates
directory is the correct source-of-truth surface.

### 3. Dispatch is uniform in principle, path-specific only in placement

The *rule* is uniform across all five completion paths: dispatch the routing/harvest step
immediately before that path's own publishing commit, so the routing writes are staged into
the same commit or fall inside the same pre-publication window.

The *edit* is not uniform, and §2's "the dispatch surface is `templates/workflows-js/`"
holds for four paths, not five. `build-epic.js` drives its phases through the
`ticket-supervisor` agent, whose ordering lives in a skill
(`templates/skills/building-epics/SKILL.md` §2.1.1), so that path is wired there instead.
Both surfaces are source-of-truth surfaces that `build.py` deploys from; neither is a
deployed copy.

| Completion path | Dispatch immediately before | Verified at |
|---|---|---|
| `build-ticket.js` | The `commit` iteration of the dispatch loop that begins at line 1258, guarded to run once per drive. **NOT the `phaseOrder` array** — see the note below | loop at line 1258 |
| `build-epic.js` | Its own change, in `templates/skills/building-epics/SKILL.md` §2.1.1 (line 608). **It does not inherit `build-ticket.js`'s wiring** — see the note below | line 388; table at SKILL.md:608 |
| `fast-lane-ship.js` | The named `agentType: "commit"` dispatch | `agent(...)` call begins at line 1371; phase comment at line 1362 reads "Phase 5 — Commit: mark ACs done + commit on the worktree branch" |
| `quick-fix.js` | The **first** (fix) commit — `const commitResult = await agent(`, staging the fix plus the parent AC back-link. Explicitly **NOT** the later changelog commit | line 894 |
| `finalize-feature.js` | Step 3.5's closure commit — `` git -C ${WORKTREE_ROOT} commit -m 'chore(tickets): close tickets and source ACs' `` | line 1646 |

All line references above were verified directly against the files on this branch. They are
verified, not asserted.

**The first two rows were wrong in this ADR's first draft, and the way they were wrong is
worth recording.** Both cited real, correctly-numbered lines. A line number is not a
mechanism, and verifying the former does not verify the latter.

- **`phaseOrder` is a sort key, not a dispatch list.** Line 1182 sorts
  `orderedPhases.filter((p) => p.status === "needed")`, and `orderedPhases` is
  `plan.ordered_phases` (line 1142) — produced by the **planner agent reading the ticket's
  own `agents:` frontmatter map** (line 1129). `phaseOrder` only orders phases a ticket
  already declares. It cannot introduce one.
  Nothing will ever declare this phase: `config/agent_registry.json:3363-3364` gives
  `knowledge-harvester` `is_ticket_phase: false` and `selection_criteria: null`. So an
  insert into `phaseOrder` would route **nothing**, while appearing correct in the diff and
  passing any structural test that greps for its presence.
  That is precisely the `fast-lane-build.js` phantom-done shape this repo has a standing
  convention about ("Gate / Workflow ACs — Verify Behaviorally, Not by Grep"), and it was
  about to ship *inside the fix for the knowledge loop*. It is also the second instance of
  the same registry error in this AC family — the IT PO caught the identical mistake for
  `workflow-architect` on `INF-700a-1`.
- **`build-epic.js` inherits nothing.** Line 388 dispatches the **`ticket-supervisor`
  agent**, not `build-ticket.js`. That agent drives its phases from a second, independent
  ordering table in `templates/skills/building-epics/SKILL.md` §2.1.1 (line 608). Wiring
  only `build-ticket.js` would leave every epic drive unwired while single-ticket tests
  stayed green — the partial-wiring failure `INF-700a-1-i` exists to catch.

Both errors were found by the IT PO during technical enrichment, by reading the dispatch
mechanism rather than the line. Recorded here rather than silently corrected, because the
failure mode — a verified line number standing in for an unverified mechanism — is the one
this ADR's own subject matter is meant to defend against.

**Precision note for `quick-fix.js`.** That file contains three nearby agent calls and only
one of them is the correct anchor. The changelog-*authoring* agent call (non-commit) ends
around line 960; the changelog **commit** agent call is separate, at lines 977–988
(`agentType: 'commit'`, label `'commit/changelog'`). The routing dispatch belongs before the
line-894 fix commit and MUST NOT be attached to either changelog-related call.

### 4. Publication choice is bound to `INF-700a-5`, not to this ADR alone

This ADR records a decision that is **forced** by an already-approved acceptance criterion.
It MUST NOT be treated as a discretionary preference that a later reader can re-weigh. See
§Revisiting this decision.

## Consequences

### Positive

- **The loop actually closes.** ADR-034 left the harvester without a caller; §3 above gives
  it five, each anchored to a commit that already exists and already reaches a PR. No new
  publication machinery is introduced.
- **Zero added commit surface.** The branch's commit count is identical whether or not there
  was anything to route, which is exactly what `INF-700a-5`'s commit-count test asserts.
- **No new blast radius on commit delegation.** The routing step never calls `git commit`
  itself, so it stays clear of `enforce_commit_delegation` and of this repo's rule that all
  commits go through the `commit` agent.
- **Review is preserved by construction.** Learnings land in a reviewed PR rather than in an
  unattended write to a tracked file.

### Negative

- **Content mixing is an accepted, inherent cost.** A PR titled e.g. *"fix the harvester's
  exit codes"* will also carry an unrelated memory-file or doc edit in the same commit and
  the same PR, because that is the mechanism. **Review guidance:** reviewers of any PR
  produced by a completion path should expect one or more knowledge-surface edits unrelated
  to the PR's stated subject, and should review them as knowledge content rather than as
  scope creep. This is stated here so it is an expectation rather than a recurring surprise.
- **Attribution through `git log` is coarse — and this is a cost of every real option, not
  of this one.** `git log` on a memory file answers "which feature was running when this
  landed", not "what was learned and why". If per-learning attribution matters, it belongs
  in each record's own frontmatter — the `created`/`by`/`at` convention already used in AC
  amendment records is the available precedent — and MUST NOT be inferred from commit
  metadata.
- **`finalize-feature.js`'s step 3.5 is the weakest of the five carriers.** That unattended
  closure commit has documented prior history of flipping ACs store-wide rather than
  per-epic (the project's "Finalize step 3.5 cross-epic closure bug" precedent). Step 3.5 is
  accepted as the chosen mechanism for that path **for now**, but it warrants its own
  hardening follow-up given that history. This ADR does not fix that pre-existing weakness;
  it adds one more thing riding on the same commit.

### Operational

- **Loss-on-abandonment is closed BY DESIGN, but NOT YET by code.** `INF-700a-5` includes a
  merge-conditional re-routing requirement — a record routed on a branch that never merges
  MUST be routed again by a later run, covered by
  `test_a_record_routed_on_a_branch_that_never_merges_is_routed_again_by_a_later_run` (line
  107 of that file). That closes the "PR is abandoned, learning is lost but marked routed"
  failure mode **at the specification level**. It is contingent on a manifest/bookkeeping
  mechanism that `harvest_learnings.py` does not yet implement (per `INF-700a-5`'s amendment
  history and its `-iii` L3 child). **The remaining gap is in the CODE, not in the option
  chosen here.** The publication choice recorded in §1 neither introduces nor resolves that
  gap; it relies on a bookkeeping fix that is tracked and pending elsewhere.
- **The concurrent-write race is named, tracked, and UNRESOLVED.**
  [`INF-700a-5-iii`](../../acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-5-iii.yaml)
  covers parallel drives racing on the same shared sink and bookkeeping — routine here
  rather than theoretical. Its status is **specified, not yet resolved**. It is recorded
  explicitly rather than silently omitted.
- **Review-semantics drift is solved by NONE of the options, including this one.** The
  existing corpus already carries **15 inconsistent `entry_kind` values across 28 records**
  (verified in `INF-400c-4.yaml`'s amendment history, line 116: *"the existing 28 records
  already carry 15 inconsistent entry_kind values, so unreviewed agent prose landing on
  memory files is how those files fill with near-duplicates"* — the cited examples are
  variant pairs such as `agent-memory`/`agent_memory` and `framing-note`/`framing_note`). A
  separate PR would attract exactly as little reviewer scrutiny as a mixed one. Riding the
  existing commit does not make this worse, and it does not make it better. **Choosing where
  writes are published does not address `entry_kind` hygiene.** That needs pre-write
  validation inside the harvester itself and belongs to its own AC family —
  `INF-400c-5`'s normalization family already exists for it.

## Alternatives

These are **not costlier options weighed against the chosen one**. They are **structurally
excluded** by an already-existing, already-approved acceptance test and an already-existing
branch-protection rule. Each is marked FORECLOSED, with the mechanism that forecloses it.

- **Separate branch plus its own PR per unit of work. FORECLOSED.** It fails
  `INF-700a-5`'s `test_a_unit_of_work_produces_the_same_number_of_commits_with_and_without_records_to_route`
  by construction. **Any** incremental commit fails that test — including an extra commit
  inside the same PR — because the test asserts the branch's commit count is *identical*
  whether or not there was anything to route. The requirement exists for durability reasons:
  an implementation must not be able to satisfy "the learning is durable" by adding an
  unattended commit. `INF-700a-5`'s notes reject the adjacent shape independently and on a
  second ground: rejected-alternative #1 ("a new commit inside the routing step") is
  rejected on `enforce_commit_delegation` grounds — this repo requires all commits to go
  through the `commit` agent, and a workflow that silently commits during a teardown
  sequence is a blast-radius change, not a wiring detail. Separately, `pull-request` (the
  agent governing PR creation) is not built to open an independent branch on its own
  initiative, so a separate knowledge PR would require unverified new machinery rather than
  reuse of anything that exists.
- **Batched periodic knowledge PR. FORECLOSED.** It fails the same commit-count test by the
  same construction. It also has no precedent anywhere in this codebase: `changelog-agent`
  and `retrospective-agent` were both checked as candidate templates for a "batch periodic"
  pattern and both ruled out — `changelog-agent` runs per-completion rather than batched,
  and `retrospective-agent` is user-approval-gated and writes nothing itself (ADR-034
  Option C).
- **Direct commit to `main`. FORECLOSED — moot, not merely risky.** Branch protection
  rejects any direct push to `main` with
  `GH013: Required status check "Lint (ruff)" is expected` — the same ruff-ruleset gate
  documented project-wide as "main is PR-only". There is no code path by which an unattended
  process can land a commit on `main` without going through a PR and its required checks.

No fourth option was seriously considered, because the first three exhaust the design space
and all three are excluded by rules that already exist.

## Revisiting this decision

This ADR is a **forced-by-AC** record, and it must read differently from an ordinary
discretionary ADR. The choice in §1 was not selected from among comparably-viable options on
preference or engineering taste; it is the only option that survives `INF-700a-5`'s
commit-count test and `main`'s branch protection.

Therefore: **this decision can only be revisited by first changing `INF-700a-5`'s own
acceptance test.** Re-litigating the ADR in isolation — for example because a future reader
dislikes the content-mixing cost recorded under Consequences → Negative — cannot change the
outcome, because the constraint does not live here. Any proposal to publish knowledge writes
some other way MUST begin with an amendment to
[`INF-700a-5`](../../acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-5.yaml)
and MUST state which durability property is being traded away in exchange.

## References

- [ADR-011 — Learning Emission Sink](ADR-011-learning-emission-sink.md) — decided the
  emission sink; silent on publication.
- [ADR-034 — Knowledge Write Ownership](ADR-034-knowledge-write-ownership.md) — decided that
  the harvester writes; explicitly silent on how that write reaches `main`. Its §2
  "Consequences that follow mechanically" flags "the harvester needs a caller".
- [`docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-5.yaml`](../../acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-5.yaml)
  — the forcing AC: the commit-count test, the merge-conditional re-routing requirement, and
  the rejected-alternatives list this ADR draws on.
- [`docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-1.yaml`](../../acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-1.yaml)
  — establishes `templates/workflows-js/` as the source-of-truth dispatch surface; its
  amendment history cites this decision as precedent.
- [`docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-5-iii.yaml`](../../acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-5-iii.yaml)
  — the concurrent-write race: specified, not yet resolved.
- [`docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-400c-4.yaml`](../../acceptance-criteria/infrastructure/INF-400-agent-learning/INF-400c-4.yaml)
  — source of the "15 inconsistent `entry_kind` values across 28 records" figure.
- `templates/workflows-js/build-ticket.js`, `build-epic.js`, `fast-lane-ship.js`,
  `quick-fix.js`, `finalize-feature.js` — the five completion paths bound by §3.
- `scripts/knowledge/harvest_learnings.py` — the writer, per ADR-034; owner of the pending
  bookkeeping mechanism noted under Consequences → Operational.
