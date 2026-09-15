---
title: "KI-SS-004 — A workflow invoked by name can run a stale session-cached script"
description: "low — the workaround is reliable"
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

# KI-SS-004 — A workflow invoked by name can run a stale session-cached script

> One known issue, split out of `docs/known-issues/supervisor-system.md` on
> 2026-09-14. Index: [supervisor-system.md](../supervisor-system.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** low — the workaround is reliable
- **Status:** open — a harness-level behaviour, independent of repository state; reproduced
  repeatedly and unaffected by anything on `main`
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** the Workflow tool's by-name resolution, against `.leafcutter/workflows/<name>.js`

**Symptom.** Invoking a workflow by name may execute a stale session-cached script even after
`build.py` has redeployed it. The redeploy succeeds, the file on disk is correct, and the run
still exercises the old code — so a verified fix appears not to work.

**Why it costs time out of proportion to its severity.** It presents identically to "the fix is
wrong". An agent that has just edited a workflow, rebuilt, and re-run has every reason to
conclude the edit was ineffective, and the disk state supports the opposite conclusion only if
someone thinks to check it.

**Workaround.** Invoke by `scriptPath` against `.leafcutter/workflows/<name>.js` to force the
current version.

**Related:** `testing-quality.md`'s `KI-TQ-004` is the same hazard one layer down — a stale
deployed copy pinned in `sys.modules` for a whole pytest session. Both turn "I rebuilt" into a
false premise.

---
