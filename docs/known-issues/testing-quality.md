---
title: "Known issues — testing-quality"
description: "Open, observed defects in the testing-quality component: the agent eval harness with its scoring and threshold gates, plus the test-isolation and verification-method defects that make a suite report the wrong answer — stale-module shadowing, incomplete fixtures, self-mirroring oracles, and verification that never asks what invokes the code. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-09-14
components:
  - testing_quality
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/how-to/prove-ac-done.md
---


# Known issues — testing-quality

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-TQ-NNN` section using the next free number.
Nothing here is generated — edit it by hand. Fill in what you actually know; an issue
recorded with a thin `Evidence` line is far better than one not recorded.

**Hitting an existing issue.** Increment `Occurrences` and update `Last seen`. Do not
add a duplicate entry. Occurrences is an escalator, not the score — a blocker seen once
outranks an annoyance seen ten times.

**Severity** is `blocker` (work cannot land) / `high` (silent wrong behaviour) /
`medium` (real but survivable) / `low` (noise, dead code, cosmetics).

**Closing an issue.** When the fix lands, delete the section and reference the issue id
in the commit message. If it earns real work, author an AC for it and note the AC id in
`Status` — this file is a capture surface, not a replacement for the AC store.

---

## How this register is stored

This file is an **index**. Each known issue is its own file under [`testing-quality/`](testing-quality/), named `<status>-<severity>-<ki-id>.md`, so the directory listing answers "is anything open, and how bad" without opening anything:

```
ls docs/known-issues/testing-quality/open-blocker-*   # anything critical open?
ls docs/known-issues/testing-quality/open-*           # everything still live
```

Severity in the **filename** is a three-level index bucket (`blocker` / `high` / `low`). The original grading is preserved verbatim on each entry's own `**Severity:**` line — the bucket never overwrites it. `critical` indexes as `blocker`; `medium` indexes as `low`.

Fixed issues move to [`testing-quality/resolved/`](testing-quality/resolved/) and are no longer listed as open. They are kept, not deleted.

**Open: 20** (1 blocker, 11 high, 8 low) · **Resolved: 3**

## Open

| Severity | Issue | File |
|---|---|---|
| `blocker` | KI-TQ-007 — Six review rounds verified a component without once asking what invokes it | [open-blocker-ki-tq-007.md](testing-quality/open-blocker-ki-tq-007.md) |
| `high` | KI-TQ-001 — An unanswered eval row scores as an all-negative prediction, so a dead agent's floor is not zero | [open-high-ki-tq-001.md](testing-quality/open-high-ki-tq-001.md) |
| `high` | KI-TQ-002 — The CI eval job reports missing credentials as a low quality score | [open-high-ki-tq-002.md](testing-quality/open-high-ki-tq-002.md) |
| `high` | KI-TQ-004 — Bare-name `sys.modules` caching lets a stale deployed copy shadow the canonical module for a whole pytest session | [open-high-ki-tq-004.md](testing-quality/open-high-ki-tq-004.md) |
| `high` | KI-TQ-005 — Fixtures that never built the collection they assert over, three times in one epic | [open-high-ki-tq-005.md](testing-quality/open-high-ki-tq-005.md) |
| `high` | KI-TQ-006 — A matcher widening measured by its own author's grep: estimated one false positive, actual twenty-three | [open-high-ki-tq-006.md](testing-quality/open-high-ki-tq-006.md) |
| `high` | KI-TQ-010 — Nothing in the build pipeline asks whether a passing test is able to fail, and for a negative control that is the only question that matters | [open-high-ki-tq-010.md](testing-quality/open-high-ki-tq-010.md) |
| `high` | KI-TQ-011 — The AC xfail-masking plugin is disabled on the only gate that blocks, so a red baseline for a not-done AC is unmergeable — and where masking does apply it makes the local run exit 0 | [open-high-ki-tq-011.md](testing-quality/open-high-ki-tq-011.md) |
| `high` | KI-TQ-20260831-mutation-probe-lands-in-the-wrong-copy — a mutation proof injected into `templates/` proves nothing, because the tests import the build output — and it fails green | [open-high-ki-tq-20260831-mutation-probe-lands-in-the-wrong-copy.md](testing-quality/open-high-ki-tq-20260831-mutation-probe-lands-in-the-wrong-copy.md) |
| `high` | KI-TQ-20260901-1655 — A red-baseline gate cannot tell "red because the feature is missing" from "red because the test asserts against a stub defined in the test file", and the second kind is unsatisfiable — one of them blocked a completed seven-AC build | [open-high-ki-tq-20260901-1655.md](testing-quality/open-high-ki-tq-20260901-1655.md) |
| `high` | KI-TQ-20260907-agent-eval-gate-has-never-evaluated-an-agent — it fast-passes when nothing is affected and dies on a missing API key when something is | [open-high-ki-tq-20260907-agent-eval-gate-has-never-evaluated-an-agent.md](testing-quality/open-high-ki-tq-20260907-agent-eval-gate-has-never-evaluated-an-agent.md) |
| `high` | KI-TQ-20260908-0900 — The agent-eval harness reports "the CLI could not be launched" as a 22% quality score, and the pre-commit gate built on it cannot be satisfied in any fresh worktree | [open-high-ki-tq-20260908-0900.md](testing-quality/open-high-ki-tq-20260908-0900.md) |
| `high` | KI-TQ-20260914-1050 — the fast lane's green gate reports a pytest timeout as a list of failing test nodeids, so a budget overrun is indistinguishable from broken code — and the distinguishing machinery that exists for exactly this is discarded one layer below | [open-high-ki-tq-20260914-1050.md](testing-quality/open-high-ki-tq-20260914-1050.md) |
| `low` | KI-TQ-003 — The eval staleness gate asks you to stage a file that is gitignored | [open-low-ki-tq-003.md](testing-quality/open-low-ki-tq-003.md) |
| `low` | KI-TQ-008 — A repository-global tree-purity guard false-positives under concurrent agents | [open-low-ki-tq-008.md](testing-quality/open-low-ki-tq-008.md) |
| `low` | KI-TQ-009 — A test-local oracle that duplicated the production bug it was written to detect | [open-low-ki-tq-009.md](testing-quality/open-low-ki-tq-009.md) |
| `low` | KI-TQ-013 — `git commit` in a temp fixture forks a background auto-gc, which races `rmtree` at teardown and fails the required CI suite at random | [open-low-ki-tq-013.md](testing-quality/open-low-ki-tq-013.md) |
| `low` | KI-TQ-20260907-0940 — A reachability fixture symlinks the package into its scratch workspace where the real consumer layout is a directory | [open-low-ki-tq-20260907-0940.md](testing-quality/open-low-ki-tq-20260907-0940.md) |
| `low` | KI-TQ-20260908-node-check-and-xfail-masking-agree-on-a-broken-script — `node --check` cannot prove the engine can load a workflow script, and a bare `pytest` on a not-done AC cannot distinguish pass from masked failure — together they nearly verified a script the engine could not run at all | [open-low-ki-tq-20260908-node-check-and-xfail-masking-agree-on-a-broken-script.md](testing-quality/open-low-ki-tq-20260908-node-check-and-xfail-masking-agree-on-a-broken-script.md) |
| `low` | KI-TQ-20260914-tempdir-cleanup-race-fails-a-green-test-run — a real-git fixture's teardown races its own `.git/objects` and fails a suite in which every assertion passed | [open-low-ki-tq-20260914-tempdir-cleanup-race-fails-a-green-test-run.md](testing-quality/open-low-ki-tq-20260914-tempdir-cleanup-race-fails-a-green-test-run.md) |
| `low` | KI-TQ-20260914-test-fixtures-hand-enumerate-their-production-dependencies — the deploy-manifest failure mode one layer down, where the error message names something other than its cause | [open-low-ki-tq-20260914-test-fixtures-hand-enumerate-their-production-dependencies.md](testing-quality/open-low-ki-tq-20260914-test-fixtures-hand-enumerate-their-production-dependencies.md) |

## Resolved

| Severity | Issue | File |
|---|---|---|
| `high` | KI-TQ-012 — A fixture that sandboxes with `git worktree add` sets its identity in the *real* repository's config, and every worktree and every session inherits it | [resolved-high-ki-tq-012-a-fixture-that-sandboxes-with-git.md](testing-quality/resolved/resolved-high-ki-tq-012-a-fixture-that-sandboxes-with-git.md) |
| `high` | KI-TQ-012 — A test fixture reassigns the real repository's commit identity, and every commit made afterwards is authored by the fixture | [resolved-high-ki-tq-012-a-test-fixture-reassigns-the-real.md](testing-quality/resolved/resolved-high-ki-tq-012-a-test-fixture-reassigns-the-real.md) |
| `high` | KI-TQ-20260901-1310 — The red-baseline gate's 60-second pytest budget silently negotiates the AC's required test shape down to whatever fits | [resolved-high-ki-tq-20260901-1310.md](testing-quality/resolved/resolved-high-ki-tq-20260901-1310.md) |
