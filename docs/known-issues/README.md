---
title: "Known Issues Register"
description: "Index of open, reproducible defects in this package that are not yet fixed, organised by component. Each entry states severity, how to detect the issue, any workaround, and a suggested fix."
type: reference
status: active
created: 2026-08-19
last_updated: 2026-09-10
components:
  - infrastructure
related_docs:
  - docs/pre-commit-hooks.md
  - docs/build-pipeline.md
  - docs/architecture/agent_delivery_workflows.md
---

# Known Issues Register

Open, reproducible defects in this package, organised by component. One file per
component; each entry carries a stable `KI-<COMPONENT>-<n>` id.

This register exists because a defect found and then only mentioned in a commit
message is, in practice, lost. Several issues below are of a kind the package is
explicitly built to prevent — a gate that never runs, a check that silently
skips, a driver that commits past its own blockers — so leaving them
undocumented would be self-defeating.

## What belongs here

An entry should be **open**, **reproducible**, and **observed** rather than
suspected. Each states:

- **Severity** and why
- **Detection** — how to tell it is happening, which for silent-failure defects
  is the load-bearing part
- **Workaround**, if any
- **Suggested fix**

Fixed issues are removed, not marked resolved — git history is the record. The
one exception is a short "fixed, recorded for context" section where knowing an
issue *used to* exist explains present code.

## Index

Counts recounted 2026-08-31. This table had listed five of the thirteen files and was stale
by roughly an order of magnitude on the two largest — an index nobody can trust is worse than
no index, since it reads as "there are five commit-guardian issues" when there are 35.

Recounted again later the same day and already 20 low across six rows, because several
same-day PRs each appended entries without touching this table. Every count here is
`grep -c '^### KI-'` over the file, so it is reproducible in one command — if you are reading
this table and it matters, re-run the count rather than trusting the number. The drift is not
a one-off; a table maintained by hand beside files appended by many agents will always lag.

Recounted 2026-09-07 at merge time by `grep -c '^### KI-'` over every file in this
directory. **Two concurrent branches each recounted this table and both were already
wrong by the time they merged** — one said 224, the other 237, and the true figure at the
moment they met was 239. Neither was careless: each counted correctly, and then the other
landed. That is the failure mode this table has, and no recount fixes it, because the
defect is that a hand-maintained total races every append. Re-run the count; do not read
the number.

**The counting problem above is now answered by the filesystem.** On 2026-09-14 every
register was split into one file per issue, named `<status>-<severity>-<ki-id>.md` under a
per-component directory. Nothing is hand-counted any more — ask the directory:

```bash
ls docs/known-issues/*/open-blocker-* | wc -l     # blockers, everywhere
ls docs/known-issues/commit-guardian/open-* | wc -l
ls docs/known-issues/commit-guardian/open-blocker-*   # is anything critical open here?
```

A count taken this way cannot race an append, because there is no shared line for two
branches to edit: a new issue is a new file. Two branches filing at once produce two files,
not a conflict and not a wrong total. The table below is therefore a **map, not a tally** —
the per-component numbers are in each component's own index, which is generated from the
directory rather than maintained by hand.

| Component | Index | Entries |
|---|---|---|
| `commit_guardian`, `precommit_hooks` | [commit-guardian.md](commit-guardian.md) | [`commit-guardian/`](commit-guardian/) |
| `build_orchestration`, `doc_compliance` | [build-orchestration.md](build-orchestration.md) | [`build-orchestration/`](build-orchestration/) |
| `build_pipeline` | [build-pipeline.md](build-pipeline.md) | [`build-pipeline/`](build-pipeline/) |
| `ac_driven_dev` | [ac-driven-dev.md](ac-driven-dev.md) | [`ac-driven-dev/`](ac-driven-dev/) |
| `ac_driven_dev` (from 2026-09-14) | [ac-driven-dev-2026-09.md](ac-driven-dev-2026-09.md) | [`ac-driven-dev-2026-09/`](ac-driven-dev-2026-09/) |
| `ac_store` | [ac-store.md](ac-store.md) | [`ac-store/`](ac-store/) |
| `testing_quality` | [testing-quality.md](testing-quality.md) | [`testing-quality/`](testing-quality/) |
| `knowledge_management` | [knowledge-management.md](knowledge-management.md) | [`knowledge-management/`](knowledge-management/) |
| `supervisor_system` | [supervisor-system.md](supervisor-system.md) | [`supervisor-system/`](supervisor-system/) |
| `agent_registry` | [agent-registry.md](agent-registry.md) | [`agent-registry/`](agent-registry/) |
| `documentation_system` | [documentation-system.md](documentation-system.md) | [`documentation-system/`](documentation-system/) |
| `feedback_collector` | [feedback-collector.md](feedback-collector.md) | [`feedback-collector/`](feedback-collector/) |
| `changelog` | [changelog.md](changelog.md) | [`changelog/`](changelog/) |
| `security_scanner` | [security-scanner.md](security-scanner.md) | [`security-scanner/`](security-scanner/) |

At the split: **255 open** (18 blocker, 129 high, 108 low) and **32 resolved**. That is a
snapshot, not a maintained figure — run the `ls` above.

## Filing a new issue

Write a new file in the component's directory. Do **not** append to the index; it is
generated, and the registers it replaced grew to 1,900–4,500 lines against a 300-line limit,
at which point `check-doc-length` correctly refused every further append and the
record-on-sight path closed. One file per issue is what keeps that from recurring.

```
docs/known-issues/<component>/open-<severity>-KI-<COMP>-<YYYYMMDD>-<slug>.md
```

**Severity in the filename** is a three-level index bucket: `blocker` / `high` / `low`.
The registers themselves graded on five levels, and that original grading is preserved
verbatim on each entry's own `**Severity:**` line — the bucket is an index, and it never
overwrites the entry's own words. `critical` indexes as `blocker`; `medium` indexes as `low`.
Where an entry named two levels ("medium for X, high for Y"), the bucket takes the **worst**:
over-grading surfaces an issue, under-grading hides one.

**When it is fixed**, move the file to `<component>/resolved/` and rename the `open-` prefix
to `resolved-`. Fixed issues are kept, not deleted — a resolved entry is how a future reader
learns why present code is shaped the way it is.

Two id conventions are in use — `KI-CG-035` and `KI-CG-20260826-1612`. The date form is the
newer of the two and is the one that cannot collide; prefer it.

**Known id collision, unrepaired:** `commit-guardian` carries **two** distinct entries
numbered `KI-CG-012` — one on hook test seams, one on `check-ac-schema` failing open on an
empty staged set. `testing-quality` carries the same problem on `KI-TQ-012`. Both are cited
elsewhere by those ids, so neither can be silently renumbered without breaking references.
The split did **not** repair this and did not renumber anything: each colliding pair keeps
its id in the filename and is told apart by a trailing slug. The collision is still there to
be fixed; it is now visible in `ls` rather than only in this paragraph.

## Highest severity first

- **KI-SUP-1** — `/build-feature`'s commit phase runs while gates are recorded
  `failed`. Phantom-done at the orchestration layer.
- **KI-TQ-1** — bare-name `sys.modules` caching lets a stale deployed copy shadow
  the canonical module for a whole pytest session. Can hide a real fix *or* a
  real bug.
- **KI-CG-1** — `check-predone-scope` blocks any lifecycle-repair commit and
  reconciles branch-wide, so no commit boundary satisfies it.
- **KI-CG-2** — `check_ticket_signoff_parity.py` silently skips check #6 on a
  wrong registry path, then exits 0.
- **KI-TQ-2** — the exit gate's tree-purity guard false-positives on any
  concurrent write, producing failures indistinguishable from real ones.
- **KI-FC-1** — `ac-validator` is missing from every category's
  `allowed_writers`, so it has never once submitted feedback.

## The common shape

Nine of the twelve entries are the same defect class: **a check that reports
success while seeing less than it should**. A hook that skips one of its own
checks and exits 0. A gate registered nowhere. A driver that commits past its own
blockers. An agent that cannot write to the corpus it is supposed to feed. An
oracle that shares the bug it exists to detect.

None of these is visible in a passing test run — the suite was green for every
one of them. That is worth stating plainly in a package whose purpose is to
detect exactly this: **green tests are not evidence against this failure class,
because this failure class is what green looks like when the check is blind.**

What did find them: measuring instead of asserting; probing with synthetic
inputs a real-artifact sweep cannot reach; deliberately breaking the
implementation to confirm the tests notice; and agents refusing to improvise past
their own algorithm's limits rather than producing a convenient pass.

## Provenance

All current entries were found on 2026-08-19 during
`EPIC-GE122UniquenessPassAndRepair`, and every one was observed directly — by
running the code, reading a hook's stderr, or watching a drive behave — not
inferred from reading source.
