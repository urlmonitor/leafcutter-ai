---
title: "POL-GIT-001: Git Operations Claude Performs Without Asking (leafcutter-ai)"
description: "Approved repository-scoped policy recorded from BrainCandy's decision of 2026-09-30. In leafcutter-ai, Claude and its agents commit, create branches and worktrees, push non-main branches and open pull requests without asking first; merging to main, force-pushing and pushing to main still need the human's confirmation. It is the first learned human decision for the Leafcutter kernel and the seed example for ADR-054 open item 2, not a decision about where or how policies are stored."
type: reference
status: active
created: 2026-09-30
last_updated: 2026-09-30
components:
  - git_vcs_operations
  - decision_kernel
related_docs:
  - docs/architecture/adrs/ADR-053-intelligence-selection-deterministic-jev-llm-human.md
  - docs/architecture/adrs/ADR-054-process-representation-and-maturity-model.md
  - docs/architecture/adrs/ADR-056-colony-memory-evidence-reinforcement.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-7-later-stages.md
  - docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3-5-client-observability-safeguards.md
  - docs/analysis/2026-09-30-decision-kernel-design-4-jev-and-capabilities.md
---

# POL-GIT-001: Git operations Claude performs without asking (leafcutter-ai)

> **What this record is.** An approved policy, version 1.0, and the first learned human
> decision recorded for the Leafcutter kernel. It is the seed example for
> [ADR-054][adr054] open item 2 ("Where policies are stored"). Its location
> (`docs/conventions/`) and its format (a fenced JSON block shaped after the illustrative policy
> data in [spec §18.4][spec7]) are provisional. They are **not** a decision about the policy
> store's final location or format. [TICKET-20260930-PolicyStore][ticket] owns that decision.

## The rule

In the leafcutter-ai repository, Claude and the agents it dispatches:

| | Git actions |
|---|---|
| **May do without asking first** | Commit. Create branches. Create worktrees. Push branches other than `main` (without force). Open pull requests. |
| **Must get the human's confirmation for** | Merging a pull request (or anything else) into `main`. Force-pushing any branch. Pushing directly to `main`. |
| **Are not covered by this policy for** | Any other git action. This record grants nothing for it, so the normal default applies: ask first. |

The policy removes the ask-first step. It removes no gate. Pre-commit hooks still run. The
commit-delegation guard still applies: commits go through the `commit` agent, and a direct
`git commit` is blocked. `--no-verify` and other guard bypasses stay forbidden. This record does
not change `.claude/settings.json` or any hook, and the Claude Code harness permission system
still applies.

The scope is this repository only. Other repositories that install Leafcutter get no permission
from this record.

## Policy record

The structured fields follow the shape of spec §18.4's illustrative `LG-PARALLEL-001`
(`id`, `version`, `scope`, `maintenance.approval_required_for_policy_change`), extended with the
authority and provenance fields that a learned human decision needs.

```json
{
  "id": "POL-GIT-001",
  "version": "1.0",
  "rule_type": "permission",
  "scope": {"repository": "leafcutter-ai"},
  "subject": "git_operations",
  "applies_to": ["claude", "claude_dispatched_agents"],
  "rule": {
    "allowed_without_asking": [
      "commit",
      "create_branch",
      "create_worktree",
      "push_non_main_branch",
      "open_pull_request"
    ],
    "requires_human_confirmation": [
      "merge_to_main",
      "force_push",
      "push_to_main"
    ],
    "unlisted_action": "not_covered_ask_first"
  },
  "authority": {
    "approved_by": "human:BrainCandy",
    "approval_status": "approved",
    "approved_at": "2026-09-30"
  },
  "source": {
    "kind": "human_decision_in_conversation",
    "decided_by": "human:BrainCandy",
    "date": "2026-09-30",
    "quote": "you always create PRs and handle all git stuff - in this repo at least … this should be some decision already that jev then should use when deciding a PR is needed … a nice example of something you should learn."
  },
  "rationale": "Routine git work in this repository is Claude's job. Asking before every commit, push or PR adds friction without adding safety: hooks and guards still run, and nothing reaches main without a merge the human confirms. Actions that rewrite shared history or land on main stay with the human, who holds authority and risk acceptance (ADR-053 section 1).",
  "mechanism": {
    "permission_question": "deterministic_lookup",
    "pr_needed_question": "jev_against_approved_criteria",
    "model_output_may_widen": false,
    "v0_enforcement": "none; surfaced as internal_principles evidence by retrieval source repo.principles"
  },
  "supersedes": null,
  "maintenance": {
    "approval_required_for_policy_change": true,
    "approver": "human:BrainCandy",
    "preserve_previous_versions": true,
    "rollback": "revert to the previous approved version"
  }
}
```

Field notes:

- `rule_type: permission` is not one of the three rule types in spec §18.4 (context, decision,
  verification). It is an authority rule that exact checks consult before any judgement runs.
  Whether "permission" becomes a fourth rule type or lives in a separate permission store is for
  the policy-store ticket to decide.
- `push_non_main_branch` means an ordinary push. A force-push is always `force_push`, whatever
  the branch.
- `unlisted_action` is lookup semantics, not part of the human's grant. An action that is not
  listed is not covered, so the lookup answers "ask first". The policy fails closed.

## Two questions, two mechanisms (ADR-053)

When a change is finished, two different questions come up. They go to different mechanisms.

| Question | Kind | Answered by |
|---|---|---|
| Is a PR needed for this change? | A bounded semantic judgement | Jev, against known criteria ([ADR-053][adr053] §1, §2) |
| May Claude do this git action without asking? | Permission and authority | A deterministic lookup against this approved policy ([ADR-053][adr053] §5). Never Jev, never an LLM. |

**"Is a PR needed for this change?"** is a bounded judgement that Jev may make against criteria.
This policy does not supply those criteria. It says who acts and whether to ask first, not when
a PR is needed. Jev must not invent the criteria ([ADR-053][adr053] §2). No approved PR-need
criteria exist yet. Until they do, the question follows the escalation path in ADR-053 §3: an
LLM may propose criteria, a human approves them, and only then does Jev decide against them.

**"May Claude do this git action without asking?"** is a permission question. ADR-053 §1 gives
authority to a human. ADR-053 §5 makes permissions and approved policy constraints exact checks
that run before Jev evaluates anything. The answer is therefore a deterministic lookup of the
action in `rule`:

```text
lookup(action, repository="leafcutter-ai")
  action in allowed_without_asking       --> proceed without asking
  action in requires_human_confirmation  --> ask the human (needs_human)
  action not listed                      --> not covered: ask the human
```

No Jev or LLM judgement takes part in this lookup. A confidence score cannot turn "requires
confirmation" into "allowed".

**Model output can never widen this policy.** Model output cannot expand permissions, remove
mandatory gates or rewrite active policies ([spec §13.3][spec5]). A generative response cannot
impersonate a human answer, grant itself permissions or approve a policy (spec §7.8). The lookup
ignores any Jev or LLM output that claims a wider permission, for example "merging is fine
here". Only a new version that the human approves changes the rule (see Change rule).

Example flow. Jev judges "PR needed: yes" against approved criteria. The lookup for
`open_pull_request` returns `allowed_without_asking`, so Claude opens the PR without asking.
Later the lookup for `merge_to_main` returns `requires_human_confirmation`, so the kernel raises
a human question, whatever any model's confidence.

## Mechanism in V0

- **Nothing enforces this at runtime yet.** V0 has no policy engine and no permission-lookup port
  (spec §4.3). [ADR-054][adr054] §4 records that policies (Level 2) have no runtime home in V0.
  Today people and Claude read this record as a project rule, as they read `CLAUDE.md`.
- **Retrieval surfaces it as evidence.** In `config/kernel_config.default.json`, source
  `repo.principles` (kind `repo_text`, category `internal_principles`) has `docs/conventions` as
  a root. The `repo_text` strategy walks that folder, so a research need for
  `internal_principles` can find this file when the query terms match. Retrieved text is
  evidence, not instructions ([design part 4][design4]; spec §13.3). V0 can therefore cite this
  record in a decision, but it cannot enforce it as a permission.
- **The deterministic lookup is future work.** [TICKET-20260930-PolicyStore][ticket] designs the
  store and a permission-lookup port. The kernel's eligibility filter (reason code
  `permission_denied`) and host work packets (`allowed_operations`, `forbidden_operations`) can
  consult that port.

## Change rule

- Any change to this policy (widening, narrowing, re-scoping or retiring it) needs the explicit
  approval of the human, BrainCandy. The approval is recorded with its date and source
  (spec §18.4 `approval_required_for_policy_change`; spec §19.2 review before activation).
- A change creates a new version. The previous version is preserved, in git history and in the
  version table below, and rolling back means reverting to the previous approved version.
- An LLM, Jev or a colony-memory trail may *propose* a change, for example after a git action
  goes wrong. A proposal is recorded as `approval_status: proposed` and changes nothing until the
  human approves it. Trails may rank and propose; they may not legislate
  ([ADR-056][adr056] §3 rule 5).

## Provenance

- **Decided by:** BrainCandy, in conversation on 2026-09-30. The user's words:
  "you always create PRs and handle all git stuff - in this repo at least … this should be some
  decision already that jev then should use when deciding a PR is needed … a nice example of
  something you should learn."
- **Interpretation applied** (by the orchestrating session, recorded as the approved reading):
  1. In leafcutter-ai, Claude and its agents perform all routine git work (commits, branches,
     worktrees, pushes, opening PRs) without asking first.
  2. Merging PRs into `main` is not covered and still needs the user's confirmation.
  3. The scope is this repository only.
- **Why it is a learned decision.** The human answered an authority question once, in
  conversation. Recording the answer means it need not be asked again. This is the learning loop
  of [ADR-054][adr054] §6 applied to a human decision instead of LLM reasoning.

## Version history

| Version | Date | Change | Approved by |
|---|---|---|---|
| 1.0 | 2026-09-30 | Initial record | human:BrainCandy |

[adr053]: ../architecture/adrs/ADR-053-intelligence-selection-deterministic-jev-llm-human.md
[adr054]: ../architecture/adrs/ADR-054-process-representation-and-maturity-model.md
[adr056]: ../architecture/adrs/ADR-056-colony-memory-evidence-reinforcement.md
[spec5]: ../analysis/2026-09-30-leafcutter-kernel-spec-rev3-5-client-observability-safeguards.md
[spec7]: ../analysis/2026-09-30-leafcutter-kernel-spec-rev3-7-later-stages.md
[design4]: ../analysis/2026-09-30-decision-kernel-design-4-jev-and-capabilities.md
[ticket]: ../../tickets/00_inbox/TICKET-20260930-PolicyStore.md
