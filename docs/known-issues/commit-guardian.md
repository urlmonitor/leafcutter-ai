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

### KI-CG-002 — The diagram-type guard silently swaps its enum source when its declaring file is unreachable

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/scripts/commit_guardian/diagram_type_validators.py:35-55` (`_find_diagram_types_json`) and `_load_diagram_types()`

**Corrected 2026-08-25 — the original wording overstated the trigger.** This was recorded
as "the diagram-type enum silently narrows from 11 values to 8", severity `high`. That is
wrong. A single resolution failure narrows nothing. The count drops only on a **second,
independent** failure. What is real is the silent substitution, and it is `medium`. The
correction is made in place because the overstated version was merged and read.

**Symptom.** `_find_diagram_types_json()` walks ancestors of its own `__file__` looking for
`leafcutter/config/diagram_types.json` or `config/diagram_types.json`. When neither
resolves it returns `None`, and `_load_diagram_types()` falls back **without any warning**
to `DOC_FM_DIAGRAM_TYPE_VALUES`. The guard changes which file it draws its authority from
and says nothing — which is exactly the fact an operator needs in order to judge whether
to trust the verdict.

**Evidence — the fallback is not narrower.** `DOC_FM_DIAGRAM_TYPE_VALUES` is not a
hardcoded constant. `config.py:190` reads it from `commit_guardian.json` →
`doc_frontmatter.diagram_type_values`, and that key lists **all 11** values. The 8-value
list written inline at `config.py:190-192` is only the `_get()` default, reached when the
key is absent. Measured by importing the module and forcing `_find_diagram_types_json()` to
return `None`: the enum stays at 11 and is the **identical set** to
`config/diagram_types.json`'s — `agent_flow, component, container, context, data_flow,
dataflow, erd, none, sequence, state, user_flow`. Nothing that would otherwise pass is
rejected.

Narrowing needs a second, independent failure: `commit_guardian.json` present but *missing*
the `doc_frontmatter.diagram_type_values` key. Removing that one key from a copy of the hook
directory, with resolution also forced to fail, does drop the enum to 8 and does lose
`agent_flow`, `data_flow`, `user_flow`. Deleting `commit_guardian.json` outright narrows
nothing either — `config.py` raises `FileNotFoundError` at import, so the hook dies loudly.

**And the first failure does not currently occur here.** The ancestor walk resolves
`config/diagram_types.json` from both the source layout (`templates/scripts/commit_guardian/`)
and the deployed layout (`.leafcutter/scripts/commit_guardian/`), returning 11 values from
each. The 2026-07-14 rewrite that replaced the broken `parents[2]` path with the walk is what
fixed that. A resolution failure is still reachable in a consumer layout where neither
candidate exists — `KI-BP-003`'s second occurrence is that shape for the sibling `doc_types`
resolver — but even there the result is substitution, not narrowing.

**`GE-105` is genuinely satisfied, not phantom.** That AC (`work_status: done`,
`readiness: approved`) requires the canonical values to be accepted, and names the effective
enum source explicitly: *"commit_guardian.json -> doc_frontmatter.diagram_type_values, used
as the runtime fallback when diagram_types.json is not deployed"*. Its covering test
(`test_commit_guardian_imports.py::TestGE105CanonicalEnumValuesAccepted`) asserts acceptance
against the module, and the config carries the values. The original entry implied a live
rejection of canonical values that GE-105 had left unfixed; there is none.

**Fix direction.** Two things, neither of them the value count. First, make the substitution
observable: log at WARNING, naming the candidates searched, when the walk fails and the
config fallback is taken, so a fallback verdict is never indistinguishable from a normal one.
`GE-118c` removed exactly this silence from the sibling `doc_type_validators.py` on
2026-08-18, on the stated grounds that "a guard that quietly answers a different question
than the one it was configured with is enforcing a rule nobody wrote." (That requirement was
tracked as `GE-120` until 2026-08-18, when the id was found to collide with an unrelated
goal-level tree and the record was renumbered to `GE-118c` under `GE-118`.)
`diagram_type_validators.py` is the file GE-118c copied its ancestor-walk pattern *from*, and
it still carries the silence that was removed. Second, the two lists live in two files, agree
today, and nothing checks that they still will — derive the config key from
`diagram_types.json` at build time, or assert parity between them. A divergence would be
invisible for precisely the reason this entry exists.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2 (a guardrail that cannot reach a
file it depends on), in its benign-today form — the substitution is unobservable, so on the
day the two sources disagree, nothing will say so.

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
when a file or store it depends on is not present. KI-CG-002 silently swaps its enum source
for a second one on that absence; this pair fails loudly and totally on it — but in both
cases the guard never asked "is my dependency supposed to be here?" before acting on its
absence.

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

### KI-CG-012 — The hooks' test seams disagree on both variable name and separator, so verifying a hook the wrong way exits 0 having checked nothing

> **Renumbered at merge, 2026-08-25: filed as `KI-CG-008`, now `KI-CG-012`.** `main`
> independently minted its own `KI-CG-008` (plus 009-011) while this branch was in flight.
> Same collision `KI-BO-016` records, in a second register on the same day.

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-24 · **Last seen:** 2026-08-24
- **Where:** `scripts/commit_guardian/check_ac_limits.py:398,418` versus
  `scripts/commit_guardian/check_ac_schema.py`

**Symptom.** The commit-guardian hooks each provide an environment-variable seam so a
caller can hand them a file list instead of reading the git index. The seams are not the
same. `check_ac_limits` reads **`HOOK_TEST_FILES`** and splits on **newlines**;
`check_ac_schema` reads **`HOOK_TEST_STAGED_FILES`** and splits on **`os.pathsep`**. Use
the wrong name or the wrong separator and the hook does not error — it resolves the whole
list to one nonexistent path, finds no AC files to examine, prints nothing, and **exits
0**. The caller sees a clean run from a hook that inspected nothing.

**Evidence.** Found 2026-08-24 by an authoring agent verifying six new AC files. Passing
a colon-separated list to `check_ac_limits` via `HOOK_TEST_FILES` produced silence and
exit 0. Re-running the identical file set newline-separated produced the expected
`OVERRIDE ACTIVE` audit lines for `BO-2400c` (6/6) and `BO-2400f` (12/12) — so the hook
was working correctly the whole time and the first invocation had simply handed it
nothing.

**Why it matters more than a CLI quirk.** This is the verification path. Someone reaching
for the seam is, by definition, trying to confirm a hook would have blocked something —
and the failure mode returns exactly the answer they were hoping for. It is the same shape
as the `argv`-ignoring trap already recorded against these hooks in KI-CG-001 and in
`CLAUDE.md`'s "AC-store commits" section: *silence from an AC hook is not a pass, it may
mean the hook was never given your file*. Two seams with two names and two separators
multiplies the ways to get that silence.

**Fix direction.** One seam, one name, one separator, shared by every hook — and make it
**fail closed**: if the variable is set and resolves to zero existing files, exit non-zero
naming what could not be resolved, rather than exiting 0 having examined nothing. An
explicitly-provided list that matches nothing is a caller error, never a pass. Until then,
the reliable way to prove a hook saw your files is the one used here: re-run it with a
deliberately invalid file alongside the real ones and confirm it fails on the invalid one.
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

### KI-CG-008 — `check-doc-frontmatter` crashes with a `TypeError` on any non-string entry in `related_docs`, making the labelled-list form uncommittable

- **Severity:** blocker
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** `templates/scripts/commit_guardian/frontmatter_validators.py:226-250`
  (`validate_paths`), crash at `:245`
- **Reported by:** adopter repo DIAGraph (`roche-sandbox/dia-graph`), against pin `54356a92`

**Symptom.** The hook aborts with an unhandled traceback rather than emitting a validation
error:

```text
File ".leafcutter/scripts/commit_guardian/frontmatter_validators.py", line 246, in validate_paths
    full_path = project_root_path / p
                ~~~~~~~~~~~~~~~~~~^~~
TypeError: unsupported operand type(s) for /: 'PosixPath' and 'dict'
```

**Root cause.** `validate_paths` guards that the *field* is a list and never that its
*elements* are strings:

```python
path_fields = ["related_docs", "related_code", "architecture_diagrams"]

for field in path_fields:
    paths = fm.get(field)
    if not paths or not isinstance(paths, list):
        continue
    for p in paths:
        full_path = project_root_path / p     # p may be a dict
```

An adopter whose convention labels each related doc with its Diataxis genre —

```yaml
related_docs:
  - explanation: docs/explanation/architecture.md
```

— hands YAML a mapping, so `p` is `{"explanation": "docs/explanation/architecture.md"}` and
`Path / dict` raises. Nothing in the package declares which shape is canonical:
`doc_types.json` says nothing about `related_docs`, and the hook's own README describes only
"path existence of `related_docs` / `related_code`". So an adopter has no way to learn the
constraint except by crashing into it.

**Scope.** Not an outlier in the reporting repo — it is the dominant convention there. Of
50 documents under `docs/**/*.md` declaring `related_docs`, **at least 33** use the mapping
form. Every one of them is uncommittable, and because the hook crashes rather than failing,
the practical workaround is `SKIP=check-doc-frontmatter` — which is worse than a strict
gate, since it teaches the reflex that also disables the ~40 hooks that were working.

**Reproduce.** From a checkout where the declaring config is reachable (otherwise KI-BP-003
masks this by crashing first):

```bash
python .leafcutter/scripts/commit_guardian/check_doc_frontmatter.py docs/reference/configuration.md
```

**Scope note.** `check_adr_cross_reference._doc_mentions_adr` also consumes `related_docs`
but does a raw case-insensitive substring match over the whole file, so it is unaffected.
`validate_paths` is the only consumer that indexes into the elements.

**Fix direction.** Normalise the element before use and decide deliberately which form is
canonical — then say so somewhere an author will read. Accepting both is cheap:

```python
for p in paths:
    if isinstance(p, dict):
        candidates = [v for v in p.values() if isinstance(v, str)]
    elif isinstance(p, str):
        candidates = [p]
    else:
        errors.append(f"Unsupported entry in '{field}': {p!r}")
        continue
    for c in candidates:
        if not (project_root_path / c).exists():
            errors.append(f"Broken path in '{field}': '{c}' does not exist")
```

Whichever shape wins, the validator must **reject an unsupported shape with a message**
rather than raise. A hook that crashes on valid-looking YAML cannot be complied with, only
bypassed.

**Pattern:** the inverse of the usual false-green — a gate so brittle that the only
available response is to turn it off, taking every sibling hook with it.

---

### KI-CG-010 — `check-roadmap-schema` never validates the roadmap, and two other guardrails require content the schema forbids

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/scripts/commit_guardian/check_roadmap_schema.py:27` — `SCHEMA_RELATIVE = "leafcutter/config/roadmap.schema.json"`

**Symptom, part one — the hook never runs.** It resolves its schema at
`<git-root>/leafcutter/config/roadmap.schema.json`. In this repository the git root **is**
the package, so the real path is `config/roadmap.schema.json` with no `leafcutter/` segment.
The file it looks for does not exist, so the hook takes its fail-open branch and reports an
advisory skip. Every commit touching `docs/roadmap.json` has passed a check that never ran.

**Symptom, part two — this is a guardrail-versus-guardrail contradiction.** Two live rules
govern the same file and disagree about its contents, and the disagreement has survived only
because one of them never executes:

| Rule | Says about `docs/roadmap.json` |
|------|--------------------------------|
| `check-surface-components-e3` (enabled, `files: ^(config/agent_registry\.json\|config/skill_registry\.json\|docs/roadmap\.json)$`) | every phase entry **must** carry a non-empty `components` list, or the commit is blocked by name |
| `config/roadmap.schema.json` (via `check-roadmap-schema`) | a phase item declares `additionalProperties: false` over six properties — `description`, `exit_criteria`, `id`, `status`, `tickets_advancing_outcome`, `title` — so `components` is **forbidden** |

The roadmap satisfies the rule that runs and violates the rule that does not. Repair the path
in isolation and the two rules meet for the first time: the enabled hook demands the key, the
newly-live schema rejects it, and `docs/roadmap.json` becomes uncommittable in both
directions at once. That is the substance of this entry — the dormant no-op is what has been
hiding it.

**Evidence.** Verified 2026-08-25. `ls <repo>/leafcutter/config/roadmap.schema.json` → no
such file; `config/roadmap.schema.json` exists. Validating the live roadmap against that
schema with `jsonschema` (installed — `requirements-dev.txt` pins `jsonschema>=4.0`, so the
hook takes its `jsonschema.validate` branch, not the laxer manual fallback) returns **8**
errors: one `components` rejection for each of the 7 phases, plus a top-level
`Additional properties are not allowed ('last_updated' was unexpected)` — the root object
also declares `additionalProperties: false`. So the schema is behind the file on two counts,
not one.

On the other side, `check-surface-components-e3` is registered with `"enabled": true` and its
`_comment` records the backfill that made it enforceable: *"ENABLED 2026-07-14 after all
registry entries were backfilled (agents 53/53, skills 36/36, roadmap 3/3)"*. All 7 phases
carry `components` today.

**Dropping `components` is not an available repair.** `KM-KGS-100e-3` — *"Registry-declared
items (agents, skills, roadmap) must declare a component too"* — is `work_status: done`,
`readiness: approved`, and its criteria name the roadmap explicitly as a
membership-declaring surface whose entries must be flagged and blocked when the membership is
absent. Its `implemented_by` is the enabled hook above. Removing the key would break a done,
approved AC and disconnect every phase from the knowledge graph's
`component_membership` edges, which is the whole point of that record.

**The third route, named and rejected on substance rather than on cost.** "Break a done AC"
is not by itself a reason — a done AC can be amended, and several were in the change that
recorded this entry. The reason is what the key *does*: `components` is what joins a phase to
the knowledge graph, so dropping it plus amending `KM-KGS-100e-3` to permit the absence would
leave the schema and the hook agreeing about a roadmap that no longer participates in the
graph. That trades a contradiction between two guardrails for the silent loss of the thing
both were protecting. The schema is behind the file; the file is not wrong.

This is also the same shape as `KI-BP-003` and `KI-CG-002` — a guardrail that cannot reach its
own declaring file in the self-hosted layout — and the third instance found. Unlike
`KI-CG-002`, which silently swaps its enum source for an equivalent one, this one skips the
check entirely.

**Fix direction.** **The schema must gain the key — that direction is forced.** Add
`components` (array of strings, non-empty) to the phase item's `properties`, and add
`last_updated` to the root object's, in the **same** change that repairs the path resolution.
Resolve the schema the way `KI-CG-009`'s repair does, from the running artifact's own
location rather than a hardcoded `leafcutter/` segment that assumes a consumer layout.
Sequencing matters: repairing the path first turns a dormant no-op into an immediate merge
blocker on the next unrelated roadmap edit.

Beyond the point fix, the two rules should not be able to drift apart again. Whatever declares
which registry surfaces must carry `components` (`config/paths.json` `edge_fields`, which the
enabled hook already reads) is the natural source for the schema's own answer. Note the
regression test must run with the CWD somewhere other than the layout under test, or it will
be green against both the broken and the fixed resolver.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M5 (a validator that reports
success having checked nothing) and M2 (a guardrail that cannot reach a file it depends on) —
with the aggravating twist that the dead validator is the only reason a live contradiction
between two guardrails has never been observed.

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

**Related — and note why `BP-1500a` cannot reach this.** This is `KI-BP-002`'s shape in
another file: a tracked generated artifact that drifts every time it is rebuilt, and
`BP-1500a` is the acceptance criterion written against that class. It cannot catch either
defect here, and the reason is structural rather than a matter of scope. `BP-1500a` promises
that *"a rebuild that would change [a tracked generated file] fails a check that names the
file"* — a comparison of committed content against regenerated content. But
`regenerate-roadmap-mirror` is a **transform-tier** hook: when `docs/roadmap.json` is staged
it rewrites `docs/roadmap.md` and then `git add`s it (`run()` →
`_git_add(mirror_path, root)`), so the mirror that lands in the commit *is* the generator's
own output, by construction. Committed and generated can never disagree about content, so a
drift check finds nothing to name. The only thing a later rebuild can move is the wall-clock
date stamp — which is noise, not either defect. `BP-1500a`'s guarantee therefore holds
**vacuously** over this file while both defects survive underneath it. Adding the roadmap
mirror to `BP-1500a`'s scope would not change that; these two want a test that asserts what
the generator *emits*, not one that compares it to what was committed.

---

### KI-CG-013 — The schema hook and the done-proof oracle disagree about what a leaf is, so one AC can be required to satisfy both branches

- **Severity:** medium
- **Status:** open
- **Occurrences:** 3
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/scripts/commit_guardian/_ac_schema_validators.py` (`_is_leaf_ac`)
  vs `scripts/ac_store/done_proof.py` (`verify_done_eligible`)

**Symptom.** Two gates that run against the same record define "leaf" from different fields:

| Gate | Definition of a leaf |
|------|----------------------|
| `_is_leaf_ac()` | `level` is `L2` or `L3` |
| `verify_done_eligible()` | `covered_by` resolves to no real AC record |

An `L2` that has real children is therefore a **leaf** to the schema hook and a
**composite** to the oracle. The schema hook demands the record carry its own `test_spec`;
the oracle derives its proof from the children and expects no direct tag. Neither is wrong
on its own terms, and nothing reconciles them.

**Evidence.** `BO-1500a-1`, `BO-1500b-1` and `BO-1500c-1`. Each was corrected from
`work_status: done` to `in_progress`, which brought it into the schema rule's scope — it
fires on `readiness: approved` AND `work_status != done` AND a code AC AND a leaf AC — and
produced:

```
approved code AC must declare a test contract — add a non-empty test_spec
```

while the oracle treated the same three records as composites resolving through their
children.

**How it was handled.** Each parent was given an integration-level `test_spec` distinct
from its children's unit contracts. That is a defensible outcome on its own merits — an L2
with children can legitimately own an integration test — but it resolved the symptom by
satisfying both definitions at once, not the divergence. The next record in this shape will
hit it again, and an author who reads only one gate's rule will conclude the other is
malfunctioning.

**Consequence.** Bounded today: it demands an extra `test_spec` rather than passing
something unproven. The risk is that the two definitions drift further, or that someone
"fixes" one gate to match the other without noticing the fix inverts a proof obligation
somewhere else.

**Fix direction.** Decide which field is canonical for leafness — `level` or resolvable
`covered_by` — and make both gates read one shared predicate, rather than aligning them by
hand. `covered_by` is the better candidate, being the thing the tree is actually built
from; `level` is an assertion about a record that its children can contradict. Whichever
wins, it wants a test asserting the two gates classify an identical fixture set the same
way, including the awkward case this issue is about: an `L2` with real children.

**Related.** `KI-ACS-006` (composite-resolution defects in the oracle) and `KI-CG-006` (the
pre-commit proof-of-done gate and the CI backstop disagreeing on what a valid covers tag
is). All three are the same underlying shape — two halves of the AC guardrail system
holding different definitions of one concept — and a fix for any one of them should check
whether it moves the other two.

---

### KI-CG-012 — `check-ac-schema` reports a clean pass on a file it never validated, because Phase 1 fails open on an empty staged set

> **ID COLLISION — this entry and the one at `KI-CG-012` above share a number.** Two sessions
> minted `KI-CG-012` independently on 2026-08-25; the other entry ("the hooks' test seams
> disagree on both variable name and separator") was itself renumbered from `KI-CG-008` at
> merge, which is how the collision arose. Deliberately **not** renumbered here, because the
> inbound references do not disambiguate cleanly and a wrong renumber is worse than a flagged
> duplicate:
>
> - `commit-guardian.md:953` and `build-pipeline.md:1095` cite `KI-CG-012` for an
>   "invisible until touched" property — fits neither entry unambiguously.
> - `BP-600d-3.yaml:186` cites it as "a third" occurrence of index-scoping — that reads as
>   *this* entry.
> - The 2026-08-25 10:26 changelog describes `KI-CG-012` as the `_is_leaf_ac()` / leaf-definition
>   disagreement, which is the text now filed as **`KI-CG-013`** — so at least one inbound
>   reference is already pointing at the wrong entry independently of this collision.
>
> Whoever owns this file should pick the renumber and fix all four references in one commit.
> Next free id at time of writing is `KI-CG-017`.

- **Severity:** high
- **Status:** open
- **Occurrences:** 3
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/scripts/commit_guardian/check_ac_schema.py` — `main()` (`root = Path(os.environ.get("HOOK_ROOT", str(Path.cwd())))`, `:673`), `_get_staged_ac_paths()` (`:307`, fail-open documented in its own docstring), the `if not staged_files:` branch (`:685`), and `_find_project_root()` (`:99`)

**Symptom.** The hook exits 0 having validated nothing, and its output is indistinguishable
from a run that validated everything and found it clean. There is no "checked 0 files"
line: a skipped Phase 1 and a passing Phase 1 look identical.

**Evidence — two independent observations on the same day.**

*Deliberate mutation.* `declares_side_effect: true` was removed from a staged
`BP-600b-3.yaml` whose criteria assert a durable effect — precisely the condition
`validate_declares_side_effect` exists to catch. Both the direct invocation and
`pre-commit run check-ac-schema` reported **Passed**. CI, on that same commit, failed the
required `AC store valid` check and named both the file and the rule. The local exit code
carried no information; only CI evaluated the record.

*Wrong-root run.* A separate agent, running the deployed hook against AC files in a
worktree, saw it print `WARNING: config/ac_store_schema.json not found at
/home/henzeh/projects/leafcutter; falling back to manual field validation` and exit 0. It
had resolved the project root to the **workspace parent** — the untracked directory above
the repository, which has no `config/` tree.

**Root cause, as far as the source states it.** Three mechanisms each independently make a
clean exit reachable without any file being checked:

1. `main()` derives its root from **CWD**: `root = Path(os.environ.get("HOOK_ROOT",
   str(Path.cwd())))`. Nothing constrains CWD to the repository whose index is being
   committed.
2. `_get_staged_ac_paths(root)` shells out to `git diff --cached` under that root, and its
   own docstring states it "returns an empty list when `HOOK_NO_GIT` is set or git is
   unavailable (**fail-open**)". `main()` then takes `if not staged_files:` and skips
   Phase 1 entirely. A wrong root and an absent git both land here.
3. `_find_project_root()` — used by Phase 2, **not** by `main()` — walks ancestors
   accepting `.git` **or `CLAUDE.md`**. The workspace parent has a `CLAUDE.md`, so that
   search can terminate at a directory that is not a repository. Two different root
   strategies in one file, and they disagree.

The schema fallback is **not** the whole story. `validate_declares_side_effect` is called
unconditionally at `:625`, independent of whether the schema loaded, so a missing schema
alone would still have caught the mutation. What silences the hook is Phase 1 not running.

**Honest limit of this report.** The `pre-commit run` invocation was not isolated to a
single mechanism — cwd was inside the worktree for that run, so (1) and (2) do not
obviously explain it, and the exact path taken was not pinned down. The three code facts
above are directly readable and each permits a silent pass; which one fired in that
specific invocation is still open. Do not close this on the strength of fixing only the
one that looks most likely.

**Third occurrence, 2026-08-25 — mechanism (2) isolated, and `HOOK_TEST_FILES` does not
rescue it.** CI's required `AC store valid` refused `BO-1500a-1.yaml` for a missing
`declares_side_effect`. Reproducing locally from inside the worktree, with the correct
root, the hook exited 0 three ways:

1. `HOOK_TEST_FILES` set to the 46 changed records — exit 0.
2. `HOOK_TEST_FILES` set to the single offending record, **before** the fix — exit 0.
3. The fix applied and staged — exit 0.

Run 2 is the control, and it is the informative one: the hook passed a record that CI
refused by name, on a rule that record genuinely violated. The common factor is that
`BO-1500a-1.yaml` was already at `HEAD` unmodified, so `git diff --cached` was empty and
`main()` took the `if not staged_files:` branch — **regardless of `HOOK_TEST_FILES`**.
Whatever that variable is honoured by, it is not the gate that decides whether Phase 1
runs, so it cannot be used to point the hook at a file for verification. The docstring's
fail-open note (mechanism 2) is therefore reachable with a correct root and a working
git, not only with a wrong root or an absent one.

This also explains why CI sees what local runs cannot: the `ac-store-valid` job does
`git reset --soft origin/main` before invoking the hooks, which stages the branch's entire
diff. Locally, only files differing from `HEAD` are ever examined — so a defect already
committed is structurally invisible to the local gate, and no amount of re-running it
proves anything about those records.

Add to the fix direction: whatever `HOOK_TEST_FILES` is for, it must either drive the
Phase 1 file set or be removed. A test seam that silently does nothing is how a
verification step becomes theatre.

**Fix direction.** Make "checked nothing" impossible to confuse with "checked and passed":

- **Never exit 0 on an empty file set.** If the hook was invoked and resolved zero files,
  say so on stderr and exit non-zero, or at minimum print the count. `KI-ACS-001` fixed
  exactly this shape in `validate_ac_schema.py` on 2026-08-19 — a bare directory printed
  `No YAML files to validate.` and exited 0 — and the same reasoning applies here.
- **Resolve the root once**, from `git rev-parse --show-toplevel`, and thread it to every
  consumer. Drop the CWD default and the `CLAUDE.md` ancestor heuristic: a `CLAUDE.md`
  marks a *workspace*, not a repository.
- **Do not fail open when git is unavailable.** A gate that cannot determine what is being
  committed has not passed; it has failed to run.

**Relationship to existing entries.** Same family as **KI-CG-009**
(`check-components-integrity` resolving the root to the main checkout rather than the
worktree) and **KI-CG-002** (a silent fallback to a second enum authority when a declaring
file is unreachable). It shares **KI-CG-001**'s index-scoping premise but is a distinct
failure: there the hook checks the wrong *set*; here it checks the *empty* set and says
nothing. Four entries now describe the same root-resolution surface, which argues for one
piece of work across the hook family rather than one hook at a time.

**Pattern:** a gate whose silence is structurally indistinguishable from a pass.

---

### KI-CG-015 — `declares_side_effect` is authored by the IT-PO pass and derived by the schema check, and on records about writing files the two systematically disagree

- **Severity:** medium
- **Status:** open
- **Occurrences:** 7 records in two families, all on 2026-08-25 (3 × `BO-2400e`, 4 × `BP-1500d`; the two families were resolved in opposite directions — see the amendment below)
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `derive_declares_side_effect` and `_DURABLE_EFFECT_RE` in `scripts/commit_guardian/_ac_schema_validators.py:560-607`; enforced by `validate_declares_side_effect`; rule is BO-2900g-2

**Symptom.** `check-ac-schema` requires the authored `declares_side_effect` to equal a value
derived from the record's own Then clause, and rejects the commit when they differ. Three
acceptance criteria in the `BO-2400e` family — `BO-2400e-3`, `BO-2400e-3-i` and `BO-2400e-4` —
each carried `declares_side_effect: true`, hand-written by the 2026-08-17 IT-PO enrichment pass,
and each was rejected the first time the file was staged after the derivation rule shipped. All
three had to be flipped to `false`.

**The rule is right and the flips were correct.** The docstring is explicit that the value must
be DERIVED and "never authored by opinion", so the hand-authored `true` was the anomaly, not the
derivation. This entry is not a request to change that.

**What is worth attention is what the derived value now says.** All three records are *about*
durable writes — the AC titles are "An interrupted update never destroys the work record it was
updating", "A store that cannot be written is announced…", and "Recording progress on a
requirement changes the progress and nothing else". Their Then clauses read:

- "the record still contains everything it contained before the update"
- "no record in the store has been changed"
- "changes exactly those thirty-three values and nothing else in the store"

None matches `_DURABLE_EFFECT_RE`, which wants `written to disk`, `is persisted`,
`updates the (database|store)` and similar. So the store now says `declares_side_effect: false`
on three records whose entire subject is bytes surviving on disk. Each carries an `amended_by`
note explaining why, because the value reads as an error without one.

**Two readings, and they need different fixes.**

1. *The pattern is too narrow.* It was calibrated to match ~3.6% of records (114 of 3,148),
   deliberately, so that the derivation marks a strict subset. But a Then clause that says the
   record is unchanged, or that nothing else in the store changed, is describing a durable
   effect in ordinary English. Widening it risks the "marks everything" failure the constraint
   was written against, so this is a judgement call, not an obvious fix.
2. *The IT-PO should not author this field at all.* Three-for-three disagreement in one family
   suggests the enrichment pass is writing a derived field by opinion. If the field is derived,
   the authoring step should omit it and let the deriver own it — which would have surfaced this
   in 2026-08-17 rather than a week later, one record at a time, at commit time.

**Why it stayed hidden for a week.** The hook validates only the files in a commit's index, so a
record authored before the rule shipped is never checked until something unrelated touches it.
All three surfaced on the same day only because all three happened to be staged that day. The
same "invisible until touched" property is recorded for a different gate in KI-CG-012, and for
mypy in KI-BP-013.

**The sweep, run 2026-08-25.** The derivation was run read-only over the whole store to size
this. Result:

```
records scanned            : 3338
with declares_side_effect  :   38
DISAGREE with derivation   :    9
  authored true,  derives false : 9
  authored false, derives true  : 0
```

Three facts follow, and each narrows the fix.

1. **The disagreement is 100% one-directional.** Nine records say `true` where the derivation
   says `false`; **not one** goes the other way. A too-narrow pattern and an over-eager author
   would both produce disagreements, but only an over-eager author produces them all in the same
   direction. That is strong evidence for reading 2 over reading 1.
2. **Nine live landmines remain**, on top of the three already repaired. Each will block a commit
   the first time anyone touches that file, at an unrelated moment, exactly as the three did:

   ```
   BO-2400g-4    BO-2400g-4-i   BO-2900g-1    BO-2900g-2   BO-2900g-2-i
   BO-2900g-4    BP-1100g-4     BP-1100g-4-i  BP-1100g-5-i
   ```
3. **`BO-2900g-2` is in the list.** The acceptance criterion that *establishes* the derive-never-
   author rule violates its own rule. Whatever else is decided, that one should be fixed on sight.

Also worth noting: only **38 of 3,338** records carry the field at all, so this is a sparsely
populated field where a quarter of the populated values are wrong — small enough to fix by hand
in one pass.

**Fix direction.** Given the one-directional result, prefer reading 2: stop the IT-PO pass
authoring a derived field, and correct the nine records. Widening `_DURABLE_EFFECT_RE` is the
more invasive change and the sweep does not support it — no record is failing because the pattern
was too strict about a value someone tried to set to `false`.

---

**AMENDED 2026-08-25 — a second family hit this the same day and resolved it the opposite way.
Occurrences 3 → 7.** `BP-1500d-1` through `BP-1500d-4` were enriched independently that day, all
four authored `declares_side_effect: true`, all four rejected. Same defect, same hook, different
resolution: instead of flipping to `false`, the BA amended the Then clauses to name the artifact
concretely, and the derivation then agreed. Both families are now in the store with **opposite**
values on the same question — `BO-2400e` says `false` on records whose subject is bytes surviving
on disk, `BP-1500d` says `true`. That inconsistency is now the most urgent thing here.

**The one-directional argument above does not support reading 2, and this is load-bearing.** The
inference is that "only an over-eager author produces them all in the same direction." That is not
so. A too-narrow pattern **also** produces exclusively `authored true / derives false`, because
under-matching can only ever fail to fire — it is structurally incapable of producing
`authored false / derives true`. The observed 9-0 split is therefore equally consistent with both
readings and discriminates between them not at all. The zero is a property of the failure mode,
not evidence about its cause.

`BP-1500d-1` is the decisive counterexample. Its Then clause read *"that project holds its own
record of what the build put there ... a copy of the project taken without the producing package
still carries it"* — a durable file by any ordinary reading — and derived `false`. Verified with a
negative control isolating vocabulary as the only variable:

| Then-clause phrasing | Derives |
|---|---|
| `Then a record file is written into that project` | `True` |
| `Then that project holds its own record of what the build put there` | `False` |

Identical claim, opposite verdict. The pattern **was** under-matching a real durable effect, so
reading 1 is not hypothetical, and "correct the nine records" would have written `false` onto four
records that genuinely do write files.

**Sweep numbers reconcile.** An independent read-only sweep the same day counted **12**
disagreements against this entry's **9**. Not a contradiction: that sweep ran on a tree predating
the `BO-2400e-3 / -3-i / -4` repair, and 9 + 3 = 12. Both counts are correct at their own commit.

**The structural fix neither entry names: there is no code-side reconciliation.** The sibling field
`package_surface` has exactly the two-sided design this one lacks — `check_package_surface_declaration.py`
(ACS-100i-8, commit-msg stage, confirmed installed) reconciles the registry entries a change
*actually adds* against the declarations of the ACs it cites. Its own registration comment states
the reason: *"the declaration is under the author's control and can simply be omitted, but the
registration cannot be."* `declares_side_effect` has only the prose side, which is why reading 2 is
dangerous on its own — telling authors to stop setting the field, with nothing checking what the
code does, makes omission both correct-by-policy and free. Omission derives `false` and passes
**silently**, switching off `user-surface-smoker`, described in this repo as the one automatic guard
against code that is built but not wired into anything.

Detection is admittedly harder here than for `package_surface`: "a registry key appeared" is a JSON
diff, whereas "this change writes a durable artifact" means recognising `open(...,'w')`,
`write_text`, `shutil.copy` and friends. And ACS-100i-8's own config records CONCESSION 3 — its
watched-registry enumeration goes stale unless extended in the same change. A side-effect
equivalent inherits that weakness.

**Revised recommendation.** Reading 1 and reading 2 are both real and neither alone is sufficient.
Keep the field author-set but make it a deliberate BA decision rather than an IT-PO reflex; demote
the regex from decider to cross-check that reports disagreement, which is the one thing it already
does well; and add the landing-time reconciliation so omission is not free. Reconcile the
`BO-2400e` / `BP-1500d` split deliberately in one pass rather than one blocked commit at a time —
and note that a standing "name durable artifacts concretely in Then clauses" authoring rule is a
poor substitute, because it asks every author to write for a matcher and collides directly with the
customer register the PO/BA are required to use.

---

**Read alongside KI-CG-014, which the sweep above structurally could not see.** That entry is
the mirror image of this one: the derivation returning `true` where it should return `false`,
because it matches a write phrase inside a *negated* clause. The sweep counted disagreements
among the **38 records that carry the field**, and reported `authored false, derives true: 0`.
That zero is real but narrow — it means nobody had yet tried to author `false` against a `true`
derivation. KI-CG-014 is what happens when someone does: the attempt is rejected and there is no
value the author can honestly write. So the sweep's conclusion that the pattern is not too strict
holds; it says nothing about the pattern being too *loose*, which is a different axis and is also
broken. Whichever reading wins here, negation handling is needed regardless.

---

### KI-CG-014 — `declares_side_effect` derivation is negation-blind, so an AC asserting that nothing is written is forced to declare that something is

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/scripts/commit_guardian/_ac_schema_validators.py` — `_DURABLE_EFFECT_RE` (`:567`) and `derive_declares_side_effect()` (`:581`)

**Symptom.** `derive_declares_side_effect()` searches the Gherkin `Then` clause for
durable-effect phrases with a plain regex. It has no notion of negation, so a criterion
asserting that a write must **not** happen derives the same `True` as one asserting that it
must. `validate_declares_side_effect()` then rejects the record unless it declares
`declares_side_effect: true` — and rejects an authored `false` as a disagreement. The author
is left with no way to state the truth: the only value the hook accepts is the wrong one.

**Evidence.** Hit live on 2026-08-25 authoring `ACS-1100d-5-i`, whose `Then` clause read
*"a referral is not a pass: no finished status **is written** while the referral stands"*.
`_DURABLE_EFFECT_RE` matches `\bis written\b`; the record asserts an abstention and has no
durable effect at all. CI failed the required `AC store valid` check with *"criteria assert
a durable, observable effect … add declares_side_effect: true."*

This is not cosmetic. `derive_declares_side_effect()`'s own docstring states the field
"routes a ticket's `user-surface-smoker` phase agent" — so a forced `true` does not merely
record a wrong fact, it dispatches a smoke-test phase to look for side effects the AC
guarantees will not occur. The wrong value propagates from the store into ticket generation.

Worked around in `ACS-1100d-5-i` by rewording `is written` → `is recorded`, with the reason
recorded in that file's notes so it is not "corrected" back. That is a workaround, not a fix:
it makes one record's phrasing dodge the matcher while every future author hits the same wall,
and it puts pressure on criteria wording to satisfy a regex rather than to read well.

**Fix direction.** The derivation is deliberately narrow and phrase-based — the code comments
argue, correctly, that a matcher marking everything is worthless. Keep that. Add negation
handling: reject a match whose phrase is governed by a preceding negator (`no`, `not`,
`never`, `must not`, `is not`) within the same clause. Then extend the calibration the
comments already describe — *"~3.6% of records with a Then clause matched (114 of 3148)"* —
to report how many of those matches are negated, which measures the false-positive rate
rather than assuming it is zero.

Whatever the fix, `validate_declares_side_effect()` should not be able to leave an author
with no acceptable value. A disagreement between an authored `false` and a derived `true` is
currently reported as the author's error; sometimes, as here, it is the derivation's.

**Relationship to KI-CG-015.** Same function, opposite direction, filed the same day by two
sessions that each hit one half. KI-CG-015 is the derivation returning `false` on records whose
whole subject is bytes surviving on disk; this is it returning `true` on a record that asserts
nothing is written. Its sweep of the 38 populated records found nine disagreements, all
`authored true / derives false`, and reasoned from that one-directionality that the pattern is
not too strict. That reasoning is sound and untouched by this entry — an over-loose match on a
negated clause is a separate defect that the sweep could not detect, because the affected record
carries no authored value to disagree with. Two entries rather than one merged entry, because the
fixes are independent: KI-CG-015 argues about who owns the field, this one about whether the
matcher reads English correctly.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M8 (a check measuring a proxy and
reporting it as a verdict) — the proxy is "does the Then clause contain a write phrase", the
verdict claimed is "this AC has a durable side effect", and negation is the gap between them.

---

### KI-CG-016 — `check-build-drift` is filtered on the consumer layout path, so it has never run on this repo's own template changes

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** the generated `.pre-commit-config.yaml`, `check-build-drift` entry — `files: ^leafcutter/templates/`

**Symptom.** The hook exists to catch a template edited without a rebuild. Its file filter is
`^leafcutter/templates/`, which is where templates live in a **consumer** install, where the
package is vendored under `leafcutter/`. In this repository — the package itself — templates
live at `templates/`. The pattern therefore matches nothing here, the hook has `pass_filenames:
false` and no `always_run`, and pre-commit skips it. The one repository where every template
change originates is the one repository where the drift gate does not run.

**Evidence.** Observed in two consecutive commits on `fix/signoff-tool-allowlist`, which is
what makes it unambiguous rather than inferred:

```text
commit 1 — staged five files under templates/agents/
  Check Build Drift (leafcutter)........................(no files to check)Skipped

commit 2 — staged only changelogs/ and docs/acceptance-criteria/
  Check Build Drift (leafcutter)........................Failed
```

Skipped on the commit that changed five agent templates; ran on the commit that changed no
template at all. The second run failed for an unrelated reason (KI-BP-011 — a manifest with no
`output_mappings`), and only because the worktree was mid-bootstrap and briefly held an older
config in which the entry carried `always_run: true`. Once the canonical build regenerated the
config, the `^leafcutter/templates/` filter came back and the hook skipped again.

**Why the severity is high rather than medium.** This is the gate whose absence lets every
other deploy-staleness issue in the build-pipeline register survive. KI-BP-004 (worktree hooks
frozen at build time) and KI-BP-008 (a skipped workflow-install phase leaving a deployed
workflow 1497 lines stale) both propose extending `check_build_drift` as the natural home for
the fix. Both proposals are unreachable while the hook never fires in the package repo.

**A DETECTOR ALREADY EXISTS, AND IT IS RED — found while committing this entry.**
`check-hook-trigger-reachability` (BP-100k-4) does exactly this analysis and fires on it. It
ran on the commit that added this section and failed, naming **five** unreachable hooks, not
one:

```text
UNREACHABLE: check-build-drift            files pattern '^leafcutter/templates/'
UNREACHABLE: check-infra-docs             files pattern '(docker-compose.*\.ya?ml|...)'
UNREACHABLE: check-paths-integrity        files pattern '^leafcutter/config/paths\.json$'
UNREACHABLE: check-architecture-scaffolds files pattern '^leafcutter/templates/docs/architecture/'
UNREACHABLE: check-output-drift           files pattern '^(\.claude/agents/|\.claude/skills/|...)'
check-hook-trigger-reachability: RESULT total=50 unreachable=5 exempt=0
```

So the correction to this entry's original framing: the gap is **not** that nothing detects the
condition. It is that the condition is unresolved across five hooks, and the gate that reports
it blocks commits touching unrelated files, which makes it likely to be skipped rather than
acted on. Three of the five (`check-build-drift`, `check-paths-integrity`,
`check-architecture-scaffolds`) are the `^leafcutter/`-anchored consumer-path class this entry
describes. `check-output-drift` is the same class pointing at `.claude/`, which is gitignored
here. `check-infra-docs` is different in kind — this repo genuinely has no docker-compose or
`.env.example`, so that one may be legitimately inapplicable rather than misconfigured, and an
`exempt` mechanism exists (`exempt=0`) that nobody has used.

That distinction is the real work: the reachability gate currently cannot tell "this filter is
written against the wrong layout" from "this hook does not apply to this repository". Until it
can, its verdict is unactionable in bulk and gets skipped, which is how five accumulated.

**Fix direction.** Derive the filter from the layout rather than hardcoding one of the two, or
match both — `(^|/)templates/`. Do it for all three consumer-path hooks at once, mark
`check-infra-docs` exempt if it is genuinely inapplicable, and decide what `check-output-drift`
should point at given `.claude/` is gitignored. Verify by staging a template change in the
package repo and observing `check-build-drift` actually run — the skip line is quiet and reads
like a pass.

**Trap.** `(no files to check) Skipped` is visually indistinguishable from a hook that ran and
had nothing to say, and it appears in the middle of a long green hook list. Nothing in a normal
commit surfaces the fact that the drift gate has been inert for the life of the repository.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2's filter form: source and deployed
layouts differ, and the gate is configured against the layout it is not running in.
