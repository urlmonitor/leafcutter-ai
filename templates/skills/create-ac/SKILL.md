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

The detection algorithm is implemented in
`scripts/ac_store/scan_ac_orphans.py` (function
`scan_draft_orphans_in_worktree`, AC BO-1500b-3). The steps below describe
the algorithm that function executes; they also apply to any direct caller
that replicates the logic inline (e.g. `plan-feature.js`
`scanOrphanedAcDrafts`).

1. **Determine the AC store directory.** Read `docs/acceptance-criteria/` as
   the default path. If `skills_config.json` overrides `ac_store_path`, use
   that value instead.

2. **Run `git status --porcelain` on the AC store directory inside the
   authoring worktree** to get a list of all YAML files with uncommitted
   changes (modified, added, or untracked).  The scan MUST target the
   authoring worktree; it must NOT scan the user's original checkout:

   ```bash
   git -C AUTHORING_WORKTREE_PATH status --porcelain --untracked-files=all docs/acceptance-criteria/
   ```

   **Committed-file exclusion guarantee (AC BO-1500b-3):** `git status`
   reports only uncommitted working-tree changes.  AC YAML files that are
   already committed on the authoring branch do NOT appear in this output.
   Therefore the scan never produces false orphan reports for files that
   were successfully committed in a prior (partial) session.  No additional
   filtering step is needed to exclude committed files.

   **Ordering with §WT:** The §PRR pre-flight runs TWICE in the full
   `/create-ac` workflow: once BEFORE §WT (targeting the original checkout)
   and once AFTER §WT (targeting the authoring worktree).  After §WT has
   run and `AUTHORING_WORKTREE_PATH` is set, the command above is the only
   valid form.  The original-checkout scan that ran before §WT is
   superseded by this authoring-worktree scan (AC BO-1500a-2).

   **Standalone invocation via the Python script:**
   ```bash
   python3 scripts/ac_store/scan_ac_orphans.py draft-orphans \
       --worktree AUTHORING_WORKTREE_PATH \
       [--ac-root-rel docs/acceptance-criteria]
   ```
   The script emits a JSON array of `{"file_path": "...", "ac_id": "..."}`
   objects to stdout (exit code 0 regardless of whether orphans are found).

   Parse each `git status` output line:
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
      - `product-owner`
      - `business-analyst`
      - `it-po`

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

## §CR — Crash-Resume: Skip Already-Committed Stages (AC BO-1500b-2)

**This step runs AFTER §PRR and AFTER §WT, before Stage 0.** It detects which
pipeline stages already committed their AC files to the authoring branch in a
prior crashed session, and skips those stages when the user restarts the
workflow.

### §CR.1 — Why this is needed

`§PRR` handles **uncommitted** orphaned drafts (files on disk but not in git).
`§CR` handles the complementary case: stages whose output was **successfully
committed** before the crash. Without `§CR`, restarting `/plan-feature` would
re-run product-owner even though its L0/L1 ACs are already in git history,
forcing the user to re-author from scratch.

### §CR.2 — Detection Algorithm

Call `scanCommittedStages(agent, authoringWorktreePath)` in `plan-feature.js`.
This function:

1. Runs `git log --oneline origin/main..HEAD` inside the authoring worktree to
   list commits on the authoring branch that are not yet on `origin/main`.

2. For each commit subject line, matches:
   ```
   /^[0-9a-f]+ plan-feature\(([^,)]+)/i
   ```
   The captured group is the display-name stage label (e.g. `PO`, `BA`,
   `IT-PO`).

3. Normalises display names to internal stage keys (`PO→po`, `BA→ba`,
   `IT-PO→itpo`) and returns a `Set<string>` of matched keys.

**On any git error** (worktree not set, `origin/main` absent): the function
returns an empty `Set` and the pipeline runs all stages normally. This is safe
— redundant re-authoring is a UX friction, not a correctness failure.

### §CR.3 — Pipeline Skip Logic

Before dispatching each stage agent, the pipeline loop checks:

```javascript
if (committedStageKeys.has(step.stage)) {
  // Stage already committed — advance to the next stage.
  stageResults.push({ stage: step.stage, agent: step.agent, acs: [], skipped: true });
  continue;
}
```

The first stage NOT in `committedStageKeys` is dispatched normally. This
ensures the workflow resumes from exactly the stage that had not committed,
without re-running any completed work.

### §CR.4 — User-visible behaviour

When resuming after a crash:

| Prior run ended after | Stages skipped on restart | First stage dispatched |
|---|---|---|
| PO committed, BA interrupted | PO | BA |
| PO + BA committed, IT PO interrupted | PO, BA | IT PO |
| No prior commits | (none) | First stage in pipeline |

The user sees no explicit notification that stages were skipped — the
workflow simply continues from the correct point.  If the user wants to
verify which stages ran, they can inspect `git log` on the authoring branch.

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

## §1–§3 — Stage Pipeline

Each authoring stage follows the same pattern:

1. Dispatch the stage agent.
2. Present produced ACs to the user for approval.
3. On **approve**: commit the AC files produced in this stage only (scoped
   `git add <ac-store-dir>/<files-from-this-stage>` followed by a staged
   commit). See `ACD-300g-2` for the scoping invariant. **The commit MUST
   succeed before the next stage agent is dispatched.** If the commit fails
   (pre-commit hook rejection, index conflict, or git error), return an error
   to the user and abort the pipeline — do NOT invoke the next stage agent
   with uncommitted files on disk.
4. On **edit**: re-invoke the stage agent with user feedback (one retry).
5. On **cancel**: abort. ACs produced so far remain as `readiness: draft`
   (not committed unless a prior stage already committed them).

### §1–§3 Commit-Before-Next-Stage Invariant (AC BO-1500b-1)

This is the **central invariant** of the `/create-ac` staged pipeline:

> After a stage's AC files are approved by the user, those files MUST be
> committed to the authoring branch (via the `commitStageOutput` path in
> `plan-feature.js`) **before** the next stage agent is dispatched. No
> subsequent stage may begin while the prior stage's files remain
> uncommitted on disk.

The invariant holds across all three stage transitions:

| Transition | What must be committed first |
|---|---|
| After PO stage → before BA stage | L0/L1 AC YAML files produced by `product-owner-v3` |
| After BA stage → before IT PO stage | L2/L3 AC YAML files produced by `business-analyst-v3` |
| After IT PO stage (final) | All enriched AC YAML files produced by `it-po-v3` |

After each commit, `git log` on the authoring branch MUST show a new commit
containing only that stage's AC files — this is the verifiable proof that the
invariant was satisfied before the next stage began.

**What constitutes a commit failure:** if `git commit` exits non-zero for any
reason (pre-commit hook rejection, index conflict, git lock, etc.), the stage
output commit has NOT happened and the pipeline MUST NOT proceed to the next
stage. Surface the error to the user with the hook name and failing files (if
applicable) so the user can fix the issue and re-run.

The commit message for each stage uses the form:
```
chore(ac): stage <N> — <agent-short-name> ACs for <one-line request summary>
```

(In `plan-feature.js` the message format is `plan-feature(<STAGE>): <component>`
with AC IDs and run-id in the body — both forms satisfy the invariant as long as
the commit is scoped to that stage's files only.)

---

## §D — Delivery: Push Branch and Open PR (AC BO-1500c-1)

**This step runs automatically after the final-stage commit succeeds.**  The
user is NOT asked to push the branch or open the pull request by hand.

### §D.1 — Trigger condition

Delivery runs when:

1. The authoring pipeline completed all stages (strategic, behavioral, or
   technical route).
2. The user gave final approval at the final gate (`§1–§3`, IT PO v3 stage).
3. The final `commitStageOutput()` call succeeded (exit 0).

If any earlier step failed (commit error, user cancel, user defer), delivery
does NOT run.

### §D.2 — Delivery mechanism

Delivery is implemented by `deliverAuthoringBranch()` in
`scripts/workflows/plan-feature.js`.  It:

1. **Reuses the `pull-request` agent** — dispatches `agentType: "pull-request"`
   with the authoring branch name, worktree path, AC IDs, and a pre-constructed
   PR title/body.  The user already gave final approval at the pipeline gate;
   the agent is instructed to proceed without an additional confirmation prompt.
2. **Pushes the authoring branch** to origin:
   ```
   git -C <AUTHORING_WORKTREE_PATH> push --set-upstream origin <authoring-branch>
   ```
3. **Opens a pull request** whose base is `main` and whose head is the
   authoring branch:
   ```
   gh pr create --base main --head <authoring-branch> --title "..." --body "..."
   ```
   The PR title follows the pattern:
   `chore(ac): <component> — AC authoring session approved (N ACs)`

### §D.3 — Failure tolerance

If the delivery step fails (e.g. no network, remote push rejected, `gh pr create`
error):

- The AC files are already committed on the authoring branch — the session
  work is NOT lost.
- The return payload includes `delivery_status: "error"` and a human-readable
  `message` explaining what failed, including the branch name so the user can
  push and open a PR manually.
- The overall workflow status is still `"ok"` (the approval was recorded;
  only delivery failed).

### §D.4 — Output contract

On success, the workflow return payload includes:

```json
{
  "status":          "ok",
  "acs_approved":    ["<AC-ID-1>", "..."],
  "priority":        "<priority>",
  "route":           "<route>",
  "authoring_branch": "ac-authoring/<session-slug>",
  "pr_url":          "<URL returned by gh pr create>",
  "pr_number":       "<PR number extracted from pr_url, e.g. \"42\">",
  "delivery_status": "ok"
}
```

The `message` field on a successful delivery includes both the PR number and the
clickable URL on separate lines so the user sees them immediately without running
a separate command (AC BO-1500d-1):

```
/plan-feature complete. N AC(s) approved with priority: <priority>.
Pull request opened: PR #<number>
<url>
```

`pr_number` is a string (e.g. `"42"`) extracted from the last path segment of
`pr_url`.  It is `null` when `pr_url` is absent or not a GitHub pull URL.

On delivery failure, `pr_url` and `pr_number` are both `null` and
`delivery_status` is `"error"`. The `message` field includes a manual recovery
instruction.

---

## §NM — No-Main-Commit Invariant (AC BO-1500c-3)

No commit produced by `/create-ac` or `/plan-feature` is ever placed directly
on the `main` branch.  This section documents the invariant, its mechanism, and
the defensive guard that enforces it at runtime.

### §NM.1 — The invariant

> Every AC YAML commit produced by the authoring workflow MUST land on the
> dedicated authoring branch (`ac-authoring/<slug>`).  The `main` branch is
> updated ONLY when a maintainer merges the authoring pull request opened by
> `deliverAuthoringBranch()` (§D).  No git command inside the workflow — not
> `git add`, not `git commit` — may execute against the `main` branch.

This invariant holds for both `/create-ac` and `/plan-feature`, across all
stages (PO, BA, IT-PO), including orphan-recovery commits (§PRR) and
crash-resume partial commits (§CR).

### §NM.2 — Mechanism: authoring branch isolation

The invariant is enforced structurally by the authoring worktree bootstrap (§WT):

1. **Dedicated worktree**: `scripts/setup_ticket_worktree.py create-ac-worktree`
   creates a new git worktree branched from `origin/main` to a fresh
   `ac-authoring/<slug>` branch.  The worktree path is stored as
   `AUTHORING_WORKTREE_PATH`.

2. **All commits use `-C AUTHORING_WORKTREE_PATH`**: every `git add` and
   `git commit` in the workflow is executed with `git -C AUTHORING_WORKTREE_PATH`
   (AC BO-1500a-2).  Because the authoring worktree's HEAD is on
   `ac-authoring/<slug>`, all commits land on that branch — not on `main` in
   the original checkout.

3. **`main` is reached only via PR merge**: after the user gives final approval,
   `deliverAuthoringBranch()` (§D) pushes the authoring branch to origin and
   opens a pull request whose base is `main`.  The `main` branch is updated
   only when that PR is merged by a maintainer, not by the workflow itself.

### §NM.3 — Defensive guard in `commitStageOutput()`

In addition to the structural isolation above, `commitStageOutput()` in
`scripts/workflows/plan-feature.js` includes a runtime check before every
commit:

1. If `authoringWorktreePath` is set, it runs:
   ```bash
   git -C "<authoringWorktreePath>" branch --show-current
   ```

2. If the current branch is `main` (case-insensitive), the commit is
   **aborted** immediately and the function returns:
   ```json
   {
     "status": "error",
     "message": "safety: refusing to commit AC files to main — authoring branch invariant violated (AC BO-1500c-3)"
   }
   ```
   No `git add` or `git commit` is executed.

3. If the branch check itself fails (e.g. git unavailable, worktree not yet
   initialised), a warning is logged to `console.warn` and the commit proceeds
   (**fail-open**).  Infrastructure failure must not block the authoring session;
   the structural isolation described in §NM.2 is still in place.

### §NM.4 — Scope and limitations

The no-main guard applies only when `authoringWorktreePath` is set (i.e. after
§WT has run and returned a valid worktree path).  In degraded environments where
§WT returns no worktree path (e.g. mock or test contexts), the guard is skipped
— the structural isolation is also absent in those contexts, which is acceptable
for non-production runs.

The guard does **not** prevent a user from manually committing to `main` outside
the workflow.  It is a workflow-internal safety net, not a repository-level
branch protection rule.

---

## §C — Cancel Behavior: No PR, Branch Preserved (AC BO-1500c-1-i)

**This section applies whenever the user cancels at any mid-pipeline or
final-gate prompt — i.e. any gate that is NOT the final-approval gate for
the IT PO v3 stage.**

### §C.1 — What "cancel" means in the pipeline

At every inter-stage gate (§1–§3) the user is presented with three choices:
`approve`, `edit`, or `cancel`. The **final-gate prompt** (IT PO v3, the last
stage) additionally accepts `defer`. The cancel path is the same at all gates:

- The workflow returns immediately.
- `deliverAuthoringBranch()` is **NOT called**.
- No `git push` is executed.
- No pull request is opened.

This is the **no-PR guarantee**: cancellation at any gate — including the
final gate — leaves the authoring branch in place without opening a PR.

### §C.2 — What happens to already-committed AC files

AC files committed in prior stages (i.e. files whose stage commit already
ran and succeeded) are **not deleted or reverted**.  They remain on the
authoring branch exactly as committed.  From git's perspective, the branch
is in a valid intermediate state — committed stages are durable, and the
next run will detect them via §CR (crash-resume) and skip re-authoring them.

These committed files are also **not present on `main`** at this point, because
`deliverAuthoringBranch()` (which pushes the branch and opens the PR) was
never called.

### §C.3 — What happens to the current stage's draft files

AC files written by the cancelled stage but not yet committed remain on disk
as uncommitted working-tree files.  On the next invocation of `/plan-feature`
or `/create-ac`, the §PRR pre-flight will detect them as orphaned drafts and
prompt the user to commit, discard, or abort before starting new work.

### §C.4 — Resume path

The user can resume the authoring session later by re-running `/plan-feature`
(or `/create-ac`) with the same session slug.  The §CR skip logic detects
stages already committed on the authoring branch and fast-forwards past them,
dispatching only the stage that had not yet completed.  This satisfies
AC BO-1500b-2 (crash-resume).

### §C.5 — Interaction with §D (delivery)

§D (delivery: push + PR) runs **only** after the user gives final approval
at the IT PO v3 gate **and** the final `commitStageOutput()` call succeeds.
A cancel at any prior gate prevents the code from reaching the `deliverAuthoringBranch()`
call entirely — the return statement exits the pipeline loop before §D executes.

This behavior is implemented at two sites in `plan-feature.js`:

| Site | Gate | Comment tag |
|---|---|---|
| Mid-pipeline cancel (lines ~1239–1248 plus comment) | Any gate before IT PO final | `AC BO-1500c-1-i — NO-PR GUARANTEE (mid-pipeline cancel)` |
| Final-gate cancel (lines ~1325–1333 plus comment) | IT PO v3 final gate | `AC BO-1500c-1-i — NO-PR GUARANTEE (final-gate cancel)` |

Both sites return `{ status: "ok", committed_acs, acs_as_drafts }` without
invoking `deliverAuthoringBranch()`.

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
- `§NM` — No-Main-Commit Invariant (AC BO-1500c-3): guarantees that no commit
  produced by `/create-ac` or `/plan-feature` lands on `main`; enforced
  structurally by the authoring worktree (§WT) and defensively by the branch
  check in `commitStageOutput()` in `scripts/workflows/plan-feature.js`.

<!--
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-24 [EPIC-SafeAcAuthoring/16/python-coder]: Implemented AC BO-1500d-1
  (PR number and URL are reported back to the user the moment the PR is opened).
  Added extractPrNumber() helper to plan-feature.js — a pure function that
  extracts the numeric PR number from the GitHub PR URL returned by gh pr create
  (last path segment of the URL, validated as digits-only). On the success path,
  the workflow message now shows "Pull request opened: PR #<number>\n<url>" so
  both the number and the clickable URL appear immediately in the final output
  without requiring a separate gh pr list command. Added pr_number to the return
  payload. Updated §D.4 Output contract in this SKILL.md to document pr_number
  and the new message format. Fallback: when pr_url is absent or non-numeric last
  segment, prNumber is null and the message falls back to the prior branch-name form.
  (#EPIC-SafeAcAuthoring/16)
- 2026-06-24 [EPIC-SafeAcAuthoring/13/python-coder]: Implemented AC BO-1500c-3
  (no AC-authoring commit ever lands directly on main). Added §NM (No-Main-Commit
  Invariant) section between §D and §C. §NM.1 states the invariant: every AC
  YAML commit lands on the authoring branch; main is only reached via PR merge.
  §NM.2 documents the structural enforcement mechanism: the dedicated worktree
  (§WT) and the git -C anchor (AC BO-1500a-2) prevent commits from reaching
  main's checkout. §NM.3 documents the defensive runtime guard added to
  commitStageOutput() in plan-feature.js: before any git add/commit, the function
  runs git branch --show-current on the authoring worktree; if the result is
  "main" (case-insensitive), the commit is aborted with a structured error (AC
  BO-1500c-3); if the check itself fails, a warning is logged and the commit
  proceeds (fail-open). §NM.4 notes the scope and limitations of the guard.
  Updated the Related section to cross-reference §NM. Also added the JSDoc
  NO-MAIN-COMMIT INVARIANT comment block to the deliverAuthoringBranch() function
  in plan-feature.js documenting that approved AC files reach main only via PR.
  (#EPIC-SafeAcAuthoring/13)
- 2026-06-24 [EPIC-SafeAcAuthoring/11/python-coder]: Implemented AC BO-1500c-1-i
  (cancelling before final approval leaves draft ACs on the branch and opens no
  PR). Added §C (Cancel Behavior) section between §D and §E documenting the
  no-PR guarantee: §C.1 explains what cancel means at any gate; §C.2 explains
  that prior-stage committed ACs remain on the authoring branch intact; §C.3
  covers current-stage draft files left on disk for §PRR to surface; §C.4
  documents the resume path via §CR (AC BO-1500b-2); §C.5 cross-references
  the two cancel sites in plan-feature.js that implement the guarantee.
  Added inline JSDoc comments at both cancel return sites in plan-feature.js
  (mid-pipeline ~line 1239 and final-gate ~line 1325) with tag
  "AC BO-1500c-1-i — NO-PR GUARANTEE" explaining that deliverAuthoringBranch()
  is not called, no push/PR happens, and committed AC files from prior stages
  are preserved on the authoring branch for later resume.
  (#EPIC-SafeAcAuthoring/11)
- 2026-06-24 [EPIC-SafeAcAuthoring/08/llm-expert]: Implemented AC BO-1500b-3
  (partial-run recovery pre-flight inspects authoring worktree, not original
  checkout, and reports no false orphans for already-committed AC files).
  Updated §PRR.2 to: (a) reference the new scan_draft_orphans_in_worktree()
  function in scripts/ac_store/scan_ac_orphans.py as the canonical
  implementation; (b) document the committed-file exclusion guarantee (git
  status naturally excludes committed files, so no additional filtering is
  needed); (c) clarify that after §WT runs the authoring-worktree scan is the
  only valid form; (d) show the standalone Python script invocation using the
  new draft-orphans subcommand. The --untracked-files=all flag was added to
  the example git command to match the plan-feature.js implementation.
  (#EPIC-SafeAcAuthoring/08)
- 2026-06-24 [EPIC-SafeAcAuthoring/07/python-coder]: Implemented AC BO-1500b-2
  (crash mid-pipeline leaves completed stages committed and resumable).
  Added §CR (Crash-Resume) section documenting the scanCommittedStages()
  function added to plan-feature.js. §CR.2 describes the git log detection
  algorithm (parse "plan-feature(<STAGE>):" subject lines from commits on
  the authoring branch since origin/main). §CR.3 shows the skip logic in
  the pipeline loop. §CR.4 gives a user-visible behaviour table. The
  complement of §PRR (handles uncommitted orphans); §CR handles committed
  stages that should not be re-run after a crash.
- 2026-06-24 [EPIC-SafeAcAuthoring/05/python-coder]: Implemented AC BO-1500b-1
  (each authoring stage commits its AC files before the next stage starts).
  Expanded §1–§3 from an abbreviated description to a full specification:
  added the Commit-Before-Next-Stage Invariant table (PO→BA, BA→IT PO, IT PO
  final), defined what constitutes a commit failure, and stated that the
  pipeline MUST NOT proceed to the next stage if the commit exits non-zero.
  Also updated build-single-ticket/SKILL.md to document that the per-stage
  commit invariant is enforced in plan-feature.js/create-ac, not in this skill.
  The plan-feature.js commitStageOutput() call already satisfied the invariant
  mechanically; this ticket makes the invariant explicit and verifiable.
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
