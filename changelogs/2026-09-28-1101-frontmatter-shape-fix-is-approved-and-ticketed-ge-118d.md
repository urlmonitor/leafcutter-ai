---
title: "Frontmatter path-shape fix (GE-118d) is now approved and ticketed — still no code changed"
date: "2026-09-28"
time: "11:01"
type: manual
components:
  - commit_guardian
  - knowledge_management
summary: "Approved the already-specified fix for a known blocker and generated its implementation ticket, so work can start — the underlying bug is still live in both places it occurs."
description: "Third entry in the GE-118d/KM-KGS-100d-3 sequence (after the 2026-09-21 spec and decision-closing entries, commits cbdbfb99 and de442295). This commit flips all seven affected ACs (GE-118d, GE-118d-1, GE-118d-2, GE-118e, GE-118f, KM-KGS-100d-3, KM-KGS-100d-3-i) from readiness: draft to readiness: approved — required because the AC scanner only surfaces approved records — and generates TICKET-20260928-GE-118d.md from GE-118d via generate_ticket_from_ac.py (ADR-012), with the generator's own implemented_by back-reference on GE-118d. work_status stays todo on all seven; no code changed." 
commits:
  - 83c664a2
breaking: false
---

## Entry

### What this is

The next step after the two 2026-09-21 entries for `KI-CG-008` (the spec, commit
`cbdbfb99`, and the decision-closing follow-up, commit `de442295`). Those left the
fix fully specified but not yet buildable through the normal scanner-driven paths.
This commit removes that gate and starts the build queue. **No code changed** — the
crash in `frontmatter_validators.py` and the silent drop in `knowledge_query.py` are
both still live.

### Seven ACs move from draft to approved

`GE-118d`, `GE-118d-1`, `GE-118d-2`, `GE-118e`, `GE-118f`, `KM-KGS-100d-3`, and
`KM-KGS-100d-3-i` were authored `readiness: draft` and stayed there through last
week's priority decision. This is not cosmetic: `scan_ac_store.py` surfaces only
`approved` records, so while these sat at `draft` they were invisible to every
scanner-driven path — direct generation with `--ac` worked, nothing else did.
Approval is the user's own gate, taken now. `work_status` stays `todo` on all
seven: approved means "build this," not "built."

### A ticket, generated the canonical way

`TICKET-20260928-GE-118d.md` was produced by
`scripts/ac_store/generate_ticket_from_ac.py --ac GE-118d --location-kind standalone`
— the AC-first path per ADR-012, not hand-written. `--verify` passed all seven
readiness checks before generation (criteria present, assigned agent, authored
test_spec, non-empty Test Requirements, it_requirements present, `files_touched`
resolved from `doc_links`, readiness approved). The generator also wrote its own
`implemented_by` back-reference onto `GE-118d`, naming the new ticket.

### Why this path, not the fast lane

The fast lane cannot currently claim an AC: its claim phase dispatches a
repository-mutating command, and two properly-scoped agents have declined that
dispatch on role grounds. That gap is tracked separately as
`KI-BO-20260901-1620` item 4 and is not a defect in these ACs — it is why this
work went through `/build-ac` → `/build-feature` instead.

### Why it matters that this is still not a fix

Nothing behavioral changed. The crash is still live in `frontmatter_validators.py`
and the silent drop is still live in `knowledge_query.py`. What changed is that the
work is now approved and has a ticket, so implementation can begin.
