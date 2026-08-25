---
title: "docs: close BO-2400e-4 against its already-shipped fix and file two latent AC-write defects"
date: "2026-08-25"
time: "12:49"
type: manual
components: 
  - ac_store
  - build_orchestration
summary: "Corrected an acceptance-criterion record that had sat marked incomplete for a week after the behaviour it describes was already fixed and tested, and logged two related risks in the AC-tracking system so they get fixed deliberately rather than discovered by accident."
description: "No production code changes (scripts/build_orchestration/fast_lane.py is deliberately untouched — a concurrent build is rewriting it). BO-2400e-4.yaml flips work_status: todo -> done and sets implemented_by, replacing a stale 2026-08-17 'VERIFIED EVIDENCE' block that was wrong about the quoted code, the function's line range, and all three call-site line numbers. The 14 existing tests in test_ki_bo_003_ac_yaml_preservation.py gain '# covers: BO-2400e-4' alongside their original '# covers: KI-BO-003' tag, which is what makes the AC done-eligible (done_proof goes from 'no linked test found' to eligible=True with 14 linked passing tests). docs/known-issues/build-orchestration.md gains three entries: KI-BO-019 (a CRLF-encoded AC record is silently rewritten LF end-to-end by a single work_status flip, latent today because 0 of 3,257 records are CRLF), KI-BO-020 (_update_ac_work_status can raise ValueError, all three call sites catch only OSError, and the escape strands an AC in in_progress permanently because release_claim is itself what aborts), and KI-BO-021 (BO-2400e-4 is closed on 2 of its 4 specified tests; the missing pair is the one that would survive a writer swap, tracked as a TODO). A new test file, test_ki_bo_020_valueerror_escapes_call_sites.py, pins KI-BO-020 with 4 tests against real AC-YAML fixtures on a real filesystem, all @unittest.expectedFailure since no fix is applied here. AC_ENFORCE_STRICT=1 pytest unit_tests/build_orchestration/ -> 141 passed, 4 xfailed, 4 subtests passed. validate_ac_schema.py on the BO-2400 folder -> OK: all 82 AC YAML files are valid."
---

## Entry

The same defect was tracked twice, one day apart, in two registries that
could not see each other: as known issue `KI-BO-003` and as acceptance
criterion `BO-2400e-4` ("Recording progress on a requirement changes the
progress and nothing else"). It was fixed under the KI id on 2026-08-18. The
AC never learned of it — it sat `work_status: todo` for a week, during which
the fast lane kept selecting it as ready work, while `KI-BO-003` has no entry
in `docs/known-issues/` at all for the AC tooling to resolve against. The
tests existed and were green the whole time; they were simply tagged with an
id the AC system does not read.

This entry closes that gap, not by writing new production code but by making
the record agree with reality:

- `BO-2400e-4.yaml` flips to `done` with `implemented_by` pointing at
  `fast_lane.py`, and its stale "VERIFIED EVIDENCE (2026-08-17, do not
  re-investigate)" block is replaced — that block was wrong about the quoted
  code, the function's line range, and all three call-site line numbers, and
  its "do not re-investigate" framing would have kept every future pass from
  correcting it.
- The 14 existing tests in `test_ki_bo_003_ac_yaml_preservation.py` gain a
  second `# covers: BO-2400e-4` tag. That one-line addition is the entire
  mechanism that moves `done_proof` from "no linked test found" to
  `eligible = True` with 14 linked passing tests — the AC and KI registries
  are now bridged for this specific record.

Two latent defects surfaced while doing this and are filed rather than fixed,
because fixing either would touch `fast_lane.py`, which a concurrent build is
rewriting:

- **`KI-BO-019`** — a CRLF-encoded AC record is rewritten LF end-to-end by a
  single `work_status` flip (154 changed lines for what should be a one-line
  diff), even though `safe_load` still returns the correct value either way.
  Latent today: 0 of 3,257 records in the store are CRLF, but nothing
  prevents one from arriving.
- **`KI-BO-020`** — `_update_ac_work_status` can raise `ValueError`, but all
  three call sites catch only `OSError`. The escape route strands the AC in
  `in_progress` permanently, because `release_claim` — the mechanism meant to
  un-stick it — is itself what aborts on the unhandled exception. Pinned by
  four new `@unittest.expectedFailure` tests in
  `test_ki_bo_020_valueerror_escapes_call_sites.py`, run against real AC-YAML
  fixtures on a real filesystem; removing the decorator is the proof once the
  call sites are widened to catch `ValueError` too.

Closure here is on partial coverage by explicit decision, not by oversight:
`BO-2400e-4` specifies four tests and is closed against two of them. The
missing pair is filed as `KI-BO-021` — and it matters now, not later, because
`BO-2400e-3` is being built this week against this exact same function, and
the untested pair is precisely the behaviour a writer swap would break
silently.

**Verification:** `AC_ENFORCE_STRICT=1 pytest unit_tests/build_orchestration/`
→ 141 passed, 4 xfailed, 4 subtests passed. `validate_ac_schema.py` on the
BO-2400 folder → `OK: all 82 AC YAML files are valid`.

**Correction (2026-08-25, post-merge).** The ids above are wrong as published.
PR #538 landed its own `KI-BO-019` and `KI-BO-020` seventeen minutes before this
entry's PR merged, and the two collided on `main`. #538 was first and keeps those
numbers; the entries described above were renumbered **`019 → 022`** and
**`020 → 023`**. `KI-BO-021` is unaffected. The body is left as written rather than
silently rewritten — see `KI-BO-024` for why this kept happening.
