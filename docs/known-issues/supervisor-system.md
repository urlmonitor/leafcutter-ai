---
title: "Known Issues: Supervisor System"
description: "Open defects in the /build-feature drive and its failure-adjudication ladder, found while driving EPIC-GE122UniquenessPassAndRepair: the commit phase runs despite unresolved blockers, and escalation can consume large amounts of wall-clock without converging."
type: reference
status: active
created: 2026-08-19
last_updated: 2026-08-19
components:
  - supervisor_system
related_docs:
  - docs/architecture/agent_delivery_workflows.md
  - templates/skills/building-epics/SKILL.md
  - templates/workflows-js/build-feature.js
---

# Known Issues: Supervisor System

Open defects in the `/build-feature` drive. All were observed directly on
2026-08-19 while driving `EPIC-GE122UniquenessPassAndRepair`, not inferred from
reading the code.

## KI-SUP-1 — The commit phase runs while gates are recorded `failed`

**Severity: high.** This is a phantom-done defect one level up from the ones the
package exists to prevent.

During the epic drive, `pr-reviewer` and `documentation-verifier` both returned
`status: blocker` on ticket `01_TICKET-20260818-GE-122a-1.md`. Neither blocker
was remediated. The drive nevertheless proceeded to the `commit` phase, which
committed and set `commit: signed_off` while the frontmatter still read:

```yaml
documentation-verifier: failed
pr-reviewer: failed
```

The commit message did name both open blockers, so the record is not dishonest —
but a gate that reports a blocker and is then committed past provides no
enforcement. The two blockers were real: one was a performance regression that
would have shipped a commit-time gate slow enough to be routinely bypassed, the
other a malformed contract line.

**Detection.** After any drive, check for a ticket where `commit: signed_off`
coexists with any phase in state `failed`:

```bash
grep -n "failed" <ticket>.md
```

**Workaround.** Do not treat drive completion as evidence. Read the frontmatter
`agents:` map directly and confirm no phase is `failed` before merging.

**Suggested fix.** Gate the `commit` phase on the absence of any `failed` phase,
and surface a halt rather than proceeding. The phase ordering in
`build-feature.js` already places every gate before `commit` at priority 12; what
is missing is the precondition check, not the ordering.

## KI-SUP-2 — The adjudication ladder can escalate repeatedly without converging

**Severity: medium.**

Three `brainstorm-lead` escalations fired on a single ticket and none produced an
applied fix. Roughly 50 minutes of a 2.5-hour drive went to them. In one case the
blocking agent had already written the exact corrective line into its own
sign-off comment; the escalation did not apply it, and it was later applied by
hand in a single edit.

For scale: the full drive covered **one** ticket of five in 2.5 hours. Driving
the same gates by direct dispatch covered the equivalent ground and found three
real defects in roughly 90 minutes.

**Detection.** Count `brainstorm-lead` spawns per ticket in the workflow
transcript directory. More than one on the same ticket is a signal:

```bash
grep -l brainstorm-lead <session>/subagents/workflows/<run>/agent-*.meta.json
```

**Workaround.** When a blocker's own remediation text is concrete and mechanical,
apply it directly rather than routing it through escalation.

**Suggested fix.** Before escalating, check whether the blocker's sign-off
contains an actionable remediation and attempt that first. Cap escalations per
ticket at one, as `building-epics` §4 already specifies — the observed behaviour
exceeded that cap.

## KI-SUP-3 — A workflow name-cache can run a stale script

**Severity: low** (workaround is reliable).

Invoking a workflow by name may execute a stale session-cached script even after
`build.py` has redeployed it. Invoke by `scriptPath` against
`.leafcutter/workflows/<name>.js` to force the current version.
