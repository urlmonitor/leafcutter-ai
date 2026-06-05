---
name: build-ac
description: |
  Find and propose the next most important unimplemented AC in the store.
  Calls ac_prioritizer.py to rank ready ACs, generates a ticket from the
  top-ranked AC via generate_ticket_from_ac.py, and prompts the user with:
  "Build this ticket now? (yes / review / skip)".

  Flags:
    --ac <id>      Bypass the ranking step; propose the named AC directly.
    --dry-run      Print the proposed AC and ticket (without writing) and exit.

  DEPTH-CAP NOTE: This command does NOT call /build-feature inline. After
  generating the ticket, it hands off to the user to run /build-feature manually.
  See ADR-006-flatten-supervisor-chain.md.
---

Invoke the `build-ac` agent with the user's full argument string: $ARGUMENTS
