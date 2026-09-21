---
title: "KI-BO-20260914-autofix-re-dispatch-is-specified-at-a-depth-that-cannot-execute — the commit agent is told to spawn the originating coder, and ADR-019 says that call is silently dropped"
description: "high. Not because anything is corrupted, but because the failure is silent by construction and the mechanism is a *recovery* path — the place where nobody is watching. If it is dead, every judgment-tier hook failure since the skill shipped "
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-20260914-autofix-re-dispatch-is-specified-at-a-depth-that-cannot-execute — the commit agent is told to spawn the originating coder, and ADR-019 says that call is silently dropped

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high. Not because anything is corrupted, but because the failure is silent by construction and the mechanism is a *recovery* path — the place where nobody is watching. If it is dead, every judgment-tier hook failure since the skill shipped has fallen through to "the fix did not happen" with no error distinguishing that from "the fixer tried and failed". It also makes a baseline BO-3800e-1 depends on a bug-shaped baseline.
- **Status:** open — **unconfirmed at runtime.** Everything below is read from source and from ADR-019; no run was instrumented. Confirming or refuting it by measurement is step one, and it is cheap.
- **Occurrences:** 0 observed. Found by inspection on 2026-09-14 during IT PO enrichment of BO-3800.
- **First seen:** 2026-09-14 · **Last seen:** 2026-09-14
- **Where:** `templates/skills/precommit-autofix/SKILL.md` Step 4a.3 (the `Agent` tool dispatch, around line 100) and its re-dispatch prompt constraint 4 (lines 136–140). Specified by `BO-210c`.

**The contradiction, in the skill's own words.** Step 4a.3 instructs the commit agent to call the `Agent` tool with `subagent_type` set to the originating coder. The prompt it hands that coder says:

```text
4. **Spawn NO sub-agents.** You are running at depth 2 in the dispatch chain
   (ticket-supervisor → commit → you). Claude Code's hard depth-1 Agent-tool
   nesting limit means any `Agent` tool call you make will be silently dropped.
```

The chain it names is right. The conclusion it draws from it is one level off. `ADR-019` records that *"an agent running at depth 1 cannot itself invoke the Agent tool. Any call beyond depth 1 is silently dropped — no error is raised, the tool call simply does not execute."* Under `ADR-006`'s flattened chain `ticket-supervisor` is depth 0 and the commit agent is depth 1 — so **the Step 4a.3 dispatch is itself the dropped call.** The document warns the depth-2 fixer not to spawn a depth-3, while presupposing a depth-2 agent that by its own stated rule cannot exist.

**Why it is plausible this has never been noticed.** `BO-210c` is `readiness: approved`, `req_status: active`, `work_status: todo`, `implemented_by: []` — the behaviour was never claimed done, so no test asserts it and no sign-off ever depended on it. But the skill is *deployed*, so the instruction is live in the commit agent's prompt on every judgment-tier failure. A capability that was never built and a capability that runs and silently no-ops look identical from outside, and this one is both at once.

**This is the exact incident ADR-019 was written about, one component over.** There, `/build-feature` dispatched `ticket-supervisor` at depth 1, its phase-agent calls sat at depth 2 and were dropped, and no phase template ever applied on any run — each ticket appeared to progress while nothing happened on disk. The shape recurred here because the depth arithmetic is done in prose inside a prompt, where nothing checks it.

**How to confirm, before fixing anything.** Drive a ticket to a judgment-tier hook failure with `check-file-size` or `check-complexity` and record what the driver actually dispatches. Do not infer it from `SKILL.md`; the whole point is that the text and the behaviour may disagree.

**Fix direction (only after confirming).** The re-dispatch has to be issued by a party that can issue it — the depth-0 driver — with the commit agent *returning* a structured "this hook failed, this agent should fix it" rather than trying to spawn the fixer itself. That is the same correction `ADR-019` applied to phase dispatch. Do not fix it by deleting constraint 4 from the prompt; the constraint is correct, it is the dispatch above it that is misplaced. Worth a mechanical guard too: nothing today checks a template's claimed depth against the dispatch chain that reaches it, so this class is invisible to every gate in the repo.

**Related.**
- `docs/architecture/adrs/ADR-019-build-feature-inline-phase-dispatch.md` — the cap, and the first time it bit.
- `docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md` — why `ticket-supervisor` is depth 0, which is what puts the commit agent at depth 1.
- `BO-3800b-2` — carries this as an escalation; its Given assumes the driver can observe the originating coder being engaged, which is exactly what is in doubt.
- `BO-3800e-1` — promises today's behaviour is preserved. If today's behaviour is "nobody is engaged", that promise is measuring a defect.

**Pattern:** depth arithmetic done in prose inside a prompt, where no gate can check it, producing a recovery path that fails by doing nothing.
