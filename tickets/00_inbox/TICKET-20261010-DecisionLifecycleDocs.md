---
title: "Decision lifecycle documentation: six DK-600 diagrams, two how-tos and the decision-record reference"
status: todo
components:
  - decision_kernel
created: 2026-10-10
last_updated: 2026-10-10
depends_on: []
priority: high
roadmap_phase: phase_1
change_target: docs
risk_surface: internal
complexity: medium
requires_diagram: true
requires_adr: false
documentation_required: true
requires_documentation_verification: true
ac_limit_override: true
source_ac:
  - DK-600a-5
  - DK-600b-4
  - DK-600b-5
  - DK-600c-5-i
  - DK-600c-5-ii
  - DK-600d-5-i
  - DK-600d-5-ii
  - DK-600d-5-iii
  - DK-600e-5
files_touched:
  - docs/architecture/diagrams/c3-024-decision-kernel-flows-forming-round.md
  - docs/architecture/diagrams/c3-025-decision-kernel-flows-decision-states.md
  - docs/architecture/diagrams/c3-026-decision-kernel-flows-record-staging.md
  - docs/architecture/diagrams/c3-027-decision-kernel-flows-record-publishing.md
  - docs/architecture/diagrams/c3-028-decision-kernel-flows-record-lifecycle.md
  - docs/architecture/diagrams/c3-029-decision-kernel-flows-precedent-reuse.md
  - docs/architecture/diagrams/c2-007-decision-kernel-flows-overview.md
  - docs/architecture/components/decision-kernel.md
  - docs/how-to/answer-the-decision-kernel-questions.md
  - docs/how-to/run-the-decision-kernel.md
  - docs/how-to/file-and-reuse-decisions-with-the-kernel.md
  - docs/reference/decision-record.md
  - docs/acceptance-criteria/decision-kernel/DK-600-decide-once-reuse/DK-600a-5.yaml
  - docs/acceptance-criteria/decision-kernel/DK-600-decide-once-reuse/DK-600b-4.yaml
  - docs/acceptance-criteria/decision-kernel/DK-600-decide-once-reuse/DK-600b-5.yaml
  - docs/acceptance-criteria/decision-kernel/DK-600-decide-once-reuse/DK-600c-5-i.yaml
  - docs/acceptance-criteria/decision-kernel/DK-600-decide-once-reuse/DK-600c-5-ii.yaml
  - docs/acceptance-criteria/decision-kernel/DK-600-decide-once-reuse/DK-600d-5-i.yaml
  - docs/acceptance-criteria/decision-kernel/DK-600-decide-once-reuse/DK-600d-5-ii.yaml
  - docs/acceptance-criteria/decision-kernel/DK-600-decide-once-reuse/DK-600d-5-iii.yaml
  - docs/acceptance-criteria/decision-kernel/DK-600-decide-once-reuse/DK-600e-5.yaml
agents:
  status-checker: not_needed
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  documentation-expert: not_needed
  architecture-diagram-author: signed_off
  how-to-author: signed_off
  reference-author: signed_off
  documentation-verifier: signed_off
  commit: signed_off
  pull-request: needed
---

# Decision lifecycle documentation: six DK-600 diagrams, two how-tos and the decision-record reference

## Actor / Goal

As a person who runs decisions through the kernel, I want the decision lifecycle documented end to end: how a
round forms, how I answer its two questions, what a staged record holds, how I publish or correct it, and how
a published record comes back as precedent. Then I can follow, check and explain each step without reading
the code. This ticket delivers the nine open DK-600 documentation ACs in one build.

## Context

- **Decision.** Kernel decision `dec-ea83c3989d1b7199` (the user's choice, published in `docs/decisions/`):
  the two DK-600 code ACs (DK-600a-3, DK-600e-3-i) go through the fast lane separately. The nine documentation
  ACs go into this one hand-authored ticket. It is built by `/build-feature` with the leaf documentation
  authors, and `documentation-verifier` checks it.
- **ADR-036** (`docs/architecture/adrs/ADR-036-documentation-dispatch-caller-boundary.md`): an AC's
  `assigned_agent` names the leaf author, never `documentation-expert`. On 2026-10-10 DK-600b-4 and
  DK-600d-5-i were reassigned to `how-to-author`, and DK-600c-5-i to `reference-author`. That is why
  `documentation-expert` is `not_needed` here; it is only the heading the verifier parses below.
- **Done-proof waiver.** All nine ACs carry `test_required: false` with a non-empty `test_rationale`
  (user-approved amendment, 2026-10-10). That is the conjunction `is_covers_tag_waived`
  (`scripts/ac_store/_done_proof_phase_helpers.py`) accepts. So `mark_ac_done.py --test-root` and the
  `check-done-proof` hook let each AC reach `done` with no covers-tagged test. A dry run on 2026-10-10 said
  "would mark ... done" for the ACs it was tried on. DK-600b-4 and DK-600c-5-i lost their planned
  `test_spec`, because `check-ac-schema` rejects a `test_spec` next to `test_required: false`. The checks
  those tests carried are now done by their authors during this build (see Producer instructions).
- **Starting material on main:** `docs/how-to/run-the-decision-kernel.md`,
  `docs/how-to/file-and-reuse-decisions-with-the-kernel.md`, and diagrams c3-013, c3-014, c3-015 and c3-020
  under parent `docs/architecture/diagrams/c2-007-decision-kernel-flows-overview.md`. The flows are in
  `docs/product-truth/flows/leafcutter/decision-{forming,staging,publishing,retrieval}.flow.json`.
- **Code ACs still in flight in the fast lane:** DK-600a-3 (a finding citing an evidence id the kernel did
  not hand over is refused; branch `fast-lane/dk-600a-3`) and DK-600e-3-i (the run's publish instruction
  carries `--correct`; branch `fast-lane/dk-600e-3-i`). This ticket never changes code. If they have merged
  to main when this builds, merge `origin/main` first and document them as built. Otherwise mark them as not
  built.
- **Why `ac_limit_override: true`.** `documentation-verifier` reads its required-docs list only from the
  `### documentation-expert` block, so all nine contract lines sit under that one heading. That is more than
  `check-ticket-ac-limits` allows per agent (7). The real load per producer is 6 / 2 / 1. Splitting the
  ticket would undo the decision above. IT-PO reviewed and accepted the override on 2026-10-10 (reasoning in
  Comments).
- **`source_ac` is a list** (the nine ids). `build-feature.js` reads it as a list. `finalize-feature`'s
  closure step calls `mark_ac_done.py --ticket`, which reads one id only. It will log a non-fatal
  "not found" warning, which is expected, because this ticket marks each AC done itself (see "Closing each
  AC").

## Scope

| # | AC | Target file (new unless noted) | Producer | Also touches |
|---|----|--------------------------------|----------|--------------|
| AC-1 | DK-600a-5 | `docs/architecture/diagrams/c3-024-decision-kernel-flows-forming-round.md` (sequence) | architecture-diagram-author | c2-007 `children:`, `docs/architecture/components/decision-kernel.md` link |
| AC-2 | DK-600b-5 | `docs/architecture/diagrams/c3-025-decision-kernel-flows-decision-states.md` (state) | architecture-diagram-author | same |
| AC-3 | DK-600c-5-ii | `docs/architecture/diagrams/c3-026-decision-kernel-flows-record-staging.md` (sequence) | architecture-diagram-author | same |
| AC-4 | DK-600d-5-ii | `docs/architecture/diagrams/c3-027-decision-kernel-flows-record-publishing.md` (sequence) | architecture-diagram-author | same |
| AC-5 | DK-600d-5-iii | `docs/architecture/diagrams/c3-028-decision-kernel-flows-record-lifecycle.md` (state) | architecture-diagram-author | same |
| AC-6 | DK-600e-5 | `docs/architecture/diagrams/c3-029-decision-kernel-flows-precedent-reuse.md` (sequence) | architecture-diagram-author | same |
| AC-7 | DK-600b-4 | `docs/how-to/answer-the-decision-kernel-questions.md` | how-to-author | `docs/how-to/run-the-decision-kernel.md` ("recorded only" correction, link) |
| AC-8 | DK-600d-5-i | `docs/how-to/file-and-reuse-decisions-with-the-kernel.md` (exists; extend) | how-to-author | none |
| AC-9 | DK-600c-5-i | `docs/reference/decision-record.md` | reference-author | `docs/how-to/file-and-reuse-decisions-with-the-kernel.md` ("What a record holds" table becomes a link) |

Each AC YAML is the spec. Its `criteria` (Gherkin) and `it_requirements` are binding, and its last
`it_requirements` line records the target file above. The ACs live in
`docs/acceptance-criteria/decision-kernel/DK-600-decide-once-reuse/`.

## Out of Scope

- Any code, test or config change, including DK-600a-3 and DK-600e-3-i (fast lane).
- Committed tests for the docs. `test_required: false` on all nine, by user decision.
- Closing the composite parents DK-600c-5 and DK-600d-5, or the L1s DK-600a to DK-600e.
- Editing the write-c4-diagram skill or any agent template.

## Producer instructions

The phases run in this order: architecture-diagram-author (3), then how-to-author (10), then
reference-author (10, after how-to-author), then documentation-verifier (11.9), commit (12) and
pull-request (13). Every producer:

- reads its AC YAML first;
- states only behaviour that a test proves on main, and marks anything else "not built";
- copies names, commands and messages from the code (`kernel/`), never from memory;
- `git add`s each file as soon as it is written. Untracked files have vanished in shared worktrees before.

### architecture-diagram-author: AC-1 to AC-6

Owns DK-600a-5, DK-600b-5, DK-600c-5-ii, DK-600d-5-ii, DK-600d-5-iii and DK-600e-5.

1. **Check the numbers first.** `scripts/next_diagram_seq.py 3` said 23 on 2026-10-10, but c3-023 is
   taken: `c3-023-decision-kernel-split-components.md` is on the open branch
   `epic/abundled-request-that-routing-turns-away-is`. That is why this ticket uses c3-024 to c3-029.
   Re-check open branches (`git ls-tree` on each `origin/*`) for c3-024 to c3-029. If a number is taken,
   take the next free one. In the same change, update that AC's Agent Contracts line below and the
   target-file line in the AC's `it_requirements`.
2. **Frontmatter for each file:** `flight_level: L3-Component` and `diagram_type: sequence` or `state`, per
   the Scope table. Set `parent: docs/architecture/diagrams/c2-007-decision-kernel-flows-overview.md`,
   `components: [decision_kernel]`, `source_ticket:` set to this ticket's path, and a one-sentence
   `description:`. Take the shape of c3-014 (sequence) or c3-015 (state).
3. **Links:** add every new file to c2-007's `children:` list. Add a link to each from
   `docs/architecture/components/decision-kernel.md`. Extend or link c3-013, c3-014 and c3-020 rather than
   redrawing their messages.
4. **Per AC** (the full rules are in each AC's `it_requirements`):
   - **DK-600a-5:** the order is the decision graph's: load, precedent, validate_basis, assess, combine,
     emit. Draw the budget-reserve exit from `budget_gate.handover` and `fallback_followup`. Draw DK-600a-3's
     citation check as not built unless it has merged.
   - **DK-600b-5:** the states map to the continuation phases `awaiting_approval`,
     `awaiting_design_choice` and `resolved`. Cancelled, or left waiting, is the unresolved end. DK-600b-2-ii
     is `done` on main. Confirm its test passes before drawing the words-answer re-rank as built.
   - **DK-600c-5-ii:** the no-approval exit sits where `builder._approval` refuses. No arrow reaches the
     repository.
   - **DK-600d-5-ii:** both exit-code-3 stops end before any write, because `publish.publish` validates
     first.
   - **DK-600d-5-iii:** a superseded record is still found and cited as evidence. It is only never offered
     for reuse (DK-600e-3-iii). Label superseded "kept on record, corrections appended only".
   - **DK-600e-5:** name the thresholds by config key: `memory.max_precedents`,
     `memory.applies_threshold` and `memory.reuse_threshold`.
5. **Checks before sign-off:** `check_doc_frontmatter`, `check_mermaid_parent_link`,
   `check_mermaid_complexity`, `check_diagram_naming` and `check_doc_links`, all on the changed files.
6. **Close AC-1 to AC-6** (see "Closing each AC").

### how-to-author: AC-7 and AC-8

Owns DK-600b-4 and DK-600d-5-i.

- **DK-600b-4:** write the new task-oriented how-to `docs/how-to/answer-the-decision-kernel-questions.md`,
  beside `run-the-decision-kernel.md`. Link to that file for reference detail instead of copying it.
  - Cover the approval question: approve all, approve a subset, reword a criterion, add an option. State
    that `edited_criteria` replaces the whole proposed set, and that `approved_criterion_ids` is ignored when
    `edited_criteria` is present.
  - Cover the ranked-choice question: choose, add an option (which leads to a new ranking), or answer in
    your own words.
  - State that the ranking is advice, the decision waits for the person's choice, and leaving or cancelling
    keeps no record.
  - In `run-the-decision-kernel.md`, correct "answer in words (recorded only)" in Step 5. DK-600b-2-ii is
    done on main: confirm its test passes before stating the words re-rank.
  - Every answer example must be accepted by the kernel exactly as written. Check each one with a scratch
    script outside the repo against `kernel/schemas/leafcutter.human_answer.v1.schema.json` and the
    semantic checks in `kernel/interaction/submissions.py`. Name the command and its result in your
    sign-off comment.
- **DK-600d-5-i:** extend `docs/how-to/file-and-reuse-decisions-with-the-kernel.md`. Do not write a second
  publishing how-to. Check and fill the four clauses of the criteria:
  - publish with `--run-id`, what is checked before any write, the two files a publish changes (the record
    and the index), and the commit and PR that follow;
  - `--correct` with a reason, and that the older record is only appended to;
  - the fix for each exit-code-3 stop, with the exact messages from `kernel/memory/cli.py` and
    `kernel/memory/publish.py`;
  - that an unpublished record is never found as precedent.

  Link c3-026, c3-027 and c3-028. Do not say that a run's own publish instruction carries `--correct`
  unless DK-600e-3-i has merged.
- Close AC-7 and AC-8 (see "Closing each AC").

### reference-author: AC-9

Owns DK-600c-5-i.

- Write `docs/reference/decision-record.md`, a lookup reference that uses `dec-d53e1c52cd47c832` as the
  example. It lists every part of the record: identity, question, filters, answer, evidence, authority,
  provenance, and the append-only corrections. It states that:
  - evidence is held as locators and content hashes, never as text;
  - only a decision a human approved, with an approval time, produces a record.
- The field list must match `config/decision_record.schema.json` in both directions: every schema
  property (recursively) is named, and every named field is in the schema. Check it with a scratch script
  outside the repo, and name the command and its result in your sign-off comment.
- Replace the "What a record holds" table in `docs/how-to/file-and-reuse-decisions-with-the-kernel.md`
  with a link to the reference. how-to-author has already edited that file; work on top of its changes.
- Close AC-9 (see "Closing each AC").

### Closing each AC: every producer, for its own ACs, after its doc is written and staged

`mark_ac_done.py` writes only `work_status`; it never writes `implemented_by` (KI-ACS-004). So the
producer sets `implemented_by` itself:

1. In the AC YAML, replace only the line `implemented_by: []` with a one-item list naming the AC's target
   file from the Scope table, for example `implemented_by:` followed by
   `  - docs/reference/decision-record.md`. Touch no other field.
2. Run `python scripts/ac_store/mark_ac_done.py --ac <AC id> --ac-root docs/acceptance-criteria --test-root tests/kernel`.
   It takes about a minute per AC and must print `marked <AC id> work_status=done`. Exit 3 means the waiver
   did not apply. Stop with a blocker; do not edit `work_status` by hand.
3. `git add` the AC YAML.

### documentation-verifier

This is the standard check of the `## Agent Contracts` block below. The nine contract files are the
required docs.

### commit

1. **Check the ACs first.** Read the nine AC YAMLs. Each must show `work_status: done` and an
   `implemented_by` that names its contract file. If one does not, return a blocker naming the producer
   that owns it. Never mark an AC done in this phase. Also read two sign-off comments. The how-to-author
   comment must name the command and result of the answer-example check (DK-600b-4). The reference-author
   comment must name the command and result of the schema-parity check (DK-600c-5-i). documentation-verifier
   checks only that each file changed and has no placeholders; it does not re-run either check. If a record
   is missing, return a blocker naming that producer.
2. **Add one changelog entry** under `changelogs/` (`scripts/changelog/emit_entry.py`). The CI check
   "Changelog entry present" is required, and `/build-feature` does not add one.
3. **Stage only this ticket's paths:** the `files_touched` list, the changelog entry, this ticket, and
   `docs/INDEX.md` if a hook regenerates it. Leave `docs/agents/cards/*` and any other bootstrap drift
   unstaged.
4. Never `--no-verify`.

### pull-request

One PR for the nine ACs. Its body cites `dec-ea83c3989d1b7199` and lists AC → file.

## Scaffold-free pass: the user must authorise it before the diagram phase runs

`scripts/scaffold/new_arch_doc.py` has never existed in this repository. Section 4 of the write-c4-diagram
skill, and the architecture-diagram-author template, tell the author to stop when it is missing.

The user's standing pass, `dec-b10271ebb40b9eaa` (approved 2026-10-10), is published on the branch
`epic/abundled-request-that-routing-turns-away-is` and is not yet on main. The standing pass it adopts is
titled "every blocked diagram until a scaffold exists". That option's text names only DK-400c-4, DK-400c-5,
DK-400d-5, DK-400e-5 and BO-1800f-3.

**Status when this ticket was written: not authorised for AC-1 to AC-6.** Before `/build-feature` runs,
the user either confirms that the pass covers DK-600a-5, DK-600b-5, DK-600c-5-ii, DK-600d-5-ii,
DK-600d-5-iii and DK-600e-5, or the diagram phase stops with a blocker, as its template requires. Write the
authorising decision id on the next line when it exists.

Authorising decision: `dec-b10271ebb40b9eaa`, the user's standing decision (approved 2026-10-10T09:45:36Z by
human:user; chosen option `opt.pass_until_scaffold_and_schedule`, "the same standing pass, plus a ticket now
that schedules INF-1300"): a recorded scaffold-free pass for every blocked diagram until a scaffold exists.
Recorded 2026-10-10 by it-po.

- **Scope.** The chosen option adopts the standing pass `opt.pass_until_scaffold`, titled "authorise the same
  recorded pass for every blocked diagram until a scaffold exists". The DK-400 and BO-1800 ids in that option's
  text are the diagrams that were blocked when the decision was taken. AC-1 to AC-6 are blocked by the same
  missing script, so they fall under the title's scope. The pass ends when INF-1300's scaffold ships.
- **Where to read it.** The record is not on main or origin yet. It is in commit `ac5a5f514` on the local
  branch `epic/abundled-request-that-routing-turns-away-is` (worktree
  `worktrees/EPIC-ABundledRequestThatRoutingTurnsAwayIs`). Read it from this worktree with
  `git show epic/abundled-request-that-routing-turns-away-is:docs/decisions/dec-b10271ebb40b9eaa.yaml`. The
  same commit filed `tickets/00_inbox/TICKET-20261010-ScheduleArchDocScaffold.md`, the ticket that schedules
  INF-1300.

How to draw under the pass (as on the DK-400 tickets):

- Take the frontmatter shape from an existing L3 diagram of the same `diagram_type`.
- Write a Legend with one entry per notation element the diagram actually uses. Do not cite ADR-015: here
  it is about exception handling.
- Set `source_ticket` to this ticket.
- Record the deviation in the diagram's own decision-history block: name the decision, say the scaffold was
  missing, and say the frontmatter and Legend were written by hand under this authorisation.
- Record the pass in your sign-off as well. The architecture-diagram-author sign-off comment names
  `dec-b10271ebb40b9eaa` and lists each of AC-1 to AC-6 (its file) as drawn scaffold-free under it. The
  decision requires the authorisation to be written down where later agents read it: in the decision record
  and in each diagram's decision history (criterion `crit.waiver_recorded`). The sign-off line is how the
  supervisor and the commit phase see it.
- Edit no skill text.

## Test Requirements

Documentation only. All nine ACs are `test_required: false` with a `test_rationale`, so test-writer has
nothing to write.

```yaml
tests: []
```

## Agent Contracts

### documentation-expert

The contract file for each AC is listed below. These files also change, but the verifier does not check
them separately: `docs/architecture/diagrams/c2-007-decision-kernel-flows-overview.md`,
`docs/architecture/components/decision-kernel.md` and `docs/how-to/run-the-decision-kernel.md`.

- [ ] AC-1: sequence-diagram | docs/architecture/diagrams/c3-024-decision-kernel-flows-forming-round.md | DK-600a-5 by architecture-diagram-author: one forming round from your question to the ranked options, with you, Claude Code as host, the kernel, the research capability and Jev in the order the round runs, plus the budget-reserve exit; listed in c2-007 children and linked from decision-kernel.md
- [ ] AC-2: state-diagram | docs/architecture/diagrams/c3-025-decision-kernel-flows-decision-states.md | DK-600b-5 by architecture-diagram-author: proposed, approved, ranked and resolved plus an unresolved end, every transition labelled, the re-rank loop from ranked back to assessment, and no path to resolved without your choice
- [ ] AC-3: sequence-diagram | docs/architecture/diagrams/c3-026-decision-kernel-flows-record-staging.md | DK-600c-5-ii by architecture-diagram-author: decision executor, record builder, file backend, the /leafcutter skill and you; approved decision detected, record built, staged under the run folder, completed-run message with the staged path and publish command; the no-approval exit stages nothing; no message to the repository
- [ ] AC-4: sequence-diagram | docs/architecture/diagrams/c3-027-decision-kernel-flows-record-publishing.md | DK-600d-5-ii by architecture-diagram-author: publish request, record checked, record and index written, store validated, commit and PR, review, merge; both exit-code-3 stops end before any write
- [ ] AC-5: state-diagram | docs/architecture/diagrams/c3-028-decision-kernel-flows-record-lifecycle.md | DK-600d-5-iii by architecture-diagram-author: staged, published (in review, then merged) and superseded; keep-staged end never found as precedent; superseded is an end state labelled kept on record, corrections appended only
- [ ] AC-6: sequence-diagram | docs/architecture/diagrams/c3-029-decision-kernel-flows-precedent-reuse.md | DK-600e-5 by architecture-diagram-author: precedent step, decision store and index, Jev, you and the decision executor; lookup, judging up to memory.max_precedents, citing at memory.applies_threshold, the reuse question at memory.reuse_threshold, your answer to reuse or decide anew; no path resolves without your answer
- [ ] AC-7: how-to | docs/how-to/answer-the-decision-kernel-questions.md | DK-600b-4 by how-to-author: approve all, a subset, reword a criterion or add an option at the approval question; choose, add an option (new ranking) or answer in words at the ranked question; ranking is advice and the decision waits for your choice; every example accepted by the kernel as written
- [ ] AC-8: how-to | docs/how-to/file-and-reuse-decisions-with-the-kernel.md | DK-600d-5-i by how-to-author: publish with --run-id, the checks before writing, the record and index it changes, commit and PR; --correct with a reason appends to the older record; the fix for each exit-code-3 stop; an unpublished record is never found as precedent
- [ ] AC-9: reference | docs/reference/decision-record.md | DK-600c-5-i by reference-author: every part of the record (identity, question, filters, answer, evidence, authority, provenance, corrections), evidence as locators and content hashes, only a human-approved decision makes a record, field list equal to config/decision_record.schema.json both ways

## Sign-offs

- [x] architecture-diagram-author — 2026-10-10 12:57
- [x] how-to-author — 2026-10-10 13:25
- [x] reference-author — 2026-10-10 13:50
- [x] documentation-verifier — 2026-10-10 13:07
- [x] commit — 2026-10-10 14:05
- [ ] pull-request

## Comments

### 2026-10-10 12:18 — it-po (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  ac_amendments_reviewed: true
  override_reviewed: true
  authorising_decision_recorded: true
IT-PO review before the build. This is not a phase sign-off: it-po is not in this ticket's `agents:` map.
The feedback id is the signoff §2a fallback, because `submit_feedback.py` accepts no category from the
writer `it-po` (`config/feedback_categories.yaml`).

**`ac_limit_override: true`: accepted.** `check-ticket-ac-limits` counts nine AC lines under
`### documentation-expert`, against a cap of 7 per agent block (total 9 of 20). The nine sit under one heading
only because documentation-verifier reads its required-docs list from that block. The work per producer is
6 diagrams (architecture-diagram-author, each S), 2 how-tos (how-to-author, M and S) and 1 reference
(reference-author, M), so no producer exceeds 7. Splitting would couple the parts more, not less: DK-600d-5-i
links c3-026 to c3-028, and how-to-author and reference-author both edit
`file-and-reuse-decisions-with-the-kernel.md`, so one ticket would wait on the other. A split would also undo
the user's decision `dec-ea83c3989d1b7199` (one docs ticket).

**AC review.** All nine keep `test_required: false` with the user-approved `test_rationale`, and none has a
`test_spec`. The ADR-036 reassignments are correct (DK-600b-4 and DK-600d-5-i to how-to-author, DK-600c-5-i
to reference-author). c3-024 to c3-029 are free on every local and origin branch (checked 2026-10-10), and
`next_diagram_seq.py 3` still says 23. Changed, each with an it-po `amended_by` entry:
- DK-600b-4: the answer-example line now says the author checks each example with a scratch script and
  records the command and result in its sign-off. The words-answer line now names DK-600b-2-ii's covering
  test, replacing "not yet by a repository test".
- DK-600c-5-i: the schema-parity line now says the author checks both directions with a scratch script and
  records the result. It also says nothing re-checks the pair after this ticket.
- DK-600d-5-i: added the target-file line that it alone lacked.
- No change to DK-600a-5, DK-600b-5, DK-600c-5-ii, DK-600d-5-ii, DK-600d-5-iii or DK-600e-5.

**Ticket.** I recorded the authorising decision `dec-b10271ebb40b9eaa` and its scope. The diagram author is
told to record the pass in its sign-off. The commit phase now checks that the two scratch-check records are
present, because documentation-verifier checks only that each file changed and has no placeholders.

### 2026-10-10 12:57 — architecture-diagram-author (status: ok)
feedback-id: fb_2026-10-10_7dc3fbad
completion_manifest:
  diagram_created: true
  flight_level_correct: true
  cross_links_added: true
Drew AC-1 to AC-6. All six are L3-Component, under parent c2-007, and listed in its `children:` and in its
"Pages in this set" table. All six are linked from `docs/architecture/components/decision-kernel.md`, in a new
"Decision lifecycle diagrams" section. All six link c3-013, c3-014 and c3-020 rather than redrawing their messages.

**Scaffold-free pass.** `scripts/scaffold/new_arch_doc.py` is still missing. Each diagram was drawn scaffold-free
under the user's standing decision `dec-b10271ebb40b9eaa`. I read it from
`epic/abundled-request-that-routing-turns-away-is` (approved_by human:user, 2026-10-10T09:45:36Z). The frontmatter
and Legend were written by hand, and each diagram's DECISION HISTORY block records the deviation. No skill text was
edited. Drawn under the pass:
- AC-1 DK-600a-5: `docs/architecture/diagrams/c3-024-decision-kernel-flows-forming-round.md` (sequence)
- AC-2 DK-600b-5: `docs/architecture/diagrams/c3-025-decision-kernel-flows-decision-states.md` (state)
- AC-3 DK-600c-5-ii: `docs/architecture/diagrams/c3-026-decision-kernel-flows-record-staging.md` (sequence)
- AC-4 DK-600d-5-ii: `docs/architecture/diagrams/c3-027-decision-kernel-flows-record-publishing.md` (sequence)
- AC-5 DK-600d-5-iii: `docs/architecture/diagrams/c3-028-decision-kernel-flows-record-lifecycle.md` (state)
- AC-6 DK-600e-5: `docs/architecture/diagrams/c3-029-decision-kernel-flows-precedent-reuse.md` (sequence)

**Numbers.** `scripts/next_diagram_seq.py 3` still said 23. A `git ls-tree` over every local and origin branch
found only c3-023 taken (epic branch), so c3-024 to c3-029 stand and no contract line moved.

**Fast-lane ACs.** Neither has merged to main. `fast-lane/dk-600a-3` has one unmerged commit, and
`fast-lane/dk-600e-3-i` has no commit beyond main. So DK-600a-3 is drawn as NOT BUILT in c3-024, and DK-600e-3-i as
NOT BUILT in c3-028 and c3-029. DK-600b-2-ii's two covering tests pass here (`pytest
tests/kernel/capabilities/test_design_ending.py::TestHumanChoiceResolves::test_a_words_answer_*`: 2 passed), so
c3-025 draws the words-answer re-rank as built.

**Checks.** `check_doc_frontmatter` passed for 9 docs; its only warning is the same-day `last_updated` note on
decision-kernel.md. The rest were called per file and report zero violations: `check_mermaid_parent_link`,
`check_mermaid_complexity` (max 24 interactions, 10 states), `check_diagram_naming`, `check_doc_links`, and
`check_ac_schema`. Every Mermaid block parses with mermaid@11 `mermaid.parse`, run from a scratch install outside
the repo. Every relative link and `related_*` path resolves.

**Closing.** Each of the six AC YAMLs got its target file in `implemented_by`.
`mark_ac_done.py --ac <id> --ac-root docs/acceptance-criteria --test-root tests/kernel` printed
`marked <id> work_status=done` for all six (about 3 minutes each). Everything is staged.

**Open point for the PO (not a blocker).** DK-600b-5's third clause says "no transition reaches resolved without
your choice". As built, `combine`'s resolved gate settles a formed decision once you approve the proposals, with no
ranked choice. Covered by `test_decision_criteria_proposals.py::test_jev_decides_against_approved_criteria_only`
(DK-600b-1). c3-025 draws that transition as built and labels it "resolved gate on the set you approved", because
your approval is the decision's approval. It also states that a decision formed by ranking never resolves without
your choice (DK-600b-3). Either reword DK-600b-5's clause to "without your answer", or open a ticket if the gate
should ask for a ranked choice.

### 2026-10-10 13:25 — how-to-author (status: ok)
feedback-id: fb_2026-10-10_ed6b179d
completion_manifest:
  guide_written: true
  location_correct: true
  steps_validated: true
Wrote AC-7 (DK-600b-4) and extended AC-8 (DK-600d-5-i). Both ACs: `implemented_by` set to the target file and
`mark_ac_done.py --ac <id> --ac-root docs/acceptance-criteria --test-root tests/kernel` printed
`marked DK-600b-4 work_status=done` and `marked DK-600d-5-i work_status=done`. All files are staged.

- AC-7: new `docs/how-to/answer-the-decision-kernel-questions.md` (flat `docs/how-to/`, beside its sibling). In
  `docs/how-to/run-the-decision-kernel.md` the "recorded only" sentence is corrected (words answer is re-assessed
  and ranked again; only a choice resolves), a link added, `last_updated` moved.
- AC-8: extended `docs/how-to/file-and-reuse-decisions-with-the-kernel.md`: publish checks in order, the two files
  written (record and index) plus the JSON output, commit and PR, `--correct` with `--reason` appending only, the
  exact exit-3 messages from `kernel/memory/publish.py` and `kernel/memory/vocab.py`, an unpublished record never
  found as precedent, and links to c3-026, c3-027 and c3-028. The "What a record holds" table is untouched, for
  reference-author. The run's own publish instruction is not said to carry `--correct` (DK-600e-3-i not merged).
- No `docs/how-to/README.md` exists, so no README entry was added.

**Answer-example check (DK-600b-4).** Command: `python %TEMP%/dk/check_examples.py` (scratch script outside the
repo, run from the worktree root). It extracts all 8 `json` fences of the new how-to, wraps each in a full resume
submission for a `HumanQuestion` (approval question: `approve` choice, free text and structured allowed; ranked
question: option choices, free text and structured allowed) and runs `kernel.interaction.submissions.check_submission`,
which applies the `leafcutter.human_answer.v1` model and the semantic checks. Result: 8 of 8 ACCEPTED. Negative
checks: both `approved_criterion_ids` and `edited_criteria` -> `schema_invalid`; an unoffered `choice_id` ->
`semantic_invalid` ("choice opt.other does not exist"); `approve` plus `free_text` and free text alone at approval ->
accepted. Words re-rank: `pytest tests/kernel/capabilities/test_design_ending.py::TestHumanChoiceResolves -k words`:
2 passed.

**Open point for the PO (not a blocker).** DK-600b-4 it_requirements say `approved_criterion_ids` "is ignored when
edited_criteria is present". As built, the pair is refused: `HumanAnswerPayload._exactly_one`
(`kernel/contracts/payloads_human.py`) fails with "approved_criterion_ids and edited_criteria are alternatives", and
`approvals.py` never sees both. The how-to states the code's behaviour (refused, exit 3 `schema_invalid`), per the AC's
own rule that the doc is corrected to the code. Reword that it_requirements line or open a ticket if "ignored" was
wanted.

### 2026-10-10 13:50 — reference-author (status: ok)
feedback-id: fb_2026-10-10_c8e6b3ec
completion_manifest:
  reference_doc_written: true
  schema_tables_complete: true
  genre_guard_passed: true
Wrote AC-9 (DK-600c-5-i): `docs/reference/decision-record.md`, using `dec-d53e1c52cd47c832` as the example. It has a record-rules table (human approval only, evidence as locators and content hashes, append-only corrections) and eight field-group tables: identity, question, filters, answer, evidence, authority, provenance, corrections. The field rows were generated from the schema, with types, required flags and defaults. Added a row to `docs/reference/README.md`. In `file-and-reuse-decisions-with-the-kernel.md` the "What a record holds" table is now a link to the reference (plus `related_docs` and See Also entries). `implemented_by` set, and `mark_ac_done.py --ac DK-600c-5-i --ac-root docs/acceptance-criteria --test-root tests/kernel` printed `marked DK-600c-5-i work_status=done`. All staged.

**Schema-parity check (DK-600c-5-i).** Command: `python $TEMP/dk/parity.py` (scratch script outside the repo, run from the worktree root). It walks `config/decision_record.schema.json` recursively through `$ref`, `anyOf` and array items to get dotted field paths, then compares them with the backticked first-column field names in the reference. Result: 104 schema paths, 104 named in the doc, missing in doc: none, not in schema: none. `check_doc_frontmatter` and `check_doc_links` passed on the changed files.

### 2026-10-10 13:07 — documentation-verifier (status: ok)
feedback-id: fb_2026-10-10_f3bdd04d
completion_manifest:
  required_docs_list_parsed: true
  all_required_docs_present_in_diff: true
  no_placeholder_content_in_changed_docs: true
Documentation coverage verified: all 9 required doc(s) present (branch-range diff origin/main...HEAD union working-tree diff) with real content. Placeholder scan (scan_for_placeholders, TBD, single-identifier token, stub check) clean on all nine.

### 2026-10-10 14:05 — commit (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Auto-authorized commit gate: subject "docs(decision-kernel): add decision lifecycle diagrams, how-tos and decision-record reference"; staged files: 23 docs, DK-600 AC yamls and this ticket. Pre-commit probe passed (failing_checks empty).
