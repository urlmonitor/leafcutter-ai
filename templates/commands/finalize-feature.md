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
