---
title: "A quarter of the AC-store suite is PyYAML, and the repo already knows the fix"
description: "Parsing the 4,635-file AC store costs 24.68s with yaml.safe_load and 1.86s with yaml.CSafeLoader, measured in one process. 44 scripts use the slow loader; one file already uses the fast one and documents why. The required AC-store CI gate is 23.16s of parsing."
type: explanation
status: active
created: 2026-10-05
last_updated: 2026-10-05
components:
  - ac_store
  - testing_quality
---

# A quarter of the AC-store suite is PyYAML

Part 3 of five. [Part 1](2026-10-05-slowest-tests-and-what-to-do-about-them.md)
gives the ranking.
[Part 2](2026-10-05-slowest-tests-and-what-to-do-about-them-2-the-speed-programmes-own-tests.md)
covers TQ-600a's own tests.
[Part 4](2026-10-05-slowest-tests-and-what-to-do-about-them-4-per-item-verdicts.md)
gives per-item verdicts.
[Part 5](2026-10-05-slowest-tests-and-what-to-do-about-them-5-skipping-and-run-once.md)
answers the skipping and run-once questions.

## 1. The measurement

Run today in one process against the real store on this worktree. Probe:
`/home/henzeh/tq600a1-backup/an_probe_store.py`; results in
`an_probe_store.jsonl`.

| step | time | detail |
|---|---|---|
| `rglob("*.yaml")` | 0.048 s | **4,635 files** |
| read every file | 0.118 s | 23.8 MB |
| parse, `yaml.safe_load` | **24.683 s** | 4,635 parsed |
| parse, `yaml.CSafeLoader` | **1.863 s** | 4,635 parsed |
| **speedup** | **13.25x** | `CSafeLoader` present |

**I/O is 0.17 s. Parsing is 24.68 s.** 99.3% of a store sweep is PyYAML's
pure-Python parser, and the C parser is sitting in the same installed library.

Two end-to-end confirmations, both measured today:

| entry point | time |
|---|---|
| `python scripts/ac_store/validate_ac_schema.py docs/acceptance-criteria` | **23.16 s** (`OK: all 4634 … valid`) |
| `python scripts/ac_store/generate_ticket_from_ac.py --ac BP-1100g-1 --dry-run` | **24.00 s** |

Both land within 6% of the bare parse cost. These programs are, to a first
approximation, PyYAML with a small amount of logic attached.

## 2. The repo found this once and did not generalise it

`scripts/render_effective_prompt.py:56-57`:

```python
#: slow (~2500 files → minutes on SafeLoader, ~1s on CSafeLoader).
_YAML_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
```

That is the fix, already written, with the `getattr` fallback that makes it
safe on a build of PyYAML without libyaml. It is used in exactly **one** file.

Meanwhile `yaml.safe_load` appears in **44 files under `scripts/`**, including:

- **26 under `scripts/ac_store/`** — `validate_ac_schema.py`, `scan_ac_store.py`,
  `_gtfa_store.py`, `ac_coverage_resolver.py`, `declared_files.py`,
  `_done_proof_phase_helpers.py`, `epic_ac_store.py`, `mark_ac_done.py`, …
- **30 under `scripts/commit_guardian/`** — `check_done_proof.py`,
  `check_ac_parent_covered_by.py`, `_ac_store_index.py`, `check_ac_limits.py`,
  `check_ac_governance.py`, `_reachability_inventory.py`, …

Plus **20 test files** that do their own unfiltered `rglob("*.yaml")` sweep of
the real store, among them four in the top-20 by cost:
`test_authored_test_spec_survives_generation.py`, `test_bo_2900g_2.py`,
`test_derived_test_reachability_floor.py`, `_uxp_300_store.py`.

## 3. Why this escaped notice for so long

Three reasons, and each is a reusable lesson.

**It is not a build, so the build-focused analysis could not see it.** The
whole ten-minute-target set anchors on `build.py` invocation counts. A test
that spawns `generate_ticket_from_ac.py` looks nothing like a test that spawns
`build.py` in a grep, and costs 24 s instead of 15 s. The 77-build-site census
was accurate and simply counted the wrong noun.

**Each individual call site is defensible.** `yaml.safe_load` is the correct,
secure, recommended API. There is no code smell to notice. The cost is entirely
in the store having grown to 4,635 files — it was **3,340 in August**, a 39%
growth in seven weeks — and nothing re-measures when a store grows.

**The one team member who did notice wrote it down in a comment in one file.**
A `#:` comment in `render_effective_prompt.py` is not a mechanism. The repo has
no shared YAML-loading helper, so the discovery had nowhere to live except the
file where it was made.

## 4. What the change is, concretely

A single shared helper plus a mechanical substitution:

```python
# scripts/ac_store/_yaml_fast.py (or an existing shared module)
import yaml

#: libyaml-backed loader when available; 13.25x faster on the AC store
#: (measured 2026-10-05: 4,635 files, 24.68s -> 1.86s). Falls back to the
#: pure-Python loader on a PyYAML build without libyaml.
SAFE_LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)


def safe_load(text):
    return yaml.load(text, Loader=SAFE_LOADER)
```

`CSafeLoader` and `SafeLoader` implement the same YAML 1.1 safe schema, so the
parsed object is the same. The two differences worth knowing before anyone
calls this a free lunch:

- **Error types.** `CSafeLoader` raises `yaml.YAMLError` subclasses, as
  `SafeLoader` does, but the messages and some mark positions differ. Any test
  asserting on a parser error *string* would need updating. Worth grepping for
  before the change, not after.
- **Duplicate-key and anchor edge cases.** Behaviour is equivalent for this
  store's content, but "equivalent on our content" is a claim that needs a
  proof, not an assertion.

**The proof that makes this safe is cheap and should be the AC**: parse the
entire real store with both loaders and assert the resulting objects are
`==`, file by file. That is a ~27 s one-off test that can live in the suite as
a standing differential guard, and it converts the whole change from "trust me"
to "measured, 4,635 of 4,635 identical".

## 5. What it is worth

**It is the only lever in this analysis that pays on all four surfaces.**

| surface | today | after | note |
|---|---|---|---|
| `AC store valid` required CI check | 23.16 s | ~3 s | required gate on every PR |
| `check_done_proof` / AC pre-commit hooks | seconds per commit | near-zero | every developer, every commit |
| the ~195 test files touching store entry points | 24 s per subprocess | ~2 s | Part 5 §2 sizes this |
| `build.py` | −2.2 s/build (prior analysis, item 7) | | `template_compiler.py:123` |

A conservative suite-level estimate. In the measured 5,525 tests, the
identified store-sweeping cluster (`test_authored_test_spec_survives_generation`,
`test_acs_100i_7_store_wide_pass`, `test_acs_100i_7_i_pass_is_real`,
`test_bo_2900g_2`, `test_derived_test_reachability_floor`,
`test_scan_ac_store_cycle`, `test_tkt_600b_2`, `test_uxp700d2_i_live_store`,
`test_uxp_700d_3_i`, `test_uxp_700d_4`, `test_uxp_700a_1_ii`, `test_uxp_300`,
`test_prioritize_ac_integration`) totals **~560 s**. If parsing is ~90% of it,
**~500 s (~8 min) goes away** for a change that alters no assertion anywhere.

And unlike the build levers, this one **does not decay as the migration lands**
— the prior analysis's central sequencing worry. The AC store is not a build
artifact. It gets *larger*: 3,340 files in August, 4,635 in October. Every
month this is not done, it is worth more.

## 6. The second-order point

There is a reason to care beyond the seconds, and it is named in
`test_authored_test_spec_survives_generation.py:183-188`:

> the store holds 3,340 YAML files and a full `yaml.safe_load` sweep takes
> ~36 s. The done-proof gate runs an AC's linked tests under a **60 s budget**,
> so an unfiltered sweep here does not merely make the suite slow — it makes
> the gate report every linked test as "not run", which reads as a **coverage
> failure rather than a timeout**.

That is the parser cost producing a **false phantom-done signal**. The author
worked around it with a raw-text pre-filter (0.12 s to narrow 4,635 files to
743 candidates) — a good workaround, and one that would be unnecessary at 1.86 s
a sweep.

It is also a ratchet. The store grew 39% in seven weeks. The budget did not.
Every test that currently squeaks under 60 s is on a timer, and when one trips
it will present as "this AC has no passing test", which is the exact signal
this repo's whole guardrail layer exists to make trustworthy. **Making the
parse 13x faster is not a performance optimisation here. It is buying back the
headroom a correctness gate depends on.**
