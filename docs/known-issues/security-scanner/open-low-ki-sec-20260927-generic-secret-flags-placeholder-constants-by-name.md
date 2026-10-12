---
title: "KI-SEC-20260927-generic-secret-flags-placeholder-constants-by-name — GENERIC_SECRET fires on any constant whose name contains TOKEN and whose value is a quoted string, including a parenthesised placeholder, and fires again on ticket prose that quotes the line"
description: "medium — no secret can slip past because of this; it costs a commit round-trip per occurrence. The only remedy the hook offers is a .security-allowlist entry keyed on file and line number, which breaks as soon as the file moves. Observed twice on 2026-09-27 during the GE-120f-1 family commit."
type: reference
category: reference
status: active
created: '2026-09-27'
last_updated: '2026-09-27'
components:
  - security_scanner
  - commit_guardian
related_docs:
  - docs/known-issues/security-scanner.md
  - docs/known-issues/security-scanner/open-low-ki-sec-20260914-entropy-flags-test-class-names.md
---

# KI-SEC-20260927-generic-secret-flags-placeholder-constants-by-name — GENERIC_SECRET judges a string by the name it is assigned to

> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium. A false positive only; it blocks the commit, and its advertised remedy is
  fragile.
- **Status:** open — no AC.
- **Occurrences:** 2 (2026-09-27, GE-120f-1 family commit, two consecutive attempts)
- **First seen:** 2026-09-27 · **Last seen:** 2026-09-27
- **Where:** `templates/scripts/commit_guardian/check_secrets.py` (the `GENERIC_SECRET` rule) and
  the scanner module it calls; `.security-allowlist` (line-number keyed entries).

## Symptom

1. `check-secrets` blocked a commit on a private module-level constant in
   `templates/scripts/commit_guardian/check_negative_control_liveness.py` whose name ended in
   `TOKEN` and whose value was a short parenthesised placeholder word (the text printed when no
   identity is available). Nothing about the value resembles a credential.
2. After the constant was renamed, the next attempt was blocked again, this time on
   `01_TICKET-20260914-GE-120f-1.md`: the commit agent's own Comments entry explained the first
   finding by quoting the original assignment verbatim, and the same rule matched the prose.
   The earlier blocker entries quoted the same line inside an escaped YAML string and did not match.

Both times the hook's remedy was a `.security-allowlist` entry of the form
`GENERIC_SECRET:<path>:<line>`.

## Mechanism

The rule keys on a secret-sounding identifier (`TOKEN`, `SECRET`, `KEY`, …) followed by an
assignment of a quoted string. It does not look at the value's shape (length, character classes,
entropy) or at the file kind, so a placeholder constant and a sentence quoting one both match.
The allowlist entry it suggests is keyed on a line number, so any edit above that line
invalidates it and the next commit fails again.

## Workaround used

Rename the constant so its name carries none of the trigger words (it became `_NO_IDENTITY`), and
refer to the old name in prose by identifier only, never as a quoted assignment. No allowlist entry
was added.

## Fix direction

Require the value to look like a secret before `GENERIC_SECRET` fires: a minimum length and
character mix, or the existing entropy measure. Skip values that are obviously placeholders
(parenthesised words, empty strings). Scope the rule away from Markdown prose, or apply the value
test there too. Offer an allowlist form keyed on the value's hash or on the identifier rather than
the line number.

**Pattern:** a detector that judges a string by the name it is assigned to rather than by what the string is.
