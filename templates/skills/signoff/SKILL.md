---
allowed-tools: Read, Edit
description: Use when a phase agent finishes work on a ticket OR when a supervisor
  needs to validate ticket state. Provides the canonical status enum (not_needed |
  needed | signed_off | failed), the atomic sign-off recipe that updates frontmatter
  and the Sign-offs checklist together, the comment-append recipe with parser-strict
  heading schema, the failed-path protocol for blockers, and the validator rules enforced
  by the parity guard. Pulled in by every phase agent (python-coder, sql-coder, pr-reviewer,
  commit, etc.) and by both supervisors (epic-supervisor, ticket-supervisor).
name: signoff
---

# signoff

This skill is the **single source of truth** for ticket-phase status management. Every phase agent invokes it as its final action when given a `ticket_path`; both `epic-supervisor` and `ticket-supervisor` use it to validate ticket state before transitioning.

If you change anything in this file, the parity guard and every consuming agent will see the change at the next invocation — that's the point. Adding a new status or a new comment tag is an edit to this one file, never an ad-hoc choice in an agent prompt.

---

## §1 Status Enum (canonical)

| Status | Meaning | Set by |
|---|---|---|
| `not_needed` | The agent is explicitly excluded from this ticket. Creator/refiner determined the work doesn't require this agent. | `business-analyst`, `refinement` |
| `needed` | The agent is required for this ticket and has not yet completed. | `business-analyst`, `refinement` |
| `signed_off` | The agent ran, the work passed acceptance, and a `## Sign-offs` entry exists with timestamp. | The agent itself, on success. |
| `failed` | The agent ran but the work did not pass acceptance. A `(status: blocker)` comment must accompany. | The agent itself, on failure. |

### Transition rules

- `not_needed` → terminal. Only the supervisor can re-promote to `needed`, and only after explicit user approval.
- `needed` → `signed_off` (success path) or `failed` (failure path).
- `signed_off` → terminal under normal conditions. May be reset to `needed` only if a downstream agent (e.g. `pr-reviewer`) explicitly hands work back via a `(status: handoff)` or `(status: blocker)` comment that names this agent.
- `failed` → `signed_off` after rework, or `needed` if the supervisor decides to retry from scratch.

A ticket is `done`-eligible iff every entry in frontmatter `agents:` is in `{not_needed, signed_off}`.

---

## §1.5 Pre-flight: Task Section Check (mandatory before atomic sign-off)

### Three-Place Parity Rule (CRITICAL — read before proceeding)

The pre-commit guard `check_ticket_signoff_parity.py` validates **three locations simultaneously**. All three must be updated **in this exact order** before committing:

1. **Set `agents.<agent-name>: signed_off`** in frontmatter YAML.
2. **Check the `- [ ] <agent-name>` box** in the `## Sign-offs` section (add `— YYYY-MM-DD HH:MM` timestamp).
3. **Check ALL `- [ ]` task checkboxes** under `### <agent-name>` in the `## Implementation Tasks` section.

A common miss: updating frontmatter and Sign-offs but leaving implementation task checkboxes unchecked — this produces a parity-guard failure on commit that requires an additional edit cycle. Do all three steps before any commit, never fewer.

**Agents marked `not_needed` must NOT appear in `## Sign-offs` at all.** Remove any `- [ ] <agent-name>` row for a `not_needed` agent — orphan Sign-offs entries are also rejected by the parity guard.

---

Before performing the atomic YAML frontmatter update (§2):

1. Locate your `### <your-agent-name>` section under `## Implementation Tasks`
   (if no such section exists, skip to step 4 — you have no tasks).
2. For each task in your section:
   - If the task is complete, change `- [ ]` to `- [x]`.
   - If the task is incomplete because the work is genuinely BLOCKED (dependency
     not met, external gate, prerequisite missing): DO NOT sign off. Instead,
     emit `(status: blocker)` to the supervisor with an explanation. The
     supervisor's failure-adjudication ladder decides escalation.
   - If the task is incomplete and out of scope (not this agent's responsibility),
     add a Comment entry explaining why before proceeding.
3. If using `(status: handoff)`: tasks in OTHER agents' sections (e.g.
   `### test-writer`) may remain unchecked — those are the next agent's tasks.
   The pre-flight only checks YOUR OWN section.
4. Verify that all Acceptance Criteria have been addressed.
5. Only after steps 1–4 may you proceed to the atomic sign-off.

Violation: if you sign off with `- [ ]` tasks remaining in YOUR section,
the pre-commit parity guard (check_ticket_signoff_parity.py) will block
the commit with an error. Fix all tasks first or emit `(status: blocker)`.

---

## §2 Atomic Sign-off Recipe (success path)

When you (the agent) have completed your phase successfully, perform a single `Edit` per surface that updates BOTH the frontmatter `agents:` line and the `## Sign-offs` checklist line. The two surfaces must move together — partial-write states are rejected by the parity guard.

### Inputs

- `ticket_path`: absolute path passed to you by the supervisor.
- `agent_name`: your own name as it appears in the ticket's `agents:` map.
- `now_local`: current timestamp formatted exactly as `YYYY-MM-DD HH:MM` (24-hour, minute resolution, no seconds, no timezone suffix).

### Steps

1. **Read** the ticket file.

   > **STOP — §1.5 first.** If you have a `### <your-agent-name>` section under
   > `## Implementation Tasks`, complete §1.5 task-section check **before** any
   > edit below. The atomic sign-off in this section is the second half of a
   > two-part operation; doing step 2 below without first flipping your `- [ ]`
   > task checkboxes to `- [x]` triggers the `check_ticket_signoff_parity.py`
   > pre-commit guard and blocks the commit phase for the entire epic. The
   > parity guard catches it, but only after work has been done — and the fix
   > requires editing the ticket file again, which the readme-read-guard and
   > frontmatter-guard hooks may re-block. Avoid the entire chain: do §1.5
   > now, before step 2 here.

2. **Edit the frontmatter line.** Find:
   ```
     <agent_name>: needed
   ```
   Replace with:
   ```
     <agent_name>: signed_off
   ```
   Use enough surrounding context in `old_string` (e.g. the line above and below) to make the match unique within the YAML block.
3. **Edit the `## Sign-offs` line.** Find:
   ```
   - [ ] <agent_name>
   ```
   Replace with:
   ```
   - [x] <agent_name> — <now_local>
   ```
   The em-dash separator is `—` (U+2014), not `-`. **The timestamp suffix is mandatory** — writing `- [x] <agent_name>` without ` — YYYY-MM-DD HH:MM` triggers `check_ticket_signoff_parity.py` at commit time and blocks the close-out. This applies to batched close-out commits too: when a supervisor flips multiple checkboxes in one Edit (e.g. `commit` and `pull-request` together), every flipped line must carry its own timestamp.
4. **Call `submit_feedback.py` and capture the feedback_id** following §2a. Do this BEFORE appending the comment.
5. **Append a `## Comments` entry** following §3. Include the `feedback-id:` line as the first line of the comment body.
6. **Self-verify** (required). Re-Read the ticket file. Confirm all three of the following are true:
   - frontmatter `agents:` row shows `<agent_name>: signed_off`
   - `## Sign-offs` line reads `- [x] <agent_name> — YYYY-MM-DD HH:MM`
   - `## Comments` section contains a heading matching the timestamp you just wrote

   If **any** check fails (row still shows `needed`, timestamp absent, etc.), the
   write was silently lost. Do NOT return `ok`. Instead return:
   ```
   {status: "failed", payload: {blocker_summary: "signoff-write-lost"}}
   ```
   and follow the §4 failed-path recipe so the supervisor can halt and report
   the named phase agent to the user.

---

## §2a Submit-Feedback Script Call (mandatory before comment append)

Before appending the `## Comments` entry, every phase agent MUST call
`submit_feedback.py` to emit one structured entry to `feedback.jsonl` and
capture the returned `feedback_id`.

### Steps

1. **Choose `--category`**: select the category that best fits the signoff outcome:
   - `complete` — phase done cleanly with no issues.
   - `knowledge-gap` — you had to look things up or make assumptions mid-task.
   - `quality-concern` — you observed a quality issue in upstream work (reviewer-class only).
   - `tooling-issue` — a hook/script/harness blocked or hindered work.
   - `convention-ambiguity` — a project rule was unclear or contradictory.
   - `blocker` — work cannot proceed (use alongside a `blocker` status comment).
   - `success-pattern` — an approach worked unusually well, worth codifying.

2. **Choose `--tags`** (optional): 1–3 kebab-case tags describing the specific instance.
   Run `list_tags.py --category <your-category> --top 5` to see current common tags.

3. **Shell out**:
   ```bash
   python scripts/feedback/submit_feedback.py \
     --ticket <ticket_path> \
     --phase <agent_name> \
     --category <category> \
     --tags <tags_or_omit_flag> \
     --note "<one-sentence note>"
   ```

4. **Capture stdout → `feedback_id`**. If the script exits non-zero, log the error
   to stderr and use `feedback-id: (submit-failed)` as the fallback value in the
   comment body. **Do NOT abort signoff** — a failed feedback submission is not a
   phase failure.

5. **Use the `feedback_id`** as the first line of the comment body in §3.

### Single-Edit-per-surface constraint

Each of steps 2 and 3 is one `Edit` call. They cannot be combined into a single `Edit` because the frontmatter and the `## Sign-offs` section are separated by intermediate content. **Both must succeed.** If step 3 fails after step 2 succeeded, you MUST revert step 2 (a third `Edit` reversing the frontmatter change) before returning, otherwise the parity guard will reject the next commit.

---

## §3 Comment-Append Recipe

Every phase agent appends one `## Comments` entry per invocation. The heading is parser-strict; the supervisor reads only the heading to decide its next move.

### Heading schema (exact)

```
### YYYY-MM-DD HH:MM — <agent-name> (status: ok|blocker|question|handoff)
```

- Three hashes (`###`).
- Exactly one space after the hashes.
- Timestamp in the §2 format.
- Em-dash `—` separator (U+2014), surrounded by single spaces.
- Agent name in lowercase-with-hyphens, matching the `agents:` map key.
- Status tag in parentheses, one of the four values listed below.

### Status tags

| Tag | When to use | Effect on supervisor |
|---|---|---|
| `ok` | Phase completed, no concerns. | Spawns the next `needed` agent in natural order. |
| `handoff` | Phase completed and explicitly hands to a named sibling (the prose body MUST name the receiving agent). | Spawns the named agent next, regardless of natural ordering. |
| `blocker` | Phase could not complete; another agent must fix something first. | Triggers failure adjudication: respawn sibling, ask user, or escalate to brainstorm-lead. |
| `question` | Phase needs user clarification. | Halts the ticket; surfaces the question to the user. |

### Body

The comment body begins with the `feedback-id:` line (from §2a), followed by
1–5 sentences of prose:

```
feedback-id: fb_2026-05-14_a3f2c891
```

- For `ok`: a one-liner summarising what changed and any test status.
- For `handoff`: the named recipient and a one-sentence reason.
- For `blocker`: what was attempted, why it failed, and a specific suggested remediation (which agent to respawn, or what user input is needed).
- For `question`: the precise ambiguity and the options the user should choose between.

**Backward compatibility**: tickets authored before EPIC-FeedbackCollection do not
have `feedback-id:` lines. The parity guard and retrospective-agent accept their
absence gracefully. This requirement applies only to signoffs after the feedback
system epoch (when `submit_feedback.py` is present in the worktree).

### Edit pattern

The `## Comments` section is append-only. To append, use `Edit` with:
- `old_string`: the last existing heading + body in the section, OR the section heading itself if no entries exist.
- `new_string`: the same text PLUS your new entry separated by one blank line.

If no `## Comments` section exists yet (legacy ticket), append both the section heading and your entry by anchoring `old_string` on the file's last line.

---

## §4 Failed Path

Use this path when you cannot pass your phase's acceptance criteria after exhausting your own retries (e.g. `commit` after the precommit-autofix loop fails twice; `pr-reviewer` after finding a high-confidence blocker; coder after tests stay red on rewrite).

### Steps

1. **Update frontmatter.** Find `<agent_name>: needed` and replace with `<agent_name>: failed`.
2. **Update `## Sign-offs`.** Find `- [ ] <agent_name>` and replace with `- [ ] <agent_name> — failed <now_local>` (checkbox stays unchecked; `failed` keyword + timestamp signals the state to humans).
3. **Append a `## Comments` entry** with status `blocker` per §3, including:
   - What you tried (1 sentence).
   - Why it failed (1–2 sentences).
   - Suggested remediation: which agent to respawn, or what user input is needed (1 sentence).
4. **Return a structured payload** to your caller (the supervisor):
   ```
   {
     "status": "failed",
     "ticket_path": "<absolute path>",
     "agent": "<agent_name>",
     "blocker_summary": "<one sentence>",
     "suggested_remediation": "respawn <sibling-name> | ask user | escalate to brainstorm-lead"
   }
   ```

The supervisor reads the latest comment heading and the structured payload to decide what to do next.

---

## §5 Validator Rules

A ticket is **valid** iff all of the following hold. The pre-commit guard `scripts/commit_guardian/check_ticket_signoff_parity.py` (ticket 04) enforces these mechanically.

1. **Enum membership.** Every entry in frontmatter `agents:` has a status in `{not_needed, needed, signed_off, failed}`.
2. **Frontmatter ↔ Sign-offs parity.** Every entry in frontmatter `agents:` whose status is NOT `not_needed` appears in `## Sign-offs` with the matching surface representation:
   - `needed` → `- [ ] <name>` (no timestamp, no `failed` keyword).
   - `signed_off` → `- [x] <name> — YYYY-MM-DD HH:MM`.
   - `failed` → `- [ ] <name> — failed YYYY-MM-DD HH:MM`.
   Agents marked `not_needed` do NOT appear in `## Sign-offs`.
3. **No orphan checklist entries.** Every line in `## Sign-offs` corresponds to an entry in frontmatter `agents:`.
4. **Comment heading validity.** Every `## Comments` heading matches the regex:
   ```
   ^### \d{4}-\d{2}-\d{2} \d{2}:\d{2} — [a-z][a-z0-9-]* \(status: (ok|blocker|question|handoff)\)$
   ```
5. **Done-folder invariant.** Tickets located under any `done/` folder must have NO entries with status `needed` or `failed`.

---

## §6 Examples

### §6.1 Clean sign-off (ok path)

**Before** (excerpt):
```yaml
agents:
  research-agent: signed_off
  python-coder: needed
  test-runner: needed
```
```markdown
## Comments
### 2026-05-08 14:30 — research-agent (status: ok)
Provided context bundle on candle_horizon dependencies. No blockers found.
```

**After** (`python-coder` has just finished cleanly):
```yaml
agents:
  research-agent: signed_off
  python-coder: signed_off
  test-runner: needed
```
```markdown
## Comments
### 2026-05-08 14:30 — research-agent (status: ok)
feedback-id: fb_2026-05-08_aa112233
Provided context bundle on candle_horizon dependencies. No blockers found.

### 2026-05-08 15:12 — python-coder (status: ok)
feedback-id: fb_2026-05-08_bb445566
Implemented procedure_populate_features per spec §4. Inner-loop tests via test-runner all green.
```

### §6.2 Failed path with blocker

**After** (`pr-reviewer` finds a regression):
```yaml
agents:
  python-coder: signed_off
  pr-reviewer: failed
```
```markdown
## Comments
### 2026-05-08 15:12 — python-coder (status: ok)
Implemented procedure_populate_features per spec §4. Tests green.

### 2026-05-08 15:25 — pr-reviewer (status: blocker)
procedure_populate_features.sql:142 uses `WHERE last_evaluated > NOW()` but the fix in commit e41ff33 requires `>= NOW() - INTERVAL '1 year'`. This is a regression. Recommend respawning sql-coder with this finding as input.
```

### §6.3 Handoff to named sibling

**After** (`architect-review` defers detail to coder):
```yaml
agents:
  architect-review: signed_off
  python-coder: needed
```
```markdown
## Comments
### 2026-05-08 14:45 — architect-review (status: handoff)
Approach approved at the architecture level (extract a writer interface; thin adapter for live vs historic). Handing to python-coder for implementation; no further architectural review needed unless the writer interface needs more than 2 implementations.
```

---

## §7 Knowledge Capture Step

### §7 Knowledge Capture Step (mandatory, runs before sign-off is declared complete)

After the atomic sign-off write (§2) succeeds, invoke the knowledge-capture prompt:

> "Did you discover anything during this ticket that future-you would have benefited from knowing at the start? (no / yes)"

**No path**: proceed — sign-off is complete.

**Yes path**:
1. Ask: "Describe the learning in one to three sentences."
2. Load `.claude/skills/route-learning/SKILL.md` and apply the decision tree to classify the learning.
3. Load `.claude/skills/capture-learning/SKILL.md` and execute the write.
4. Emit a `knowledge_captured` telemetry event to `agent_telemetry.jsonl`:
   ```json
   {"event": "knowledge_captured", "timestamp": "<ISO>", "ticket": "<ticket_path>", "destination": "<routed_file>", "entry_kind": "<entry_kind>"}
   ```

This step is **mandatory** — skipping it is a protocol violation. If `route-learning` or `capture-learning` are unavailable, log a warning and proceed (do not block sign-off).

---

## §8 Anti-Patterns

- **Don't** sign off without appending a comment. The comment is the audit trail.
- **Don't** use timestamps with seconds (`HH:MM:SS`) or timezone suffixes — minute-resolution local time is the convention, full stop.
- **Don't** mark yourself `signed_off` if any of your work failed. Use `failed` and let the supervisor adjudicate.
- **Don't** invent new status values or comment status tags. Adding new ones is an edit to this skill, never an ad-hoc choice in an agent prompt.
- **Don't** edit other agents' lines in `agents:` or `## Sign-offs`. You only ever modify your own row.
- **Don't** combine your sign-off Edit with substantive content edits in a way that obscures the audit trail. Sign off in its own dedicated Edit pair after your work is complete.
- **Don't** skip the `submit_feedback.py` call (§2a). If the script fails, use `feedback-id: (submit-failed)` and proceed — do not abort signoff. An empty feedback entry is not a valid substitute for calling the script.
