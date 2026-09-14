---
title: "Known issues — ac-driven-dev (from 2026-09-14)"
description: "Continuation register for the ac-driven-dev component: AC selection and prioritisation, ticket generation from AC records, and the traceability block the downstream gates read. Opened because ac-driven-dev.md reached 1,891 lines against a 300-line limit and the doc-length ratchet correctly refuses any further growth, closing the record-on-sight path for that component. New entries land here; the older register stays frozen until it is split."
type: reference
category: reference
status: active
created: 2026-09-14
last_updated: 2026-09-14
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/architecture/components/ac-driven-dev.md
  - docs/known-issues/README.md
---

# Known issues — ac-driven-dev (from 2026-09-14)

Observed defects in this component that are **not yet fixed**, recorded from 2026-09-14
onward. Entries filed before that date live in
[ac-driven-dev.md](ac-driven-dev.md) — **read both**; they are one register split across
two files, not two registers.

## Why this file exists

`ac-driven-dev.md` stands at 1,891 lines against a 300-line limit. On 2026-09-14 the
`check-doc-length` gate moved from `warn` to `block`, ratcheting exactly as
`check-file-size` does for code: a doc may not cross its limit, and a doc already over may
not grow. That is the right rule and it was the right change — under `warn` the gate always
exited 0, which is how three registers reached ~4,500 lines without one commit being
stopped.

It has one consequence nobody has dealt with yet, and it is worth stating plainly rather
than working around silently: **an append-only defect register cannot be appended to once
it is over.** The register's own stated purpose is that "a defect noticed in passing can be
recorded in seconds"; for this component and two others, that path is now closed. A
compliant split of 1,891 lines across 29 entries needs roughly seven files, because a new
file over 300 lines would itself be refused for crossing.

This file is the minimum honest response: a dated continuation that is itself well within
the limit, cross-linked from the excluded `README.md` index, establishing the split
boundary the gate is pushing toward. It is not a bypass — nothing was deleted, nothing was
exempted, and the old register was not touched. The proper split of
`ac-driven-dev.md` remains outstanding.

---

### KI-ACD-20260914-generated-implemented-by-records-the-staging-path — the generator has a flag whose whole purpose is to name the ticket's final location, and the one field that stores a durable path ignores it

- **Severity:** medium. Nothing is corrupted and the ticket itself is correct. The cost is that `implemented_by` — the field the coverage resolver reads — is written pointing at a path that will never exist, and nothing in the repo notices. It is a phantom citation manufactured by the tooling whose purpose is to prevent phantom-done.
- **Status:** open — **confirmed by observation**, 2026-09-14.
- **Occurrences:** 9 of 9 epic-member tickets generated for `EPIC-FilesStayWorkable`. Structural: every epic-member ticket, every time.
- **Where:** `scripts/ac_store/generate_ticket_from_ac.py` lines 3834–3847.

**Symptom.** Nine tickets were generated into an epic folder and renamed to the epic
convention (`01_TICKET-…`, `02_TICKET-…`). Every source AC came back carrying:

```yaml
implemented_by:
- tickets/00_inbox/epics/EPIC-FilesStayWorkable/TICKET-20260914-GE-127d-1.md
```

No such file exists. The file on disk is `01_TICKET-20260914-GE-127d-1.md`.

**Mechanism.** The back-reference is derived from the path actually written:

```python
ticket_path = tickets_root / _ticket_filename(ac_id)
relative_ticket_path = str(ticket_path.relative_to(worktree)) ...
_write_implemented_by(ac_path, relative_ticket_path, ac_id, worktree=worktree)
```

`_ticket_filename(ac_id)` has no notion of ordinal prefixes, because at write time there is
no epic order to know. That part is reasonable. What makes this a defect rather than a
limitation is that **the generator already accepts the right answer and does not use it
here.** `--resolved-destination` exists precisely to carry *"the ticket's FINAL
repo-relative location, distinct from `--tickets-root` which may be a staging root a later
step moves the file out of"* — its own help text. It is consumed for phase-deferral
classification (`_location_kind_for_destination`) and nowhere else. The one field that
persists a path beyond this process reads `tickets_root` instead.

**Why nothing catches it, which is the worse half.** The AC hooks read the git index, and a
freshly generated ticket and its AC are both untracked at generation time, so their silence
proves nothing — the same blind spot as *"AC-store commits — stage the parent alongside the
child"* in `CLAUDE.md`. `validate_ac_schema.py` checks that `implemented_by` is a list of
strings, not that the strings resolve. So the store passes every gate while holding nine
citations to files that were never created.

**Workaround in use.** After renaming into epic order, repoint every entry by hand and
confirm with a store-wide grep for the unprefixed form. Done for all nine in the
`EPIC-FilesStayWorkable` scaffold.

**Fix direction.**
- Prefer `resolved_destination` in the back-reference call, falling back to `ticket_path`
  only when it was not supplied. The value is already in scope and already validated
  against `--location-kind`.
- Consider requiring `--resolved-destination` for `--location-kind epic_member` — an epic
  member's final name is never the one the generator picks.
- Add a store-level check that every `implemented_by` path resolves. That is the general
  defence and would have caught this class on the first run. It must read the working tree,
  not the index, or it inherits the blind spot above.

**Related.** `KI-ACD-20260831-agent-contracts-block-not-pipe-delimited` and
`KI-ACD-20260914-0657` in [ac-driven-dev.md](ac-driven-dev.md) — same family: generated
content a downstream reader cannot use.
`KI-TQ-20260914-test-fixtures-hand-enumerate-their-production-dependencies` in
[testing-quality.md](testing-quality.md) — same session, same shape: a derived value nothing
checks against reality.

**Pattern:** a tool that is handed the correct value, uses it for a secondary purpose, and
derives the primary one from a path it happens to be holding.
