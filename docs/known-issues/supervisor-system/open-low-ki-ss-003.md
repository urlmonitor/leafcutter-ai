---
title: "KI-SS-003 — The adjudication ladder escalates to `brainstorm-lead` without a per-ticket cap and can burn a drive without converging"
description: "KI-SS-003 — The adjudication ladder escalates to `brainstorm-lead` without a per-ticket cap and can burn a drive without converging"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - supervisor_system
related_docs:
  - docs/known-issues/supervisor-system.md
  - docs/known-issues/README.md
---

# KI-SS-003 — The adjudication ladder escalates to `brainstorm-lead` without a per-ticket cap and can burn a drive without converging

> One known issue, split out of `docs/known-issues/supervisor-system.md` on
> 2026-09-14. Index: [supervisor-system.md](../supervisor-system.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open — code is on `main` and live; the code carries a per-*phase* retry cap and no
  per-*ticket* escalation cap at all
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-26 (re-verified against `37655862`)
- **Where:** `templates/workflows-js/build-feature.js:1657-1668` (the `failure-classifier`
  dispatch) and `:296` (`MAX_RETRIES = 2`); `templates/skills/building-epics/SKILL.md` §4

**Symptom.** Three `brainstorm-lead` escalations fired on a single ticket and none produced an
applied fix. Roughly 50 minutes of a 2.5-hour drive went to them. In one case the blocking agent
had already written the exact corrective line into its own sign-off comment; the escalation did
not apply it, and it was later applied by hand in a single edit.

For scale: the full drive covered **one** ticket of five in 2.5 hours. Driving the same gates by
direct dispatch covered the equivalent ground and found three real defects in roughly 90 minutes.

**Root cause.** `building-epics` §4 specifies a cap of one escalation per ticket. Nothing
implements it. `build-feature.js` dispatches `brainstorm-lead` as the `failure-classifier` on
**every** blocker or failure, unconditionally, before any classification exists to gate on. The
only bound in the code is `MAX_RETRIES = 2` per phase name — so a ticket with several failing
phases can legitimately escalate many times while every individual counter stays inside its
limit. The observed behaviour did not violate the code; the code never encoded the rule.

**Detection.** Count `brainstorm-lead` spawns per ticket in the workflow transcript directory.
More than one on the same ticket is a signal:

```bash
grep -l brainstorm-lead <session>/subagents/workflows/<run>/agent-*.meta.json
```

**Workaround.** When a blocker's own remediation text is concrete and mechanical, apply it
directly rather than routing it through escalation.

**Fix direction.** Two parts, in order of value. (1) Before escalating, check whether the
blocker's sign-off contains an actionable remediation and attempt that first — in the observed
case the answer was already written down and the escalation was pure cost. (2) Count escalations
per *ticket*, not per phase, and enforce the §4 cap of one. A documented cap that no counter
implements is worse than no cap, because it is read as a guarantee.

---
