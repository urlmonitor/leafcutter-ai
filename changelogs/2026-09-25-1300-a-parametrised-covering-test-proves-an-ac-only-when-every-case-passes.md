---
title: "A parametrised covering test proves an AC only when every case passes"
date: "2026-09-25"
time: "13:00"
type: manual
components:
  - ac_store
summary: "The done-proof oracle now reads every case of a parametrised covering test. Before, it read only the first nodeid pytest reported for the function, so a test with case [0] passing and case [1] failing proved its AC done — a false green on the required CI done-proof gate. Any non-passing case now makes the covering test non-passing and is named in the refusal; an all-passing parametrised test still proves the AC, and same-file matches still take precedence over name-only matches."
description: "Covers ACS-200f-2: a parametrised covering test proves an AC only when every one of its cases passes. Root cause: _find_nodeid_for_test in scripts/ac_store/done_proof.py returned the first nodeid whose function name matched, and _classify_outcomes read only that nodeid's outcome, so later parametrised cases were never considered. A new helper, _find_nodeids_for_test, collects every matching case (same-file matches preferred as a group, as before), and _find_nodeid_for_test now returns a non-passing case whenever one exists. Its single-nodeid contract is unchanged, so the fast lane's red-baseline check, which shares the helper, gets the same fix. Known issue: KI-ACS-20260925-done-proof-parametrised-first-match. Regression tests in unit_tests/ac_store/test_find_nodeid_for_test.py cover both result orders, the all-passing case and same-file precedence; a mutation proof (fix reverted, test red; restored, test green) was run before commit."
commits: [9fa4c65d]
breaking: false
---

## Entry

The done-proof oracle judged a parametrised covering test by the first case
pytest reported. A test tagged `# covers: <AC>` with `test_b[0]` passing and
`test_b[1]` failing therefore proved the AC done, so the required CI
done-proof gate could pass an AC whose own test was partly failing.

`_find_nodeid_for_test` now considers every matching case through the new
`_find_nodeids_for_test` helper and returns a non-passing case whenever one
exists. The failing case is named in the refusal, the verdict no longer
depends on the order pytest reports cases in, and an all-passing
parametrised test still proves its AC. The fast-lane red-baseline check
uses the same helper and inherits the fix.
