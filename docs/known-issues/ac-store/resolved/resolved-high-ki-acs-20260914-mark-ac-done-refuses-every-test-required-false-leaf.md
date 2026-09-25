---
title: "KI-ACS-20260914-mark-ac-done-refuses-every-test-required-false-leaf — the sanctioned tool for marking an AC done cannot pass a single docs-only leaf, ever"
description: "KI-ACS-20260914-mark-ac-done-refuses-every-test-required-false-leaf — mark_ac_done.py --test-root refuses every leaf AC declaring test_required: false, because done_proof.py's oracle has no leaf exemption, so no docs-only AC can be marked done by the sanctioned tool."
type: reference
category: reference
status: active
created: '2026-09-14'
last_updated: '2026-09-25'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
---

# KI-ACS-20260914-mark-ac-done-refuses-every-test-required-false-leaf — the sanctioned tool for marking an AC done cannot pass a single docs-only leaf, ever

> One known issue. Index: [ac-store.md](../../ac-store.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** **RESOLVED** (`01601fbb`, PR #861, BO-2500a-1-ii; verified 2026-09-25 by
  re-running this entry's own repro, which now exits 0, plus a non-dry-run probe on a scratch
  store copy and the fix's 18 regression tests)
- **Occurrences:** 1
- **First seen:** 2026-09-14 · **Last seen:** 2026-09-14
- **Where:** `scripts/ac_store/mark_ac_done.py` (`mark_ac_done()`, the `test_root is not
  None` branch) → `scripts/ac_store/test_enforcement.py::verify_done_eligible` →
  `scripts/ac_store/done_proof.py::verify_done_eligible`

**Symptom.** `mark_ac_done.py --ac <id> --test-root <dir>` — the sanctioned, gated way to
flip an AC's `work_status` to `done` — refuses **every** leaf AC that legitimately declares
`test_required: false` (a docs-only or prompt-convention AC with no covers-taggable test),
with exit code 3 and the message `no linked test found for <id>`. There is no way to make
the call succeed for such an AC short of bypassing the tool (hand-editing the YAML, or
`--dry-run`-and-ignore, which is not a real path since dry-run never writes).

**Root cause.** `done_proof.py::verify_done_eligible` — the oracle both `mark_ac_done.py`
and the commit-guardian `check_done_proof.py` hooks call — has **zero** references to
`test_required` anywhere in the module (confirmed by a full-file search: none). It has a
composite exemption (`_has_resolvable_child` / `_verify_composite_eligible`, for an AC whose
`covered_by` resolves to real children) but no leaf exemption at all: an AC with no linked
`# covers:` tag and no resolvable children is unconditionally `{"eligible": False, "reason":
"no linked test found for <id>"}`, regardless of what its own `test_required` field says.

This is not the same gap as `KI-CG-006` (commit-guardian register). That entry is about two
of three **commit-guardian hook** functions (`check_all_done_acs`, `check_changed_done_acs`)
already reading `test_required` themselves — as a filter applied *before* calling
`verify_done_eligible`, in the hook file, not inside the oracle — while a third
(`check_staged_done_proofs`) originally lacked it (see that entry's 2026-09-14 update: the
third has since gained it too). `mark_ac_done.py` calls the oracle **directly**, with no
such pre-filter of its own anywhere in `scripts/ac_store/mark_ac_done.py` or
`test_enforcement.py`. The exemption pattern exists in this codebase — three separate call
sites have each independently reimplemented `if data.get("test_required") is False:
continue` — and the one tool whose entire job is "mark this AC done" is the one place it
was never added.

**Reproduced live, 2026-09-14** against `TQ-500c-1` (`status: active`, `test_required:
false`, currently `work_status: todo` — chosen because it is unrelated to the epic that
surfaced this and demonstrates the defect is general, not specific to one ticket family):

```
$ python scripts/ac_store/mark_ac_done.py --ac TQ-500c-1 \
    --ac-root docs/acceptance-criteria --test-root unit_tests --dry-run
REFUSED: TQ-500c-1 is not eligible for done — no linked test found for TQ-500c-1
exit: 3
```

**Real-world instance.** `ACD-2100e-2` (`test_required: false`, an L2 AC whose deliverable
is a how-to guide) had its documentation committed and its `implemented_by` field populated
at `15f745bb1`, but `work_status` stayed `todo` — not because the work was incomplete, but
because `mark_ac_done.py --test-root` could not pass it. The corresponding ticket (25 of
`EPIC-StartingNewWorkTheProperWayAlways`) was later flipped to `status: done` in its
frontmatter, which then tripped `check_ticket_ac_status_parity` (a pre-commit hook that
blocks a staged `status: done` ticket whose `source_ac.work_status` is not also `done`) and
blocked the commit. The eventual fix was a hand-authored `chore` commit
(`b328b874d`, 2026-09-14, "flip status to done for 5 ACD-2100 tickets + AC") that edited the
AC YAML's `work_status` directly — bypassing the sanctioned tool because the sanctioned tool
structurally cannot do this. The commit message states the mechanism explicitly: *"the
fulfillment gate never flipped it automatically because mark_ac_done.py --test-root cannot
pass a test_required: false AC."* This is a second, independent ticket in the same epic
hitting the identical gap `TQ-500c-1` reproduces above — not a one-off.

**Why this matters beyond one ticket.** Every hand-edit of `work_status` bypasses whatever
audit trail `mark_ac_done.py` would otherwise leave (its dry-run preview, its idempotency
guard, its `status: active` guard, its ticket-context logging) and normalises "edit the YAML
directly" as the actual procedure for an entire class of AC — docs-only and
prompt-convention ACs, which are common (`test_required: false` appears repeatedly across
this store; see `KI-ACS-012`'s neighbourhood for the broader test-contract gaps). A
mechanism that exists specifically to prevent unaudited `work_status` writes is routinely
routed around for a whole category of legitimate, correctly-authored work.

**Fix direction.** Add the same `if ac.get("test_required") is False: <treat as eligible>`
short-circuit to `done_proof.py::verify_done_eligible` itself — once, in the oracle all three
existing call sites (and `mark_ac_done.py`) already trust — rather than a fourth independent
reimplementation in `mark_ac_done.py`. This also retires the two hook-level pre-filters in
`check_done_proof.py` as redundant once the oracle handles it centrally, closing the
"reimplemented three times" smell noted above. Pair with a regression test that calls
`mark_ac_done.py --test-root` directly (not the oracle in isolation) against a real
`test_required: false` fixture AC and asserts exit code 0.

**Related.** `KI-CG-006` (the hook-side half of the same `test_required` vocabulary, now
partially fixed there — see [`../commit-guardian/open-high-ki-cg-006.md`](../../commit-guardian/open-high-ki-cg-006.md));
[`KI-ACS-012`](../open-high-ki-acs-012.md) (test-contract gaps on code ACs, the opposite shape
— code that should have a test contract and doesn't, versus docs that legitimately shouldn't
and can't get past the gate anyway).

**Resolution (verified 2026-09-25).** Fixed in the oracle, as the fix direction asked, by
`01601fbb` — "fix(build-orchestration): an untestable AC can be marked done, and one with no
stated reason no longer slips past CI (BO-2500a-1-ii) (#861)". One shared predicate,
`is_covers_tag_waived()` (defined in `scripts/ac_store/_done_proof_phase_helpers.py`,
re-exported from `done_proof.py`), now waives the covers-tag requirement inside
`verify_done_eligible`. `check_done_proof.py` consults the same predicate, so there is no
longer a separate reimplementation per hook. There is one deliberate tightening. The waiver
needs `test_required: false` **and** a non-empty `test_rationale`, so a `test_required: false`
AC with no stated reason is still refused. That is intended behaviour, not a residue of this
defect.

Evidence:

- This entry's own repro, run on main at `d2fe85a1`:
  `python scripts/ac_store/mark_ac_done.py --ac TQ-500c-1 --ac-root docs/acceptance-criteria --test-root unit_tests --dry-run`
  → `[dry-run] would mark TQ-500c-1 work_status=done`, exit 0 (it was `REFUSED`, exit 3).
- A non-dry-run probe on a scratch copy of `TQ-500c-1.yaml` with an empty test root →
  `marked TQ-500c-1 work_status=done`, exit 0, and the file read `work_status: done` afterwards.
  The same copy with `test_rationale` removed → `REFUSED ... no linked test found`, exit 3,
  which is the intended rationale gate.
- `python -m pytest unit_tests/commit_guardian/test_done_proof_test_required_exemption.py unit_tests/commit_guardian/test_done_proof_test_required_rationale_gate.py -q`
  → 18 passed.

Not done from the fix direction: none of those tests calls `mark_ac_done.py` directly. They
exercise the oracle and the hooks. Do not confuse this entry with
`KI-ACS-20260925-mark-ac-done-reports-success-without-writing-the-key`, which is a different,
still-open `mark_ac_done` defect.

**Pattern:** an exemption implemented independently at every consumer of an oracle except
the oracle itself, so the one caller that forgets to reimplement it — here, the tool whose
whole purpose is the thing being gated — fails for every input the exemption exists to
cover.

---
