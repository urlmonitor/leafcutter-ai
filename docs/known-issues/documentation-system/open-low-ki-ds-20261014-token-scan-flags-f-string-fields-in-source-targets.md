---
title: "KI-DS-20261014-token-scan-flags-f-string-fields-in-source-targets — documentation-verifier runs its unfilled-token check on every required path, so a `.py` target's f-string fields block the phase as placeholders"
description: "medium — documentation-verifier Step 6c greps every required doc for a bare `{identifier}` whatever the file extension. When a ticket names a Python source file as the required doc, its f-string fields ({exc}, {jsonl_path}, ...) are reported as unfilled template tokens and the phase blocks. Nothing rejects a non-doc target before the scan runs."
type: reference
category: reference
status: active
created: '2026-10-14'
last_updated: '2026-10-14'
components:
  - documentation_system
related_docs:
  - docs/known-issues/documentation-system.md
  - docs/known-issues/README.md
  - docs/known-issues/ac-driven-dev/open-low-ki-acd-20260925-contract-target-is-parent-link.md
  - docs/known-issues/build-pipeline/open-high-ki-bp-20260831-generator-emits-unparseable-doc-contract.md
---

# KI-DS-20261014-token-scan-flags-f-string-fields-in-source-targets — documentation-verifier treats f-string fields as unfilled placeholders

> One known issue. Index: [documentation-system.md](../documentation-system.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium. The verifier fails closed, so nothing wrong lands. But the blocker names
  the wrong cause (placeholders in a doc), and a ticket needs a hand fix before the phase can pass.
- **Status:** open — no AC.
- **Occurrences:** 1
- **First seen:** 2026-10-12 · **Last seen:** 2026-10-12
- **Where:** `templates/agents/documentation-verifier.md` on `origin/main` `435c11395`:
  - `:149-166` (Step 2). Any second pipe-delimited field becomes a `required_docs` entry. The
    path's extension is never checked.
  - `:366-370` (Step 6). All four placeholder sub-checks run on every `required_docs` path that
    is in the diff.
  - `:455-461` (Step 6c). The pattern is `grep -onP '(?<!\$)\{[A-Za-z_][A-Za-z0-9_]*\}'`. A
    Python f-string field such as `{exc}` has exactly this shape.
  - `:491-506`. The template's own "Known residual" note admits that a bare identifier still
    matches when it names a code construct. It only considers Markdown diagrams, not a source
    file named as the target.

## Symptom

On 2026-10-12, ticket 02 of `EPIC-OneDurableLogRootForEveryWorkspace` (`INF-500d-4-i`)
named `templates/scripts/feedback/submit_feedback.py` as its documentation-expert target.
documentation-verifier blocked with:

```text
templates/scripts/feedback/submit_feedback.py: unfilled single-identifier {token}-style
placeholders (6c) at lines 153, 154, 155, 343, 398, 420, 423, 425 ({checked_path}, {exc},
{jsonl_path}, {ts_epoch}, {sidecar_path}).
```

Every hit is an f-string field in working code. The blocker comment is kept in
`tickets/00_inbox/epics/EPIC-OneDurableLogRootForEveryWorkspace/02_TICKET-20261009-INF-500d-4-i.md`,
2026-10-12 17:31. The contract was corrected by hand to name
`docs/architecture/feedback-lifecycle.md` (`ddae96e40`), and the re-run passed.

## Mechanism

6c is a text-shape heuristic tuned for Markdown and template output. In a `.py`, `.js` or
`.ts` file the same shape is normal syntax: f-strings, `str.format` fields, and JS object
shorthand. The verifier has no notion of which files it should be reading as docs. It trusts
the contract, and the contract can name a source file
(KI-ACD-20260925-contract-target-is-parent-link, Occurrence 2).

## Consequence

The blocker reads "placeholder content in required documentation". That points the next agent
at documentation-expert to "fill in" tokens in working code, not at the mis-wired contract. On
this occurrence the verifier's own remediation text guessed the real cause, but the template
does not tell it to.

## Fix direction

Either of these, with the first preferred:

1. **Reject a non-doc target up front.** In Step 2, block with a "contract names a non-doc
   target" reason when a `target_path` is not a documentation file (for example, not `.md` /
   `.mdx`, or outside the docs roots). That names the real defect.
2. **Skip 6c for non-doc extensions.** Keep 6a, 6b and 6d, and record that 6c was skipped and
   why in the completion manifest.

Add a regression case that feeds a `.py` file with f-strings as a required doc and asserts the
verdict names the target, not placeholders.

**Related.** KI-ACD-20260925-contract-target-is-parent-link (the generator picks the source
file). KI-BP-20260831-generator-emits-unparseable-doc-contract, point 2 (source files as doc
targets).

**Pattern:** a heuristic tuned for one file type, run on whatever path an upstream producer
names, so the producer's defect is reported as a content defect in the wrong file.
