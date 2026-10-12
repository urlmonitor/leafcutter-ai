---
title: "Policy store: where learned human decisions and policies live (ADR-054 open item 2)"
status: todo
components:
  - decision_kernel
  - git_vcs_operations
created: 2026-09-30
depends_on: []
priority: low
roadmap_phase: phase_kernel_3_workflows
advances_current_outcome: false
requires_diagram: true
requires_adr: true
change_target: code
risk_surface: auth
tags:
  - decision-kernel
  - policy
  - stage-3
  - later-stage
last_updated: 2026-09-30
files_touched:
  - docs/conventions/POL-GIT-001-git-operations-without-asking.md
  - tickets/00_inbox/TICKET-20260930-PolicyStore.md
---

# Policy store: where learned human decisions and policies live (ADR-054 open item 2)

## Actor / Goal
In order to stop asking the human the same authority question twice, we need a decided home
and format for scoped policies and learned human decisions, plus a deterministic way for the
kernel to look them up, so that an approved answer is reused exactly and no model output can
widen it.

## Context
- **Open decision.** [ADR-054](../../docs/architecture/adrs/ADR-054-process-representation-and-maturity-model.md)
  open item 2: "Where policies are stored. Spec part 7, §18.4 shows illustrative Stage 3 policy
  data (`LG-PARALLEL-001`). No storage location or format is decided."
- **First real example.**
  [POL-GIT-001](../../docs/conventions/POL-GIT-001-git-operations-without-asking.md), recorded on
  2026-09-30 from BrainCandy's decision in conversation. In leafcutter-ai, Claude and its agents
  commit, create branches and worktrees, push non-main branches and open PRs without asking;
  merging to `main`, force-pushing and pushing to `main` need confirmation. Its location
  (`docs/conventions/`) and its fenced-JSON format are provisional. This ticket decides whether
  they stay, and migrates the record if they do not.
- **Mechanism rule.** [ADR-053](../../docs/architecture/adrs/ADR-053-intelligence-selection-deterministic-jev-llm-human.md)
  §1 and §5: a permission or authority question is answered by deterministic code or a human,
  never by Jev or an LLM. Jev decides bounded judgements against known criteria (§2).
- **Spec.** [Spec part 7](../../docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-7-later-stages.md)
  §18.4 (scoped policies, stable ids, three rule types), §18.5 (inheritance, conflicts, scope
  expansion), §19.2 (review before activating a changed policy, preserved versions, rollback),
  §21 ("Policy inheritance, authority, and approval: Stage 3/4 before automated policy
  application or mutation"). [Spec part 5](../../docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-5-client-observability-safeguards.md)
  §13.3: model output cannot expand permissions or rewrite active policies.
- **Colony memory.** [ADR-056](../../docs/architecture/adrs/ADR-056-colony-memory-evidence-reinforcement.md)
  §3 rule 5 ("trails may rank and propose; they may not legislate") and §5 layer 3 (POLICY GAP
  proposals).
- **Binding user decisions (2026-09-30).**
  1. This ticket carries **no acceptance criteria**. ACs come later, when the work is scheduled.
  2. It is **later-stage (Stage 3) work, not V0 MVP scope**. Spec §4.3 excludes a policy engine
     from the MVP.

## Scope

1. **Storage location and format for scoped policies.** Decide where policies live and in what
   format, recorded in an ADR that closes ADR-054 open item 2. Cover the scope levels of spec
   §18.4 and §18.5: repository, language or framework, component, and folder. Cover inheritance
   (a narrower scope may add requirements and may weaken a broader mandatory rule only through
   an explicit, authorized override), conflict handling (a conflict produces a conflict
   decision, never a silent model-chosen winner), and stable ids that a local file can reference
   instead of copying an inherited rule. Decide whether `permission` (as used by POL-GIT-001)
   becomes a fourth rule type beside context, decision and verification, or lives in a separate
   permission store.
2. **A deterministic permission-lookup port.** A read-only port that answers "is actor X allowed
   to do action A in scope S without asking?" with `allowed`, `requires_confirmation` or
   `not_covered`, citing the policy id and version it used. It fails closed: an unlisted action
   is `not_covered`. Two kernel consumers:
   - the eligibility filter, which already has a `permission_denied` reason code
     ([design part 2](../../docs/analysis/2026-09-30-decision-kernel-design-2-contracts-registry-config.md));
   - host work packets, whose `allowed_operations` and `forbidden_operations` are derived from
     the lookup ([design part 5](../../docs/analysis/2026-09-30-decision-kernel-design-5-client-observability.md)).
   The port is exact code. No Jev or LLM judgement takes part, and no model output can widen
   its answer (spec §13.3).
3. **From conversation to policy record.** How an approved human decision made in conversation
   becomes a policy record: who drafts it (a template or a generative capability, as a
   proposal), how the human's approval is captured (`approved_by`, `approved_at`, the quoted
   source), versioning, preserved previous versions, and rollback (spec §19.2). A generative
   response cannot approve a policy or impersonate the human's answer (spec §7.8). POL-GIT-001
   was written by hand; this item makes the path repeatable.
4. **How Jev uses policies as known criteria (ADR-053).** A policy supplies known criteria, so
   Jev can judge applicability ("does this policy apply to this task?") and bounded questions
   against it, as in spec §18.4's `applicability_question`. Keep the split explicit: for
   POL-GIT-001, "is a PR needed for this change?" is a Jev judgement against approved criteria
   (none exist yet, so they must be proposed and approved first), while "may Claude open it
   without asking?" is the item 2 lookup.
5. **Relation to ADR-056 colony memory.** Outcome evidence (for example a git action that went
   wrong, or a repeated human override) may produce a POLICY GAP or a change proposal against a
   policy id and version. The proposal never activates without the human's review. Decide how
   policy ids and versions appear in the recorded traces, so that evidence can be scoped to the
   policy version that produced it (ADR-056 §3 rule 2, §9 Stage 1 recommendation).

## Out of Scope
- Anything in the V0 MVP. V0 keeps reading POL-GIT-001 only as `internal_principles` evidence
  through retrieval source `repo.principles`, which already has `docs/conventions` as a root.
- Changing POL-GIT-001's rule. Only BrainCandy can approve a new version.
- Automatic policy mutation, reinforcement-driven activation and the analytics job (Stage 4,
  ADR-056).
- Changing Claude Code harness permissions (`.claude/settings.json`) or any hook.

## Open Questions
- Is the store files in the repository (reviewable in PRs), a structured registry beside
  `config/capability_registry.json`, or a hybrid?
- Where do policies that span repositories (organization scope) live?
- Does a permission policy bind only Claude and its agents, or any host executor (spec §20)?

## Risk & Safety
- Touches money? No.
- Touches data? No. This commit adds one policy record and this ticket, both docs.
- Reversibility? Fully reversible. The later design must itself keep policy changes reversible
  (preserved versions and a rollback path).

## Comments

_(Append-only log — leave blank when authoring.)_
