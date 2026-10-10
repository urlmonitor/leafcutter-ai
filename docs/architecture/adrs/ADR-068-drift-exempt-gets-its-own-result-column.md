---
title: "ADR-068: A Drift-Exempt Recorded Output Gets Its Own RESULT Column"
description: "check-output-drift must stop counting a drift-exempt recorded output in uncomparable and must report it in a new drift_exempt column appended last, because two live tests already assert population and line-reconciliation identities that the current double-counting silently violates."
type: "adr"
status: "active"
created: "2026-10-09"
last_updated: "2026-10-09"
deciders:
  - BrainCandy
  - adr-author
components:
  - commit_guardian
  - build_pipeline
related_docs:
  - docs/known-issues/commit-guardian/open-low-ki-cg-20261008-drift-exempt-recorded-key-widens-registry-and-double-counts.md
  - docs/2b_direction_b_output_drift_detection.md
  - docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/BP-100k-3.yaml
  - docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/BP-100k-3-iv.yaml
related_code:
  - templates/scripts/commit_guardian/_drift_exemptions.py
  - templates/scripts/commit_guardian/check_output_drift.py
  - templates/scripts/commit_guardian/check_build_drift.py
  - unit_tests/commit_guardian/test_drift_exempt_recorded_key.py
  - unit_tests/commit_guardian/test_bp_100k_3_i.py
  - unit_tests/commit_guardian/test_bp_100k_5.py
---

# ADR-068: A Drift-Exempt Recorded Output Gets Its Own RESULT Column

## Status

| Field | Value |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-10-09 |
| **Author** | adr-author (on request from BrainCandy) |
| **Supersedes** | None |

---

## Context

PR #1013 (merged 2026-10-05 as `2d895308`, a hand patch with no ticket and no AC at
the time) added a `DIRECT-DRIFT: EXEMPT` branch to
`templates/scripts/commit_guardian/check_output_drift.py`. A manifest-RECORDED output
whose on-disk hash no longer matches its `expected_output_hash`, but whose key carries
a grounded entry in `drift_gate_exemption_registry`, is now reported as excused and
does not block. The behaviour was retrofitted with acceptance criteria on 2026-10-08:
`BP-100k-3-iv` describes it, `BP-100k-3-v` bounds how narrow the suppression must stay,
`BP-100k-3-vi` pins that missing and unreadable outputs are never excused.

**This ADR does not revisit whether that excusal should exist.** It settles the single
counting question those three records deliberately left unencoded, and which
[`KI-CG-20261008`](../../known-issues/commit-guardian/open-low-ki-cg-20261008-drift-exempt-recorded-key-widens-registry-and-double-counts.md)
files as its Defect 2: **how such a key is counted in the gate's RESULT line.** There is
no originating ticket; the originating artifacts are that known issue and the three
retrofitted ACs, each of which names "pending an ADR" as the reason the question is open.

### What the gate does today

`_reconcile_recorded` returns a `drift_exempt` total, and `_scan_output_files` folds it
into `uncomparable`. The key was also hash-compared, so it is already in `verified`.
Reproduced with three recorded keys — one clean, one exempt-drifted, one
unexempt-drifted:

```
check-output-drift: RESULT verified=3 uncomparable=1 exempt=1 gaps=0 drifted=1 missing=0 unreadable=0
```

Three artifacts, four bucket memberships.

### Why that is not merely a prose defect

`ScanResult`'s own docstring in `_drift_exemptions.py` states that this never happens:
`verified` "Never includes uncomparable artifacts (AC-4)", and `uncomparable` is "Count
of artifacts neither found in the manifest (coverage gap) nor validly declared exempt".
A drift-exempt key **is** in the manifest, so by that definition it does not belong in
`uncomparable` at all. The tempting cheap fix — correct the docstring and leave the code
— was investigated and does not hold, because the double-count is not only asserted in
prose. Two tests in this repo already assert identities that the current counting
violates, and both pass today only because **no live registry entry names an
`output_mappings` key**:

1. `unit_tests/commit_guardian/test_bp_100k_5.py::TestRunSummary...::test_run_summary_reports_compared_and_not_compared_counts_together`
   asserts `len(actual_deployed_files) == verified + uncomparable` against the **real**
   deployed tree. A key counted in both inflates that sum by one per drift exemption.
2. `unit_tests/commit_guardian/test_bp_100k_3_i.py` asserts
   `len(exempt_lines) == reported_uncomparable`, where
   `_EXEMPT_LINE_RE = ^UNCOMPARABLE:\s*EXEMPT\b` — a pattern that does **not** match a
   `DIRECT-DRIFT: EXEMPT` line. A drift exemption raises `uncomparable` without
   emitting a line that regex can see, and that test's own failure message calls a
   count which does not reconcile with the per-artifact lines "exactly the unearned-pass
   this AC exists to prevent".

So the first registry entry that ever names a recorded, drifted output turns two tests
red with messages that misdescribe the cause — test 1 would report that "several hundred
deployed files are simply never counted", which is the diagnosis of a different,
much worse defect (BP-100k-5) than the one actually present. The cost of not deciding is
a trap primed to fire on whoever next writes a legitimate registry entry.

### What `verified` actually means

`verified` is incremented before the hash comparison, so it already counts ordinary
drift violations. Its own docstring says "found in the manifest/output_mappings and
hash-compared (regardless of match/drift outcome)". `verified` therefore means
**comparable**, not **clean** — which bounds how wrong the current state is: the
`verified` membership of a drift-exempt key is correct and consistent. The whole defect
sits in the `uncomparable` membership.

### What BP-100k-3's last clause demands

BP-100k-3's closing criterion requires that "'could not compare' and 'compared and
matched' are distinguishable in the gate's output and in its exit status". Today the
per-artifact line distinguishes them (`DIRECT-DRIFT:` versus `UNCOMPARABLE:` prefix,
pinned by `BP-100k-3-iv`'s `it_requirements`), but the RESULT line does not: a reader
with only the summary cannot tell a registration question from a content question that
was answered and excused. The separate column restores at the summary layer the same
distinction the per-artifact prefix already makes.

### Who reads the RESULT line

Grepped rather than assumed. Every consumer found is in-repo and uses a
prefix-anchored `re.search` over named `field=<digits>` pairs, positional in its
capture groups: `test_bp_100k_3.py`, `test_bp_100k_3_i.py`, `test_bp_100k_3_ii.py`,
`_bp_100k_3_iii_harness.py`, `test_bp_100k_3_vi.py`, `test_bp_100k_3_hardening_b1.py`,
`test_bp_100k_3_hardening_b2.py`, `test_bp_100k_4*.py`, `test_bp_100k_5.py`,
`test_bp_100k_5_i.py`, `test_bp_100k_5_ii.py`, `test_bp_100n_1.py`, `test_bp_100n_4*.py`,
`test_drift_exempt_recorded_key.py`, `unit_tests/portability/_bp1500d1i_harness.py`, and
the prose contract in `docs/2b_direction_b_output_drift_detection.md`. No consumer
outside the repo is known, and none splits the line by whitespace index. This is why
`unreadable` was appended last under adversarial-review finding B-2, and why the module
records appending as the convention.

---

## Decision

1. **`uncomparable` MUST NOT count a drift-exempt recorded output.**
   `_scan_output_files` in `check_output_drift.py` MUST stop adding `drift_exempt` into
   the `uncomparable` field it passes to `ScanResult`. `uncomparable` continues to mean
   exactly what its docstring says: artifacts absent from the manifest, whether a
   coverage gap or a declared exemption.

2. **`verified` MUST continue to count a drift-exempt recorded output.**
   The key was hash-compared, and `verified` means comparable, not clean — it already
   counts ordinary drift violations on the same grounds. No change to how `verified` is
   incremented, and `ScanResult.verified`'s docstring MUST be amended to drop the false
   "Never includes uncomparable artifacts (AC-4)" sentence while keeping the
   "regardless of match/drift outcome" clause that makes this sub-decision true.

3. **`ScanResult` MUST gain a `drift_exempt: int = 0` field, declared last.**
   It goes in `templates/scripts/commit_guardian/_drift_exemptions.py`, after
   `unreadable`, with a default of `0`, exactly as `unreadable` was added — so no
   existing keyword construction breaks. The fallback `_ScanResult` in
   `check_output_drift.py`'s `ImportError` branch MUST mirror the new field
   field-for-field, per that module's IMPORT FALLBACK contract: the degraded path runs
   precisely when nothing else can catch a mismatch, so a missing field would raise
   `TypeError` at the one moment it is needed.

4. **Both drift gates MUST append one `drift_exempt=<Z>` column, after `unreadable`.**
   The RESULT line becomes:

   ```
   RESULT verified=<N> uncomparable=<M> exempt=<E> gaps=<G> drifted=<D> missing=<X> unreadable=<Y> drift_exempt=<Z>
   ```

   No existing field may be renamed, removed, or reordered. `check_build_drift.py` MUST
   emit the column too, always `0` until it ever grows a drift-exempt branch of its own:
   the two gates read one shared registry through one shared `ScanResult` (BP-100k-3's
   AC-5), and letting their summary line formats diverge would reintroduce by a new
   route the "same registry, two behaviours" ambiguity `_drift_exemptions.py` exists to
   make mechanically impossible.

5. **`drift_exempt` MUST NOT drive the exit verdict.**
   `_verdict` is unchanged. A grounded, per-key drift exemption is reported and never
   blocks, per `BP-100k-3-iv`. The verdict stays keyed on `violations`, `missing`,
   `unreadable`, `gaps`, and the `verified == 0` floor.

6. **These identities MUST hold after the change, and a test MUST assert each.**

   | Identity | Meaning |
   |---|---|
   | `uncomparable == gaps + exempt` | the derivation every consumer computes `exempt` from |
   | `exempt == count of UNCOMPARABLE: EXEMPT lines` | the summary reconciles with the per-artifact lines |
   | `drift_exempt == count of DIRECT-DRIFT: EXEMPT lines` | the same reconciliation for the new column |
   | `verified + uncomparable == deployed population` | no artifact is counted twice or zero times |
   | `drift_exempt <= verified` | a drift exemption is always a compared artifact |

7. **The migration MUST land as one commit.** Code, ACs, tests, and reader-facing docs
   move together: `_drift_exemptions.py` and `check_output_drift.py` and
   `check_build_drift.py`; `BP-100k-3-iv`'s `exempt=1` / `exempt=2` clauses rewritten to
   `drift_exempt=1` / `drift_exempt=2` (its own `notes` and `it_requirements` already
   require this same-change amendment, and its "OPEN QUESTION, DELIBERATELY NOT ENCODED"
   requirement MUST be replaced with a citation to this ADR);
   `unit_tests/commit_guardian/test_drift_exempt_recorded_key.py`'s `_RESULT_LINE_RE`
   extended with a trailing optional `drift_exempt` group and its three `exempt`
   assertions repointed at it; `docs/2b_direction_b_output_drift_detection.md`'s verdict
   table row and its "Current counting behaviour, stated as it is rather than as a
   settled design" paragraph rewritten to state the settled design and cite this ADR;
   `KI-CG-20261008`'s Defect 2 marked resolved with this ADR named. Splitting them
   leaves a window in which the shipped gate and its own ACs disagree.

8. **Consumers MUST read `drift_exempt` by name and MUST NOT derive it by arithmetic.**
   No consumer may compute a drift-exemption count as `verified - something` or
   `uncomparable - gaps`. `exempt` means unrecorded-and-excused only; `drift_exempt`
   means recorded-compared-differed-and-excused only. A consumer that wants "all
   excusals" MUST add the two named fields.

---

## Consequences

### Positive

- The two latent test failures described in Context are defused before they fire. The
  first legitimate registry entry naming a recorded output becomes an ordinary change
  instead of a red CI run with a misleading diagnosis.
- `ScanResult`'s docstring becomes true again without weakening any invariant: every
  artifact lands in exactly one of gap / unrecorded-exempt / verified, and `verified`
  then subdivides into clean, drifted, and drift-exempt.
- The summary line regains the distinction BP-100k-3's last clause demands. A reader of
  the RESULT line alone can tell a registration question from an excused content
  question.
- It follows the `unreadable` precedent exactly, so the next "belongs in no existing
  bucket" case has one worked pattern rather than two competing ones.
- `drift_exempt` becomes a greppable risk metric: how much drift the repo is currently
  excusing is one named number, not a quantity hidden inside `exempt`.

### Negative

- It changes a parsed output contract. Appending keeps every known consumer working,
  but any out-of-repo consumer that counts fields or anchors on end-of-line breaks, and
  this ADR cannot prove no such consumer exists — only that none was found in-repo.
- The RESULT line reaches eight fields. It is long, and a reader must now know that
  `exempt` and `drift_exempt` are disjoint rather than nested.
- Real migration cost in artifacts that are currently green and correct: an AC's
  criteria text, three test assertions, a test regex, a verdict table, and a known-issue
  entry, all of which must move in one commit (Decision §7).
- `check_build_drift.py` carries a column that is structurally always `0`, which is
  dead-looking output until that gate ever gains its own drift-exempt branch.

### Operational

- The one-commit requirement means `check-output-drift` is itself in the blast radius
  while the commit is being made: the gate's own templates are build inputs, so the
  change must be built and the deployed copy re-run before committing, per the repo rule
  that a hook's dependencies must be deployed before the hook is believed.
- Verification MUST be behavioral, per the standing repo rule and `BP-100k-3-iv`'s
  `it_requirements`: run the deployed gate as a separate process and read its stderr
  lines, RESULT line, and exit status. A grep of the gate source proves nothing here.
- The new identity assertions in Decision §6 are cheap to add to the existing
  subprocess-based fixtures in `test_drift_exempt_recorded_key.py`, which already
  synthesize one clean, one exempt-drifted, and one unexempt-drifted recorded key.
- This ADR starts at **Proposed**. No code change is authorised until it is promoted to
  Accepted.

---

## Alternatives

- **Leave the counting as it is and only correct `ScanResult`'s docstring.** Rejected.
  This was the cheaper outcome and was tested against the code rather than against
  intent. It fails because the double-count is asserted in two live tests, not only in
  prose: `test_bp_100k_5.py` asserts `verified + uncomparable == deployed population`
  and `test_bp_100k_3_i.py` asserts `uncomparable == count of UNCOMPARABLE: EXEMPT
  lines`. Making the docstring match the code would require weakening both — i.e.
  retiring a real population-accounting property of the gate — to legalise a count that
  nothing needs.

- **Remove the key from `verified` instead, keeping it in `uncomparable`.** Rejected.
  `verified` is incremented before the hash comparison, so it already counts ordinary
  drift violations; removing only the excused ones would make `verified` mean "clean" for
  one case and "compared" for every other. Carrying it through consistently would mean
  removing drift violations from `verified` too, which breaks `BP-100k-3-iv`'s
  `verified=3` clause and every `verified`-based population identity, for no gain.

- **Count it in `drifted` and rely on the verdict fields to decide blocking.**
  Rejected. `drifted` is `len(violations) + missing` and is the field a reader uses to
  decide whether a run was clean; a count there that deliberately does not block makes
  `drifted > 0` stop implying a non-zero exit — the precise ambiguity BP-100k-3 removed
  when it moved the verdict off total `uncomparable` onto `gaps`.

- **Count it in no field at all — report only the per-artifact line.** Rejected. An
  excusal reported on stderr but absent from every count is a finding that the summary
  line describes as a clean run, which is the "a check that cannot perform its check
  must not report a pass" defect this whole gate exists to remove, and the exact shape
  `docs/2b_direction_b_output_drift_detection.md` forbids ("every uncomparable case
  above must print a line and be counted in the RESULT summary, whether or not it
  blocks the commit").

- **Rename or widen `uncomparable` (e.g. to `excused`) so its documented meaning covers
  both cases.** Rejected. `uncomparable` is matched by name in the regex of at least
  fifteen in-repo consumers; renaming breaks all of them to fix a prose mismatch, and
  the widened field would then conflate a registration question with a content question
  — destroying at the summary layer the distinction `BP-100k-3-iv`'s `it_requirements`
  deliberately preserve at the per-artifact layer.

- **Insert the new column next to `exempt` rather than appending it last.** Rejected.
  Every in-repo consumer's regex is positional in its capture groups, so an insertion
  silently shifts the meaning of every group after it — `int(match.group(5))` would
  start reading a different field while still parsing successfully. This is why
  `unreadable` was appended last under B-2, and the module records appending as the
  convention for exactly this reason.

- **Revert the PR #1013 widening instead of counting it.** Rejected as a different
  decision, not as a bad idea. Whether a registry entry should be able to excuse a
  recorded key's content drift is Defect 1 of `KI-CG-20261008`, explicitly out of scope
  there, and already bounded by `BP-100k-3-v` (per key, ground-gated, any further
  widening must retire a named AC in the open). Blocking the counting fix on that larger
  question would leave two false documented contracts and two primed test failures
  standing for however long the larger question takes.

---

## References

- Known issue: [`KI-CG-20261008`](../../known-issues/commit-guardian/open-low-ki-cg-20261008-drift-exempt-recorded-key-widens-registry-and-double-counts.md)
  — Defect 2 is this decision; Defect 1 is explicitly out of scope.
- Acceptance criteria: `BP-100k-3` (registry and four-verdict vocabulary),
  `BP-100k-3-iv` (the behaviour; carries the same-commit amendment caveat),
  `BP-100k-3-v` (how narrow the suppression stays), `BP-100k-3-vi` (missing and
  unreadable are never excused), `BP-100k-5` (population accounting).
- Code: `templates/scripts/commit_guardian/_drift_exemptions.py` (`ScanResult`),
  `templates/scripts/commit_guardian/check_output_drift.py` (`_reconcile_recorded`,
  `_scan_output_files`, `_print_result_line`, `_verdict`, and the DRIFT-EXEMPT
  REPORTING docstring section that names this question as pending an ADR),
  `templates/scripts/commit_guardian/check_build_drift.py`.
- Reader-facing contract: `docs/2b_direction_b_output_drift_detection.md` (verdict table
  and RESULT line format).
- Origin: PR #1013, merged 2026-10-05 as `2d895308`. No originating ticket exists.
