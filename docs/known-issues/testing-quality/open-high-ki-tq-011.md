---
title: "KI-TQ-011 — The AC xfail-masking plugin is disabled on the only gate that blocks, so a red baseline for a not-done AC is unmergeable — and where masking does apply it makes the local run exit 0"
description: "KI-TQ-011 — The AC xfail-masking plugin is disabled on the only gate that blocks, so a red baseline for a not-done AC is unmergeable — and where masking does apply it makes the local run exit 0"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
---

# KI-TQ-011 — The AC xfail-masking plugin is disabled on the only gate that blocks, so a red baseline for a not-done AC is unmergeable — and where masking does apply it makes the local run exit 0

> One known issue, split out of `docs/known-issues/testing-quality.md` on
> 2026-09-14. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 1 (18 tests across 8 files, one PR)
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `scripts/ac_store/pytest_ac_enforcement.py` (`_strict_mode`, `pytest_runtest_makereport`,
  `pytest_terminal_summary`); `.github/workflows/ci.yml` → job `test` ("Test suite (pytest)"),
  `env: AC_ENFORCE_STRICT: "1"`

**Symptom.** Two mechanisms in this repository disagree about what a failing test covering a
not-done AC means, and each is individually reasonable:

- `pytest_ac_enforcement` downgrades such a failure to `xfail`. Its docstring states masking is
  **opt-out** — the default is to mask.
- CI's `test` job sets `AC_ENFORCE_STRICT: "1"`, which opts out **globally**. That job is a
  required status check, with a comment stating the intent plainly: *"a PR carrying a failing test
  now fails this check and cannot merge."*

The plugin's default therefore never applies in the one place a test outcome decides anything. It
masks only in local and ad-hoc runs.

**Measured, same file, same commit** (`unit_tests/build_orchestration/test_bo2400e_4_crlf_preservation.py`,
`54ca1f32f`):

| run | outcome | exit code |
|---|---|---|
| local, no flag | `3 xfailed` | **0** |
| CI, `AC_ENFORCE_STRICT=1` | 3 failures, required check red | non-zero |

**Consequence 1 — a red baseline cannot be merged.** The AC-driven practice authors a failing test
for an AC before the fix exists. That test cannot reach `main`: the required gate rejects it, no
matter that its redness is the point. The evidence either sits on a branch collecting merge
conflicts or is deleted. Observed on PR #602 — 18 red-baseline tests across 8 files, every one
green-by-xfail locally and every one a hard failure in CI run `32969277018`.

**Consequence 2 — where masking *does* apply, it inverts the local signal.** A masked run exits
**0** and prints `3 xfailed`. A developer cannot distinguish "the suite is clean" from "three
genuinely-broken behaviours are recorded and hidden" without reading a summary line that competes
with ~4,000 other results. The mechanism built so a known defect is not lost is the same mechanism
that makes it invisible to anyone not looking for it.

**Why this is not simply "CI is right".** The strict flag is a good decision and this entry does
not argue against it. The defect is that **both mechanisms are maintained while only one can ever
apply.** The plugin carries masking logic, a terminal-summary reporter, and its own test files
(`unit_tests/ac_store/test_pytest_ac_enforcement.py`,
`test_pytest_ac_enforcement_strict_on_ci.py`) for a behaviour the only blocking consumer switches
off. Either the masking default is wrong, or the global opt-out is too broad. Holding both means
the documented default is a fiction, and a practice built on it — author the red baseline first —
silently has no merge path.

**Fix direction.** Not "loosen the gate."

1. **Make the red baseline explicit rather than inferred.** `@pytest.mark.xfail(strict=True,
   reason="<AC-ID> red baseline — defect unfixed")` is honest in both environments: pytest core
   handles it before the plugin sees a failure, so it reports `xfail` under `AC_ENFORCE_STRICT=1`
   too, and `strict=True` turns the day-the-fix-lands XPASS into a failure that forces the mark's
   removal. The baseline retires itself instead of rotting.

   **Verified, not assumed** — two marked probes covering a not-done AC, run under
   `AC_ENFORCE_STRICT=1`:

   | probe | outcome under the strict flag |
   |---|---|
   | marked, body fails | `xfailed` — the mark survives the flag |
   | marked, body passes | `FAILED [XPASS(strict)]` — forces the mark's removal |

   The plugin logs `NOT masked (AC_ENFORCE_STRICT=1)` for the second and stays out of the way of
   the first, because `pytest_runtest_makereport` only ever intercepts a *failing* report and
   pytest core has already resolved the marked one.

   This cannot create phantom-done: `done_proof` already treats XFAIL as **not** satisfying the
   done gate (see `unit_tests/ac_store/test_bo2500a_done_proof.py` — an all-xfail run exits 0 and
   is still not done-eligible), so a marked baseline can be merged without becoming evidence.
2. **Then decide the plugin's fate on the numbers.** With explicit marks carrying the red
   baselines, count what dynamic masking still masks. If the answer is "nothing anyone relies on",
   delete it — a default that never applies where it matters is worse than no default, because it
   reads as a safety net.
3. **Whatever is kept, make a masked run non-silent** — a masked failure should not produce exit 0
   with no distinguishing signal beyond one summary line.

**Related.** `KI-TQ-010` (the red baseline is the pipeline's only falsifiability check — this entry
is about that same baseline being unable to merge). Project memory *"Red-baseline gate: one-red
rule"* and *"pytest xfail-masking"* record earlier encounters with the same plugin from the
opposite direction.

**Pattern:** two correct-looking mechanisms whose defaults contradict, where the one that loses is
the one every practice is written against.

---
