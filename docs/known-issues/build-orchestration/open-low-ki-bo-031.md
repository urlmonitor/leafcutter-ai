---
title: "KI-BO-031 — `check_doc_frontmatter.py` tells the operator to consult a spec file that does not exist"
description: "KI-BO-031 — `check_doc_frontmatter.py` tells the operator to consult a spec file that does not exist"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-031 — `check_doc_frontmatter.py` tells the operator to consult a spec file that does not exist

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** low
- **Status:** open — code is on `main` and live
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-26 (re-verified against `37655862`)
- **Where:** `templates/scripts/commit_guardian/check_doc_frontmatter.py:473-474` (the failure
  remediation block); also referenced at `:5`, `:127`, `:601`, `:610`

**Symptom.** On any frontmatter violation the hook prints:

```
   FIX: Add or correct YAML frontmatter per docs/FRONTMATTER.md spec.
   📖 Spec: docs/FRONTMATTER.md
```

`docs/FRONTMATTER.md` does not exist in this repository. The one file with that name is
`templates/docs/architecture/FRONTMATTER.md`, which is a consumer-install template and not
reachable at the path printed.

**Why it survives.** The message is on the *failure* path only, so it is read exactly when
someone is already blocked and looking for the rule — the worst moment to hand them a dead
path. Nothing tests remediation strings, and a dangling reference in a print statement is
invisible to `check-doc-links`, which reads markdown link syntax rather than program output.

**Evidence.** Recovered as a sub-note of the (now fixed, hence dropped) agent-card frontmatter
entry; the parent defect was resolved and this one was not. `ls docs/FRONTMATTER.md` →
`No such file or directory`.

**Fix direction.** Point at the file that actually documents the rules, or make the message
name the specific missing field and the valid enum it is checked against — which the hook
already computes and prints one line earlier, making the spec pointer redundant rather than
merely wrong.

**Pattern:** same shape as `KI-TQ-003` — a gate that works correctly and whose remediation
instruction cannot be followed.

---
