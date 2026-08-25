---
title: "Known issues — commit-guardian"
description: "Open, observed defects in the commit-guardian component: the pre-commit hook family that gates commits, and in particular the AC-store hooks whose scope is the git index rather than the store. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-25
components:
  - commit_guardian
related_docs:
  - docs/architecture/components/commit-guardian.md
  - docs/architecture/components/phantom-done-prevention.md
---

# Known issues — commit-guardian

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-CG-NNN` section using the next free number.
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

### KI-CG-001 — AC hooks are scoped to the git index, so parent-level drift is unreachable

- **Severity:** high
- **Status:** open
- **Occurrences:** 2
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-19
- **Where:** `templates/scripts/commit_guardian/check_ac_parent_covered_by.py:134-150`, and the AC hook family generally

**Second occurrence, 2026-08-19.** Staging `GE-113c-1-iii` and `GE-113c-1-v` for an
unrelated one-line `components` edit made `check-ac-schema` fail both with *"approved code
AC must declare a test contract — add a non-empty `test_spec`"*. Neither record has ever
had one. They are `readiness: approved`, `change_target: code`, and have been sitting on
`main` in that state — invisible because no commit had happened to stage them since the
rule was introduced. The hook was not silent because they were fine; it was silent because
it had never been shown them. A store-wide sweep would find how many more there are; the
index-scoped hook structurally cannot.

**Symptom.** These hooks derive their file list from `git diff --cached --name-only` (or
`HOOK_TEST_FILES` under test) — never from the store. Any fact that is true of the store
but not of the staged set is structurally invisible. Because normal work edits children
and leaves the parent untouched, the parent is almost never staged, so the hooks that
exist to check parents are almost never handed one. Their silence reads as a pass; it
means they were not given the file.

**Evidence.** `ACD-400a` on `main` at `439b9076f` carries **both** failure modes at once:
`covered_by: [ACD-400a-1, ACD-400a-2]` while `ACD-400a-3` and `-4` have existed on disk
since 2026-08-12, and `work_status: done` while `ACD-400a-1` and `-2` are both still
`todo`. Every commit in that five-day window passed every AC hook. It surfaced only when
the parent was incidentally staged on 2026-08-18.

It is not an isolated record. A read-only sweep of all 3,146 store records at the same
commit found **20** composites marked `done` with at least one unfinished child —
`ACD-300a`, `ACD-400b` and `ACD-600a` each with 3-4 `todo` children. Sixteen are L2; in
thirteen of those, every unfinished child is a Roman-suffixed technical-constraint
sibling, so the dominant shape is flipping an L2 to `done` once its behaviour works while
its `-i` constraints stay `todo`.

Two aggravating details. These hooks fail open on unexpected exceptions, so an error is
also silent. And they ignore `argv`: passing a path on the command line does not make
them check that path, which makes them easy to "verify" without having verified anything.

**Fix direction.** For any staged AC, resolve and check its parent from the store whether
or not the parent is staged — the store is on disk and cheap to read. A store-wide sweep
in CI would also catch existing drift, which per-commit hooks by construction never will.
Until then, the workaround is documented in `CLAUDE.md` → "AC-store commits — stage the
parent alongside the child".

**Pattern:** `docs/reference/false-green-mechanisms.md` → M3.

---

### KI-CG-002 — The diagram-type enum silently narrows from 11 values to 8 when its declaring file is unreachable

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/scripts/commit_guardian/diagram_type_validators.py:35-55` (`_find_diagram_types_json`) and `_load_diagram_types()`

**Symptom.** `_find_diagram_types_json()` walks ancestors of its own `__file__` looking for
`leafcutter/config/diagram_types.json` or `config/diagram_types.json`. When neither
resolves it returns `None`, and `_load_diagram_types()` falls back **without any warning**
to the `DOC_FM_DIAGRAM_TYPE_VALUES` constant in `config.py:190`. The hook then validates
against a different, narrower enum than the one it is configured with, and says nothing.

**Evidence.** The declaring file `config/diagram_types.json` defines **11** types:
`agent_flow`, `component`, `container`, `context`, `data_flow`, `dataflow`, `erd`, `none`,
`sequence`, `state`, `user_flow`. The fallback constant defines **8**: `context`,
`container`, `component`, `sequence`, `erd`, `state`, `dataflow`, `none`. So on the
fallback path a doc declaring `diagram_type: agent_flow`, `data_flow` or `user_flow` — all
canonical — is rejected as an unknown value.

The resolution gap is not hypothetical: it is the same one that made
`check-doc-frontmatter` crash on 2026-08-18 (see
`docs/known-issues/build-pipeline.md` → KI-BP-003). Both resolvers hardcode the package
directory as `leafcutter/`, while this package installs as `leafcutter-ai/`, and the
self-hosted workspace target has no `config/` tree at all. `doc_types` fails loudly there;
`diagram_types` fails quietly.

**This is the exact failure GE-118c fixed in the sibling module on the same day.**
(That requirement was tracked as `GE-120` until 2026-08-18, when the id was found to
collide with an unrelated goal-level tree and the record was renumbered to `GE-118c`
under `GE-118`.) That work
removed the silent `except (json.JSONDecodeError, OSError): pass` and the `.exists()`
fallthrough from `doc_type_validators.py`, on the stated grounds that "a guard that quietly
answers a different question than the one it was configured with is enforcing a rule nobody
wrote." `diagram_type_validators.py` is the file GE-118c copied its ancestor-walk pattern
*from*, and it still has the behaviour that was removed.

**Fix direction.** Mirror GE-118c the rest of the way: raise a `FileNotFoundError` naming
the resolved path instead of substituting the constant, and fix the path resolution for
both modules together. If a fallback must be retained for consumer installs, log it at
WARNING so it is at least observable — a narrowed enum reached in silence is
indistinguishable from a passing check.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M5 (a check that runs against
less than it claims to, and reports success).

---

### KI-CG-006 — The pre-commit proof-of-done gate and the CI backstop disagree on what a valid tag is, in both directions

- **Severity:** high
- **Status:** open
- **Occurrences:** 3
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-19
- **Where:** `templates/scripts/commit_guardian/check_done_proof.py`
  (`check_staged_done_proofs`, `_collect_all_covered_ids`)

**Symptom.** `check_staged_done_proofs` never reads `test_required`, and has no composite
path. Its two siblings have both: `check_all_done_acs` and `check_changed_done_acs` each
skip an AC with `test_required: false`, and both derive a composite's verdict from its
children via `verify_done_eligible`. So the fast local gate blocks commits that the CI
gate would pass.

**The disagreement also runs the other way — it accepts tags that link to nothing.**
The two gates do not share a scanner. `_collect_all_covered_ids` is a flat
`COVERS_TAG_RE.finditer` over each file's whole text and keeps every id it sees, wherever
it sits. The oracle's Python scanner (`done_proof._scan_single_test_file`) attributes a tag
to the most recent enclosing `def test_*` and **drops** any tag with no enclosing test
function. A tag in a module docstring, an import block, a helper, or a comment header is
therefore proof to the pre-commit gate and invisible to the authoritative one.

So the two halves of one file define "a valid covers tag" differently: a text-presence
scan with no notion of a test function, versus a scanner that requires one. Neither reads
the other. That is the actual defect — the strictness gap and the laxity gap are two
symptoms of it, and fixing only the direction that blocks a commit leaves the direction
that waves one through.

**Evidence (false accept).** In a consumer install (DIAGraph),
`tests/test_psd_problems_case_count.py` carries `# covers: MSN-101` **inside its module
docstring** — before any `def`. The pre-commit gate finds the id and passes `MSN-101` as
proven; `verify_done_eligible('MSN-101')` reports `no linked test found`. The record can
be committed as `done` locally with nothing behind it. The lax half is the more dangerous
one: it is phantom-done, and it is the failure mode this hook exists to prevent.

Worth noting the oracle's own scanner is not the safe reference either — it cannot see an
`async def` test at all (KI-ACS-008 D-1), so "the strict one is right" does not hold
either. Any fix should settle on one shared scanner, not pick a winner.

The module docstring documents the exemption for the two CI functions and is silent about
the pre-commit one, so the omission may be deliberate. It is still incoherent in effect:
the same docstring calls the pre-commit check the fast approximation and CI "the
authoritative backstop". An approximation stricter than its backstop is not an
approximation.

**Consequence.** An AC that is legitimately `test_required: false` and `work_status: done`
can never appear in a staged diff again. Editing so much as a stale path inside one of
those files is uncommittable without `SKIP=`. Same for any `done` composite.

**Evidence.** On 2026-08-18 a commit correcting AC statuses was blocked on seven records:
`BO-1500a-3`, `BO-1500b-4`, `BO-1500c-4`, `BO-1500c-5` (all `test_required: false`
documentation ACs whose diagrams and how-to exist on disk) and `BO-1500b-1`, `BO-1600d`,
`BO-510-3` (composites). The authoritative gate — `check_done_proof --mode ci-changed
--base origin/main`, which backs the required "Proof-of-done coverage check (BO-2500b)"
status check — exited 0 on the same tree.

Earlier in the same session the same hook was run standalone from the workspace parent and
exited 0, which was read as a pass. It was vacuous: `git diff --cached` saw no index there,
so it checked nothing. See KI-CG-001 for the same index-scoping confusion.

**Fix direction.** Mirror the siblings: skip `test_required: false`, and fall through to
the composite path rather than demanding a direct tag. It is a small change but it widens
a phantom-done gate, so it wants an AC and a test rather than an in-passing edit.

For the laxity half, replace `_collect_all_covered_ids`' bare regex sweep with the oracle's
own scanner — export `done_proof._scan_test_root_for_covers_tags` and derive the id set
from `{t["ac_id"] for t in tags}`, so a tag outside a test function stops counting as
presence in both gates by construction. That import already exists in this module (the
`verify_done_eligible` / `COVERS_TAG_RE` block), so it costs no new coupling. Fix
KI-ACS-008 D-1 first or the shared scanner will start rejecting every async-tested AC at
pre-commit time. The right end state is one scanner with one definition and a test
asserting the two gates agree on a fixture set covering all four shapes: sync, async,
file-level, composite.

---

### KI-CG-004 — moved to `security-scanner`

Refiled 2026-08-19 as **KI-SEC-001** in
[`docs/known-issues/security-scanner.md`](security-scanner.md): *prose exemption
disables entropy detection for whole files, including executable Python under
`templates/skills/`, and its path match is not root-anchored.*

Moved when the `security-scanner` register was created. The defect is about what the
secrets scanner can be talked out of reporting, which is that surface's question, not
the guardrail framework's. The id is retired here rather than reused, so the numbering
gap is intentional.

**Six `GE-123` records still cite `KI-CG-004` at this file path, deliberately** — they
fence it as out of scope so that repairing it and `GE-123d-4-i` are not closed as
duplicates of one another. Those citations were left untouched by the move; this stub is
what resolves them. Do not repoint them.

---

### KI-CG-005 — `check-product-truth-validate` / `check-product-truth-generate` hard-fail on an absent, explicitly optional product-truth store, gating every AC YAML commit

- **Severity:** blocker
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/scripts/commit_guardian/commit_guardian.json:986` (`check-product-truth-validate`) and `:999` (`check-product-truth-generate`)

**Symptom.** Both hooks declare `files: "(^docs/product-truth/|^docs/acceptance-criteria/.*\\.yaml$)"`,
so they fire on **any staged AC YAML**, not only on product-truth artifacts, and both invoke
scripts living under `docs/product-truth/scripts/` (`validate_product_truth.py`,
`generate_product_truth.py`). `check-product-truth-validate`'s own `_comment` states the
posture plainly: *"jsonschema is a HARD dependency (validator exits 2 if absent — never a
silent no-op)."* But the product-truth store is **opt-in** — the `/plan-feature` skill
documents the intended behaviour on its absence: *"When the product-truth store is absent
the PT phase self-skips non-silently and AC authoring still proceeds"* (AC UXP-595a). The
defect is the disagreement between these two, not either half on its own: the workflow is
explicitly designed to degrade gracefully when the store is absent, and the hooks treat that
same absence as a hard failure. A consumer who never opted in cannot commit *any* AC YAML —
the optional feature's absence gates the mandatory one.

**Evidence.** Reported by a consumer project (DIAGraph) on 2026-08-18. Their
`docs/product-truth/` directory exists only because `build.py` deploys schemas and scripts
into it; zero of their docs reference the feature and they never opted in. They had been
running `/plan-feature` without the PT phase throughout, exactly as designed — and were then
blocked from committing by these two hooks the first time an AC YAML was staged.

**Relationship to KI-CG-002.** Same root shape as KI-CG-002 above: a guard behaving badly
when a file or store it depends on is not present. KI-CG-002 narrows its enum silently on
that absence; this pair fails loudly and totally on it — but in both cases the guard never
asked "is my dependency supposed to be here?" before acting on its absence.

**Fix direction.** The fix is not "add a guard to the hook" in isolation — the workflow
already encodes the decision that product-truth is optional. Make the hooks agree with it:
skip when the store is absent, the same way the workflow does. Pick one answer to "is this
optional?" and have both halves honour it.

---

### KI-CG-007 — The sanctioned way to add a component produces an entry the required gate rejects, and the gate's stated rule is weaker than the one it enforces

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** `scripts/add_component.py` (writer) · `templates/scripts/commit_guardian/check_components_integrity.py:475-540` (gate) · `docs/components.json` (the registry)

**Symptom.** Registering a component the documented way blocks your commit, twice, for
reasons the tooling does not tell you in advance. Four separate defects compound:

**1. The writer and the gate disagree.** `scripts/add_component.py` — wrapped by the
`add-component` skill precisely so "agents can add a new entry … without knowing the
script path or argument format" — has no flags for `agent_affinity` or
`exposed_interfaces` and writes neither. `check-components-integrity` requires **both** on
every new component and blocks the commit. The tool the project provides for this job
cannot produce output the project's own required gate accepts.

**2. The stated rule is weaker than the enforced rule.** The gate's failure output prints:

```
5. An 'agent_affinity' field that is a JSON array (use [] if none).
6. An 'exposed_interfaces' field that is a JSON array (use [] if none).
```

Following that exactly — a JSON array of strings — fails on the next attempt with
`exposed_interfaces[0] must be a JSON object`. The code additionally requires each element
to be an object carrying `name`, `type`, `path` and `shape`, with `type` drawn from a fixed
seven-value set (`VALID_INTERFACE_TYPES`, line 110). None of that appears in the message.
An author who reads the error and complies is still blocked, and only reading the hook
source resolves it.

**3. Grandfathering means there is no precedent to copy.** The gate checks only components
whose entry appears in the diff — *"Existing components (no diff) are not checked — legacy
state is accepted."* So **zero** of the 42 pre-existing entries carry `agent_affinity` or
`exposed_interfaces`. The first author to add a component cannot look at a neighbour to
learn the shape, and whatever they invent silently becomes the precedent for a validated
field. `security_scanner` (added 2026-08-19) is that first entry.

**4. The registry has no owning component.** No entry in `docs/components.json` claims
`docs/components.json` or `scripts/add_component.py` in its `primary_code`, and there is no
`component_registry` component. This issue is filed here because
`check_components_integrity.py` is a commit-guardian hook, but the writer half genuinely
has no home — which is why the two halves were free to drift apart in the first place.

**Evidence.** Adding `security_scanner` on 2026-08-19 took three commit attempts:

```
attempt 1  [x] 'agent_affinity' field is required (use [] if no agent affinity).
           [x] 'exposed_interfaces' field is required (use [] if ... no external interfaces).
attempt 2  [x] exposed_interfaces[0] must be a JSON object.
           [x] exposed_interfaces[1] must be a JSON object.
attempt 3  passed
```

Both blocks came from `add_component.py`'s own output, unmodified.

**Fix direction.** In descending order of payoff:

- **Teach the writer the full contract.** Give `add_component.py` `--agent-affinity` and
  `--exposed-interface` flags, and have it emit the required element shape. A generator
  that cannot satisfy the validator is worse than no generator, because it is trusted.
- **Make the printed rule the enforced rule.** The message must state the element schema
  and the valid `type` values, or point at them. A gate whose remedy does not resolve the
  failure trains people to bypass it.
- **Decide whether grandfathering is permanent.** Either backfill the 42 legacy entries so
  new authors have a pattern to copy, or say explicitly in the registry that these fields
  are new-entries-only. The current state reads as "everyone else omitted this", which is
  the opposite of the intended signal.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M8, in its inverse form — not a
check that passes when it should fail, but a check whose documented contract and enforced
contract differ, so compliance with the message is not compliance with the gate.

---

### KI-CG-009 — `check-components-integrity` resolves the repo root to the main checkout instead of the worktree, so a branch-only `detail_ref` doc is reported missing

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/scripts/commit_guardian/check_components_integrity.py` — `_repo_root()` (`:134-175`), the module-level `REPO_ROOT` binding (`:127`), and the `detail_ref` existence check `doc_path = root / detail_ref` (`:657`)
- **Reported by:** customer bug report, 2026-08-25

**Symptom.** Committing in a git worktree, the hook reports a component's `detail_ref`
architecture doc as missing even though the doc exists on the branch being committed. The
file is there and is reachable; the hook is reading a *different*, perfectly valid checkout
and truthfully reporting that the doc is not in that tree. The failure message does not name
the root it used, so it reads as "you forgot to write the doc" while the doc sits in front of
you.

**Root cause.** `_repo_root()` — added by `ACS-300g-6` — resolves the root by running
`git rev-parse --show-toplevel`, which is CWD-based and therefore correct inside a worktree.
Its fallback is not. The fallback is `Path(__file__).resolve().parents[2]`, and in a worktree
`.leafcutter` is commonly a **symlink** to the workspace parent's `.leafcutter` — the layout
this package's own `CLAUDE.md` → "Worktree pre-commit config" explicitly recommends.
`Path.resolve()` follows that symlink before `parents[2]` is taken, so the fallback lands on
the **main workspace checkout** rather than on the worktree being committed to. The one
resolution path meant to be the safety net is the path that walks out of the repository you
are committing to.

There is a second, independent half. The module-level `REPO_ROOT` (`:127`) is bound to that
same `__file__`-relative expression **at import time** and is only corrected inside `main()`.
Any code path reading `REPO_ROOT` before or outside `main()` therefore gets the wrong root no
matter what `_repo_root()` would have returned — `validate_component_entry`'s own
`doc_path = REPO_ROOT / detail_ref` (`:433`) is exactly such a consumer. Repairing only the
fallback expression leaves this half live.

**Why it matters.** The file exists, on the branch being committed; the hook simply computes
the wrong root. The symlinked `.leafcutter` layout is not an exotic setup someone talked
themselves into — it is the documented, supported one, so a hook that breaks under it is the
thing that is wrong, not the layout. The practical workaround is `SKIP=`, which is precisely
the reflex this repo is trying to eliminate: a guard that must be bypassed to commit correct
work teaches people to bypass guards. There is a false-green corollary too — a `detail_ref`
that exists in the main checkout but *not* on the branch being committed passes this gate for
the same reason, landing a registry entry that points at a doc the branch does not contain.

**Evidence.** Reported by a customer on 2026-08-25, committing from a worktree whose
`.leafcutter` was a symlink to the workspace parent's. The code facts are directly readable:
`REPO_ROOT: Path = Path(__file__).resolve().parents[2]` at `:127`, under a comment stating
*"main() updates this via _repo_root()"*, and `_repo_root()`'s two fallback branches at
`:161-174`, both returning `_fallback = Path(__file__).resolve().parents[2]`. The helper's
docstring claim that it is *"correct regardless of where the hook file lives (e.g. via a
.leafcutter symlink into another repo)"* holds only for the `git rev-parse` branch, not for
the fallback sitting immediately beneath it.

**AC coverage — already claimed, and already once phantom-done.** `ACS-300g-6` ("Component
integrity hook resolves REPO_ROOT to the actual repository top-level") names this invocation
path in its criteria verbatim: *"invoked through the `.leafcutter` symlink install path (so
that `Path(__file__).resolve().parents[2]` resolves to `<repo>/.leafcutter` rather than the
real repository root)"*. It was marked `work_status: done` on 2026-07-08 (commit `4216ddcf`)
and stayed that way for six weeks; it was reopened to `todo` on 2026-08-18 because the shipped
fix swapped a `__file__`-anchored root bug for a CWD-anchored one, and because its test never
exercised a symlinked `.leafcutter` or a linked worktree at all. So this is **incomplete
coverage on an AC that was already marked done** — a phantom-done instance with a paper trail,
not virgin territory, and the current customer report is that same defect resurfacing from a
second direction. Anyone picking this up should read that record's `notes` before writing a
line of code. Store anomaly worth recording alongside it: `ACS-300g-6` carries
`covered_by: []` while its `implemented_by` names a test file — the coverage link that would
have exposed the gap was never made.

**Fix direction.** Never resolve the root through the `.leafcutter` symlink. Prefer the
`git rev-parse --show-toplevel` result and, when it fails, derive the root from the **CWD**
rather than from `__file__` — the question being asked is "which tree is being committed to",
and `__file__` cannot answer that once the hook is reached through a link. Bind `REPO_ROOT`
lazily, or thread the resolved root into every consumer the way `validate_new_component`
already does, so no caller can read the import-time fallback. Heed the trap recorded on
`ACS-300g-6`: the obvious regression test cannot fail, because a test run with the CWD already
at the worktree top-level returns the right root against broken and fixed code alike. A test
for this must exercise a symlinked `.leafcutter` **and** place the CWD somewhere other than
the worktree top-level, or it will be green against the defect — which is how this survived
the first time.

**Relationship to KI-BP-003.** Same symlinked-worktree setup, different defect, and the
distinction decides the fix. `KI-BP-003` is a **missing-artifact** failure: `config/doc_types.json`
was never deployed into the layout the hook runs in, so no amount of correct root resolution
would have found it and the repair belongs in the deploy manifest. This is a **wrong-tree**
failure: the file exists, on the branch being committed, and the hook reads a different
checkout — deploying more files fixes nothing here.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2, the same family — a hook that
cannot reach a file it depends on because it is wrong about where it is — though M2's
mechanism is the deploy manifest and this one's is root resolution through a symlink.

---

### KI-CG-010 — `check-roadmap-schema` never validates the roadmap, and the roadmap would fail it if it did

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/scripts/commit_guardian/check_roadmap_schema.py:27` — `SCHEMA_RELATIVE = "leafcutter/config/roadmap.schema.json"`

**Symptom.** The hook resolves its schema at `<git-root>/leafcutter/config/roadmap.schema.json`.
In this repository the git root **is** the package, so the real path is
`config/roadmap.schema.json` with no `leafcutter/` segment. The file it looks for does not
exist, so the hook takes its fail-open branch and reports an advisory skip. Every commit
touching `docs/roadmap.json` has passed a check that never ran.

The second half is worse than the first: **if the hook ever found its schema, the roadmap
would fail it.** Every phase in `docs/roadmap.json` carries a `components` key, and the
schema's phase item declares `additionalProperties: false` over exactly six permitted
properties — `description`, `exit_criteria`, `id`, `status`, `tickets_advancing_outcome`,
`title`. `components` is not among them. So fixing the path alone converts a silent no-op
into a blocked commit on an unrelated change.

**Evidence.** Verified 2026-08-25 while rewording a phase_1 exit criterion.
`ls <repo>/leafcutter/config/roadmap.schema.json` → no such file. The schema's own
`properties.phases.items` was read directly: six properties, `additionalProperties: false`.
The hook reported no failure on the commit that changed `docs/roadmap.json`.

This is the same shape as `KI-BP-003` and `KI-CG-002` — a guardrail that cannot reach its
own declaring file in the self-hosted layout — and the third instance found. Unlike
`KI-CG-002`, which narrows an enum, this one skips the check entirely.

**Fix direction.** Resolve the schema the way `KI-CG-009`'s repair does, from the running
artifact's own location rather than a hardcoded `leafcutter/` segment that assumes a
consumer layout. Land the `components`-vs-schema disagreement in the **same** change —
either add `components` to the phase schema or drop it from the roadmap — because repairing
the path first turns a dormant no-op into an immediate merge blocker. Note the regression
test must run with the CWD somewhere other than the layout under test, or it will be green
against both the broken and the fixed resolver.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M5 (a validator that reports
success having checked nothing) and M2 (a guardrail that cannot reach a file it depends on).

---

### KI-CG-011 — The roadmap mirror strips its own `description` frontmatter and backdates `created` to today

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/scripts/commit_guardian/regenerate_roadmap_mirror.py:155-163` — the frontmatter block

**Symptom.** The generator emits a fixed six-line frontmatter: `title`, `type`, `status`,
`created`, `last_updated`, `components`. Two defects follow.

It never emits `description`, so any `description` present in `docs/roadmap.md` is **deleted
on every regeneration**. The comment above the block says the frontmatter is "required by
check_doc_frontmatter.py", which is exactly the convention the omission violates.

And `created` is written from the regeneration timestamp
(`date_only = generated_at[:10]`, line 154), so a file created on one date silently claims
it was created today, every time the mirror is rebuilt. `created` is supposed to be
immutable; only `last_updated` should move.

**Evidence.** Verified 2026-08-25 in the commit that reworded a phase_1 exit criterion. A
one-line change to `docs/roadmap.json` produced a 16-line diff in `docs/roadmap.md`: the
criterion itself, the two generated timestamps, quoting and indentation churn, and the
removal of `description: Overview of Project Roadmap.`. `created` moved `2026-08-17` →
`2026-08-25` on a file that plainly was not created that day.

Not currently merge-blocking — `check-description-field` is not among the six required CI
checks — so this erodes quietly.

**Fix direction.** Emit `description` in the generated frontmatter, and preserve the
existing `created` value when the mirror already exists rather than stamping the
regeneration date. Both are small, and both are worth doing together with a test that
regenerates twice and asserts the only field that moves is `last_updated`.

**Related.** This is `KI-BP-002`'s shape in another file — a tracked generated artifact that
drifts every time it is rebuilt — and `BP-1500a` is the acceptance criterion written against
that class. The roadmap mirror is not currently in `BP-1500a`'s scope; worth checking
whether it should be when that AC is built.
