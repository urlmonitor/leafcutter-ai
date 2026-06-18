---
title: "How to use the AC-driven build loop on a consumer install"
description: "Step-by-step guide to running the AC-driven build loop (/build-ac and ac-scanner) on a consumer install, including the deployed ac_store scripts."
type: how-to
category: how-to
status: active
created: 2026-06-17
last_updated: 2026-06-17
components:
  - ac_store
  - skills_system
  - build_pipeline
related_docs:
  - docs/architecture/adrs/ADR-010-ac-store-as-authoritative-backlog.md
  - docs/architecture/adrs/ADR-013-portable-skill-script-deployment-boundary.md
  - docs/how-to/ac-driven-development.md
  - docs/how-to/build-ac-unified.md
  - docs/how-to/ticket-creation-workflow.md
---

# How to use the AC-driven build loop on a consumer install

The AC-driven build loop turns the AC store into the authoritative backlog for
any project running leafcutter. You author acceptance criteria with `/plan-feature`,
approve the ones you want built, and let `/build-ac` generate the ticket and drive
it through the full agent build pipeline — on your own project, not just in the
leafcutter package itself.

This guide covers four tasks:

1. [Verifying the prerequisites on a consumer install](#1-verifying-the-prerequisites)
2. [Authoring and approving ACs with /plan-feature](#2-authoring-and-approving-acs)
3. [Running /build-ac to generate and dispatch a ticket](#3-running-build-ac)
4. [Completing the ticket and closing the traceability loop](#4-completing-the-ticket)

**Design references:**

- [ADR-010 — AC Store as Authoritative Backlog](../architecture/adrs/ADR-010-ac-store-as-authoritative-backlog.md) —
  explains why the AC store, not ticket files, is the source of truth.
- [ADR-013 — Portable Skill Script Deployment Boundary](../architecture/adrs/ADR-013-portable-skill-script-deployment-boundary.md) —
  defines what "portable: true" means and how `build_ac_store` deploys the
  pipeline scripts to consumer installs.

---

## Prerequisites

Before you begin, confirm the following:

- **Build has been run.** `build.py` has been executed against your project:

  ```bash
  python leafcutter-ai/scripts/build.py --target-dir .
  ```

  This is the step that deploys the AC pipeline scripts to your project. If you
  skip it, `/build-ac` and `/ac-scanner` will be absent.

- **PyYAML is installed.** The AC store scripts require it:

  ```bash
  pip install pyyaml
  ```

- **Both `/plan-feature` and `/build-ac` are deployed.** Verify by listing the
  deployed slash-command workflows:

  ```bash
  ls .claude/workflows/
  ```

  You should see `plan-feature.js` and `build-ac.js` (or equivalent `.md` files,
  depending on your install version). If either is missing, re-run `build.py` after
  confirming that `plan-feature` deployment is complete (see
  EPIC-AcPipelineDeployGaps for context on the `plan-feature.js` deployment step).

- **AC store directory exists.** The store lives at `docs/acceptance-criteria/`.
  It is created by `build.py` if absent, but confirm it exists before proceeding:

  ```bash
  ls docs/acceptance-criteria/
  ```

- **Familiarity required.** You understand the five AC readiness states
  (`draft`, `reviewed`, `approved`, `done`, `deferred`) and the YAML schema for
  AC files. See [How to use the AC Traceability Store](ac-traceability-store.md)
  for a schema reference.

---

## 1. Verifying the Prerequisites

Before invoking `/plan-feature`, confirm the AC pipeline scripts were deployed
correctly by the `build_ac_store` phase.

### Step 1: Check that all six AC pipeline scripts are present

```bash
ls scripts/ac_store/
```

Expected output (order may differ):

```
scan_ac_store.py
generate_ticket_from_ac.py
ac_prioritizer.py
mark_ac_done.py
build_ac_mode_detection.py
goal_to_epic.py
```

If any of these files are missing, `build.py` either did not run or ran from
an older version of leafcutter-ai that predates the `build_ac_store` phase
(introduced in EPIC-AcPipelineDeployGaps). Re-run `build.py` with the current
leafcutter-ai source.

### Step 2: Confirm /build-ac is registered

```bash
ls .claude/workflows/
```

Confirm `build-ac.js` or `build-ac.md` is listed. If it is absent, check that
your leafcutter-ai version includes the `/build-ac` and `/plan-feature` workflow
templates — both require the `plan-feature.js` deployment step described in
EPIC-AcPipelineDeployGaps ticket 02.

### Step 3: Validate PyYAML is importable by the scripts

```bash
python -c "import yaml; print('pyyaml ok')"
```

Expected output: `pyyaml ok`. If the command raises `ModuleNotFoundError`,
install PyYAML and re-verify.

---

## 2. Authoring and Approving ACs

ACs are authored through the `product-owner` → `business-analyst` → `it-po`
pipeline and stored as YAML files under `docs/acceptance-criteria/`. Only ACs
you explicitly promote to `readiness: approved` are eligible for ticket
generation.

For the full walkthrough of the authoring pipeline, see
[How to use the AC-driven development system](ac-driven-development.md).

### Step 1: Invoke /plan-feature

```
/plan-feature
```

Describe the feature you want to build in plain language. Include the observable
behaviour you expect, the error cases you care about, and any priority guidance.

`/plan-feature` runs the three-agent pipeline under the hood and produces AC
YAML files under `docs/acceptance-criteria/<component>/`. All new ACs are
written with `readiness: reviewed`.

### Step 2: Review the produced ACs

```bash
python scripts/ac_store/scan_ac_store.py --level leaf --work-status todo --readiness reviewed
```

Open each YAML file and verify:

- `criteria:` — is the requirement specific and testable?
- `priority:` — is the priority level correct (`critical`, `high`, `medium`, or `low`)?
- `estimated_complexity:` — does the IT PO's estimate look right?

### Step 3: Promote ACs to approved

Edit each AC you want to build and change the `readiness` field:

```yaml
readiness: approved
```

Commit the approvals:

```bash
git add docs/acceptance-criteria/<component>/<ID>.yaml
git commit -m "approve <ID>: <short reason>"
```

Only `readiness: approved` ACs are visible to `/build-ac`. ACs at `draft` or
`reviewed` are excluded from the scanner.

---

## 3. Running /build-ac

`/build-ac` is the single entry point for generating a ticket from the AC store
and dispatching the build. It auto-detects the AC type (leaf vs goal) and routes
to the appropriate pipeline.

The command uses two AC pipeline scripts deployed by `build_ac_store`:

- `ac_prioritizer.py` — ranks all approved, todo ACs by priority and surfaces
  the top candidate.
- `generate_ticket_from_ac.py` — writes the ticket file and the `implemented_by`
  back-link into the AC YAML.

### Step 1: Run /build-ac

```
/build-ac
```

The agent calls `ac_prioritizer.py` and presents the top-ranked approved AC:

```
Next AC: ACS-042 — Add retry logic to the scanner
Priority: high | Complexity: M
Build this ticket now? (yes / review / skip)
```

### Step 2: Respond to the prompt

**`yes`** — the ticket is generated at `tickets/00_inbox/<slug>.md` and the
`implemented_by` field is written into the AC YAML. The agent prints the ticket
path. You then run `/build-feature` on that path (see Task 4).

**`review`** — the generated ticket file is opened for inspection. After
reviewing, answer `yes` or `skip`.

**`skip`** — the current AC is marked `work_status: deferred` and the next
ranked candidate is proposed immediately. Use this to defer low-priority work
without losing track of it.

### Step 3: Note the generated ticket path

After answering `yes`, the agent prints the ticket path:

```
Ticket written: tickets/00_inbox/042_add-retry-logic.md
```

Keep this path — you will pass it to `/build-feature` in the next task.

### Targeting a specific AC

If you want to build a specific AC rather than the top-ranked candidate, pass
the `--ac` flag:

```
/build-ac --ac ACS-042
```

The ranking step is skipped. All other steps are identical.

---

## 4. Completing the Ticket

After `/build-ac` generates the ticket, you drive it to completion with
`/build-feature`. When the PR merges, `mark_ac_done.py` closes the traceability
loop by writing `work_status: done` back onto the source AC.

### Step 1: Drive the ticket with /build-feature

Pass the ticket path printed in Task 3:

```
/build-feature tickets/00_inbox/042_add-retry-logic.md
```

`ticket-supervisor` dispatches all phase agents in order
(`test-writer`, `python-coder`, `pr-reviewer`, `commit`, `pull-request`).

### Step 2: Merge the PR

Review and merge the pull request on your Git hosting platform. After the PR
merges to main, the traceability loop is ready to close.

### Step 3: Close the traceability loop

`/build-ac` calls `mark_ac_done.py` automatically after a successful build.
If the build was interrupted or `/build-feature` was invoked separately, close
the loop manually:

```bash
python scripts/ac_store/mark_ac_done.py --ticket tickets/00_inbox/042_add-retry-logic.md
```

`mark_ac_done.py` reads the `source_ac` field from the ticket frontmatter,
locates the AC YAML, and sets `work_status: done`. The AC is now excluded from
future scanner runs.

### Step 4: Verify the loop closed

Confirm the AC was marked done:

```bash
grep "work_status: done" docs/acceptance-criteria/<component>/<ID>.yaml
```

Expected output: `work_status: done` on a line in the YAML file.

---

## Verification

After completing all four tasks, confirm the full loop ran correctly:

**Check the ticket was generated:**

```bash
ls tickets/00_inbox/
```

Your ticket file should be listed (e.g. `042_add-retry-logic.md`).

**Check the AC back-link was written:**

```bash
grep "implemented_by" docs/acceptance-criteria/<component>/<ID>.yaml
```

Expected output: a line containing `implemented_by:` with the ticket path.

**Check the AC is marked done:**

```bash
grep "work_status: done" docs/acceptance-criteria/<component>/<ID>.yaml
```

Expected output: `work_status: done`.

**Check no approved ACs are still pending:**

```bash
python scripts/ac_store/scan_ac_store.py --level leaf --work-status todo --readiness approved
```

If the AC you just built is still listed, `mark_ac_done.py` did not run. Close
the loop manually as described in Task 4, Step 3.

---

## Troubleshooting

**1. `/build-ac` reports "command not found"**

The `build-ac.js` or `build-ac.md` workflow was not deployed. Re-run `build.py`
using a version of leafcutter-ai that includes the `plan-feature.js` deployment
step (EPIC-AcPipelineDeployGaps). Confirm both `plan-feature.js` and `build-ac.js`
appear under `.claude/workflows/` after the build.

**2. `scripts/ac_store/` is missing or incomplete**

The `build_ac_store` deployment phase did not run. This phase was added in
EPIC-AcPipelineDeployGaps. If your leafcutter-ai source predates this epic,
update the source and re-run `build.py`. If your source is current, confirm
`build_ac_store` is listed as a phase in `scripts/build_phases.py` and that
`build.py` calls it.

**3. `ModuleNotFoundError: No module named 'yaml'`**

PyYAML is not installed in the Python environment that runs the AC store scripts.
Install it:

```bash
pip install pyyaml
```

If you are using a virtual environment, activate it before running the AC store
scripts.

**4. `/build-ac` generates a ticket but the `implemented_by` field is missing**

`generate_ticket_from_ac.py` did not write the back-link. This can happen if the
AC YAML file is not writable or if the AC ID could not be resolved. Verify the
AC YAML file is readable and writable, and that the `id` field in the YAML
matches the ID passed to `/build-ac`. Add the back-link manually if needed:

```yaml
implemented_by: tickets/00_inbox/<slug>.md
```

**5. `mark_ac_done.py` exits with "source_ac not found in ticket frontmatter"**

The ticket was not generated by `generate_ticket_from_ac.py`, or the
`source_ac` field was manually removed. Add it back to the ticket frontmatter:

```yaml
source_ac: <AC-ID>
```

Then re-run `mark_ac_done.py`.

---

## See Also

- [How to use the AC-driven development system](ac-driven-development.md) —
  detailed walkthrough of the PO → BA → IT PO authoring pipeline, approval
  gate, and done-link loop.
- [How to use the unified /build-ac entry point](build-ac-unified.md) —
  auto-detection logic for leaf vs goal mode; epic-generation path for L0/L1
  goal ACs.
- [How to create a ticket: /plan-feature + /build-ac](ticket-creation-workflow.md) —
  canonical two-phase ticket-creation sequence and migration from /create-ticket.
- [ADR-010 — AC Store as Authoritative Backlog](../architecture/adrs/ADR-010-ac-store-as-authoritative-backlog.md) —
  the design decision that makes the AC store the source of truth for the backlog.
- [ADR-013 — Portable Skill Script Deployment Boundary](../architecture/adrs/ADR-013-portable-skill-script-deployment-boundary.md) —
  canonical policy for which skills and scripts are deployed to consumer installs.
- [docs/README.md](../README.md) — project overview and navigation index.
