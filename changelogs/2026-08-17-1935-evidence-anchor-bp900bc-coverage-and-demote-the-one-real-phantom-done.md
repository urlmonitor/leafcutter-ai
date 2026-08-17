---
title: "fix(ac-store): evidence-anchor BP-900b/c coverage; demote the one real phantom-done"
date: "2026-08-17"
time: "19:35"
type: manual
components:
  - build_pipeline
summary: "Adds five evidence-anchored covers tags to the tests that genuinely back BP-900b/c ACs, and demotes BP-900b-3 from done to todo because every test touching its guard mocks it away."
description: "check-done-proof found no '# covers:' tag anywhere for six BP-900 ACs marked work_status: done. An ac-audit (mechanical citation map, green-test run, two skeptical per-group verification passes) found five of the six are genuinely implemented and genuinely covered — the covering tests exist and are load-bearing, they were simply tagged for other ACs, so a grep-based gate could not see them. Adds those five covers tags next to the assertions that actually back each AC and narrows covered_by from bare filenames to specific test functions. BP-900b-1-1's coverage was confirmed empirically: five references in the real package resolve only via EXTERNAL_DEPENDENCY_ALLOWLIST, so deleting the allowlist union turns its test red. BP-900b-3 is the one real gap and is demoted to todo — its guard is wired into build.py main() at lines 1518-1520, but every test that touches it at build level mocks it to return 0, so the suite stays green whether or not the 'return 1' propagation exists; its test_spec is added with an explicit instruction not to mock the guard. Three further audit findings are recorded in AC notes rather than dropped: BP-900b-1 scans templates/ source rather than the compiled output its criteria describe and its sys.path.insert regexes match nothing real; BP-900b-2's derive-do-not-hardcode requirement is only partly met; BP-900c-2's stdout-clean and exact-three-keys clauses are unasserted. Also converts it_requirements to the structured object form on the six touched ACs. Merged via PR #460."
pr: 460
commits:
  - 7617a2c46
---

## Entry

The AC store's own done-proof gate caught six BP-900 ACs claiming `done` with no
covering-test tag. Rather than satisfying the gate by pasting tags on plausible
tests, an `ac-audit` established per-AC evidence first.

Five were true positives for the *gate* but false alarms for the *product*: the
behaviour is implemented and really is covered, by tests tagged for neighbouring
ACs. Those five now carry evidence-anchored `# covers:` tags and function-level
`covered_by` entries.

One — `BP-900b-3` — was the genuine article. Its guard is correctly wired into
`build.py` `main()`, but every build-level test mocks the guard to return 0, so
deleting the `return 1` propagation breaks nothing. It is back to `todo` with a
test contract that forbids mocking the thing under test.
