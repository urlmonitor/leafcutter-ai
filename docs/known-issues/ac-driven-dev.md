---
title: "Known issues — ac-driven-dev"
description: "Open, observed defects in the ac-driven-dev component: AC selection and prioritisation, ticket generation from AC records, and the traceability block the downstream gates read. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-26
components:
  - ac_driven_dev
related_docs:
  - docs/architecture/components/ac-driven-dev.md
  - docs/architecture/components/phantom-done-prevention.md
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

### KI-ACD-001 — `ac_prioritizer` discards each AC's `priority` field, so `critical` never surfaces

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/ac_store/ac_prioritizer.py:209` — `complexity_to_priority(ac.get("estimated_complexity", ""))`

**Symptom.** The prioritiser never reads the `priority:` field that PO/BA/IT-PO author
on every AC. It derives the queue position **solely** from `estimated_complexity`, via
`COMPLEXITY_TO_PRIORITY` (`S → high`, `M → medium`, `L → low`, `XL → low`). Two
consequences:

1. No AC can ever be reported as `critical` — nothing in the mapping produces that
   value, even though `critical` is a valid `priority` in the AC schema and
   `PRIORITY_ORDER` ranks it first.
2. The ordering is **inverted from author intent**: a large critical defect (`L` →
   `low`) sorts *below* a small cosmetic one (`S` → `high`). Effort is being used as a
   proxy for importance.

**Evidence.** `ACD-1900b-5-i` — `priority: critical`, `estimated_complexity: L`, a live
vacuous-pass defect in the pre-commit path — was reported by `ac_prioritizer.py` as
`[ac] [low]` at position **465 of 477** in the READY queue. Grepping the full run output
for `critical` returns zero matches across all 477 entries. `/build-ac` selecting "the
next highest-priority unimplemented AC" would not have reached it; the ticket was only
built because the AC was targeted explicitly by id.

**Fix direction.** Rank on the AC's own `priority` when present, and fall back to the
complexity mapping only when it is absent. Complexity is a scheduling input (how big is
this), not a priority signal (how much does it matter) — the two should be separate sort
keys, not the same one. Note `PRIORITY_ORDER` already handles `critical` correctly, so
the fix is in what gets *fed* to it, not in the sort.

---

### KI-ACD-002 — Generated Agent Contracts lines have no pipe delimiters, so documentation-verifier fail-closes on every generated ticket

- **Severity:** high
- **Status:** open
- **Occurrences:** 2
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-26
- **Where:** `scripts/ac_store/generate_ticket_from_ac.py` — the `## Agent Contracts` →
  `### documentation-expert` emitter

**Symptom.** `documentation-verifier` (priority 11.9, immediately before `commit`)
parses each `- [ ] AC-N:` line under `### documentation-expert` as three pipe-delimited
fields, `<genre> | <target_path> | <content_constraint>`, and emits `(status: blocker)`
on any line without them. The generator emits no pipes at all:

```
- [ ] AC-1: [(unspecified genre)] templates/agents/ac-fulfillment-gate.md — <criterion text>
```

So the verifier fail-closes at Step 2 on **every** generated ticket whose source AC
carries `doc_links`, and the documentation phase is never actually verified. Because the
blocker is correctly classified `cross_agent` (it names the ticket generator as the
responsible sibling), the phase is *skipped* — and the build still reports `status: ok`.

A second defect sits in the same line: `target_path` is populated from the AC's
`doc_links` **`describes`** entries, which point at whatever the AC references —
frequently an agent template or a Python module, not a documentation file. Even with
pipes added, the path named is often not a doc.

**Evidence.** `TICKET-20260818-ACD-1900b-5-i.md:262` carried exactly one such line,
naming `templates/agents/ac-fulfillment-gate.md` as the documentation target. The
verifier blocked with "Agent Contracts line is malformed (no pipe-delimited
target_path)". Repaired by hand on that branch — naming the two docs
`documentation-expert` actually wrote — so the phase could run; the generator itself is
unchanged and will reproduce this on the next generated ticket.

**Occurrence 2 — 2026-08-26, `TICKET-20260825-BP-900g-8.md:263`, during PR #578.** The
generator reproduced the malformed line exactly as predicted above, and the drive played
out precisely as the first occurrence describes: `documentation-verifier` fail-closed,
the blocker was classified `cross_agent`, and the phase was skipped. Repaired by hand on
that branch again. Two things this occurrence adds:

**A third defect in the same line: the contract is emitted even when the AC says no
documentation exists.** `_resolve_doc_genres` (`:1841-1849`) reads the parent L1's
`documentation_triggers`; when that list is **empty** it logs a WARNING and returns the
`["(unspecified genre)"]` marker — then the caller emits the contract line anyway. But an
empty `documentation_triggers` is not a missing value. It is the AC store's way of saying
*this change requires no documentation*, and `BP-900g.yaml:23-24` says exactly that, with
a written rationale that the change introduces no user-facing surface. So the generator
takes a deliberate "no docs" declaration, converts it to a marker meaning "genre unknown",
and emits a documentation obligation the parent AC explicitly disclaims.

That turns the malformed-line defect into a compounding one. `documentation-verifier`
blocks on the missing pipes; repair the pipes and it blocks again, this time demanding a
document the governing AC states must not exist. There is no form of the line that both
parses and is satisfiable. On BP-900g-8 the only correct resolution was to record the
verifier as `not_needed` — verified against its own dispatch condition
(`requires_documentation_verification`, absent from the ticket) rather than against the
line it was choking on.

**The warning is real but goes nowhere.** Unlike the pipe defect, this one *does* log at
WARNING naming the AC. It is emitted at ticket-generation time, into the generator's
stderr, hours or days before the drive that trips over it — nothing carries it forward to
the drive, and no gate reads it. A warning whose only consumer is a human watching a
one-off command is, in practice, silence.

**Fix direction.** Three changes, in increasing order of value:

1. Emit the pipe-delimited format the verifier documents.
2. Source `target_path` from the docs the change *requires* (the `creates`/`modifies`
   doc_links, or the `requires_documentation` types) rather than from `describes`
   back-references.
3. **Distinguish "no documentation required" from "genre unknown."** An empty
   `documentation_triggers` on the parent should suppress the `### documentation-expert`
   subsection entirely — and, correspondingly, should stop the generator marking
   `documentation-expert: needed` in the agents map. Only a parent that is genuinely
   *unresolvable* warrants the `(unspecified genre)` marker. Distinguishing these is what
   stops the pipe fix from converting one blocker into another.

Whatever lands should be covered by a test that runs the generator and then runs the
verifier's Step 2 parser over the output — the two sides have disagreed silently, which is
the same producer/consumer divergence class as the `ac_traceability` shape mismatch that
`ACD-1900b-5-i` fixes. Add a second case for the empty-`documentation_triggers` parent,
asserting that **no** contract line is emitted at all.

---

### KI-ACD-003 — `ac-fulfillment-gate` returns `ok` on an AC it left with `covered_by: []`

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/agents/ac-fulfillment-gate.md` — the Step 3 auto-fix / Step 5
  verdict, for the `covered_by` field specifically

**Symptom.** The gate's stated job is to verify that `work_status`, `implemented_by` and
`covered_by` are accurate before a commit is allowed. Observed outcome on a real run: it
returned `ok`, and the AC it verified was left with `work_status: done`,
`implemented_by` correctly populated with five paths, and **`covered_by: []`** — while
five `# covers:`-tagged tests for that AC existed and were passing. So `implemented_by`
is reconciled and `covered_by` is not, yet the verdict is `ok` either way.

An AC marked done with no `covered_by` is a phantom-done vector in the same sense as
KI-BO-002 (which is the mirror case: `mark_done` populates neither). Whichever of the
two fields is missing, the store loses the link between the claim and its proof.

**Evidence.** `ACD-1900b-5-i` after its build: gate verdict `ok` (journal
`wf_ebe75602-f98`), `covered_by: []` on disk, and
`done_proof.verify_done_eligible("ACD-1900b-5-i")` independently returning
`eligible: True` with all five test node-ids listed under `passing_tests`. The proof
existed and was discoverable by an existing helper — the gate simply did not write it
back. Populated by hand on that branch. The same run also failed to add the new
behavioural test to `BO-201`'s `covered_by`, even though the AC's own `it_requirements`
explicitly required BO-201 to gain its first executing coverage via a
`# covers: BO-201` tag; that tag was written into the test but never reflected in the
store.

**Fix direction.** Reuse `done_proof.verify_done_eligible`, which already returns the
passing covers-tagged tests, to populate `covered_by` during the same auto-fix pass that
populates `implemented_by`. Make an empty `covered_by` on a `work_status: done` AC a
blocking condition rather than a silent pass — the gate that exists to prevent
unevidenced "done" should not itself sign one off. Note the fix must also reconcile ACs
named in a `# covers:` tag other than the ticket's own (the BO-201 case), which the
current pass does not consider at all.

**Related.** KI-BO-002 (`mark_done` leaves `implemented_by: []`) — same family, other
field, other code path.
</content>

### KI-ACD-004 — `/plan-feature` cannot start in the self-hosting layout: worktree setup resolves git from the untracked workspace

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

### KI-ACD-005 — User approval gates are dispatched to a `status-checker` agent, whose out-of-scope refusal is parsed as "the user chose cancel"

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

### KI-ACD-006 — A run that authors zero ACs reports `status: "ok"`

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

### KI-ACD-007 — Product-truth artifacts are written to the user's main checkout, not the authoring worktree

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

### KI-ACD-008 — AC id allocation misses ids owned by feature folders, and has already minted a live duplicate on main

- **Severity:** high
- **Status:** open — live duplicate currently on `main`, see below
- **Occurrences:** 2
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-25
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
| 2026-08-17 16:48 | `ec8bb173a` (#453) | a tree was renamed onto `GE-120` from its now-retired predecessor id — folder + 43 files |
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
retired ids as taken: the id between GE-118 and GE-120 is recorded as retired and
must never be reissued (see PR #453; not written out here, because the GE-122e-1
guard fails the build on any live citation of it).

**Not fixed here.** Resolving the live `GE-120` collision means renaming one of the two
records. The loose L2 is the later claimant (#466) and is the cheaper move — 1 AC file
plus 4 `# covers: GE-120` tags in
`unit_tests/commit_guardian/test_ge_120_doc_types_deployed_resolution.py` — versus 43
files for the tree. Left for a decision rather than done unilaterally, because it
renames another author's AC and edits their tests.

**Update — the collision is resolved (2026-08-18); the allocator defect above is NOT.**
The loose L2 was renumbered from `GE-120` to `GE-118c` and moved into
`docs/acceptance-criteria/guardrail-engine/GE-118-hooks-work-in-worktrees/`, parented under
`GE-118` (2 of 7 children -> 3 of 7). Its four `# covers:` tags moved with it and the test
module was renamed to `test_ge_118c_doc_types_deployed_resolution.py`. The goal tree keeps
`GE-120`, as its claim is test-enforced by `unit_tests/commit_guardian/test_ge_122e_1.py`.
A suffix-shaped id was chosen over the free root number `GE-124` because
`check_ac_parent_covered_by.py` and `scan_ac_orphans.py` derive a parent from id SHAPE and
`derive_parent_id()` returns `None` for a root id — a root-shaped id would carry a parent
link no gate could police. The evidence block above is left exactly as written: it records
what was true on `main` when this issue was filed. **This entry stays open** — nothing about
the id-allocation step has changed, and the next `/plan-feature` run can still mint a
duplicate the same way.

**Second occurrence, 2026-08-25 — and it widens the entry.** A `business-analyst` run
authoring ACs for `GE-122d` allocated `BP-900h-4`, an id already live and
`readiness: approved` on `main`. Caught before the PR by a manual store-wide grep;
renumbered to `BP-900h-6` across 11 references.

Two things this adds to the entry as written above. First, the defect is **not confined to
`/plan-feature`**: this run was a directly-dispatched authoring agent in an isolated
worktree, so the fix must land in whatever the shared id-allocation step is, not in one
command's prompt. Second, and worse for detection, the collision was minted **in a
worktree branched from `origin/main`** — the colliding id was present in the branch's own
checkout the whole time. So this is not a stale-clone problem that fetching would fix; the
allocator simply did not look. Combined with KI-ACS-001 (the required `AC store valid`
check does not test id uniqueness), a duplicate authored this way reaches `main` with every
gate green.

---

### KI-ACD-009 — `/plan-feature` halts before any authoring agent and blames a registry field that is correct

- **Severity:** blocker
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** `templates/workflows-js/plan-feature.js:1745-1790` — the `resolve-workspace-setup-permission` step and the `permitsShell` fail-closed branch

**Symptom.** Every run halts with:

> Workspace-setup step 'worktree-setup' is configured to dispatch to agent
> 'worktree-agent', whose registered charter does not permit running repository/shell
> commands. … Fix the workspace_setup_agent configuration or
> `config/agent_registry.json`'s `permits_shell` field for that agent.

**The message is false.** `worktree-agent` has `permits_shell: true`
(`config/agent_registry.json:1368`). Following the remedy leads an operator to a field
that is already correct, and there is nothing there to fix.

**Root cause — a lookup failure rendered as a permissions verdict.** The step reads the
registry by dispatching a `status-checker` agent to `cat` it, then:

```js
const match = entries.find((e) => e && e.id === workspaceSetupAgentId);
permitsShell = !!(match && match.permits_shell === true);
```

`permitsShell` is `false` for *four different reasons* — agent dispatch failed, output
unparseable, file unreadable, or the id genuinely absent — and only the last is a
permissions problem. All four print the permissions message. Failing closed is right;
asserting a specific false cause is not.

**Two independent causes were both present in the observed run**, which is why this is a
blocker rather than a flake:

1. **The path does not exist.** The deployed workflow reads
   `.leafcutter/config/agent_registry.json` (relative). Verified 2026-08-19: that file
   exists at the **workspace root** (`<workspace>/.leafcutter/config/`) but **not** in a
   worktree's `.leafcutter/`. So the `cat` fails for any run whose cwd is a worktree —
   deterministically, not intermittently. Same self-hosting-layout class as KI-ACD-004,
   different resolution site.
2. **The dispatch itself errored.** The run recorded
   `[resolve-workspace-setup-permission] failed: API Error: Connection lost
   mid-response`, so `permissionResult` was `null` and the parse could not have
   succeeded regardless.

Either alone produces the halt. Because a transient API error is indistinguishable in
the output from a real mis-assignment, a reader cannot tell a retryable failure from a
configuration one.

**Evidence.** Run `wf_359683cc-51a`, 2026-08-19, from
`worktrees/safety-security`. 3 agents dispatched, 2 completed, 1 errored; halted before
triage and before any authoring agent, so zero ACs were produced.

```
$ ls <worktree>/.leafcutter/config/agent_registry.json
ls: cannot access ...: No such file or directory
$ find <workspace> -name agent_registry.json -not -path '*/worktrees/*'
<workspace>/leafcutter-ai/config/agent_registry.json
<workspace>/.leafcutter/config/agent_registry.json
```

**Fix direction.** Three separable changes:

- **Distinguish the four outcomes.** Report `could not read the registry at <path>`,
  `could not parse it`, `agent <id> not found in it`, and `agent <id> has
  permits_shell: false` as different messages. Keep failing closed — the objection is to
  the diagnosis, not the caution. This is the same "green means checked" distinction
  `GE-120` draws, inverted: a check that could not run must not report a specific verdict
  about what it did not see.
- **Resolve the registry path, do not hardcode a relative one.** Use the same root
  resolution the guardian hooks use, so the read works from a worktree as well as the
  workspace root.
- **Do not gate startup on a live agent dispatch to read a static local file.** The
  workflow runtime can read it directly; routing it through a `status-checker` adds an
  API round-trip whose failure mode is a false halt.

**Why it matters beyond the message.** `/plan-feature` is the mandated entry point for
all new work (`CLAUDE.md`, "New Work Goes Through ACs"). While this holds, that path is
closed from any worktree, and the only way to author ACs is to dispatch the PO/BA/IT-PO
agents by hand — which skips the triage, the gates, and the staged-commit invariant the
workflow exists to enforce.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M8, inverted — not a check
reporting success it did not establish, but a check reporting a *specific failure cause*
it did not establish.

---

### KI-ACD-010 — An ASCII comma in an AC title survives every normalisation step and lands in the epic folder name, the AC store, and Master_Plan

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/goal_to_epic.py:217` (`_normalize_non_ascii_punct`) and `:306`
  (`_to_pascal_case`, the split regex)
- **Reported by:** customer bug report 2026-08-25

**Symptom.** An epic folder is created whose name ends in a comma. The punctuation is
not cosmetic damage confined to the folder — it becomes the epic's identity, so every
downstream field derived from that name carries the comma too.

**Root cause.** Punctuation removal in this generator has exactly two paths, and an
ASCII comma is on neither. `_normalize_non_ascii_punct()` normalises **non-ASCII**
punctuation, symbols and separators only, so a plain `,` is untouched by construction.
`_to_pascal_case()` then splits the normalised title on `[\s\-_]+` — whitespace, hyphen,
underscore — and a comma is none of those either, so it is not a separator and is not
dropped. It simply rides along inside whatever word token it is attached to and emerges
in the PascalCase result. There is no third filter and no final whitelist, so nothing
downstream can catch it.

**Evidence.** AC `DTW-100n` produced a folder named literally
`EPIC-ReconcileWiringNodesToRealRdkMaterials,` — trailing comma included. From there the
comma propagated into `target_epic` on **8** ACs, into every `implemented_by` path those
ACs carry, and into the generated Master_Plan. The name is 39 characters, which keeps it
under the 40-character `_EPIC_NAME_MAX_CHARS` cap (`:314`), so truncation never fired and
never incidentally clipped the trailing character — a one-character-longer title would
have hidden the defect by accident.

**Why it ranks high rather than low.** This corrupts silently and persistently. A blocked
commit is loud and costs an hour; this lands bad data *in the AC store*, survives the
epic, requires manual cleanup across 8 records plus their paths, and poisons any
traceability lookup that string-matches on epic names — a search for
`EPIC-ReconcileWiringNodesToRealRdkMaterials` will not match the folder that exists.

**AC-coverage note — this is a phantom-done instance, and it should be recorded as one.**
`ACD-1200a-3-iii` is `work_status: done` and `readiness: approved`, and it explicitly
claims that the em-dash "and any surrounding stray punctuation" are stripped, and that
the resulting name "does not end in a dangling separator". The observed folder name ends
in a dangling separator. The claim is false as written, and the store says it is
satisfied and approved. Its three tests
(`unit_tests/ac_driven_dev/test_acd_1200a_3_iii.py`) every one construct a title
containing an em-dash; none feeds an ASCII comma, and none feeds any ASCII punctuation at
all. The trailing-character assertion the criterion depends on
(`result[-1].islower() or result[-1].isdigit()`) would in fact have caught the comma — it
was simply never given one.

**Fix direction.** Strip or normalise ASCII punctuation on the same path as non-ASCII, so
there is one place where "what is not allowed in a name" is decided. Better still, make
the final derived name conform to an explicit `[A-Za-z0-9]` whitelist before it is used
for anything — a whitelist cannot be defeated by a character class nobody thought of,
which is precisely how this survived. Whatever lands must be parametrised over ASCII
punctuation, not over one more hand-picked character.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M4 — the fixtures encode the
punctuation the author had in mind (the em-dash they were fixing), not the punctuation
real AC titles contain.

---

### KI-ACD-011 — Epic-name truncation has no phrase awareness, so names end on a dangling preposition or article

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/goal_to_epic.py:385-433` — `_truncate_pascal_at()`
- **Reported by:** customer bug report 2026-08-25

**Symptom.** A long AC title yields an epic name that stops mid-phrase, on a word that
carries no meaning by itself.

**Root cause.** `_truncate_pascal_at()` locates word starts with
`re.finditer(r"[A-Z][a-z0-9]*")` and keeps the longest prefix that fits under the cap.
That is a PascalCase *word boundary* and nothing more. It has no notion of content words
versus function words, so a preposition or article that happens to fall inside the budget
is kept and becomes the last word of the name.

**Evidence.** AC `DTW-100r` produced `EPIC-WiringReconciliationActuallyLandsInThe`.

**AC-coverage note — a behaviour gap, not a regression.** No existing AC claims this.
`ACD-1200a-3-iii` requires only that truncation cut at a PascalCase word boundary, and
`…InThe` satisfies that requirement literally: it ends on a complete word, and it passes
the criterion's own trailing-character assertion because `e` is lowercase. File this as
new behaviour to specify rather than as a broken promise — the promise that exists was
kept.

**Note which path this is.** `_derive_epic_name()` (`:436`) reaches truncation only when
`_summarise_title_via_llm()` is unavailable or errors; when the summariser answers, the
concise name it returns is used instead. So this is the offline/fallback path — which
means it is the path CI takes, the path any key-less environment takes, and the path any
run takes when the API is having a bad minute. The degraded path is the common one, not
the rare one.

**Fix direction.** Drop trailing stopwords after truncating, or require the fallback to
cut at the last *content*-word boundary rather than the last word boundary. Either way,
keep the cap — the defect is where the cut lands, not that a cut happens.

---

### KI-ACD-012 — The generated `Master_Plan.md` is missing six fields the repo's own ticket guard requires

- **Severity:** high
- **Status:** open
- **Occurrences:** 3
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/goal_to_epic.py:1626` — the frontmatter block in
  `_render_master_plan()`; against `templates/hooks/ticket_frontmatter_guard.py`
- **Reported by:** customer bug report 2026-08-25

**Symptom.** The generator emits an artifact that the repository's own pre-commit gate
rejects. Every epic it produces therefore arrives with a Master_Plan that cannot be
committed without either hand-editing the file or skipping the hook.

**Root cause — producer and consumer disagree about the required field set.**
`_render_master_plan()` writes frontmatter with five keys: `epic_name`, `created`,
`status`, `components`, `source_ac`. `ticket_frontmatter_guard.py` demands rather more.
Its `REQUIRED_FIELDS` constant (`:26`) is
`("title", "status", "components", "created", "depends_on")`; on top of that it calls
`_check_required_tristate()` for `requires_diagram` and `requires_adr` (`:556-557`), and
`_check_change_target()` / `_check_risk_surface()` (`:560-561`) — the last two promoted
from optional to REQUIRED by BO-610-4.

Intersecting the two lists leaves **six** required fields the generator never writes:
`title`, `depends_on`, `requires_diagram`, `requires_adr`, `change_target`,
`risk_surface`. Note also that `epic_name` and `source_ac`, the two keys the generator
does emit beyond the overlap, carry no weight with the guard at all — so the artifact is
not merely thin, it is describing itself in a vocabulary the gate does not read.

**AC-coverage note — a genuine spec gap.** No AC claims this. `ACD-1200a-8` is
`work_status: todo` and enumerates Master_Plan **content** only; it never mentions
frontmatter fields, so even completing it as written would not close this. There is no
criterion anywhere stating that generated artifacts must satisfy the gates that guard
hand-written ones.

**Second occurrence, 2026-08-25.** Reproduced verbatim by
`goal_to_epic.py --ac GE-120`: the generated `EPIC-TrustThatAGreenCheckActuallyChecked/Master_Plan.md`
was rejected for exactly the six fields named above. Fixed by hand in that epic — `title`,
`type: epic`, `depends_on: []`, `requires_diagram`, `requires_adr`, `change_target`,
`risk_surface` added, and `status` corrected from `in_progress` to `todo`, since no ticket
in the epic has been started. The generator is unchanged, so the next epic reproduces it.

**Third occurrence, 2026-08-25** — and it reconciles this entry with `KI-ACD-019`'s
correction, which are both right about different gates. Reproduced by
`goal_to_epic.py --ac GE-122d` (`EPIC-TheNumberingGuaranteeHoldsAtEveryStage`); all six
fields supplied by hand again. Three runs, three identical hand-repairs — this is not
intermittent.

**There are two gates and they disagree by four fields.** Verified against both:

| Gate | When it fires | Required set | Generator misses |
|---|---|---|---|
| `check_doc_frontmatter.py`, config `templates/scripts/commit_guardian/commit_guardian.json` → `ticket_frontmatter.required_fields` | pre-commit, on `tickets/**/*.md` | `title`, `status`, `components`, `created`, `depends_on` | **2** — `title`, `depends_on` |
| `templates/hooks/ticket_frontmatter_guard.py` | Claude Code `PreToolUse` on `Edit`/`Write` | the same 5, plus `requires_diagram`, `requires_adr` (`:556-557`), `change_target`, `risk_surface` (`:560-561`) | **6** |

`KI-ACD-019` is right that the generator writes through Python file I/O and so never trips
the `PreToolUse` guard on generation, making the commit-blocking count 2. What it misses is
the sequel: **the moment anyone opens the file with `Edit` or `Write` to supply those two,
the `PreToolUse` guard fires and demands four more.** That is why every run so far has been
repaired to the full six — not because six were commit-blocking, but because the act of
repairing is itself an `Edit`. The number is 2 or 6 depending on how you fix it, and there
is no route that requires only 2.

So the fix direction below is unchanged, but the regression test must run **both** gates:
satisfying only the pre-commit set leaves a Master_Plan no agent can subsequently edit.
The four-field divergence between the two gates is worth closing on its own merits — a
hand-written ticket and a generated one are held to different standards today.

**Fix direction.** Render the full required frontmatter set. Then add a test that runs
`ticket_frontmatter_guard` against a freshly generated Master_Plan, so the generator and
the gate cannot drift apart again — the two are maintained independently and each is
individually correct, which is exactly the condition under which a divergence goes
unnoticed. The test must run the real guard rather than assert a field list, or it
becomes a second copy of the requirement that can itself fall behind.

---

### KI-ACD-013 — `goal_to_epic.py` writes a `target_epic` field the AC schema rejects, so every epic it generates fails the required store gate

- **Severity:** high
- **Status:** fixed (schema extended 2026-08-25; no regression test yet)
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/goal_to_epic.py` (`_write_target_epic_field`,
  `_read_target_epic_from_file`, call sites `:1111-1129`) against
  `config/ac_store_schema.json`

**Symptom.** Generating an epic from `GE-120` wrote `target_epic: EPIC-...` into all 37
leaf AC records. `config/ac_store_schema.json` sets `additionalProperties: false` and has
no `target_epic` property, so `validate_ac_schema.py` reported a violation on **every one
of the 37 records**:

```text
GE-120a-1.yaml: schema violation at <root> — Additional properties are not allowed
  ('target_epic' was unexpected)
```

`AC store valid` is one of the six required status checks on `main`. So the tool's normal,
successful output cannot be merged.

**This is not a corrupt write — the field is deliberate.** `_write_target_epic_field()`
records which epic an AC's ticket was assembled into, and `_read_target_epic_from_file()`
reads it back on a re-run to decide whether the AC already belongs to one. It is the
idempotency mechanism. Stripping it would make every re-run re-append it.

**Why it went unnoticed until now.** A store-wide grep found `target_epic` on exactly
**37 records — the 37 this run just created**. No previously-generated epic carries it.
So `goal_to_epic.py --ac` has never produced a committed epic in this repository, and the
incompatibility had no opportunity to surface. The tool and the gate were each correct in
isolation and had simply never met.

**Fix applied.** `target_epic` added to `config/ac_store_schema.json` as an optional
string. The data was right and the schema had not learned about it.

**Residual — no test binds the two.** Nothing runs `validate_ac_schema` over the output of
`goal_to_epic`. The same class of drift can recur with the next field either side adds.
The regression test must generate a small epic and validate the touched records with the
real validator, not assert a property list — a property list is a second copy of the
schema that can itself fall behind (same reasoning as KI-ACD-012).

**Pattern:** a first-party producer and a required gate that were never run against each
other.

---

### KI-ACD-014 — `goal_to_epic.py` writes absolute filesystem paths into `implemented_by`

- **Severity:** medium
- **Status:** open (data corrected by hand 2026-08-25; generator unchanged)
- **Occurrences:** 2
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/goal_to_epic.py` — the `implemented_by` back-reference write

**Symptom.** After generating the GE-120 epic, all 37 AC records carried a
machine-specific absolute path:

```yaml
implemented_by:
- /home/henzeh/projects/leafcutter/leafcutter-ai/tickets/00_inbox/epics/EPIC-.../15_TICKET-20260825-GE-120b-4.md
```

Every other path field in the store is repo-relative (`docs/…`, `tickets/…`,
`templates/…`). An absolute path baked into a tracked YAML file resolves only on the
machine that generated it, so the AC→ticket link is dead in CI, in any other clone, and in
any consumer install.

**Note what the tool got right, because it narrows the bug.** The tickets are first written
loose into `tickets/00_inbox/`, then moved into the numbered epic folder. The generator
correctly **re-pointed** every back-reference to the post-move location — the link targets
are accurate. Only their form is wrong. So the defect is a missing
`relative_to(project_root)` at the write, not a path-tracking error.

**Fix applied to the data.** All 37 rewritten to repo-relative; verified that each one
resolves to a file that exists.

**Second occurrence, 2026-08-25.** Reproduced by `goal_to_epic.py --ac GE-122d` on all
nine ACs of `EPIC-TheNumberingGuaranteeHoldsAtEveryStage`, rewritten to repo-relative by
hand again. This run was made **from a worktree**, so the embedded prefix was
`/home/henzeh/projects/leafcutter/worktrees/ge122-acs/…` — a path that does not exist even
on the machine that generated it once the worktree is removed. Worth stating because the
first occurrence's absolute path at least pointed at the main checkout and so looked
merely redundant; from a worktree the same defect writes a link that is dead everywhere,
including locally.

**Fix direction for the tool.** Make the back-reference relative to the project root at
the point of write, and assert repo-relativity in the same test that covers KI-ACD-013 —
both are "the generator writes store data the store's own conventions reject."

---

### KI-ACD-015 — Epic ordering reads `depends_on` only, so `expects_from` contract edges are invisible to the build sequencer

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/goal_to_epic.py` (`_build_depends_on_index`,
  `_translate_ticket_depends_on`) — zero occurrences of `expects_from` in the file

**Symptom.** `goal_to_epic.py` builds its topological order purely from `depends_on`. The
AC schema also carries `expects_from: {ac_id, contract}`, which states that an AC consumes
a named contract from another AC — a build-order fact by any reading. The generator never
looks at it.

In the GE-120 tree three records declared a contract edge that existed **only** in
`expects_from`:

```text
GE-120b-1     expects_from GE-120c-1    depends_on: [GE-120b, ACS-1200a]
GE-120b-4     expects_from GE-120c-1    depends_on: [GE-120b, GE-120b-2]
GE-120b-1-i   expects_from GE-120a-2    depends_on: [GE-120b-1]
```

`GE-120c-1` is the out-of-process harness that `b-1` and `b-4` are *verified through*.
Without the edge the sequencer is free to schedule both before the harness exists. The
edges were added to `depends_on` by hand before generating, and the resulting order put
`c-1` at position 12 ahead of `b-1` (13) and `b-4` (15) — so the mechanism works, it is
simply fed from one field when the store records the dependency in two.

**The open question is which field is authoritative,** and the answer is not obvious.
`expects_from` may be intended purely as contract documentation with `depends_on` as the
scheduling field. If so the defect is in the ACs (an IT-PO that writes `expects_from`
should mirror it into `depends_on`) and the fix is a validator rule, not a generator
change. If instead `expects_from` is meant to be load-bearing, the generator must read it.
Deciding this is a prerequisite to fixing it — implementing either half without the
decision produces two sources of truth for build order.

**Detection cost today.** Nothing surfaces the discrepancy. It was found by diffing
`expects_from.ac_id` against `depends_on` across the tree by hand. Whichever direction is
chosen, a store rule should assert the invariant.

---

### KI-ACD-016 — Generated tickets carry AC checklist items truncated mid-clause

- **Severity:** low
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/ac_store/generate_ticket_from_ac.py` — the `- [ ] AC-N:` checklist
  rendering

**Symptom.** Below the full ` ```gherkin ` block, each generated ticket repeats the
criteria as a checklist built by splitting the Gherkin on `And` and taking the first
physical line of each clause. Because the criteria are wrapped block scalars, every item
ends mid-sentence:

```markdown
- [ ] AC-1: it creates a real second working copy of the repository, stages real files in it, and
- [ ] AC-3: the source tree is not on the import path of the process under test, so a check that can
```

**Impact is bounded but real.** No information is lost — the complete criteria sit in the
Gherkin block directly above, and that is what `ac-validator` reads. The risk is an agent
or reviewer working from the checklist, which reads as a list of half-requirements. AC-3
above inverts especially badly: truncated, it stops immediately before the condition that
gives it meaning.

**Fix direction.** Join the wrapped continuation lines before splitting, or drop the
checklist entirely and let the Gherkin block stand alone. The checklist duplicates content
it cannot represent faithfully, so removing it is the cheaper correct answer.

---

### KI-ACD-017 — Epic generation re-scans the whole AC store per ticket: ~30 minutes for 37 tickets

- **Severity:** low
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/goal_to_epic.py` → per-ticket `generate_ticket_from_ac.py`, plus
  `_translate_ticket_depends_on` and the Master_Plan dependency map

**Symptom.** `goal_to_epic.py --ac GE-120` took **~30 minutes of wall clock at 30-55% CPU**
to produce 37 tickets — roughly 50 seconds per ticket, against a `--dry-run` that resolves
the same 37-leaf set in about a second. Time is spent re-loading and re-walking the AC
store (3,000+ records) once per ticket, then again during dependency translation and
Master_Plan assembly.

**Why it is worth recording despite being only slow.** The run produces no incremental
output — `tail` buffers everything to the end — so for half an hour there is no way to
distinguish progress from a hang. During this run the loose tickets sat in
`tickets/00_inbox/` for ~20 minutes before being moved into the epic folder, and that
intermediate state was misread as a duplicate-ticket defect. A long silent run invites
wrong conclusions about its own correctness, and invites a user to kill it partway, which
would leave exactly the half-assembled state that was feared.

**Fix direction.** Load the store once and pass it down rather than re-reading per ticket,
and emit a per-ticket progress line so the run is legible while it is happening.

---

### KI-ACD-018 — Every generated `depends_on` reference is the pre-move filename, so all 27 inter-ticket edges dangle

- **Severity:** high
- **Status:** open (data corrected by hand 2026-08-25; generator unchanged)
- **Occurrences:** 2
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/goal_to_epic.py` (`_translate_ticket_depends_on`, the epic-folder move,
  `_render_master_plan`) against `templates/hooks/ticket_frontmatter_guard.py`

**Symptom.** `goal_to_epic.py` writes tickets loose into `tickets/00_inbox/`, then moves
them into the epic folder under an ordinal prefix — `TICKET-20260825-GE-120b-2.md` becomes
`09_TICKET-20260825-GE-120b-2.md`. `depends_on` is translated **before** the move and never
re-pointed after it, so every reference names a file that no longer exists:

```text
❌ FRONTMATTER VIOLATION: '.../15_TICKET-20260825-GE-120b-4.md'
   depends_on 'TICKET-20260825-GE-120c-1.md' not found. Looked in:
     .../EPIC-TrustThatAGreenCheckActuallyChecked/TICKET-20260825-GE-120c-1.md
     .../EPIC-TrustThatAGreenCheckActuallyChecked/done/TICKET-20260825-GE-120c-1.md
```

**27 references across 20 of the 37 tickets — every inter-ticket edge in the epic.** The
Master_Plan's "Depends On" column carries the same stale names.

**The topological order is not affected, which is what makes this easy to miss.** The
ordinal prefixes encode the correct sequence: `c-1` really is at 12, ahead of `b-1` at 13
and `b-4` at 15. So the epic *looks* correctly wired in the Master_Plan table and reads
correctly to a human. What is broken is the machine-readable edge — the field
`ticket-prioritizer` and the supervisors use to compute a ready set. Left uncorrected, a
dependency-aware drive would treat all 37 tickets as unblocked.

**Contrast with KI-ACD-014, because together they localise the bug.** In the same run the
generator **did** correctly re-point `implemented_by` in the AC store to the post-move
`NN_`-prefixed path. So `goal_to_epic.py` knows the final filenames — it simply applies
that knowledge to the AC-store back-reference and not to the ticket-to-ticket references or
the Master_Plan table. This is one missing re-point pass over two surfaces, not a
path-tracking failure.

**It is caught, at least.** `ticket_frontmatter_guard` rejects the whole set at commit
time, which is why this is recorded as loud rather than silent. But it means
`goal_to_epic.py`'s output is uncommittable out of the box — the second such defect after
KI-ACD-012, whose Master_Plan frontmatter gap was confirmed again in this same run.

**Fix direction.** Move the tickets first, then translate `depends_on` and render the
Master_Plan against the final filenames — or re-point both surfaces after the move, reusing
whatever already re-points `implemented_by`. The regression test should generate a
two-ticket epic with one edge between them and run the real `ticket_frontmatter_guard`
over the result, for the same reason KI-ACD-012 gives: asserting a filename format is a
second copy of the rule that can itself fall behind.

**Second occurrence, 2026-08-25.** Reproduced by `goal_to_epic.py --ac GE-122d`: seven
dangling references across four of the nine tickets, plus the Master_Plan table. Repaired
by hand.

This occurrence sharpens the "easy to miss" claim above into something stronger. The
`GE-122d` epic exists specifically to make a scaffold ticket precede a registration ticket
— registering the commit-time check before the namespace roots exist would block every
commit in a fresh install. That ordering is carried **only** by `depends_on`. So the
generator's stale references do not merely degrade the build order here; they erase the
one constraint the epic was assembled to enforce, while the Master_Plan table still reads
correctly to a human reviewer. `ticket_frontmatter_guard` caught it, as before — but note
that it catches it only because it resolves each reference against disk. A check that
asserted `depends_on` was *present and non-empty* would have passed all four tickets.

**Pattern:** a producer that renames its artifacts after writing the references to them.

---

### KI-ACD-019 — `goal_to_epic.py` cites two governing acceptance criteria that do not exist, and five `done` ACs in this register's scope are falsified

- **Severity:** high
- **Status:** open — handover ticket raised for the falsified ACs; the missing records are being authored separately
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/goal_to_epic.py` (`:16`, `:37`, `:311`, `:319`, `:439`, `:2601`) citing `ACD-1200a-6`; three further sites citing `ACD-1200a-7`

**Ticket:** [`tickets/00_inbox/TICKET-20260825-BuildOrchestrationPhantomTriage.md`](../../tickets/00_inbox/TICKET-20260825-BuildOrchestrationPhantomTriage.md)

**Symptom — the part that is not in any other entry.** `scripts/goal_to_epic.py` names
`ACD-1200a-6` **six times** and `ACD-1200a-7` three times as the acceptance criteria governing
its behaviour. **Neither id exists anywhere in the AC store.** Verified: a store-wide search
for `^id: ACD-1200a-6` and `^id: ACD-1200a-7` returns nothing, while
`grep -c "ACD-1200a-6" scripts/goal_to_epic.py` returns 6.

Their siblings `ACD-1200a-4` and `-5` were re-parented to `ACD-1200g-1`/`g-2` on 2026-06-17
with `amended_by` notes recording the move. `-6` and `-7` left no record and no supersession
note.

So the two behaviours those citations govern — `KI-ACD-011` (phrase-unaware epic-name
truncation) and `KI-ACD-012` (Master_Plan frontmatter missing fields the commit gate requires)
— are not merely uncovered. **The code asserts it is governed by criteria that were deleted.**
That is a `GE-122`-class citation-resolving-to-zero-records instance sitting inside the file
this register describes, and it is worse than an ordinary gap: a reader who checks whether the
behaviour is specified finds a citation and stops looking.

**Five `done` ACs falsified.** The same triage found `BO-2200c-5`, `BO-202`, `BO-2300a-1`,
`BO-2300a-2` and `BO-1500f-1` marked `done` with criteria the code does not satisfy; the
per-record evidence is in the ticket. `ACD-1200a-3-iii` is a sixth, and is this component's
own: it claims "the derived folder name contains only ASCII alphanumeric characters", and
`_to_pascal_case('Ship parts tree — the fast path, quickly')` returns
`'ShipPartsTreeTheFastPath,Quickly'` — reproduced inside the criterion's own `Given`. Its three
covering tests all assert `result.isascii()`, which is `True` for a comma.

**Two of these are one bug.** `KI-ACD-005` and `KI-ACD-006` both follow from a single decision
in `plan-feature.js:2057-2097` — an agent's reply is accepted as a user's decision — and both
ACs went `done` against it in the same ticket. Fixing either half alone leaves the other
false. Likewise `KI-ACD-004` and `KI-ACD-009` are both `{{config.output_root}}` resolving
relative to the session cwd, and both halt `/plan-feature` before triage.

**A correction to `KI-ACD-012`, which names the wrong gate.**
`templates/hooks/ticket_frontmatter_guard.py` is a Claude Code `PreToolUse` hook on
`Edit|Write`, not a pre-commit hook. A `Master_Plan.md` written by `goal_to_epic.py` through
Python file I/O never passes through the Edit/Write tool, so that guard never fires on
generation. The gate that actually runs at commit time is `check_doc_frontmatter.py`, whose
`ticket_frontmatter.required_fields` is `["title", "status", "components", "created",
"depends_on"]`. The generator emits `status`, `components` and `created` — so **two** fields
are missing at the real gate, not six. The defect and the fix direction are right; the
mechanism and the number are not.

**A correction to `KI-ACD-002`'s counters.** `Occurrences: 1` / `First seen: 2026-08-18`
undercounts by a week and at least four tickets. The identical verbatim blocker is recorded on
three tickets under `tickets/99_done/EPIC-BuildAcResolvesALeafAcsConnectedBuildSet/`, all
`created: '2026-08-11'`, and one of them shows the hand-repaired pipe form — so the manual
workaround had been applied at least three times before the 2026-08-18 sighting.

**Scope note.** The triage covered `KI-ACD-001` through `KI-ACD-012`. Entries `-013` onward
were filed after it ran and are **not** triaged.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M1 for the tests that let these read
`done`; the missing-citation half is its own shape — a reference that resolves to nothing reads
as coverage to everyone who checks for one.

---

### KI-ACD-020 — Non-interactive epic generation drops every unapproved leaf AC without naming one of them

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/goal_to_epic.py:1449-1455` — `_gate_select_approved_ids()`, the
  `if yes or approved_only:` branch; and its caller `run()` at `:2252-2264`

**Symptom.** `goal_to_epic.py --ac <goal> --yes` (or `--approved-only`) generates an epic
containing only the leaves that were already `readiness: approved`. Every leaf below
`approved` is silently excluded: it is not listed, not counted, not warned about. The run
exits 0 and reports success, and the epic looks complete because nothing in its output
refers to what is missing.

**Evidence — probed directly against the real function.**

```text
--yes            returns=['GE-999a-1', 'GE-999a-2']
--yes            stdout=''
--approved-only  returns=['GE-999a-1', 'GE-999a-2']
--approved-only  stdout=''
```

Input was two approved and two unapproved ids (`reviewed`, `draft`). Both flags returned
the identical two-element list and **wrote nothing to stdout at all**. The caller then does
`leaf_ids = approved_ids` with no further notice.

**Two distinct defects, and the second is the reason the first is invisible.**

1. **The two flags are behaviourally identical.** Both enter the same branch and return
   `list(readiness["approved"])`. Their help text presents them as different operations —
   `--yes` as *"equivalent to choosing 'yes' at the interactive prompt"*, `--approved-only`
   as *"filter to only already-approved leaf ACs and skip unapproved ones"*. A caller
   reading that help reasonably expects `--yes` to be the permissive option. There is no
   non-interactive way to include an unapproved leaf; `--yes` is a misleading name for
   "skip everything not approved".

2. **The exclusion is never reported.** `_print_readiness_report()` — which exists and
   names every unapproved id and its readiness value — is called only from
   `readiness_gate_prompt()`, the interactive path. The flag branch returns before it.
   Note the asymmetry this creates in `run()`: the **all-approved** path calls
   `print_fast_path_message()` and announces itself, while the **partial** path says
   nothing. The complete run is the one that reports; the incomplete run is silent.

**Why this matters more than a missing log line.** Epic generation is the step that decides
what gets built. A goal AC is decomposed into leaves precisely because the leaves are the
work; dropping a subset produces a well-formed epic that omits part of its own goal, with a
Master_Plan that reads as authoritative. Encountered on `--ac GE-122d`, where three of the
nine leaves were `readiness: reviewed` — and those three were the registration work the
epic exists to deliver. Either flag would have produced a six-ticket epic whose purpose had
been removed from it, exit 0, no warning. Caught only because the readiness values were
checked by hand first.

This is a false-green of the `M1` family (`docs/reference/false-green-mechanisms.md`): a
successful-looking result whose scope silently shrank.

**Fix direction.** Two things, and the second matters even if the first is contested:

- Print the readiness report in the non-interactive branch too, and follow it with an
  explicit line naming the count and ids being excluded. Reuse `_print_readiness_report()`
  — it already formats exactly this.
- Give the flags distinct meanings, or collapse them. If `--yes` is meant to be
  "proceed with what is approved", it should say so; `--approved-only` is then a redundant
  alias and should be documented as one. If instead `--yes` was intended to mean "treat
  reviewed leaves as good enough", that is a real behaviour to build, and its absence is
  why the current naming misleads.

A regression test should assert on **stdout**, not just on the returned list — the returned
list is correct under the current design, and the defect lives entirely in what is not
said.

**Pattern:** a narrowing applied silently on the path that has no human watching, while the
path that does have one reports fully.

---

### KI-ACD-021 — Every `depends_on` edge pointing at an AC's own parent is dropped from the generated ticket, while the Master_Plan still draws it

- **Severity:** high
- **Status:** open (data corrected by hand 2026-08-25; generator unchanged)
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/goal_to_epic.py` — the ticket-frontmatter `depends_on` write, against
  the same file's `_render_master_plan()` dependency block

**Symptom.** In the epic generated from `GE-122d`, three tickets were written with
`depends_on: []` in their frontmatter while the Master_Plan's own Dependencies block, in the
same run, correctly recorded an edge for each:

| Ticket | Master_Plan says | Frontmatter says |
|---|---|---|
| `GE-122d-3-i` | `-> GE-122d-3` | `[]` |
| `GE-122d-3-ii` | `-> GE-122d-3` | `[]` |
| `GE-122d-6-i` | `-> GE-122d-6` | `[]` |

Each edge is present in the source AC YAML — `GE-122d-3-i.yaml:39-40` reads
`depends_on: [GE-122d-3]`. So the generator read the edge, rendered it in one output, and
omitted it from the other.

**The rule, which is what makes this predictable rather than random.** Every dropped edge
points at the AC's **own parent by id shape**; every retained edge points at a sibling or
cousin. `GE-122d-2 -> GE-122d-1`, `GE-122d-4 -> GE-122d-1, GE-122d-2`,
`GE-122d-5 -> GE-122d-2, GE-122d-3` and `GE-122d-6 -> GE-122d-1, GE-122d-3-ii` were all
written correctly. `GE-122d-6 -> GE-122d-3-ii` is the one that settles it: a Roman-suffixed
AC is fine as a dependency *target*. It is being the **source** of an edge to its own parent
that loses it. The generator appears to treat a parent reference as the `covered_by` tree
relation and filter it out, which is defensible for a tree link and wrong for `depends_on` —
the author wrote it in the build-order field, and for the Roman-suffix
technical-constraint pattern the base AC genuinely is a build predecessor.

**Consequence.** `build-feature` reads frontmatter `depends_on`, not the Master_Plan prose.
Three tickets were therefore machine-readable as unblocked and could be dispatched before the
base AC they constrain. In this epic that is not cosmetic: `GE-122d-3-ii` scaffolds the
namespace roots that `GE-122d-6` registers a commit-time check against, and registering
before scaffolding makes every commit in every fresh install fail closed on an unresolvable
root.

**Distinct from `KI-ACD-018`, and the pair is worth reading together.** That entry is about
edges that are *written but stale* — the pre-move filename. This one is about edges that are
*not written at all*. They have opposite detection properties, which is the useful part:
a stale edge is caught by `check_doc_frontmatter`, because a name that resolves to nothing is
an error. A **missing** edge resolves vacuously — `depends_on: []` is valid frontmatter — so
no gate fires, and the Master_Plan table reads correctly to a human reviewer either way.
Between the two, `goal_to_epic.py` produced an epic in which four of the eight declared edges
were wrong and only the loud half was caught.

**Fix direction.** Write `depends_on` from the same resolved edge set the Master_Plan
dependency block is rendered from — the divergence exists because two renderings compute the
edge list separately, and one of them applies a parent filter. If parent references really
should be excluded from build order, exclude them from *both* outputs and say so; a
generator that draws an edge it does not wire is worse than one that does neither.

The regression test must assert **frontmatter against the Master_Plan** for the same run,
not either against an expected literal. A test that checks only that "some `depends_on` was
written" passes here, since five of the eight edges were correct.

**Pattern:** one fact rendered twice by two code paths, agreeing in the surface a human reads
and disagreeing in the surface a machine reads.
