---
title: "Known Issues: Commit Guardian"
description: "Open defects in commit-guardian hooks found while driving GE-122: a scope hook that cannot tell a ticket-as-subject from a ticket-as-driver, a parity hook silently skipping one of its checks, an unretired always-exit-0 fail-open contract, and a repair module with no supported entry point."
type: reference
status: active
created: 2026-08-19
last_updated: 2026-08-19
components:
  - commit_guardian
  - precommit_hooks
related_docs:
  - docs/pre-commit-hooks.md
  - docs/architecture/components/commit-guardian.md
  - docs/architecture/adrs/ADR-029-adr-number-collision-prevention.md
---

# Known Issues: Commit Guardian

Open defects observed directly on 2026-08-19 while driving
`EPIC-GE122UniquenessPassAndRepair`.

## KI-CG-1 — `check-predone-scope` cannot distinguish a ticket's subject from its driver

**Severity: medium.** Blocks any lifecycle-repair commit.

The hook reads every modified ticket `.md` in the change set as a *governing*
ticket authorising the commit, then reports source changes as undeclared against
that ticket's `files_touched`. It has no notion of a ticket being the *subject*
of a change.

This misfires on any work that repairs tickets. GE-122e-2 deleted five duplicate
work items; the hook read those five long-finished June tickets as the commit's
authorisers and blocked.

**Second, compounding defect: it reconciles branch-wide, not commit-wide.** An
attempt to satisfy it by splitting the source changes into a separate commit
still failed, and the error named files that were not in the commit at all
(`_commit_disposition.py`, `_uniqueness_scanners.py`, `_work_items_scanner.py` —
all from earlier commits on the branch). No commit boundary can satisfy it.

**Detection.** The tell is a blocker naming files absent from `git diff --staged`.

**Workaround.** `SKIP=check-predone-scope`, with the justification written into
the commit message. Used once on `6715e4c3`.

**Suggested fix.** Two independent changes: (1) distinguish subject from driver,
probably by treating a ticket as governing only when the commit is authored under
it; (2) reconcile against the staged diff rather than the branch diff.

## KI-CG-2 — `check_ticket_signoff_parity.py` silently skips check #6

**Severity: medium.** A gate check has been inert.

The hook resolves the agent registry at
`<worktree_root>/leafcutter/config/agent_registry.json`. That path is wrong for
this layout — nothing exists there — so it emits a warning to stderr and skips
check #6 entirely:

```
[check-ticket-signoff-parity] WARNING: agent registry not found at
  <worktree>/leafcutter/config/agent_registry.json; skipping check #6
```

The hook then **exits 0**. The other checks run, so the hook looks healthy; one
of its checks has simply never fired in this layout.

**Detection.** Run the hook and read stderr, not just the exit code. Silence is
not the same as a pass.

**Suggested fix.** Resolve the registry the way other layout-aware scripts do
(derive the root from `git rev-parse`, and support both the source-repo and
deployed layouts). Consider whether an unresolvable registry should fail closed
rather than skip.

## KI-CG-3 — `check_ticket_state_integrity.py` retains an always-exit-0 contract

**Severity: medium.**

The script documents a `Returns: Always 0` fail-open contract. GE-122a-2 widened
work-item integrity checking but did **not** retire it. The contract is pinned by
existing tests, so a coder may not unilaterally weaken it — retiring it needs a
`test-writer` pass first to change the pinned expectations.

While this stands, the hook cannot block anything.

## KI-CG-4 — `repair_work_item_duplicates.py` has no CLI

**Severity: low.**

The module is importable only. The live repair run against the real `tickets/`
tree therefore went through a throwaway operator harness in `/tmp` rather than a
supported entry point. Nothing in the AC's `test_spec` required a CLI, and adding
untested surface for convenience was declined — but a repair that can only be
invoked from a test is awkward to re-run and hard to audit.

## KI-CG-5 — Staged paths with non-ASCII characters are silently unattributed

**Severity: low** in this repository, **medium** in a consumer project with
non-ASCII filenames.

`_get_staged_paths` in `_commit_disposition.py` uses plain
`git diff --cached --name-only`, with no `-z` and no `--no-quote-path`. Under
git's default `core.quotePath=true`, a staged path containing non-ASCII
characters comes back **quote-escaped** (e.g. `"tickets/caf\303\251.md"`). That
string does not resolve to a real path, so the attribution check silently fails
to match it.

The consequence is directional and bad: a collision the current commit **did**
cause is reported as *unattributed*, which by design does **not** block. The
commit proceeds.

Found during the first review of `GE-122a-1-i`. It is inherited from
`check_ac_schema.py::_get_staged_ac_paths`, which that AC's own `doc_links` name
as its precedent — so it is a pre-existing convention rather than something the
GE-122 work introduced.

**Why it is low here:** this repository's numbered artifacts are ASCII by
convention (`GE-122a-1.yaml`, `ADR-029-*.md`, `TICKET-*.md`). Nothing currently
in the collection can trigger it.

**Suggested fix.** Use `git diff --cached --name-only -z` and split on NUL, or
pass `--no-quote-path`. Fix both call sites together — leaving the precedent
unfixed means the next author copies it again.

## Fixed, recorded for context

Two defects in this area were found and fixed during the same drive; they are
listed here only so the history is legible, and are **not** open:

- **`check_adr_collision.py` was never registered.** ADR-029 claimed it had been
  "shipped and wired into `.pre-commit-config.yaml` since the package's early
  history". It appeared in none of the 49 registered hooks. Now registered as
  `check-decision-number-uniqueness`; ADR-029 amended.
- **The uniqueness pass's id fast path diverged from `yaml.safe_load`.** Plain
  scalars like `no`, `007` and `0x1F` resolved to their raw source text rather
  than YAML's coerced value, so two records YAML considers identical looked like
  two different ids and a real collision was silently missed. Fixed by asking
  PyYAML's own resolver whether a plain scalar would be coerced.
