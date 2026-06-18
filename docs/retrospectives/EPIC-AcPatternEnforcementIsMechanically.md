---
description: Retrospective for EPIC-AcPatternEnforcementIsMechanically (ACS-500f)
epic: EPIC-AcPatternEnforcementIsMechanically
date: 2026-06-18
---

# Retrospective: EPIC-AcPatternEnforcementIsMechanically
Date: 2026-06-18
Epic duration: 2026-06-17 to 2026-06-18
PR: #100 (scaffold), #102 (implementation)

## Summary

This epic implemented AC ACS-500f: AC pattern enforcement is mechanically guaranteed, not
prompt-only. Five sub-tickets were derived from the leaf ACs beneath ACS-500f using the
goal_to_epic.py pipeline. The deliverables were: a `check_ac_schema.py` hook registered in
commit_guardian.json that validates AC YAML files at commit time (including binding-completeness
and implements_pattern field-preservation checks); a fail-open error-handling wrapper ensuring
the hook never blocks unrelated commits on its own errors; a `check_ac_pattern_refs.py` hook
that aligns the business-analyst pattern-detection predicate with the deployed hook predicate;
and schema widening of `config/ac_store_schema.json` to accept all 1401+ real hierarchical AC
ids and the `pattern_slots` field while still rejecting malformed ids and unknown fields.

The drive surfaced several process friction points: the scaffold had to go through its own PR
(#100) because main is now behind a ruff branch-protection gate; EMU PR creation required
a REST fallback (`gh api -X POST .../pulls`); ticket 03 required agent substitution (workflow-
architect is not a ticket-phase agent); goal_to_epic.py wrote duplicate ticket files; and a
post-epic spot-check revealed that the in-loop PR reviewer conflated "ids match regex" with
"records validate", missing that 98.6% of the real AC store records were rejected by the
schema until ticket 04 widened it.

## Epic Facts

| Metric | Value |
|--------|-------|
| Ticket count | 5 |
| Completed tickets | 5 |
| Source AC | ACS-500f |
| Scaffold PR | #100 |
| Implementation PR | #102 |
| Commits (epic-related) | ~8 (scaffold + feat commits + archive) |
| Blocker comments | 0 (no `status: blocker` in any ticket) |
| Handoff comments | 0 (no `status: handoff` in any ticket) |
| Agent substitutions | 1 (ticket 03: workflow-architect replaced by llm-expert) |
| Pre-commit hook retries | 2 (tickets 02, 05: missing feedback-id lines caught at commit) |
| submit-failed events | 1 (ticket 02 ticket-supervisor comment, pre-epoch sink) |

## Phase Agent Counts (from ticket frontmatter)

| Phase | Signed Off | Failed | Needed |
|-------|-----------|--------|--------|
| python-coder | 4 | 0 | 0 |
| llm-expert (subst. for workflow-architect) | 1 | 0 | 0 |
| test-writer | 5 | 0 | 0 |
| test-runner | 5 | 0 | 0 |
| pr-reviewer | 5 | 0 | 0 |
| commit | 5 | 0 | 0 |
| pull-request | 5 | 0 | 0 |
| documentation-expert | 0 | 0 | 5 (not_needed) |
| sql-coder | 0 | 0 | 5 (not_needed) |

## Category Breakdown (Feedback System)

No structured feedback entries exist in feedback.jsonl for this epic. The epic pre-dates
or was outside the feedback system epoch for this drive. Ticket-level comments in
`## Comments` sections were used as the primary data source instead.

## What Went Well

- All 5 tickets completed without a single `status: blocker` or `status: handoff` — zero
  structural blockers across the entire drive.
- The agent substitution on ticket 03 (workflow-architect -> llm-expert) was handled
  autonomously by ticket-supervisor with a clear rationale comment, no user intervention.
- Tickets 01, 04, 05 all had clean commit phases. Tickets 02 and 05 fixed pre-commit
  hook violations (missing feedback-id lines) within the autofix loop without escalating.
- The fail-open pattern (`try/except Exception` with `# noqa: BLE001`) was correctly
  applied and validated by pr-reviewer against the project error-handling policy.
- Schema widening (ticket 04) independently verified 1403 existing store records all
  match the widened regex before sign-off — thorough coverage.
- PR #102 PR creation used the REST fallback (`gh api -X POST .../pulls`) under the
  EMU account without halting the drive.

## Friction Points

- **Scaffold-to-main friction (ticket ordering, pre-drive):** After `/create-epic`, the
  scaffold commit (Master_Plan.md + 5 stub tickets) had to go through its own PR (#100)
  because the ruff branch-protection gate on main rejects direct pushes. The documented
  Pre-Drive step "push scaffold to origin/main" via `git push origin main` no longer works.
  (See Proposed Improvements: Rule Update #1.)

- **EMU PR creation inconsistency (pull-request phase, ticket 03):** `gh pr create` was
  blocked at the GraphQL layer under the EMU account
  (`createPullRequest` returns "Unauthorized"). The REST fallback
  (`gh api -X POST /repos/:owner/:repo/pulls`) succeeded. Later tickets used an existing PR.
  No single documented stable procedure for the PR creation step under EMU accounts.
  (See Proposed Improvements: Rule Update #2 / KI-1.)

- **Agent substitution: workflow-architect not a ticket-phase agent (ticket 03):**
  goal_to_epic.py / generate_ticket_from_ac.py assigned `workflow-architect` as the
  implementing agent for ACS-500f-2. workflow-architect has `is_ticket_phase: false` and
  `signoff: false` in the registry. ticket-supervisor had to substitute llm-expert at
  runtime. The ticket-generation scripts have no guard against emitting non-ticket-phase
  agents.
  (See Proposed Improvements: KI-2.)

- **Duplicate ticket files from goal_to_epic.py (pre-drive):** goal_to_epic.py wrote each
  of the 5 tickets to BOTH `tickets/00_inbox/` root AND the epic folder
  (byte-identical duplicates), and wrote `implemented_by` back-refs pointing at the
  inbox-root path. Required manual deduplication and repointing before the drive started.
  (See Proposed Improvements: KI-3.)

- **Post-epic spot-check caught real schema defects the in-loop pr-reviewer missed:**
  pr-reviewer on ticket 04 (ACS-500f-3) signed off confirming "1403 existing store records
  all match" — but this was the python-coder's self-reported count, not an independent
  validation. The spot-check found the schema had previously rejected 98.6% of the real
  store (the old regex `^[A-Z]{2,6}-[0-9]{3}$` was too narrow). pr-reviewer did not run
  `python -c "import jsonschema; ..."` against the real store to verify AC4. This is a
  pattern of conflating "the implementation claims to handle all ids" with "it actually does."
  (See Proposed Improvements: Rule Update #3.)

- **Hooks committed to gitignored build-output tree (post-drive):** The `check_ac_schema.py`
  and `check_ac_pattern_refs.py` hooks were committed to `scripts/commit_guardian/` in the
  worktree (which is the gitignored build-output `leafcutter/scripts/` tree), not to
  `templates/commit-guardian/` (the deployable source in the package). On a fresh install,
  consumers would not receive these hooks. Caught by spot-check only. ticket 02's python-coder
  comment notes "the templates/ version already had it" but the initial commit landed in
  scripts/.
  (See Proposed Improvements: Rule Update #3 / KI-4.)

- **Pre-commit hook retries on missing feedback-id lines:** Both ticket 02 and ticket 05
  required a retry at the commit phase because ticket-supervisor comment headings lacked
  feedback-id lines (or used underscore instead of hyphen). The `check-feedback-id` hook
  blocked the commit in both cases. Not a blocker — handled by the autofix loop — but it
  represents recurring friction from the ticket-generation scaffold not pre-populating
  feedback-id placeholders in ticket-supervisor comment slots.

- **.security-allowlist symlink resolution hazard:** The `check_secrets` hook resolves its
  allowlist via the symlink target (workspace root), not the worktree root. Any worktree
  whose symlink points to a different workspace root silently gets a different allowlist.
  This is a latent maintenance hazard that becomes a real defect when a worktree is moved
  or the workspace structure changes.

## Knowledge Gaps Found

- The Pre-Drive Checklist in CLAUDE.md describes pushing the scaffold via `git push origin
  main`, but main is PR-only under the ruff gate. Engineers starting a new epic must know
  to go through a PR instead.

- No documented stable EMU-account PR-creation procedure exists in the Pre-Drive Checklist.
  The current section says "open the PR manually at https://..." but doesn't document the
  REST API fallback that succeeded in this drive.

- The agent_registry.json `is_ticket_phase` flag is not checked by goal_to_epic.py /
  generate_ticket_from_ac.py when emitting `assigned_agent`. A non-ticket-phase agent in
  `assigned_agent` field is silently accepted by the AC YAML schema.

- goal_to_epic.py writes tickets to both the epic subfolder and the inbox root. The
  `implemented_by` back-ref points at the wrong (inbox-root) path.

- The spot-check step in the finalize/close flow should include "validate schema against
  real data" and "confirm deployable source path (templates/ not scripts/)". These are
  not currently part of the finalize-feature checklist.

- pr-reviewer's ACs for schema changes should require an independent validation run
  against the real store, not just accepting the coder's self-reported count.

## Subagent Quality Trends

No supervisor feedback entries found for this epic (supervisors may pre-date
EPIC-SupervisorFeedback or no adjudication events occurred during this drive; feedback.jsonl
contains 0 entries in the subagent-quality category).

## Unresolved Feedback

There are 54 unresolved feedback entries in feedback.jsonl. These are from earlier epics
(EPIC-GoalToEpic, EPIC-Defineabehavioronce, etc.) — not from this epic. Run `/feedback-review`
to triage them.

---

## Proposed Improvements

### Rule Update 1: Pre-Drive Checklist — scaffold goes through a PR, not git push origin main

The Pre-Drive section "Push scaffold commit before creating the epic worktree" currently says:

```
git -C <repo> push origin main
```

This now fails because main is behind the ruff branch-protection gate. The correct procedure
is to push the scaffold to a branch and open a PR.

Proposed diff for the "Push scaffold commit before creating the epic worktree" subsection
in `CLAUDE.md` (Pre-Drive Checklist section):

```diff
-### Push scaffold commit before creating the epic worktree
+### Push scaffold commit to origin before creating the epic worktree

 After running `/create-epic`, confirm the scaffold commit (Master_Plan.md + sub-ticket
-stubs) is already on `origin/main` before calling `worktree-agent` to create the epic
-worktree.
+stubs) has been merged to `origin/main` before calling `worktree-agent` to create the
+epic worktree.

-```bash
-# The scaffold files must be reachable from origin/main (empty output = nothing unpushed):
-git -C <repo> log --oneline origin/main..main
-```
-
-If that lists the scaffold commit (i.e. it is unpushed), push first:
-```bash
-git -C <repo> push origin main
-```
+**main is PR-only (ruff branch-protection gate).** Direct pushes to main are rejected.
+The scaffold must go through its own PR:
+
+```bash
+# 1. Push the scaffold commit to a short-lived branch:
+git -C <repo> push origin main:scaffold/EPIC-<name>
+
+# 2. Open a PR targeting main and merge it before continuing:
+#    https://github.com/<org>/<repo>/compare/main...scaffold/EPIC-<name>
+
+# 3. Verify the scaffold is on origin/main before creating the epic worktree:
+git -C <repo> fetch origin
+git -C <repo> log --oneline origin/main | head -3
+```

 **If you skip this:** the epic worktree (created from `origin/main`) diverges at a stale
 point — the scaffold files are unreachable inside it and ticket agents cannot read them
 until the scaffold commit is cherry-picked onto the epic branch. Worse, when the scaffold
 later reaches `origin/main` independently, the epic PR hits an add/add merge conflict on
 those files at finalize (resolve in favor of the branch — the `status: done` versions win).
-(Source: EPIC-AcPipelineDeployGaps retrospective, 2026-06-17, Findings #1 + #5)
+(Source: EPIC-AcPipelineDeployGaps retrospective 2026-06-17 Findings #1 + #5;
+ confirmed in EPIC-AcPatternEnforcementIsMechanically 2026-06-18.)
```

Routing: `CLAUDE.md` — Pre-Drive Checklist section (process convention, repo-local).

---

### Rule Update 2: Pre-Drive Checklist — stable EMU PR-creation procedure

The existing EMU section documents opening the PR manually via the GitHub web UI. This drive
found that `gh pr create` GraphQL is blocked under EMU but the REST endpoint works.

Proposed diff for the "EMU account: open epic PR before drive" subsection in `CLAUDE.md`:

```diff
 ### EMU account: open epic PR before drive (if applicable)

 **What to check:** If you are operating under an Enterprise Managed User (EMU)
 GitHub account, `gh pr create` is blocked at the CLI level. Before dispatching
 any tickets:

 ```bash
 # Switch to the non-EMU account
 gh auth switch --user urlmonitor

 # Push the epic branch to origin first
 git push -u origin EPIC-<name>

 # Then open the PR manually at:
 # https://github.com/<org>/<repo>/compare/main...EPIC-<name>
 ```

+**REST API fallback (if gh auth switch is unavailable):**
+If `gh auth switch --user urlmonitor` is not available in the current shell,
+the REST API endpoint works where the GraphQL createPullRequest is blocked:
+
+```bash
+gh api -X POST /repos/urlmonitor/leafcutter-ai/pulls \
+  --field title="feat(ac-store): <title>" \
+  --field head="EPIC-<name>" \
+  --field base="main" \
+  --field body="<body>"
+```
+
+This was confirmed working in EPIC-AcPatternEnforcementIsMechanically PR #102 (2026-06-18).
+Later tickets that push to an existing PR branch do not need to re-create; they just push.
+
 Once the PR exists, the `pull-request` phase on each ticket should detect it via
 `gh pr list --head EPIC-<name>` and push to the existing branch without re-opening.

 **If you skip this:** The pull-request phase on the first ticket that tries `gh pr
 create` under the EMU account will fail with "Unauthorized: As an Enterprise Managed
 User, you cannot access this content (createPullRequest)".
```

Routing: `CLAUDE.md` — Pre-Drive Checklist section (process convention, repo-local).

---

### KI-1: goal_to_epic.py / generate_ticket_from_ac.py must guard against non-ticket-phase agents

**Proposed Knowledge Item:**

> When `goal_to_epic.py` or `generate_ticket_from_ac.py` emits an `assigned_agent` value
> into a generated ticket, it reads the assigned_agent from the AC YAML `assigned_agent`
> field (or `it_requirements.assigned_agent`). It does NOT validate that the named agent
> has `is_ticket_phase: true` in `agent_registry.json`.
>
> Agents with `is_ticket_phase: false` (e.g. `workflow-architect`) cannot sign off on a
> ticket phase; ticket-supervisor will either fail or must substitute another agent at
> runtime.
>
> **Fix:** `generate_ticket_from_ac.py` should load `agent_registry.json` and, if the
> assigned agent has `is_ticket_phase: false`, substitute the agent recommended in the AC
> `it_requirements` or fall back to `llm-expert` (the canonical substitute for prompt-
> engineering work) or `python-coder` (for implementation work). A warning should be emitted
> naming the substitution.
>
> **Ticket to file:** TICKET-goal_to_epic-agent-phase-guard.md (create-ticket against
> the goal_to_epic component).
>
> Source: EPIC-AcPatternEnforcementIsMechanically, ticket 03 (ACS-500f-2), 2026-06-17,
> ticket-supervisor substitution comment.

Routing: `docs/how-to/` — a how-to doc for "avoid non-ticket-phase agents in AC assignments"
or as a code-level comment in `generate_ticket_from_ac.py`. The code fix belongs in a new
ticket; the KI itself routes to a project how-to.

---

### KI-2: goal_to_epic.py writes duplicate ticket files — inbox-root and epic folder

**Proposed Knowledge Item:**

> `goal_to_epic.py` (as of 2026-06-17) writes each generated ticket to BOTH:
> - `tickets/00_inbox/<ticket_filename>.md` (inbox root)
> - `tickets/00_inbox/epics/EPIC-<Name>/<N>_<ticket_filename>.md` (epic folder)
>
> Both copies are byte-identical at creation time. The `implemented_by` back-ref written
> into each AC YAML file points at the inbox-root path (the first write target), not the
> epic-folder path.
>
> **Impact:** Engineers must manually deduplicate before starting the drive, and must
> repoint `implemented_by` back-refs to the epic-folder path so that ticket-supervisor and
> ac-fulfillment-gate can find the ticket.
>
> **Fix:** `goal_to_epic.py` should write tickets ONLY to the epic folder and never to the
> inbox root. The `implemented_by` back-ref should point at the epic-folder path.
>
> **Ticket to file:** This is a known bug. File a ticket against goal_to_epic component.
>
> Source: EPIC-AcPatternEnforcementIsMechanically drive setup, 2026-06-17, manual
> deduplication step.

Routing: `docs/architecture/` reference doc for goal_to_epic.py known limitations, or
directly as a bug-report ticket. The KI itself documents the workaround until fixed.

---

### Rule Update 3: pr-reviewer must run independent validation against real data for schema-change ACs

The pr-reviewer on ticket 04 accepted a python-coder claim that "all 1403 existing store
records match" without independently running the schema validation command. The post-epic
spot-check found that the previous (pre-ticket-04) schema actually rejected 98.6% of the
real store.

Additionally, the hooks were initially committed to `scripts/commit_guardian/` (the
gitignored build-output tree) rather than `templates/commit-guardian/` (the deployable
package source). pr-reviewer did not verify the deployment path.

Proposed addition to pr-reviewer instructions or to the finalize-feature checklist:

```diff
+## Schema-Change AC Verification (pr-reviewer)
+
+When reviewing a ticket whose ACs include "no currently-valid stored record is rejected
+by the schema" or equivalent bulk-validation language:
+
+1. Run the validation independently — do NOT accept the coder's self-reported count:
+   ```bash
+   python -c "
+   import json, jsonschema, pathlib
+   schema = json.loads(pathlib.Path('config/ac_store_schema.json').read_text())
+   errors = []
+   for f in pathlib.Path('docs/acceptance-criteria').rglob('*.yaml'):
+       import yaml
+       rec = yaml.safe_load(f.read_text())
+       try:
+           jsonschema.validate(rec, schema)
+       except jsonschema.ValidationError as e:
+           errors.append((str(f), str(e.message)))
+   print(f'{len(errors)} validation errors')
+   "
+   ```
+2. Verify that any new hook script is in `templates/<hook-dir>/` (the deployable
+   package source), not only in `scripts/` (the build-output tree that is gitignored
+   in the workspace).
+
+Source: EPIC-AcPatternEnforcementIsMechanically post-epic spot-check, 2026-06-18.
```

Routing: `templates/agents/pr-reviewer.md` (agent template instruction addition) or
`docs/how-to/` as a how-to for reviewing schema-change tickets. Given the impact,
routing to the pr-reviewer agent template is preferred.

---

### KI-3: finalize / spot-check must include "validate against real data" and "build-simulation deploy" checks

**Proposed Knowledge Item:**

> Two classes of defect that in-loop phase gates routinely miss:
>
> **Class 1 — Schema validation proxy mismatch:** An agent reports "all N records match"
> without running the actual schema validator. The check it ran (e.g. regex match on IDs
> only) is a proxy for the real AC, which requires full jsonschema validation of every record.
> The spot-check step in finalize-feature should include a bulk schema validation command
> for any ticket that touched a schema file.
>
> **Class 2 — Deployable-path miss:** A hook or script is implemented in `scripts/` (the
> build-output tree, gitignored in the workspace) and NOT in `templates/` (the installable
> source). The file exists and works in the author's local environment but would not be
> present after a fresh consumer install. The spot-check step should verify that any new
> hook exists under `templates/` and is registered in `templates/commit-guardian/
> commit_guardian.json`.
>
> **Recommended spot-check additions:**
> - After any schema-change ticket: run jsonschema validation against all real store records.
> - After any commit-guardian hook ticket: verify the hook file exists at
>   `templates/commit-guardian/<hook_name>.py` and is registered in
>   `templates/commit-guardian/commit_guardian.json`.
>
> Source: EPIC-AcPatternEnforcementIsMechanically post-epic spot-check, 2026-06-18.

Routing: `docs/how-to/` — how-to for post-epic spot-checks, or an addition to the
`finalize-feature` skill (`templates/skills/building-epics/SKILL.md` finalization section).

---

### KI-4: .security-allowlist symlink resolves via workspace root, not worktree root

**Proposed Knowledge Item:**

> The `check_secrets` pre-commit hook resolves its `.security-allowlist` file by following
> the symlink `<worktree-root>/.leafcutter` to the workspace root, then looking up
> `.security-allowlist` relative to that target. In a standard worktree setup:
>
> - Main tree: `leafcutter/.leafcutter/` — symlink resolves here, allowlist is correct.
> - Epic worktree: `<worktree-path>/.leafcutter` → same symlink target, same allowlist.
>
> **Latent hazard:** If the workspace structure changes (e.g. the worktree is moved, or
> `.leafcutter` is a copy rather than a symlink), the resolved allowlist path will differ
> silently. Secrets that should be allowlisted may trigger false positives (or false
> negatives if the allowlist at the resolved path is more permissive).
>
> **Mitigation:** The worktree pre-commit config check (already in the Pre-Drive Checklist)
> partially covers this. When creating a worktree on NTFS/WSL2 where symlinks are
> restricted and a file copy is used instead of a symlink, manually verify that the copied
> `.pre-commit-config.yaml` points to the same allowlist path as the main tree.
>
> Source: EPIC-AcPatternEnforcementIsMechanically drive observation, 2026-06-18.

Routing: `CLAUDE.md` — Pre-Drive Checklist, as an additional note under "Worktree pre-commit
config (MANDATORY for worktree-based drives)".
