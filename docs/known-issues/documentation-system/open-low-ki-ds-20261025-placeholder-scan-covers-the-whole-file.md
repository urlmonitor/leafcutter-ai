---
title: "KI-DS-20261025-placeholder-scan-covers-the-whole-file — documentation-verifier's 6c token scan reads the whole required doc, so brace syntax that was already in the file before the ticket blocks the ticket"
description: "medium — Step 6c runs grep -onP over the entire file, not over the lines the ticket added. Ticket GE-124g-1 edited docs/reference/ac-schema.md and was blocked on {word}, {slot_name} and {slot} at lines 73, 332 and 352, none of which it wrote. The ticket author reworded pre-existing text to get past it. 6a and 6b scan the whole file the same way."
type: reference
category: reference
status: active
created: '2026-10-25'
last_updated: '2026-10-25'
components:
  - documentation_system
related_docs:
  - docs/known-issues/documentation-system.md
  - docs/known-issues/README.md
  - docs/known-issues/documentation-system/open-low-ki-ds-20261014-token-scan-flags-f-string-fields-in-source-targets.md
---

# KI-DS-20261025-placeholder-scan-covers-the-whole-file — the verifier blames a ticket for text it did not write

> One known issue. Index: [documentation-system.md](../documentation-system.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. The verifier fails closed, so nothing wrong lands. But it blocks a ticket on
  someone else's text, and the cheapest way past is to edit lines outside the ticket's scope.
- **Status:** open, no AC.
- **Occurrences:** 1, ticket GE-124g-1, GE-124 epic drive, 2026-10-25.
- **First seen:** 2026-10-25 · **Last seen:** 2026-10-25
- **Where:** `templates/agents/documentation-verifier.md` on `origin/main` `0087a1700`:
  - `:455-460` (Step 6c). The command is
    `grep -onP '(?<!\$)\{[A-Za-z_][A-Za-z0-9_]*\}' <absolute_file_path>`. It runs on the whole
    file.
  - `:379` (6a, the helper-script scan) and `:422` (6b, the TBD grep) also take the whole file.

## Symptom

GE-124g-1 named `docs/reference/ac-schema.md` as its required doc and edited part of it.
documentation-verifier blocked on unfilled single-identifier placeholders (6c) at lines 73, 332 and
352: `{word}`, `{slot_name}` and `{slot}`. All three were already in the file before the ticket, as
prose describing slot syntax.

## Mechanism

The verifier's question is "did this ticket leave placeholder content in the doc it was asked to
write?" Step 6 answers a different one: "does this file contain anything shaped like a
placeholder?" For a new doc the two are the same. For an existing doc, every past author's text is
in scope, so a long reference doc that discusses brace syntax fails every ticket that touches it.

## Workaround used

The pre-existing lines were reworded so they no longer matched. That changed text outside the
ticket's own edit to satisfy a gate.

## Fix direction

1. **Scan only the lines the ticket added.** Take them from
   `git diff -U0 <base>...HEAD -- <file>` (the `+` lines, with their new line numbers) and run 6c on
   those.
2. **Fail closed to a whole-file scan** when no base can be resolved, and record in the completion
   manifest which mode ran.
3. Apply the same scoping to 6a and 6b, which have the same shape.

Add a regression case: a doc whose HEAD version already holds `{slot}`, a ticket diff that adds a
clean paragraph, assert 6c passes; and a diff that adds `{slot}`, assert it blocks.

**Related.** KI-DS-20261014-token-scan-flags-f-string-fields-in-source-targets is the same scan run
on the wrong kind of file; this one is the right kind of file with the wrong extent.

**Pattern:** a per-change gate that measures the whole artifact, so it charges each change for the
artifact's history.
