# Retrospective: EPIC-FrontendAgent

Date: 2026-05-28
Epic duration: 2026-05-28 (11:28 UTC+2) to 2026-05-28 (12:32 UTC+2)
Commits: 10 (branch: 2621ddb → 680ad2a, merged via PR #19)

---

## Summary

EPIC-FrontendAgent introduced `frontend-coder` as a first-class sibling implementation
agent in the leafcutter-ai package — a peer to `python-coder` and `sql-coder` rather
than a nested sub-agent. The epic delivered six tightly-coupled tickets in a single
epic branch: the agent template, two optional skills (`webapp-testing`,
`frontend-design`), onboarding wizard integration, agent registry and skills config
extensibility (with TDD-verified config loader changes), and BA/supervisor routing
wiring. All six tickets passed every required phase with zero blockers, zero handoffs,
and zero retries.

The epic shipped the first optional-skill pair in the package, establishing a
file-existence detection contract (ADR-005) as the canonical pattern for conditional
skill loading. The batch parallelism strategy (tickets 02, 03, 05 in batch 2; tickets
04, 06 in batch 3) proved effective: disjoint `files_touched` sets allowed concurrent
documentation-expert passes that fed into a single batch-2 commit (711f151) and a
single batch-3 commit (b45756e).

---

## Metrics

| Phase | Signed Off | Failed | Needed (open) |
|---|---|---|---|
| architect-review | 6 | 0 | 0 |
| adr-author | 1 | 0 | 0 |
| documentation-expert | 5 | 0 | 0 |
| python-coder | 1 | 0 | 0 |
| test-writer | 1 | 0 | 0 |
| test-runner | 1 | 0 | 0 |
| pr-reviewer | 6 | 0 | 0 |
| commit | 6 | 0 | 0 |
| pull-request | 6 | 0 | 0 |
| sql-coder | 0 (all not_needed) | 0 | 0 |

---

## Category Breakdown (Feedback System)

| Category | Count |
|---|---|
| complete | 26 |
| knowledge-gap | 0 |
| convention-ambiguity | 0 |
| blocker | 0 |

All 26 feedback entries were `complete`. No friction categories recorded.

---

## Epic Facts

| Metric | Value |
|---|---|
| Ticket count | 6 |
| Completed tickets | 6 |
| Git commits (branch) | 10 |
| Blocker comments | 0 |
| Handoff comments | 0 |
| Feedback entries | 26 |
| PR | #19 |

---

## What Went Well

- **Perfect phase pass rate.** All 6 tickets passed every required phase on the first
  attempt. Zero failed entries across all phases in `phase_agent_counts`.

- **ADR-first design.** ADR-005 was authored by `adr-author` before any implementation
  work began on ticket 01. The ADR captured three decisions (sibling agent rationale,
  optional-skill file-existence detection contract, priority-8 slot) that were
  referenced by every subsequent ticket, preventing re-derivation of design choices.

- **Batch parallelism used correctly.** Tickets 02, 03, and 05 had disjoint
  `files_touched` sets and ran concurrently in batch 2, collapsing to a single commit
  (SHA 711f151, 11 files, 840 insertions). Tickets 04 and 06 ran concurrently in
  batch 3 (commit b45756e). Total wall-time was compressed significantly.

- **TDD loop on ticket 05.** The only ticket requiring `python-coder` also required
  `test-writer` and `test-runner`. All 20 tests were written first (red baseline),
  then made green by `python-coder`. Regression suite (5 existing tests) stayed green.

- **Single-PR-per-epic convention held.** All 6 tickets accumulated on the epic branch
  without per-ticket PRs; PR #19 merged the full set atomically.

- **Antigravity compatibility built in from day 1.** Both `webapp-testing` SKILL.md
  and the onboard wizard step 5b include explicit Antigravity skip logic, preventing
  a category of future adopter confusion.

---

## Friction Points

- **`submit-failed` feedback IDs on pull-request phase (tickets 02, 03, 05).** Three
  tickets recorded `feedback-id: (submit-failed)` in their `pull-request` comment
  blocks. The phase itself passed (comments read "Single-PR-per-epic convention: no
  per-ticket PR"), but the feedback system failed to assign an ID for these events.
  This is a recurrence of the feedback-sink reliability issue documented in
  TICKET-20260527-FeedbackSinkPreDriveCheck — the feedback.jsonl write succeeded for
  most events but the `pull-request` phase events for batch-2 tickets lost their IDs.
  The retrospective tooling was still functional because the structured feedback for
  all 26 entries was captured; only 3 `pull-request` events lacked IDs (no data loss
  for analysis purposes, but metadata is incomplete).

- **`extract_epic_facts.py` did not capture git dates.** The script returned
  `git_commit_count: 0` and null dates, because the epic folder was moved to
  `tickets/99_done/` before the script ran and the script's git-log query uses folder
  paths rather than branch names. Git dates were recovered manually from `git log`.

- **Timestamp precision in sign-off blocks.** Tickets 04 and 06 recorded sign-offs as
  "2026-05-28 (current session)" rather than with a specific time. This made
  chronological ordering of the drive ambiguous in retrospect.

---

## Knowledge Gaps Found

- **No documented contract for `feedback-id: (submit-failed)` sentinel.** When the
  feedback system cannot write an ID, agents write the literal string
  `(submit-failed)` in the comment block. There is no documented convention for what
  this means, how to detect it in aggregate, or whether these events should be
  retried. The aggregate.py script does not flag these.

- **`extract_epic_facts.py` git-date limitation undocumented.** The script silently
  returns null git dates when the epic folder has been moved to `99_done/` before the
  retro runs. There is no warning in the script output or the retro instructions about
  this limitation.

- **Optional-skill `allow-tools` constraints not validated by build.py.** The
  `webapp-testing` skill uses `allowed-tools: Bash Read Write` and `frontend-design`
  uses `allowed-tools: Read`. These constraints are declared in SKILL.md frontmatter
  but there is no build-time check that the frontmatter is valid or that the
  `allowed-tools` key is present. A malformed skill frontmatter would deploy silently.

---

## Subagent Quality Trends

No supervisor feedback entries found for this epic (supervisors may pre-date
EPIC-SupervisorFeedback or no adjudication events occurred during this drive).

---

## Proposed Improvements

---

### KI-1: `submit-failed` feedback sentinel — meaning and handling

**Proposed Knowledge Item:**

> When the feedback system cannot resolve a feedback ID at submission time, agents
> record the sentinel string `(submit-failed)` in the ticket's `## Comments` block
> rather than a real UUID. This is a known degraded-mode behaviour. It does NOT mean
> the phase failed — the phase commentary is still valid and the sign-off still counts.
>
> Detection: `grep -r "submit-failed" tickets/` will surface all affected entries.
> The `aggregate.py` script does not currently flag these entries; they are invisible
> to the feedback summary.
>
> Mitigation during a drive: if the feedback sink pre-drive check (CLAUDE.md,
> Pre-Drive Checklist) passes but `submit-failed` sentinels still appear, the most
> likely cause is a race condition on the JSONL file during batch-parallel commits.
> No action is required during the drive; note the count in the retrospective.

**Routing:** `docs/explanation/` — this is explanatory reference material about a
system behaviour, not a rule or ADR-level decision. Suggested filename:
`docs/explanation/feedback-submit-failed-sentinel.md`.

**Proposed diff to present for approval:**

```diff
--- /dev/null
+++ docs/explanation/feedback-submit-failed-sentinel.md
@@ -0,0 +1,28 @@
+# Feedback submit-failed sentinel
+
+## What it means
+
+When the feedback system cannot resolve a feedback ID at write time, agents record
+the literal string `(submit-failed)` in the ticket's `## Comments` block instead of
+a real UUID (e.g. `fb_2026-05-28_aa635bbd`).
+
+This is a known degraded-mode behaviour. It does NOT mean the phase failed — the
+phase commentary is still valid and the sign-off still counts. Only the correlation
+ID is missing.
+
+## Detection
+
+```bash
+grep -r "submit-failed" tickets/
+```
+
+## Impact on retrospectives
+
+`aggregate.py` does not flag `(submit-failed)` entries — they are invisible to the
+feedback summary. The retro author should run the grep above and note the count in
+the Friction Points section.
+
+## Mitigation
+
+If the feedback sink pre-drive check (CLAUDE.md Pre-Drive Checklist) passes but
+`submit-failed` sentinels still appear, the most likely cause is a write-ordering
+race during batch-parallel commits. No corrective action is needed during the drive.
+Note the count in the retrospective and move on.
```

---

### KI-2: `extract_epic_facts.py` returns null git dates when run post-move

**Proposed Knowledge Item:**

> `extract_epic_facts.py` determines git dates by running `git log` scoped to the
> epic folder path. When the epic has already been moved to `tickets/99_done/` before
> the retro runs, the script's folder-path query returns no commits and reports
> `git_commit_count: 0` with null dates. This is a silent failure — the script exits
> 0 with no warning.
>
> Workaround: recover git dates manually with:
> ```bash
> git log --oneline <first-epic-commit>..<merge-commit>
> git show <first-epic-commit> --format="%ci" --quiet | head -1
> git show <merge-commit> --format="%ci" --quiet | head -1
> ```

**Routing:** `CLAUDE.md` Pre-Drive Checklist section — this is operational guidance
for running a retro correctly, best placed inline where the retrospective agent reads
its instructions. However, since `CLAUDE.md` is a knowledge home that requires user
approval before modification, this is presented as a diff.

**Proposed diff for `CLAUDE.md` (leafcutter-ai repo):**

```diff
--- a/CLAUDE.md
+++ b/CLAUDE.md
@@ ... (Pre-Drive Checklist section — end) ...
+
+## Post-Epic Retrospective Notes
+
+### extract_epic_facts.py git-date limitation
+
+`extract_epic_facts.py` queries git log by epic folder path. If the epic folder has
+already been moved to `tickets/99_done/` before the retro runs, the script returns
+`git_commit_count: 0` and null dates (silent failure — exit 0).
+
+Workaround — recover dates manually:
+```bash
+git log --oneline <first-commit>..<merge-commit>
+git show <first-commit> --format="%ci" --quiet | head -1
+git show <merge-commit> --format="%ci" --quiet | head -1
+```
```

---

### KI-3: Skill frontmatter validation gap

**Proposed Knowledge Item:**

> `build.py` deploys skill SKILL.md files from `templates/skills/*/SKILL.md` to
> `.claude/skills/*/SKILL.md` but does not validate the YAML frontmatter of skill
> files. In particular, the `allowed-tools` key (which constrains what tools the
> skill's hosting agent can use) is not checked for presence or valid values.
>
> A malformed skill frontmatter deploys silently and only surfaces as a runtime error
> when the skill is invoked.
>
> Until a build-time check is added, the `pr-reviewer` phase for skill-authoring
> tickets must explicitly verify: (a) frontmatter is valid YAML, (b) `name` key is
> present, (c) `allowed-tools` key is present and contains only valid tool names.

**Routing:** `docs/architecture/adrs/` — this is an architectural constraint gap that
warrants either a new ADR documenting the limitation, or an addition to ADR-005
(which covers the optional-skill contract). Alternatively, as a lighter-weight
interim measure, this can be added to the `pr-reviewer` agent's sign-off checklist
in `templates/agents/pr-reviewer.md`.

The lighter-weight interim path is recommended: add a checklist item to
`templates/agents/pr-reviewer.md`.

**Proposed diff for `templates/agents/pr-reviewer.md`:**

```diff
--- a/templates/agents/pr-reviewer.md
+++ b/templates/agents/pr-reviewer.md
@@ ... (existing skill-file review checklist, if present) ...
+
+### Skill file review checklist (applies when ticket authors a SKILL.md)
+
+- [ ] YAML frontmatter is valid (no parse errors)
+- [ ] `name` key is present and matches the skill directory name
+- [ ] `allowed-tools` key is present and contains only valid tool names
+       (valid: Bash, Read, Write, Edit, Agent, mcp__*)
+- [ ] Input contract section is present (what the calling agent passes)
+- [ ] Output contract section is present (what the skill returns)
```

---

**Please review the three proposed improvements above.**

For each one, reply:
- `yes` — apply the change (I will make the edit)
- `skip` — skip this item
- `edit <revised text>` — revise before applying

None of the above changes have been applied. Awaiting your approval per item.
