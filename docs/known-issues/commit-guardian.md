---
title: "Known issues — commit-guardian"
description: "Open, observed defects in the commit-guardian component: the pre-commit hook family that gates commits, and in particular the AC-store hooks whose scope is the git index rather than the store. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-18
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

### KI-CG-006 — The pre-commit proof-of-done gate is stricter than the CI backstop it approximates

- **Severity:** high
- **Status:** open
- **Occurrences:** 2
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/scripts/commit_guardian/check_done_proof.py` (`check_staged_done_proofs`)

**Symptom.** `check_staged_done_proofs` never reads `test_required`, and has no composite
path. Its two siblings have both: `check_all_done_acs` and `check_changed_done_acs` each
skip an AC with `test_required: false`, and both derive a composite's verdict from its
children via `verify_done_eligible`. So the fast local gate blocks commits that the CI
gate would pass.

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
