---
name: plan-feature
description: |
  Triage, orchestrate, and gate AC authoring for a user's feature request.
  Invokes the /plan-feature workflow (.claude/workflows/plan-feature.js): dispatches
  ac-triage to classify the request as strategic / behavioral / technical /
  covered. It then runs an always-on product-truth (PT) phase — classify the
  request (pt-classifier), draft only the artifacts it needs (mock-data-author,
  mockup-author, flow-author, in that fixed order, each behind an approve/edit/cancel
  gate and a surgical commit), then derive ACs from the approved flow — before
  routing through the correct authoring agents (PO v3, BA v3, IT PO v3) with user
  confirmation gates between stages. When the product-truth store is absent the PT
  phase self-skips non-silently and AC authoring still proceeds. All output goes
  exclusively to the AC store (docs/acceptance-criteria/) and the product-truth
  store (docs/product-truth/) — no ticket files are produced. The user sets priority
  at the final gate; the workflow writes readiness: approved on approval.
  Trigger phrases: "plan feature", "new AC", "author ACs",
  "write requirements", "/plan-feature".
allowed-tools: Bash, Read, Agent
workflow_script: .claude/workflows/plan-feature.js
---

# plan-feature skill

## Purpose

`/plan-feature` is the user-facing entry point to the AC authoring pipeline. It
wraps the `plan-feature.js` workflow script, which:

1. **Pre-triages** the user's request via the `ac-triage` agent (Haiku-tier)
   to check for duplicates and classify the routing path.
2. **Runs the always-on product-truth (PT) phase** (see §PT) — classifies the
   request, drafts only the artifacts it needs, and derives ACs from the approved
   flow — between triage and the AC pipeline.
3. **Dispatches** the correct authoring agents in sequence based on the triage
   result, skipping upstream agents when the request only needs downstream work.
4. **Gates** each stage transition with user confirmation — the user sees the
   ACs produced at each stage and can approve, request edits, or cancel.
5. **Writes exclusively to the AC store and the product-truth store** — no ticket
   files are produced.

## Invocation

```
/plan-feature <description> [--component <name>] [--force]
```

| Argument | Required | Description |
|---|---|---|
| `<description>` | Yes | Natural-language description of the feature or requirement. |
| `--component <name>` | No | Limit triage search to a specific component subdirectory (e.g. `--component inventory`). If omitted, all components are searched. |
| `--force` | No | Skip the duplicate check. Always creates new ACs even if existing ACs cover the request. Implicitly uses route: strategic. |

## Examples

```bash
# Author ACs for a new analytics dashboard (no existing L1 — strategic route)
/plan-feature "Allow users to export their dashboard as PDF" --component reports

# Author ACs for a behavioral addition to existing inventory feature
/plan-feature "Add sub-category filter to inventory list" --component inventory

# Force-create ACs even though the store has similar entries
/plan-feature "Inventory export as CSV" --component inventory --force

# Add a technical constraint to an existing feature
/plan-feature "Inventory API must respond in < 200ms for ≤10,000 items" --component inventory
```

## Routing Paths

| Route | When | Agents dispatched |
|---|---|---|
| `strategic` | No matching L1 AC found. New capability. | PO v3 → gate → BA v3 → gate → IT PO v3 → final gate |
| `behavioral` | Matching L1 AC found. Adding scenarios to existing feature. | BA v3 → gate → IT PO v3 → final gate |
| `technical` | Only adding technical constraints. | IT PO v3 → final gate |
| `covered` | Request fully covered by existing ACs. | Show existing ACs → user: cancel / amend / force |

## Gate Behaviour

At each gate, the user is shown the ACs produced by the previous agent and
offered three choices:

| Choice | Effect |
|---|---|
| `approve` | Proceeds to the next agent in the pipeline. |
| `edit` | Re-invokes the same agent with user-provided feedback (one retry). |
| `cancel` | Aborts the pipeline. ACs produced so far remain as `readiness: draft`. |

At the **final gate** (after IT PO v3), the user also sets the priority:
`critical`, `high`, `medium`, or `low`. Choosing `approve` + a priority sets
`readiness: approved` and `priority: <chosen>` on all ACs produced in the run.
Choosing `defer` leaves ACs as `readiness: reviewed` for a later approval run.

## Output

All AC files are written to:

```
docs/acceptance-criteria/<component>/<AC-ID>.yaml
```

Each AC file must pass `scripts/ac_store/validate_ac_schema.py` before the
workflow exits.

**No files are created in `tickets/`.** This workflow produces AC store entries
only; ticket generation from ACs is a separate concern handled by the
`/build-ac` command (AC scanner → ticket generator).

## Telemetry

The workflow logs each stage transition to `debugging/logs/agent_telemetry.jsonl`
via the `emit_event.py` script (non-blocking; failures are ignored).

## Error Handling

- If `ac-triage` returns unparseable JSON: the workflow exits with `status: error`
  and a descriptive message.
- If an authoring agent fails: the workflow retries once. If the retry fails,
  the pipeline aborts with `status: error`.
- If the AC store does not exist: triage defaults to route: strategic.

---

## §WSP — Workspace-Setup Permission Pre-flight

**This section runs BEFORE the workflow is invoked, and before §PRR below.**
It must complete before `Workflow(...)` is called. If it is skipped, the
workflow has no way to establish whether the isolated-workspace setup step
(fetch, branch-create, `git worktree add`) is permitted to run, and its own
fail-closed guard will halt the run at Stage 0 (see "§WSP.3 — Fail-closed
guard" below).

### §WSP.1 — Why this runs here, not inside the workflow (ACD-2100b-5)

The isolated-workspace setup step the workflow dispatches later runs
repository-mutating shell commands. It must only ever be dispatched to an
agent whose registered charter (`config/agent_registry.json`) grants
`permits_shell: true`. Establishing that fact requires reading a local file
-- but the E2 workflow engine (ADR-030) contextifies a workflow script's body
with EXACTLY the injected globals `agent`, `parallel`, `pipeline`, `phase`,
`log`, `args`, `workflow`, and `budget` -- no module loader and no filesystem
primitive of any kind (canonical statement: `unit_tests/
_workflow_engine_harness.py`'s docstring, "ENGINE FIDELITY" section). A
workflow body physically cannot read `config/agent_registry.json` itself.

This skill runs in the main agent loop, which has real Bash/Read access, so
it performs the read here and passes the result into the workflow through
`args` -- the only injected global that carries caller-supplied data.
Precedent for a skill-invoked pre-flight script on this same surface: §PRR
below already invokes `scripts/ac_store/scan_ac_orphans.py` by absolute path
from this skill for the identical reason.

### §WSP.2 — Running the pre-flight

Resolve `scripts/worktree/check_workspace_setup_permission.py` to its
repository-anchored, absolute, deployed location (the same resolution
mechanism §PRR.2 and the workflow's own `resolveRepoAnchoredScriptPath()`
use), then run it:

```bash
python3 <resolved-absolute-path>/scripts/worktree/check_workspace_setup_permission.py \
    --agent-id <workspace_setup_agent, default "worktree-agent">
```

The script makes NO agent dispatch and NO network call -- it reads
`config/agent_registry.json` locally, resolved repository-anchored (the same
worktree-aware, `git rev-parse --git-common-dir`-based way ACD-2100a-1 /
ACD-2100a-3 already established), so it reaches the project's real registry
even when this skill is running from inside a linked git worktree that holds
no `.leafcutter/` of its own. It always prints exactly one JSON object to
stdout and exits 0 -- including when the verdict denies permission or the
registry could not be read or parsed; a non-zero exit here means the
invocation itself was malformed, not that the check ran and denied.

The verdict's shape is `{"permits": bool, "outcome": "<str>", ...}`, where
`outcome` is one of `granted`, `read_failure`, `parse_failure`,
`agent_not_found`, `no_entries_collection`, `permission_denied` -- kept
distinguishable from one another so the workflow can report the SAME
specific facts ACD-2100b-1 through -3 require, rather than a single
collapsed boolean.

**Error handling:** if the script itself cannot be found or fails to run at
all (as opposed to running and reporting a verdict), do NOT fabricate a
permitted verdict. Proceed to invoke the workflow without
`args.workspace_setup_permission` set -- its own fail-closed guard (§WSP.3)
will halt the run with a report naming the missing pre-flight, which is the
honest fact in that situation.

### §WSP.3 — Passing the verdict into the workflow

Pass the pre-flight's raw stdout JSON through VERBATIM as
`args.workspace_setup_permission` when invoking the workflow -- never
re-derive or re-shape it. The workflow reads this key and nothing else for
this check: no dispatch, no filesystem access, and it fails closed (halts
before any authoring agent is dispatched) whenever the key is absent, not an
object, or has `permits !== true`.

This is also the guard against the bypass a skill-only check would otherwise
open: a caller who invokes the deployed workflow directly (for example
`Workflow({scriptPath: '.leafcutter/workflows/plan-feature.js'})`, a real and
currently-used invocation path that skips this skill's own pre-flight step)
supplies no `args.workspace_setup_permission` at all, so the workflow halts
with a report naming the MISSING pre-flight -- never a permission verdict it
never established.

### §WSP.4 — Performance Constraint

The pre-flight is a single local file read (plus, on the happy path, one
`git rev-parse` call to resolve the repository root) -- no network call and
no agent dispatch. It must not add a per-run cost beyond that; this section
exists to REMOVE the latency of the round-trip dispatch it replaces, not to
reintroduce it elsewhere.

---

## §PRR — Partial-Run Recovery Pre-flight

**This section runs BEFORE Stage 0.** It must complete before any authoring
agent is dispatched. If the pre-flight is skipped, a new session may overwrite
or conflict with orphaned AC files from a prior crashed session.

### §PRR.1 — When to Run

Run the Partial-Run Recovery pre-flight on every invocation of `/plan-feature`,
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
   `/plan-feature` workflow: once BEFORE §WT (targeting the original checkout)
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
   error manually before re-running /plan-feature."` and **abort the workflow**
   (do not proceed to Stage 0). The user must fix the git state before
   continuing.

3. On success, display:
   `"N AC files committed. Proceeding with new /plan-feature session."`

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
crashed `/plan-feature` session. Other uncommitted changes in the working tree are
the user's responsibility and are not touched by this pre-flight.

---

## §0 — Stage 0: Triage

After the authoring worktree has been set up and the Partial-Run Recovery
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

## §PT — Product-Truth Authoring Phase (always-on)

**This phase runs after §0 Triage and before the §1–§3 AC pipeline, on every
invocation.** It authors the product-truth artifacts a request needs so the AC
pipeline decomposes a reviewed flow rather than starting from prose. See ADR-021
and ADR-020. Behaviour (implemented in `templates/workflows-js/plan-feature.js`):

1. **Classify (always-on).** Dispatch `pt-classifier` exactly once. Derive the
   run-set from `classifier.outcome`
   (`full-set | mockup+data | mockup-only | mock-data-only | none`) via the
   canonical `OUTCOME_TO_STAGES` mapping — never the advisory `dispatch` array
   (validate `dispatch` against `outcome`; the outcome wins on disagreement). An
   unparseable/inconsistent classifier or `outcome = none` skips the PT phase and
   proceeds straight to the AC pipeline. (AC UXP-544 / UXP-544a)

2. **Store-absent self-skip (non-silent).** When the outcome is not `none`, probe
   for `docs/product-truth/` + its scripts via a `status-checker` dispatch. If
   absent, emit an **observable** telemetry/warning dispatch (never a silent
   no-op — `log()` is inert under E2) and skip the PT phase; the AC pipeline still
   runs. (AC UXP-595a)

3. **Draft the artifacts (fixed order, gated, surgical commits).** Run the run-set
   in the fixed `PT_ORDER` `mock-data-author → mockup-author → flow-author`. Each
   stage is presented at an approve/edit/cancel gate; `edit` re-dispatches the
   stage agent with feedback (bounded retries); `approve` commits that stage's
   output **before** the next agent runs. Each commit is **surgical** — only the
   reported artifact paths + their derived files + `docs/product-truth/index.json`
   (never a blanket `git add docs/product-truth`; never `docs/acceptance-criteria/`)
   — under subject `plan-feature(MOCK-DATA|MOCKUP|FLOW): <component>`. A failed
   commit aborts before the next agent; `cancel` opens no PR and preserves prior
   committed stages; a commit to `main` is refused fail-closed.
   (ACs UXP-544b / UXP-545 / UXP-545a / UXP-545b / UXP-545c / UXP-546)

4. **Flow → business-analyst.** Commit the flow + regenerated `index.json` before
   the BA stage so the BA self-discovers it via `index.json`; supply a flow
   derivation instruction. When the triage route is `technical` (no BA) but a flow
   was produced, force the BA stage in with an L1 anchor so derived L2s are not
   orphaned. (AC UXP-547)

5. **Reconcile back-links.** After the BA runs, `docs/product-truth/scripts/apply_flow_backlinks.py`
   writes the BA's reported `flow_backlinks` into the flow's `step.implements[]`
   (union, order-preserving) and re-runs `generate_product_truth.py`, on its own
   reconciliation commit. Idempotent; an unknown step id is a non-fatal warning.
   (AC UXP-548)

**Crash-resume:** committed `plan-feature(<STAGE>)` commits are recognised on
resume; already-committed stages are skipped and the flow reference is recovered
from a committed `FLOW` commit. (AC UXP-549)

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

This is the **central invariant** of the `/plan-feature` staged pipeline:

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

## §MP — Main-Branch Invocation: No Branch Switch Required (AC BO-1500e-1)

This section documents the supported — and common — case where the user invokes
`/plan-feature` while their current checkout is on the protected `main` branch.

### §MP.1 — Why invocation from main is safe

The AC-authoring pipeline is structurally isolated from the user's current
checkout.  The dedicated authoring worktree is **always** branched from
`origin/main` by `scripts/setup_ticket_worktree.py create-ac-worktree`, regardless
of which branch the user currently has checked out.  This means:

1. **The authoring worktree is independent of the user's current branch.**
   Whether the user is on `main`, a feature branch, or a detached HEAD, the
   authoring worktree always starts from the true remote tip of `origin/main`.

2. **No AC files are written to the user's main checkout.**
   All AC YAML files produced during the session land under
   `<AUTHORING_WORKTREE_PATH>/docs/acceptance-criteria/` — never under the
   user's original checkout.

3. **No commits are placed on the user's main branch.**
   The `-C AUTHORING_WORKTREE_PATH` git anchor ensures
   every `git add` and `git commit` targets the authoring worktree's branch
   (`ac-authoring/<slug>`), not the user's main checkout.

4. **The delivery PR is opened against main — not committed to main.**
   `deliverAuthoringBranch()` opens a pull request whose base is `main`
   and whose head is the authoring branch.  Approved AC files reach `main` only
   after a maintainer merges the PR — the workflow never pushes directly to
   `main`.

### §MP.2 — User experience when invoked from main

The workflow proceeds identically whether the user is on `main` or any other
branch.  No manual branch switch is required before running `/plan-feature`.

`plan-feature.js` detects the user's current branch at the start of the `run()`
function (before the worktree is created) and emits a brief informational log
when the user is on `main`:

```
[plan-feature] Detected: current checkout is on protected main branch.
[plan-feature] The AC-authoring worktree will be created from origin/main
on a dedicated ac-authoring/ branch — your main branch will not be modified.
[plan-feature] No branch switch is required. Proceeding with worktree setup.
```

This message appears in the workflow output before any authoring agent is
dispatched.  After this point the workflow continues normally: the authoring
worktree is created, partial-run recovery runs (§PRR), committed stages
are detected, and the pipeline proceeds through triage and the stage
agents.

### §MP.3 — Interaction with the no-main guard

The `commitStageOutput()` function includes a runtime guard that
aborts any commit if the authoring worktree's HEAD is on `main`.  This guard
is a safety net for misconfiguration — it should never fire when the workflow
runs normally, because the authoring worktree's branch is always
`ac-authoring/<slug>`, not `main`.

When the user is on `main` in their original checkout, the guard still operates
correctly: it checks `AUTHORING_WORKTREE_PATH`'s current branch (not the
user's checkout), which is `ac-authoring/<slug>` — so the guard passes and the
commit proceeds normally.

### §MP.4 — Branch detection is best-effort

The current-branch detection in `plan-feature.js` (used only for the
informational log) is best-effort.  If `git branch --show-current` fails (e.g.
the tool is unavailable, or the git environment is unusual), the detection is
skipped silently and the workflow continues without the diagnostic log.  The
authoring worktree is created regardless — the safety properties described in
§MP.1 are structural (enforced by the worktree isolation) and do not depend on
the branch detection succeeding.

---

## §RS — Resuming a Paused Run (ACD-2100c-1 / ACD-2100c-4)

### §RS.1 — What `paused_awaiting_input` means

When a gate along the pipeline needs a decision no live answerer can supply,
the workflow's terminal payload carries:

```json
{ "status": "paused_awaiting_input", "run_id": "<run>", "gate_id": "<gate>", "question": { ... } }
```

The run is waiting on **one specific decision**, identified by the pair
`run_id` + `gate_id` — both are required to resume it. The drafted work up to
that point is intact on disk: committed stages stay committed, and the
decision the run is waiting on is not applied until a genuine answer arrives.

**The `reason` field.** When present, `reason` explains WHY a supplied answer
was **not applied** — for example the provenance refusal in §RS.3 below, or a
`resume_answer.gate_id` that does not match the gate the run is actually
paused at. `reason` only appears on a refused resume attempt; a fresh pause
(nothing supplied yet) carries `question` instead. Surface `reason` verbatim
to the person — do not summarize, reword, or drop it. Swallowing it is the
KI-ACD-005 defect this AC exists to close: a run that refused an answer for
provenance reasons must never be reported as one that "could not understand"
the answer, because the answer was perfectly well formed.

### §RS.2 — How to resume

Re-invoke the workflow, passing the person's decision as `args.resume_answer`:

```json
{
  "gate_id": "<the gate_id from the paused terminal payload>",
  "type": "single_choice",
  "action": "approve",
  "channel": "person"
}
```

- `gate_id` — must match the gate the run is actually paused at; `resolveGate()`
  refuses a mismatch and the run stays paused.
- `type` — matches the gate's own question type (`single_choice`,
  `priority_choice`, `free_text`), read from `question.type` in the paused
  payload.
- `action` (or `choice`) — the decision itself: `approve` / `edit` / `cancel` /
  `defer`, or the free-text/priority payload the gate's question asked for.
- `channel` — the provenance marker; see the obligation below.

### §RS.3 — The provenance obligation (binding on whoever constructs this object)

Set `channel: "person"` **only** when the value in `action` is the decision
the actual human running the route gave. Never set it to relay a guess, a
default, a retry, or an answer an agent composed on the human's behalf —
provenance must be a true fact about where the answer came from, not a label
that makes the answer look accepted.

`resolveGate()` treats any `channel` other than exactly `"person"` — including
its absence — as a refusal, by design: the run stays at the decision point
and stays waiting, the named choice is not carried out, and the terminal
payload's `reason` names provenance rather than a shape or parse problem.
**That is the intended behaviour, not a bug to work around.**

Stamping `channel: "person"` on an answer the person did not actually give
defeats the gate this AC exists to enforce, and is **prohibited** — it puts
an agent's own guess in place of the human decision the gate exists to wait
for. If you are not relaying a decision the person made in this session,
omit `channel` (or leave any other value in it) and let the run keep waiting;
do not synthesize `"person"` to get past a wait it is legitimately still
owed.

---

## Related

- `templates/agents/ac-triage.md` — Haiku-pinned triage agent.
- `.claude/workflows/plan-feature.js` — the underlying workflow script (built from `templates/workflows-js/plan-feature.js`).
- `scripts/ac_store/validate_ac_schema.py` — AC YAML schema validator.
- `config/ac_schema.json` — JSON Schema for the triage output object.
- `/build-ac` — downstream command: scanner + ticket generator from existing ACs.
- `docs/architecture/adrs/ADR-010-ac-store-as-authoritative-backlog.md` —
  documents the recovery behaviour and the staged-commit model for the authoring pipeline.
- `docs/architecture/adrs/ADR-008-ac-store-schema-id-format-enforcement.md` —
  defines the `origin_agent` and `readiness` fields used to qualify orphaned ACs.
- `docs/architecture/diagrams/c2-002-ac-authoring-pipeline.md` — the authoring
  pipeline sequence diagram, updated to reflect the Partial-Run Recovery step.
- `scripts/ac_store/scan_ac_orphans.py` — orphan detection script.
- `scripts/worktree/check_workspace_setup_permission.py` — workspace-setup
  permission pre-flight (§WSP), invoked by this skill before the workflow;
  reads `config/agent_registry.json` locally and emits the verdict passed
  through `args.workspace_setup_permission`.
- `docs/architecture/adrs/ADR-030-dual-engine-workflow-support.md` —
  documents the E2 injected-globals sandbox that forced §WSP out of the
  workflow body and into this skill.
- `docs/architecture/adrs/ADR-024-interactive-pause-resume.md` — the
  pause-resume mechanism; `resolveGate()`/`pauseAtGate()` implement it, and
  §RS documents the producer (skill/caller) side of the same contract.

<!--
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 [TICKET-20260826-ACD-2100c-4/llm-expert]:
  Added §RS (Resuming a Paused Run) documenting the resume_answer contract's
  skill-side half: what a `paused_awaiting_input` terminal payload means
  (run_id/gate_id identify the wait; drafted work stays on disk; `reason`
  explains a refused resume attempt and must be surfaced, never swallowed),
  how to construct `args.resume_answer` (gate_id/type/action/channel), and
  the provenance obligation on `channel: "person"` (set only when relaying
  the actual human's own decision; never to relay a guess, default, retry,
  or agent-composed answer — doing so defeats the ACD-2100c-4 gate in
  templates/workflows-js/plan-feature.js's resolveGate() by design).
  Before this ticket, `channel` had no producer anywhere in the skill/command
  surface, so the accept path was unreachable from documented behaviour.
- 2026-06-29 [TICKET-20260629-CompleteACD1100c-MigrateCreateAcToplanFeature/llm-expert]:
  Migrated §PRR (Partial-Run Recovery Pre-flight), §1–§3 (Stage Pipeline with
  Commit-Before-Next-Stage Invariant), and §MP (Main-Branch Invocation) from
  templates/skills/create-ac/SKILL.md into this canonical plan-feature surface.
  References in templates/skills/build-single-ticket/SKILL.md repointed to this file.
  create-ac/SKILL.md and directory to be deleted by python-coder.
- 2026-09-07 [TICKET-20260826-ACD-2100b-5/python-coder]:
  Added §WSP (Workspace-Setup Permission Pre-flight), running BEFORE §PRR and
  before the workflow is invoked. Moves the workflow's Pre-Stage-0 workspace-
  setup permission gate's registry read OUT of templates/workflows-js/
  plan-feature.js's own body (which the E2 engine's ADR-030 sandbox makes
  physically incapable of reading a local file) and into a new script this
  skill runs directly: scripts/worktree/check_workspace_setup_permission.py.
  The verdict crosses into the workflow through args.workspace_setup_permission.
====================================================================
-->
