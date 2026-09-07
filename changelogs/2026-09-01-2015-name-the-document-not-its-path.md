---
title: "Name the document, not its path"
date: "2026-09-01"
time: "20:15"
type: manual
components:
  - ticket_creation_pipeline
  - guardrail_engine
breaking: false
summary: "Two GE-123 records stopped declaring a live known-issues register as a file to modify — the last surviving symptom of the breakage that halted EPIC-SuppressionNarrowsNeverDisables. Adds TKT-600a-2, which specifies the durable generator rule, and corrects a TKT-500f-8-i clause that shipped code has contradicted since the edit-surface relationship filter landed."
description: "GE-123d-3 and GE-123d-4-i both resolved files_touched to [docs/known-issues/commit-guardian.md, templates/scripts/commit_guardian/check_secrets.py] — a live, cross-referenced document presented to a coder as a file to edit. This was one of the two original symptoms that stopped the 27-ticket epic; the other, bare directories, was fixed by TKT-600a-1. Nobody authored it wrongly: those records FENCE KI-CG-004 as out of scope, #657 correctly kept the doc_link at relationship related, and the harvester took the path out of the prose anyway because it has an extension and exists on disk. That residual is explicitly accepted in TKT-600a-1's 2026-09-01 criteria. The immediate fix is at the record: one it_requirements bullet in each now names the register rather than its path, keeping the KI id a reader needs. Measured before and after against the shipped _build_files_touched — both drop to [templates/scripts/commit_guardian/check_secrets.py], and a sweep of all 32 GE-123 records confirms zero bare directories, zero nonexistent paths, zero empty leaves and zero known-issues surfaces. The fence itself is untouched: it is load-bearing in four places per record (the related doc_link and its relevance text, the bullet, the notes block, and a test_spec entry asserting the two exemptions reach different verdicts) and is bidirectional, since the register names both ACs back. Only one path token on one of those four surfaces was removed, and the bullet now restates the related relationship in words. TKT-600a-2 (new, L2, draft) specifies the durable rule: a path a record's own doc_links declare at a non-edit-surface relationship is not harvested from that same record's prose. This is mechanical — it reads a relationship enum an author chose in a structured field, so there is no phrase to match and no intent to infer — which is what distinguishes it from the two approaches TKT-600a-1 records as rejected. Five scenarios, including two the authoring agent added on its own judgement: describes behaving like related, so the rule is 'outside the edit-surface set' rather than a string match, and a path declared at BOTH related and modifies, where the explicit edit-surface declaration wins. That second is a fork an implementer meets on day one and would otherwise decide by accident. It is placed as an L2 child of TKT-600a rather than an L3, because derive_parent_id makes 'L3' and 'child of TKT-600a' mutually exclusive and the only L3 slot sits under TKT-600a-1, which is work_status: done — hanging a todo child there would recreate the done-composite-with-unfinished-child shape CLAUDE.md names as the dominant phantom-done vector. Separately, TKT-500f-8-i's second scenario said files_touched contains 'the AC's doc_links paths', unqualified, written before _EDIT_SURFACE_RELATIONSHIPS existed; read strictly it requires informational links to be included, so that approved and done record has been literally false in that clause ever since the filter landed. Demonstrable on itself: it declares four doc_links and only its constrains and specifies entries appear. Narrowed to 'edit-surface doc_links paths' with the five relationships named. A wording correction, not a requirement change — no behaviour is asked to change, no test moves, covering tests green before and after."
---

## Entry

Two `GE-123` records resolved `files_touched` to a **live document**:

```
GE-123d-3     ['docs/known-issues/commit-guardian.md',
               'templates/scripts/commit_guardian/check_secrets.py']
```

This was the last surviving symptom of the breakage that halted `EPIC-SuppressionNarrowsNeverDisables`. The other — bare directories — was fixed by `TKT-600a-1`.

**Nobody authored it wrongly.** Those records *fence* KI-CG-004 as out of scope, and #657 correctly kept the `doc_link` at `relationship: related`. The harvester took the path out of the prose anyway, because it has an extension and exists on disk. `TKT-600a-1`'s criteria explicitly accept that residual.

The immediate fix is at the record: name the register, not its path.

```
GE-123d-3     ['templates/scripts/commit_guardian/check_secrets.py']
GE-123d-4-i   ['templates/scripts/commit_guardian/check_secrets.py']
```

Across all 32 records: zero bare directories, zero nonexistent paths, zero empty leaves, **zero known-issues surfaces**.

### The fence survives

It is load-bearing in four places per record — the `related` link and its relevance text, the bullet, the `notes` block, and a `test_spec` entry asserting the two exemptions reach *different* verdicts — and it is bidirectional: the register names both ACs back. One path token on one of those four surfaces was removed, and the bullet now restates the relationship in words.

That the register is genuinely live and cross-referenced is the argument, not a complication: it is exactly why presenting it as editable was the defect.

### TKT-600a-2 — the durable rule

> A path a record's own `doc_links` declare at a non-edit-surface relationship is not harvested from that same record's prose.

Mechanical: it reads a relationship enum an author chose in a structured field. No phrase to match, no intent to infer — which is what separates it from the two approaches `TKT-600a-1` records as rejected.

Five scenarios. Two of them came from the authoring agent's own judgement rather than the brief: `describes` behaving like `related` (so the rule is *outside the edit-surface set*, not a string match), and a path declared at **both** `related` and `modifies`, where the explicit edit-surface declaration wins. The second is a fork an implementer meets on day one and would otherwise decide by accident.

Placed as an **L2** child of `TKT-600a`, not an L3. `derive_parent_id` makes "L3" and "child of `TKT-600a`" mutually exclusive, and the only L3 slot sits under `TKT-600a-1`, which is `work_status: done` — a `todo` child there recreates the done-composite-with-unfinished-child shape CLAUDE.md names as the dominant phantom-done vector.

### TKT-500f-8-i said something shipped code contradicts

Its second scenario read "files_touched still contains the AC's **doc_links paths**" — unqualified, written before `_EDIT_SURFACE_RELATIONSHIPS`. Read strictly, that requires informational links to be included.

Demonstrable on the record itself. It declares four `doc_links`:

```
files_touched -> [docs/reference/ac-schema.md,
                  scripts/ac_store/generate_ticket_from_ac.py]
```

Present: `constrains`, `specifies`. Absent: the two `describes`. **The code is right and the sentence was wrong.**

Narrowed to "edit-surface doc_links paths", naming the five relationships. A wording correction, not a requirement change — no behaviour changes, no test moves, covering tests green before and after.
