---
title: "KI-CG-024 — `check_ticket_signoff_parity.py` silently skips check #6 because its default registry path does not exist in this layout"
description: "KI-CG-024 — `check_ticket_signoff_parity.py` silently skips check #6 because its default registry path does not exist in this layout"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-024 — `check_ticket_signoff_parity.py` silently skips check #6 because its default registry path does not exist in this layout

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open — code is on `main`, but see the correction below: it is **not** live
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-26 (re-verified against `37655862`)
- **Where:** `templates/scripts/commit_guardian/config.py:224-226`
  (`AGENT_REGISTRY_PATH` default) consumed by
  `templates/scripts/commit_guardian/_signoff_parity_checks.py:96-103`
  (`load_agent_registry`)

> **Correction, 2026-08-31.** This entry's title says the hook "silently skips check #6". It skips
> **all six** — `check_ticket_signoff_parity.py` is named by no `entry:` line, so it never runs on
> any commit. The registry-path defect below is real, but repairing it alone would change nothing
> observable. `templates/scripts/precommit-autofix.json` also carries autofix routing for this
> hook: remediation wired to a gate that cannot fire. See
> `KI-CG-20260831-hook-scripts-never-invoked`.

**Symptom.** The hook resolves the agent registry at
`<worktree_root>/leafcutter/config/agent_registry.json`. That path is wrong for this layout
— nothing exists there — so it emits a warning to stderr and skips check #6 entirely:

```
[check-ticket-signoff-parity] WARNING: agent registry not found at
  <worktree>/leafcutter/config/agent_registry.json; skipping check #6
```

The hook then **exits 0**. The other checks run, so the hook looks healthy; one of its checks
has simply never fired in this layout.

**Evidence.** `config.py:224` reads
`AGENT_REGISTRY_PATH = _get("ticket_signoff_parity", "agent_registry_path",
"leafcutter/config/agent_registry.json")`. The registry actually lives at
`config/agent_registry.json` (repo root), and no `ticket_signoff_parity.agent_registry_path`
override is set anywhere in `config/` or `.claude/skills_config.json`, so the wrong default
is what every run uses. `load_agent_registry` returns `{}` and its docstring names the
behaviour as intentional: *"Fail-open: returns an empty dict when the registry file is absent
or unreadable so that check #6 is skipped rather than blocking commits."*

**Detection.** Run the hook and read stderr, not just the exit code. Silence is not the same
as a pass.

**Fix direction.** Resolve the registry the way other layout-aware scripts do — derive the
root from `git rev-parse` via the sibling `_resolve_root.py` that 27 files in the same
directory already import, and support both the source-repo and deployed layouts. Correcting
the default alone is the one-line fix. Separately, consider whether an unresolvable registry
should fail closed rather than skip: fail-open was chosen so a missing registry cannot block
commits, but the cost is a check nobody knows is off.

**Pattern:** `docs/reference/false-green-mechanisms.md` — a gate that reports success while
one of its checks was never given the data it needs.

---
