---
description: |
  RETIRED — /create-ticket is no longer the canonical ticket-creation path.
  Per ADR-012, the canonical path is /plan-feature followed by /build-ac.
  This command now routes you to those two commands.
---

**/create-ticket has been retired (ADR-012).**

The canonical ticket-creation path is now:

1. **`/plan-feature <your feature request>`** — runs the PO → BA → IT PO
   authoring pipeline to produce AC YAML files in `docs/acceptance-criteria/`.
   Gates at each stage so you can review and approve ACs before moving forward.

2. **`/build-ac`** — scans the AC store for the next ready leaf AC, generates
   a ticket file from it via `generate_ticket_from_ac.py` (respecting
   `depends_on` ordering and writing `implemented_by` back-links), and presents
   the proposed ticket for your approval. Then run **`/build-feature`** to drive
   the ticket to completion.

### Why the change?

`create-ticket.js` silently produced no ticket file when invoked with the v3
business-analyst agent (the agent now writes AC YAML files rather than the JSON
payload the old workflow expected). The AC-store model (ADR-010) inverts the
source of truth: tickets are derived artefacts generated from the AC store, not
primary inputs. ADR-012 formalises this by retiring `create-ticket.js` and
consolidating on the `/plan-feature + /build-ac` pipeline.

For full context see:
- `docs/architecture/adrs/ADR-012-retire-create-ticket-js.md`
- `docs/architecture/adrs/ADR-010-ac-store-as-authoritative-backlog.md`
