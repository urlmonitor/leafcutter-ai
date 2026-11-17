---
title: "Reference: Implementation .py in Scope — the Test Requirements signal"
description: "Normative rule for when a generated ticket carries a Test Requirements section: the implementation-.py-in-scope predicate, the per-entry OR signal, and where it is implemented (TKT-500f-6). Moved from ac-schema.md."
type: reference
status: active
created: 2026-10-14
last_updated: 2026-10-14
components:
  - ac_store
  - ac_driven_dev
related_docs:
  - docs/reference/ac-schema.md
  - scripts/ac_store/_gtfa_impl_py.py
  - templates/agents/ticket-supervisor.md
---

# Implementation `.py` in Scope — the Test Requirements signal

> **Parent document:** [ac-schema.md](ac-schema.md). The section below was moved here verbatim
> (ACD-2500c-3) to keep the parent under its length ratchet.

## Implementation `.py` in Scope — the Test Requirements signal (TKT-500f-6)

**This section is normative.** It is the single statement of the rule, and both
sides that apply it are kept in step against this text by SPEC PARITY — not by a
shared import. One side is Python (`scripts/ac_store/_gtfa_impl_py.py`), the
other is markdown prose (`templates/agents/ticket-supervisor.md`); there is no
portable code path across that boundary, so if you change the rule you must
change this section and BOTH sides in the same commit.

### The predicate

A `files_touched` entry is an **implementation `.py` in scope** when **all** of
the following hold:

1. it ends in `.py` (which also settles the `.yaml` / `.json` exclusion — a path
   cannot end in two extensions at once);
2. no directory component of it is `docs`;
3. no directory component of it is `tickets`;
4. its basename matches neither `test_*.py` nor `*_test.py`.

### The signal

Classification is **per entry**, and the section-required decision is a logical
**OR** over the entries — *any* one qualifying entry obliges the section,
regardless of how many documentation or configuration entries accompany it. It
is never a unanimity check: `all(...)` where `any(...)` was meant passes the
single-file case and the all-excluded case and fails only the mixed one.

- **At least one qualifying entry** → the generated ticket carries a
  `## Test Requirements` section, and every stub in it names the qualifying
  implementation files under `implementation_files`. Its presence is the
  authoritative signal that the test-writer phase is **required**.
- **Entries present, none qualifying** → no `## Test Requirements` section, and
  the omission is **silent**. It is the correct answer, not a degraded one; a
  warning on every docs/config-only ticket is how a warning channel becomes
  noise. Its absence is the authoritative signal that a test-writer skip is
  **legitimate**.
- **`files_touched` empty** → *no evidence either way*, not a No. The AC declared
  no edit surface the generator could derive anything from, so the decision falls
  back to the computed agent map's production-code classification (the signal
  that governed the section before this predicate existed). Reading an empty list
  as "no implementation file in scope" would strip the section from 769 of the
  1,100 coder-assigned records with no authored `test_spec` in the real store
  (measured 2026-09-21). An unnecessary section is noise; a silently withheld one
  skips test-writer, which is the strictly worse error.

An it-po-authored `test_spec` is an **independent** ground for the section and is
unaffected by this predicate (see `TKT-500g-1`); `test_required: false` outranks
both.

### Where it is implemented

`is_implementation_python_path` in `scripts/ac_store/_gtfa_impl_py.py` is the
**only** implementation of the predicate in the repository. Both AC-to-ticket
generators reach it: the direct path (`generate_ticket_from_ac.py`, via
`_gtfa_body` and `_gtfa_tests_section`) and the goal path
(`scripts/ac_store/epic_tickets.py`, which delegates to that same script as a
subprocess). Do not inline or duplicate it in either —
`unit_tests/ac_store/test_tkt_500f_6_iii_a.py` fails on a second implementation
as well as on none.
