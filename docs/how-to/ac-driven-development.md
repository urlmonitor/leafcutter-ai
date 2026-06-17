---
title: "How to use the AC-driven development system"
type: how-to
category: how-to
status: active
created: 2026-06-05
last_updated: 2026-06-05
components:
  - ac-store
  - build-orchestration
  - ticket-creation
related_docs:
  - docs/architecture/diagrams/c2-002-ac-authoring-pipeline.md
  - docs/architecture/diagrams/c2-004-build-ac-flow.md
  - docs/architecture/diagrams/c2-003-ac-readiness-states.md
  - docs/architecture/diagrams/c2-001-ac-driven-pipeline.md
  - docs/how-to/ac-traceability-store.md
---

# How to use the AC-driven development system

The AC-driven development system turns the AC store into the authoritative
backlog. Instead of writing tickets by hand, you author acceptance criteria
once through the `product-owner` / `business-analyst` / `it-po`
pipeline, approve the ones you want built, and let `/build-ac` generate
the ticket and drive it through the full agent build pipeline.

This guide covers six tasks:

1. [Authoring new ACs via the PO/BA pipeline](#1-authoring-new-acs-via-the-poba-pipeline)
2. [Reviewing and approving ACs](#2-reviewing-and-approving-acs)
3. [Invoking /build-ac](#3-invoking-build-ac)
4. [Targeting a specific AC with /build-ac --ac](#4-targeting-a-specific-ac-with-build-ac---ac)
5. [Checking which ACs are ready, blocked, or draft](#5-checking-which-acs-are-ready-blocked-or-draft)
6. [Understanding the done-link loop](#6-understanding-the-done-link-loop)

**Prerequisites:**

- Tickets 00–04 of EPIC-ACDrivenDevelopment are merged and deployed
  (`build.py` has been run in your project).
- `scan_ac_store.py`, `ac_prioritizer.py`, `generate_ticket_from_ac.py`,
  and `mark_ac_done.py` are installed under `scripts/ac_store/`.
- The `/build-ac` command is registered in `.claude/` (deployed from
  `templates/workflows/build-ac.md`).
- `validate_ac_schema.py` is active as a pre-commit hook.

---

## 1. Authoring new ACs via the PO/BA pipeline

New ACs are authored through a three-agent pipeline. You describe the
feature to `product-owner`, which writes L0/L1 ACs; `business-analyst`
decomposes them into L2/L3 behavioural ACs and produces documentation ACs
where needed; `it-po` enriches the ACs with technical fields and sets
them to `readiness: reviewed`.

### Step 1: Invoke product-owner

Open a new Claude Code conversation and run:

```
/product-owner
```

Describe the feature you want to build. Be as specific as you can about
the observable behaviour you expect (inputs, outputs, error cases).

`product-owner` will produce L0 and L1 AC YAML files under
`docs/acceptance-criteria/<component>/`. Each AC is written with
`readiness: draft` and `priority: medium`. L1 ACs include a
`documentation_triggers` field listing which diagram and guide types
are needed (e.g. `[how-to, sequence-diagram]`).

### Step 2: Let business-analyst decompose the L1 ACs

`product-owner` will automatically hand off to `business-analyst`,
or you can invoke it directly:

```
/business-analyst
```

Pass the L1 AC file paths. `business-analyst` will produce L2/L3
behavioural ACs and, for each `documentation_triggers` entry on the parent
L1, a corresponding documentation AC (e.g. a how-to AC assigned to
`documentation-expert`). All new ACs are written with `readiness: draft`.

### Step 3: Let it-po enrich and gate the batch

Invoke `it-po` and pass the new AC files:

```
/it-po
```

`it-po` adds technical fields (`assigned_agent`, `estimated_complexity`,
`delivers_to`, `expects_from`) and checks the documentation gate: for any
L1 with `documentation_triggers`, at least one documentation AC must exist
for each trigger type. When the gate passes, `it-po` sets
`readiness: reviewed` on the batch.

### Step 4: Validate and commit

The `validate_ac_schema.py` pre-commit hook will run automatically when
you `git commit`. It enforces the JSON schema and requires both `readiness`
and `priority` fields. If any AC is missing a required field, the commit is
blocked with a message naming the field and valid values.

Fix any reported errors and commit again.

---

## 2. Reviewing and approving ACs

After `it-po` sets `readiness: reviewed`, the AC is visible to you but
not yet eligible for ticket generation. Only you (the user) may promote an
AC to `readiness: approved`.

### Step 1: List reviewed ACs

```bash
python scripts/ac_store/scan_ac_store.py --level leaf --work-status todo --readiness reviewed
```

This returns all ACs that have been enriched and are awaiting your approval.

### Step 2: Read and inspect each AC

Open the YAML file for each AC you want to assess. Check:

- `criteria:` — is the acceptance criterion specific and testable?
- `priority:` — is this the right priority (`critical`, `high`, `medium`,
  or `low`)? Adjust if needed.
- `estimated_complexity:` — does the IT PO's estimate seem correct?
- `documentation_triggers:` (on L1 ACs) — are the listed doc types correct?

### Step 3: Promote to approved

For each AC you want to build, edit the YAML file and change the
`readiness` field:

```yaml
readiness: approved
```

Optionally adjust `priority` at the same time. Commit the change:

```bash
git add docs/acceptance-criteria/<component>/<ID>.yaml
git commit -m "approve <ID>: ready to build"
```

The AC is now eligible for ticket generation. The scanner will pick it up
the next time `/build-ac` runs.

For a visual reference of all five states and who owns each transition, see
the [AC readiness state machine](../architecture/diagrams/c2-003-ac-readiness-states.md).

---

## 3. Invoking /build-ac

`/build-ac` finds the highest-priority approved AC, generates a ticket from
it, and asks you to confirm before building.

### Step 1: Run /build-ac

```
/build-ac
```

The agent calls `ac_prioritizer.py` to rank all `readiness: approved`,
`work_status: todo` ACs and surfaces the top candidate:

```
Next AC: ACS-042 — Add retry logic to the scanner
Priority: high | Complexity: M
Build this ticket now? (yes / review / skip)
```

### Step 2: Choose a response

**`yes`** — The agent calls `generate_ticket_from_ac.py`, writes the ticket
to `tickets/00_inbox/`, then dispatches `/build-feature` on that ticket.
After `/build-feature` completes it calls `mark_ac_done.py` to close the
AC. The full done-link loop runs automatically.

**`review`** — The agent opens the generated ticket file so you can inspect
it before deciding. After inspection, re-answer with `yes` or `skip`.

**`skip`** — The agent marks the current AC as `work_status: deferred` and
immediately proposes the next ranked candidate. Use `skip` to defer low-
priority work without losing track of it.

For the full sequence diagram of this flow, see
[/build-ac execution flow](../architecture/diagrams/c2-004-build-ac-flow.md).

---

## 4. Targeting a specific AC with /build-ac --ac

When you know exactly which AC you want to build, bypass the ranking step:

### Step 1: Find the AC id

```bash
python scripts/ac_store/scan_ac_store.py --level leaf --work-status todo --json
```

Note the `id` field of the AC you want (e.g. `ACS-042`).

### Step 2: Invoke /build-ac with the --ac flag

```
/build-ac --ac ACS-042
```

The ranking step is skipped. The agent proposes `ACS-042` directly and
presents the `yes / review / skip` prompt. All subsequent steps are
identical to the standard flow.

This is useful when:
- You want to build a lower-priority AC before a higher-priority one.
- You are re-activating a previously `deferred` AC.
- You are testing the end-to-end pipeline with a specific AC.

---

## 5. Checking which ACs are ready, blocked, or draft

Use `scan_ac_store.py` directly to inspect the state of the AC store
without triggering a build.

### List all ready (approved + todo) ACs

```bash
python scripts/ac_store/scan_ac_store.py --level leaf --work-status todo --json
```

Only ACs with `readiness: approved` appear in the READY list. ACs at
`draft` or `reviewed` are excluded.

### List blocked ACs

Blocked ACs are `readiness: approved` but have an unresolved `depends_on`
dependency (the depended-on AC is not yet `work_status: done`).

```bash
python scripts/ac_store/scan_ac_store.py --level leaf --work-status todo --show-blocked
```

The output includes each blocked AC and the dependency that is blocking it.

### Find draft and reviewed ACs awaiting action

These ACs are visible in the store but not yet eligible for the scanner:

```bash
python scripts/ac_store/scan_ac_store.py --level leaf --work-status todo --readiness draft
python scripts/ac_store/scan_ac_store.py --level leaf --work-status todo --readiness reviewed
```

Use these commands to track which ACs are waiting for `it-po` enrichment
(`draft`) or waiting for your approval (`reviewed`).

### Validate the entire store

```bash
python scripts/ac_store/validate_ac_schema.py docs/acceptance-criteria/
```

Reports all YAML files that violate the schema. Fix any errors before
promoting ACs to `approved`, as the scanner may fail on malformed files.

For the component-level view of all scripts and how they connect, see the
[AC-driven pipeline component diagram](../architecture/diagrams/c2-001-ac-driven-pipeline.md).

---

## 6. Understanding the done-link loop

The done-link loop closes the traceability chain from AC definition through
to merged implementation. It runs automatically at the end of a successful
`/build-ac` run.

### What happens

1. `/build-feature` dispatches `ticket-supervisor`, which drives the ticket
   through all phase agents (`python-coder`, `test-writer`, `test-runner`,
   `pr-reviewer`, `commit`, `pull-request`).
2. After `pull-request` completes and the PR merges to main, `build-ac`
   calls `mark_ac_done.py --ticket <ticket_path>`.
3. `mark_ac_done.py` reads the `source_ac` field from the ticket frontmatter,
   locates the AC YAML in `docs/acceptance-criteria/`, and sets
   `work_status: done`.
4. The AC is now `readiness: approved`, `work_status: done`. It is excluded
   from future scanner runs.

### Verifying the loop

After a build completes, check that the AC was closed:

```bash
grep "work_status: done" docs/acceptance-criteria/<component>/<ID>.yaml
```

You can also inspect the ticket to confirm `source_ac` was set:

```bash
grep "source_ac:" tickets/00_inbox/<ticket_name>.md
```

### If the loop did not run

If the build failed or `/build-feature` was interrupted, `mark_ac_done.py`
may not have run. In that case the AC remains `work_status: todo` and will
be proposed again by `/build-ac`. This is safe — the idempotency guard in
`generate_ticket_from_ac.py` will detect the existing ticket and refuse to
generate a duplicate.

To manually close the loop after a successful merge:

```bash
python scripts/ac_store/mark_ac_done.py --ticket tickets/00_inbox/<ticket_name>.md
```

For the full sequence showing when `mark_ac_done.py` is called, see the
[/build-ac execution flow diagram](../architecture/diagrams/c2-004-build-ac-flow.md).

---

## Diagram Index

All four diagrams that underpin this guide:

| Diagram | What it shows |
|---|---|
| [AC authoring pipeline](../architecture/diagrams/c2-002-ac-authoring-pipeline.md) | User → PO → BA → IT PO → User approval sequence with readiness states |
| [/build-ac execution flow](../architecture/diagrams/c2-004-build-ac-flow.md) | Ranking, ticket generation, yes/review/skip branches, and done-link |
| [AC readiness state machine](../architecture/diagrams/c2-003-ac-readiness-states.md) | All five states (`draft`, `reviewed`, `approved`, `done`, `deferred`) and owning actors |
| [AC-driven pipeline component diagram](../architecture/diagrams/c2-001-ac-driven-pipeline.md) | All seven scripts and agents with labelled data flows |

---

## See Also

- [How to use the AC Traceability Store](ac-traceability-store.md) — creating,
  amending, and deprecating individual AC YAML files.
- [Agent Delivery Workflows](../architecture/agent_delivery_workflows.md) —
  how `epic-supervisor` and `ticket-supervisor` execute the tickets produced
  by this pipeline.
