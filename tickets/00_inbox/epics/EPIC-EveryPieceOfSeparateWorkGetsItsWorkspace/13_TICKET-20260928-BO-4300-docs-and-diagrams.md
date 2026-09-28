---
title: 'Docs and diagrams: getting and clearing a workspace, the answer reference, component, sequence
  and state diagrams'
status: todo
components:
- worktree_manager
- documentation_system
created: '2026-09-28'
last_updated: '2026-09-28'
depends_on:
- 11_TICKET-20260928-BO-4300-workflow-routes.md
- 12_TICKET-20260928-BO-4300-legacy-cut-over.md
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
change_target: docs
risk_surface: internal
complexity: medium
requires_adr: false
requires_diagram: true
source_ac: BO-4300a-3
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2:
  - BO-4300a-3
  - BO-4300a-4
  - BO-4300a-5
  - BO-4300c-5
  - BO-4300d-5
  - BO-4300e-5
ac_coverage: 0/6
tags:
- BO-4300
- re-cut-2026-09-28
files_touched:
- docs/how-to/get-a-workspace.md
- docs/how-to/clear-a-workspace.md
- docs/reference/workspace-maker-answer.md
- docs/architecture/components/worktree-manager.md
- docs/architecture/diagrams/c3-010-workspace-request-halt-sequence.md
- docs/architecture/diagrams/c3-011-workspace-request-states.md
- docs/analysis/2026-09-25-worktree-delivered-maker.md
- docs/components.json
- docs/INDEX.md
- docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300c-5.yaml
- docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300d-5.yaml
- unit_tests/build_orchestration/test_bo_4300_docs.py
agents:
  ac-fulfillment-gate: needed
  ac-validator: needed
  architect-review: needed
  architecture-diagram-author: needed
  commit: needed
  documentation-expert: needed
  documentation-verifier: needed
  frontend-coder: not_needed
  pr-reviewer: needed
  pull-request: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: needed
  test-writer: needed
  user-surface-smoker: not_needed
---

# 13: Docs and diagrams: getting and clearing a workspace, the answer reference, component, sequence and state diagrams

## Actor / Goal

In order that agents and people get and clear workspaces the one way, we need the how-tos, the answer reference and the three diagrams written against what actually shipped, so that every written instruction points at the maker and nothing restates the contract.

## Context

These six ACs were six separate tickets owning the same `worktree-manager.md`. They are written last among the builders (after tickets 11 and 12) so they describe the shipped CLI and routes; a-3 is what BO-4300f-2-ia/ib (ticket 14) point every rewritten passage at.

Part of `EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace`, re-cut on 2026-09-28 by deliverable (see Master_Plan.md, 'Re-cut 2026-09-28'). This ticket owns the files in `files_touched` and covers 6 AC(s); the AC YAML records under `docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/` are the source of truth and win over any text here.

## AC References

| # | AC | Level | Title | Expects from | Producing ticket |
|---|----|-------|-------|--------------|------------------|
| AC-1 | BO-4300a-3 | L2 | How-to: getting a workspace, for agents and people alike | BO-4300a-1 | 01_TICKET-20260927-BO-4300a-1.md |
| AC-2 | BO-4300a-4 | L2 | Component diagram: the one workspace maker and everyone who calls it | BO-4300a-1 | 01_TICKET-20260927-BO-4300a-1.md |
| AC-3 | BO-4300a-5 | L2 | Reference: the answer every caller receives, and what a caller must do with it | BO-4300c-2 | 03_TICKET-20260928-BO-4300-answer-contract.md |
| AC-4 | BO-4300c-5 | L2 | Sequence diagram: a caller, the workspace maker, and the halt path | BO-4300c-3 | 10_TICKET-20260928-BO-4300-workflow-runtime-and-shell-runner.md |
| AC-5 | BO-4300d-5 | L2 | State diagram: a workspace's states and what each request does to it | BO-4300d-2 | 07_TICKET-20260928-BO-4300-safe-re-request.md |
| AC-6 | BO-4300e-5 | L2 | How-to: clearing a workspace by hand, and authorising the loss of unsent work | BO-4300e-3 | 08_TICKET-20260928-BO-4300-locate-and-clear.md |

**Closure order.** Children are listed before their parents. No composite AC in this ticket. `source_ac` (`BO-4300a-3`) is the anchor `check-ticket-ac-status-parity` checks; `ac_traceability` (list form) names every AC so `ac-fulfillment-gate` verifies each one before commit. The ticket may be set `done` only when every AC above is `work_status: done`.

## Acceptance Criteria

### AC-1: BO-4300a-3 (L2) -- How-to: getting a workspace, for agents and people alike

```gherkin
Given an agent or a person needs a workspace to work in,
When they open the how-to guide for getting one,
Then it shows the single way to request a workspace, and that the same request
  works from the project's top folder, the folder above it and inside another
  workspace,
And it shows how to read a ready answer and where the workspace's location is
  given in it,
And it shows what to do on a refusal: stop, remedy the cause the refusal
  names, and ask again,
And it states that asking again for the same work is always safe,
And it gives no alternative step-by-step recipe for making, linking or setting
  up a workspace by hand.
```

### AC-2: BO-4300a-4 (L2) -- Component diagram: the one workspace maker and everyone who calls it

```gherkin
Given a reader wants to see where workspaces come from,
When they open the component diagram for the workspace maker,
Then it shows the workspace maker as one standalone component,
And it shows each caller -- workflows receiving its answer, the skill agents
  run it from, agents, and a person at a terminal -- reaching workspaces only
  through it,
And it shows the main copy, the shared project, the landing place for
  workspaces, and each workspace holding its own installed tools,
And it shows no second path by which a workspace is made, found or cleared.
```

### AC-3: BO-4300a-5 (L2) -- Reference: the answer every caller receives, and what a caller must do with it

```gherkin
Given a workflow author, skill author or person needs to act on the workspace
  maker's answer,
When they open the reference document for that answer,
Then it lists every outcome the maker can give -- ready, and each cause of a
  refusal -- with the meaning of each,
And it states that anything other than a ready answer means the caller stops,
And it states that the workspace's location is taken only from a ready answer,
  never from an agent's own words or from the folder the caller happens to be in,
And it states that the answer has the same form whichever route asked.
```

### AC-4: BO-4300c-5 (L2) -- Sequence diagram: a caller, the workspace maker, and the halt path

```gherkin
Given a reader wants to understand how a workflow obtains its workspace and when
  it stops,
When they open the sequence diagram,
Then it shows the caller, the skill or agent that runs the workspace maker, the
  workspace maker, and the shared project,
And it shows the ready path, in which the caller takes the location from the
  answer and only then dispatches its first working step,
And it shows the halt path for each answer that is not ready -- refusal,
  error, prose, or no answer -- ending the run before any working step,
And it shows no path on which the caller continues without a ready answer.
```

### AC-5: BO-4300d-5 (L2) -- State diagram: a workspace's states and what each request does to it

```gherkin
Given a reader wants to know what asking for a workspace does in each situation,
When they open the state diagram,
Then it shows the states absent, half-made, ready, and occupied by other work,
And it shows, for each state, the outcome of a request for the same work:
  absent to ready or refused; half-made to ready or refused; ready to ready
  again; occupied by other work left as it is and refused,
And it shows that no request moves a workspace from occupied by other work to
  any other state.
```

### AC-6: BO-4300e-5 (L2) -- How-to: clearing a workspace by hand, and authorising the loss of unsent work

```gherkin
Given a person wants to clear away a workspace,
When they open the how-to guide for clearing one,
Then it shows how to find the workspace for a piece of work and how to ask for
  it to be cleared,
And it shows what a refusal lists -- unpushed commits and uncommitted files --
  and how to deliver that work first,
And it shows how to authorise, up front in the request, the loss of work that
  will not be delivered,
And it gives no manual deletion steps that bypass the workspace maker.
```

- [ ] AC-1: BO-4300a-3 -- How-to: getting a workspace, for agents and people alike
- [ ] AC-2: BO-4300a-4 -- Component diagram: the one workspace maker and everyone who calls it
- [ ] AC-3: BO-4300a-5 -- Reference: the answer every caller receives, and what a caller must do with it
- [ ] AC-4: BO-4300c-5 -- Sequence diagram: a caller, the workspace maker, and the halt path
- [ ] AC-5: BO-4300d-5 -- State diagram: a workspace's states and what each request does to it
- [ ] AC-6: BO-4300e-5 -- How-to: clearing a workspace by hand, and authorising the loss of unsent work

## Test Requirements

Taken from each AC's `test_spec` (one test module per AC); the last entry is the ticket's reachability proof. Every test carries `# covers: <AC-ID>` and `# angle: <angle>`.

```yaml
tests:
- name: test_get_a_workspace_how_to_publishes_a_maker_command_that_runs
  file: unit_tests/build_orchestration/test_bo_4300_docs.py
  covers:
  - BO-4300a-3
  asserts: docs/how-to/get-a-workspace.md exists with valid how_to frontmatter, is reachable from docs/INDEX.md,
    and every maker command it publishes, run against the deployed maker on a temp project with a bare
    hub, answers ok; the page carries no git worktree, symlink or copy recipe.
  framework: unittest
  type: behavioral
  angle: real_artifact
  implementation_files:
  - docs/how-to/get-a-workspace.md
  - docs/how-to/clear-a-workspace.md
  - docs/reference/workspace-maker-answer.md
  - docs/architecture/components/worktree-manager.md
  - docs/architecture/diagrams/c3-010-workspace-request-halt-sequence.md
  - docs/architecture/diagrams/c3-011-workspace-request-states.md
- name: test_component_diagram_names_the_one_maker_and_every_caller
  file: unit_tests/build_orchestration/test_bo_4300_docs.py
  covers:
  - BO-4300a-4
  asserts: docs/architecture/components/worktree-manager.md carries a mermaid component diagram (diagram_type
    valid per diagram_types.json) naming the maker, its resolver, every caller route and the landing place,
    and no retired script.
  framework: unittest
  type: behavioral
  angle: real_artifact
  implementation_files:
  - docs/how-to/get-a-workspace.md
  - docs/how-to/clear-a-workspace.md
  - docs/reference/workspace-maker-answer.md
  - docs/architecture/components/worktree-manager.md
  - docs/architecture/diagrams/c3-010-workspace-request-halt-sequence.md
  - docs/architecture/diagrams/c3-011-workspace-request-states.md
- name: test_answer_reference_points_at_the_contract_record
  file: unit_tests/build_orchestration/test_bo_4300_docs.py
  covers:
  - BO-4300a-5
  asserts: docs/reference/workspace-maker-answer.md exists with reference frontmatter, names BO-4300c-2
    as the authoritative contract, lists every code of the deployed maker's answer table (including AMBIGUOUS_LINE)
    and the discard_token field, and is reachable from docs/INDEX.md.
  framework: unittest
  type: behavioral
  angle: real_artifact
  implementation_files:
  - docs/how-to/get-a-workspace.md
  - docs/how-to/clear-a-workspace.md
  - docs/reference/workspace-maker-answer.md
  - docs/architecture/components/worktree-manager.md
  - docs/architecture/diagrams/c3-010-workspace-request-halt-sequence.md
  - docs/architecture/diagrams/c3-011-workspace-request-states.md
- name: test_halt_sequence_diagram_exists_and_shows_the_halt_path
  file: unit_tests/build_orchestration/test_bo_4300_docs.py
  covers:
  - BO-4300c-5
  asserts: The c3 halt-sequence diagram exists with a mermaid sequenceDiagram including the caller, the
    maker and a halt path for each non-ready answer class; BO-4300c-5's doc_links path matches the file.
  framework: unittest
  type: behavioral
  angle: real_artifact
  implementation_files:
  - docs/how-to/get-a-workspace.md
  - docs/how-to/clear-a-workspace.md
  - docs/reference/workspace-maker-answer.md
  - docs/architecture/components/worktree-manager.md
  - docs/architecture/diagrams/c3-010-workspace-request-halt-sequence.md
  - docs/architecture/diagrams/c3-011-workspace-request-states.md
- name: test_state_diagram_exists_and_names_every_request_state
  file: unit_tests/build_orchestration/test_bo_4300_docs.py
  covers:
  - BO-4300d-5
  asserts: The c3 workspace-states diagram exists with a mermaid stateDiagram naming absent, half-made,
    ready and occupied-by-other-work, a refusal code on each refused edge and no edge leaving occupied;
    BO-4300d-5's doc_links path matches the file.
  framework: unittest
  type: behavioral
  angle: real_artifact
  implementation_files:
  - docs/how-to/get-a-workspace.md
  - docs/how-to/clear-a-workspace.md
  - docs/reference/workspace-maker-answer.md
  - docs/architecture/components/worktree-manager.md
  - docs/architecture/diagrams/c3-010-workspace-request-halt-sequence.md
  - docs/architecture/diagrams/c3-011-workspace-request-states.md
- name: test_clear_a_workspace_how_to_publishes_a_remove_command_that_runs
  file: unit_tests/build_orchestration/test_bo_4300_docs.py
  covers:
  - BO-4300e-5
  asserts: docs/how-to/clear-a-workspace.md exists with valid frontmatter, is reachable from docs/INDEX.md,
    and its published commands run against the deployed maker with the documented outcome -- remove on
    a workspace with unsent work is refused with a discard_token, and the documented repeat with --discard-token
    clears it.
  framework: unittest
  type: behavioral
  angle: real_artifact
  implementation_files:
  - docs/how-to/get-a-workspace.md
  - docs/how-to/clear-a-workspace.md
  - docs/reference/workspace-maker-answer.md
  - docs/architecture/components/worktree-manager.md
  - docs/architecture/diagrams/c3-010-workspace-request-halt-sequence.md
  - docs/architecture/diagrams/c3-011-workspace-request-states.md
- name: test_ticket_13_reachable_from_entry_point
  file: unit_tests/build_orchestration/test_bo_4300_docs.py
  covers:
  - BO-4300a-3
  angle: reachability
  surface_invoked: the maker commands published in docs/how-to/get-a-workspace.md and clear-a-workspace.md,
    executed against the deployed maker (CLI via subprocess)
  asserts: Invoke the production entry point named in surface_invoked (never an import of the function)
    and assert the new behaviour occurs and is consumed.
  implementation_files:
  - docs/how-to/get-a-workspace.md
  - docs/how-to/clear-a-workspace.md
  - docs/reference/workspace-maker-answer.md
  - docs/architecture/components/worktree-manager.md
  - docs/architecture/diagrams/c3-010-workspace-request-halt-sequence.md
  - docs/architecture/diagrams/c3-011-workspace-request-states.md
```

## Implementation Notes

### Ticket-specific (harvested from the failed run and the AC records)

- a-5 reference points at BO-4300c-2 as the single authoritative contract rather than restating it (c-2 it_requirements), and supersedes the as-built table in `docs/analysis/2026-09-25-worktree-delivered-maker.md` (leave a pointer there).
- DIAGRAM NUMBERS: BO-4300c-5 names `c3-009-workspace-request-halt-sequence.md`, but `c3-009` is taken (`c3-009-record-freshness-check-sequence.md`). Use the next free numbers (c3-010 sequence, c3-011 states; BO-4300d-5 named c3-010 for the state diagram) and update the two ACs' doc_links paths in the same change. Confirm numbers are still free at authoring time.
- Validate every `diagram_type` against `leafcutter/config/diagram_types.json`; load the write-c4-diagram skill; keep each doc under the 300-line ratchet (01 had to split).
- `docs/components.json` `worktree_manager.primary_code` gains the new maker modules from tickets 03-08 and 12.
- PROOF FOR DONE (settled by the coordinator 2026-09-28, recorded by IT PO in the six AC records): the six doc ACs now declare `test_required: true` with a `test_spec` naming their test here and a `test_rationale` -- there is no waiver. The done path is the real test `unit_tests/build_orchestration/test_bo_4300_docs.py` with a `# covers: <AC-ID>` tag per AC (each doc exists with valid frontmatter, is reachable from docs/INDEX.md, each diagram carries a mermaid block of its declared type, and the maker commands the how-tos publish execute successfully against the deployed maker).
- USER DECISIONS (2026-09-28) the docs describe as shipped: Q4 naming `<kind>/<slug>` with legacy aliases (ticket 06); Q5 sibling landing root `<project-dir-name>-worktrees/` with the validated `--landing-root` override (ticket 04); Q8 the two-step remove -- refusal with `discard_token`, then `remove --discard-token` (ticket 08); the `AMBIGUOUS_LINE` code and `discard_token` field (ticket 03). Nothing is pending: document the mechanisms, do not mark any argument as open.

### AC technical requirements (verbatim from the AC store; shared boilerplate omitted)

**BO-4300a-3**

- Frontmatter per the project doc conventions (title, description, type, status, created, last_updated, components: [worktree_manager, build_orchestration]); must pass the doc-related pre-commit hooks and be reachable from docs/INDEX.md via the build's doc index.
- Commands shown are exactly the deployed maker's CLI as built (BO-4300a-1 / BO-4300c-2); no hand-written alternative recipe, no symlink or copy steps.
- Location: docs/how-to/get-a-workspace.md. It is the single page every retired recipe points to (BO-4300f-2-ia/-ib), and it links to docs/how-to/clear-a-workspace.md (BO-4300e-5) and to the answer reference (BO-4300a-5) rather than repeating them.
- Q4 and Q5 are DECIDED (user, 2026-09-28): the page may say that every workspace is named <kind>/<slug> (legacy spellings such as EPIC-<Name> are accepted and reach the same workspace) and lives in the project's sibling folder <project-dir-name>-worktrees/, but a reader is told to take the location only from the workspace_path in the ready answer, never to build it from that pattern (an explicit --landing-root override moves it).

**BO-4300a-4**

- Rewrite docs/architecture/components/worktree-manager.md for per-feature clones: overview, responsibilities and entry points change (git worktree lifecycle, setup_ticket_worktree.py and the ACD-2100a-2 resolution notes are replaced by the one maker); add the C4 component diagram per the write-c4-diagram skill.
- The diagram shows the maker as one standalone component; callers (workflows receiving args.workspace or one verbatim dispatch, the workspace skill, agents, a person at a terminal) reaching workspaces only through it; the main copy, the hub, the landing place, and each workspace holding its own installed tools; no second make/find/clear path.
- Stay consistent with the components.json worktree_manager update recorded on BO-4300a-1 (description and primary_code).
- The landing place shown is the decided one (Q5, user 2026-09-28) -- the project's sibling folder <project-dir-name>-worktrees/ holding each workspace at <kind>/<slug> -- outside the main copy.

**BO-4300a-5**

- Frontmatter per the project doc conventions (title, description, type, status, created, last_updated, components: [worktree_manager, build_orchestration]); must pass the doc-related pre-commit hooks and be reachable from docs/INDEX.md via the build's doc index.
- Location: docs/reference/workspace-maker-answer.md. Lists every field, every code with its status and exit code, the verb-specific fields, the rule that workspace_path/worktree_path/workspace_path_posix are absent on every non-ok answer, and the schema_version policy.
- States the caller rules verbatim from the contract: halt on anything but status ok; take the location only from workspace_path of an ok answer, never from prose or from the caller's cwd; the answer has the same form whichever route asked.
- Q8 is DECIDED (user, 2026-09-28): the page documents discard_token on remove's UNSENT_WORK answer and the --discard-token argument -- a one-time token bound to that workspace and exactly the unsent set listed with it, valid only on the remove request for that workspace while the set is unchanged, never an environment variable or config setting, never remembered -- and the AMBIGUOUS_LINE code with its lines field (Q4), both as recorded in BO-4300c-2.

**BO-4300c-5**

- Location: docs/architecture/diagrams/c3-009-workspace-request-halt-sequence.md (next free c3 number; verify before writing), Mermaid sequence per the write-c4-diagram skill, linked from docs/architecture/components/worktree-manager.md.
- Participants: caller workflow, entry skill or shell-permitted agent, the maker, the hub. Shows the ready path (location taken from workspace_path, then the first working dispatch), one halt path per non-ready answer class (refused, error, prose, none), and no continue-without-ready path.

**BO-4300d-5**

- Location: docs/architecture/diagrams/c3-010-workspace-request-states.md (next free c3 number; verify before writing), Mermaid state diagram per the write-c4-diagram skill, linked from docs/architecture/components/worktree-manager.md.
- States absent, half-made, ready, occupied-by-other-work (the legacy-worktree occupant may be shown as a sub-state); transitions exactly as the criteria list, with the refusal code on each refused edge; no edge leaves occupied.

**BO-4300e-5**

- Frontmatter per the project doc conventions (title, description, type, status, created, last_updated, components: [worktree_manager, build_orchestration]); must pass the doc-related pre-commit hooks and be reachable from docs/INDEX.md via the build's doc index.
- Commands shown are exactly the deployed maker's CLI as built (BO-4300a-1 / BO-4300c-2); no hand-written alternative recipe, no symlink or copy steps.
- Location: docs/how-to/clear-a-workspace.md; linked from get-a-workspace.md. Documents locate, remove, the UNSENT_WORK refusal lists, delivering work first, and the up-front discard authorisation as decided (Q8, user 2026-09-28): the refusal returns a one-time discard_token bound to that workspace and exactly the listed unsent work; to discard, repeat the remove with --discard-token <that token>; a token does not work for another workspace or once anything unsent changes (ask again for a fresh one); there is no environment variable, config setting or remembered answer that authorises a discard.

## Agent Contracts

### test-writer

- [ ] AC-1: red tests for BO-4300a-3 per `## Test Requirements`
- [ ] AC-2: red tests for BO-4300a-4 per `## Test Requirements`
- [ ] AC-3: red tests for BO-4300a-5 per `## Test Requirements`
- [ ] AC-4: red tests for BO-4300c-5 per `## Test Requirements`
- [ ] AC-5: red tests for BO-4300d-5 per `## Test Requirements`
- [ ] AC-6: red tests for BO-4300e-5 per `## Test Requirements`

**Delivers to:** documentation-expert (red baseline).

### documentation-expert

- [ ] AC-1: how-to | docs/how-to/get-a-workspace.md | How-to: getting a workspace, for agents and people alike
- [ ] AC-2: architecture | docs/architecture/components/worktree-manager.md | Component diagram: the one workspace maker and everyone who calls it
- [ ] AC-3: reference | docs/reference/workspace-maker-answer.md | Reference: the answer every caller receives, and what a caller must do with it
- [ ] AC-4: architecture | docs/architecture/diagrams/c3-010-workspace-request-halt-sequence.md | Sequence diagram: a caller, the workspace maker, and the halt path
- [ ] AC-5: architecture | docs/architecture/diagrams/c3-011-workspace-request-states.md | State diagram: a workspace's states and what each request does to it
- [ ] AC-6: how-to | docs/how-to/clear-a-workspace.md | How-to: clearing a workspace by hand, and authorising the loss of unsent work

### architecture-diagram-author

- [ ] AC-2: diagram for BO-4300a-4 (component / sequence / state)
- [ ] AC-4: diagram for BO-4300c-5 (component / sequence / state)
- [ ] AC-5: diagram for BO-4300d-5 (component / sequence / state)

### Expects From

- **BO-4300a-3 <- BO-4300a-1** (01_TICKET-20260927-BO-4300a-1.md): CLI of the one maker. Deployed at <install-root>/scripts/worktree.py (source templates/scripts/worktree.py; the name is provisional until this AC is built, after which that path is the contract every caller names). Stdlib-only Python, run as `python <absolute path> <verb> ...` from ANY cwd. Verbs: `ensure --kind {ticket|feature|ac|fastlane|epic|scratch} --slug <work identity> [--repo-root P] [--allow-stale-base] [--config-path P]` -- the only creating verb, idempotent, always fetch + build + canary; `locate (--kind K --slug S | --path P | --branch B) [--repo-root P]` -- read-only; `list [--repo-root P]` -- read-only scan of the landing place's markers, never git worktree list; `verify --path P [--kind K --slug S] [--repo-root P]` -- read-only readiness re-check; `remove --path P [--discard-token T] [--delete-remote-branch] [--repo-root P]` -- T is the one-time token from this same workspace's own UNSENT_WORK refusal (Q8, decided 2026-09-28, BO-4300e-3); `where` -- prints the maker's own absolute path. ensure, locate, list, verify and remove also accept [--landing-root P], the explicit landing-place override the maker validates (Q5, decided 2026-09-28, BO-4300b-2); --kind K --slug S is normalised to the one identity <kind>/<slug>, legacy spellings accepted as aliases (Q4, decided 2026-09-28, BO-4300a-2). There is no --reset-existing (BO-4300d-4 resumes), no --no-bootstrap (decision 2), and no flag that skips a readiness ingredient.
- **BO-4300a-4 <- BO-4300a-1** (01_TICKET-20260927-BO-4300a-1.md): Component boundary: one stdlib script at <install>/scripts/worktree.py with verbs ensure/locate/list/verify/remove/where; marker-based registry in the landing place.
- **BO-4300a-5 <- BO-4300c-2** (03_TICKET-20260928-BO-4300-answer-contract.md): The result contract exactly as recorded in BO-4300c-2 delivers_to (the one authoritative copy -- not restated here, so a field added there cannot be missed in a copy). The reference must cover every code and field listed there at the time it is written, including the per-stage hook checks, inactive_stages and the ticket_path_in_worktree fields added by the 2026-09-25 duplication audit.
- **BO-4300c-5 <- BO-4300c-3** (10_TICKET-20260928-BO-4300-workflow-runtime-and-shell-runner.md): Workflow acceptance predicate and halt semantics.
- **BO-4300d-5 <- BO-4300d-2** (07_TICKET-20260928-BO-4300-safe-re-request.md): Half-made identification (maker 'creating' record) and completion semantics.
- **BO-4300e-5 <- BO-4300e-3** (08_TICKET-20260928-BO-4300-locate-and-clear.md): remove CLI including --discard-token T, where T is the one-time token from the same workspace's own UNSENT_WORK refusal (Q8, decided 2026-09-28).

### Delivers To

- consumed by **BO-4300f-2-ia** in 14_TICKET-20260928-BO-4300-retire-former-ways.md
- consumed by **BO-4300f-2-ib** in 14_TICKET-20260928-BO-4300-retire-former-ways.md

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |

## Risk & Safety

- Touches money? No.
- Touches data? No production data; developer repositories are protected by the ticket 02 session guard.
- Reversibility: all changes are code/docs on the epic branch; nothing ships until the epic PR merges.

## Sign-offs

- [ ] architect-review
- [ ] architecture-diagram-author
- [ ] test-writer
- [ ] test-runner
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] ac-validator
- [ ] ac-fulfillment-gate
- [ ] documentation-verifier
- [ ] commit

## Comments

_(Append-only log -- leave blank when authoring.)_
