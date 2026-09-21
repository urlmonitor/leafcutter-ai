---
title: "KI-ACD-016 — Generated tickets carry AC checklist items truncated mid-clause"
description: "KI-ACD-016 — Generated tickets carry AC checklist items truncated mid-clause"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
---

# KI-ACD-016 — Generated tickets carry AC checklist items truncated mid-clause

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** low
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/ac_store/generate_ticket_from_ac.py` — the `- [ ] AC-N:` checklist
  rendering

**Symptom.** Below the full ` ```gherkin ` block, each generated ticket repeats the
criteria as a checklist built by splitting the Gherkin on `And` and taking the first
physical line of each clause. Because the criteria are wrapped block scalars, every item
ends mid-sentence:

```markdown
- [ ] AC-1: it creates a real second working copy of the repository, stages real files in it, and
- [ ] AC-3: the source tree is not on the import path of the process under test, so a check that can
```

**Impact is bounded but real.** No information is lost — the complete criteria sit in the
Gherkin block directly above, and that is what `ac-validator` reads. The risk is an agent
or reviewer working from the checklist, which reads as a list of half-requirements. AC-3
above inverts especially badly: truncated, it stops immediately before the condition that
gives it meaning.

**Fix direction.** Join the wrapped continuation lines before splitting, or drop the
checklist entirely and let the Gherkin block stand alone. The checklist duplicates content
it cannot represent faithfully, so removing it is the cheaper correct answer.

---
