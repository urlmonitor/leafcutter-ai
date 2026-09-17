---
title: "KI-CG-20260917-claude-code-hooks-reference-contradicts-exit-codes — the Claude Code hooks reference lists a stale stdin contract and says a non-zero exit never blocks, contradicting itself and the shipped guards"
description: "KI-CG-20260917-claude-code-hooks-reference-contradicts-exit-codes — the Claude Code hooks reference lists a stale stdin contract and says a non-zero exit never blocks, contradicting itself and the shipped guards"
type: reference
category: reference
status: active
created: '2026-09-17'
last_updated: '2026-09-17'
components:
  - commit_guardian
  - documentation_system
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260917-claude-code-hooks-reference-contradicts-exit-codes — the Claude Code hooks reference lists a stale stdin contract and says a non-zero exit never blocks, contradicting itself and the shipped guards

> Index: [commit-guardian.md](../commit-guardian.md). Filename severity is the three-level
> index bucket (`low`); the original grading is the `**Severity:**` line below.

- **Severity:** medium. The doc is wrong on the one fact a hook author needs most, but no
  gate reads it. The damage happens when someone writes a hook from it.
- **Status:** open — owning ACs `GE-129e` for (a) (the reference for the safeguards must say
  how the committer is recognised); `GE-130a` / `GE-130f` for (b) (`GE-130f` lists this doc
  in `doc_links`: "must agree with the repaired guards")
- **Occurrences:** 1 (read against the official reference, 2026-09-17)
- **First seen:** 2026-09-17 · **Last seen:** 2026-09-17
- **Where:** `docs/reference/claude-code-hooks.md` (`last_updated: 2026-06-18`) — stdin
  contract `:47-68`; PreToolUse stdout table and note `:140-153`; Exit Code Semantics
  `:169-178`; Bypass / Escape Hatches `:297-306`

**Source of truth used.** Claude Code's hooks reference, `code.claude.com/docs/en/hooks`,
fetched 2026-09-17.

**(a) The stdin contract is stale.** The doc's PreToolUse payload has three fields:
`tool_name`, `tool_input`, `session_id`. The official reference lists common input fields
`session_id`, `prompt_id`, `transcript_path`, `cwd`, `scratchpad_dir`, `permission_mode`,
`effort`, `hook_event_name`, plus `tool_use_id` on the PreToolUse example. It also lists two
subagent fields, present only when running with `--agent` or inside a subagent: `agent_id`
("use to distinguish subagent calls from main-thread calls") and `agent_type` (the agent's
name). Missing those two matters most. `GE-129` ("who acts, not what typed") needs caller
identity, and a reader of this doc would conclude, as
`KI-CG-20260907-commit-delegation-is-a-password-not-an-identity` wondered, that a hook
cannot see provenance.

**(b) The exit-code semantics contradict themselves.**

| Where in the doc | What it says |
|---|---|
| `:144` stdout table | non-zero exit "by convention, treated as allow" |
| `:151-153` note | "A non-zero exit code is NOT used to signal a block — it is treated as a fail-open allow" |
| `:173` Exit Code Semantics | PreToolUse non-zero: "Allow (fail-open — never blocks, even on error)" |
| `:306` escape-hatch table | `inline_work_guard` "Downgrades the guard from blocking (exit 2) to warn-only" |

The shipped guards follow `:306`, not `:173`: `inline_work_guard.py:180` and
`readme_read_guard.py:271` both block with `sys.exit(2)`. The official reference agrees with
them: exit 2 "Blocks the tool call (cannot be overridden)", and *"Exit code 1 treated as
non-blocking. Use exit 2 to enforce policy."* So the doc's general rule is wrong, and its own
table is the counter-example.

**Secondary, same section.** The doc presents `{"decision": "block", "reason": ...}` as the
PreToolUse block pattern. The official reference lists `decision`/`reason` as **deprecated
but still working**, replaced by `hookSpecificOutput.permissionDecision` /
`permissionDecisionReason`. Not a defect today, but the reference should not teach the
deprecated form as canonical.

**Why it matters.** An author following `:173` either blocks with JSON (works) or assumes
exit codes cannot block and never uses exit 2. The reverse mistake is live:
`documentation_guard` blocks with exit 1, which the doc's own table calls an allow, and the
doc still describes that hook as blocking (`:40`, `:305`). See `KI-CG-037`.

**Fix direction.**

- Rewrite the stdin contract from the official reference, including `agent_id`/`agent_type`
  and when they are absent. Link the upstream page and date the check.
- Replace the Exit Code Semantics table: 0 = no decision / JSON honoured; 2 = block, stderr
  is the reason; other non-zero = non-blocking error. Drop "never blocks".
- Show `hookSpecificOutput.permissionDecision` as the primary JSON form and mark
  `decision`/`reason` deprecated.
- Keep the fail-open advice, restated: an unexpected exception should exit 0, and a
  deliberate refusal should exit 2.

**Related.** `KI-CG-037`,
`KI-CG-20260907-commit-delegation-is-a-password-not-an-identity`.

---
