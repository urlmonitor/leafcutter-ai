---
title: Requirements written for a nightly test run that holds pull requests while it is failing
date: "2026-10-08"
time: "13:00"
type: manual
components: 
  - testing_quality
summary: "Slow tests that no longer run on every pull request will run each night instead. Ten requirements describe how a failing night is flagged in one place, how every pull request is held until it is fixed, and how the pull request that carries the fix is let through."
description: "Adds TQ-600a-13-ii through TQ-600a-13-xi beneath TQ-600a-13, authored by the business analyst and technically enriched by the IT product owner. A scheduled nightly run executes the tests the default run now excludes, re-runs only first-run failures once, and names a test that passed only on retry rather than hiding it. A failing night opens a single GitHub issue labelled nightly-red, carrying the failing test ids, a log link and the commits merged since the last green night; a further red night comments on it rather than opening another, and a green night closes it. A run that does not finish, including a run that collects no tests, is never treated as green. Every pull request runs a check named Nightly suite status that reads that one issue, costs a single API read and runs no tests, and fails while the flag is open, posting one comment that it updates rather than repeats. A pull request that declares it fixes the open issue, or carries a nightly-fix label, is let through, so the fix itself is never blocked. The check fails closed when it cannot read the flag, distinguishing that from a flag that is open. Until the check is added to the repository's required checks by hand, it is described as advisory, never as protecting main. No step may commit, push or open a pull request to fix a failure automatically. The design puts all decision logic in small Python modules and keeps the workflow files thin, so every requirement is tested by calling the modules against a recording fake of the GitHub API; the family's tests are estimated at a few seconds in total. Several design questions are left explicitly open for a decision, including whether a pull request can release its own hold under the default trigger."
---

## Entry
