---
title: "KI-BO-20260917-no-status-transition-into-blocked — `set_ticket_status.py` cannot move a ticket into `blocked` or `deferred` even with `--force`, while the epic runbook prescribes exactly that command"
description: "KI-BO-20260917-no-status-transition-into-blocked — `set_ticket_status.py` cannot move a ticket into `blocked` or `deferred` even with `--force`, while the epic runbook prescribes exactly that command"
type: reference
category: reference
status: active
created: '2026-09-17'
last_updated: '2026-09-17'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-20260917-no-status-transition-into-blocked — `set_ticket_status.py` cannot move a ticket into `blocked` or `deferred` even with `--force`, while the epic runbook prescribes exactly that command

> Index: [build-orchestration.md](../build-orchestration.md). Filename severity is the
> three-level index bucket (`low`); the original grading is the `**Severity:**` line below.

- **Severity:** medium. The refusal is loud, not silent. But no sanctioned route exists to
  record a hold in frontmatter, and hand-editing the status runs into a commit gate.
- **Status:** open — **no AC**. No acceptance criterion in the store owns ticket hold/deferral
  status transitions. The `BO-400` ACs that cite `set_ticket_status.py` cover
  `in_progress`/`done` writes and the done-folder rules, not holds.
- **Occurrences:** 1 (2026-09-16: 7 tickets in `EPIC-StartingNewWorkTheProperWayAlways` held
  back; each carries a "HELD BACK" comment explaining why its status stayed `todo`)
- **First seen:** 2026-09-16 · **Last seen:** 2026-09-16
- **Where:** `scripts/set_ticket_status.py:49-72` (`ALLOWED_TRANSITIONS`,
  `FORCE_ALLOWED_TRANSITIONS`, `VALID_STATUSES`) and the refusal at `:394-410`;
  `templates/skills/building-epics/SKILL.md` §7.2 (`:1220-1222`, deployed to
  `.claude/skills/building-epics/SKILL.md`);
  `templates/scripts/commit_guardian/check_proof_promise_claim.py:149-153`
  (`_STILL_PLANNED_STATUS = "todo"`)

**Symptom.** `set_ticket_status.py --status blocked --force` on a `todo` ticket prints
`Invalid transition: todo -> blocked (not permitted even with --force)` and exits 1.

**Mechanism — three pieces that do not agree.**

1. **The script.** `VALID_STATUSES` includes `blocked` and `deferred`. But no pair in
   `ALLOWED_TRANSITIONS` (`todo→in_progress`, `in_progress→done`, `in_progress→todo`) or
   `FORCE_ALLOWED_TRANSITIONS` has either one as its **target**. `blocked` appears only as a
   source (`blocked→todo`, `blocked→in_progress`), and `deferred` appears in no pair. A ticket
   can leave `blocked` but cannot enter it from any state, `in_progress` included.
2. **The runbook.** `building-epics` §7.2 says a failing sub-ticket at archival must be
   deferred "by updating its frontmatter `status:` to `blocked` via
   `set_ticket_status.py --status blocked --force`". That command always fails.
3. **The proof-promise gate.** `check_proof_promise_claim` (BP-1100g-4-ii) exempts **only**
   `status: todo` from its promise-versus-claim comparison. Its own comment says blocked and
   deferred "remain subject to the check". So hand-editing an unstarted ticket to `blocked`
   makes the commit fail whenever the ticket promises a test kind that no test claims yet,
   which is the normal state of an unbuilt ticket.

Together: an unstarted ticket cannot be put on hold in frontmatter by the script, by the
runbook's recipe, or by hand.

**Evidence.** The 2026-09-16 hold, as recorded in the ticket itself
(`tickets/00_inbox/epics/EPIC-StartingNewWorkTheProperWayAlways/01_TICKET-20260826-ACD-2100a-1.md`,
"2026-09-16 — HELD BACK"):

> Status deliberately left at `todo`. An unstarted ticket cannot be `blocked` here:
> `set_ticket_status.py` has no `todo -> blocked` transition (refused even with `--force`),
> and the proof-promise gate (BP-1100g-4) exempts only `todo` from its claim check. The hold
> is recorded by this comment and by Master_Plan.md.

`grep -l "HELD BACK"` finds that comment in 7 of the epic's tickets, and all 26 tickets read
`status: todo`.

**Workaround in use.** Leave `status: todo`. Record the hold in a `## Comments` entry and in
a "Held back" section of `Master_Plan.md`. Nothing enforces that record; see
`KI-BO-20260917-epic-planner-ignores-held-tickets`.

**Fix direction.**

- Add `todo→blocked`, `in_progress→blocked`, `todo→deferred` and `in_progress→deferred`
  (forced or not; a hold is not a completion claim), plus a way out of `deferred`.
- Let `check_proof_promise_claim` exempt `blocked`/`deferred` the way it exempts `todo`,
  **only** when the ticket has no sign-offs, keeping the fail-closed posture for started work.
  Otherwise record why not in BP-1100g-4-ii.
- Correct `building-epics` §7.2 in the same change, and add a test that runs its literal
  command.
- Author an AC for "a ticket can be put on hold and the hold is honoured", which would also
  own the planner half.

---
