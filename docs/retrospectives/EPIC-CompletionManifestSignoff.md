# Retrospective: EPIC-CompletionManifestSignoff

Date: 2026-05-30
Epic duration: 2026-05-28 (created) to 2026-05-30 (merged, PR #24)
Commits: 14 implementation + 1 archive = 15 total (branch: worktree-EPIC-CompletionManifestSignoff)

---

## Summary

EPIC-CompletionManifestSignoff introduced a structured `completion_manifest:` requirement
into the agent signoff system. Before this epic, phase agents could declare `status: ok`
with only a free-text comment. After it, every phase agent is expected to append a
machine-parseable YAML block confirming each expected artifact as `true` or `false`.

The epic had 23 sub-tickets: one foundational (ticket 01 — the signoff skill §2b format
spec), nineteen per-agent checklist tickets (02_01–02_19, fully parallel after 01),
two structural tickets (03 — ticket-supervisor validation, 04 — ticket-authoring schema
update), and one documentation ticket (05 — building-epics skill). The dependency graph
was clear and well-specified. Execution followed it.

A notable observation: not all 19 per-agent checklists received individual commits. Some
agents were batched in a single bulk commit (`af02e16 feat(agents): add
default_artifact_checklist to remaining agent templates`). This means the commit graph
does not map 1:1 to ticket graph — several tickets were resolved by a single commit.
The implementation is complete but the traceability between commit and ticket is partial
for the batch.

---

## Metrics

| Component | Status |
|-----------|--------|
| signoff/SKILL.md §2b | Done |
| Agent templates with default_artifact_checklist | Done (all 19 targeted agents) |
| ticket-supervisor §2.3 manifest validation | Done |
| ticket-authoring schema update (ticket 04) | Done (via bulk commit) |
| building-epics §2.3 documentation (ticket 05) | Done |

All 5 ticket groups completed. No failures. No retries recorded.

---

## Epic Facts

| Metric | Value |
|--------|-------|
| Ticket count | 23 sub-tickets |
| Completed tickets | 23 |
| Git commits | 15 (including archive) |
| PR | #24 (urlmonitor/leafcutter-ai) |
| Breaking change | No |
| ADRs authored | 0 |

---

## What Went Well

- **Dependency graph was correctly observed.** Ticket 01 (signoff §2b) was implemented
  first, establishing the manifest format before any per-agent checklist work began.
  Tickets 03 and 05 were held until the agent templates and ticket-supervisor were ready.
  No out-of-order commits.

- **Parallel batch executed cleanly.** The 19 per-agent checklist tickets (02_01–02_19)
  touched disjoint files and were implemented without merge conflicts. The bulk-commit
  approach for the remaining agents after individual commits for the first several was
  pragmatic and did not introduce any regression.

- **Validation logic is layered and non-breaking.** The ticket-supervisor §2.3 block only
  fires when a manifest is present. This means agents without a checklist continue to
  function, allowing progressive adoption. The design avoids a hard cut-over that would
  require all agents to be updated simultaneously.

- **Format spec in a single source of truth.** Anchoring the `completion_manifest:`
  format in `signoff/SKILL.md §2b` means all phase agents and supervisors share one
  canonical reference. Per-ticket overrides are allowed but the baseline is centralized.

- **Ticket 04 (ticket-authoring schema update) was correctly scoped.** Documenting the
  optional `artifact_checklist:` field in the ticket-authoring skill ensures authors
  know how to override agent defaults. This is a pure documentation ticket with no
  implementation risk.

---

## Friction Points

- **Partial commit-to-ticket traceability.** The bulk commit `af02e16` resolved multiple
  per-agent checklist tickets at once. While the implementation is correct, an auditor
  looking at `git log` cannot easily identify which commit satisfies which ticket
  (02_02 vs 02_07 vs 02_09 vs 02_12 etc.). The ticket status tracking relied on
  `## Comments` sections rather than commit messages for those batch tickets.

- **23 sub-tickets is a large parallel batch.** The 19 per-agent checklist tickets are
  structurally identical: add `default_artifact_checklist:` to one agent template each.
  This is boilerplate-heavy work. A code-generation approach (a build script or template
  expander that stamps the checklist into all agent frontmatters in a single pass) would
  reduce 19 near-identical tickets to 1 implementation ticket + 1 validation ticket.
  Worth considering for future "stamp all agents" style epics.

- **No ADR was authored.** The completion manifest is a meaningful architectural decision
  — it defines the contract between phase agents and the supervisor. A short ADR
  documenting the hybrid (default + per-ticket override) model and the rationale for
  progressive adoption over hard cut-over would be valuable future reference material.
  This was not flagged as a ticket gap before the epic started.

- **Ticket 04 had no individual commit.** Ticket 04 (ticket-authoring schema update)
  appears to have been resolved as part of the bulk agent commit or another combined
  commit rather than its own. It is in 99_done, so the work was done, but the specific
  diff for ticket 04 is not cleanly isolated in the git log.

---

## Knowledge Gaps Found

- **No convention for stamping many identical changes across all agents.** When a
  "stamp this field into all N agent templates" change is needed, the current workflow
  creates N near-identical tickets. A lightweight convention (e.g., a single ticket with
  `scope: all-phase-agents` that delegates to a build-step or loop rather than N parallel
  tickets) would reduce planning and commit overhead for this class of work.

- **No ADR trigger for supervisor contract changes.** Changes to the ticket-supervisor
  validation logic alter the contract between agents and the supervisor. This is a system
  boundary change that likely warrants an ADR, but the current ticket authoring guidance
  does not flag supervisor contract changes as an ADR trigger. The `requires_adr:` field
  in ticket frontmatter relies on the author knowing to set it. A convention note in the
  ticket-authoring skill for "supervisor/agent contract changes → requires_adr: true"
  would close this gap.

---

## Proposed Improvements

### KI-1: Convention for "stamp all phase agents" style epics

**Proposed Knowledge Item text:**

> When a change needs to be applied identically to all N phase agents (e.g., adding a
> new frontmatter field), prefer a single implementation ticket with a build step or
> loop rather than N individual tickets. Structure as:
>
> 1. One "define format" ticket (foundational — sets the field schema and default value).
> 2. One "stamp all agents" ticket that runs a script or commits a batch diff across
>    all agent templates in a single commit.
> 3. One "validate" ticket that reads back all agent templates and confirms the field
>    is present and correct.
>
> This reduces a 19-ticket parallel batch to 3 tickets with cleaner commit traceability.

Routing: `templates/skills/building-epics/SKILL.md` — add as a planning note under
the parallel batch section.

---

### KI-2: ADR trigger for supervisor/agent contract changes

**Proposed rule addition to ticket-authoring guidance:**

> Set `requires_adr: true` in ticket frontmatter when the ticket modifies:
> - The format or validation logic inside `ticket-supervisor`
> - The signoff protocol (signoff/SKILL.md)
> - The contract between phase agents and the supervisor (e.g., new required fields,
>   new rejection conditions)
>
> These are system boundary changes. The ADR documents why the contract changed, what
> alternatives were considered, and what the migration path is for existing agents.

Routing: `templates/skills/ticket-authoring/SKILL.md` or the ticket frontmatter
schema reference in `docs/reference/`.

---

*All proposed KIs above require explicit user approval before being applied.
No files have been modified by this retrospective.*
