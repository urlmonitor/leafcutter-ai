---
title: "KI-CG-024 — `check_ticket_signoff_parity.py` silently skips check #6 because its default registry path does not exist in this layout"
description: "KI-CG-024 — `check_ticket_signoff_parity.py` silently skips check #6 because its default registry path does not exist in this layout"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-25'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-024 — `check_ticket_signoff_parity.py` silently skips check #6 because its default registry path does not exist in this layout

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** **RESOLVED** (`e5965006`, PR #793; hook registered in `406375c8`, PR #660; verified
  2026-09-25 on `main` @ `d2fe85a1` by running the deployed hook and `load_agent_registry()`)
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

## Resolution

Verified 2026-09-25 against `main` @ `d2fe85a1`.

- **Registry default fixed.** `templates/scripts/commit_guardian/config.py:224-226` now defaults
  `AGENT_REGISTRY_PATH` to `config/agent_registry.json`, which exists. The deployed copy
  `.leafcutter/scripts/commit_guardian/config.py:225` matches. Fixed in `e5965006`
  (`fix(commit-guardian): four gates that reported success while seeing nothing`, PR #793).
- **Registry actually loads.** Calling `load_agent_registry()` from the deployed
  `_signoff_parity_checks.py` with the repo root returned **60** entries (the fixing commit
  reports 0 before and 60 after).
- **Hook is live.** The 2026-08-31 correction no longer applies. `.pre-commit-config.yaml:438-444`
  registers `check-ticket-signoff-parity` with an `entry:` line, added in `406375c8` (PR #660).
  Running that entry against a staged-style ticket path
  (`run_hook.py .../check_ticket_signoff_parity.py tickets/00_inbox/TICKET-20260526-git_check_precondition.md`)
  exited 0 **with no `skipping check #6` warning on stderr**. This follows the KI's own Detection advice
  to read stderr as well as the exit code.

**Out of scope, still present, and not tracked by any KI as of this date:** the same
`leafcutter/`-prefix path bug exists in `_PATHS_JSON_REL = "leafcutter/config/paths.json"` at
`templates/scripts/commit_guardian/check_paths_integrity.py:28` and
`templates/scripts/commit_guardian/check_architecture_scaffolds.py:38`. The latter also has
`_SCAFFOLD_DIR_REL = "leafcutter/templates/docs/architecture"`. These belong to different hooks
and are a different defect from this entry's agent-registry default, so they need their own KI.
The fail-open design choice this entry questions is still in place. The folder-keyed enforcement
defect in the same hook is tracked separately as
`KI-CG-20260925-signoff-parity-enforces-only-under-done-folder`.

---
