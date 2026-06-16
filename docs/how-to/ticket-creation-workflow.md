---
title: "How to create a ticket: /plan-feature + /build-ac"
type: how-to
category: how-to
status: active
created: 2026-06-16
last_updated: 2026-06-16
components:
  - ticket_creation_pipeline
  - ac-store
related_docs:
  - docs/architecture/adrs/ADR-012-retire-create-ticket-js.md
  - docs/architecture/adrs/ADR-010-ac-store-as-authoritative-backlog.md
  - docs/how-to/ac-driven-development.md
  - docs/how-to/build-ac-unified.md
---

# How to create a ticket: /plan-feature + /build-ac

The canonical ticket-creation path in leafcutter-ai is a two-phase sequence:

1. **`/plan-feature`** — describe your feature to the PO → BA → IT PO authoring
   pipeline; it produces AC YAML files in the store.
2. **`/build-ac`** — select the highest-priority approved AC; it generates a
   ticket file and you drive the ticket with `/build-feature`.

This guide covers four tasks:

1. [Running /plan-feature to author ACs](#1-running-plan-feature-to-author-acs)
2. [Approving ACs for building](#2-approving-acs-for-building)
3. [Running /build-ac to generate a ticket](#3-running-build-ac-to-generate-a-ticket)
4. [Migration: from /create-ticket to /plan-feature + /build-ac](#4-migration-from-create-ticket-to-plan-feature--build-ac)

**Prerequisites:**

- `build.py` has been run in your project (or `build-self.sh` in the package
  workspace).
- `scan_ac_store.py`, `ac_prioritizer.py`, and `generate_ticket_from_ac.py`
  are installed under `scripts/ac_store/`.
- The `/plan-feature` and `/build-ac` commands are registered in `.claude/`.

---

## 1. Running /plan-feature to author ACs

`/plan-feature` is the entry point for turning a feature description into
structured acceptance criteria. It runs a three-agent pipeline under the hood:
`product-owner` (L0/L1 customer-value ACs) → `business-analyst`
(L2/L3 behavioural ACs) → `it-po` (technical enrichment).

### Step 1: Invoke /plan-feature

```
/plan-feature
```

Describe the feature you want to build. Include:

- The observable behaviour you expect (what the user sees or experiences).
- The error cases or edge conditions you care about.
- Any priority guidance (critical / high / medium / low).

You do not need to know how the feature will be implemented — that is the IT
PO's job.

### Step 2: Answer the authoring pipeline's questions

The pipeline may ask clarifying questions between stages. Answer them in plain
English. Each stage produces AC YAML files under
`docs/acceptance-criteria/<component>/`.

After the pipeline completes, all new ACs are at `readiness: reviewed`. They
are visible in the store but not yet eligible for ticket generation.

### Step 3: Review and adjust

Check the produced AC YAML files. In particular, verify:

- `criteria:` — is the criterion specific and testable?
- `priority:` — correct priority level?
- `estimated_complexity:` — does the IT PO's estimate look right?

Make any adjustments directly in the YAML files, then commit:

```bash
git add docs/acceptance-criteria/<component>/
git commit -m "plan: <feature name> — AC authoring via /plan-feature"
```

---

## 2. Approving ACs for building

Only ACs you explicitly approve are eligible for ticket generation. This gate
ensures you control what goes into the build backlog.

### List reviewed ACs awaiting approval

```bash
python scripts/ac_store/scan_ac_store.py --level leaf --work-status todo --readiness reviewed
```

### Promote each AC you want to build

Edit the YAML file and change:

```yaml
readiness: reviewed
```

to:

```yaml
readiness: approved
```

Commit the approval:

```bash
git add docs/acceptance-criteria/<component>/<ID>.yaml
git commit -m "approve <ID>: <short reason>"
```

The AC is now eligible for `/build-ac` to pick up.

---

## 3. Running /build-ac to generate a ticket

`/build-ac` selects the highest-priority approved AC, generates a ticket from
it, writes the ticket file to disk, and asks you to confirm before building.

### Step 1: Run /build-ac

```
/build-ac
```

The agent calls `ac_prioritizer.py` to rank all approved ACs and surfaces the
top candidate:

```
Next AC: ACS-042 — Add retry logic to the scanner
Priority: high | Complexity: M
Build this ticket now? (yes / review / skip)
```

### Step 2: Confirm, review, or skip

**`yes`** — the agent calls `generate_ticket_from_ac.py`, writes the ticket to
`tickets/00_inbox/`, and writes the `implemented_by` back-link into the AC
YAML. You then run `/build-feature` on the generated ticket path.

**`review`** — the agent opens the generated ticket file for inspection. After
inspection, answer `yes` or `skip`.

**`skip`** — the AC is marked `work_status: deferred` and the next ranked
candidate is proposed.

### Step 3: Drive the ticket to completion

After confirming, run `/build-feature` with the ticket path that `/build-ac`
prints:

```
/build-feature tickets/00_inbox/NN_<slug>.md
```

`ticket-supervisor` drives the ticket through its phase agents. After the PR
merges, `mark_ac_done.py` sets `work_status: done` on the source AC, closing
the traceability loop.

### Targeting a specific AC

If you want to build a specific AC rather than the top-ranked one, pass the
`--ac` flag:

```
/build-ac --ac ACS-042
```

The ranking step is skipped. All other steps are identical.

---

## 4. Migration: from /create-ticket to /plan-feature + /build-ac

`create-ticket.js` (the `/create-ticket` slash-command) is retired as of
ADR-012 (2026-06-16). It was built against the pre-v3 business-analyst JSON
contract; the v3 business-analyst produces AC YAML instead, so every field
`create-ticket.js` consumed was undefined at runtime — no ticket file was ever
produced. Invoking `create-ticket.js` now immediately exits with status 1 and
the message:

```
create-ticket.js is retired. Use /plan-feature + /build-ac instead.
See docs/architecture/adrs/ADR-012-retire-create-ticket-js.md
```

### What changes for you

| Old behaviour | New behaviour |
|---|---|
| Run `/create-ticket` to start ticket creation | Run `/plan-feature` to author ACs first |
| BA returns JSON → ticket file written immediately | BA produces AC YAML → you approve → `/build-ac` generates the ticket |
| Ticket is produced as a primary artefact | Ticket is a derived artefact generated from the AC store |
| No traceability from AC → ticket | `implemented_by` back-link written automatically |
| `depends_on` ordering manual | `scan_ac_store.py` resolves dependency order automatically |

### Why the change was made

ADR-010 (2026-06-05) inverted the source-of-truth: the AC store is now the
authoritative backlog, and tickets are derived artefacts generated from it.
`create-ticket.js` was the pre-inversion path — it bypassed the AC store and
produced tickets directly. ADR-012 retired it because:

- It was silently failing (no ticket file produced since v3 BA was shipped).
- Rewriting it to consume v3 BA output would duplicate `/plan-feature + /build-ac`
  with no benefit.
- Retiring it eliminates the silent-failure surface and consolidates on the
  ADR-010 pipeline.

### Quick mapping for common /create-ticket usage patterns

**"I just want a ticket for a small task right now"**

Use `/plan-feature` with a tightly scoped description. The pipeline will produce
one or two ACs. Approve them immediately and run `/build-ac`. The extra AC-authoring
step adds minimal overhead for small tasks and gives you a permanent requirement
record.

**"I was using /create-ticket to create epic tickets"**

The `/plan-feature + /build-ac` path supports goal-level ACs (L0/L1). When you
run `/build-ac --ac <L0-or-L1-ID>`, the system detects it is a goal and generates
a full EPIC folder from all leaf ACs beneath it. See
[How to use the unified /build-ac entry point](build-ac-unified.md) for details.

**"I need to see the ticket before building it"**

Answer `review` at the `/build-ac` confirmation prompt. The generated ticket
file is opened for inspection before any build is dispatched.

---

## Why phases are separated

The `/plan-feature` and `/build-ac` phases are deliberately separate:

- **`/plan-feature`** owns the _what_ — it captures requirements in the AC store
  before any implementation agent is involved. You can plan multiple features
  at once and approve only the ones you want to build.
- **`/build-ac`** owns the _when_ — it respects the `depends_on` ordering in
  the AC store so tickets are always generated in a valid dependency sequence.
  You cannot accidentally build AC-B before AC-A if AC-B depends on AC-A.

Combining the two phases into one step (as `create-ticket.js` did) coupled
requirement authoring to ticket generation, making it impossible to batch-plan
or to enforce dependency ordering at the ticket-generation boundary.

---

## See Also

- [How to use the AC-driven development system](ac-driven-development.md) —
  detailed walkthrough of the full PO → BA → IT PO → approve → build loop.
- [How to use the unified /build-ac entry point](build-ac-unified.md) —
  leaf vs goal mode detection and the epic-generation path.
- [ADR-012 — Retire create-ticket.js](../architecture/adrs/ADR-012-retire-create-ticket-js.md) —
  the decision record for the retirement with full alternatives analysis.
- [ADR-010 — AC Store as Authoritative Backlog](../architecture/adrs/ADR-010-ac-store-as-authoritative-backlog.md) —
  the source-of-truth inversion that motivated the canonical path.
