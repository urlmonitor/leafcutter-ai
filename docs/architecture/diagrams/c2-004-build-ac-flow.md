---
title: "/build-ac Execution Flow — Sequence Diagram"
type: architecture
status: active
created: 2026-06-05
last_updated: 2026-06-05
flight_level: L2
parent: agent_delivery_workflows.md
components:
  - ac_store
  - build_orchestration
related_docs:
  - docs/architecture/diagrams/ac-authoring-pipeline.md
  - docs/architecture/diagrams/ac-readiness-states.md
  - docs/architecture/diagrams/ac-driven-pipeline.md
  - docs/how-to/ac-driven-development.md
---

# /build-ac Execution Flow — Sequence Diagram

This diagram shows the end-to-end execution path when a developer invokes
`/build-ac`. The flow covers the ranking step, ticket generation, the
`yes / review / skip` confirmation branches, the build step, and the
done-link loop that closes the AC after the ticket merges.

---

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant BAC as build-ac
    participant PRI as ac_prioritizer.py
    participant GEN as generate_ticket_from_ac.py
    participant BF as build-feature
    participant DONE as mark_ac_done.py

    User->>BAC: /build-ac [--ac <id>]

    alt --ac flag provided
        Note over BAC: Skip ranking; use the named AC directly
    else No flag
        BAC->>PRI: --json
        PRI-->>BAC: Top-ranked approved AC (id, title, priority)
    end

    BAC-->>User: "Next AC: <id> — <title>\nBuild this ticket now? (yes / review / skip)"

    alt User answers yes
        BAC->>GEN: --ac <id>
        GEN-->>BAC: ticket_path
        BAC->>BF: /build-feature <ticket_path>
        BF-->>BAC: Build complete
        BAC->>DONE: --ticket <ticket_path>
        DONE-->>BAC: AC work_status → done
        BAC-->>User: "Done — AC <id> marked done."

    else User answers review
        BAC-->>User: Opens ticket file for inspection
        Note over User: User reads the generated ticket
        User->>BAC: yes / skip (re-confirmation)
        Note over BAC: Re-enters yes or skip branch

    else User answers skip
        Note over BAC: Sets AC work_status → deferred
        BAC->>PRI: --json (next candidate)
        PRI-->>BAC: Next-ranked approved AC
        BAC-->>User: "Next AC: <id> — <title>\nBuild this ticket now? (yes / review / skip)"
        Note over BAC: Loop repeats until yes or no more ACs
    end

    alt No approved ACs exist
        PRI-->>BAC: Empty ready list
        BAC-->>User: "AC store is empty — no unblocked todo ACs found."
    end
```

---

## Branch Summary

| User answer | Effect |
|---|---|
| `yes` | Generates ticket, dispatches `/build-feature`, marks AC done on merge. |
| `review` | Opens the generated ticket file; re-prompts with yes / skip after inspection. |
| `skip` | Sets `work_status: deferred` on the current AC; loops to the next candidate. |
| *(no ACs)* | Prints "AC store is empty" and exits cleanly. |

---

## Notes on the Done-Link Loop

`mark_ac_done.py` is called with `--ticket <ticket_path>` after
`/build-feature` returns. It reads the ticket's `source_ac` field,
locates the AC YAML, and sets `work_status: done`. This closes the
traceability loop from AC definition through to merged implementation.

If the `--ac` flag was used to bypass ranking, the same done-link step
runs — the agent always marks the targeted AC done after a successful build.

---

## Cross-References

- [AC authoring pipeline](ac-authoring-pipeline.md) — how ACs reach
  `readiness: approved` before this flow can start.
- [AC readiness state machine](ac-readiness-states.md) — all five states
  and the transitions that this flow exercises.
- [AC-driven pipeline component diagram](ac-driven-pipeline.md) — all
  scripts and data flows end-to-end.
- [How to use the AC-driven development system](../../how-to/ac-driven-development.md) — task-oriented guide.
