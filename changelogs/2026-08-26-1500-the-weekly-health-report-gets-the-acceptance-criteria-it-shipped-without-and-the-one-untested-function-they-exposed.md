---
title: "docs(infrastructure): the weekly health report gets the acceptance criteria it shipped without, and the two coverage gaps they exposed"
date: "2026-08-26"
time: "15:00"
type: manual
components:
  - infrastructure
  - agent_telemetry
summary: "Retrofits AC traceability onto the weekly health report through the full PO/BA/IT-PO pipeline, and closes the coverage gap that enrichment exposed before marking anything done."
description: "Authors INF-500e and its seven-record subtree covering scripts/agent-health/weekly_health.py, which merged in PR #608 without AC traceability. Binding real test contracts exposed two coverage gaps — ac_birth_dates had no test at all, and the L1 had no end-to-end test — both closed against real temporary git repositories before any AC was marked done. Also corrects a test count overstated in the previous changelog entry."
breaking: false
---

## Entry

`scripts/agent-health/weekly_health.py` merged in PR #608 without acceptance criteria,
against the `/plan-feature` → `/build-ac` rule in `CLAUDE.md`. That gap was declared in
the previous entry rather than hidden, and this closes it — through the actual pipeline,
not by hand.

**What was authored.** `INF-500e` — *"One command tells you whether delivery is getting
healthier — and whether it is getting faster"* — is a new L1 under `INF-500`
(operational observability), with five L2s and two L3 technical constraints:

| id | covers |
|---|---|
| `INF-500e-1` | Delivery is scored on what was retracted, not only on what was claimed |
| `INF-500e-2` | An unobtainable figure reads as unknown, while a measured zero still reads as zero |
| `INF-500e-2-i` | A truncated merge history is unknown for the weeks it cannot reach, not a quiet period |
| `INF-500e-3` | A criterion keeps its identity and its age when it moves to another folder |
| `INF-500e-3-i` | An age that cannot be established is left out, not entered as zero days |
| `INF-500e-4` | Volume written is attributed to a language and a kind, so building is distinguishable from bookkeeping |
| `INF-500e-5` | The weeks compared are whole calendar weeks, oldest first, ending with the one in progress |

**The two gaps the pipeline found.** Binding each criterion to a test that really
executes it is what makes enrichment worth running, and here it paid twice — both times
catching a criterion that would have been marked done on evidence never touching the code
implementing it. That is precisely the phantom-done shape this store exists to prevent,
caught one step before it happened.

*The producer was untested.* `ac_birth_dates` — the function establishing a criterion's
first appearance by walking the git log — **had no test at all**. Every cycle-time test
injected a `births` mapping directly, proving the consumer while leaving the producer
unexercised, so `INF-500e-3`'s central clause (*"age is measured from first appearance,
not from the last time the file was written"*) was unproven. Four tests now drive it
against a real temporary git repository with controlled commit dates: a criterion edited
after creation keeps its original birth date, moving it into a feature folder does not
reset its age, the registry index is excluded, and a repository with no store yields an
empty index.

*The L1 had no end-to-end test.* Its claim is that **one** command answers both questions,
so no amount of unit coverage on the parts establishes it. Four more tests run
`build_report` against a real temporary repository and render the result, asserting all
three tiers plus the code-volume section are present, that the trust tier is rendered
before the velocity tier, that a criterion closed in a period is counted in that period,
and that absent telemetry produces a named reason rather than a 0% completion rate.

Only then was anything marked done.

**Evidence recorded.** All eight records carry `work_status: done` set through
`mark_ac_done.py` with `--test-root` enforcing the coverage gate — no hand-edited status
flips — plus `implemented_by` pointing at commit `d0fa881c` and the module, and 19
`# covers:` tags across a suite that grew from 49 tests to 62. The parent `INF-500.yaml`
is staged alongside its new child, since a hook only ever validates what is in the
commit's index.

**A disagreement between two gates, worth knowing about.** `mark_ac_done.py --test-root`
accepted the L1 `INF-500e` on the composite path (proof derived from its children), while
the `check-done-proof` pre-commit hook rejected the same record for having no direct
`# covers:` tag of its own. Two gates over the same question returning different answers
is a defect in one of them; here it pushed toward the better outcome, since writing the
end-to-end test the hook demanded was the right thing regardless.

**Correction to the previous entry.** The 2026-08-26 11:30 entry stated "54 unit tests
cover the pure computations and the honesty guarantees". 54 was the whole
`unit_tests/agent_health/` directory; 49 of those belong to this work and 5 are the
pre-existing telemetry failsafe tests. The correct figure for that entry was **49**. The
suite now stands at **58** in the directory, 53 of them this work's.

One shipped-code fix rides along: `--no-gh`'s help text still read "PR columns report
zero", describing behaviour that changed when unknown stopped rendering as zero. It now
reads "unknown, never zero".

**Declared limitation, carried into the records rather than resolved:** the lane-event
vocabularies remain unverified against real data, because nothing has yet emitted a lane
event (`KI-BO-012`). `INF-500e-2` records this as a live false-negative risk in shipped
code — if the names drift from what the fast lane eventually writes, the autonomy tier
will report "no lane data" while events are arriving.
