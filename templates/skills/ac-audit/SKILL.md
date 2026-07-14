---
name: ac-audit
description: |
  Evidence-based implementation audit of an AC area (component, id-prefix, or
  store subpath). Answers, per acceptance criterion: is it really implemented,
  by which code, and by which green unit test? Treats the store's own
  work_status / implemented_by / covered_by fields as UNTRUSTED and verifies
  against the actual repo — grep citation maps, ticket files_touched, and a live
  test run — then fans out skeptical per-group agents to catch phantom-done code
  (orphaned / dead / opposite-behaviour / xfail-masked). Produces a per-AC
  verdict report and, on request, evidence-anchored store reconciliation and
  remediation/test-backfill work orders.
  Use when: "audit the <X> ACs", "which <area> ACs are actually implemented",
  "assess implementation coverage for <component>", "are these ACs really done".
allowed-tools: Bash, Read, Write, Agent
---

# ac-audit skill

## Purpose

Assess how much of an AC area is *genuinely* implemented and tested — the same
way the BO-* audit was done. The output for every leaf AC is a verdict plus the
concrete **code file** and **green unit test** that back it (or the gap).

## Core principle — the store lies; verify everything

The AC store's bookkeeping is systematically out of sync with reality. Do **not**
trust these fields:

- `work_status` — frequently `todo` on ACs that are fully built (and occasionally
  `done` on ones that aren't).
- `implemented_by` — records the **generating ticket**, not code. A populated
  value is NOT evidence of implementation.
- `covered_by` — sometimes a real test link, sometimes child AC ids, sometimes a
  `# covers:` label that was pasted onto an unrelated test (phantom coverage).

**"Done" only counts when a concrete, green unit test names the AC.** Any AC
without one is either a remediation gap or a test-backfill gap — never a silent
`done`.

Watch for **phantom-done** — green tests over code that does not actually satisfy
the criterion:

- **orphaned** — a tested library that nothing calls (grep the callers).
- **dead** — a tested helper never invoked by the entrypoint.
- **opposite** — code (and its test) assert the *opposite* of the AC.
- **xfail-masked / mis-pathed** — tests converted to xfail, or importing a path
  that isn't deployed, so they never actually assert.

## Stage 1 — mechanical evidence map (deterministic)

Run the engine for the area. One selector is required.

```bash
# by id prefix
python3 .claude/skills/ac-audit/scripts/audit_ac_area.py --prefix ACS --out /tmp/ac_audit.md
# by component field
python3 .claude/skills/ac-audit/scripts/audit_ac_area.py --component ac-store
# by store subpath, JSON for machine consumption
python3 .claude/skills/ac-audit/scripts/audit_ac_area.py --path ac-driven-dev --format json
```

It enumerates the area's ACs and builds AC-id citation maps over the test dirs
(`unit_tests/`, `tests/`) and source dirs (`scripts/`, `templates/`, `config/`).
**The verdict is derived from repo citations only** — the store's own
`work_status` / `implemented_by` / `covered_by` are read only to compute
comparison flags, never to set the verdict (so the tool cannot launder a store
claim into "done"). It emits:

- a first-pass verdict per leaf (`FULLY_IMPLEMENTED` / `CODE_NO_TEST` /
  `TEST_NO_CODE` / `NOT_IMPLEMENTED`) from cited code + cited tests,
- **flags**: `phantom-suspect` (store/ticket says done, no cited test),
  `unverified-coverage-claim` (`covered_by` names a test the repo doesn't cite),
  `stale-bookkeeping` (evidence exists, store≠done), `needs-test`,
- a `store_claimed_code` column (files_touched, shown but not counted as evidence),
- the list of **cited test files** — the suites to run in Stage 2.

Treat every Stage-1 verdict as a hypothesis. Grep misses code/tests that don't
embed the AC id, and it can't tell a passing test from an orphaned one.

## Stage 2 — green-test ground truth

Run the cited test files (from Stage 1) and record pass/fail. Do not trust a
verdict that depends on a test you did not see go green.

```bash
python3 -m pytest <cited test files...> -v -p no:cacheprovider --continue-on-collection-errors -o addopts="" > /tmp/ac_audit_pytest.txt 2>&1
```

- A `FULLY_IMPLEMENTED` whose test is red is **not** done — demote it.
- Distinguish genuine failures from **deploy-layout artifacts**: tests that
  invoke `leafcutter-ai/scripts/...` can fail in a source checkout because that
  path is only populated in the parent-workspace deploy. Behaviour may be fine;
  the test path is wrong → route to test-portability, not remediation.

## Stage 3 — deep verification (skeptical agents, in parallel)

For each group in the Stage-1 rollup that has non-trivial evidence, dispatch ONE
`general-purpose` agent (in parallel — one message, multiple Agent calls). Give
each the group's AC ids and this contract:

> You are auditing AC group `<GROUP>` in the leafcutter-ai repo (root:
> `<REPO_ROOT>`). For EACH AC id `<IDS>`: read its YAML `criteria`; independently
> find the implementing code (do NOT trust `implemented_by`/`work_status` — they
> are stale) by searching `scripts/`, `templates/`, `config/`, `.claude/`; find
> the unit test(s) that genuinely exercise the behaviour and confirm they assert
> it (not just import). Be skeptical — this repo has a documented phantom-done
> problem (orphaned libs, dead helpers, opposite-behaviour code, xfail-masked
> tests). Verdict per AC: FULLY_IMPLEMENTED (code + real green test) /
> CODE_NO_TEST / TEST_NO_CODE / NOT_IMPLEMENTED. Return ONLY a one-line summary
> with counts, then a markdown table: AC | Verdict | Code file(s) | Test file(s)
> | Note (≤12 words). Repo-relative paths. Read-only; modify nothing.

Collect each agent's table; its verdicts override Stage 1 where they differ.

## Stage 4 — synthesise the report

Write `reports/<area>-implementation-audit-<YYYY-MM-DD>.md`: executive summary
(verdict counts), per-group rollup, the merged per-AC table (code + test + verdict),
and a **phantom-done risk** section calling out orphaned/dead/opposite/masked cases.

## Stage 5 — act on it (only when the user asks)

Do these in an **isolated worktree off `origin/main`** (shared main gets clobbered
by concurrent finalize flows); `main` is PR-only → branch + PR; commit via the
commit agent (or `COMMIT_AGENT_MODE=1` when the user authorised in-conversation).

- **Evidence-anchored reconciliation.** For each AC with a confirmed green test:
  write `covered_by: ["<test file>::<test>"]`, then
  `python3 scripts/ac_store/mark_ac_done.py --ac <id>`. Never mark done without a
  linked green test.
- **Remediation / test-backfill work orders.** Cluster the gaps by root-cause
  file (many ACs often share one fix — 21 ACs behind a single wiring change
  should be one ticket, not 21). Scaffold an epic; per ticket, run
  `python3 scripts/ac_store/generate_ticket_from_ac.py --ac <anchor>` for a
  guard-correct skeleton, then edit in real `files_touched`, an `ac_coverage`
  list, and a `## Remediation Context` section pasting the audit finding
  ("wire, don't rewrite").

## Caveats

- Source of truth is `templates/`; `scripts/`, `.claude/`, `config/` copies are
  build outputs — verify against the `templates/` original when they diverge.
- `ruff` excludes `templates/`, so template-hosted scripts are not lint-gated;
  correctness is on you.
- Composite L0/L1 ACs are not leaves — their fulfilment rolls up from children;
  the engine audits leaves (L2/L3) only.
