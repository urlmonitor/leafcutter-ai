---
title: "KI-FC-002 — The sidecar id-recovery fallback is keyed on whole seconds and shares one stderr file, so parallel agents can read each other's feedback id"
description: "KI-FC-002 — The sidecar id-recovery fallback is keyed on whole seconds and shares one stderr file, so parallel agents can read each other's feedback id"
type: reference
category: reference
status: active
created: '2026-08-25'
last_updated: '2026-08-25'
components:
  - feedback_collector
related_docs:
  - docs/known-issues/feedback-collector.md
  - docs/known-issues/README.md
---

# KI-FC-002 — The sidecar id-recovery fallback is keyed on whole seconds and shares one stderr file, so parallel agents can read each other's feedback id

> One known issue, split out of `docs/known-issues/feedback-collector.md` on
> 2026-09-14. Index: [feedback-collector.md](../feedback-collector.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open (latent — mechanism confirmed, no wrong id observed in a ticket yet)
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/feedback/submit_feedback.py` (`:549-550`);
  `templates/skills/signoff/SKILL.md` (`:180`, `:186`)

**Symptom.** When an agent cannot capture the id from stdout, the documented fallback is to
read a sidecar file whose path the script writes to stderr. Both halves of that fallback are
shared state under parallel dispatch:

1. The sidecar is named `feedback_id_<epoch_seconds>.txt` (`:549-550`) — one-second
   granularity. Two entries in this drive, `869bc2f7` and `9057159a`, share timestamp
   `18:52:29Z`. Only one sidecar exists for that second
   (`/tmp/feedback_id_1787683949.txt`), containing `fb_2026-08-25_9057159a`. The other was
   overwritten.
2. Every agent redirects stderr to the **same** `/tmp/feedback_err.txt` (`SKILL.md:180`) and
   greps it for the sidecar path (`SKILL.md:186`).

`/build-feature` dispatches a batch of tickets concurrently, so both collisions are reachable
in an ordinary drive.

**Why it is worth recording while still latent.** It did not bite here — stdout capture
worked for every agent that got that far. But the failure it produces is a *wrong* id written
into a ticket sign-off, not a missing one. A missing id is visible; a plausible id belonging
to another agent's phase is not, and it corrupts the traceability the field exists to provide.

**Fix direction.** Add PID and a random suffix to the sidecar filename. Give each agent a
distinct stderr file — `ticket-supervisor.md` already uses a `feedback_err_<slug>.txt`
convention that the signoff skill does not follow. Neither change is large; the current
naming is only safe under serial dispatch, which is not how epics run.

**Pattern:** a recovery path that assumes one writer, invoked from a fan-out.

---
