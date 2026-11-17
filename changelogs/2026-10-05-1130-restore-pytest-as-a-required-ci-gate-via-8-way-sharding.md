---
title: "Restore pytest as a CI gate via 8-way sharding"
date: "2026-10-05"
time: "11:30"
type: manual
components: 
  - testing_quality
  - build_pipeline
  - commit_guardian
summary: "The automated test suite runs on pull requests again, split across 8 parallel jobs so a full pass takes minutes instead of the roughly 53-minute run that got it switched off. It reports but does not yet block — making it blocking again is a separate decision, and the check name it needs is already in place."
description: "5 commits on ci/shard-pytest-suite. ci(testing-quality) re-enables the `test` job as an 8-way pytest-split matrix (`test-shard`) feeding a `test` aggregator that carries the stable check name `Test suite (pytest)`, plus a five-part analysis under docs/analysis/ and a new .github/workflows/test-durations.yml. Two fix(ci) commits correct the durations-completeness guard to measure the collected test count instead of a stale constant, and correct the concurrent-job estimate to a measured count against GitHub's job cap. One merge from origin/main. One docs(commit-guardian) commit files known issue KI-CG-20261005."
pr: 1011
commits: 
  - bf308893
  - 7ead1cf5
  - de515f02
  - 807fd45e
  - c4174a7f
---

## Entry

The `test` job had been `if: ${{ false }}` and off the main-branch required-check
list since 2026-10-02, after a single full run took ~53 minutes. Since that date
main had no behavioural CI gate at all — every other required check (lint,
component vocab, done-proof, changelog, AC store) is static. This restores a
behavioural gate.

It **reports** rather than blocks: the aggregator is informational until the
owner promotes it in the branch ruleset. That promotion is deliberately left as
a separate decision, which is why the stable check name is put in place now —
so promoting it later needs no workflow edit.

`test` is now an 8-way `pytest-split` matrix (`test-shard`) feeding a `test`
aggregator job that carries the stable check name `Test suite (pytest)` — the
one the required list used before 2026-10-02 — and is green only when every
shard is, via `needs.test-shard.result` with `if: always()` so a failed shard
reports instead of being skipped. The shards partition the collected set with
`fail-fast: false`: every test still runs exactly once, on exactly one shard.
Nothing is skipped, deselected, or sampled.

Known gap: `.github/test_durations.json` is not included in this change, so
shards currently split by test count rather than measured duration and will be
uneven until the file lands — a balance problem, never a coverage problem. It
cannot be generated locally: five pinned dev dependencies (pydantic, langgraph,
langchain, neo4j, langfuse) are absent from a typical local environment, so 163
test modules fail to import and collect zero tests outside CI. The new
`.github/workflows/test-durations.yml` generates the file on a runner where
those dependencies are installed. Its own completeness guard was then corrected
to require ≥95% of a `--collect-only`-measured count rather than trusting a
hardcoded 5318, after that stale constant let a short, incomplete merged
durations file pass the guard it existed to fail.

Two measurements already circulating in this work are corrected here: the
intra-package closure guard costs 11.84s of a 14.81s build (80%), not the
previously reported 39.07s of 50.38s — the percentage share held because both
numbers were inflated together by fleet contention, not because the absolute
figures were right. And the suite collects 7,604 tests, not the 5,318 figure in
CLAUDE.md. A later commit also replaced an estimated "~12-14 concurrent jobs"
rationale with a measured count: a PR now starts 21 slots from this repo's own
workflows plus 4 more from sibling workflows, 25 at peak against a 20-job
account cap — the 8-shard matrix is kept anyway because the overflow is
short-lived static jobs that free their slots within minutes.

Also included: a five-part analysis under
`docs/analysis/2026-10-05-pytest-ten-minute-target*.md`, and known issue
`KI-CG-20261005`, filed (not fixed, to keep this branch's review narrow) against
the AC schema validator's `declares_side_effect` derivation, which can read a
match starting from the Given clause and carries an unbounded `deployed to`
pattern — both can misread ordinary prose as asserting a durable side effect.
