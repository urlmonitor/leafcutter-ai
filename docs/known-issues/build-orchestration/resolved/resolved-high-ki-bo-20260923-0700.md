---
title: "KI-BO-20260923-0700 — the docs-only guard discards out_of_scope, so a documentation ticket on a multi-ticket branch can never be marked done"
description: "KI-BO-20260923-0700 — the docs-only guard discards out_of_scope, so a documentation ticket on a multi-ticket branch can never be marked done"
type: reference
category: reference
status: active
created: '2026-09-23'
last_updated: '2026-09-23'
components:
  - build_orchestration
  - commit_guardian
related_docs:
  - docs/known-issues/build-orchestration.md
---

# KI-BO-20260923-0700 — the docs-only guard discards `out_of_scope`, so a documentation ticket on a multi-ticket branch can never be marked done

- **Severity:** high — it had no workaround that was both honest and effective. The hook's
  own printed remedy could not be followed.
- **Status:** resolved — see `BP-1100e-1-viii` (the fix), landed 2026-09-23
- **Occurrences:** 1 observed (BO-400e-5, 2026-09-23), but it applies to every docs-only
  ticket in every multi-ticket epic.
- **First seen:** 2026-09-23 · **Last seen:** 2026-09-23
- **Where:** `scripts/commit_guardian/hooks/check_files_touched_reconciliation.py`, the
  declared-scope computation (`is_docs_only_or_config_only_ticket` branch, ~line 517).

**Symptom.** Committing the `status: done` flip for a documentation-only ticket fails:

```
[check-predone-scope] ERROR: source files changed but not declared in files_touched or out_of_scope
  Ticket : .../05_TICKET-20260914-BO-400e-5.md
  Undeclared source files:
    - scripts/set_ticket_status.py
    - templates/workflows-js/build-feature.js
    ... 22 more ...
  Fix: add the above files to files_touched (or out_of_scope if
  intentionally excluded) in the ticket frontmatter before marking done.
```

All 24 files were **already** listed in that ticket's `out_of_scope`. The hook's own parser
reads them correctly — `_parse_yaml_list_field(frontmatter, "out_of_scope")` returns 25
entries when run against the staged blob. They are discarded a few lines later:

```python
if is_docs_only_or_config_only_ticket(files_touched):
    return set()

return {_normalise_path(p) for p in files_touched + out_of_scope}
```

The early return happens **before** `out_of_scope` is unioned in. So for any ticket whose
`files_touched` is entirely non-source, the declared scope is the empty set and every source
file changed anywhere in the branch range is reported undeclared.

**Why it matters.** The remedy the hook prints is the one thing that cannot work. Adding the
files to `out_of_scope` is exactly what was already done; adding them to `files_touched`
would make the ticket claim it touched source it did not touch, which is a false record of
the kind this component exists to prevent — and it would also flip the ticket out of
docs-only classification, which is itself a lie about the change. The only remaining routes
are to skip the hook or to leave the ticket unclosable.

This is not an edge case. It fires for **every** documentation ticket in **every** epic that
also contains implementation tickets, because the changed-file set is computed over the
branch range rather than per-commit. A docs ticket is almost always last in such an epic, so
it meets the whole branch's accumulated source diff.

**Distinct from** the sibling assumption already noted elsewhere in this register, that
`check-predone-scope` assumes one commit carries one ticket. That assumption is what makes
the branch-range diff land on a docs ticket at all; this entry is about the separate fact
that `out_of_scope` — the field provided precisely to answer "not mine" — is unreachable for
the tickets that most need it.

**Evidence it is the guard and not the ticket.** `git show 3d924ec4 --stat` for BO-400e-5's
implementation commit lists four files, all `.md`: the diagram, the component doc, a
known-issue, and the ticket itself. Zero source files. The ticket's declaration is accurate;
the hook's verdict is not.

**Fix (landed 2026-09-23, `BP-1100e-1-viii`).** The docs-only branch now returns the
normalised `out_of_scope` set instead of a bare empty one:

```python
if is_docs_only_or_config_only_ticket(files_touched):
    return {_normalise_path(p) for p in out_of_scope}
```

This is a narrowing of the guard, not a removal, and `BP-1100e-1-iii` is preserved
unchanged in effect. A docs-only ticket that declares **nothing** out of scope still yields
an empty declared scope, so it still cannot silently absorb source changes it never
mentioned — which is the case that guard was written for. A source file named in neither
list is still flagged.

Covered by `unit_tests/commit_guardian/test_predone_scope_docs_only_out_of_scope.py`, three
cases: the one that was broken, the one that must stay strict, and `BP-1100e-1-iii`'s own
case. The middle one is load-bearing — a "fix" that simply deleted the docs-only branch
would satisfy the first test and still be wrong. Red baseline before the fix: 1 of 3
failing, and exactly the broken case. Full commit_guardian suite after: 1515 passed.

**Historical note on the workaround.** Before the fix, the only routes were
`SKIP=check-predone-scope` with the ticket's zero-source diff quoted as evidence, or listing
source files the ticket never touched. It was skipped twice on BO-400e-5, with the reason
recorded in both commit messages. Do not reintroduce the `files_touched` padding route: a
false record is exactly what this component exists to prevent.

**Pattern:** a guard whose early return drops the very field its failure message tells you
to use — the check and its own advice disagree, and following the advice changes nothing.
