---
name: feedback-review
description: >
  Use when the user wants to triage unresolved feedback entries from
  feedback.jsonl. Presents each unresolved entry grouped by category and
  prompts the user to create a ticket, dismiss with a rationale, or skip.
  Calls resolve_feedback.py after each user decision. Exits with a summary
  of N resolved, M tickets created, K skipped.
  Trigger phrases: "review feedback", "/feedback-review", "triage feedback",
  "what unresolved feedback is there", "process feedback entries".
allowed-tools: Bash, Read, Agent
---

# Skill: feedback-review

This skill walks the user through every unresolved feedback entry in
`feedback.jsonl`, one category at a time, and lets them decide what to do
with each one.

> **Dependency:** Requires `TICKET-20260603-FeedbackResolutionTracking` to be
> shipped (provides `aggregate.py --unresolved` and `resolve_feedback.py`).

---

## Step 1 — Load Unresolved Entries

Run:

```bash
python scripts/feedback/aggregate.py --unresolved --format json
```

If the command exits non-zero, surface stderr verbatim and abort:

```
aggregate.py failed — check feedback.jsonl path and try again.
<stderr output>
```

If the command succeeds but returns zero entries (empty list or `"total": 0`):

```
No unresolved feedback entries — nothing to triage.
```

Then exit. Do not proceed to Step 2.

---

## Step 2 — Group by Category

Parse the JSON output. Group entries by the `category` field. Present one
category at a time, in this order (most actionable first):

1. `subagent-quality`
2. `hook-violation`
3. `process-finding`
4. `knowledge-gap`
5. `convention-ambiguity`
6. `tooling-issue`
7. `submit-failed`
8. Any other categories, alphabetical

Within each category, sort by `timestamp` ascending (oldest first).

---

## Step 3 — Triage Each Entry

For each entry, display:

```
--- [<category>] <feedback_id> ---
Timestamp : <timestamp>
Severity  : <severity>
Phase     : <phase>
Tags      : <tags joined by ", " or "(none)">
Note      : <note>
Source    : <source if present, else omit>

[c] Create ticket   [d] Dismiss   [s] Skip
```

Wait for the user's single-character input.

### When the user selects [c] — Create Ticket

1. Dispatch `/create-ticket`
   with the feedback `note`, `category`, `tags`, and `feedback_id` as the
   primary request context. Include the full entry JSON as supplementary context.
2. After the ticket is created, resolve the entry:
   ```bash
   python scripts/feedback/resolve_feedback.py \
     --feedback-id <feedback_id> \
     --ticket <new_ticket_path> \
     --note "Ticket created via /feedback-review"
   ```
3. If `resolve_feedback.py` exits non-zero, surface stderr and record the
   entry as "resolve-failed" in the session summary. Do NOT abort the loop.
4. Increment `tickets_created` counter.

### When the user selects [d] — Dismiss

1. Prompt the user:
   ```
   Dismiss reason (one line):
   ```
2. Wait for input. Do not accept an empty string — re-prompt once if blank.
3. Call:
   ```bash
   python scripts/feedback/resolve_feedback.py \
     --feedback-id <feedback_id> \
     --note "<user_reason>"
   ```
4. If `resolve_feedback.py` exits non-zero, surface stderr and record the
   entry as "resolve-failed" in the session summary. Do NOT abort the loop.
5. Increment `resolved_count` counter.

### When the user selects [s] — Skip

No `resolve_feedback.py` call. The entry remains unresolved for the next
triage session. Increment `skipped_count` counter.

### Invalid input

If the user types anything other than `c`, `d`, or `s`, print:
```
Invalid input. Enter c (create), d (dismiss), or s (skip):
```
and re-prompt once. If the second input is also invalid, treat as [s] (skip)
and continue.

---

## Step 4 — Summary

After all entries in all categories have been handled, print:

```
/feedback-review complete: <resolved_count> resolved, <tickets_created> tickets created, <skipped_count> skipped.
```

If any entries were marked "resolve-failed", append:
```
Warning: <N> resolve_feedback.py call(s) failed — those entries remain unresolved.
Re-run /feedback-review or call resolve_feedback.py manually to retry.
```

---

## Error Handling

| Error | Action |
|-------|--------|
| `aggregate.py` exits non-zero | Surface stderr, abort with "aggregate.py failed" message |
| `resolve_feedback.py` exits non-zero (Create Ticket path) | Surface stderr, mark "resolve-failed", continue loop |
| `resolve_feedback.py` exits non-zero (Dismiss path) | Surface stderr, mark "resolve-failed", continue loop |
| `/create-ticket` fails or returns no ticket path | Surface error, do NOT call `resolve_feedback.py`, increment `skipped_count` |
| `feedback.jsonl` does not exist | `aggregate.py` will surface this; abort as per the aggregate.py error case |

---

## Invocation Contexts

| Trigger | Notes |
|---------|-------|
| User types `/feedback-review` | Direct invocation — full triage session |
| `retrospective-agent` recommends it | User should invoke `/feedback-review` manually after reading the recommendation |

---

## Constraints

- Never auto-resolve entries without user input for each one.
- Never create tickets in bulk without user confirmation per entry.
- Never abort the loop on a single `resolve_feedback.py` failure — mark it and continue.
- The `aggregate.py --unresolved` flag is the source of truth for which entries need triage; do not re-implement the filter logic.
