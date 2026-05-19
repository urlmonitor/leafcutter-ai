---
title: "Convention: ADR Numbering and Collision Prevention"
type: how-to
status: active
created: 2026-05-17
last_updated: 2026-05-17
related_docs:
  - "docs/architecture/adrs/ADR-029-adr-number-collision-prevention.md"
  - "docs/how-to/documentation/write-adr.md"
related_code:
  - "leafcutter/scripts/commit_guardian/check_adr_collision.py"
  - "scripts/commit_guardian/check_adr_collision.py"
  - "leafcutter/templates/agents/adr-author.md"
---

# Convention: ADR Numbering and Collision Prevention

This convention document specifies the rules for assigning ADR integers, explains the
collision-prevention mechanism introduced by
[ADR-029](../../docs/architecture/adrs/ADR-029-adr-number-collision-prevention.md),
and describes the 2026-05-15 incident that motivated it.

---

## 1. Background: The 2026-05-15 ADR-024 Collision Incident

On 2026-05-15, two epics ran in parallel and both independently claimed ADR number 024:

| Epic | ADR File | Merge Order |
|------|---------|-------------|
| EPIC-FeedbackCollection | `ADR-024-feedback-collection.md` | Merged first |
| EPIC-PortableSQLAgents | `ADR-024-portable-agent-project-context-layout.md` | Merged second |

Because the git filenames differed, there was no merge conflict. The collision surfaced
only post-merge as a logical ambiguity: two entirely different architectural decisions
were both labelled ADR-024.

**Resolution cost:** 1 manual file rename, 2 sed passes with a negative-lookahead guard
to avoid clobbering the other ADR-024, 2 `build.py` reruns, and 2 push rounds while
`main` kept advancing.

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
[docs/architecture/adrs/ADR-029-adr-number-collision-prevention.md](../../docs/architecture/adrs/ADR-029-adr-number-collision-prevention.md).

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
ERROR [check_adr_collision] ADR-029 is already claimed on origin/main.
  Suggested next-free ADR number: 030
  Rename your ADR file to: docs/architecture/adrs/ADR-030-<your-slug>.md
```
Use the suggested next-free number (`030` in this example) instead of your candidate.
Update your filename accordingly before proceeding.

### Step 3 — Write the ADR file

Write the ADR to `docs/architecture/adrs/ADR-NNN-<slug>.md` using the confirmed free
number. Follow the full ADR authoring guide at
[docs/how-to/documentation/write-adr.md](../../docs/how-to/documentation/write-adr.md).

### Step 4 — Stage and commit

```bash
git add docs/architecture/adrs/ADR-NNN-<slug>.md
git commit -m "docs(adr): add ADR-NNN <short title>"
```

The pre-commit hook will run automatically and block the commit if a collision is
detected against `origin/main` or any remote in-flight branch at commit time.

---

## 4. The Pre-Commit Hook

The hook is registered in `.pre-commit-config.yaml` as `check-adr-collision`. It fires
automatically on commits that stage files matching `^docs/architecture/adrs/ADR-.*\.md$`.

### What it checks

1. Scans `origin/main` for committed ADR integers (via `git ls-tree`).
2. Scans all remote branches for in-flight ADR integers not yet on `origin/main`.
3. Compares the proposed integer (from the staged filename) against both sets.
4. Exits non-zero and prints the next-free number if a collision is found.
5. Exits 0 silently when no collision is detected.

### Fail-open behavior

Any unexpected error (git unavailable, `docs/architecture/adrs/` absent, network
failure) causes the script to print a warning to stderr and **exit 0** — the commit
is never blocked by a script error. This prevents the hook from becoming a deployment
blocker in CI environments or on new developer machines.

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
ls docs/architecture/adrs/ADR-*.md | sort | tail -1
# → docs/architecture/adrs/ADR-028-timescaledb-bounds-cte.md → candidate is 029

# 2. Run collision guard (pre-write)
python scripts/commit_guardian/check_adr_collision.py
# → exits 0: proceed with 029
# → exits 1: use the suggested number instead

# 3. Write ADR
# docs/architecture/adrs/ADR-029-<your-slug>.md

# 4. Commit (hook also runs here as a second guard)
git add docs/architecture/adrs/ADR-029-<your-slug>.md
git commit -m "docs(adr): add ADR-029 <title>"
```

---

## Related

- [ADR-029: ADR Number Collision Prevention Mechanism](../../docs/architecture/adrs/ADR-029-adr-number-collision-prevention.md)
- [How-To: Write an Architecture Decision Record](../../docs/how-to/documentation/write-adr.md)
- [`check_adr_collision.py`](../scripts/commit_guardian/check_adr_collision.py) — the collision-detection script
- [`adr-author.md`](../templates/agents/adr-author.md) — the adr-author agent template
