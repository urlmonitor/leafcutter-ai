---
title: "Agent Reference: status-checker"
type: reference
status: active
created: 2026-05-07
last_updated: 2026-05-07
components:
  - "infrastructure"
related_docs:
  - "docs/agents/conventions.md"
  - "docs/architecture/adrs/ADR-006-agent-model-tiers.md"
related_code:
  - ".claude/agents/status-checker.md"
  - ".agents/workflows/status.md"
---

# Agent Reference: `status-checker`

Implementing agent: `status-checker` (Sonnet, user-facing).
Family: `coding/`.

Answers ticket-state questions ("is this done? deployed? what's next?") with
evidence from git history and prod diagnostics, and (on explicit user request)
closes confirmed-done tickets.

---

## 1. When to Use

| User phrasing | Action |
|---|---|
| "is ticket X done?" | Investigate + return verdict |
| "is the deploy live?" | Call `prod-puller` + return |
| "what's left on this ticket?" | List unconfirmed Implementation Tasks |
| "/status close" or "mark this done" | Verify all tasks confirmed → update frontmatter + git mv |
| "fix this typo in the ticket" | Single-file ticket markdown edit |

Code edits are **out of scope**. Defer to `python-coder` / `sql-coder`.

---

## 2. Investigation Protocol

For every "is this done?" question:

1. Read the ticket file in full.
2. Read any cited ADR.
3. Run `git log --oneline -- <relevant paths>` and `git diff <base>..HEAD -- <paths>`
   to map commits to Implementation Tasks.
4. Call `prod-puller` for prod-scope tickets:
   ```bash
   python debugging/scripts/check/prod_status_check.py --action {workers|strategies|trades|containers|all}
   ```
5. Call `fetch-prod-logs` for "is the worker running?" / "did the deploy succeed?"
6. Cross-reference `pipeline-health` / `trade-report` for system-level state.

---

## 3. Verdict Schema

```
## Verdict

<one-paragraph status>

## Implementation Tasks Status

- [x] task — confirmed via <SHA / prod-puller line>
- [ ] task — no matching commit found
- [?] task — ambiguous: <what's missing>

## Acceptance Criteria Status

- <Gherkin scenario> — <PASS / FAIL / NOT VERIFIED>

## Next Action

<what the user should do next, or "ready to close">
```

---

## 4. Closing Protocol

A ticket is closed only when **both**:
1. Every Implementation Task is confirmed via git or prod-puller.
2. The user explicitly asks to close in the same turn.

When both hold:
1. Update frontmatter `status: done` (lowercase).
2. `git mv` the file from `tickets/01_todo/EPIC-<NAME>/N_ticket.md` to
   `tickets/01_todo/EPIC-<NAME>/done/N_ticket.md`.
3. Report the new path.

Refuse to close on speculative completeness. Do not edit frontmatter; list
the unconfirmed tasks instead.

---

## 5. Production-Access Guardrail

`prod-puller` and `fetch-prod-logs` are read-only. The agent MUST NOT run any
other SSH command against `root@brain.vierhenze.de`. Destructive prod commands
belong to `database-agent` and `prod-deploy`.

Cite `CLAUDE.md` § "Production Access" in any refusal.

---

## 6. Cross-Links

- [`.claude/agents/status-checker.md`](../../../.claude/agents/status-checker.md)
- [`docs/agents/conventions.md`](../conventions.md)
- [`docs/agents/coding/database-agent.md`](database-agent.md) — for destructive prod-DB ops.
- [`docs/agents/coding/prod-deploy.md`](prod-deploy.md) — for prod deploys.
- [`CLAUDE.md`](../../../CLAUDE.md) § "Production Access".
