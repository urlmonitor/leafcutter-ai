---
title: "KI-CG-20260914-ratchet-freezes-central-registries — a per-file ratchet makes any manifest or registry unmaintainable once it crosses its limit, because complying with the rule on one file forces violating it on another"
description: "high — `check-file-size` is LIVE (registered by GE-127a-1, 2026-09-07), so this is not a latent registration hazard like its neighbours above. It blocks real work today, and the only exits are a bypass or a large unrelated refactor."
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

# KI-CG-20260914-ratchet-freezes-central-registries — a per-file ratchet makes any manifest or registry unmaintainable once it crosses its limit, because complying with the rule on one file forces violating it on another

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high — `check-file-size` is LIVE (registered by GE-127a-1, 2026-09-07), so this is not a latent registration hazard like its neighbours above. It blocks real work today, and the only exits are a bypass or a large unrelated refactor.
- **Status:** open — no AC. `GE-127` is the owning family; this needs a declared exemption class or an equivalent, which is a change to the gate's own contract.
- **Occurrences:** 1 observed live, and structural — it recurs for every future module added to any over-limit registry.
- **First seen:** 2026-09-14 (splitting `cross_reference_audit.py` for `ACS-1600a-1`) · **Last seen:** 2026-09-14
- **Where:** `templates/scripts/commit_guardian/check_file_size.py` + `_file_size_ratchet.py` (the ratchet); triggered against `scripts/build_phases.py`, **2681 content lines against a 400 limit — 6.7× over**.

**The trap, in the order it springs.** `check-file-size` refused a 3-line bug fix because its target, `cross_reference_audit.py`, stood at 557 content lines — already over, and the ratchet refuses any growth on an already-over file. The gate's own remedy is to split, so the file was split: 557 → 177 across five new sibling modules, all six under 400. Correct outcome, exactly what the gate asked for.

But a new deployed module **must** be registered in `build_phases.py`'s deploy map, or it raises `ModuleNotFoundError` at runtime in every consumer install while passing every local test (the failure CLAUDE.md documents under "New Hook / Gate Dependencies Must Be in the Build Deploy-Manifest"). Registering five modules costs six lines. `build_phases.py` is 6.7× over its own limit, so the ratchet refuses those six lines too.

Four options, and every one is bad:

| option | outcome |
|---|---|
| Don't split | original blocker stands; the bug fix cannot land |
| Split and register | the manifest file now violates — where this actually landed |
| Split, don't register | gate passes, **deployed tool breaks in every consumer install** — strictly worst |
| Trim 6 lines from the manifest to offset | deleting documentation to satisfy a counter — the gate's own refusal message explicitly forbids exactly this |

**Why registries are the specific casualty, and why this is not just "some file is too big".** A manifest, registry, or dispatch table exists *to be appended to*. Every new hook, module, phase or agent must edit one to become reachable. So the ratchet's per-file granularity lands hardest precisely on the files whose growth is by design, and it lands there permanently: once such a file crosses its limit, **nothing new can ever be registered again** without a bypass. `build_phases.py` is frozen today. `commit_guardian.json`'s `hooks_manifest`, `agent_registry.json` and `components.json` are the same shape and should be measured before `check-file-size`'s siblings are registered.

Note the interaction with the nine per-gate briefs above: several of those gates cannot be registered *at all* without editing `commit_guardian.json`. If that file is or becomes over-limit, the census's whole remediation programme inherits this deadlock.

**Fix direction.** A declared exemption class is the shape that fits: a registry file is one whose purpose is enumeration, and the honest rule for it is not "never grow" but "grow only by enumeration entries". Options, cheapest first: (a) an explicit allowlist of registry paths exempt from the ratchet — simple, auditable, and the exemption is visible where a reader looks for it; (b) a rule that growth consisting solely of additions to a recognised literal collection does not count — more precise, much harder to implement, and probably not worth it; (c) raise the limit for a named set of files — the crudest, and it just defers the same wall.

Whichever is chosen, the exemption must be **declared and reviewable**, not inferred — an implicit carve-out reproduces the "silence is not a pass" family this register is full of. Note also that this does not need solving before the gate is useful: it is already catching true positives, and it caught one here. It needs solving before the gate can be lived with.

**Precedent worth reusing.** `GE-127b`'s ratchet already distinguishes "over the limit" from "made worse", which is the same move one level down — the insight that a rule about a *state* is unworkable and a rule about a *delta* is workable. This asks for the next step: some deltas are legitimate by the file's nature.

**Resolution used this once, on the record.** `SKIP=check-file-size` on the commit that landed `ACS-1600a-1`, with the full reasoning in that commit message. One sanctioned exception, on a commit whose *target* file went 557 → 177 rather than being skipped. Do not read that bypass as precedent for skipping the gate on a file that simply grew.

**Related.**
- `KI-CG-20260909-gate-root-files` (below) — the same shape in a different gate: a rule that reads as "no new root files" actually means "these five may never be edited again", because it matches `M` as well as `A`.
- `KI-CG-20260908-ratchet-reads-pre-merge-head` (above, RESOLVED) — the merge-commit false positive in this same ratchet. That one was a bug; this one is the rule working as designed and still being unlivable.
- `KI-CG-20260908-file-size-refusal-advises-a-dead-command` (above) — the gate's only offered remedy points at a slash command whose first step runs a script that does not exist. Encountered again here and routed around manually; the split was done by a directly-briefed coder instead.

**Pattern:** a constraint expressed per-file rather than per-change is unsatisfiable for files that exist to accumulate — and the files that exist to accumulate are exactly the ones every other change must touch.

---
