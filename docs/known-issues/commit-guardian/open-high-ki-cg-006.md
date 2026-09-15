---
title: "KI-CG-006 — The pre-commit proof-of-done gate and the CI backstop disagree on what a valid tag is, in both directions"
description: "KI-CG-006 — The pre-commit proof-of-done gate and the CI backstop disagree on what a valid tag is, in both directions"
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

# KI-CG-006 — The pre-commit proof-of-done gate and the CI backstop disagree on what a valid tag is, in both directions

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 3
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-19
- **Where:** `templates/scripts/commit_guardian/check_done_proof.py`
  (`check_staged_done_proofs`, `_collect_all_covered_ids`)

**Symptom.** `check_staged_done_proofs` never reads `test_required`, and has no composite
path. Its two siblings have both: `check_all_done_acs` and `check_changed_done_acs` each
skip an AC with `test_required: false`, and both derive a composite's verdict from its
children via `verify_done_eligible`. So the fast local gate blocks commits that the CI
gate would pass.

**The disagreement also runs the other way — it accepts tags that link to nothing.**
The two gates do not share a scanner. `_collect_all_covered_ids` is a flat
`COVERS_TAG_RE.finditer` over each file's whole text and keeps every id it sees, wherever
it sits. The oracle's Python scanner (`done_proof._scan_single_test_file`) attributes a tag
to the most recent enclosing `def test_*` and **drops** any tag with no enclosing test
function. A tag in a module docstring, an import block, a helper, or a comment header is
therefore proof to the pre-commit gate and invisible to the authoritative one.

So the two halves of one file define "a valid covers tag" differently: a text-presence
scan with no notion of a test function, versus a scanner that requires one. Neither reads
the other. That is the actual defect — the strictness gap and the laxity gap are two
symptoms of it, and fixing only the direction that blocks a commit leaves the direction
that waves one through.

**Evidence (false accept).** In a consumer install (DIAGraph),
`tests/test_psd_problems_case_count.py` carries `# covers: MSN-101` **inside its module
docstring** — before any `def`. The pre-commit gate finds the id and passes `MSN-101` as
proven; `verify_done_eligible('MSN-101')` reports `no linked test found`. The record can
be committed as `done` locally with nothing behind it. The lax half is the more dangerous
one: it is phantom-done, and it is the failure mode this hook exists to prevent.

Worth noting the oracle's own scanner is not the safe reference either — it cannot see an
`async def` test at all (KI-ACS-008 D-1), so "the strict one is right" does not hold
either. Any fix should settle on one shared scanner, not pick a winner.

The module docstring documents the exemption for the two CI functions and is silent about
the pre-commit one, so the omission may be deliberate. It is still incoherent in effect:
the same docstring calls the pre-commit check the fast approximation and CI "the
authoritative backstop". An approximation stricter than its backstop is not an
approximation.

**Consequence.** An AC that is legitimately `test_required: false` and `work_status: done`
can never appear in a staged diff again. Editing so much as a stale path inside one of
those files is uncommittable without `SKIP=`. Same for any `done` composite.

**Evidence.** On 2026-08-18 a commit correcting AC statuses was blocked on seven records:
`BO-1500a-3`, `BO-1500b-4`, `BO-1500c-4`, `BO-1500c-5` (all `test_required: false`
documentation ACs whose diagrams and how-to exist on disk) and `BO-1500b-1`, `BO-1600d`,
`BO-510-3` (composites). The authoritative gate — `check_done_proof --mode ci-changed
--base origin/main`, which backs the required "Proof-of-done coverage check (BO-2500b)"
status check — exited 0 on the same tree.

Earlier in the same session the same hook was run standalone from the workspace parent and
exited 0, which was read as a pass. It was vacuous: `git diff --cached` saw no index there,
so it checked nothing. See KI-CG-001 for the same index-scoping confusion.

**Fix direction.** Mirror the siblings: skip `test_required: false`, and fall through to
the composite path rather than demanding a direct tag. It is a small change but it widens
a phantom-done gate, so it wants an AC and a test rather than an in-passing edit.

For the laxity half, replace `_collect_all_covered_ids`' bare regex sweep with the oracle's
own scanner — export `done_proof._scan_test_root_for_covers_tags` and derive the id set
from `{t["ac_id"] for t in tags}`, so a tag outside a test function stops counting as
presence in both gates by construction. That import already exists in this module (the
`verify_done_eligible` / `COVERS_TAG_RE` block), so it costs no new coupling. Fix
KI-ACS-008 D-1 first or the shared scanner will start rejecting every async-tested AC at
pre-commit time. The right end state is one scanner with one definition and a test
asserting the two gates agree on a fixture set covering all four shapes: sync, async,
file-level, composite.

---
