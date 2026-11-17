---
title: "KI-ACD-20261116-generator-checklists-given-and-when-preconditions — the ticket generator turns every And line into a - [ ] AC-N: item, including Given/When preconditions and lower-case 'and' wrap lines, so multi-scenario ACs trip the 20-AC ticket cap"
description: "medium — _criteria_checkboxes matches any line starting with Then or And, case-insensitively, and does not track which keyword the And continues. Given-And and When-And preconditions, and wrapped continuation lines that start with 'and', each become a checklist item. Generated tickets from multi-scenario ACs then exceed check-ticket-ac-limits' 20-total cap on outcomes that are really under it."
type: reference
category: reference
status: active
created: '2026-11-16'
last_updated: '2026-11-16'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
  - docs/known-issues/ac-driven-dev/open-low-ki-acd-016.md
  - docs/known-issues/commit-guardian/open-low-ki-cg-20261116-ticket-ac-limits-override-passes-silently.md
---

# KI-ACD-20261116-generator-checklists-given-and-when-preconditions — preconditions become checklist items

> Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below.

- **Severity:** medium. It is loud, not silent: a correctly sized ticket is refused at commit, and the only ways through are a split or an `ac_limit_override` that needs IT PO review. Both DIAGraph cases chose the override, and the override then goes silent (KI-CG-20261116). The checklist also presents preconditions as outcomes to be ticked off.
- **Status:** open, no AC. TKT-500f-11 requires only that the checklist text is "derived from the source AC's criteria", so it neither demands nor forbids this.
- **Occurrences:** 2 DIAGraph tickets: `TICKET-20261103-A2A-100q-1` (23 lines, 18 outcomes by its 2026-11-04 IT PO review) and `TICKET-20261022-AGT-300g-1-i` (22 lines, 15 outcomes; 2026-11-16). · **First seen:** 2026-11-04 · **Last seen:** 2026-11-16
- **Where:** `scripts/ac_store/_gtfa_body.py:188-223`, `_criteria_checkboxes()`, called from `_body_header_lines()` at `:266` and re-exported by `scripts/ac_store/generate_ticket_from_ac.py:383`. It is deployed through `AC_STORE_DEPLOY_MAP` as `.leafcutter/scripts/ac_store/_gtfa_body.py`; the DIAGraph copy is identical to main. There is no `templates/` copy.

## The mechanism

`_gtfa_body.py:211` is `re.match(r"^(Then|And)\s+(.*)", stripped, re.IGNORECASE)`, applied to each physical line on its own. It has two faults:

1. **No keyword state.** An `And` after a `Given` or a `When` matches just like an `And` after a `Then`. Each scenario's preconditions are added to the count.
2. **Case-insensitive.** A wrapped continuation line that starts with lower-case `and ...` becomes its own item. Examples are A2A-100q-1 `AC-7: GPCH code` and `AC-10: end offset 28 ...`.

The ticket hook then counts those lines. The `## Agent Contracts` block the generator writes holds no `- [ ] AC-N:` lines, so `check_ac_limits.py:431-432` falls back to the full ticket body (fenced blocks stripped) and counts the checklist under `## Acceptance Criteria`. Against `_MAX_ACS_TOTAL = 20` (`:52`), every precondition line counts as an AC.

This is a sibling of KI-ACD-016: the same function also keeps only the first physical line of a clause. AGT-300g-1-i shows both faults, for example `AC-22: the response follows the existing A2A error state for an`.

## Seen

Current main `8d76d670a`, dry run against the real DIAGraph AC. The run writes nothing:

```
$ python3 scripts/ac_store/generate_ticket_from_ac.py --ac AGT-300g-1-i \
    --ac-root /home/henzeh/projects/worktrees/srf-commit-clone/docs/acceptance-criteria \
    --tickets-root /tmp/claude-scratch/ki-acl/gen-tickets --dry-run > .../gen_dryrun.md
exit: 0
$ grep -c "^- \[ \] AC-" .../gen_dryrun.md
22
```

The AC has 5 scenarios. AC-1 to AC-3 and AC-11 to AC-13 come from Given-And lines, and AC-4 from a When-And line. That leaves 15 outcome clauses, under the cap, yet the hook refused the ticket with `total: 22 ACs (max 20)`. A minimal probe gives 5 items for 2 outcomes:

```
Given a precondition / And a second precondition / When an action happens / And a second action /
Then outcome one / and its wrapped continuation / And outcome two
-> AC-1: a second precondition, AC-2: a second action, AC-3: outcome one,
   AC-4: its wrapped continuation, AC-5: outcome two
```

## Fix direction

- Track the governing keyword. Emit a checklist item for `Then` and for `And`/`But` lines that follow a `Then`, and reset at each `Given`/`When`. Match the keywords case-sensitively, so a wrapped lower-case `and` stays part of its clause, and join continuation lines into the clause (this also closes KI-ACD-016).
- Or drop the checklist and count Then-clauses from the Gherkin block. That is KI-ACD-016's cheaper option, but `ac-validator` and TKT-500f-11 rely on the `- [ ] AC-N:` lines, so they would need to change too.
- After the fix, regenerate or recount the DIAGraph tickets that carry an override. They may no longer need it.
