---
title: "KI-SEC-20261020-entropy-flags-decision-history-tail-tag — ENTROPY_HIGH flags the doc-enforcer-mandated DECISION HISTORY tail tag whenever the epic name is long, so two mandated conventions collide"
description: "low — no secret can slip past because of this; the refusal is loud and has a workaround, but it recurs on every long-named epic. The workaround, per-line ENTROPY_HIGH suppressions, is fragile when lines shift. Observed 2026-10-20 on scripts/knowledge/emit_knowledge.py lines 334-336."
type: reference
category: reference
status: active
created: '2026-10-20'
last_updated: '2026-10-20'
components:
  - security_scanner
  - commit_guardian
related_docs:
  - docs/known-issues/security-scanner.md
  - docs/known-issues/security-scanner/open-low-ki-sec-20260914-entropy-flags-test-class-names.md
  - templates/skills/doc-enforcer/SKILL.md
---

# KI-SEC-20261020-entropy-flags-decision-history-tail-tag — ENTROPY_HIGH flags the mandated DECISION HISTORY tail tag when the epic name is long

> One known issue. Index: [security-scanner.md](../security-scanner.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** low. The refusal is loud and has a workaround, but it will recur on every long-named epic.
- **Status:** open — no AC.
- **Occurrences:** 3 findings in one commit attempt (2026-10-20, `scripts/knowledge/emit_knowledge.py` lines 334-336)
- **First seen:** 2026-10-20 · **Last seen:** 2026-10-20
- **Where:** `templates/skills/security-scanner/scripts/scan_secrets.py`: `_TOKEN_RE` = `[A-Za-z0-9+/=_\-]{20,}`, `_ENTROPY_THRESHOLD = 4.5`, `_ENTROPY_MIN_LEN = 20`. The colliding convention is the tail-tag format in `templates/skills/doc-enforcer/SKILL.md` section 4.1.

## Symptom

`check-secrets` refused a commit with an `ENTROPY_HIGH` finding on each of three DECISION HISTORY lines in `scripts/knowledge/emit_knowledge.py` (lines 334-336). Each line ends with the tail tag that doc-enforcer requires on every new entry, in the shape `(#EPIC-<Name>/<NN>)`. The epic in question was `EPIC-ALearningAnAgentHasTodayActuallyGets`, ticket `01`.

## Measurement

Shannon entropy of the tag token, computed with the scanner's formula:

| Token | Entropy | Result |
|---|---|---|
| tag with the `/01` ticket suffix (epic name `ALearningAnAgentHasTodayActuallyGets`) | 4.52 | flagged (over 4.5) |
| the same tag without the `/01` | 4.35 | passes |

`_TOKEN_RE` includes `/` and `-` in its character class, so `#EPIC-<Name>/<NN>` is one token rather than two. The epic name and ticket number merge, and the digits and `/` push a long mixed-case name over the threshold.

## Mechanism

Two mandated conventions collide. doc-enforcer requires the tail tag on every new DECISION HISTORY entry. The scanner reads that tag as a candidate secret once the epic name is long enough. Every new entry in any epic with a long name will be refused.

## Workaround used

Three per-line `ENTROPY_HIGH` suppressions, one per flagged line, added to both `.security-allowlist` copies (workspace-root and worktree) and committed on branch `feat/inf-700b-capture-learnings`. Per-line entries break when lines shift. A whole-file glob on production code would suppress real secrets, so it was not used.

## Fix directions (owner to choose)

- (a) Exempt tokens matching the tail-tag shape `#EPIC-[A-Za-z]+/\d+` from the entropy rule.
- (b) Exclude `/` from `_TOKEN_RE`.
- (c) Shorten the tag convention.

**Pattern:** a detector whose false positives are structurally produced by a convention that another gate mandates. Same family as [KI-SEC-20260914-entropy-flags-test-class-names](open-low-ki-sec-20260914-entropy-flags-test-class-names.md).
