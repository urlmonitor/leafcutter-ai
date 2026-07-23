---
description: |
  Post-merge feature finalization: capture pre-merge test baseline on main,
  open PR if missing, merge origin/main into worktree, run post-merge tests
  (with triage baseline), merge PR to main only when tests pass, sync local
  main, close tickets/archive epic, remove worktree. Prompt gates on all
  destructive steps. HALT on test regression before PR merge.
---

**This command requires the Workflow tool. If the Workflow tool is not available
in your environment, this command will not work — do not attempt to run it
manually as an LLM conversation.**

Invoke the `finalize-feature` workflow script via the Workflow tool:

```
Workflow("finalize-feature", $ARGUMENTS)
```

Pass the epic or ticket name as a plain string (e.g. `"EPIC-FooBar"` or
`"fix/my-branch"`). Do NOT wrap it in an object — the script checks
`typeof args === 'string'` and the object form silently falls through to
CWD-based detection, which is usually wrong when invoked from a different
working directory.

## Progress Relay Protocol (launcher responsibility)

After the `finalize-feature` background run is started, the launcher (the main
conversation loop that invoked this command) MUST poll the run-progress journal and
relay new progress lines into the main conversation while the run is in flight. A
background workflow cannot inject messages into the main conversation directly — the
relay is the launcher's responsibility.

### Locating the journal

The run-progress journal is the durable append-only record created by the
`finalize-feature` workflow per AC `BO-1000c-1a`. It lives at the path the workflow
emits at launch time (keyed by worktree root and run ID). Use that exact path. Do NOT
invent a second path or a parallel log location — one journal per run, located as the
workflow reports it.

### Polling loop

1. **Begin polling immediately** after the background run is launched. Do not wait for
   user instruction — the relay is automatic.
2. **Interval**: poll once every 5–10 seconds (bounded interval). A fixed pause between
   reads avoids hammering the filesystem while keeping latency low.
3. **Incremental relay**: track the last line position relayed. On each poll, emit only
   lines added since the previous read (new lines only, no duplicates).
4. **Emission order**: relay each new batch of lines in the order they appear in the
   journal. Separate successive relay batches with a blank line so the user can
   distinguish updates.
5. **Stop when the run terminates**: stop polling when the workflow exits — either with
   a success payload or a halt/error payload. After the run ends, present the end-of-run
   recap (the workflow's final summary or the last journal lines, whichever is richer)
   in the main conversation.

### Graceful degradation

If the journal file is absent or unreadable at any polling interval:

- Do NOT error the launch.
- Emit one informational note into the main conversation:
  > "Live progress unavailable (journal not yet readable). The run is still in
  > flight — final results will be reported when the workflow completes."
- Continue polling (the journal may appear after the workflow's brief startup delay).
- If the journal remains absent after 3 consecutive polls, stop active polling and
  await the workflow's exit payload rather than continuing to poll an absent file.

### Halt-Flush Protocol

When the polling loop detects that the background run has terminated with a halt
or error payload, the launcher MUST perform the following steps in this exact
order before presenting the halt summary (AC `BO-1000c-2-i`):

1. **Perform a final journal read immediately on halt detection.** Before surfacing
   the halt payload to the user, read the journal from the last-relayed position to
   the end of the file. Do this immediately when the workflow exit is detected —
   do not skip this read even if the previous poll was recent.
2. **Relay all remaining lines first.** Emit every unrelayed journal line
   (including the halting step's start-of-step line, which BO-1000a-1-i guarantees
   was written before the step failed) into the main conversation, in order.
3. **Present the halt summary only after the flush completes.** After the final
   flush is emitted to the conversation, present the halt payload (halt reason,
   halting step, status). The user MUST see the halting step's start-of-step
   progress line as the most recent conversation line before the halt summary
   arrives.

**Why a final flush is mandatory:** BO-1000a-1-i guarantees that the halting step
emits its start-of-step journal line before the step fails. BO-1000c-1a guarantees
that line reaches the journal. However, without a final flush on halt detection,
the halting step's line may still be in the unread journal tail when the relay loop
exits — the user would then see the halt payload without ever seeing the step that
caused it in the conversation. The halt-flush closes that gap: the live conversation
stream reflects the halting step, not only the returned halt payload.

**Anti-pattern to avoid:** Do NOT present the halt summary first and then relay
remaining journal lines as trailing output. The halt-flush must precede the halt
summary so the final progress line the user reads before the halt result is the
halting step's own line.

### Over-Time Delivery Guarantee

This section asserts the combined delivery contract of the incremental journal
(BO-1000c-1a) and the poll/relay loop (BO-1000c-1b). The launcher MUST uphold
all four invariants:

1. **In-flight delivery** — a progress line for a step MUST appear in the
   conversation while the run is still in flight, before the run has finished,
   reflecting the step currently underway. Deferring all relay until after the
   workflow exits violates this guarantee.

2. **Multiple distinct updates** — at least one progress update MUST arrive in
   the conversation per executed or skipped step that emits a journal line, spread
   across the run's execution. Delivering all lines in a single batch only after
   run completion violates this guarantee.

3. **No re-delivery** — lines already relayed MUST NOT be re-emitted on
   subsequent polls. The launcher tracks the last-relayed file position and
   advances it on every successful relay batch (duplicates defeat the dedup
   requirement and produce confusing output).

4. **Halt-flush invariant** — when the run terminates with a halt, ALL remaining
   unrelayed journal lines MUST be emitted into the conversation BEFORE the halt
   payload is presented. The halting step's start-of-step line MUST appear as the
   last relayed progress line visible in the conversation before the halt summary.
   The user MUST learn which step halted from the relayed journal, not only from
   the halt payload. This invariant is the observable contract for AC `BO-1000c-2-i`
   and depends on the Halt-Flush Protocol above being executed on every run
   termination that carries a halt payload.

These invariants define the observable contract for AC `BO-1000c-2` and its
sub-criterion `BO-1000c-2-i`. They depend on BO-1000c-1a writing the journal
incrementally (append-as-you-go) and BO-1000c-1b's poll/relay loop running while
the workflow is active. Do NOT attempt to satisfy them by buffering all journal
output and emitting it after the run ends — that is the anti-pattern this AC
exists to prohibit.

### User experience goal

The user receives finalize-feature progress directly in the main conversation, without
opening the live-workflows view. The live-workflows view remains available as a fallback
but is not the primary delivery path for in-flight progress. When the workflow completes,
the launcher presents the final status (success or halt reason) in the main conversation,
closing the relay loop.

If the Workflow tool is unavailable or the script returns an error, stop
immediately and report the failure. Do NOT improvise an LLM-mediated
alternative. The correct response to a missing Workflow tool is:

> ERROR: /finalize-feature requires the Workflow tool (Claude Code ≥ 2.1.154).
> The Workflow tool is not available in this environment.
> This command cannot proceed. Check your Claude Code version and environment.
