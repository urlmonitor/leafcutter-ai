---
title: "UXP-700c-2 and UXP-700c-2-ii finished by hand from a halted /build-feature run"
date: "2026-09-16"
time: "22:10"
type: manual
components:
  - ux_prototyping
summary: "Completes two tickets left uncommitted by the interrupted /build-feature run wf_3d2879c1-2ae: a journey that has been confirmed against the acceptance criteria and files it describes now states that confirmation and is reported behind, naming what changed, the moment any of them move (UXP-700c-2); and a journey the checker finds behind now carries that verdict as a durable mark on the journey artifact itself, written when the check finds it behind and removed the moment a later check finds it current, readable by any surface without re-running the checker (UXP-700c-2-ii)."
description: "Run wf_3d2879c1-2ae drove EPIC-TruthfulProjectRecord and halted with tickets 21 (UXP-700c-2) and 23 (UXP-700c-2-ii) staged but uncommitted, both carrying a recorded ac-validator blocker. UXP-700c-2's _check_freshness fell back to `ac_records.get(ac_id, {})` for an AC id named in a journey's `confirmed.state` that had since vanished from the AC store, hashing an empty record whose signature could never match the recorded one, so the journey was wrongly reported BEHIND with the vanished id listed as changed -- directly contradicting the ticket's own declared Expects-From contract with sibling UXP-700c-1 ('a behind verdict is not produced for a target that simply vanished'), reproduced verbatim via ac-validator's own repro. Fixed per its own suggested remediation: a confirmed.state id absent from ac_records now routes to a distinct [freshness-unresolvable] warning and is never folded into changed, mirroring how _check_pointers already keeps unresolvable separate from broken; a new regression test was written test-first (confirmed red for the exact vanished-id reason, then green after the fix) since no test-writer dispatch exists in this by-hand recovery flow. UXP-700c-2-ii's blocker was structural rather than a defect: _sync_behind_marks (the ADR-043 write/remove helper) existed and its own direct-call tests passed, but nothing called it from run_checks()/main() -- deliberately deferred by the halted run's own two python-coder passes because UXP-700c-2's verdict computation, the helper's sole input, had not landed yet. With UXP-700c-2 now fixed and landed, _sync_behind_marks was wired into main(), called once per run after the freshness comparison, and a new reachability test was added driving the real, wired two-process CLI path end to end (not a direct helper call) to prove both a mark being written for a drifted confirmed journey and removed once re-confirmed current, plus that a never-confirmed journey run through the real CLI writes zero marks, matching ADR-043's own 'the first run MUST write zero marks' claim. Extracting the five freshness/behind-mark functions into a sibling product_truth_freshness.py module (this file's usual 400-content-line ratchet escape valve) was tried and reverted: it reproduced a real bug, but only under the FULL unit_tests/product_truth suite, never in file-level isolation -- test_uxp_700a_1.py deliberately pops validate_product_truth from sys.modules in its own cleanup (testing fresh-install import behaviour), and a later cross-module re-import silently binds to a different module object than the one a test had patched STORE on. The functions were kept inline instead, reading STORE as a plain same-module global exactly like generate_product_truth.py's own STORE pattern every sibling test already relies on -- which is also what ADR-043 SS10 already requires ('the write/remove helper MUST live in validate_product_truth.py, in the same module as UXP-700c-2's verdict computation... a parallel script MUST NOT be created'), a constraint the halted run's own two python-coder passes on these same tickets had independently already honoured. To bring the file back under its 400-content-line ratchet with the freshness/behind-mark code staying inline, moved OTHER, unrelated, STORE-independent code out instead: OUTCOME_BY_COMBO, _validate_schema, and two new pure functions (validate_eval_rows, check_mock_data_ref, extracted from _check_eval's row loop and run_checks()'s mock_data_ref cross-check) now live in the existing product_truth_checks.py sibling module, re-imported so vpt._validate_schema/vpt.OUTCOME_BY_COMBO still resolve; validate_product_truth.py measured 398 content lines and product_truth_checks.py 396 via the hook's own count_content_lines, and check_file_size.py run directly against the staged set passes. Separately, check-secrets flagged product-truth-schema-reference.md's related_docs entry for UXP-591.yaml as a high-entropy false positive (Shannon 4.511, just over the 4.5 threshold) -- rather than add a .security-allowlist entry, removed that related_docs entry, since UXP-591.yaml already carries the reverse doc_links entry pointing back at the schema reference. Both tickets' shared source files (flow.schema.json, validate_product_truth.py, product_truth_checks.py) and the split-out pure test-fixture helper modules are declared in files_touched on both tickets; each ticket's own doc/schema-only files are cross-declared under the other's out_of_scope."
commits:
breaking: false
---

## Entry

Two tickets from the halted `/build-feature` epic run `wf_3d2879c1-2ae`
(EPIC-TruthfulProjectRecord) were finished by hand at the user's direction on
2026-09-16, on branch `feature/uxp-700c-2-c-2-ii` off `origin/main`.

**UXP-700c-2 — the record states what it was last confirmed against, and
says so when that has moved.** `_check_freshness` compares a journey's
`confirmed.state` (a content signature per described AC, taken at
confirmation time) against each AC's current content, reporting a journey
BEHIND when something has moved. The bug: an AC id in `confirmed.state` that
had since vanished from the AC store (renamed, retired, or the record
simply moved) fell back to an empty record via `ac_records.get(ac_id, {})`,
whose signature can never equal the recorded one — every vanished id was
therefore misreported as changed, violating the ticket's own declared
contract with sibling `UXP-700c-1` that a vanished target must never itself
produce a behind verdict. Fixed by routing a vanished id into a distinct
`[freshness-unresolvable]` warning, reported by name and never folded into
`changed`, mirroring `_check_pointers`'s existing unresolvable/broken split.
A new test, `TestFreshnessSurvivesAVanishedCitationTarget`, was written
test-first against the ticket's own reproduction, confirmed red for exactly
that reason, then green after the fix.

**UXP-700c-2-ii — a journey known to be behind carries that mark in the
record itself.** The ADR-043 write/remove helper (`_sync_behind_marks`,
`_behind_mark_for`, `_resolve_flow_path`) already existed and its own
direct-call tests already passed, but it was never wired into
`run_checks()`/`main()` — deliberately deferred by the halted run because
its sole verdict source, `UXP-700c-2`, had not landed. With `UXP-700c-2` now
fixed, the wiring was added: `main()` calls `_sync_behind_marks` once per
run, immediately after stating how many journeys it compared for freshness,
passing this run's verdicts and today's date. A new reachability test,
`TestMainWritesAndRemovesBehindMarksThroughTheRealCli`, drives the real,
wired two-process CLI path (the real `generate_product_truth.py` then the
real `validate_product_truth.py`, both subprocesses) to prove a mark is both
written for a drifted confirmed journey and removed once re-confirmed
current — through `main()` itself, not a direct helper call — closing
exactly the reachability gap `ac-validator`'s blocker named. A second
scenario proves a never-confirmed journey run through the real CLI writes
zero marks, matching ADR-043's own "the first run MUST write zero marks"
claim.

Both tickets' own regression/reachability tests were authored directly by
`python-coder` in this pass — no `test-writer` dispatch exists in this
by-hand recovery flow — following the same test-first discipline (red
confirmed before the fix, green after) the pipeline would otherwise enforce.
An extraction of the five freshness/behind-mark functions into a sibling
`product_truth_freshness.py` module was attempted (this file's usual
size-ratchet escape valve, already used by four sibling `product_truth_*.py`
modules) and reverted after it reproduced a real, full-suite-only bug
(`test_uxp_700a_1.py`'s `sys.modules` eviction of `validate_product_truth`
in its own cleanup silently detaches a later cross-module `STORE` read from
whichever module object a test actually patched); the functions stayed
inline, per ADR-043 SS10's own binding same-module requirement, which the
halted run's own python-coder passes on both tickets had already
independently honoured the same way. To still clear the 400-content-line
ratchet, moved OTHER, unrelated, STORE-independent code out instead:
`OUTCOME_BY_COMBO`, `_validate_schema`, and two new pure functions
(`validate_eval_rows`, `check_mock_data_ref`) now live in the existing
`product_truth_checks.py` sibling module — neither reads nor patches
`STORE`, so neither reintroduces the `sys.modules` hazard above.
`validate_product_truth.py` measured 398 content lines and
`product_truth_checks.py` 396 (the hook's own `count_content_lines`); both
files, and the two new test files, pass `check_file_size.py` run directly
against the staged set. Separately, `check-secrets` flagged
`product-truth-schema-reference.md`'s `related_docs` entry for
`UXP-591.yaml` as a high-entropy false positive (Shannon 4.511, just over
the 4.5 threshold) — rather than add a `.security-allowlist` entry, that
`related_docs` entry was removed, since `UXP-591.yaml` already carries the
reverse `doc_links` entry pointing back at the schema reference.

Independently re-verified rather than trusted from the halted run's own
comments: ran `unit_tests/product_truth/test_uxp_700c_2.py` (6/6, one new)
and `test_uxp_700c_2_ii.py` (6/6, two new) individually green, then the full
`unit_tests/product_truth/` suite under `AC_ENFORCE_STRICT=1` against a
disposable `git worktree add -d` pristine `origin/main` baseline on this
host (125 passed / 0 failures here, 113 passed / 0 failures on baseline —
the 12-test delta is this group's two new test files); mutation-tested both
fixes (reverted each in place, confirmed its own guarding test goes red for
the exact reason, restored, confirmed green again); and ran the real CLI
against the committed store both before and after the wiring landed
(`checked-and-sound`, `"compared 0 journey(s) for freshness"` since no real
journey carries `confirmed` yet, zero journey-file churn in `git status`).
`agents.ac-validator` and `agents.commit` (ticket 21) / `ac-validator`
(ticket 23) are reset to `needed` rather than ticked `signed_off`, since
those phases were not actually re-dispatched in this by-hand pass — only
independently verified by `python-coder` directly — matching this project's
own established by-hand-completion precedent.
