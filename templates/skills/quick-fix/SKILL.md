---
name: quick-fix
description: |
  Fast bug-fix pipeline for a single, already-diagnosed bug in one file.
  Operates in place when the current working directory is already an isolated,
  non-default-branch worktree; otherwise self-isolates into a new worktree via
  the repository's canonical `setup_ticket_worktree.py create-only` script
  before doing any work. Accepts a structured bug diagnosis (target file,
  location hint, symptom, root cause) and drives: worktree self-isolation →
  AC creation (hierarchical store) → test-first (red, AC_ENFORCE_STRICT) →
  warning checks → fix (python-coder) → green phase + mutation proof → commit
  → changelog entry → close (push + confirmed PR). Escalates to the full
  /build-feature pipeline when scope expands beyond the single target file.
  Invoked by /quick-fix.
allowed-tools: Bash, Read, Write, Edit, Agent
produces: orchestration
---

# quick-fix

This skill drives a focused, single-file bug fix from diagnosis to a pushed,
PR-ready branch.

**Two surfaces implement this workflow, and they must agree.**
`templates/workflows-js/quick-fix.js` is the primary driver — `/quick-fix`
invokes it first, and its deterministic JS control flow is what actually runs
on a current install. This file is the human-readable specification of the same
workflow *and* the executable fallback: the command falls back to loading it
when the workflow script is unavailable (pre-v2.1.154 installs). Load it when
the user invokes `/quick-fix` and no workflow script is present, or when you
need to understand or change what the workflow does.

Because both surfaces are real, **a behavioural change must land in both**. A
change made only here is documentation of something that does not happen; a
change made only in the JS leaves this file lying to the next reader. The phase
names below match the `phase()` calls in the script deliberately, so the two can
be diffed against each other.

**Isolation is conditional, not absent.** If the session's current working
directory is already inside a git worktree on a branch other than
`main`/`master`, quick-fix operates in place — the branch and directory are
unchanged from start to finish, exactly as before. But this workspace's
sessions frequently start in an untracked workspace parent (not a git repo at
all), and this repository's `main` is PR-only (branch-protection ruleset
`require-ci-lint`) — a direct commit to `main` cannot be pushed. So when the
cwd is not a suitable target (not a repo, or on `main`/`master`), quick-fix
self-isolates into a new worktree using the repo's canonical
`setup_ticket_worktree.py create-only` script (Phase 0) before doing anything
else, then operates inside that worktree exactly as it would have operated
in place.

Contrast with `build-single-ticket`: that skill always creates a new isolated
worktree from a ticket and drives a full phase-agent lifecycle. This skill
never scaffolds a ticket or epic — it isolates only when the current location
requires it, and its unit of work is a single AC, not a ticket.

> **Known AC-store gap (read before amending BP-600 ACs):** the L2 records
> `BP-600a-1`, `BP-600a-2`, `BP-600b-1`, and `BP-600d-3` under
> `docs/acceptance-criteria/build_pipeline/BP-600-quick-fix-workflow/` are
> `work_status: done` and their `criteria` fields still assert the *old*
> behaviour this rewrite replaces (no worktree ever created; three-file
> commit only). `BP-600f`'s own YAML is itself a live artifact of the old
> six-field flat AC template this rewrite retires (it is missing `level`,
> `work_status`, `depends_on`, `covered_by`, and other now-required fields).
> This skill rewrite does **not** touch AC files — that is out of scope for
> this task — so those records are now stale relative to the shipped
> behaviour. Do not let their `work_status: done` be read as confirmation
> that the old no-worktree/three-file behaviour is still correct; file a
> follow-up to amend or supersede them.

---

## Input

Accept the user's diagnosis in either format:

**Natural language:**
> "In `scripts/build_helpers.py` line 42, `_resolve_precommit_cmd()` returns a
> non-executable path because the executability probe is missing."

**Structured JSON:**
```json
{
  "target_file": "scripts/build_helpers.py",
  "location_hint": "line 42 / _resolve_precommit_cmd()",
  "symptom": "returns a non-executable path",
  "root_cause": "executability probe is missing"
}
```

Parse both into these four fields before proceeding. If any field is missing or
ambiguous, ask the user to clarify before starting Phase 0.

- `target_file` — repo-relative path to the file containing the bug (relative
  to the repo root as it will exist AFTER Phase 0 — see the worktree-relative
  note below).
- `location_hint` — line number or function name narrowing the location.
- `symptom` — observable wrong behaviour.
- `root_cause` — the mechanism causing the symptom.

> **Worktree-relative paths — read this before Phase 1.** After Phase 0
> completes, every subsequent path in this workflow (`target_file`, the AC
> store, the test file, the changelog folder) is relative to `WORKTREE_ROOT`
> — the directory Phase 0 established — **not** the directory the session
> started in. `WORKTREE_ROOT` is recorded once at the end of Phase 0 and
> reused verbatim by every later phase. This is the single most likely thing
> to get wrong: a stale reference to the original session cwd will silently
> read or write the wrong copy of a file once self-isolation has run.

---

## Your Available Sub-Agents

| Agent | Role | When spawned |
|-------|------|--------------|
| `test-writer` | Writes the failing test that covers the new AC | Phase 2 |
| `test-runner` | Executes the test and returns a narrative pass/fail report (advisory — see Phase 2/4) | Phase 2 (red), Phase 4 (green) |
| `python-coder` | Applies the targeted fix to the single target file | Phase 3 |
| `changelog-agent` | Authors the changelog entry (Steps 1–7 of its own template only; commit is handled by quick-fix, not by changelog-agent's own Step 8) | Phase 6 |
| `commit` | Stages the AC YAML(s) + test file + fixed source and commits; stages the changelog entry in a second commit | Phase 5, Phase 6 |

**Who runs the tests differs by surface, and both are correct.** The rule they
share: an unqualified verdict is never trusted for a gate decision.

Following this file, you are an agent loop with a `Bash` tool, so run
`AC_ENFORCE_STRICT=1 python -m pytest` **yourself** for the red, green,
related-test and mutation checks. A verdict you produced is better evidence
than one relayed to you, and it costs nothing here.

`quick-fix.js` cannot do that — the workflow engine has no shell primitive of
its own, only `agent()`. So it dispatches `test-runner` and closes the same gap
differently: the runner must return the exact command it ran in
`strict_command_run`, and the script refuses the verdict outright when that
string lacks the prefix. Same guarantee, reached the only way that surface can
reach it.

Do not "reconcile" these by making one imitate the other. If you change the
substance of the guarantee, change it in both.

The orchestrator also runs `gh` commands directly in Phase 7 rather than
dispatching the `pull-request` agent, since this workflow has no `ticket_path`
for that agent's sign-off protocol to attach to.

---

## Phase 0 — Guards and Self-Isolation

Run all of Phase 0 before any other action. Halt on any failure.

### Step 0.1 — Determine whether the cwd is a usable git worktree

```bash
git rev-parse --is-inside-work-tree 2>/tmp/quick-fix-worktree-check.err
```

- If this command exits non-zero (prints `fatal: not a git repository` to the
  redirected stderr file), set `NOT_A_REPO = true`.
- If it exits 0 and prints `true`, set `NOT_A_REPO = false` and continue to
  Step 0.2.

### Step 0.2 — Read the current branch (only when `NOT_A_REPO = false`)

```bash
git rev-parse --show-toplevel
```

Record the output as `SESSION_REPO_ROOT`.

```bash
git branch --show-current
```

Record the output as `CURRENT_BRANCH`. An empty string (detached HEAD) counts
as "no usable branch" below.

### Step 0.3 — Decide: operate in place, or self-isolate

```
NEEDS_ISOLATION = NOT_A_REPO
                  OR CURRENT_BRANCH == ""
                  OR CURRENT_BRANCH == "main"
                  OR CURRENT_BRANCH == "master"
```

**If `NEEDS_ISOLATION` is false:** operate in place — this preserves the
skill's original identity for the common case. Set:
- `WORKTREE_ROOT = SESSION_REPO_ROOT`
- `ACTIVE_BRANCH = CURRENT_BRANCH`

Skip to Step 0.5 (Uncommitted Changes Guard).

**If `NEEDS_ISOLATION` is true:** proceed to Step 0.4 (Self-Isolation).

### Step 0.4 — Self-Isolation (Guard BP-600a-2, rewritten)

This replaces the old "no isolation, ever" guard. Two conditions make that
guard unworkable in this repo: a session cwd that is the
untracked workspace parent has no git branch to report at all, and `main` is
PR-only (`require-ci-lint` ruleset, 6 required checks) — a direct commit to
`main` cannot be pushed, so offering "commit straight to main" is a dead end.

**Step 0.4.1 — Locate the canonical worktree-setup script.**

```bash
pwd
```

Record the output as `SESSION_CWD` (this is well-defined even when
`NOT_A_REPO` is true).

Check the two supported layouts, in order:

```bash
ls "<SESSION_CWD>/scripts/setup_ticket_worktree.py"
```

```bash
ls "<SESSION_CWD>/leafcutter-ai/scripts/setup_ticket_worktree.py"
```

The first candidate that exists is `SCRIPT_PATH` — the first is the deployed
consumer/dev-root layout, the second is the dev workspace-parent layout where
`leafcutter-ai/` is a subdirectory (see this repo's own `CLAUDE.md`
"Repository Structure" section). If **neither** exists, halt:

```
Halt: cannot locate setup_ticket_worktree.py under <SESSION_CWD>/scripts/
or <SESSION_CWD>/leafcutter-ai/scripts/. quick-fix cannot self-isolate.
Provide the correct project directory and re-run /quick-fix.
```

Derive `SCRIPT_REPO_ROOT` by stripping the trailing
`/scripts/setup_ticket_worktree.py` from `SCRIPT_PATH` — this is the
leafcutter-ai git repository root, used as the `-C` anchor below.

**Step 0.4.2 — Guard against a stale local `main` (mandatory, before creating anything).**

`create-only` roots the new branch at the **local** `main` HEAD, not
`origin/main` — this is the one subcommand in `setup_ticket_worktree.py` that
does this (`create-ac-worktree` and `create-fastlane-worktree` both root at
`origin/main`; see the module's `_create_worktree()` docstring). A stale local
`main` would silently produce a stale branch, so check first:

```bash
git -C "<SCRIPT_REPO_ROOT>" fetch origin
```

```bash
git -C "<SCRIPT_REPO_ROOT>" rev-list --left-right --count main...origin/main
```

The output is `<L>\t<R>` — commits only on local `main` (L) and commits only
on `origin/main` (R). **If R is non-zero, halt:**

```
Halt: local main is <R> commit(s) behind origin/main.
setup_ticket_worktree.py create-only roots the new branch at LOCAL main,
so proceeding now would silently create a stale branch.

Fast-forward local main first:
  git -C "<SCRIPT_REPO_ROOT>" checkout main
  git -C "<SCRIPT_REPO_ROOT>" merge --ff-only origin/main

Then re-run /quick-fix with the same diagnosis.
```

Only proceed to Step 0.4.3 when R is 0.

**Step 0.4.3 — Derive a slug and create (or reuse) the worktree.**

Derive a kebab-case slug from the diagnosed bug (e.g. a bug in
`fast_lane.py`'s structural-parent resolution becomes
`fast-lane-structural-parent`).

```bash
python "<SCRIPT_PATH>" create-only "<slug>"
```

This is idempotent: a second run with the same slug reuses the existing
worktree and reports `created: false` rather than failing. It also runs the
full bootstrap (build.py, pre-commit shim install, `.pre-commit-config.yaml`
symlink) — this is *why* the script is used instead of a hand-rolled `git
worktree add`: a hand-made worktree gets none of that bootstrap and silently
skips all package pre-commit hooks for the entire session.

Parse the single-line JSON payload from stdout:

```json
{"worktree_path": "...", "branch": "feature/<slug>", "created": true}
```

Set:
- `WORKTREE_ROOT = <worktree_path from the payload>` — do not guess this path
  any other way.
- `ACTIVE_BRANCH = <branch from the payload>` — always `feature/<slug>`. The
  script always prefixes with `feature/`; it does **not** honour `fix/`,
  `bugfix/`, `hotfix/`, or `chore/` prefixes on creation. This is a current
  limitation of the script, not a choice made by this skill — do not tell the
  user their branch will be named anything other than `feature/<slug>`.

### Step 0.5 — Branch invariant (re-anchored)

Whichever path Step 0.3/0.4 took, `ACTIVE_BRANCH` is now fixed for the rest of
this run. After every phase that touches git state, verify the branch has not
changed:

```bash
git -C "<WORKTREE_ROOT>" branch --show-current
```

If it differs from `ACTIVE_BRANCH`, halt immediately:

```
Halt: branch changed from '<ACTIVE_BRANCH>' to '<current>' during quick-fix.
This is a bug — quick-fix must never switch branches after Phase 0.
```

Note the re-anchoring: the invariant is now "the branch established by Phase
0", not "the branch the session started on" — the two differ whenever
self-isolation ran.

### Guard BP-600a-3 — Uncommitted changes guard

Check whether the target file has uncommitted changes, anchored to
`WORKTREE_ROOT`:

```bash
git -C "<WORKTREE_ROOT>" status --porcelain
```

If the output contains the `target_file` path (on any line beginning with
`M`, `A`, `D`, `R`, or `??`), halt immediately:

```
Halt: '<target_file>' has uncommitted changes in <WORKTREE_ROOT>.
Commit or stash your current work before running /quick-fix.

Option A — stash:
  git -C "<WORKTREE_ROOT>" stash

Option B — commit in two steps:
  git -C "<WORKTREE_ROOT>" add <target_file>
  git -C "<WORKTREE_ROOT>" commit -m "wip: save work before quick-fix"

Then re-run /quick-fix with the same diagnosis.
```

Do not proceed past this guard if the target file is dirty.

---

## Phase 1 — AC Creation (rewritten for the hierarchical store)

The store is hierarchical, not flat:
`docs/acceptance-criteria/<component>/<L0-slug-dir>/<ID>.yaml`, with
`L0 → L1 → L2 → L3`. A six-field flat record (the old template) is rejected
by `check_ac_schema.py`. Ground every write below against the actual hooks
(`scripts/commit_guardian/check_ac_schema.py`,
`scripts/commit_guardian/check_ac_limits.py`,
`scripts/commit_guardian/check_ac_parent_covered_by.py`,
`scripts/ac_store/validate_ac_schema.py`, and
`_ac_schema_validators.validate_test_contract`), not against memory of a past
run.

### Step 1.1 — Locate the L0 component

Read `<WORKTREE_ROOT>/docs/acceptance-criteria/index.yaml`. Match
`target_file` against the `directory_patterns` fields (if present) or the
component whose `description` best matches the file's role. Record the
matching component `prefix` (e.g. `BP`) and kebab `id` (e.g.
`build-pipeline`).

**When nothing matches, stop and ask** — do not fall back to a default
component (`BP-600b-2-i`). List the candidates you considered and let the user
name the right one. There is no safe default: `build-pipeline` is a real
component that would silently absorb a criterion belonging to another, the AC
file is permanent by design (Step 1.4's output is never deleted or moved by any
later phase, including escalation), and this same phase already stops and asks
in three adjacent situations — no matching L1 (Step 1.2), a parent at its child
cap (Step 1.3), and an underscore id missing from `components.json` (below).
Guessing the component while asking about the others is the inconsistency, and
it is the more consequential of the two vocabulary axes.

This is not hypothetical. `BP-600f.yaml` in this repo was created misfiled by a
real `/quick-fix` run and stayed wrong for six weeks before anyone noticed.

**Two-axis component vocabulary — do not conflate them.** The scalar
`component:` field on the new AC YAML takes this kebab-case `id`
(e.g. `build-orchestration`) from `index.yaml`. The `components:` LIST field
takes the underscore id (e.g. `build_orchestration`) from
`docs/components.json` — a different registry for a different axis (AC
namespace vs. knowledge-graph membership). The default heuristic in this
repo's existing store is a straight hyphen→underscore swap
(`build-orchestration` → `build_orchestration`, `ac-driven-dev` →
`ac_driven_dev`), but this is a convention, not a guarantee — confirm the
underscore id actually exists in `docs/components.json` before writing it:

```bash
grep -n "<underscore-id>" "<WORKTREE_ROOT>/docs/components.json"
```

If it does not exist under the swapped name, do not invent one — stop and ask
the user which registered component id applies.

### Step 1.2 — Locate the matching L1 (do not invent new L0/L1 nodes)

List the existing L0 directories for the component and read the L1 files
inside the one whose title/criteria best matches the diagnosed behaviour
(match against `target_file`, `symptom`, and `root_cause`):

```bash
ls "<WORKTREE_ROOT>/docs/acceptance-criteria/<component-id>/"
```

Read the candidate L0/L1 YAML files to confirm the match.

**If a clear matching L1 exists**, record it as `PARENT_L1` (id + file path)
and proceed to Step 1.3. **If no L1 plausibly covers the diagnosed behaviour**,
this is out of scope for `/quick-fix` to improvise — authoring new L0/L1
nodes is Product-Owner/Business-Analyst territory (`/plan-feature`), not a
bug-fix decision. Stop and ask the user to identify the correct parent, or to
redirect to `/plan-feature` if this is genuinely new capability rather than a
fix to existing behaviour.

### Step 1.3 — Determine level, id, and respect the child caps

List the L2 (and any L3) children already on disk under `PARENT_L1`'s L0
directory. `check_ac_limits.py` hard-caps `_MAX_L1_PER_L0 = 7` and
`_MAX_L2_PER_L1 = 5` (children with `status: superseded_by`/`superseded` do
not count). Also read `PARENT_L1`'s own YAML for a `child_limit_override`
field, which — only when explicitly present and ≥ the default — raises the
cap for that parent.

- **If `PARENT_L1`'s active L2 child count is below its effective cap:**
  create a new L2 sibling, ID `<PARENT_L1>-<N+1>` (next unused integer
  suffix), describing the corrected behaviour. This is the common case for a
  genuinely new behavioural fix.

- **If the cap is already reached** (as observed in a real run against
  `BO-2600a`, which sat at exactly 5 L2 children): do **not** add
  `child_limit_override` yourself — that is an audited waiver, not a
  quick-fix decision. Instead, check whether the diagnosed bug is a
  **technical constraint on an already-specified L2 behaviour** (an edge
  case, an additional invariant, a boundary condition on something that
  already works) rather than a wholly new behaviour. If so, create a
  Roman-suffix L3 child on the most relevant existing L2 sibling:
  `<chosen-L2-id>-i` (or `-ii`, `-iii`, ... — increment past any existing
  Roman children of that L2). This is the right shape only when the fix is a
  constraint on existing behaviour; if the bug genuinely needs a new L2
  behaviour and the parent is already full, stop and ask the user — an
  `ac-tree-split` or an explicit `child_limit_override` is a decision for a
  human, not something `/quick-fix` should apply silently.

### Step 1.4 — Write the AC YAML with the real required field set

Write the file at
`<WORKTREE_ROOT>/docs/acceptance-criteria/<component-id>/<L0-slug-dir>/<NEW-ID>.yaml`.

**Hard-required by `config/ac_store_schema.json`** (validated by
`jsonschema` when present, which is the dominant path — `validate_manually()`
is only a fallback when the schema or the `jsonschema` package is absent):
`id`, `title`, `component` (kebab), `components` (list, underscore),
`status`, `criteria`.

**Also required in practice** so the AC is usable and passes the other
hooks and downstream tooling:

```yaml
id: <NEW-ID>
components:
  - <underscore-component-id>
title: "<one-line title describing the correct behaviour the fix enforces>"
component: <component-id>
level: <L2 or L3>
status: active
req_status: draft
work_status: todo               # stays todo until Phase 5 flips it, not before
readiness: approved             # triggers the test-contract requirement below
priority: medium
roadmap_phase: phase_1
criteria: |
  Given <context matching the diagnosed situation>
  When  <the action or input that previously triggered the bug>
  Then  <the correct outcome that the fix must produce>
  And   the bug symptom ("<symptom>") must not occur
depends_on: [<PARENT_L1 or PARENT_L2 id>]
doc_links:
  - path: <target_file>
    relationship: modifies
    status: exists
assigned_agent: python-coder
estimated_complexity: S
delivers_to: null
expects_from: null
origin_agent: <committing user or agent identity>
created: <YYYY-MM-DD>
amended_by: []
superseded_by: null
covered_by: []
implemented_by: []
change_target: code
risk_surface: internal
test_spec:
  - name: <planned test function name, matching what test-writer will produce in Phase 2>
    target_dir: <the unit_tests/ subdirectory this component's tests live under>
    framework: <unittest or pytest, matching the target file's existing test suite>
    type: unit
    description: "<what the test asserts, derived from the criteria above>"
```

**Why `readiness: approved` + `test_spec` together, and why `test_spec` is
not optional here:** `validate_test_contract()` (in
`_ac_schema_validators.py`, wired into `check_ac_schema.py`) requires a
non-empty `test_spec` on any AC that is `readiness: approved`,
`work_status != done`, targets code (`change_target` in the code/schema set),
and is a leaf (`level` in `L2`/`L3`) — exactly the shape of the AC this phase
just created. Leaving `test_spec` empty, or setting `test_required: false` on
a code AC, is rejected outright: a code AC always needs tests. Do not set
`test_required: false` here.

`origin_agent` remains required by the `check-ac-governance` hook — set it to
the committing user's identity; fall back to a recognised authoring agent
name only when no human identity is available.

This AC YAML file is permanent. It must NOT be deleted or moved after the
lifecycle closes, even if the workflow later aborts.

### Step 1.5 — Back-link the parent (mandatory, same-commit)

Read the parent file (the L1 for a new L2 child, or the L2 for a new L3
technical-constraint child) and use the `Edit` tool to append the new child's
id to its `covered_by:` list.

**This parent file MUST be staged in the same commit as the child** (Phase
5). The AC guardian hooks — `check_ac_parent_covered_by.py`,
`check_done_proof.py` — validate only the files present in that commit's git
index; they do not read the store. An unstaged parent is never checked, so a
stale `covered_by` silently rots. This is documented in this repo's own
`CLAUDE.md` under "AC-store commits — stage the parent alongside the child" —
Phase 5 below stages the parent explicitly for this reason.

### Step 1.6 — Validate before continuing

Fail fast here rather than discovering a hook failure at commit time:

```bash
python "<WORKTREE_ROOT>/scripts/ac_store/validate_ac_schema.py" "<new-ac-absolute-path>"
```

If this reports errors, fix the AC YAML (and re-run) before proceeding to
Phase 2. Do not pass a bare directory to this script — it does no globbing of
its own and silently reports "No YAML files to validate" while exiting 0.

---

## Phase 2 — Test-First (Red Phase)

### Step 2.1 — Dispatch test-writer

Dispatch the `test-writer` agent with all four diagnosis fields plus the AC
path (all paths anchored to `WORKTREE_ROOT`). Pass as the agent input:

```
Write a failing test for the bug described below.
The test MUST include the comment `# covers: <AC-ID>` near the top of the
test function or class.

AC file:        <WORKTREE_ROOT>/docs/acceptance-criteria/<component-id>/<L0-slug-dir>/<AC-ID>.yaml
Target file:    <WORKTREE_ROOT>/<target_file>
Location hint:  <location_hint>
Symptom:        <symptom>
Root cause:     <root_cause>

The test must fail (red phase) against the current unmodified code.
```

Record the path to the test file written by `test-writer`. Call it
`TEST_FILE` (absolute, under `WORKTREE_ROOT`).

### Step 2.2 — Red-phase verification (orchestrator-run, strict)

Run the test yourself with the strict flag — do not rely solely on a relayed
`test-runner` verdict for this decision:

```bash
AC_ENFORCE_STRICT=1 python -m pytest "<TEST_FILE>" -v
```

**Why `AC_ENFORCE_STRICT=1` is mandatory, both here and in Phase 4:**
`scripts/ac_store/pytest_ac_enforcement.py` downgrades any failing test that
covers a not-yet-`done` AC to `xfail` — and the AC this workflow just created
is by definition not `done` yet. Running the default (non-strict) invocation
during the red phase reproduces exactly the false-green conditions a real run
hit: the default invocation showed green on a genuinely failing test; only
`AC_ENFORCE_STRICT=1` showed the true (red) result. `AC_ENFORCE_STRICT=1
python -m pytest ...` is a single env-prefixed command and is allowed under
this project's shell convention.

You may additionally dispatch `test-runner` for a narrative report, but its
verdict is advisory only — the strict pytest invocation above is authoritative
for the halt/continue decision below.

**Expected: the command exits non-zero (FAIL).** If it exits 0 (PASS) against
unmodified code, halt:

```
Halt: the test written by test-writer PASSES (under AC_ENFORCE_STRICT=1)
against unmodified code. This means either the bug has already been fixed, or
the test does not actually cover the diagnosed bug.

Options:
  1. Re-diagnose: confirm the bug reproduces on the current branch.
  2. Re-write: re-invoke /quick-fix with a corrected diagnosis.
  3. Skip: if the bug is already fixed, no further action is needed.
```

Do not proceed to Phase 2.5 or Phase 3 until the red phase is confirmed.
Record the full failure output as `RED_PHASE_OUTPUT`.

---

## Phase 2.5 — Root-Cause Divergence Warning (BP-600e-2)

Compare `RED_PHASE_OUTPUT` (the strict-mode failure/traceback from Step 2.2)
against the diagnosed `root_cause`.

If the failure pattern diverges — e.g. the test fails with an error unrelated
to the diagnosed cause (different exception, different module, different line
than `location_hint`) — display this warning and wait for user input before
continuing:

```
Warning: the test failure suggests the root cause may differ from your diagnosis.

  Diagnosed: <root_cause>
  Observed:  <actual failure message / key traceback lines>

Options:
  - "continue" — proceed with the fix as diagnosed (you accept the risk)
  - "re-diagnose" — abort /quick-fix and start over with an updated diagnosis

What would you like to do?
```

Do NOT proceed until the user explicitly replies "continue" or "re-diagnose".
On "re-diagnose", halt cleanly and preserve the AC YAML (already written — do
not delete it).

---

## Phase 3 — Fix (BP-600d-1, BP-600d-2)

### Step 3.1 — Dispatch python-coder

Dispatch the `python-coder` agent with the full diagnosis and the AC to apply
the fix. Pass as the agent input:

```
Apply a targeted fix for the diagnosed bug.

CONSTRAINT: Modify ONLY the target file listed below. Do not touch any other
source file. If the fix logically requires changes to other files, do NOT make
those changes — instead return a note listing what additional changes would be
needed. The /quick-fix workflow will handle escalation.

AC file:        <WORKTREE_ROOT>/docs/acceptance-criteria/<component-id>/<L0-slug-dir>/<AC-ID>.yaml
Target file:    <WORKTREE_ROOT>/<target_file>
Location hint:  <location_hint>
Symptom:        <symptom>
Root cause:     <root_cause>
```

### Step 3.2 — Capture modified files

After python-coder returns, check which files were modified:

```bash
git -C "<WORKTREE_ROOT>" status --porcelain
```

Record the set of modified files as `MODIFIED_FILES`.

---

## Phase 3.5 — Scope Expansion Warning (BP-600e-1)

If `MODIFIED_FILES` contains any file other than `target_file` (ignoring the
AC YAML(s) and the test file, which are expected additions), display this
warning:

```
Warning: python-coder modified files beyond the target.

  Target file:      <target_file>
  Additional files: <list each extra modified source file>

This may indicate the bug requires a larger fix than /quick-fix supports.

Options:
  - "continue" — accept the scope expansion and proceed to the green phase
  - "escalate" — hand off to the full /build-feature pipeline

What would you like to do?
```

Wait for user input.

**On "continue":** proceed to Phase 4.

**On "escalate":** run the escalation path (see Escalation section below).

---

## Phase 4 — Green Phase + Mutation Proof (BP-600c-3)

### Step 4.1 — Green-phase verification (orchestrator-run, strict)

```bash
AC_ENFORCE_STRICT=1 python -m pytest "<TEST_FILE>" -v
```

**Expected: exits 0 (PASS).** If it exits non-zero (FAIL), halt with a
structured report:

```
Halt: the test is still failing after the fix (AC_ENFORCE_STRICT=1).

  Test file:     <TEST_FILE>
  AC:            <AC-ID>
  Failure:       <failure message / key traceback lines>

The fix applied by python-coder did not resolve the bug. Options:
  1. Respawn python-coder with this failure as additional context.
  2. Escalate to /build-feature for a deeper investigation.
  3. Inspect the fix manually and re-run /quick-fix after editing.
```

Do not commit if the green phase fails. You may additionally dispatch
`test-runner` here for a narrative report, but the strict invocation above is
authoritative.

### Step 4.2 — Mutation proof (mandatory before commit)

Green-after-red is not sufficient evidence that the test is actually coupled
to the fix — the test could be passing for an unrelated reason. Prove the
coupling by reverting the fix and confirming the test goes red again, per this
repo's own doctrine ("Gate / Workflow ACs — Verify Behaviorally, Not by Grep"
and "Real-artifact behavioral spot-check before declaring done" in
`CLAUDE.md`):

```bash
git -C "<WORKTREE_ROOT>" stash push -- "<target_file>"
```

```bash
AC_ENFORCE_STRICT=1 python -m pytest "<TEST_FILE>" -v
```

**Expected: exits non-zero (FAIL)** — with the fix stashed away, the bug is
back. If this instead still PASSES, halt:

```
Halt: the test remains GREEN with the fix stashed away (target_file reverted
to its unmodified state). The test is not actually coupled to the bug fix —
it may be passing for an unrelated reason.

Do NOT mark this AC done. Options:
  1. Rewrite the test so it genuinely exercises the fixed code path.
  2. Re-diagnose: the fix may not be addressing the real root cause.
```

If it correctly fails, restore the fix and confirm green one more time before
proceeding:

```bash
git -C "<WORKTREE_ROOT>" stash pop
```

```bash
AC_ENFORCE_STRICT=1 python -m pytest "<TEST_FILE>" -v
```

**Expected: exits 0 (PASS) again.** Record this whole red→green,
stash-revert→red, stash-pop→green sequence as `MUTATION_PROOF_OUTPUT` for the
close-phase summary. Do not proceed to Phase 5 until this final PASS is
confirmed.

---

## Phase 5 — Commit (BP-600d-3, rewritten file list)

Dispatch the `commit` agent. Provide exact staging instructions — this is no
longer three files; it is at least four, because the AC-store back-link from
Step 1.5 must land in the same commit as the child AC it back-links:

```
Stage and commit exactly these files:

  1. <parent AC YAML path>       — updated covered_by back-link (Step 1.5)
  2. <new child AC YAML path>    — new acceptance criterion (Step 1.4)
  3. <TEST_FILE>                 — new test covering the bug
  4. <target_file>               — bug fix

If Step 1.3 created an L3 technical-constraint child instead of an L2, both
the L2 (immediate parent) and the L1 (grandparent, unchanged) are NOT both
required — only the immediate parent (the L2) needs its covered_by updated
and staged.

Also flip on the child AC file: work_status: todo -> done, and add
implemented_by: [<target_file>] and covered_by: [<TEST_FILE relative path>]
before staging it — do this NOW, not as a follow-up commit, per this repo's
"AC-store reconciliation" convention (a done fix with a stale todo AC is a
phantom-done vector).

Commit message format:
  fix(<component-id>): <one-line description of the fix> (<AC-ID>)

  Covers <AC-ID>: <AC title>
  Root cause: <root_cause>

Do not stage any other files.
```

The `commit` agent handles pre-commit hook failures and the autofix retry loop
per its own protocol. If the commit fails after the retry loop is exhausted,
halt and surface the commit agent's failure message verbatim to the user.

Record the resulting commit SHA as `FIX_COMMIT_SHA`.

---

## Phase 6 — Changelog (new phase — closes the CI gap)

`Changelog entry present` is one of six **required** status checks on `main`
(`scripts/release/check_changelog_presence.py`). Every path this workflow
touches (`docs/acceptance-criteria/` is exempt, but `target_file` and
`TEST_FILE` are not) means a `/quick-fix` PR is always releasable content and
therefore always requires an entry — this phase is never optional.

### Step 6.1 — Author the entry (prefer the agent)

Dispatch `changelog-agent`, but instruct it to perform **only Steps 1–7 of
its own template** (range/collect/categorize/write) and to **skip its own
Step 8** (`git add` + `git commit`). Quick-fix's own `commit` agent will stage
and commit the entry file in Step 6.2 below — this avoids a second, separate
commit path that bypasses this repo's commit-delegation hook.

Pass as input: the range is exactly `FIX_COMMIT_SHA` (a single commit), the
`type` is `manual`, and the `components` list is drawn from
`docs/components.json` for the packages `target_file` lives under (same
underscore-id lookup as Phase 1). Frontmatter shape (confirmed against a real
entry under `changelogs/`): `title`, `date`, `time`, `type`, `components`,
`summary`, `description`, `commits: [<FIX_COMMIT_SHA short form>]`,
`breaking: false`.

If `changelog-agent` is unavailable, author the entry file by hand under
`<WORKTREE_ROOT>/changelogs/YYYY-MM-DD-HHMM-<kebab-title>.md` with the same
frontmatter shape — read an existing entry under `changelogs/` first to match
the exact field set rather than guessing.

### Step 6.2 — Commit the entry

Dispatch the `commit` agent a second time:

```
Stage and commit exactly this file:

  1. <new changelog entry path>

Commit message:
  docs(changelog): entry for <AC-ID>
```

(`docs(changelog):` is this repo's actual convention for changelog-only commits
— confirm with `git log --format=%s -- changelogs/` before changing it.)

This produces a second, small commit on the same branch, before push — so the
`Changelog entry present` gate is satisfied the first time the branch is
pushed, not discovered missing after CI runs.

---

## Phase 7 — Close (BP-600d-4, push + confirmed PR)

Run these operations in order. Each is a separate Bash or Agent call (no
chaining).

### Step 7.1 — Push

```bash
git -C "<WORKTREE_ROOT>" push origin HEAD
```

If this fails, halt immediately:

```
Halt: push to origin failed.

  Error: <push error output>

The fix is committed locally (in <WORKTREE_ROOT>) but NOT visible on the
remote. The work will NOT be considered closed until the push succeeds.

Recovery:
  1. Check your network connection and remote permissions.
  2. Re-run: git -C "<WORKTREE_ROOT>" push origin HEAD
  3. Then re-run the close phase.
```

Do not proceed to Step 7.2 until the push succeeds.

### Step 7.2 — Switch to the non-EMU account before any `gh pr` command

```bash
gh auth switch --user urlmonitor
```

This repo's default `gh` account is EMU-blocked for PR creation
(`createPullRequest` mutation). Run this before any `gh pr` command below,
every time — do not assume the prior session already switched.

### Step 7.3 — Check for an existing PR

```bash
gh pr list --head "<ACTIVE_BRANCH>"
```

If a PR already exists, log its URL and skip to Step 7.5.

### Step 7.4 — Open the PR (confirmation-gated)

A PR is now mandatory to land the work — the branch is never `main`, so
nothing merges without one. Draft a title (≤70 chars) and a body (Summary +
Test plan, mirroring the `pull-request` agent's own body contract), then show
both to the user and wait for an explicit "yes" before opening anything:

```
Proposed PR:

  Title: <title>

  Body:
  <full body>

  Branch: <ACTIVE_BRANCH> -> main

OK to open the PR? (yes / edit / cancel)
```

On "cancel" or any negative: stop here, do not open a PR, and report the push
as complete with no PR — print the compare URL instead:
`https://github.com/<org>/<repo>/compare/main...<ACTIVE_BRANCH>`.

On "yes" (or "edit" then a subsequent "yes"): **write the PR body to a file
first, then reference it with `--body-file`.** Do not pass the body inline on
the command line — a body containing a bare identifier like `TKT-500f-1`
gets shell-interpolated and corrupts the published PR (`TKT-500f-1: command
not found` was published inside a PR body in a real run because of this).

Use the `Write` tool (never `python -c` or a heredoc — see Constraints) to
create `/tmp/quick-fix-pr-body-<AC-ID>.md` with the drafted body, then:

```bash
gh pr create --title "<title>" --body-file "/tmp/quick-fix-pr-body-<AC-ID>.md"
```

Capture the PR URL from the output.

Leave merging out of scope — that stays the user's call.

### Step 7.5 — Confirm close

Print the completion summary:

```
/quick-fix complete.

  AC:            <AC-ID> — <AC title>
  Test:          <TEST_FILE>  [green, mutation-proven]
  Fix:           <target_file>
  Fix commit:    <FIX_COMMIT_SHA>
  Changelog:     <changelog entry path>
  Worktree:      <WORKTREE_ROOT>
  Branch:        <ACTIVE_BRANCH>
  PR:            <PR URL or "none — see compare link above">
```

---

## Escalation Path (BP-600e-3)

Escalation is triggered by:
- User choosing "escalate" in Phase 3.5 (scope expansion), OR
- Any other condition where the fix cannot be contained to `target_file`.

**Escalation steps:**

1. Do NOT delete or revert any artefacts already created (AC YAML(s), test
   file). Leave them in `<WORKTREE_ROOT>`. If they are already committed,
   they remain.

2. Print the escalation summary:

```
/quick-fix is escalating to the full build pipeline.

Preserved artefacts (in <WORKTREE_ROOT>):
  AC:           <AC-ID>  [docs/acceptance-criteria/<component-id>/<L0-slug-dir>/<AC-ID>.yaml]
  Test file:    <TEST_FILE>
  Target file:  <target_file>
  Root cause:   <root_cause>
  Branch:       <ACTIVE_BRANCH>

Next steps:
  1. Stage and commit the AC YAML(s) and test file if not already committed:
       git -C "<WORKTREE_ROOT>" add <parent AC YAML path> <child AC YAML path> <TEST_FILE>
       git -C "<WORKTREE_ROOT>" commit -m "chore: stage quick-fix artefacts for escalated fix (<AC-ID>)"

  2. Create a ticket referencing the AC:
       /create-ticket
       > Fix the multi-file bug diagnosed by /quick-fix. AC ID: <AC-ID>.
       > Test file already written: <TEST_FILE>
       > Target file: <target_file>
       > Root cause: <root_cause>

  3. Drive the ticket through the full pipeline, from the SAME worktree:
       /build-feature <ticket-path>
```

3. Halt. Do not run Phase 4, 5, 6, or 7.

---

## Stop-and-Ask Rule

The `/quick-fix` skill MUST stop and ask the user (do not proceed
automatically) when:

- Phase 0.4.2 finds local `main` behind `origin/main` (non-zero right-hand
  count) — do not create a worktree from a stale base.
- Neither candidate location for `setup_ticket_worktree.py` exists
  (Phase 0.4.1) — quick-fix cannot self-isolate without it.
- Guard BP-600a-3 fires (uncommitted changes in the target file).
- Phase 1 Step 1.2 finds no clearly matching L1 parent for the diagnosed
  behaviour — authoring new L0/L1 nodes is PO/BA scope, not a bug-fix
  decision.
- Phase 1 Step 1.3 finds the parent L1/L2 at its child cap AND the bug is a
  genuinely new behaviour (not a technical constraint on an existing one) —
  do not silently add `child_limit_override` or split the tree.
- Phase 2.2 red-phase verification finds the test already passes under
  `AC_ENFORCE_STRICT=1`.
- Phase 2.5 divergence warning fires.
- Phase 3.5 scope expansion warning fires.
- Phase 4.1 green-phase verification fails.
- Phase 4.2 mutation proof finds the test still green with the fix reverted —
  the test is not actually coupled to the fix.
- Phase 5 commit fails after the retry loop is exhausted.
- Phase 7.1 push fails.
- Phase 7.4, before opening any PR (outward-facing action) — always wait for
  explicit "yes".
- The diagnosis input is missing any of the four required fields.
- The target file does not exist in the repository.

Never attempt to auto-resolve any of the above. Surface the exact condition to
the user with the available options and wait for explicit direction.

---

## Constraints

- **Single-command bash rule** — every Bash call is a single, simple command.
  No `&&`, `;`, `||`, pipes, or multi-line scripts. An `ENV=val command`
  prefix (e.g. `AC_ENFORCE_STRICT=1 python -m pytest ...`) counts as one
  command and is allowed. Use `git -C "<path>"` instead of `cd`. Redirect
  stderr to `/tmp/`, never a relative path.
- **File edits go through Read/Edit/Write, never inline interpreters** — do
  not write a PR body, changelog entry, or AC YAML via `python -c`, `sed -i`,
  heredocs, or `echo >>`. Use the `Write` or `Edit` tool.
- **One file only** — python-coder is instructed to modify ONLY `target_file`.
  This constraint is non-negotiable; scope expansion triggers escalation
  (Phase 3.5).
- **AC file is permanent** — do NOT delete or move any AC YAML written by
  this workflow after creation, even if the workflow aborts mid-run.
- **Isolation is conditional, not absolute** — quick-fix operates in place
  whenever the cwd is already a usable, non-default-branch worktree. It
  self-isolates via `setup_ticket_worktree.py create-only` only when the cwd
  is not a git repo, or is on `main`/`master`, or is in detached HEAD. It
  never uses `worktree-agent`, the `feature` skill, or a raw `git worktree
  add` — always the canonical script, for its bootstrap side-effects.
- **Branch invariant, re-anchored** — the branch established at the end of
  Phase 0 is the branch at Phase 7. Verify with
  `git -C "<WORKTREE_ROOT>" branch --show-current` after every git-touching
  phase.
- **No registry or build pipeline edits** — do not edit
  `config/agent_registry.json`, `scripts/build.py`,
  `scripts/build_phases.py`, `scripts/build_precommit.py`, or any
  commit-guardian manifest.
- **Commit via the `commit` agent only** — never call `git commit` directly;
  this repo's `enforce_commit_delegation` hook blocks it, and the sign-off /
  autofix protocol lives entirely in that agent.
- **Scope boundary** — this skill does not create tickets or epics, and it
  does not merge a PR — opening one (Phase 7.4) is confirmation-gated, and
  merging is always left to the user.
