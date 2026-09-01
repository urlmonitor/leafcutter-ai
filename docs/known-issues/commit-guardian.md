---
title: "Known issues — commit-guardian"
description: "Open, observed defects in the commit-guardian component: the pre-commit hook family that gates commits, and in particular the AC-store hooks whose scope is the git index rather than the store. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-26
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
>
> **Citation audit, 2026-08-26 — still not renumbered, and the reason is now stronger.** A
> repo-wide sweep done while resolving a different collision in this register found the
> inbound set has grown from four to **nine**, and it splits across *both* entries:
>
> | Citation | Resolves to |
> |---|---|
> | `GE-126a-3.yaml:43`, `:63`, `:96`, `:128` · `GE-126a.yaml:26`, `:85` · `GE-126.yaml:209` | the **test seams** entry (above) |
> | `GE-126.yaml:160` ("re-run with a deliberately invalid file") · `build-pipeline.md:1234` | **this** entry |
> | `GE-126e.yaml:28` ("all the same family") · `BP-600d-3.yaml:186` | ambiguous |
>
> So a renumber is now a nine-site change spanning six acceptance-criteria records, two of
> which cannot be resolved from their text alone. That is a deliberate, owner-sized piece of
> work and not a drive-by fix — attempting it as a side effect of unrelated work is how the
> `016`/`017` collision below was created in the first place.
>
> **Do not allocate a sequential id at all. New entries use `KI-CG-<YYYYMMDD>-<slug>`.**
> This line previously read `018`, then `034`, then `035`; each was true when written and
> overtaken shortly after — `034` was consumed by the very PR that wrote the line claiming
> it was free, and `035` by a PR that landed while another author was mid-draft against it.
> That author's entry is now `KI-CG-20260831-hook-scripts-never-invoked`; it was written as
> `KI-CG-035` and renamed at merge, which is the fourth recorded collision on this counter.
>
> The advice that replaced the number — "read the file on a fresh `origin/main` immediately
> before you land" — does not work either, and it is worth being precise about why: the read
> and the land are not atomic. Any gap between them is a window, and a parallel session only
> has to land inside it. The date-and-slug form removes the window rather than narrowing it.
> See `build-pipeline.md` → "Why not the next free number" and `KI-BO-024`. Existing
> `KI-CG-NNN` ids stay as they are — renumbering would break inbound references.

- **Severity:** high
- **Status:** open
- **Occurrences:** 4
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-26
- **Where:** `templates/scripts/commit_guardian/check_ac_schema.py` — `main()` (`root = Path(os.environ.get("HOOK_ROOT", str(Path.cwd())))`, `:673`), `_get_staged_ac_paths()` (`:307`, fail-open documented in its own docstring), the `if not staged_files:` branch (`:685`), and `_find_project_root()` (`:99`)

**Fourth occurrence, 2026-08-26 — and it came wearing a disguise worth knowing about.** A run
against 16 staged AC records in a worktree exited 0 while printing:

```text
WARNING: config/ac_store_schema.json not found at /home/henzeh/projects/leafcutter;
         falling back to manual field validation.
exit: 0
```

This was initially filed as a **separate** defect — a missing schema causing a downgrade to a
weaker check. That diagnosis is wrong and was withdrawn; see the retracted
`KI-CG-20260826-1334` at the end of this file for the A/B that disproves it (with the schema
*removed* the hook is **stricter**, catching an extra id-format error).

The WARNING is a red herring that appears at exactly the moment of the false pass. The actual
mechanism is this entry's: `_get_staged_ac_paths` shells `git diff --cached` with **no
`cwd=root`**, so the resolved root and the staged set can come from different repositories.
The root here — `/home/henzeh/projects/leafcutter` — holds a `CLAUDE.md` but no `.git`, so the
root resolution settled on the workspace directory, the staged set came back empty, and
Phase 1 was skipped.

**Why this occurrence is the most valuable of the four:** it is the first with a demonstrated
cost. The 16 staged records included two that `validate_declares_side_effect` errors on when
called directly (`KI-CG-014`). The hook passed them; CI, which builds fresh, would have failed
the required `AC store valid` check. So this is not "the hook checked nothing" in the abstract
— it is the hook returning a green that was **wrong about the specific change in front of it**,
on a change that would have gone red in CI minutes later.

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
- **Occurrences:** 14 records in three families (3 × `BO-2400e`, 4 × `BP-1500d` on 2026-08-25; 7 × `BO-3100`/`BO-3200` on 2026-08-26 — see the third-family note below)
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-26
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

**Third family, 2026-08-26 — `BO-3100` / `BO-3200`, and the first evidence that the derivation
is too LOOSE on a whole class it was not previously tested against.** The IT-PO enrichment pass
authored `declares_side_effect: true` on seven records; the gate rejected all seven with
`derives False`. On three the gate was plainly right and the authored value was implementation
reasoning rather than a reading of the Then clause — `BO-3100a-1` (assembly stops with a
failure), `BO-3200d-1` and `BO-3200d-2` (what a step *reads*, what verdict it *forms*). Those
are exactly the "authored by opinion" case BO-2900g-2 forbids, and removing the field was the
correct resolution.

On the other four the derivation looks wrong, and they share a shape the earlier two families
did not have — **a durable change to a store, expressed without any of the writing verbs the
pattern matches**:

| Record | Then clause | Why it is durable |
|---|---|---|
| `BO-3200b-1` | "every item it claimed is **back in its unclaimed state in that same store**" | mutates a store explicitly described as outliving the run |
| `BO-3200b-1-i` | "every item it had already claimed is **back in its unclaimed state**" | same |
| `BO-3100b-2` | "**no completed step is recorded**" / "**exactly one completed step is recorded**" | a sign-off persisted to the ticket record |
| `BO-3200c-1` | the run **pauses resumably** awaiting a person | a pause record that survives the run |

`_DURABLE_EFFECT_RE` looks for writing verbs. "Is back in its unclaimed state", "is recorded"
and "pauses resumably" describe the *resulting state* rather than the act, so the pattern misses
them. That is a third axis, distinct from both the too-strict reading of the first two families
and from KI-CG-014's negation blindness: **state-described-as-outcome rather than as an action.**

Resolved by removing the field on all seven rather than authoring a value the gate rejects — the
schema is explicit that this value is derived, not authored, so a conflicting authored value is
not a legitimate way to record the disagreement. The observation is recorded here instead, which
is the point of this register. Four records therefore now carry a derived `false` that is
arguably wrong; when the deriver learns outcome-state phrasing they should flip to `true` with
no criteria change, and that is the regression test for the fix.

**AMENDED 2026-08-31 — the landmine list is down to seven, and the narrowing in #594 can only
have made this entry's underlying problem larger.**

Two of the nine listed above are resolved:

- **`BO-2900g-2`** — fixed on sight in #618, exactly as point 3 above instructed. Adding a child
  (`BO-2900g-2-ii`) required staging the parent, and the forward ratchet then refused the commit
  until the stale declaration was settled. **A record cannot gain a child while it holds one** —
  a coupling nobody designed, and the mechanism by which the remaining seven are most likely to
  surface. Set to `false` for consistency with `BO-2600b-2`, whose Then clause has the identical
  "what a record *carries*" shape.
- **`BP-1100g-4`** — reconciled on `main` by other work while a branch was open. Caught by a
  store-wide allowlist-staleness test rather than by anyone noticing.

Seven remain: `BO-2400g-4`, `BO-2400g-4-i`, `BO-2900g-1`, `BO-2900g-2-i`, `BO-2900g-4`,
`BP-1100g-4-i`, `BP-1100g-5-i`. They are pinned in
`unit_tests/ac_store/test_bo_2900g_2_ii_store.py::_KNOWN_PRE_EXISTING_DISAGREEMENTS`, with one
test asserting no disagreement appears **outside** that set and a second failing when a pinned id
stops disagreeing — so the set cannot silently rot in either direction, and shrinking it is
mechanically visible. Of the seven, `BO-2400g-4-i` is the likeliest genuine false negative: it
requires findings to appear on a pull request, which is durable, externally visible, and asserted
in its Then.

**The direction of travel is against this entry.** #594 narrowed the matcher from 139 marked
records to 89 and #618 to 89 after stripping rationale. Narrowing removes false positives and, by
construction, **cannot remove a false negative — it can only create more**. Fifty-one records
flipped `true → false`; none was verified to be a genuine non-effect beyond the seven judged
individually, because the change's own acceptance criterion only required that no *authored*
value be contradicted. So this entry's population is very likely larger than seven today, and the
sweep that would size it has not been re-run. Anyone taking this on should re-run the 2026-08-25
sweep before trusting any count in this entry.

---

### KI-CG-014 — `declares_side_effect` derivation is negation-blind, so an AC asserting that nothing is written is forced to declare that something is

- **Severity:** medium → **high** (see "Second and third sightings" below)
- **Status:** open
- **Occurrences:** 4 (a fourth negated instance, `GE-125d-3`, on 2026-08-31)
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-31
- **Where:** `templates/scripts/commit_guardian/_ac_schema_validators.py` — `_DURABLE_EFFECT_RE` and `derive_declares_side_effect()` (line numbers moved in #594/#618)
- **Narrowed twice, still open:** see the 2026-08-31 measurement at the end of this entry — 50 non-negated false positives removed, **zero** negated ones

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

**Second and third sightings, hours later, same AC family — and the reason this is now high.**
An IT-PO enrichment pass over the 22-record `ACS-1100` tree hit the identical wall twice more:

- **`ACS-1100a-2`** — *"a record whose identifier **is written** with surrounding quotes"*.
  A description of YAML syntax. Nothing is written by anything.
- **`ACS-1100b-2`** — *"no second traversal of the AC tree **is written** to produce a total"*.
  A clause whose entire content is that a thing is not written.

Confirmed by calling the functions directly against both records: `derived=True`,
`authored=None`, and a real error from `validate_declares_side_effect` — with **no readiness
gate**, so `draft` records are blocked too. Both were left `draft` and staged out rather than
reworded.

**The workaround should stop, but not for the reason first given.** Rewording `is written` →
`is recorded` fixed `ACS-1100d-5-i` and was reasonable once. Applied repeatedly it becomes a
policy of bending specification prose around a regex, and that is reason enough to stop.

An earlier draft added a second argument — that rewording *erases the evidence*, because every
reworded record is one the calibration will never count. That premise is false. The population
is re-derivable in about 25 lines by re-running the matcher over the store, so nothing is
destroyed by rewording: the evidence is a property of the corpus, not of any file's current
wording. The recommendation survives; the justification offered for it did not.

The measurement that replaces it is stronger than the argument it displaces: **33 of 139
store-wide matches are fully negated, and 31 of those are currently unfixable as written on
`origin/main`.** That is the case for high severity, and it is an order of magnitude beyond the
"three instances in one day" this entry was first escalated on. Two caveats a fixer needs:
"fully negated" is proxy-dependent — a 60-character tail-anchored window yields 33, a
120-character window yields **51** — and the 31 are blocked only *when touched*, since
validation is staged-only. Re-measure with a stated window rather than inheriting the number.

**A note for whoever fixes this — the original note here was wrong, and dangerously so.**
It named `ACS-1100a-3` as a genuine true positive to be used as the **negative control**,
asserting its `Then` clause really persists an exemption record and that it must keep deriving
`True` after any negation fix.

`ACS-1100a-3` is a **false positive**. Its only `_DURABLE_EFFECT_RE` match is:

```text
And no second traversal of the AC tree is written to produce a total for that
```

— the identical negated construction `ACS-1100b-2` is filed for above. A correct negation fix
must flip `ACS-1100a-3` to `False`. Anyone following the original instruction would have
treated the correct behaviour as a regression and preserved the defect they were sent to
remove.

How the error was made, since it is instructive: the AC *does* describe a persisted exemption
record elsewhere in its criteria, and that prose was taken at face value without checking
**which clause the regex actually fired on**. (A further correction: an earlier draft of this
paragraph said the record had `declares_side_effect: true` authored on the strength of that
rationale. It does not — the field is absent, and has been since the record's only commit.
The mistake was reading the criteria, not the field.) A true positive and a false positive in
the same record look identical unless you ask the matcher what it matched.

**There is therefore no verified negative control in this batch.** Whoever fixes the negation
handling should establish one deliberately — find a record whose *matched clause* is genuinely
affirmative — rather than inheriting a candidate from this entry.

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

**2026-08-31 — the matcher was narrowed twice and the negation defect is untouched. Re-measure
before assuming otherwise.**

PR #594 replaced the bare `\bis written\b` / `\bare written\b` alternatives with object-aware
forms (a durable noun governing the verb, or a write naming a non-transient destination), and
#618 stripped `Because` rationale from the searched text. Both were measured against the real
store. Neither addressed negation, and the numbers say so precisely — same 60-character
tail-anchored window this entry specifies, so the counts are directly comparable:

| | before #594 | today |
|---|---|---|
| records marked | 139 | **89** |
| of those, negated | 33 | **33** |
| negated share | 24% | **37%** |

**Fifty non-negated false positives were removed and not a single negated one.** The defect
this entry is filed for is exactly as prevalent in absolute terms and half again as prevalent
as a proportion of what the matcher now claims. Anyone reading "the derivation was fixed" and
inferring this entry is closed would be wrong.

Of the three records named above, checked against the shipped derivation today:

- `ACS-1100d-5-i` — now derives `False`. Fixed incidentally: `status is written` no longer
  matches, because `status` is not a durable object. Not a negation fix.
- `ACS-1100a-2` — now derives `False`, same incidental reason (`identifier is written`).
- `ACS-1100b-2` — **still derives `True`**. `no second traversal … is written to produce a
  total` matches the destination-form alternative, and nothing looks at the `no`.
- `ACS-1100a-3` — **still derives `True`**, on the identical construction. The correction
  above still stands in full: a correct negation fix must flip it to `False`, and it is not a
  negative control.

So two of the four resolved as a side-effect of unrelated narrowing, and the two that are
squarely negation are unchanged. The remaining population is more concentrated and therefore
easier to fix than when this was filed: 33 of 89 rather than 33 of 139.

**Four further false-positive mechanisms in the same function, found and fixed in the same
work, none of them negation.** Recorded here because they bear on how the fixer should think
about the matcher, not because they are this entry's subject: a write to a **stream** rather
than to disk (`a notice is written to the error stream`); a **reported** clause whose subject
is a document and whose write belongs to another AC (`the reference states that a notice … is
written`); a **relative clause naming a location** (`names the file suppressions are written
in`); and an ordinary **authoring verb** (`before any test is written`). Five false positives
across three mechanisms surfaced in a single day's work, which is the strongest available
argument that a keyword matcher over natural language will keep finding new ways to be wrong —
and that the fix worth investing in is the one this entry already prescribes: make
`validate_declares_side_effect` unable to leave an author with no acceptable value.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M8 (a check measuring a proxy and
reporting it as a verdict) — the proxy is "does the Then clause contain a write phrase", the
verdict claimed is "this AC has a durable side effect", and negation is the gap between them.

---

### KI-CG-016 — `enforce_commit_delegation` matches the phrase anywhere in the command string, so read-only commands that merely mention committing are blocked

- **Severity:** low
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** the `enforce_commit_delegation` PreToolUse hook, matching against the whole Bash command string rather than the resolved program and its subcommand

**Symptom.** Any Bash command whose text contains the phrase is refused with the full
delegation error, regardless of what the command actually does. Searching for the phrase,
printing it, or reading a file about it are all blocked.

**Evidence.** Two pure reads, both refused on 2026-08-25 with
*"direct git commit is not allowed … COMMIT_AGENT_MODE is not set to '1'"*:

```
grep -c "git commit" CLAUDE.md
grep -n "git add\|add -A\|stageAll\|git commit" templates/workflows-js/fast-lane-ship.js
```

Neither invokes git. The first counts lines in a Markdown file. The second was an audit of the
fast lane's staging behaviour — the work that produced `KI-BO-029` — and the block is what
forced that audit to be re-run with the phrase removed from the pattern.

**Why it is low.** It is loud, immediate and trivially worked around by rephrasing the search.
Nothing is silently wrong; the cost is a wasted call and a detour.

**Why it is worth filing anyway.** The affected commands are disproportionately the ones that
*audit commit behaviour* — greps over hook code, workflow staging steps, and this register's own
prose. A guardrail that obstructs inspection of itself raises the cost of the reviews most
likely to find its own defects. `CLAUDE.md` and several agent templates contain the phrase in
prose, so any grep across them is affected.

**The converse is the open question, and is NOT claimed here.** A matcher keyed on a substring
of the raw command is in principle both over-inclusive (this entry) and potentially
under-inclusive against spellings that do not contain the literal phrase. Only the
over-inclusive half was observed. Deliberately not probed — attempting to slip a real commit
past a safety hook is not an appropriate way to characterise it. Flagged for the owner to
settle by reading the matcher, not by experiment.

**Fix direction.** Match on the parsed invocation — program resolves to `git` and the
subcommand is `commit` — rather than on a substring of the command text. Failing that, exclude
commands whose program is a known read-only tool (`grep`, `rg`, `cat`, `less`, `echo`).

**Numbering.** A concurrent session minted `KI-CG-016` for a different defect on the same
day and renumbered its own entry to `KI-CG-017` before merge, leaving `016` to this one — see
that entry's own note. This is `KI-BO-024`'s id-collision shape again, resolved cooperatively
rather than by any check.

---

### KI-CG-018 — `check_ac_governance` exits 0 without inspecting anything, and its own "did I look?" diagnostic cannot fire on the paths where it did not

- **Severity:** high
- **Status:** open
- **Occurrences:** 2
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/scripts/commit_guardian/check_ac_governance.py:631-642` — `main()`

**Symptom.** The hook returns `0` having read no file, with no output on stdout or stderr,
and is indistinguishable at the call site from a run that checked every staged record and
found nothing wrong.

**Root cause — the diagnostic is downstream of the silent exits.** `main()` has two early
returns, and the introspection counter that exists to prove the hook did work sits *after*
both of them:

```python
631    if not ac_store.is_dir():
632        # No AC store — exit 0 immediately without creating any directories
633        return 0
634
635    # Get staged AC YAML files
636    staged_paths = _get_staged_ac_paths()
637    if not staged_paths:
638        return 0  # No AC files staged — nothing to check
639
640    # Emit parsed file count to stderr for test introspection (AC-13)
641    if os.environ.get("HOOK_COUNT_PARSED"):
642        print(f"{_HOOK_PREFIX} parsed_files: {len(staged_paths)}", file=sys.stderr)
```

`HOOK_COUNT_PARSED` was added so a caller could confirm the hook saw its files. It is
unreachable on precisely the two paths where it saw none. Setting it and getting silence is
therefore ambiguous between "the variable is unset", "the hook is old", and "the hook
checked nothing" — and only the third is true.

Line 631 is reached with `ac_store` wrong whenever `_find_project_root()` resolves above the
AC store. In the ADR-001 self-hosting layout the workspace parent carries a `CLAUDE.md` but
no `docs/acceptance-criteria/`, so a run whose working directory is the workspace parent
takes the 633 exit every time. Not intermittent.

**Evidence.** Both observed on 2026-08-25 while authoring `ACD-2100`, by two agents
independently, on a worktree that did contain 31 staged AC records:

```
$ HOOK_COUNT_PARSED=1 HOOK_TEST_FILES=<relative path to a real staged AC> \
    python <worktree>/.leafcutter/scripts/commit_guardian/check_ac_governance.py
(no output at all)
exit: 0

$ env --chdir=<worktree> HOOK_COUNT_PARSED=1 HOOK_TEST_FILES=<same path> \
    python <worktree>/.leafcutter/scripts/commit_guardian/check_ac_governance.py
[check-ac-governance] parsed_files: 1
exit: 0
```

Same hook, same file, same exit code; only the working directory differs, and only the
second run inspected anything.

**Compounding: `argv` is ignored.** `_get_staged_ac_paths()` (`:285`) reads `git diff
--cached` or `HOOK_TEST_FILES`. Passing paths on the command line does not make the hook
check them, so a caller who verifies the hook by invoking it with a path gets a pass that
means nothing. This is the same shape already recorded for the other AC hooks — silence is
not a pass, and neither is exit 0 with an argument the hook never read.

**Why this is worse than a crash.** In pre-commit the working directory is the repository
root, so the gate does run there — its practical blast radius is ad-hoc verification, agent
self-checks, and any CI step that invokes it from elsewhere. Those are exactly the callers
who would report "governance passes" on the strength of an exit code.

**Fix direction.** Three separable changes, in order of value:

- Emit the `HOOK_COUNT_PARSED` diagnostic (or an unconditional one-line summary naming the
  resolved root and the file count) **before** the early returns, so a run that checked
  nothing says so. A check that cannot report what it looked at should not be able to
  report success.
- Distinguish "no AC store found at `<resolved root>`" from "AC store found, nothing
  staged". Both are legitimately exit 0; they are not the same fact.
- Resolve the root the way the guardian hooks that already handle this layout do —
  `_resolve_root.py` exists for it. Falling back to a bare relative `_AC_STORE_DIR` when
  `_find_project_root()` returns `None` (`:627`) is what makes the failure depend on cwd.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M8, and a variant worth naming
separately: the *instrumentation* meant to defeat M8 placed where the M8 path cannot reach
it.

---

### KI-CG-019 — the `templates/` copy of `check_ac_parent_covered_by` fail-opens on an import it can never satisfy, so verifying from `templates/` always passes

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/scripts/commit_guardian/check_ac_parent_covered_by.py` — the
  `derive_parent_id` import guard

**Symptom.** Run from `templates/`, the hook prints a warning and exits 0 without checking
anything:

```
$ HOOK_ROOT=<worktree> HOOK_TEST_FILES=<a real AC record> \
    python <worktree>/templates/scripts/commit_guardian/check_ac_parent_covered_by.py
[check-ac-parent-covered-by] WARNING: cannot import derive_parent_id: ac_parent_id.py not
found via package import, script-relative, or project-root walk.; skipping check (fail-open)
exit: 0
```

The deployed copy under `.leafcutter/scripts/commit_guardian/` imports cleanly and runs.

**Root cause.** `ac_parent_id.py` lives in `scripts/ac_store/` and is placed next to the
hook only by `build.py`. In `templates/` that sibling does not exist, and none of the three
resolution strategies can find it — so the condition is not an environment accident but a
permanent property of that copy. The failure is guaranteed, and the response to a guaranteed
failure is to pass.

**Why it matters.** It is louder than `KI-CG-018` — it does print a warning — but it lands in
the same trap: anyone verifying AC parent back-links by running the hook out of `templates/`
gets exit 0 and a clean-looking result. That is a natural thing to do, because `templates/`
is where the source of truth for the hook lives and where an author editing it is already
working. The hook that exists to catch a stale `covered_by` is the one that silently
abstains.

Found while verifying `ACD-2100e`: a business-analyst hit the fail-open, noticed the warning,
re-ran the deployed copy, and additionally corroborated the invariant by reading the parent's
`covered_by` directly rather than trusting either exit code.

**Fix direction.** Fail **closed** when the import cannot be satisfied and the hook was given
files to check — the check exists to be blocking, and a blocking check that cannot load its
own dependency has not passed. If the `templates/` copy is genuinely not meant to be
executable in place, make it say that explicitly ("this copy is a build source; run the
deployed hook") and exit non-zero, rather than emitting a warning shaped like a skip.

Related: the deployed hook has no `parsed_files`-style diagnostic at all, so even a correct
run cannot state what it inspected. Adding one alongside the `KI-CG-018` fix would make both
hooks answerable to the same question.

---

### KI-CG-020 — hook registration has a fourth leg nobody documents: a hook absent from `blocking_hook_ids` is skipped by the autofix loop

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/scripts/precommit-autofix.json` `blocking_hook_ids`;
  `templates/skills/precommit-autofix/SKILL.md` Step 4; `templates/skills/create-hook/SKILL.md`

**Symptom.** A hook can be correctly registered by every documented step — script written,
config key added, `hooks_manifest` entry added, row added to the hook documentation index —
and still be ignored by the autofix loop, because a **fourth** registration surface exists
that the `create-hook` procedure does not mention.

`templates/scripts/precommit-autofix.json` carries a closed allowlist:

```json
"blocking_hook_ids": [
  "check-complexity",
  "check-docstrings",
  "check-exception-handling",
  "check-file-size",
  "check-ac-schema",
  "check-ac-limits",
  "check-contract-shrinking"
]
```

`precommit-autofix/SKILL.md` Step 4 is explicit about the consequence: if a failing hook
does not appear in `blocking_hook_ids`, *"the hook is non-gating — skip it entirely, do not
dispatch any fixer."*

**Why this is a registration gap rather than a configuration choice.** The allowlist is a
reasonable design — not every hook should have a fixer dispatched at it. The defect is that
it is a **fourth leg of registration documented nowhere in the procedure that exists to
enumerate the legs.** `create-hook` codifies three-way registration (script + guardian
config + doc index) and `check_hook_parity` enforces consistency across those three. Neither
knows this file exists. So the natural failure is silent: an author follows the documented
procedure completely, `check_hook_parity` passes, and the hook lands outside the loop with
nothing reporting the omission.

**Evidence.** Found on 2026-08-25 while reviewing `BP-1100b-5`, an approved AC specifying a
new staged-hunk commit-guardian hook (`check_presence_only_assertions.py`). Its
`it_requirements` spell out three-way registration in detail — including an explicit
`n_location_rule: "2"` constraint warning that a config key without a `hooks_manifest` entry
"is a no-op that reads as shipped". Neither that record's `it_requirements`, `constraints`
nor `doc_links` mentions `precommit-autofix.json`. As specified, the AC ships a gate the
autofix loop is configured to ignore — and the record's own coverage would not catch it,
because all twelve of its test descriptors exercise the hook directly.

The irony is worth recording: `BP-1100b-5` exists to stop tests that look like proof but
are not, and it carries a registration spec that looks complete but is not, for the same
structural reason — an enumeration everyone trusts that is missing an item.

**Scope.** The 7 hooks on the allowlist are unaffected. The exposure is every hook added
since the allowlist was closed and every hook added from here, and the symptom is not a
failure but a *reduced* one: the hook still blocks the commit, it simply gets no autofix
attempt, so the effect is friction rather than a false pass. That is why this is `medium`
and not `high` — but it is the kind of gap that is only ever noticed by someone reading the
autofix config for an unrelated reason.

**Fix direction.**

- Add the fourth leg to `create-hook`'s procedure, with the decision made explicit: every
  new hook is either added to `blocking_hook_ids` or is deliberately non-gating, and the
  author records which. An omission by default is the current behaviour and is the thing to
  remove.
- Extend `check_hook_parity` to cover it, so a hook present in `hooks_manifest` and absent
  from `blocking_hook_ids` is reported — as a warning naming the deliberate-exclusion route,
  not as a hard failure, since exclusion is legitimate.
- Amend `BP-1100b-5` when it is built, or accept the gap knowingly for that hook.

---

### KI-CG-017 — `check-build-drift` is filtered on the consumer layout path, so it has never run on this repo's own template changes

> **Minted as `KI-CG-016`, renumbered to `017` before merge.** A concurrent session claimed
> `KI-CG-016` for a different defect (the delegation hook substring-matching command text) in a
> PR authored at the same time. Renumbered here rather than there because that PR's description
> was already written around `016`, and because filing a duplicate in the same commit that flags
> the `KI-CG-012` duplicate would be self-defeating. Both numbers are free on `origin/main` at
> the time of writing; if the other PR lands as something else, this entry keeps `017` regardless
> — the number is arbitrary, the collision is not.

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

---

### KI-CG-032 — The uniqueness pass's YAML fast path fabricates an id claim for records a full parse rejects

> **Renumbered 2026-08-26: filed as `KI-CG-016` in PR #575, now `KI-CG-032`.** That number was
> already taken on `origin/main` by the `enforce_commit_delegation` entry above. The id was
> allocated by grepping a stale checkout and taking the max, and that copy stopped at
> `KI-CG-014` — `015`-`020` were already landed. The original `KI-CG-016` keeps its number: it
> was there first and is cited from `changelogs/2026-08-25-2312-*.md`. This entry is hours old
> and had exactly one inbound citation, repointed in the same commit.
>
> This is the fourth id collision in this register in two days and the second caused by
> allocating against a snapshot — the defect `KI-BO-028` describes, committed in the register
> that documents it.

- **Severity:** medium
- **Status:** open — **the code is not on `main`**; it lives on unmerged PR #495, branch
  `feat/ge-122-integrity-guard`. Recorded here so it is not lost when that branch is picked up.
- **Occurrences:** 1
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `templates/scripts/commit_guardian/_uniqueness_scanners.py:396-487` —
  `_fast_scan_top_level_id()`, against `_read_yaml_id()`'s contract

**Symptom.** `_read_yaml_id`'s contract is that an unparsable record yields **no** claim. The
fast path validates only the `id:` line and its immediate successor, and the caller falls back
to the full parse **only when the fast path returns `None`** — so a wrong non-`None` answer is
never corrected. Any YAML syntax error *after* the `id:` line produces a fabricated claim.

**Reproduced end-to-end** with the most realistic shape, an unquoted value containing a colon:

```yaml
id: GE-500
title: Fix: the parser      # -> yaml.ScannerError
```

`scan_acceptance_criteria` returns `passed=False` with the finding
`GE-500 claimed by [a_malformed.yaml, b_legit.yaml]`. Under the contract there is exactly one
claimant and no collision at all. **The author is blocked with a duplicate-id message when the
real fault is a YAML syntax error somewhere else** — so the diagnostic points at the wrong file
and the wrong problem. A fuzz comparison of the two paths diverged on 6 of 24 inputs; the others
were `- foo` after a mapping, tab indentation, an unclosed flow sequence, an undefined alias,
and `...\t` / `....` as a last line.

**Latent today, and the reason it is latent is itself the concern.** Audited against all 3,097
real AC files: **zero divergences**. But 3,096 of the 3,097 are answered by the fast path — the
full-parse safety net runs exactly once across the entire store. The fallback is not a
meaningful second opinion; it is unreachable in practice.

**Do not fix this with another token special-case.** Rounds 4, 5 and 6 of this PR's review each
added one, and rounds 4-6 each introduced the defect the next round found. The two durable
options are: have the fast path bail whenever any non-blank line it did not positively classify
appears after the `id:` line, or accept the divergence deliberately and re-scope the documented
contract so callers stop being promised a guarantee the fast path does not provide.

**Confirmed NOT broken, so nobody re-opens it:** the document-end token `...` is handled
correctly — lone trailing, with a trailing space, with a trailing comment, and with no trailing
newline all agree with the full parse. That round-6 fix is sound.

*Minor, same file:* `_is_document_boundary_token:311` hardcodes `raw_line[3]` and
`len(raw_line) > 3` rather than deriving from `len(token)`. Correct only because both tokens
happen to be three characters.

**Pattern:** an optimisation whose fallback is the correctness guarantee, and which answers
often enough that the fallback never runs.

---

### KI-CG-033 — Placeholder marker detection flags markdown emphasis as a list bullet, and its false-positive cost was measured on one marker and claimed for all six

> **Renumbered 2026-08-26: filed as `KI-CG-017` in PR #575, now `KI-CG-033`.** Same cause as
> `KI-CG-032` above — allocated against a stale snapshot that stopped at `KI-CG-014`. The
> original `KI-CG-017` (`check-build-drift` filtered on the consumer layout path) keeps its
> number: it was there first and is cited from three `GE-126` acceptance criteria
> (`GE-126d-1`, `GE-126e-2-i`, `GE-126e`), all of which mean the `check-build-drift` entry and
> are correct as written. This entry's one inbound citation is repointed in the same commit.

- **Severity:** medium
- **Status:** open — **the code is not on `main`**; it lives on unmerged PR #495, branch
  `feat/ge-122-integrity-guard`. `main` still has only the narrow `\bFIXME\s*:` form and none
  of the widening described below.
- **Occurrences:** 1
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `scripts/build_placeholder_detection.py:114` (`_LEADING_BULLET_REQUIRED`) and
  `:87` (`_LEADING_MARKER_PREFIX`), plus the claims in the comments at `:98` and `:231`

**Two defects. The second is worse than the first.**

**(a) The bullet requirement accepts a bullet *character*, not a list bullet.** The pattern
`r"^\s*(?:[-*+]|\d+[.)])\s*"` matches markdown emphasis and ordered prose:

| Line | Result |
|---|---|
| `*Placeholder* text is shown when empty.` | **flagged** — false positive |
| `**Placeholder** text is shown when empty.` | not flagged — the `\s*` cannot span the second `*` |
| `3. Placeholder naming follows the house style.` | **flagged** — false positive |

Note the italic/bold inconsistency: the same sentence is flagged or not depending on emphasis
style, which is the tell that the rule is matching punctuation rather than structure.

**(b) The recorded claim that these markers carry no false-positive cost is wrong, and wrong in
a specific way worth naming.** The comments state there is "no repo-wide evidence of a
false-positive cost" for `TODO` / `FIXME` / `Replace with`. A repo-wide scan of 5,063 md/yaml
files returns **55 hits**, of which **14** survive purely on the optional-bullet rule
(indentation only, no bullet). Nearly all are plainly false:

```
docs/ticket-lifecycle.md:11,15,19              todo --> in_progress: ...   (Mermaid state transitions)
templates/skills/roadmap-query/SKILL.md:54,58  todo: 1 / todo: 2           (a count field)
templates/skills/signoff/SKILL.md:110,119      Replace with:
ACD-400a-4.yaml:15, BP-900h-4-i.yaml:238,      wrapped prose: "todo -> in_progress -> done"
TKT-500c-6.yaml:16, UXP-411.yaml:28
```

Marker distribution across those 55: **`todo` 42, `<!-- question:` 8, `replace with` 3,
`placeholder` 2.**

**The measurement error, stated plainly, because it is the reusable lesson.** The false-positive
cost was measured for `PLACEHOLDER` only and then asserted for all six markers. `PLACEHOLDER`
accounts for 2 of the 55 hits. So the tightening landed on the marker responsible for 2 and left
untouched the marker responsible for 42. A prior round of the same work made the same shape of
error — a widening measured with a grep that shared the widening's blind spot, reported as "one
instance" when the true cost was 23 false positives across 4,815 files.

**Fix direction.** Require a bullet **followed by whitespace** so emphasis cannot satisfy it, and
decide the ordered-list case deliberately rather than by regex accident. Then re-run the
repo-wide measurement per marker — not in aggregate — before restating any zero-cost claim, and
record the per-marker counts next to the rule so the next person tightening it can see which
marker actually costs anything.

**Pattern:** a claim generalised from the one case that was measured, in a change whose whole
purpose was to bound false positives.

---

> **Entries `KI-CG-021` … `KI-CG-031` are recovered from an unmerged branch.** They were
> written between 2026-08-19 and 2026-08-25 while driving
> `EPIC-GE122UniquenessPassAndRepair`, into a parallel known-issues register that PR #495
> invented with its own id scheme (`KI-CG-9`, `KI-CG-12`, …). That register lost every
> reconciliation conflict against this file and was discarded; a pairwise comparison then
> found the two are disjoint in subject matter, so the analysis below would have been lost
> with the branch. Every entry was re-verified against `main` at `37655862` before being
> filed, and each `Status` line states plainly whether the code it describes is on `main`
> or only on the unmerged branch. Two entries from that set were **dropped** as no longer
> true and are deliberately absent: one about `origin/main`-staleness in
> `test_ge_122e_1.py` (fixed 2026-08-18, the assertion is now a one-directional id-set
> difference) and one about agent cards failing `check-doc-frontmatter` (fixed — `card` is
> now a valid `config/doc_types.json` type and the cards validate clean).

---

### KI-CG-021 — The whole-collection uniqueness pass is registered in no hook config and no CI workflow, and has never run

- **Severity:** blocker
- **Status:** open — **the code is NOT on `main`**; `check_identifier_uniqueness.py` and its
  four scanners live only on the unmerged PR #495 (`feat/ge-122-integrity-guard`). Filed
  here because it is the gating precondition on landing that branch: the merge must not be
  taken as "the gate now exists".
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** PR #495's `templates/scripts/commit_guardian/check_identifier_uniqueness.py`;
  `templates/scripts/commit_guardian/commit_guardian.json`; `.pre-commit-config.yaml`

**Symptom.** Found in review round six, by the first reviewer to test the gate *as deployed*
rather than by invoking it from the source tree. Nothing invokes it:

```
grep "check_identifier_uniqueness" templates/scripts/commit_guardian/commit_guardian.json  -> 0
grep "check_identifier_uniqueness" .pre-commit-config.yaml                                 -> 0
grep -rl across every .json / .yaml / .yml / .js / .toml in the repo
    -> docs/acceptance-criteria/.../GE-122a-1.yaml   (the AC that specifies it)
    -> tickets/.../.pending/adr_handoff.json         (a pending handoff)
       nothing else
```

No pre-commit hook invokes it. No CI workflow invokes it. The one registered hook with a
similar name, `check-decision-number-uniqueness`, runs a **different** script
(`check_adr_collision.py`) — and see `KI-CG-022`: that registration itself exists only on
the branch.

**Root cause.** Six review rounds and five fix commits hardened a `main()` that no runner
calls. The commit immediately before the discovery is titled *"the fail-closed contract was
never wired to the exit code"* — and nothing reads that exit code.

The epic's own `Master_Plan.md` named this outcome in advance:

> The trap this epic is most likely to fall into: **a guard that is built, tested green, and
> registered nowhere.**

and its Success Criteria require *"one whole-collection uniqueness pass, **registered in
`commit_guardian.json`** and reachable through its production entry point — not a second
inert detector."* **That criterion is not met.** The epic was commissioned because three
whole-collection detectors were already registered nowhere. It produced a fourth.

**Why nothing caught it.** Every round verified behaviour by importing the module or running
the script directly. Not one asked what invokes it in production. Each round's verification
was accurate and none of them addressed the question. This register's recurring lesson — *a
signal computed correctly and then not consumed* — applied to the entire component, and the
reviews inherited the blind spot from the thing they were reviewing. Generalised as
`KI-TQ-007` in the testing-quality register.

**Fix direction.** **Do not register it in the same change that ships it.** See
`KI-BO-030` — doing so today makes the package uninstallable. Required order: scaffold the
missing namespace roots, **then** register, **then** re-run the deployed-consumer test.

**Pattern:** `docs/reference/false-green-mechanisms.md` — a gate whose reachability was
never asked about; verification that stops at the function and never reaches the entry point.

---

### KI-CG-022 — `check_adr_collision.py` exists but is registered nowhere, and the branch that registers it also makes it fail closed without `origin/main`

- **Severity:** medium — **downgraded from the high recorded on the branch, because the
  claim it rested on is false for `main`** (see Evidence)
- **Status:** open — the *script* is on `main` and has been since the initial commit; the
  *registration* and the *fail-closed behaviour* are **not** on `main` and live only on
  unmerged PR #495. The defect is therefore latent on `main` and becomes live the moment
  that branch lands.
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-26 (re-verified against `37655862`)
- **Where:** `templates/scripts/commit_guardian/check_adr_collision.py:81-101`
  (`get_committed_adr_numbers`); `templates/scripts/commit_guardian/commit_guardian.json`

**Symptom (as observed on the branch).** The hook reads the decision-number sequence from
`origin/main` and fails closed when that ref does not exist:

```
[check_adr_collision] BLOCKED -- could not read the decision-number sequence:
  could not read the decision sequence on 'origin/main' (git ls-tree exited 128):
  fatal: Not a valid object name origin/main
[check_adr_collision] Uniqueness was not established, so this commit cannot proceed.
```

A `git init` repository has no `origin/main`. Every ADR-touching commit in any repo that is
not a clone with a `main` branch is blocked. Found while building a fresh consumer install
to test `KI-CG-021`.

**Evidence — the branch entry's own framing was wrong, and this is the correction.** The
branch recorded this as *"This hook IS registered and required … live on `main` today — not
introduced by this epic."* Both halves are false for `main`, verified directly at
`37655862`:

- **Not registered.** `grep -n 'check_adr_collision\|check-decision-number-uniqueness'
  templates/scripts/commit_guardian/commit_guardian.json` returns **nothing**, across all 55
  registered hooks. A repo-wide grep over `.json` / `.yaml` / `.yml` / `.py` / `.js` /
  `.toml` finds the name only in the script itself, `config/package_boundary.json`,
  `scripts/adr_refs.py`, and seven GE-12x AC records. No `.pre-commit-config.yaml` entry
  either. `git log -- templates/scripts/commit_guardian/check_adr_collision.py` shows the
  file present since `11dbd26b` (initial commit) and never registered since.
- **Not fail-closed.** `main`'s copy fails **open**. Its docstring states
  *"Empty on any error"* and the body is literally `if rc != 0: return set()`
  (`check_adr_collision.py:93-94`). The `BLOCKED -- could not read the decision-number
  sequence` string appears **nowhere** in the repository.

So the branch registered the hook (as `check-decision-number-uniqueness`) *and* converted it
from fail-open to fail-closed, then observed the consequence and recorded it as pre-existing.
It was neither.

**Why this matters more, not less.** `main` today has the opposite defect: a decision-number
collision detector that has never run in the package's entire history, silently returning an
empty set on any git error even where it *is* invoked by hand. And the branch's two changes
compose into the fresh-install blocker above. Landing PR #495 without addressing this ships
that blocker.

**Fix direction.** Treat as one change with three parts: register the hook; keep it fail-closed
(fail-open is what let it hide for months); and make an absent `origin/main` a *distinguishable*
condition — resolve the first ref that exists from `origin/main`, `main`, `HEAD` and only block
when none resolves, matching the `_resolve_first_ref` pattern
`unit_tests/commit_guardian/test_ge_122e_1.py:504` already uses for exactly this reason.

**Pattern:** an entry that mis-states which tree its evidence came from. Verification run on a
branch, recorded as a property of `main`.

---

### KI-CG-023 — `check-predone-scope` cannot distinguish a ticket's subject from its driver, and reconciles branch-wide rather than commit-wide

- **Severity:** medium
- **Status:** open — code is on `main` and live, but **advisory by default**
  (`files_touched_reconciliation.strict: false`), which is what keeps this at medium rather
  than the blocker severity observed on the branch, where it was hit in strict mode
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-26 (re-verified against `37655862`)
- **Where:** `templates/scripts/commit_guardian/hooks/check_files_touched_reconciliation.py`
  — `_reconcile` (`all_changed = branch_diff_files | frozenset(staged_files)`, ~:451) and
  `_get_branch_diff_files` (:113-132); registered as `check-predone-scope` in
  `commit_guardian.json:589`

**Symptom.** The hook reads every modified ticket `.md` in the change set as a *governing*
ticket authorising the commit, then reports source changes as undeclared against that
ticket's `files_touched`. It has no notion of a ticket being the *subject* of a change.

This misfires on any work that repairs tickets. GE-122e-2 deleted five duplicate work items;
the hook read those five long-finished June tickets as the commit's authorisers and blocked.

**Second, compounding defect: it reconciles branch-wide, not commit-wide.** An attempt to
satisfy it by splitting the source changes into a separate commit still failed, and the error
named files that were not in the commit at all (`_commit_disposition.py`,
`_uniqueness_scanners.py`, `_work_items_scanner.py` — all from earlier commits on the
branch). No commit boundary can satisfy it.

**Evidence.** Both defects are visible in the hook's own source on `main`. Its module
docstring states it *"Computes branch diff plus staged source files"* and that *"when
multiple done tickets are staged together, reconciliation uses the UNION"* — the two
behaviours described above, documented as intent. The union is computed at
`all_changed = branch_diff_files | frozenset(staged_files)`.

**Detection.** The tell is a blocker (or advisory) naming files absent from
`git diff --staged`.

**Fix direction.** Two independent changes: (1) distinguish subject from driver, probably by
treating a ticket as governing only when the commit is authored under it; (2) reconcile
against the staged diff rather than the branch diff. Until then, `SKIP=check-predone-scope`
with the justification written into the commit message — used once on `6715e4c3`.

**Pattern:** a scope check whose population is the branch while its subject is the commit.
The same population-vs-change mismatch as `KI-CG-001`.

---

### KI-CG-024 — `check_ticket_signoff_parity.py` silently skips check #6 because its default registry path does not exist in this layout

- **Severity:** medium
- **Status:** open — code is on `main` and live
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-26 (re-verified against `37655862`)
- **Where:** `templates/scripts/commit_guardian/config.py:224-226`
  (`AGENT_REGISTRY_PATH` default) consumed by
  `templates/scripts/commit_guardian/_signoff_parity_checks.py:96-103`
  (`load_agent_registry`)

**Symptom.** The hook resolves the agent registry at
`<worktree_root>/leafcutter/config/agent_registry.json`. That path is wrong for this layout
— nothing exists there — so it emits a warning to stderr and skips check #6 entirely:

```
[check-ticket-signoff-parity] WARNING: agent registry not found at
  <worktree>/leafcutter/config/agent_registry.json; skipping check #6
```

The hook then **exits 0**. The other checks run, so the hook looks healthy; one of its checks
has simply never fired in this layout.

**Evidence.** `config.py:224` reads
`AGENT_REGISTRY_PATH = _get("ticket_signoff_parity", "agent_registry_path",
"leafcutter/config/agent_registry.json")`. The registry actually lives at
`config/agent_registry.json` (repo root), and no `ticket_signoff_parity.agent_registry_path`
override is set anywhere in `config/` or `.claude/skills_config.json`, so the wrong default
is what every run uses. `load_agent_registry` returns `{}` and its docstring names the
behaviour as intentional: *"Fail-open: returns an empty dict when the registry file is absent
or unreadable so that check #6 is skipped rather than blocking commits."*

**Detection.** Run the hook and read stderr, not just the exit code. Silence is not the same
as a pass.

**Fix direction.** Resolve the registry the way other layout-aware scripts do — derive the
root from `git rev-parse` via the sibling `_resolve_root.py` that 27 files in the same
directory already import, and support both the source-repo and deployed layouts. Correcting
the default alone is the one-line fix. Separately, consider whether an unresolvable registry
should fail closed rather than skip: fail-open was chosen so a missing registry cannot block
commits, but the cost is a check nobody knows is off.

**Pattern:** `docs/reference/false-green-mechanisms.md` — a gate that reports success while
one of its checks was never given the data it needs.

---

### KI-CG-025 — `check_ticket_state_integrity.py` retains an always-exit-0 contract that a coder cannot unilaterally retire

- **Severity:** medium
- **Status:** open — **the code is NOT on `main`**; the script lives only on unmerged
  PR #495. Filed so the constraint is not rediscovered when that branch lands.
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** PR #495's `templates/scripts/commit_guardian/check_ticket_state_integrity.py`

**Symptom.** The script documents a `Returns: Always 0` fail-open contract, so the hook
cannot block anything. GE-122a-2 widened work-item integrity checking but did **not** retire
it.

**Root cause of the stall, which is the part worth recording.** The contract is pinned by
existing tests, so a coder may not unilaterally weaken it — retiring it needs a `test-writer`
pass first to change the pinned expectations. That ordering constraint is why a known
fail-open survived a change that touched the same file.

**Fix direction.** Sequence it as test-writer (amend the pinned expectations) → coder (retire
the contract), not the reverse. Any AC written for it must name the pinned tests explicitly,
or the coder phase will correctly refuse again.

---

### KI-CG-026 — The unattributed-collision count is computed and then discarded by `pre-commit`

- **Severity:** medium
- **Status:** open — **the producing code is NOT on `main`** (it is PR #495's
  `check_identifier_uniqueness.py`), but the **consuming** half of the defect is: no hook in
  `commit_guardian.json` sets `verbose`, so this will reproduce exactly as described the
  moment the gate is registered
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-26 (consuming half re-verified against
  `37655862`)
- **Where:** PR #495's `check_identifier_uniqueness.py` operator message;
  `templates/scripts/commit_guardian/commit_guardian.json` (the generated `pre-commit` config)

**Symptom.** GE-122a-1-i requires a visible count of reported-but-unattributed collisions, on
the stated grounds that *"a visible count is what makes the backlog shrink."* Run directly,
the gate emits it:

```
[check_identifier_uniqueness] 1 reported-but-unattributed contested number(s)
  with no claimant in the current change set (not blocking)
```

Under `pre-commit`, a **passing** hook's stdout is discarded. So on the non-blocking path —
the only path this message exists for — the operator never sees it.

**Evidence.** `grep -c verbose templates/scripts/commit_guardian/commit_guardian.json`
returns **0**. The generated config sets `verbose: true` on no hook at all, so this is not a
per-hook oversight but a property of every advisory message the hook family emits on its
passing path.

**Fix direction.** Set `verbose: true` on this hook's registration when `KI-CG-021` is
addressed. Worth a wider look while there: any other hook whose value is an advisory printed
on the passing path has the same problem today.

**Pattern:** same shape as `KI-CG-007`, one layer further out — computed correctly, then not
consumed.

---

### KI-CG-027 — `main()` derives the project root from `Path.cwd()` while the canonical resolver sits unused beside it

- **Severity:** medium
- **Status:** open — **the code is NOT on `main`**; lives only on unmerged PR #495. The
  shared resolver it should adopt (`_resolve_root.py`) **is** on `main` and is imported by 27
  sibling files.
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** PR #495's `check_identifier_uniqueness.py` `main()`; against
  `templates/scripts/commit_guardian/_resolve_root.py`

**Symptom.** Under `pre-commit` the cwd happens to be the repo root, so it works **by luck**.
From any nested directory it does not:

```
$ env --chdir=<consumer>/docs python3 .../check_identifier_uniqueness.py
BLOCKING: ... acceptance-criteria, decisions, diagrams, work-items      exit 1
```

All four namespaces unresolvable, so with the `KI-CG-007` fail-closed fix in place it
hard-blocks. Any agent or manual invocation from a subdirectory is affected.

**Fix direction.** Adopt `_resolve_root.py` (git-toplevel first). The resolver exists, is
already the convention, and is in the same directory — this is a one-import change, not a
design question.

---

### KI-CG-028 — The diagrams root is hardcoded while its sibling architecture roots are configurable

- **Severity:** medium
- **Status:** open — **the consuming code is NOT on `main`** (PR #495's
  `check_identifier_uniqueness.py`), but the **cause** is on `main` and verified: there is no
  `architecture_diagrams` key in `config/paths.json`
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-26 (re-verified against `37655862`)
- **Where:** `config/paths.json:48-51`; PR #495's `check_identifier_uniqueness.py`

**Symptom.** `config/paths.json` declares the other architecture roots and not this one:

```json
"architecture":            "docs/architecture/",
"architecture_adrs":       "docs/architecture/adrs/",
"architecture_components": "docs/architecture/components/",
```

There is **no `architecture_diagrams` key** — confirmed by direct read at lines 48-51, where
`architecture_components_optional: true` follows and the enumeration ends. The gate hardcodes
`docs/architecture/diagrams/` instead. So of the four namespaces it polices, one has a root a
consumer cannot relocate while its two immediate siblings can.

**Why it matters.** Once the gate is registered (`KI-CG-021`), a consumer that keeps diagrams
anywhere else gets a permanently unresolvable namespace, which under the `KI-CG-007`
fail-closed contract blocks every commit with no configuration escape.

**Fix direction.** Add `architecture_diagrams` to `paths.json` and read the root from it,
mirroring how `architecture_adrs` is already consumed — **non-optional**, since the gate hard-
requires the root to exist. Fold this into the scaffolding work (`KI-BO-030`): the same change
decides where the directory lives and how the gate finds it, and splitting them invites the two
answers to diverge. `docs/reference/architecture-docs-layout.md` is the design note for this.

**Context for whoever picks this up.** `docs/architecture/diagrams/` currently holds 24 files:
13 match the `c{level}-{seq}` pattern the gate's numbering namespace polices, and 11 do not.
Those 11 are a **binding, permanent exemption** recorded in `GE-122e.yaml` / `GE-122b.yaml` by
a PO gate decision of 2026-08-17 — do not renumber them.

---

### KI-CG-029 — `repair_work_item_duplicates.py` has no CLI, so a destructive repair can only be invoked from a test

- **Severity:** low
- **Status:** open — **the code is NOT on `main`**; lives only on unmerged PR #495
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** PR #495's `templates/scripts/commit_guardian/repair_work_item_duplicates.py`

**Symptom.** The module is importable only. The live repair run against the real `tickets/`
tree therefore went through a throwaway operator harness in `/tmp` rather than a supported
entry point.

**Why it was left.** Nothing in the AC's `test_spec` required a CLI, and adding untested
surface for convenience was declined — the right call under the rules in force. Recorded
because the consequence outlives the decision: a repair that can only be invoked from a test
is awkward to re-run and hard to audit, and the `/tmp` harness that actually mutated the
tickets tree is not in version control.

**Fix direction.** If the branch lands, give it a CLI *with* a test, or record explicitly that
the repair is one-shot and closed.

---

### KI-CG-030 — Staged paths with non-ASCII characters are silently unattributed

- **Severity:** low in this repository, **medium in a consumer project with non-ASCII
  filenames**
- **Status:** open — the instance is on unmerged PR #495 (`_commit_disposition.py`), but the
  **precedent it was copied from is on `main` and live**: `check_ac_schema.py` uses the same
  unsafe form at three call sites
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-26 (precedent re-verified against
  `37655862`)
- **Where:** `templates/scripts/commit_guardian/check_ac_schema.py:349`, `:396`, `:439`
  (`_get_staged_ac_paths` and siblings); PR #495's `_commit_disposition.py::_get_staged_paths`

**Symptom.** These call sites use plain `git diff --cached --name-only`, with no `-z` and no
`--no-quote-path`. Under git's default `core.quotePath=true`, a staged path containing
non-ASCII characters comes back **quote-escaped** (e.g. `"tickets/caf\303\251.md"`). That
string does not resolve to a real path, so the check silently fails to match it.

**Why the direction is bad.** For the uniqueness gate the consequence is that a collision the
current commit **did** cause is reported as *unattributed*, which by design does **not**
block. The commit proceeds. A silent miss, on the side that lets work through.

**Evidence.** Found during the first review of `GE-122a-1-i`. It is inherited from
`check_ac_schema.py::_get_staged_ac_paths`, which that AC's own `doc_links` name as its
precedent — so it is a pre-existing convention rather than something the GE-122 work
introduced. On `main` at `37655862` all three `check_ac_schema.py` call sites still use the
bare `--name-only` form.

**Why it is low here.** This repository's numbered artifacts are ASCII by convention
(`GE-122a-1.yaml`, `ADR-029-*.md`, `TICKET-*.md`). Nothing currently in the collection can
trigger it.

**Fix direction.** Use `git diff --cached --name-only -z` and split on NUL, or pass
`--no-quote-path`. **Fix both call sites together** — leaving the precedent unfixed means the
next author copies it again, which is exactly how this instance arose.

---

### KI-CG-031 — `scan_decisions` and `scan_diagrams` fail silently while their sibling scanner logs

- **Severity:** low, but it makes every misconfiguration harder to diagnose than it should be
- **Status:** open — **the code is NOT on `main`**; lives only on unmerged PR #495
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** PR #495's `_uniqueness_scanners.py` (`scan_decisions`, `scan_diagrams`) against
  `_work_items_scanner.py`

**Symptom.** When a namespace root is missing, `_work_items_scanner.py` logs:

```
[check_identifier_uniqueness] WARNING: cannot read <path>/tickets/ticket_lifecycle.json
```

`scan_decisions` and `scan_diagrams` return `passed=False` for an absent root with **no log
line at all**.

**Evidence that this costs real time.** Three failing tests were first read as "the lifecycle
config is missing" because that was the only namespace that said anything; the fixtures were
in fact missing **three** roots, and the two silent ones were only found by printing the
verdict directly. That mis-diagnosis is also recorded from the other side, as the second
instance in `KI-TQ-005`. Since the fail-closed contract now blocks the commit, an operator
hitting this sees a non-zero exit with one namespace named and two staying quiet.

**Fix direction.** Give the silent scanners the same WARNING the work-items scanner already
emits. The `unresolvable_namespaces` field added for `KI-CG-007` already carries the
information; this is only about surfacing it at the point of failure.

---

### KI-CG-20260826-1334 — RETRACTED: "a missing schema makes `check-ac-schema` fail open" — tested and disproved; the real cause is the `KI-CG-012` at line 800

> **Timestamped id** — `KI-<COMPONENT>-<YYYYMMDD>-<HHMM>`, minted at authoring time. Authored
> as `KI-CG-016`, renumbered to `KI-CG-021` when 016 was taken mid-review, then 021 was taken
> too. Sequential numbering has been abandoned for new entries in this register; see the
> convention note on `KI-BP-20260826-1331` in `build-pipeline.md`.
>
> This register is the worst affected: `KI-CG-012`, `KI-CG-016` and `KI-CG-017` each currently
> resolve to **two unrelated defects** on `main`. Those are not renumbered here — they are
> cited elsewhere and picking a winner is the owner's call — but they are the reason a
> retracted entry landing on a live id would have been actively harmful. Before this change,
> `KI-CG-021` on `main` is an open defect ("the whole-collection uniqueness pass is registered
> in no hook config and has never run"); merging a **RETRACTED** entry onto that number would
> have told every reader the real defect had been withdrawn.

- **Severity:** n/a — retracted before merge
- **Status:** **closed — hypothesis disproved by experiment.** Kept as a record so the same
  wrong diagnosis is not filed again; the observation that prompted it is real and is logged
  as an occurrence on `KI-CG-012` (line 800).
- **First seen:** 2026-08-25 · **Retracted:** 2026-08-26

**What was originally claimed.** That `check-ac-schema`, unable to locate
`config/ac_store_schema.json`, printed a WARNING, silently downgraded to "manual field
validation", and exited 0 — a weaker check reporting as a passing one (M5).

**Why it is wrong.** A controlled A/B with `ACS-1100b-2` staged, run by an independent
reviewer:

```text
schema present  -> exit 1, catches the declares_side_effect error
schema REMOVED  -> exit 1, catches that error PLUS an id-format error
```

**The degraded mode is stricter, not weaker.** It cannot be the cause of a false pass, and the
central claim of the retracted entry is the opposite of the measured behaviour.

Two supporting claims were also wrong. The **Where** field cited root resolution via
`_resolve_root.py`; `check_ac_schema.py` never imports that module. And the fallback
explanation offered — that stale deployed validators were missing `declares_side_effect` —
cannot produce this outcome either, because the import of `validate_declares_side_effect` is
unguarded and a missing symbol would raise `ImportError` rather than skip a rule.

**The real mechanism, already filed.** `_get_staged_ac_paths` shells out `git diff --cached`
with **no `cwd=root`**, so the resolved root and the staged set can come from different
repositories. The root in the observed run, `/home/henzeh/projects/leafcutter`, contains a
`CLAUDE.md` but no `.git` — so the staged set came back empty, Phase 1 was skipped, and the
hook exited 0 having examined nothing. That is exactly `KI-CG-012` at line 800 ("reports a
clean pass on a file it never validated, because Phase 1 fails open on an empty staged set"),
and the sighting is recorded there.

**Worth keeping rather than deleting.** The WARNING line is a genuine red herring: it appears
at the moment of the false pass, names a real missing file, and points at the wrong cause. The
next person to see it will reach for the same explanation. The A/B above is the two-minute
experiment that rules it out.

**How this got filed wrong.** The WARNING and the `exit: 0` were observed in the same output
and a causal link between them was assumed rather than tested — while the actual discriminating
experiment (remove the schema, re-run) takes about a minute. The entry then asserted a `Where`
field naming a module the script does not import, which a single `grep` would have caught. It
is the same failure mode this register documents: a plausible mechanism, written up with real
evidence attached to it, where the evidence supports the *observation* and not the *diagnosis*.

**Pattern:** a correlation in one output stream promoted to a mechanism without the
experiment that would separate them.

<!-- Superseded body removed on retraction; the original text is in PR #568's history. -->

**Symptom (retained for searchability).** Running the deployed hook against 16 staged AC
records in a worktree:

```text
WARNING: config/ac_store_schema.json not found at /home/henzeh/projects/leafcutter;
         falling back to manual field validation.
exit: 0
```

The `exit: 0` is real and so is the missing file. What does not follow is that the second
caused the first — see the A/B above.

**Still true, and worth keeping from the retracted analysis.** The observed run's staged set
contained two records that `validate_declares_side_effect` errors on when called directly
(see `KI-CG-014`), and the hook passed them. CI, which builds fresh, would have failed the
required `AC store valid` check. So the local green was not merely weak — it was **wrong about
the specific change in front of it**. That remains the strongest available demonstration of
`KI-CG-012`@800's real-world cost, which is why the sighting is logged there.

Also still true: `KI-CG-018` (`check_ac_governance` exiting 0 without inspecting anything)
landed on `main` independently. With `KI-CG-012`@800 and `KI-CG-012`@380 that makes three
distinct routes to "exit 0 having checked nothing" in one hook family — which suggests the
family needs one audited "I did not actually check anything" path rather than several ad-hoc
ones. That recommendation survives the retraction; only the fourth route claimed here does not.

**Register hygiene note.** `KI-CG-012` is used twice in this file, at lines 380 and 800, for
two unrelated defects; PR #575 has since duplicated `KI-CG-016` and `KI-CG-017` the same way.
That is the collision `KI-BO-024` predicts for append-the-next-free-number under concurrent
agents, landed here three times over. Not renumbered in this change because the ids are cited
elsewhere and picking a winner is the owner's call — flagged so it is fixed deliberately rather
than by whoever notices next.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M5 (a validator that validates
nothing and reports success).

---

### KI-CG-034 — `check_output_drift` examines every output file and compares none of them: the scanner and the installer key paths in two namespaces that never intersect

- **Severity:** high
- **Status:** **resolved — and it was already resolved when this entry was filed.** See
  "Correction" immediately below before reading anything else here.
- **Occurrences:** 1
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26 (fixed by `ab9e91c41`, PR #593)
- **Where:** `scripts/commit_guardian/check_output_drift.py` — the directory scan and the
  `not in output_mappings` branch; `scripts/build_helpers.py::write_build_manifest` supplies
  the mapping it is compared against

**Correction, 2026-08-26.** This entry was filed against a worktree pinned at `18c8e10a`. PR
#593 (`ab9e91c41`, "gates that could not check stop reporting passes") had already rewritten
the scanner by then — and `ab9e91c41` is an **ancestor** of the commit that added this entry.
So the defect was fixed on `main` before the entry describing it reached `main`. Re-run
against `d0fa881c`:

```
$ python scripts/commit_guardian/check_output_drift.py ; echo "exit: $?"
exit: 0
check-output-drift: RESULT verified=466 uncomparable=5 exempt=5 gaps=0 drifted=0 missing=0 unreadable=0
```

466 files hash-compared against the manifest, zero skipped into the fail-open branch, and the
five uncomparables are declared exemptions that name their ground (`CLAUDE.md`, the glossary
seeds, `roadmap.json`, `vision.md` — write-if-absent scaffolds whose content is human-owned
from creation). `_derive_scan_dirs()` now derives the scan set from the manifest's own
`output_mappings` keys, which is precisely the fix direction recorded below.

**How this happened, since it is the more useful half.** The evidence was gathered in a
long-lived worktree and never re-checked against current `main` before landing. Everything
downstream inherited that: the severity argument, the `ACD-2100d-2` framing, the commit
message. A stale baseline does not announce itself — the run really did print 169 skips and
zero comparisons, so every check of the *evidence* passed. Only a check of the *baseline*
would have caught it. Pin the commit you measured, and re-measure on `origin/main`
immediately before you land.

**The reverse error is the one worth guarding against.** The `ACD-2100d-2` coder read this
entry, found production already correct, and refused to write a no-op edit to manufacture a
diff. That was right. An entry like this one — confident, evidenced, wrong — is exactly what
pressures an agent into "fixing" working code.

The original report follows unchanged, because the mechanism it describes was real at
`18c8e10a` and is worth keeping as a pattern.

**Symptom (as of `18c8e10a`; no longer reproducible).** The Direction-B drift guard passes on
every working copy because it never performs a comparison. Run against a freshly built
worktree at `18c8e10a`:

```
$ python scripts/commit_guardian/check_output_drift.py ; echo "exit: $?"
exit: 0
$ grep -c  "not in output_mappings" <output>   → 169
$ grep -vc "not in output_mappings" <output>   → 0
```

**169 files examined, 169 skipped, zero compared, and not one line of any other kind.** The
`grep -vc` is the load-bearing half of that evidence: it establishes that the skip branch is
not merely common but *total*. A count of skips alone would be consistent with a check that
also did some real work.

**Cause.** The scanner walks a hardcoded list of directory names and keys each result
relative to the repository root — `.claude/agents/README.md`. The installer keys every
manifest entry under the *configured output root* — `<output_root>/agents/README.md`. The two
key namespaces are disjoint, so every lookup misses and every file takes the fail-open
`not in output_mappings → INFO → continue` path.

**Why this is high rather than medium.** The severity is not the missing coverage, it is that
the missing coverage is **shaped like success**:

- An unmapped file prints an informational line and is skipped. From outside, that is
  indistinguishable from a file that was checked and found clean. The hook exits 0 either way.
- This is the fourth distinct route to "exit 0 having checked nothing" in this hook family
  (`KI-CG-012`@380, `KI-CG-012`@800, `KI-CG-019`). Unlike the other three, this one has
  **never** worked — there is no regression to point at, which is why nothing noticed.
- It is the guard that `ACD-2100d-2` is written to strengthen. An acceptance criterion built
  on the assumption that the check works, when it has never run a comparison, would be
  satisfied by an implementation that leaves it inert. *(Superseded: `ab9e91c41` landed the
  comparison, so `ACD-2100d-2` found its premise already satisfied.)*
- The registration compounds it: the hook's `files` trigger in
  `scripts/commit_guardian/commit_guardian.json` carries the same stale path prefixes, so a
  deployed file under a differently-configured output root does not match and the hook does
  not fire at all. Repairing the script alone leaves a gate that computes the right answer
  and is never invoked.

**Fix direction — implemented by `ab9e91c41` before this entry was written.** Derive both the
set of files to check and the key each is looked up under from the installer's mapping itself,
rather than from a hardcoded directory list, so a newly deployed directory is covered the day
it appears. Make the unmapped case report rather than skip — a deployed file with no mapping
entry is either a mapping defect or an untracked output, and both are findings. Cover it with
a test that asserts a run examining files while checking none of them **fails**; a test
written without that assertion passes against the defect.

`ab9e91c41` did all of that: `_derive_scan_dirs()` reads the manifest keys, the unmapped case
reports `GAP`/`EXEMPT` instead of skipping, and the `verified == 0` floor treats an empty
`output_mappings` as INDETERMINATE rather than clean. Recorded here as the shape of the fix,
not as outstanding work.

**Caution for whoever fixes this.** `_compute_output_mappings`'s docstring says it enumerates
four template directories by hand and therefore cannot see the route file. **That docstring is
stale and the claim is false** — the generated manifest contains nine `workflows-js` entries
including the deployed `plan-feature.js`. The mapping side is installer-derived and already
correct; the defect is entirely on the scan side. An agent working from the docstring during
the `ACD-2100d-2` enrichment pass reached the wrong conclusion and caught it only by running
the check. Run it; do not read it.

**Related.** `ACD-2100d-2` (written to repair this; found it already repaired). `KI-CG-019`,
`KI-CG-012` (the sibling exit-0-having-checked-nothing routes — those are still open, and
unlike this one they have regressed from working states). `KI-BP-016` (the same output-root
confusion in the build's doc-index phase).

**Pattern:** `docs/reference/false-green-mechanisms.md` → M5 (a validator that validates
nothing and reports success).

---

### KI-CG-20260826-package-surface-refuses-merge-commits — merging `origin/main` into a branch is refused as if the branch had added every registry entry landed upstream since it forked

> **First entry in this file using the date-and-slug id form.** See `build-pipeline.md` →
> "Why not the next free number", `KI-BO-024`, and
> `knowledge-management.md` → `KI-KM-20260826-id-convention-diverged-across-registers`.
> The sequential `KI-CG-NNN` entries above keep their ids.

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 2 observed (2026-08-26, PRs #601 and #577); reproducible on demand
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `templates/scripts/commit_guardian/check_package_surface_declaration.py`
  → `_new_entries()` (~:139-158)

**Symptom.** A merge commit that changes no registry at all is refused:

```text
[check-package-surface-declaration] REFUSED: this change adds a package-registry entry,
but none of the acceptance criteria it cites declares a package surface.
  templates/scripts/commit_guardian/commit_guardian.json: new entry
  '__drift_gate_exemption_registry_doc', 'check-hook-trigger-reachability',
  'check-presence-only-assertions', 'presence_only_assertion_guard', …
```

None of those entries came from the branch. `git diff origin/main -- <that file>` was **empty**
on both occasions — the registry in the index was byte-identical to `origin/main`.

**Mechanism — confirmed by reading the code, not inferred from the message.** `_new_entries()`
computes, per watched registry:

```python
staged = registry_entry_keys(parse_registry_document(_blob(repo, f":{rel_path}")), containers)
head   = registry_entry_keys(parse_registry_document(_blob(repo, f"HEAD:{rel_path}")), containers)
return sorted(staged - head)
```

During a merge, `HEAD` is still the **pre-merge tip of your own branch** — the merge commit does
not exist yet — while the index holds the **merged** content. So `staged - head` is not "what
this change adds"; it is "everything upstream added since this branch forked." The second parent
is never consulted: `MERGE_HEAD` appears **zero** times in the file.

**Reproduction (deterministic).** Using the hook's own `WATCHED_REGISTRIES`,
`parse_registry_document` and `registry_entry_keys`, with `OLD` = the branch base and
`NEW` = `origin/main`:

```text
config/agent_registry.json                          60 -> 60 keys   0 reported new
config/skill_registry.json                          42 -> 42 keys   0 reported new
config/paths.json                                   12 -> 12 keys   0 reported new
templates/scripts/commit_guardian/commit_guardian.json
                                                    85 -> 94 keys   9 reported new
```

Those nine include the exact seven the hook named when it refused the two real merges. The set
is not fixed — **it grows with every registry entry landed upstream**, so the longer a branch
lives the more entries it is accused of adding.

**Why it is easy to dismiss and therefore high, not medium.** Three of the four watched
registries reported zero, so the refusal only fires when upstream happened to touch
`commit_guardian.json`. That makes it intermittent and reads like a real finding on first
encounter. And the remedy the hook prints — *"Set `package_surface: true` on the criterion that
registers this surface"* — is actively wrong here: the branch registers no surface, so following
the advice means annotating **someone else's** already-merged AC with a claim about work you did
not do. The only paths through are `SKIP=check-package-surface-declaration` or `--no-verify`,
both of which disable the gate wholesale. Both merge commits in PRs #601 and #577 were landed
with `SKIP=`; the hook was verified beforehand to be firing on content identical to
`origin/main`, but that verification is a manual step nothing enforces, and the habit it trains
is the one this register exists to discourage.

**Fix direction.**

1. **Consult both parents when a merge is in progress.** When `.git/MERGE_HEAD` exists, a key is
   new only if it is absent from **both** `HEAD:<path>` and `MERGE_HEAD:<path>`. That is the
   whole fix, and it preserves the real obligation: an entry genuinely introduced by the branch
   is absent from both parents and is still caught. Octopus merges have several `MERGE_HEAD`
   lines — read them all rather than the first.
2. **Prefer the merge base over the first parent** if a general form is wanted:
   `staged - keys(merge_base)` restricted to keys not present in any parent. Equivalent for the
   two-parent case, and it also covers rebase and cherry-pick states.
3. **Do not fix this by exempting merge commits entirely.** A merge is a legitimate place to
   introduce a registry entry — conflict resolution can add one — and skipping the check there
   would open exactly the hole the hook exists to close.

**Related.** `KI-CG-20260826-1612` — **same hook, different and independent defect**, filed the
same day by another session. That entry reports `check_package_surface_declaration` among the
hooks whose `--diff-filter=AM` makes a staged *rename* invisible; this entry reports its
baseline being wrong on a merge. They do not overlap and neither fix addresses the other:
`--diff-filter` decides *which paths* the hook sees, `HEAD` vs `MERGE_HEAD` decides *what it
compares them against*. Both are worth fixing in one pass, since both live in the same twenty
lines of git plumbing. `KI-CG-012`, `KI-CG-019` (sibling checks that reach a verdict from an
incomplete read of git state). `KI-BP-20260826-1331` (the same class of wrong-baseline
comparison, there against the deployed tree rather than against `HEAD`).

**Pattern:** a check that treats `HEAD` as "the state before this change" — true for an ordinary
commit, false for every merge.

---

### KI-CG-20260826-1612 — Every AC guardian filters the index on `--diff-filter=AM`, so a *renamed* AC record is invisible to all six — and renaming is exactly what a tree split requires

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `templates/scripts/commit_guardian/check_ac_parent_covered_by.py:150`,
  `check_ac_limits.py:354`, `check_ac_schema.py`, `check_ac_governance.py`,
  `check_ac_circular_deps.py`, `check_ac_pattern_refs.py` — all six read
  `git diff --cached --name-only --diff-filter=AM`. Nine further guardian hooks
  (`transform_*`, `check_package_surface_declaration`, `check_surface_components_e2/e3`)
  use the same filter and are likely affected the same way.

**The mechanism.** `--diff-filter=AM` selects **A**dded and **M**odified paths. A rename is
status **R**, so a staged rename is silently absent from every one of these hooks' file lists.
The record is fully staged — `git status` shows it, the commit will contain it — and the gate
that exists to validate it never receives its path.

**Why this is worse than it sounds.** The `ac-tree-split` skill *mandates* renaming. Pattern C
step 6a: "Rename the file to reflect the new parent prefix … the old filename must no longer
exist," because `check_ac_limits.py` attributes a child to its parent by deriving the parent
from the child's **ID string** (GE-106), so a moved child that kept its prefix still counts
against the old parent. The skill is right that the rename is unavoidable. The consequence is
that **the single operation most likely to break parent/child back-links produces a commit in
which the back-link gate cannot see any of the moved records.**

**Evidence — controlled A/B, same store state, same hook, one variable.** Splitting `BP-100k`
into `BP-100k` + `BP-100n` moved three L2s (`BP-100k-6/-7/-8` → `BP-100n-1/-2/-3`).
`BP-100n-1` was then deliberately removed from `BP-100n`'s `covered_by` — a real violation of
exactly what this hook enforces:

| how the hook was invoked | result |
|---|---|
| via the git index, children staged as `R` | **exit 0**, no output |
| via `HOOK_TEST_FILES`, same broken store | **exit 1**, `BLOCKED — child AC 'BP-100n-1' is staged but parent AC 'BP-100n' does not include 'BP-100n-1' in its covered_by field` |

The hook is not lenient about renames; it is blind to them. Confirmed the filter is the cause:
`git diff --cached --name-only --diff-filter=AM` listed 4 of the 7 staged AC records, and
`--diff-filter=R` listed the 3 missing ones.

**Why the split that found it is nonetheless verified.** Rename detection was disabled locally
(`git config diff.renames false`), which makes git report the moves as Add + Delete so the `AM`
filter includes them; all six gates were then re-run and passed with the moved children genuinely
inspected. That is the workaround, and it is also the shape of the fix.

**Blast radius beyond tree splits.** Any AC record that is renamed — a corrected ID, a record
moved between feature folders, a Pattern A/C split — passes all six required AC gates unexamined.
`check_ac_limits` partially escapes only by accident: it keys on the *parent* being staged, and in
a split the parents are `M`/`A`. Change a child's ID without touching either parent and it is blind
too.

**Suggested fix.** Add `R` to the filter (`--diff-filter=AMR`) in the shared staged-path helpers.
For a rename, git's `--name-only` reports the destination path, which is the one that should be
validated. Worth doing in one pass across the family rather than per hook, since all fifteen
copies of this line drifted from a common ancestor.

**Relationship to `KI-CG-001`.** Adjacent but distinct, and both should stay. `KI-CG-001` is
"the file was never staged, so the hook never saw it". This is "the file **was** staged and the
hook still never saw it". The first is fixed by staging discipline — the standing
"stage the parent alongside the child" rule in `CLAUDE.md`. That rule does **not** help here:
you can stage every file involved, correctly, and the gate still reports a clean pass.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M5 (a validator that validates
nothing and reports success).

---

### KI-CG-20260831-0713 — `check-hook-trigger-reachability` blocks EVERY commit in a consumer project that tracks no Python

- **Severity:** blocker
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** `templates/scripts/commit_guardian/commit_guardian.json:1082-1093` (the gate's
  own manifest entry), `templates/scripts/commit_guardian/check_hook_trigger_reachability.py`,
  and `hook_trigger_reachability_exemption_registry` in the same config

**The defect.** The gate shipped by `BP-100k-4` is `always_run: true`, `pass_filenames: false`,
and exits non-zero when any registered hook's `files` pattern matches no tracked path. It is
rendered into every consumer's `.pre-commit-config.yaml` — `_render_hook_yaml` in
`scripts/build_precommit.py` iterates the whole `hooks_manifest` with no tier filtering and no
opt-out. Two registered hooks trigger on `files: '\.py$'`: `check-placeholder-defaults` and
`check-exception-handling`. **A consumer project containing no Python therefore cannot make a
commit at all.**

**Evidence — reproduced independently, twice, against the real registry.**
Synthetic consumer repos, gate executed as a process with cwd inside the probe:

| probe | result |
|---|---|
| Fresh TypeScript consumer (`src/index.ts`, `README.md`, `.gitignore`) | `exit 1` · `RESULT total=52 unreachable=27 exempt=9` |
| **Fully-onboarded** consumer — adds `docs/*.md`, `docs/components.json`, `docs/roadmap.json`, `docs/acceptance-criteria/*.yaml`, `tickets/*.md`, `docs/product-truth/*.json` | **still `exit 1`** · `RESULT total=52 unreachable=2 exempt=9` |

The onboarded residue is exactly the two language-shaped triggers:

```
UNREACHABLE: check-placeholder-defaults reason=files pattern '\.py$' matches none of the 9 path(s) this repository tracks
UNREACHABLE: check-exception-handling   reason=files pattern '\.py$' matches none of the 9 path(s) this repository tracks
```

So this is not a not-yet-onboarded edge case. There is no amount of correct onboarding that
clears it short of adding a `.py` file to the consumer's own tracked tree.

**Why the blast-radius sweep missed it.** `BP-100k-4`'s consumer-layout check was done — nine
grounded exemptions exist and they are good ones — but every exemption reasons about a
**path-shaped** pattern ("this path only exists inside the vendored package / the gitignored
deploy mirror"). No one asked the different question a **language-shaped** pattern raises:
*what if the consumer simply is not a Python project?* The package is self-hosted in Python, so
`\.py$` always matches here, and the gate is green in the only repo it was exercised in.

Two further gates look like the same omission and have no exemption:
`check-surface-components-e3` (targets `config/agent_registry.json` — the **same file**
`check-agent-spawn-consistency` was exempted for) and `check-eval-staleness`.

**Suggested fix (not applied).** Distinguish "this trigger is dead" from "this repository has
none of that kind of file yet". A pattern that names a language or file family should be
unreachable only when the repository *could* have such files. Options: extend the exemption
vocabulary with a language-conditional ground; skip language-shaped triggers when the
repository tracks zero files of that type; or make the gate advisory in consumer installs and
blocking only in the package's own checkout. Whichever is chosen, add a consumer-layout probe
that tracks **no** `.py` to the test suite — the existing consumer fixture has Python in it,
which is why this passed.

**Found by** an adversarial review of the shipped `ab9e91c41`, then independently reproduced
before filing.

**Pattern:** the inverse of this register's usual M5 — not a gate that passes without checking,
but a gate that **fails without a defect**. Same root cause though: the gate cannot tell
"nothing to check" from "something is wrong".

---

### KI-CG-035 — `check-proof-promise-claim` is a done-time gate that fires at creation time, so no generated epic scaffold can be committed

- **Severity:** high
- **Status:** open
- **Occurrences:** 1 epic (27 tickets); structurally affects every generated epic
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** `templates/scripts/commit_guardian/check_proof_promise_claim.py` — `main()`; rule is BP-1100g-4

**Symptom.** The hook reads each staged **ticket** file, extracts the proof kinds its AC
promises via `test_spec`, and refuses the commit unless a test already claims each one with a
matching `# covers:` / `# angle:` tag. It has no notion of *when* in a ticket's life it is
being asked.

A freshly generated epic cannot satisfy it, by construction. The tickets were written seconds
earlier by `goal_to_epic`; their tests are written **later**, during each ticket's own drive,
by `test-writer`, immediately before its coder runs — which is the TDD order this package
mandates everywhere else. So the gate demands, as a precondition of *creating* a ticket, the
very artefact the ticket exists to produce.

The effect is that **every generated epic scaffold is unlandable** until the hook is skipped.

**Evidence.** 2026-08-31, committing `EPIC-SuppressionNarrowsNeverDisables` (27 tickets, all
ACs `work_status: todo`, no test claiming any of them and none asserted to). The hook produced
one refusal per promised proof — 13 in the first screenful alone, across `GE-123d-3`,
`GE-123b-3` and `GE-123d-4-ii` — each instructing the committer to *"write a test tagged
'# covers: …'"* for work that has not been started. Committed with
`SKIP=check-proof-promise-claim`, recorded in the commit message.

This is not an argument against the gate. Its purpose — a promised proof that never arrives is
phantom-done — is exactly right, and it should keep full force at the commit that marks an AC
`done`. The defect is the trigger, not the rule.

**Detection.** Try to commit any freshly generated epic whose ACs carry a `test_spec`.

**Workaround.** `SKIP=check-proof-promise-claim` on the scaffold commit only, with the reason
recorded. Safe **only** while every AC in the commit is `work_status: todo` and nothing claims
coverage — state that explicitly, because a blanket habit of skipping this hook would restore
precisely the phantom-done hole it closes.

**Fix direction.** Key the check on lifecycle rather than on existence. A promise is due when
the AC is being marked `done` (or when the ticket has entered a drive), not when the ticket
file first appears. `work_status` is already on the record and already read by neighbouring
hooks.

**Related.** `KI-ACS-018` (the generator whose output this gate then refuses). `KI-SUP-1` (the
opposite failure: a driver that commits *past* its own recorded blockers).

---

### KI-CG-036 — Criteria wrap onto lines beginning with a lowercase Gherkin keyword, making any line-anchored clause matcher ambiguous

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1 confirmed near-miss (`BP-1500d-3`); the wrapping shape is store-wide
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** AC `criteria` block scalars store-wide; consumed by any line-anchored matcher, currently `_BECAUSE_CLAUSE_RE` in `templates/scripts/commit_guardian/_ac_schema_validators.py`

**Symptom.** Gherkin keywords in this store are capitalised at line start — `Given`, `When`,
`Then`, `Because`. But criteria are long prose wrapped into block scalars, and the wrapping is
blind to that convention: a sentence containing the ordinary English word *"because"*
mid-clause can have it land as the **first word of a continuation line**. To a matcher anchored
with `^`, that line is indistinguishable from the start of a real `Because` clause.

**Evidence — a near-miss, not a theory.** Adding `_BECAUSE_CLAUSE_RE` to strip rationale from
the durable-effect derivation, the first version was case-insensitive. Measured against the
real store it flipped **two** records, not the one it was written for. The second was
`BP-1500d-3`, whose text wraps as:

```
    and the build's own report is not enough to satisfy this,
because the build's own report is the last place this failure currently shows up,
    And the identical build … leaves the record file written to disk in that project,
```

The stripper matched that line-initial lowercase `because` and consumed everything up to the
next capitalised keyword — swallowing the `And` clause containing *"leaves the record file
written to disk"*, a **genuine** durable effect. The record would have silently flipped to
`declares_side_effect: false`: a true declaration discarded in order to suppress a false one,
the same error the fix existed to correct, in the other direction.

Caught only because the blast radius was measured record by record before the change landed.
Reasoning about the pattern would not have found it. Fixed by making the pattern
case-sensitive, with a regression test using `BP-1500d-3`'s own phrasing.

**Detection.** For any new line-anchored matcher over `criteria`, run it across the whole store
and diff the result set against the previous one; a matcher that changes more records than the
case it was written for is reading something it did not intend. Directly:
`grep -rn "^ *because\b" docs/acceptance-criteria/`.

**Workaround.** Anchor case-sensitively. Gherkin keywords are capitalised here by convention,
so case sensitivity is not a hack — it is that convention being enforced.

**Fix direction.** Two independent halves, both worth doing.

*The parser half:* treat the capitalisation as load-bearing and say so where it matters. Done
for `_BECAUSE_CLAUSE_RE`; any future clause matcher must follow, and the reason belongs in a
comment rather than being rediscovered.

*The store half — the "should not happen" part:* the wrapping should not be able to put a
lowercase keyword-lookalike at column 0 at all. Whatever re-emits these block scalars should
either avoid breaking a line immediately before `because`, `given`, `when` or `then`, or indent
continuation lines so none ever starts at the same column as a clause keyword. The second is
stronger: it makes the ambiguity unrepresentable rather than merely unlikely.

**Related.** `KI-CG-014` and `KI-CG-015` (the derivation this was found while repairing).
`KI-ACS-017` (the other defect this week caused by rewriting YAML as text rather than as a
document).

---

### KI-CG-20260831-hook-scripts-never-invoked — 24 hook scripts are named by no `entry:` line, and the guard that exists to find unreachable hooks iterates only the registered ones

> Authored first as `KI-CG-035` — the next free sequential number — and renamed on merge
> after hitting the very problem the date-and-slug convention exists to prevent. Picking
> "the next free number" requires reading the file and appending before anyone else does;
> this entry collided with two concurrent additions in one afternoon. See
> `build-pipeline.md` → "Why not the next free number" and `KI-BO-024`.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** `.pre-commit-config.yaml` (built from `templates/pre-commit-config.yaml`) — the
  set of `entry:` lines; `templates/scripts/commit_guardian/check_*.py` — the set of scripts;
  `templates/scripts/commit_guardian/check_hook_trigger_reachability.py` and its
  `hook_trigger_reachability_exemption_registry`; `templates/scripts/commit_guardian/README.md`
  — documents `check-ticket-signoff-parity` as a live hook id

**Symptom.** `check_ticket_signoff_parity.py` exists, is deployed, is documented in the
commit-guardian README as hook id `check-ticket-signoff-parity` with *"current config uses
`--enforce`"*, and **never runs**. It is not registered in `.pre-commit-config.yaml`, and it
is not exempted. It is simply absent from the only surface that would invoke it.

It is not alone:

```
registered hook ids in .pre-commit-config.yaml     54
check_*.py in templates/scripts/commit_guardian/   66
scripts named by NO entry: line                    24
```

`grep -c signoff .pre-commit-config.yaml` → `0`.

**Method, and the control that makes it trustworthy.** Comparing script *names* to hook *ids*
over-reports: `check_ac_limits.py` is registered but runs under the id
`check-ac-tree-limits`, so a kebab-case name match calls it unregistered when it is not. The
count above is therefore taken from `entry:` lines — the path pre-commit actually executes —
not from ids. The control: `check_done_proof.py` and `check_ac_limits.py` both appear on
`entry:` lines and were observed running in a live commit; `check_ticket_signoff_parity.py`,
`check_ticket_test_requirements.py` and `check_test_ac_tags.py` appear on none and were
observed not running.

**Not an alternative-dispatcher artefact.** `run_hook.py` takes the target script as an
argument and dispatches nothing on its own — its only mention of `check_docstrings` is inside
a docstring. Nothing in `.github/` invokes the two probed scripts either. So "no `entry:`
line" means "never runs", not "runs by another route".

**Cause — why the guard cannot see this.** `check_hook_parity` compares the four *directory*
copies of the hook tree (runtime, canonical template, legacy template, deployed output); it
answers "is this file present everywhere it should be", not "is this file ever invoked".
`check_hook_trigger_reachability` does ask a reachability question, but it iterates the
**registered** hooks and asks whether each one's triggers can fire. An unregistered script is
not in the set it walks. So the one guard built to find hooks that cannot fire is structurally
blind to the hook that was never wired up at all — the gap is in the enumeration, not the
predicate. Consistently, `check-ticket-signoff-parity` is *not* in the nine-entry
`hook_trigger_reachability_exemption_registry`: nobody exempted it, because nothing looked.

**Why high.** Three compounding reasons.

1. **A documented hook that does not run is worse than an absent one.** The README states it
   is live and configured with `--enforce`. Anyone reasoning about sign-off integrity —
   human or agent — will conclude the parity check is covered.
2. **It is load-bearing for scheduled work.** `BP-1100g-5-i` pins its entire mechanical
   reader onto `_signoff_parity_checks.py` "reached via `check_ticket_signoff_parity.py`",
   and its `doc_links` call that "the registered hook entry point". That is false today.
   Building it as specified would produce a reader reachable from nothing — the exact failure
   its own `it_requirements` warn about: *"A reader that is not reachable from a registered
   hook is inert."* Four `TQ-500` acceptance criteria now depend on the same host.
3. **19 of the 24 are unaudited.** Each is currently indistinguishable from a guard everyone
   believes is running. Until triaged, the commit-guardian surface's real coverage is unknown,
   and it is smaller than 66.

**AMENDED 2026-08-31 — the 24 are two different populations, and only one is a defect.** The
entry above was written before the registry itself was read. `commit_guardian.json` →
`hooks_manifest.hooks` holds **59** entries, of which **5** carry `enabled: false` and are
filtered out by `scripts/build_precommit.py`, leaving the 54 emitted. So:

| population | count | status |
|---|---|---|
| registered and enabled | 54 | fine |
| registered, `enabled: false` | 5 | **deliberate.** `check-mermaid-drift`, `check-diagram-naming`, `check-duplicate-code`, `check-diff-coverage`, `check-surface-components-e2` |
| absent from the registry entirely | 19 | the defect |

The 19: `check_ac_coverage`, `check_complexity`, `check_debug_scripts`, `check_doc_coverage`,
`check_doc_links`, `check_docstrings`, `check_documentation`, `check_file_size`,
`check_folder_density`, `check_identifier_uniqueness`, `check_pytest_style`, `check_root_files`,
`check_sql_complexity`, `check_sql_dependencies`, `check_test_ac_tags`,
`check_test_fixture_bloat`, `check_ticket_signoff_parity`, `check_ticket_test_requirements`,
`check_v2_ac_store_alignment`.

This distinction is load-bearing for any fix: a check that reports the 5 deliberate ones
produces five false alarms on the day it lands, and a false alarm has exactly one natural
remedy — weakening the check until it stops. Three states, not two:
registered-and-enabled, registered-and-disabled (valid, silent), absent (reported).

**ONE HALF OF THIS CHECK ALREADY EXISTS.** `scripts/build_precommit.py` calls
`_check_hook_script_integrity(hooks, cg_dir)`, which iterates the registry and warns for every
**registered hook whose script is missing from disk**. The converse — a script on disk that no
registry entry names — was simply never written. The asymmetry is the whole defect in one
function: the build already knows to ask whether the registry points at real files, and has
never asked whether real files are in the registry.

**Remediation.** Register `check-ticket-signoff-parity` (restoring the documented id rather
than minting a new one — `commit_guardian.json` is a package-surface registry, so a *new* id
trips `check-package-surface-declaration` and requires the structured five-field spec). Then
triage the remaining 18: register, delete, or record as a declared non-gate with a stated
ground. Finally, close the enumeration gap — the guard should walk the scripts on disk and
report any that no registry entry names, rather than walking the registry and trusting it to
be complete.

**SCHEDULED WORK — acceptance criteria already exist. Do not re-derive them.**

| AC | level | covers |
|---|---|---|
| `BP-100n-4` | L2 | the enumeration itself: scripts on disk vs registry in effect, with registered-but-disabled as a valid silent third state |
| `BP-100n-4-i` | L3 | the declared-non-gate register — an honest exemption path, keyed so an unregistered script (which has no hook id) can be named at all |
| `BP-100n-4-ii` | L3 | the no-op floor: the check must state how many scripts it compared, so "compared nothing" is unrepresentable rather than merely guarded |

Placed under `BP-100n` ("no guard infers from an empty result that there was nothing to
verify") rather than as a sibling to `BP-100k-4`, for two reasons. `BP-100k` is at its cap of
5 L2 children and its `child_limit_override: 9` was **discharged, not raised**, in the
2026-08-26 split — adding a sixth child would re-instate a waiver deliberately retired. And
`BP-100n`'s cluster rule is this defect verbatim: *"an absence must be reported as an absence
and never inferred to mean there is nothing to check."*

`BP-100k-4` remains the direct counterpart and is cross-linked: its title carries the scope
limit in its first word — *"A **registered** commit gate whose activation condition can never
match…"*. **Extend that check's enumeration; do not build a second reachability guard beside
it.**

Each absence-asserting clause in the three ACs carries a named mutation in its `notes` — the
concrete injection that must turn it red — because those clauses are green on arrival today
for the trivial reason that nothing is reported at all. That is `KI-TQ-010`'s shape, and
writing them without a stated mutation would reproduce it.

**How it was found.** An `it-po` agent enriching the `TQ-500` tree checked whether the host
its ACs pin was actually registered, instead of accepting the README's claim that it was. The
brief it was given asserted the hook was registered; it was the brief that was wrong.

**Related.** `KI-CG-034`, `KI-CG-019`, `KI-CG-012` (sibling exit-0-having-checked-nothing
routes). `BP-1100g-5-i` and `TQ-500b-1` / `TQ-500c-2` / `TQ-500c-3` / `TQ-500e-2` (the
scheduled work that depends on this host). `TQ-500b-1` overlaps deliberately and is
complementary, not duplicate: it makes registering *that one* hook a precondition of its own
reader, while `BP-100n-4` covers the class.

**Pattern:** a completeness guard whose input is the registry it is meant to be checking —
so anything missing from the registry is invisible to the check for missing things.

---

### KI-CG-20260831-fictional-config-schema-fragment — two approved acceptance criteria declare a package-surface config key that was never created, and the validator that demanded the declaration cannot tell

- **Severity:** medium
- **Status:** open
- **Occurrences:** 2 (same defect, two sibling records)
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** `docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/BP-100k-4.yaml`
  (`it_requirements.config_schema_fragment.hook_trigger_reachability`) and `BP-100k-4-i.yaml`
  (`…hook_trigger_reachability_indeterminate`); `templates/scripts/commit_guardian/_package_surface_registry.py`;
  `check_package_surface_declaration`

**Symptom.** Both records carry a structured `config_schema_fragment` naming a top-level key
of `commit_guardian.json`, complete with `type`, `description` and a `reference_file_path`.
Neither key exists. Measured in the worktree:

```
commit_guardian.json top-level keys                 36
hook_trigger_reachability                       ABSENT
hook_trigger_reachability_indeterminate         ABSENT
```

Both ACs are `work_status: done` and `readiness: approved`. The behaviour they describe
shipped; the configuration surface they declare did not.

**Cause.** `check-package-surface-declaration` requires a record that registers a package
surface to carry a structured `it_requirements` spec. It checks that the declaration is
*present and well-formed*. It does not check that the key it names is *real* — there is no
step that opens `commit_guardian.json` and looks. So the cheapest way to clear the gate is to
write a plausible fragment, and a plausible fragment is indistinguishable from a true one.

**Why this matters more than a stale field.** The spec is machine-checked, which is exactly
what makes it dangerous: a reader who knows the validator ran will trust the fragment
describes the surface. Two records now assert a configuration contract that has never
existed, and the assertion carries the authority of a passed gate. **A spec that is validated
for shape but not for existence is worse than no spec** — no spec prompts a reader to go and
look.

It also propagates. An `it-po` enriching a sibling reached for the same pattern as precedent
and had to be told not to, which would have made three. That near-miss is how this was found.

**Remediation.** Decide per record whether the key should exist. If yes, create it in
`commit_guardian.json` and keep the fragment. If no, remove the fragment and re-derive
whether `package_surface` is truthfully `true` at all. Then close the gap in the validator:
when a `config_schema_fragment` names a key in a `reference_file_path`, open that file and
require the key to be present — the same disk-versus-declaration comparison
`KI-CG-20260831-hook-scripts-never-invoked` asks for one layer down. Both are the same
omission: a check that reads the declaration and never the thing declared.

**Not fixed here, deliberately.** Found while enriching `BP-100n-4-ii`, which was steered away
from copying the pattern and carries an `it_requirement` saying why. Repairing two approved,
done records is a store-integrity change with its own blast radius and belongs in its own
change rather than riding along with unrelated criteria.

**How it was found.** An `it-po` agent checked whether the precedent it was about to copy
described a real key, instead of copying it because a validator had passed it.

**Related.** `KI-CG-20260831-hook-scripts-never-invoked` (the same declaration-versus-reality
gap, one layer down). `BP-100n-4-ii` (the record that declined to repeat it). `BO-2000d` (the
thin-or-fictional-spec rule this violates).

**Pattern:** a validator that checks a declaration is well-formed and never checks that what
it declares exists — so the cheapest way to pass it is to invent something plausible.

---

### KI-CG-20260831-1933 — `check-predone-scope` compares the whole branch diff against one ticket's `files_touched`, so it can never pass on a multi-ticket epic branch

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 3 (three commits on one epic branch, each skipped)
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** `scripts/commit_guardian/hooks/check_files_touched_reconciliation.py` —
  `_BRANCH_BASE_CANDIDATES = ["origin/main", "main"]` at `:67` and the three-dot branch diff
  at `:114` ("Return files changed in this branch relative to origin/main")

**Symptom.** Committing a ticket transitioning to `status: done` on an epic branch:

```
[check-predone-scope] ERROR: source files changed but not declared in
files_touched or out_of_scope

  Ticket : .../02_TICKET-20260826-ACD-2100a-2.md
  Undeclared source files:
    - templates/workflows-js/plan-feature.js
    - unit_tests/ac_driven_dev/test_acd_2100a_2.py
    - unit_tests/build_guards/test_acd_2100d_2.py
    - unit_tests/test_workflow_dual_engine.py
    - unit_tests/workflows/test_acd_2100a_1.py
```

Every file it names belongs to a **different ticket** on the same branch — 01 and 20. None
of them has anything to do with ticket 02.

**Cause.** The hook computes its change set as `origin/main...HEAD`, the entire branch, and
compares that against the `files_touched` of whichever single ticket is transitioning to
done. That is correct for a one-ticket branch, which is the only shape it appears to assume.
On an epic branch every ticket after the first inevitably sees every earlier ticket's files
as undeclared, and the set grows as the epic proceeds.

**Why high rather than medium.** The only ways to make it pass are both wrong. Declaring
another ticket's files in this ticket's `out_of_scope` is false, and it would have to be
repeated for all 25 tickets, each with a different and growing list — which would also
destroy the field's value as a scope signal for `change-scope-reviewer`. The alternative is
skipping the hook, which is what actually happened three times. A gate whose only passing
strategies are falsification or bypass provides no protection on the branch type it most
needs to.

**Fix direction.** Scope the diff to the commits that belong to the ticket rather than to the
branch. The per-ticket commits are identifiable — they carry the AC id — or the hook could
compare against the staged set plus the ticket's own prior commits. Failing that, detect an
epic-member ticket (path under `EPIC-*/`) and compare against the union of all sibling
`files_touched`, which at least makes the assertion true even if it is weaker.

**Workaround in use.** `SKIP=check-predone-scope`, recorded in each affected commit message
with the reason, so the skips are auditable rather than silent.

**Pattern:** a gate whose correctness assumption (one ticket per branch) is invisible in its
output, so its failure reads as a finding about the ticket rather than about itself.
