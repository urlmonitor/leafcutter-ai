---
title: 'Convention: ADR Numbering and Collision Prevention'
type: how-to
status: active
created: 2026-05-17
last_updated: 2026-08-18
components:
- commit_guardian
- documentation_system
related_docs:
- docs/architecture/adrs/ADR-029-adr-number-collision-prevention.md
related_code:
- scripts/adr_refs.py
- templates/scripts/commit_guardian/check_adr_collision.py
- templates/agents/adr-author.md
description: 'Overview of Convention: ADR Numbering and Collision Prevention.'
---
# Convention: ADR Numbering and Collision Prevention

This convention document specifies the rules for assigning ADR integers, explains the
collision-prevention mechanism recorded in
[ADR-029](../architecture/adrs/ADR-029-adr-number-collision-prevention.md),
and describes the numbering repair that motivated it.

---

## 1. Background: The 2026-08-13 Numbering Repair

By 2026-08-13 the corpus had accumulated **four** duplicated integers — ten ADR files
sharing four numbers:

| Number | Files sharing it |
|--------|------------------|
| 004 | `consolidated-output-root`, `tdd-workflow-enforcement` |
| 007 | `contract-driven-acs`, `ac-store-schema-id-format-enforcement`, `test-fixture-convention` |
| 017 | `computed-quality-gates`, `dual-engine-workflow-support`, `worktree-quality-gate-guard` |
| 025 | `first-class-flow-decisions`, `tiered-parallel-code-smell-review` |

Because the git filenames differ, none of these produced a merge conflict. Each collision
surfaced only afterwards as a logical ambiguity: two or three entirely different decisions
answering to one label, and **382 bare `ADR-NNN` citations** that no longer resolved to a
single decision. The stale index had papered over it with invented `ADR-004b` / `ADR-007b`
/ `ADR-007c` labels that appear nowhere in the filenames.

**Resolution cost:** 6 file renames, ~430 citation rewrites across ~200 files, one
sequence gap filled, and two ADRs written retroactively for decisions that were being
cited but had never been recorded.

**Root cause:** `adr-author` scans `docs/architecture/adrs/ADR-*.md` for the highest
existing number and increments by one. This is correct for serial workflows but is racy
under concurrent epic worktrees — each branch's scan sees only committed files on
`origin/main`, blind to in-flight ADRs on sibling branches.

---

## 2. The Chosen Mechanism: Option C (Pre-Commit Collision Hook)

The chosen fix is **Option C**: a pre-commit hook (`check_adr_collision.py`) that
detects numeric collisions against `origin/main` and remote in-flight branches.

**Why Option C was chosen over the alternatives:**

- **Option A (branch-local reservation file):** A `.reserved` file becomes a coordination
  surface that itself produces merge conflicts when two branches both modify it — reproducing
  the problem at a new layer.
- **Option B (date/branch-prefixed numbering):** Requires renaming all 28+ existing ADRs
  and breaks chronological ordering. Migration cost far exceeds benefit.
- **Option C (pre-commit hook):** Minimal footprint, fail-open, no migration, no renaming.
  Works within the existing integer sequence.

The decision is recorded in full at
[docs/architecture/adrs/ADR-029-adr-number-collision-prevention.md](../architecture/adrs/ADR-029-adr-number-collision-prevention.md).

---

## 3. Rules for `adr-author`: Step-by-Step

Follow these steps every time you author a new ADR:

### Step 1 — Find the highest existing number

```bash
ls docs/architecture/adrs/ADR-*.md | sort
```

Identify the highest `NNN` in the output. The **candidate next number** is `NNN + 1`,
zero-padded to three digits.

### Step 2 — Run the collision guard

```bash
python scripts/commit_guardian/check_adr_collision.py
```

**If the script is not present** (new project, hook not yet installed), skip this step
and use the candidate number from Step 1.

**If the script exits 0:** No collision detected. Proceed with your candidate number.

**If the script exits non-zero:** A collision was detected. The script prints:
```
ERROR [check_adr_collision] ADR-NNN is already claimed on origin/main.
  Suggested next-free ADR number: NNN+1
  Rename your ADR file to: docs/architecture/adrs/ADR-<NNN+1>-<your-slug>.md
```
Use the suggested next-free number instead of your candidate.
Update your filename accordingly before proceeding.

### Step 3 — Write the ADR file

Write the ADR to `docs/architecture/adrs/ADR-NNN-<slug>.md` using the confirmed free
number. Follow the full ADR authoring guide at
[docs/how-to/documentation/write-adr.md](../how-to/documentation/write-adr.md).

### Step 4 — Stage and commit

```bash
git add docs/architecture/adrs/ADR-NNN-<slug>.md
git commit -m "docs(adr): add ADR-NNN <short title>"
```

The pre-commit hook is *intended* to run automatically and block the commit if a collision
is detected against `origin/main` or any remote in-flight branch at commit time. **As of
2026-08-18 it is not registered and does not run** — see [The Pre-Commit
Hook](#4-the-pre-commit-hook) below. Until it is wired up, check the number by hand with
`python scripts/adr_refs.py`.

---

## 4. The Pre-Commit Hook

> **NOT CURRENTLY ACTIVE (verified 2026-08-18).** This section originally opened "The hook
> is registered in `.pre-commit-config.yaml` as `check-adr-collision`." It is not.
> `check_adr_collision.py` appears in none of the 49 hook entries in
> `templates/scripts/commit_guardian/commit_guardian.json`, from which
> `.pre-commit-config.yaml` is generated, so it is deployed but never invoked. Everything
> below describes the hook's behaviour **when it is wired up**, which is tracked under goal
> `GE-122`. Treat the number-collision guard as manual until then.

The hook is designed to fire on commits that stage files matching
`^docs/architecture/adrs/ADR-.*\.md$`.

### What it checks

1. Scans `origin/main` for committed ADR integers (via `git ls-tree`).
2. Scans all remote branches for in-flight ADR integers not yet on `origin/main`.
3. Compares the proposed integer (from the staged filename) against both sets.
4. Exits non-zero and prints the next-free number if a collision is found.
5. Exits 0 silently when no collision is detected.

### Failure behaviour — fail-open for its own bugs, fail-closed when it could not read

*Amended 2026-08-18 by [ADR-029 Amendment 1](../architecture/adrs/ADR-029-adr-number-collision-prevention.md#amendment-1--2026-08-18--fail-open-is-narrowed-to-the-guards-own-defects).
This section previously said any unexpected error exits 0. That unqualified rule is
withdrawn.*

The disposition turns on **whether the hook managed to read the whole ADR sequence**, not
on which exception it caught:

| Situation | Read the sequence? | Behaviour |
|---|---|---|
| Bug in the hook's own reporting, after the scan completed | Yes | Warn on stderr, **exit 0** |
| Git unavailable, `docs/architecture/adrs/` absent, remote scan failed | No | Name what it could not read, report how many numbers it did read, **do not exit 0** |

The first case has established that your number is free and then tripped on the way to
saying so; a bug in the hook must not hold an unrelated commit hostage. The second has
established nothing, and exiting 0 there would mean "I could not check, therefore your
number is fine."

### Visibility gap

The branch-scan heuristic cannot see branches that exist only locally on another
developer's machine (never pushed). The guard is best-effort, not a hard guarantee.
A collision that slips through this gap is still much cheaper to fix at review time
than post-merge — and the hook catches the common case (pushed feature branches).

---

## 5. Failure Modes

| Mode | What happens | How to resolve |
|------|-------------|----------------|
| **Collision on origin/main** | Hook exits 1, prints next-free number | Rename your ADR file to the suggested number; update all cross-references; re-stage |
| **Collision on in-flight branch** | Hook exits 1, prints next-free number | Coordinate with the owner of the sibling branch; one branch increments |
| **Script exits 0 but collision exists** (visibility gap) | Hook passes; collision discovered at PR review | Manual rename at PR review time (same procedure as post-merge fix) |
| **Script error** | Hook exits 0 with a stderr warning | Check that `git` is available; ignore if transient |
| **New project without `scripts/` directory** | Script not found; `adr-author` skips check | Install the leafcutter build by running `python leafcutter/scripts/build.py` |

---

## 6. Quick Reference

```
# 1. Find next candidate number
python scripts/adr_refs.py
# → read the "Unclaimed numbers" line; the first entry is your candidate NNN.
#   Prefer this over `ls | tail -1`: it also excludes numbers that own no file
#   but are still cited somewhere, which would false-resolve if you reused them.

# 2. Run collision guard (pre-write)
python scripts/commit_guardian/check_adr_collision.py
# → exits 0: proceed with NNN
# → exits 1: use the suggested number instead

# 3. Write ADR
# docs/architecture/adrs/ADR-NNN-<your-slug>.md

# 4. Regenerate the index (it is generated, never hand-edited)
python scripts/adr_refs.py --index --write

# 5. Commit (hook also runs here as a second guard)
git add docs/architecture/adrs/ADR-NNN-<your-slug>.md docs/architecture/adrs/README.md
git commit -m "docs(adr): add ADR-NNN <title>"
```

---

## Related

- [ADR-029: ADR Number Collision Prevention Mechanism](../architecture/adrs/ADR-029-adr-number-collision-prevention.md)
- [How-To: Write an Architecture Decision Record](../how-to/documentation/write-adr.md)
- [`check_adr_collision.py`](../../templates/scripts/commit_guardian/check_adr_collision.py) — the forward collision guard
- [`adr_refs.py`](../../scripts/adr_refs.py) — the retrospective audit: duplicates, gaps, dangling numbers, broken slugs, and the index generator
- [`adr-author.md`](../../templates/agents/adr-author.md) — the adr-author agent template
