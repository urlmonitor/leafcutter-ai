---
name: create-ac
description: |
  Entry-point skill for the /create-ac workflow. Drives AC authoring from
  user request through a three-stage agent pipeline (product-owner-v3 →
  business-analyst-v3 → it-po-v3), committing AC YAML files to the AC store
  after each stage approval. Begins with a mandatory Partial-Run Recovery
  pre-flight that detects and resolves uncommitted AC files left over from a
  prior crashed session before starting new work.
  Trigger phrases: "create ac", "author ac", "/create-ac", "new acceptance criteria".
allowed-tools: Bash, Read, Edit, Agent
---

# create-ac skill

## Purpose

`/create-ac` is the user-facing entry point to the staged AC authoring pipeline.
It differs from `/plan-feature` in one critical respect: after each stage
(product-owner-v3, business-analyst-v3, it-po-v3), the workflow **commits the
AC files produced by that stage** before moving on. This staged-commit model
ensures that a session crash does not lose work — each completed stage is
permanently recorded in git before the next stage begins.

The workflow sequence is:

1. **Partial-Run Recovery pre-flight** — detect and resolve any uncommitted AC
   files left over from a prior crashed session (this section, §PRR below).
2. **Stage 0: Triage** — classify the user's request (strategic / behavioral /
   technical / covered) via the `ac-triage` agent.
3. **Stage 1: PO** — `product-owner-v3` authors L0/L1 ACs; user approves.
4. **Stage 1 Commit** — commit Stage 1 AC files: `chore(ac): stage 1 — PO ACs for <request-summary>`.
5. **Stage 2: BA** — `business-analyst-v3` decomposes L1s into L2/L3 ACs; user approves.
6. **Stage 2 Commit** — commit Stage 2 AC files: `chore(ac): stage 2 — BA ACs for <request-summary>`.
7. **Stage 3: IT PO** — `it-po-v3` enriches ACs with technical fields; user approves.
8. **Stage 3 Commit** — commit Stage 3 AC files: `chore(ac): stage 3 — IT PO ACs for <request-summary>`.

Each stage commit is scoped to only the AC files created or modified by that
stage's authoring agent (see ADR-010-ac-store-as-authoritative-backlog.md).

---

## §PRR — Partial-Run Recovery Pre-flight

**This section runs BEFORE Stage 0.** It must complete before any authoring
agent is dispatched. If the pre-flight is skipped, a new session may overwrite
or conflict with orphaned AC files from a prior crashed session.

### §PRR.1 — When to Run

Run the Partial-Run Recovery pre-flight on every invocation of `/create-ac`,
without exception. The check is fast (< 2 seconds for up to 500 files) and
non-destructive on the happy path (no orphans found → silent proceed).

### §PRR.2 — Detection Algorithm

1. **Determine the AC store directory.** Read `docs/acceptance-criteria/` as
   the default path. If `skills_config.json` overrides `ac_store_path`, use
   that value instead.

2. **Run `git status --porcelain` on the AC store directory** to get a list of
   all YAML files with uncommitted changes (modified, added, or untracked):

   ```bash
   git -C <project-root> status --porcelain docs/acceptance-criteria/
   ```

   **Important — ordering with §WT:** The §PRR pre-flight runs TWICE in the
   full `/create-ac` workflow: once BEFORE §WT (targeting the original
   checkout) and once AFTER §WT (targeting the authoring worktree).  When
   §WT has already run and `AUTHORING_WORKTREE_PATH` is set, replace
   `<project-root>` with `AUTHORING_WORKTREE_PATH` in the command above so
   the git status targets the authoring worktree, not the original checkout
   (AC BO-1500a-2):

   ```bash
   git -C AUTHORING_WORKTREE_PATH status --porcelain docs/acceptance-criteria/
   ```

   Parse each output line:
   - Column 1 (`X`) = index (staged) status; column 2 (`Y`) = worktree status.
   - Relevant status codes: `M` (modified), `A` (added), `?` (untracked).
   - Include a file if: `X` or `Y` is one of `M`, `A`, `?`.
   - Exclude files whose path does not end in `.yaml` (e.g. `index.yaml` is
     a registry, not an AC — exclude it from the orphan set).

   **Error handling:** If `git status` exits non-zero (e.g. not a git
   repository, or git is unavailable), emit a warning to the user:
   `"Warning: could not check for uncommitted AC files (git error: <reason>).
   Proceeding without orphan detection."` and continue to Stage 0 without
   blocking.

3. **Load and qualify each detected YAML file.** For each file path returned
   by the git status scan:

   a. Read the YAML file. If the file is untracked (status `??`) it exists
      on disk only; if modified/added it exists in the working tree. Use a
      standard YAML load (PyYAML or stdlib `ruamel.yaml` if available;
      otherwise read raw lines for field extraction).

   b. Check the `origin_agent` field. Accept only:
      - `product-owner-v3`
      - `business-analyst-v3`
      - `it-po-v3`

   c. Check the `readiness` field. Accept only: `draft`.

   d. Extract the `id` field for display. If `id` is absent, use the filename
      stem as a fallback identifier.

   e. A file qualifies as an **orphaned AC** only if both (b) and (c) pass.
      Files that fail either check are not orphans — skip them silently.

   **Error handling:** If reading a YAML file raises an `OSError` or parse
   error, skip that file with a debug-level note (do not block the workflow).

4. **Collect qualifying orphaned ACs into a list sorted by file path.**

### §PRR.3 — User Prompt (when orphans are found)

If the orphan list is empty, proceed silently to Stage 0.

If `N >= 1` orphans are found, present the user with:

```
Found N uncommitted AC files from a prior session: [<AC-ID-1>, <AC-ID-2>, ...].
Commit them before starting new work? (yes/no/discard)
```

Where:
- `N` is the count of qualifying orphaned AC files.
- The bracketed list contains the `id` field of each orphaned AC, comma-separated,
  in sorted order.

Wait for the user's response. Accept `yes`, `no`, or `discard` (case-insensitive;
accept `y`, `n`, `d` as shorthand).

### §PRR.4 — Response Handling

#### yes — Commit orphaned files

1. Stage the orphaned AC files.  After §WT runs, replace `<project-root>`
   with `AUTHORING_WORKTREE_PATH` so the add operates in the authoring
   worktree, not the original checkout (AC BO-1500a-2):
   ```bash
   git -C AUTHORING_WORKTREE_PATH add <file1> <file2> ...
   ```

2. Commit them with a fixed message (same `-C` anchor):
   ```bash
   git -C AUTHORING_WORKTREE_PATH commit -m "chore: commit orphaned AC files from prior session"
   ```

   **Error handling:** If `git add` or `git commit` exits non-zero, emit:
   `"Error: could not commit orphaned AC files: <stderr>. Resolve the git
   error manually before re-running /create-ac."` and **abort the workflow**
   (do not proceed to Stage 0). The user must fix the git state before
   continuing.

3. On success, display:
   `"N AC files committed. Proceeding with new /create-ac session."`

4. Proceed to Stage 0.

#### no — Abort

Display:
```
Uncommitted AC files must be resolved before a new run can begin.
Re-run after committing or discarding them.
```

Abort the workflow. Do not dispatch any authoring agent.

#### discard — Revert and continue

1. For each orphaned AC file:
   - If the file is **tracked** (status `M` or `A` in the staged or worktree
     column): run `git restore` to discard working-tree changes.  After §WT
     runs, replace `<project-root>` with `AUTHORING_WORKTREE_PATH` so the
     restore operates in the authoring worktree (AC BO-1500a-2):
     ```bash
     git -C AUTHORING_WORKTREE_PATH restore <file>
     ```
     If the file was staged (status `A` in index column): first unstage it:
     ```bash
     git -C AUTHORING_WORKTREE_PATH restore --staged <file>
     ```
     Then restore it:
     ```bash
     git -C AUTHORING_WORKTREE_PATH restore <file>
     ```
   - If the file is **untracked** (status `??`): delete it:
     ```bash
     rm <file>
     ```

   **Error handling:** If any `git restore` or `rm` exits non-zero, emit a
   per-file warning: `"Warning: could not discard <file>: <reason>."` Continue
   with remaining files; do not abort the entire discard run.

2. After processing all files, display:
   `"N AC files discarded. Proceeding with a clean working tree."`

3. Proceed to Stage 0.

### §PRR.5 — Performance Constraint

The full pre-flight (git status + YAML qualification of all detected files) must
complete within **2 seconds** for an AC store of up to 500 YAML files. The
`git status --porcelain` command is the primary cost driver; it is bounded by
the filesystem and git object store, not by the number of YAML files scanned.
No looping git call is made — a single `git status` invocation covers the
entire AC store directory.

### §PRR.6 — Scope

The orphan scan covers **only the AC store directory** (`docs/acceptance-criteria/`
or the configured override). It does not scan:
- Ticket files (`tickets/`)
- Workflow state files (`.claude/`)
- Any file outside the AC store directory

This scope is intentional: only AC YAML files written by the three AC-authoring
agents (product-owner-v3, business-analyst-v3, it-po-v3) can be orphaned by a
crashed `/create-ac` session. Other uncommitted changes in the working tree are
the user's responsibility and are not touched by this pre-flight.

---

## §WT — Authoring Worktree Bootstrap (AC BO-1500a-1)

**This section runs AFTER §PRR and BEFORE §0.** It creates the dedicated
AC-authoring worktree in which all subsequent AC YAML file writes will land.
Every AC YAML file produced in this session MUST be written under the
worktree path returned by this step — no AC file may be written under the
user's original checkout.

### §WT.1 — Why a dedicated worktree

AC authoring sessions that share the user's main checkout can lose work when
concurrent finalize flows reset or branch-delete the current branch mid-session
(MEMORY: `feedback_ac_authoring_needs_isolated_worktree.md`). A dedicated
worktree on a fresh branch cut from `origin/main` isolates the authoring session
from both in-flight implementation work and from any local uncommitted commits
that happen to be on `main`.

### §WT.2 — Create or reuse the authoring worktree

Call `scripts/setup_ticket_worktree.py create-ac-worktree` with an optional
session name derived from the user's request (kebab-case, ≤ 20 characters):

```bash
python scripts/setup_ticket_worktree.py create-ac-worktree "<session-slug>"
```

If no session slug is provided, the script defaults to `ac-YYYYMMDD`.

The script:
1. Fetches `origin` (best-effort — warns on failure; continues on cached ref).
2. Creates a new branch `ac-authoring/<session-slug>` starting from `origin/main`.
3. Bootstraps the worktree (`.env` symlink, `.mcp.json` copy, `build.py` run).
4. Outputs a single-line JSON payload:
   ```json
   {
     "worktree_path": "<absolute path to the new worktree>",
     "branch":        "ac-authoring/<session-slug>",
     "ac_store_path": "<absolute path to docs/acceptance-criteria/ inside the worktree>",
     "created":       true
   }
   ```
   When the worktree already exists (idempotent re-run), `"created"` is `false`
   and the existing worktree path is returned.

**On non-zero exit:** surface the stderr verbatim to the user and abort the
workflow. Do NOT fall through to authoring in the original checkout — writing
AC files outside the dedicated worktree violates AC BO-1500a-1.

### §WT.3 — Override the AC store path for this session

After parsing the JSON payload from §WT.2:

- Store `worktree_path` → `AUTHORING_WORKTREE_PATH` for the session.
- Store `ac_store_path` → `AC_STORE_PATH` for the session.  **All subsequent
  agent dispatches in §0–§3 must pass `AC_STORE_PATH` as the AC store
  directory**, overriding the default `docs/acceptance-criteria/` that the
  authoring agents would otherwise derive from `skills_config.json` in the
  current checkout.

In practice this means every authoring agent call in §0–§3 receives an
additional instruction field:

```
"ac_store_path": "<AC_STORE_PATH>",
```

The `-C` anchor for **ALL** git operations executed by this workflow —
`git status`, `git add`, `git commit`, `git restore`, `git restore --staged`
— MUST be `AUTHORING_WORKTREE_PATH`.  This applies to the §PRR scan, the
§1–§3 stage/commit calls, and the discard-path restore calls.  No git
command may run without the `-C AUTHORING_WORKTREE_PATH` flag after §WT.3
completes (AC BO-1500a-2).

### §WT.4 — Scope and isolation invariant

**File invariant:** No AC YAML file produced by this `/create-ac` session
may appear under a path that is outside `AC_STORE_PATH`.

**Git operation invariant (AC BO-1500a-2):** All git commands executed by
this workflow (`git status`, `git add`, `git commit`, `git restore`,
`git restore --staged`) MUST use `git -C AUTHORING_WORKTREE_PATH` so that
no operation touches the original checkout or any concurrent worktree.
Using bare `git` commands (without `-C`) or `git -C <project-root>` after
§WT.3 completes is a violation of this invariant.

The §PRR scan (§PRR.2) should be re-run with `AC_STORE_PATH` as its target
directory after §WT completes, so that orphan detection covers the correct
location.  The §PRR scan that ran before §WT (targeting the original checkout)
covered the user's checkout; the scan after §WT covers the authoring worktree.

---

## §0 — Stage 0: Triage

After the authoring worktree has been set up (§WT) and the Partial-Run Recovery
pre-flight passes (or passes with no orphans) in the authoring worktree,
dispatch `ac-triage` to classify the user's request:

```
route: strategic | behavioral | technical | covered
```

| Route | When | Agents dispatched |
|---|---|---|
| `strategic` | No matching L1 AC. New capability. | PO v3 → gate → BA v3 → gate → IT PO v3 → final gate |
| `behavioral` | Matching L1 AC found. Adding scenarios. | BA v3 → gate → IT PO v3 → final gate |
| `technical` | Only adding technical constraints. | IT PO v3 → final gate |
| `covered` | Request fully covered by existing ACs. | Show existing ACs → user: cancel / amend / force |

---

## §1–§3 — Stage Pipeline (abbreviated)

Each authoring stage follows the same pattern:

1. Dispatch the stage agent.
2. Present produced ACs to the user for approval.
3. On **approve**: commit the AC files produced in this stage only (scoped
   `git add <ac-store-dir>/<files-from-this-stage>` followed by a staged
   commit). See `ACD-300g-2` for the scoping invariant.
4. On **edit**: re-invoke the stage agent with user feedback (one retry).
5. On **cancel**: abort. ACs produced so far remain as `readiness: draft`
   (not committed unless a prior stage already committed them).

The commit message for each stage uses the form:
```
chore(ac): stage <N> — <agent-short-name> ACs for <one-line request summary>
```

---

## §E — Error Handling Summary

| Step | Error condition | Behaviour |
|---|---|---|
| §PRR.2 `git status` | Non-zero exit | Warn user; proceed to Stage 0 without blocking |
| §PRR.3 YAML read | `OSError` / parse error | Skip file; log warning; continue scan |
| §PRR.4 `yes` / `git commit` | Non-zero exit | Emit error message; abort workflow |
| §PRR.4 `discard` / `git restore` | Non-zero exit | Per-file warning; continue with other files |
| §PRR.4 `discard` / `rm` | Non-zero exit | Per-file warning; continue with other files |

All git and filesystem calls are treated as external I/O and wrapped in error
handling per the project Error Handling Policy (CLAUDE.md). No exception is
silently swallowed — each produces a user-visible warning or error.

---

## Related

- `templates/skills/plan-feature/SKILL.md` — the non-staged AC authoring skill
  (no per-stage commits; sessions are all-or-nothing).
- `docs/architecture/adrs/ADR-010-ac-store-as-authoritative-backlog.md` —
  documents the recovery behaviour and the staged-commit model for `/create-ac`.
- `docs/architecture/adrs/ADR-007-ac-store-schema-id-format-enforcement.md` —
  defines the `origin_agent` and `readiness` fields used to qualify orphaned ACs.
- `docs/architecture/diagrams/c2-002-ac-authoring-pipeline.md` — the authoring
  pipeline sequence diagram, updated to reflect the Partial-Run Recovery step.
- `scripts/ac_store/validate_ac_schema.py` — AC YAML schema validator.

<!--
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-24 [EPIC-SafeAcAuthoring/03/python-coder]: Implemented AC BO-1500a-2
  (original checkout and concurrent worktrees left untouched). Updated §PRR.2
  to clarify that after §WT runs, `<project-root>` must be replaced with
  `AUTHORING_WORKTREE_PATH` in the git status command so orphan detection
  targets the authoring worktree, not the original checkout. Updated §PRR.4
  yes-branch git add/commit commands and discard-branch git restore commands
  to carry the same `-C AUTHORING_WORKTREE_PATH` anchor. Strengthened §WT.3
  with an explicit statement that the `-C` anchor for ALL git operations in
  the workflow is `AUTHORING_WORKTREE_PATH`. Added the Git operation invariant
  to §WT.4: all git commands must use `git -C AUTHORING_WORKTREE_PATH`; bare
  git or `-C <project-root>` after §WT.3 is a protocol violation.
- 2026-06-24 [EPIC-SafeAcAuthoring/01/python-coder]: Added §WT (Authoring
  Worktree Bootstrap) implementing AC BO-1500a-1. The new section inserts
  between §PRR and §0 and mandates that a dedicated worktree (branched from
  origin/main via `setup_ticket_worktree.py create-ac-worktree`) is created
  before any authoring agent is dispatched. §WT.3 documents how callers must
  override the default ac_store_path for every subsequent agent dispatch so
  AC YAML files land inside the authoring worktree rather than in the user's
  original checkout. §WT.4 states the isolation invariant. The §0 heading was
  updated to reference §WT as a prerequisite.
- 2026-06-18 [04_TICKET-20260618-ACD-300g-2-i/python-coder]: Initial authoring.
  Created templates/skills/create-ac/SKILL.md to implement AC ACD-300g-2-i.
  Added §PRR (Partial-Run Recovery Pre-flight) as the mandatory first step
  of the /create-ac workflow. Detection uses git status --porcelain scoped
  to the AC store directory; qualification requires origin_agent in
  {product-owner-v3, business-analyst-v3, it-po-v3} and readiness: draft.
  Three-way prompt (yes/no/discard) with fully specified response handling
  per each branch. Error handling follows project policy (no bare excepts,
  no silent swallows, external I/O wrapped).
====================================================================
-->
