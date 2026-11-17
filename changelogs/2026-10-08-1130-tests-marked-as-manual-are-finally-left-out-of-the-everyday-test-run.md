---
title: Tests marked as manual are finally left out of the everyday test run
date: "2026-10-08"
time: "11:30"
type: manual
components: 
  - testing_quality
summary: "Forty-three slow tests were named as manual and described as skipped by default, but nothing actually skipped them. They are now genuinely left out of the everyday run and can still be run on request, which takes about a thousand seconds off every full test run."
description: "Implements TQ-600a-13 by making the behaviour match what the documentation already claimed. A test whose name ends in _MANUAL is now marked manual automatically by a small pytest plugin, and the default run deselects every manual test, so the suffix itself is the rule and a newly added manual test needs no list or decorator to be excluded. The tests still exist and still run on request with pytest -m manual, and the default and manual collections are proven to split the suite exactly in two, with nothing lost between them. On the current suite that removes 43 tests and roughly 1,004 seconds, about 16 per cent of a full run. The proof is behavioural: every check collects the suite in a real pytest subprocess rather than reading the configuration, because this repository previously carried a pytest option that looked correct and did nothing. Two checks prove the comparison can fail, one against a project with no mechanism at all and one against a selection option that pytest accepts and ignores. The documentation now describes the real mechanism, and one guide that told readers to opt in with a keyword filter, which would now match nothing, has been corrected. There is a known gap, recorded in the documentation: these 43 tests now run nowhere in CI until a scheduled nightly run exists to catch failures in them. That run is being designed separately, and this change was deliberately sequenced first."
---

## Entry
