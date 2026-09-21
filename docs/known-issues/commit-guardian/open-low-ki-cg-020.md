---
title: "KI-CG-020 — hook registration has a fourth leg nobody documents: a hook absent from `blocking_hook_ids` is skipped by the autofix loop"
description: "KI-CG-020 — hook registration has a fourth leg nobody documents: a hook absent from `blocking_hook_ids` is skipped by the autofix loop"
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

# KI-CG-020 — hook registration has a fourth leg nobody documents: a hook absent from `blocking_hook_ids` is skipped by the autofix loop

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/scripts/precommit-autofix.json` `blocking_hook_ids`;
  `templates/skills/precommit-autofix/SKILL.md` Step 4; `templates/skills/create-hook/SKILL.md`

**Symptom.** A hook can be correctly registered by every documented step — script written,
config key added, `hooks_manifest` entry added, row added to the hook documentation index —
and still be ignored by the autofix loop, because a **fourth** registration surface exists
that the `create-hook` procedure does not mention.

`templates/scripts/precommit-autofix.json` carries a closed allowlist:

```json
"blocking_hook_ids": [
  "check-complexity",
  "check-docstrings",
  "check-exception-handling",
  "check-file-size",
  "check-ac-schema",
  "check-ac-limits",
  "check-contract-shrinking"
]
```

`precommit-autofix/SKILL.md` Step 4 is explicit about the consequence: if a failing hook
does not appear in `blocking_hook_ids`, *"the hook is non-gating — skip it entirely, do not
dispatch any fixer."*

**Why this is a registration gap rather than a configuration choice.** The allowlist is a
reasonable design — not every hook should have a fixer dispatched at it. The defect is that
it is a **fourth leg of registration documented nowhere in the procedure that exists to
enumerate the legs.** `create-hook` codifies three-way registration (script + guardian
config + doc index) and `check_hook_parity` enforces consistency across those three. Neither
knows this file exists. So the natural failure is silent: an author follows the documented
procedure completely, `check_hook_parity` passes, and the hook lands outside the loop with
nothing reporting the omission.

**Evidence.** Found on 2026-08-25 while reviewing `BP-1100b-5`, an approved AC specifying a
new staged-hunk commit-guardian hook (`check_presence_only_assertions.py`). Its
`it_requirements` spell out three-way registration in detail — including an explicit
`n_location_rule: "2"` constraint warning that a config key without a `hooks_manifest` entry
"is a no-op that reads as shipped". Neither that record's `it_requirements`, `constraints`
nor `doc_links` mentions `precommit-autofix.json`. As specified, the AC ships a gate the
autofix loop is configured to ignore — and the record's own coverage would not catch it,
because all twelve of its test descriptors exercise the hook directly.

The irony is worth recording: `BP-1100b-5` exists to stop tests that look like proof but
are not, and it carries a registration spec that looks complete but is not, for the same
structural reason — an enumeration everyone trusts that is missing an item.

**Scope.** The 7 hooks on the allowlist are unaffected. The exposure is every hook added
since the allowlist was closed and every hook added from here, and the symptom is not a
failure but a *reduced* one: the hook still blocks the commit, it simply gets no autofix
attempt, so the effect is friction rather than a false pass. That is why this is `medium`
and not `high` — but it is the kind of gap that is only ever noticed by someone reading the
autofix config for an unrelated reason.

**Fix direction.**

- Add the fourth leg to `create-hook`'s procedure, with the decision made explicit: every
  new hook is either added to `blocking_hook_ids` or is deliberately non-gating, and the
  author records which. An omission by default is the current behaviour and is the thing to
  remove.
- Extend `check_hook_parity` to cover it, so a hook present in `hooks_manifest` and absent
  from `blocking_hook_ids` is reported — as a warning naming the deliberate-exclusion route,
  not as a hard failure, since exclusion is legitimate.
- Amend `BP-1100b-5` when it is built, or accept the gap knowingly for that hook.

---
