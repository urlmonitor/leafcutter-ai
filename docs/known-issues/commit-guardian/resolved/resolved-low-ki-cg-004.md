---
title: "KI-CG-004 — moved to `security-scanner`"
description: "KI-CG-004 — moved to `security-scanner`"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-004 — moved to `security-scanner`

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

Refiled 2026-08-19 as **KI-SEC-001** in
[`docs/known-issues/security-scanner.md`](security-scanner.md): *prose exemption
disables entropy detection for whole files, including executable Python under
`templates/skills/`, and its path match is not root-anchored.*

Moved when the `security-scanner` register was created. The defect is about what the
secrets scanner can be talked out of reporting, which is that surface's question, not
the guardrail framework's. The id is retired here rather than reused, so the numbering
gap is intentional.

**Six `GE-123` records still cite `KI-CG-004` at this file path, deliberately** — they
fence it as out of scope so that repairing it and `GE-123d-4-i` are not closed as
duplicates of one another. Those citations were left untouched by the move; this stub is
what resolves them. Do not repoint them.

---
