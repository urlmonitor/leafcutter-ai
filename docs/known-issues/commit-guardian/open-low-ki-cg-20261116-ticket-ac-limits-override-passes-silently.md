---
title: "KI-CG-20261116-ticket-ac-limits-override-passes-silently — with ac_limit_override: true, check-ticket-ac-limits counts only the Agent Contracts block, finds 0 on generated tickets, and exits 0 without its override warning"
description: "medium — the override branch of _analyse_ticket skips the full-body fallback the normal branch uses when ## Agent Contracts holds no AC lines. Generated tickets keep their checklist under ## Acceptance Criteria, so the override path counts 0 and the 'WARNING (override active)' line is never printed. Pre-commit also hides passing-hook output, because the hook has no verbose: true."
type: reference
category: reference
status: active
created: '2026-11-16'
last_updated: '2026-11-16'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
  - docs/known-issues/ac-driven-dev/open-low-ki-acd-20261116-generator-checklists-given-and-when-preconditions.md
---

# KI-CG-20261116-ticket-ac-limits-override-passes-silently — the ticket AC-count override leaves no trace

> Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below.

- **Severity:** medium. The commit outcome is the intended one: an override is not blocked. What is lost is the warning that GE-114-3 promises ("a warn-only message is emitted"), and with it any record of how far over the cap an overridden ticket is. Once the flag is set, the ticket can grow without any signal.
- **Status:** open, no AC.
- **Occurrences:** 2 DIAGraph tickets (`TICKET-20261022-AGT-300g-1-i`, `TICKET-20261103-A2A-100q-1`). Both reproduced on `8d76d670a`. · **First seen:** 2026-11-16 · **Last seen:** 2026-11-16
- **Where:** `templates/scripts/commit_guardian/hooks/check_ac_limits.py` (deployed as `.leafcutter/scripts/commit_guardian/hooks/check_ac_limits.py`), `_analyse_ticket()` and `_print_override_warning()`. The registration is `templates/scripts/commit_guardian/commit_guardian.json:1523-1536` (`check-ticket-ac-limits`). This is not the tree-limits checker of the same name, `scripts/commit_guardian/check_ac_limits.py`.

## The mechanism

1. **The override branch has no fallback.** At `check_ac_limits.py:394-406` it counts from the `## Agent Contracts` block when that block is a non-empty string (`if contracts_block:`, line 398). It counts the full body only when the block is absent or empty.
2. **The normal branch does have one.** The GE-114 H-2 "Gap 1" fix (`:431-432`) falls back to the fence-stripped full-body count when the block yields 0 ACs. The fix was added to the normal branch only.
3. **Generated tickets have exactly that shape.** `## Agent Contracts` holds `### Delivers To` / `### Expects From` contract bullets and no `- [ ] AC-N:` lines. The checklist sits under `## Acceptance Criteria`. So with the override set, `total_ac_count` is 0.
4. **The warning is then suppressed.** `_print_override_warning()` skips any ticket that is not over a limit (`:542-544`), so nothing is printed and the hook exits 0.
5. **A fixed warning would still be hidden.** It goes to stderr (`:548-553`). The registration has no `verbose: true`, and the DIAGraph `.pre-commit-config.yaml:564-567` has none either, so pre-commit drops the output of a passing hook. The commit step's `committed` answer carries no `hook_output` either (`templates/scripts/commit_changes.py:385`).

The unit tests cover only the v1-flat override shape, with no `## Agent Contracts` section (`unit_tests/commit_guardian/test_check_ac_count_limits.py:277`, `:677`). None covers the shape the generator writes.

## Seen

DIAGraph clone `srf-commit-clone`, 2026-11-16. Without the flag, `TICKET-20261022-AGT-300g-1-i.md` was refused with `total: 22 ACs (max 20)`. The it-po agent then set `ac_limit_override: true` and the hook went silent. Reproduced on current main with copies under `/tmp/claude-scratch/ki-acl/`. `HOOK_TEST_DIFF` lists absolute paths, which `project_root / path` keeps as they are:

```
$ HOOK_TEST_DIFF=.../override_paths.txt python3 templates/.../hooks/check_ac_limits.py
exit: 0                      # stdout 0 bytes, stderr 0 bytes
$ HOOK_TEST_DIFF=.../nooverride_paths.txt ...      # same ticket, flag removed
    total: 22 ACs (max 20) — this ticket is an epic in disguise
exit: 1
$ HOOK_TEST_DIFF=.../override_flat_paths.txt ...   # flag kept, Agent Contracts heading renamed
[check-ac-limits] WARNING (override active): ... exceeds AC limits (total: 22) but ac_limit_override: true — commit not blocked.
exit: 0
```

`TICKET-20261103-A2A-100q-1.md` (DIAGraph main, override set by it-po on 2026-11-04, 23 checklist lines) also gives `exit: 0` with no output.

## Fix direction

- In the override branch, use the same count as the normal branch: the Agent Contracts count, falling back to the fence-stripped full body when that count is 0. One shared helper keeps the two branches from drifting again.
- Add `verbose: true` to the `check-ticket-ac-limits` registration so the warning reaches a passing commit, as GE-122d-6 does for `check-identifier-uniqueness`.
- Add a test with a generator-shaped ticket: contracts present, no AC lines in them, 21 or more checklist lines elsewhere, and the override set.
