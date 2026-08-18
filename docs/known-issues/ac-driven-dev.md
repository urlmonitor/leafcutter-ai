---
title: "Known issues — ac-driven-dev"
description: "Open, observed defects in the AC-Driven Development component: the /plan-feature authoring workflow, its worktree and gate machinery, and /build-ac ticket generation. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-18
components:
  - ac_driven_dev
related_docs:
  - docs/architecture/components/ac-driven-dev.md
  - templates/skills/plan-feature/SKILL.md
  - templates/skills/build-ac/SKILL.md
---

# Known issues — ac-driven-dev

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-ACD-NNN` section using the next free number.
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

### KI-ACD-001 — `/plan-feature` cannot start in the self-hosting layout: worktree setup resolves git from the untracked workspace

- **Severity:** blocker
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/workflows-js/plan-feature.js:1740` → `scripts/setup_ticket_worktree.py` `_git_toplevel()`

**Symptom.** `/plan-feature` dies before triage, before the product-truth phase, and
before any authoring agent runs. It returns
`status: error — Authoring worktree creation failed (exit code 1)` with a
`subprocess.CalledProcessError` from `git rev-parse --show-toplevel`. Nothing is
authored and nothing is written.

**Root cause — two layers, both needed to reproduce.**

1. The workflow shells a **relative** path:
   `python .leafcutter/scripts/setup_ticket_worktree.py create-ac-worktree`, dispatched
   through a `status-checker` agent. Which copy of the script runs therefore depends on
   the caller's working directory. In the ADR-001 self-hosting dev layout the session
   cwd is the workspace parent (`leafcutter/`), so it selects
   `<workspace>/.leafcutter/scripts/` — the deployed build output.

2. `_git_toplevel()` defaults its anchor to `Path(__file__).resolve().parent`. That
   directory is `<workspace>/.leafcutter/scripts/`, and `<workspace>` is **untracked** —
   `leafcutter-ai/` is the git root, one level *down*. So `rev-parse` exits 128.

The function's own docstring names this exact layout as the thing it is protecting
against — *"the leafcutter dev layout where `leafcutter-ai/` is the git root but the
script may be launched from its parent"* — and then defeats that intent one line later
by asserting *"the script always lives physically inside the repository it operates
on."* Under self-hosting the deployed copy does not.

**Evidence.** Reproduced directly:

```
$ git -C /home/henzeh/projects/leafcutter/.leafcutter/scripts rev-parse --show-toplevel
fatal: not a git repository (or any of the parent directories): .git
exit: 128
```

The same command against any worktree-local copy succeeds and returns that worktree's
root. Full traceback in the failed run's workflow result (`run_id: scanner-hardening-1`).

**Why it is not caught by tests.** Unit tests for `setup_ticket_worktree.py` invoke it
from a `tmp_path` fixture that *is* a git repository, so the default anchor always
resolves. The failure needs the real deployed layout — a copy of the script sitting in
an untracked parent — which no fixture reproduces. Same class as the
`check_secrets` root-resolution defect fixed in GE-118a-1.

**Fix direction.** Two candidates, not mutually exclusive:

- Make `_git_toplevel()` honest about the layout it documents: on failure of the
  script-dir anchor, fall back to locating the repository rather than raising. A
  conservative rule that works: probe the immediate children of the workspace for git
  toplevels and accept the result only when exactly one is found; otherwise re-raise.
- Better, in `plan-feature.js`: stop invoking a cwd-relative `.leafcutter/` path.
  Resolve the script from the repository the workflow is operating on, so the copy that
  runs is never a function of where the session happens to be sitting.

Whichever lands must be covered by a test that executes the script from a directory
that is **not** a git repository, with the script itself outside the repo — otherwise
the fixture bias that hid this recurs.

**Workaround used 2026-08-18.** Patched the *deployed* copy at
`<workspace>/.leafcutter/scripts/setup_ticket_worktree.py` with the single-candidate
fallback above, warning on stderr when it fires. This is **build output** — `build.py`
overwrites it from `templates/`, so the workaround evaporates on the next build and is
not a fix.

---

### KI-ACD-002 — User approval gates are dispatched to a `status-checker` agent, whose out-of-scope refusal is parsed as "the user chose cancel"

- **Severity:** blocker
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/workflows-js/plan-feature.js` — the PT-phase approve/edit/cancel gate (`pt-gate-mockdata`); `resolveGate()` / gate answer parsing

**Symptom.** The gates that the skill documents as *user* decision points are not
presented to a user at all. They are dispatched as prompts to a `status-checker` agent.
That agent — correctly — replies that approving product-truth artifacts is not its job.
Its reply is then parsed as a gate answer of `action: cancel`, and the pipeline
discards the run. **No human was involved at any point.**

**Evidence.** The final agent result in the run journal for `wf_1969bd0b-43f`:

```json
{"action": "cancel",
 "feedback": "This request is outside status-checker's defined scope (ticket-state
  verification and closing per docs/agents/conventions.md). status-checker has no
  defined process for reviewing or approving mock-data-author's product-truth
  artifacts, and no ticket_path or sign-off context was provided for this dispatch.
  Recommend routing this approval gate to the agent/role actually responsible for
  product-truth review ... not status-checker."}
```

The agent diagnosed the defect and named the fix in its own refusal.

**Why this is worse than a hang.** A gate that cannot reach a user should **pause and
persist** a resumable state. Instead the failure mode resolves to `cancel`, which is the
one answer that throws work away. Any agent reply the parser cannot map to
`approve`/`edit` becomes a destructive default.

**Fix direction.** Gates must not be answered by an agent. Either surface them to the
real user, or persist a pause record and exit with a status that says "awaiting input"
— and re-enter via `args.resume_answer`, which the script already supports (ADR-024).
Separately, harden the answer parser: an unrecognised or refusal-shaped reply must
never resolve to `cancel`; fail to `pause`, never to `discard`.

---

### KI-ACD-003 — A run that authors zero ACs reports `status: "ok"`

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/workflows-js/plan-feature.js` — cancellation return path

**Symptom.** The cancelled run returned:

```json
{"status": "ok",
 "message": "Pipeline cancelled at the product-truth gate (mock-data-author).
             No PR was opened. ...",
 "cancelled_at": "pt-gate-mockdata"}
```

`status: ok` for a run that produced no ACs, opened no PR, and left a draft stranded.
A caller that branches on `status` — which is the whole point of returning one — treats
this as success. Verified independently: the authoring worktree
`worktrees/guardrail-engine` had **zero commits** and **zero AC files** afterwards.

**Fix direction.** `ok` should mean "the thing you asked for happened". A cancellation
is `cancelled`; a cancellation nobody asked for is an `error`. This is the same
false-success class as `build-feature` reporting `status: ok` with `skipped_phases: []`
while never opening a PR — see `docs/known-issues/build-orchestration.md` KI-BO-001 for
the sibling shape in the other workflow.

---

### KI-ACD-004 — Product-truth artifacts are written to the user's main checkout, not the authoring worktree

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/workflows-js/plan-feature.js` — PT phase (`mock-data-author` dispatch)

**Symptom.** `mock-data-author` wrote its artifact into the **user's main checkout**
rather than `AUTHORING_WORKTREE_PATH`, and modified a tracked file there. After the run:

```
leafcutter-ai/  (branch: main)
  ?? docs/product-truth/mock-data/guardrails/secret-scanning.mock.json   (510 lines)
   M docs/product-truth/index.json                                        (+68/-1)

worktrees/guardrail-engine/  (branch: ac-authoring/guardrail-engine)
  (no AC or product-truth changes at all)
```

The isolation the skill promises in §MP.1 — *"No AC files are written to the user's main
checkout"* — does not hold for product-truth artifacts. The worktree is created, then
not used.

**Why it matters.** It leaves `main` dirty with unreviewed generated output. In this
repo a dirty `main` is actively dangerous: a concurrent `finalize-feature` run resets it,
and the stray files are then either lost or swept into an unrelated commit. It also
defeats §PRR, whose orphan scan is scoped to the *authoring worktree* and to
`docs/acceptance-criteria/` only — so a stranded product-truth draft in the main
checkout is invisible to the recovery pre-flight that exists to catch exactly this.

**Fix direction.** Anchor the PT-phase agent dispatches to `AUTHORING_WORKTREE_PATH` the
same way the AC-stage commits are anchored with `git -C`. Then extend the §PRR orphan
scan to cover `docs/product-truth/` alongside the AC store, so a stranded draft is
detected on the next run rather than sitting in the user's checkout indefinitely.

**Workaround used 2026-08-18.** Moved the stranded mock-data file into the
`safety-security` worktree, reverted `docs/product-truth/index.json` on `main`, and
removed the untracked file — restoring `main` to clean.

---

### KI-ACD-005 — AC id allocation misses ids owned by feature folders, and has already minted a live duplicate on main

- **Severity:** high
- **Status:** open — live duplicate currently on `main`, see below
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `/plan-feature` AC-authoring stages — the id-selection step

**Symptom.** When choosing the next free AC id, the pipeline does not see ids that are
owned by an existing **feature folder**. It picked an id that a 43-file tree already
held, producing two records with the same `id` in the same component.

**Evidence — the duplicate is on `main` right now.**

```
docs/acceptance-criteria/guardrail-engine/GE-120.yaml
  id: "GE-120"   level: L2
  "A guard enforces the document types the project declared, not a narrower list ..."

docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120.yaml
  id: GE-120     level: L0
  "Trust that a green check actually checked something"       (+42 descendant files)
```

Ordering, from git:

| When | Commit | What |
|---|---|---|
| 2026-08-17 16:48 | `ec8bb173a` (#453) | the `GE-119` tree was renamed to `GE-120` — folder + 43 files |
| 2026-08-18 09:09 | `160d4f47a` (#466) | a **`plan-feature(AC)`** run authored a loose L2 *also* claiming `GE-120` |

The tree held the id for ~16 hours before `/plan-feature` reissued it. A
product-owner agent run manually on 2026-08-18 avoided the same trap only because it
was told to scan both, and reported: *"Scanned BOTH the feature folders and the LOOSE
`GE-*.yaml` files at component root (a folder-only listing under-reports)."* The
pipeline needs that behaviour by construction, not by prompt luck.

**Why nothing caught it.** See `docs/known-issues/ac-store.md` KI-ACS-001 — the
store validator behind the *required* `AC store valid` CI check does not test id
uniqueness, so a duplicate id merges clean.

**Fix direction.** Id allocation must enumerate every `id:` field actually present in
the component's store — walking the directory tree, not listing folder names or loose
files alone — and must refuse to allocate an id already in use. It should also treat
retired ids as taken: `GE-119` is recorded as retired and must never be reissued.

**Not fixed here.** Resolving the live `GE-120` collision means renaming one of the two
records. The loose L2 is the later claimant (#466) and is the cheaper move — 1 AC file
plus 4 `# covers: GE-120` tags in
`unit_tests/commit_guardian/test_ge_120_doc_types_deployed_resolution.py` — versus 43
files for the tree. Left for a decision rather than done unilaterally, because it
renames another author's AC and edits their tests.

---
