---
title: "Known issues — ac-store"
description: "Open, observed defects in the ac-store component: the acceptance-criteria YAML store, its truth fields, its schema validator, the done-proof oracle, and the scripts that read it and transition a criterion to done. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-18
components:
  - ac_store
related_docs:
  - docs/how-to/prove-ac-done.md
  - docs/known-issues/build-orchestration.md
  - docs/reference/ac-schema.md
---

# Known issues — ac-store

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-ACS-NNN` section using the next free number.
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

### KI-ACS-001 — `validate_ac_schema.py` exits 0 when it validates nothing

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/ac_store/validate_ac_schema.py:333`

**Symptom.** The script takes **file paths** and does no globbing of its own. Handed a
directory — the intuitive way to validate a component — it matches zero files, prints
`No YAML files to validate.` and **exits 0**. The caller sees a success-shaped result
from a run that checked nothing. A validator that cannot distinguish "clean" from "I was
given nothing" is worse than no validator, because it is consulted for reassurance.

**Evidence.** Verified 2026-08-18 against `docs/acceptance-criteria/testing-quality/`:
the bare-directory form prints the no-op message and exits 0, while
`find <dir> -name "*.yaml" -exec python scripts/ac_store/validate_ac_schema.py {} +`
over the same tree reports eight real violations (`documentation_triggers` present on L2
records, permitted only on L1). Across the whole store the correct invocation reports
**288** violations, most of them legacy list-form `it_requirements` predating the
object-form rule — real, but not a fire.

This mattered because `CLAUDE.md`'s own "AC-store hygiene — bulk pre-flight" section
prescribed the bare-directory form from 2026-08-10 until 2026-08-18, so the documented
defence against store rot was itself a no-op for eight days. That instruction is now
fixed; the script is not.

**Fix direction.** Exit non-zero, or at minimum warn loudly, when the resolved file count
is zero. Better: accept a directory and walk it, since that is plainly what every caller
means. Note a plain `*/*.yaml` glob is **not** an adequate workaround — AC YAML sits at
more than one depth, so a fixed-depth pattern silently skips directories, which is the
same defect wearing a different hat.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M5.

---

### KI-ACS-002 — `--verify` passes `files_touched` on a path count, not on correctness

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/ac_store/generate_ticket_from_ac.py` — the `--verify` readiness report

**Symptom.** The readiness report's surface check asserts only that *some* paths were
derived. Its output reads `[PASS] files_touched has N path(s) from doc_links` — N > 0 is
the whole test. An AC whose derived surface omits the file the work changes, and includes
a file the AC's own criteria forbid touching, passes it and the report concludes `READY`.
The provenance label is misleading too: paths that came from the prose fallback are
reported as coming from `doc_links`.

**Evidence.** `python scripts/ac_store/generate_ticket_from_ac.py --ac BO-2400g-2 --verify`
on `main` at `439b9076f` exits 0 and prints:

```
=== Ticket readiness report for BO-2400g-2: READY ===
  [PASS] files_touched has 4 path(s) from doc_links
```

The four paths are `scripts/build.py`, `templates/agents/change-scope-reviewer.md`,
`templates/agents/pr-reviewer.md` and `unit_tests/_workflow_engine_harness.py`. The file
that AC exists to change — `templates/workflows-js/fast-lane-ship.js` — is absent, because
its `doc_link` is tagged `describes`. `change-scope-reviewer.md` is a file that AC's
criteria explicitly forbid touching, and `scripts/build.py` came from the prose scan, not
from a `doc_link` at all.

This is the check people reach for when they want reassurance that a generated ticket is
sane, so a count dressed as a verdict is worse here than elsewhere.

**Fix direction.** Compare the derived surface against something independent — at minimum
warn when an AC has edit-surface `doc_links` for files that did not make the list, or when
a path arrived only via the prose fallback. Report provenance per path honestly. A check
that cannot assess correctness should report `INFO`, not `PASS`. Related: the prose
fallback itself is `BP-1100a-4`, and the authoring-side rule is documented in
`docs/how-to/ac-traceability-store.md`.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M8.

---

### KI-ACS-003 — The store validator does not check id uniqueness, so duplicate AC ids merge clean through a required gate

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/ac_store/validate_ac_schema.py`, and the `AC store valid` CI job that runs it

**Symptom.** `validate_ac_schema.py` validates each file against the schema
independently. It never compares `id` fields across files, so two records sharing an id
both validate and the store reports healthy.

**Evidence.** Run directly against the two files that currently both claim `GE-120` on
`main`:

```
$ python3 scripts/ac_store/validate_ac_schema.py \
    docs/acceptance-criteria/guardrail-engine/GE-120.yaml \
    docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/GE-120.yaml
OK: all 2 AC YAML files are valid.
```

One is an L2 about the doc-types guard; the other is an L0 with 42 descendants. Same
id, different level, unrelated subjects. See `docs/known-issues/ac-driven-dev.md`
KI-ACD-008 for how the duplicate was created.

**Why it matters more than a normal validator gap.** `AC store valid` is one of the six
**required** status checks on `main`. It is the gate whose entire job is to keep the
store trustworthy, and an id is the store's primary key — every `depends_on`,
`covered_by`, `implemented_by` back-link and every `# covers:` done-proof tag resolves
through it. A duplicated id means those references are ambiguous: a coverage resolver
asked for `GE-120` gets whichever file it happens to read first. Green here currently
means "each file is individually well-formed", not "the store is consistent", and the
name of the check invites the stronger reading.

**This is no longer hypothetical — the ambiguity is producing wrong output today.**
`scan_ac_orphans.py parent-links` over `docs/acceptance-criteria/guardrail-engine/`
**exits 1** reporting five orphans: `GE-120a`, `GE-120b`, `GE-120c`, `GE-120d`,
`GE-120e` "missing from `GE-120.yaml`'s `covered_by`". All five reports are false.
The two records:

```
GE-120-green-means-checked/GE-120.yaml   (L0)   covered_by: [GE-120a..GE-120e]   <- correct
GE-120.yaml                              (L2)   covered_by: []                   <- resolved instead
```

The resolver derived parent `GE-120` from each child id, read the **loose L2**, found
an empty `covered_by`, and declared the children orphaned. The real parent lists all
five correctly. So the duplicate id is already corrupting a store-integrity tool's
verdict — and `check_ac_parent_covered_by` is a commit-time hook resolving parents the
same way, which means the same ambiguity can block a correct commit or wave through an
incorrect one depending only on which file is read first.

That elevates this from "a gap that let a duplicate merge" to "a gap that is actively
producing incorrect results in the tooling built on top of it".

**Fix direction.** Add a store-wide uniqueness pass: collect every `id:` across the AC
root, fail on any id claimed more than once, and name both paths in the error. This is
a whole-store check rather than a per-file one, so it needs a mode that takes the store
root — note the CLI currently accepts **file** arguments only and silently skips
anything that is not a `.yaml`, which is also why a directory argument returns the
misleading `No YAML files to validate.` Worth covering retired ids in the same pass:
the id between GE-118 and GE-120 is recorded as retired and must never be
reissued (see PR #453), which a pure uniqueness check would not catch on its
own. It is not written out here because the GE-122e-1 guard fails the build on
any live citation of it outside dated historical records.

**Update — the duplicate is gone (2026-08-18); the validator gap is NOT.** The loose L2 was
renumbered to `GE-118c` and moved under `GE-118`, so `GE-120` now resolves to exactly one
record and `scan_ac_orphans.py` no longer reports the five false orphans quoted above. The
reproduction commands and their output are left unchanged as the record of what the store
looked like when this issue was filed. **This entry stays open**: `validate_ac_schema.py`
still performs no store-wide uniqueness pass, so the next duplicate id will merge just as
cleanly. Note also that the false-orphan symptom above is the strongest available argument
for that pass — it is the only reason this particular duplicate was noticed at all.

---

### KI-ACS-005 — The package-surface `it_requirements` rule blocks commits that did not cause it

- **Severity:** blocker
- **Status:** open
- **Occurrences:** 3
- **First seen:** 2026-08-13 · **Last seen:** 2026-08-18
- **Where:** `config/ac_store_schema.json` (the top-level `if`/`then`, BO-2000d), enforced
  by `check-ac-schema` locally and by the required `AC store valid` CI job

**Symptom.** The `if` fires on `assigned_agent: python-coder` AND `component` in
`{build_pipeline, build-orchestration}`, and the `then` demands `it_requirements` be an
object with five fields (`config_schema_fragment`, `reference_file_path`,
`n_location_rule`, `required_skills`, `post_write_commands`). The trigger is a proxy for
"package-surface AC" and it over-matches: it catches every python-coder AC in those two
components, most of which register no config key at all, so there is no honest
`config_schema_fragment` or `reference_file_path` to supply.

The rule also postdates most of the data. Enum and `if`/`then` landed together in
`9e59b1fe7` (2026-07-09); the records it rejects were authored earlier with the older
list-of-strings form.

**Evidence.** Whole store at `f8cfdfc47`, `index.yaml` excluded: 2887 AC YAML files, 253
failing schema validation, **251 of them on `it_requirements`** (the other 2 are
`framework: playwright`, outside the enum). `BO-100a.yaml` is an untouched control — it
fails on a clean checkout with no local modifications.

**Correction, 2026-08-19 — it also UNDER-matches, and that half is worse.** The original
writeup above described only the over-match. Measured at `9b16d013`, the enum mixes the two
component spellings:

```
component: build-orchestration   845   <-- in enum (kebab)
component: build_pipeline         65   <-- in enum (underscore)
component: build-pipeline        440   <-- NOT in enum
```

`components.json` graph ids use underscores; `index.yaml` namespaces use kebab. The enum
took one of each. So of 1610 python-coder records, the rule fires on 411 and **misses 239
build-* records — 215 of which carry non-object `it_requirements` and have therefore never
been checked once.** The gate is simultaneously too tight and too loose, keyed off a
spelling.

The proxy is also false of the population it does catch: of 245 records carrying the object
form, **73 set `config_schema_fragment: null`** — nearly a third wrote an explicit null to
get past a rule that does not apply to them.

Any fix must therefore do more than narrow the trigger; it must stop keying on `component`
at all, or the 440 kebab records stay invisible. Specified in `ACS-100i-6`, `ACS-100i-6-ii`
and `ACS-100i-7`.

**Why it matters.** Both gates are diff-scoped, so the violation is invisible until an
unrelated change puts one of these files in a diff — then it blocks that commit. It has
now been deferred with a documented `[HOOK-SKIP: check-ac-schema]` twice, in `7c8c505e3`
(PR #424) and again on 2026-08-18, both times by authors who did not write the offending
records. On the second occasion 29 files were flagged and **all 29 were verified to fail
identically at HEAD** — zero introduced by the commit. A gate skipped twice by people who
cannot fix it is training people to reach for `SKIP=`.

The skip does not clear CI: `AC store valid` is a required check and re-blocks the same
files at the PR, so the local skip only moves the wall.

**Fix direction.** Two, not mutually exclusive. (1) Narrow the trigger — key the `if` off
an explicit marker such as `package_surface: true` rather than inferring it from
`assigned_agent` + `component`. Smaller, and it stops the class growing. (2) Backfill the
existing records — an epic, and it should depend on
`TICKET-20260710-ITPOv3-StructuredItRequirements.md` so the authoring agent stops emitting
list-form `it_requirements` before the backfill starts. Closing condition: a commit
touching a `build-orchestration` AC no longer needs `[HOOK-SKIP: check-ac-schema]`.

**Pattern:** `docs/reference/false-green-mechanisms.md` — the inverse; a gate that fires
where it should not, whose only escape trains the reader to disarm it.

---

### KI-ACS-006 — Three defects in the done-proof oracle that misreport AC coverage

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/ac_store/done_proof.py` (`_verify_composite_eligible`,
  `_resolve_all_child_ids`); `scripts/ac_store/test_enforcement.py` (`COVERS_TAG_RE`)

All three found by running the real oracle over the store rather than reading it. Context
for why they stayed hidden: CI runs `check_done_proof --mode ci-changed`, which only
evaluates ACs in the diff. The whole-store mode (`--mode ci`, `check_all_done_acs`) has
never run in CI, so none of these ever produced a visible failure.

**D-1 — the composite path ignores a child's `test_required: false`.**
`check_all_done_acs` honours the exemption for the AC it is evaluating, but
`_verify_composite_eligible` never reads the field when checking children —
`_build_ac_status_map` does not even carry it, so the function structurally cannot. A
composite whose only uncovered children are legitimately test-exempt can therefore never
be eligible. Live: `verify_done_eligible('BO-2300a')` → `composite BO-2300a has uncovered
children: BO-2300a-3`, where `BO-2300a-3` is a state-diagram AC with `test_required:
false` whose diagram exists at
`docs/architecture/diagrams/c3-001-interactive-pause-resume-run-lifecycle.md`. Three ACs
are stuck this way: `BO-2300`, `BO-2300a`, `BO-2300d`.

**D-2 — a legacy `covered_by` entry makes a child vanish.** `_resolve_all_child_ids`
recurses on `if child_covered_by:` — truthiness — instead of checking whether any entry
resolves to a store record. The legacy-path guard (`_has_resolvable_child`, the BO-2500a-6
M-2 remediation) is applied by the top-level caller but not at each recursion step. A child
whose own `covered_by` holds only a legacy test-file path is treated as a composite with no
leaves and contributes nothing, so the parent reports "no coverable children" instead of
naming the real untested child. Live: `BO-510-3.covered_by = ['BO-510-3-i',
'unit_tests/test_agent_produces_validation.py']` and `BO-510-3-i.covered_by =
['unit_tests/test_agent_produces_validation.py']` → `composite BO-510-3 has no coverable
children`. The correct verdict names `BO-510-3-i`.

**D-3 — multi-id `covers:` tags are mis-parsed.** `COVERS_TAG_RE` captures a single
`(\S+)`, so a line naming two ACs swallows the comma into the first id and drops the
second. `# covers: BO-610-1, BO-610-3-i` registers the id `'BO-610-1,'` — which matches
nothing and is also reported as a dangling tag — and `BO-610-3-i` is not registered at all.
`BO-610-1` and `BO-610-2` were both `work_status: done` with passing tests and the oracle
reported "no linked test found" for each. Partially mitigated on 2026-08-18 by splitting
the two affected tag lines one-id-per-line; **the regex is unchanged**, so the trap is live
for the next author. Two more occurrences remain in
`unit_tests/test_generate_ticket_from_ac.py` (`BO-530`, `BO-560`), harmless today only
because those ACs are `todo`.

**Why it matters.** D-3 produces false "untested" verdicts on ACs that are genuinely
covered, which is how a correct record gets flipped backwards. D-1 and D-2 make four ACs
permanently ineligible. Together they mean the whole-store sweep cannot be turned on: it
would block every merge on defects in the gate rather than in the store.

**Fix direction.** D-3 first — smallest, and it is the one currently producing wrong
verdicts. Then D-1 (pass `test_required` through `_build_ac_status_map` and honour it in
the composite path), then D-2 (apply `_has_resolvable_child` at each recursion step). Each
changes a gate's verdict, so each wants an AC and a test. Worth pairing with a decision on
whether `--mode ci` should run in CI at all — it currently cannot pass.

**Related:** a fourth defect in this family lives in `commit-guardian` — see KI-CG-006 for
the pre-commit variant being stricter than the CI backstop. A fifth is definitional: the
schema hook's `_is_leaf_ac()` treats any `level: L2` AC as a leaf, while the oracle treats
an AC with resolvable children as a composite, so the two gates can demand contradictory
things of the same record (observed on `BO-1500a-1`, `BO-1500b-1`, `BO-1500c-1`).

---

### KI-ACS-004 — An AC is marked `done` with no link to the code implementing it

- **Severity:** high
- **Status:** open — no AC authored yet; the semantics question below is the reason
- **Occurrences:** 12
- **First seen:** 2026-08-17 · **Last seen:** 2026-08-18
- **Where:** `scripts/ac_store/mark_ac_done.py`; also reached from
  `scripts/build_orchestration/fast_lane.py` — `_update_ac_work_status`, used by
  `mark_done_built_acs`

**Symptom.** Every automated path to `work_status: done` is status-only. Nothing
writes `implemented_by`, so an AC can assert completion with no traceable link to the
code that satisfied it — the reader has no way to check the claim.

**Evidence.** TKT-600a-1 after its fast-lane build: `work_status: done`,
`implemented_by: []`; populated by hand in `b3124ff25`. Same gap on 2026-08-17 when
the BO-2400a-3 family was marked done via `mark_ac_done.py`, which also only sets
`work_status` — so this is not specific to the fast lane.

Reproduced ten more times on 2026-08-18 (PR #485). Every one of BO-2400f-4, its six
children, BO-2400f-11, and BO-2400c-1-ii/-iii/-iv was marked done through
`mark_ac_done.py --test-root`, passed the coverage gate, and landed with
`implemented_by: []`. All ten were filled in by hand in the same commit. The
count is what makes the shape clear: this is not an occasional miss, it is the
guaranteed outcome of every automated done-transition, and the only thing
currently preventing a store full of unprovenanced dones is somebody noticing.

Worth recording precisely because the gate did its job. Coverage was verified, a
passing covers-tagged test existed for each — so the failure is not "done was
claimed falsely", it is "done was claimed truthfully and left untraceable". It is a
sibling of KI-ACS-001 above rather than a duplicate: that one is a check reporting a
pass it did not earn, this one is a record omitting the evidence for a pass it did.

**Fix direction.** Write `implemented_by` at mark-done time from the evidence already
in hand (the coder phase reports `files_modified`; `done_proof` already resolves the
covering test). Note this is a **provenance-semantics decision, not a mechanical
one** — what `implemented_by` must contain for a claim of done to be trustworthy is
the owning question, and it should be settled here rather than in each call site.

**Provenance.** Originally recorded as KI-BO-002 in
`docs/known-issues/build-orchestration.md` because it was found during a fast-lane
run. Refiled here on 2026-08-18: the call site is in `fast_lane.py`, but the
semantics of `implemented_by` and of what "done" must prove belong to this
component, not to the lane that happens to invoke it. Renumbered twice while this
branch waited to merge — filed as KI-ACS-001, then 003, now 004: `ac-store.md` was
created independently on both sides of the merge, and main kept adding entries
underneath. The id churn is cosmetic; the defect is not.

---

### KI-ACS-005 — `components` is required and hand-authored while the package ships its deriver

- **Severity:** blocker
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/ac_store/validate_ac_schema.py:225-230` · `config/ac_store_schema.json:521`
  · `scripts/ac_store/_component_migration_map.py` · `scripts/check_component_vocab.py:25`

**Symptom.** Every AC must carry a `components` list, validated non-empty against
`docs/components.json`. Almost all of it is mechanically derivable from the `component`
scalar the AC already has — and the package ships the derivation:
`_component_migration_map.py` exists for exactly this translation, and
`generate_ticket_from_ac.py` imports it to produce the list from the scalar.

Required-plus-derivable is the design error. It converts any failure to supply the
deriver into a hard block on a field the tooling was built to compute. That is not
hypothetical: `_component_migration_map.py` is **absent from the build deploy manifest**
(`build_ac_store`'s `deploy_map`, `scripts/build_phases.py:851-879` — which also omits
`_ac_components.py` and `validate_ac_schema.py` itself). In a consumer repo that vendors
the build output, the store therefore cannot satisfy its own schema. BrainCandy measured
**972 of 973** ACs invalid in one such repo, on a field the tooling was supposed to
generate.

**Evidence.** Measured 2026-08-18 over this repo's own store (3,154 AC YAML files):

| Case | Count | Share | Information added by the field |
|---|---:|---:|---|
| Identical spelling — `component` == `components[0]` | 296 | 9.4% | none |
| Different name, still 1:1, resolved by `MIGRATION_MAP` | 2,441 | 77.4% | none a lookup can't produce |
| Genuinely multi-valued — real 1:N membership | 377 | 12.0% | real |
| Single-valued but **underivable** — see below | 29 | 0.9% | none, but the map can't supply it |
| No `components` field at all | 9 | 0.3% | — |

So **86.8% is derivable**, and the residue is a narrow, repeating set of shapes — the top
three multi-valued pairings account for 122 of the 377.

Two findings beyond the derivability count:

- **`MIGRATION_MAP` is incomplete.** It holds 13 entries. `code-review` → `review_system`
  is not among them, which is the whole of the 29-record underivable bucket. Making the
  deriver the default without completing the map would fail exactly there.
- **The "required" field is not actually enforced store-wide.** Nine records carry no
  `components` at all and have survived. Cf. KI-ACS-001 — the validator exits 0 when
  handed a directory, so the store was never swept.

**The two vocabularies are a synonym problem, not a modelling one.** `ac_store_schema.json`
and `check_component_vocab.py` both assert the split is deliberate — "a SEPARATE axis …
intentionally NOT migrated". But the renames it bridges (`guardrail-engine` →
`commit_guardian`, `ticket-creation` → `ticket_creation_pipeline`, `code-review` →
`review_system`) are two names for one component, held in parallel and reconciled by a
lookup table. Parallel names bridged by a map drift by construction; the incomplete
`MIGRATION_MAP` above is that drift, already present. This also contradicts the standing
intent to retire `docs/acceptance-criteria/index.yaml` in favour of `docs/components.json`
as the single registry — a migration that is still half-done, with `index.yaml` live in
`validate_ac_schema.py`, `check_component_vocab.py`, `ac_store_schema.json` and seven
backfill scripts.

**Fix direction.** Three changes, in order, and the first is the one that unblocks
consumers:

1. Make `components` **optional**, defaulting to `[migrate(component)]`. Keep it explicit
   only for the 12% with real 1:N membership. Complete `MIGRATION_MAP` first, or the
   default is wrong for 29 records.
2. Reconcile the two vocabularies to one. Either `docs/components.json` keys become the
   single vocabulary and `index.yaml` is retired (the standing intent), or the reverse —
   but not both maintained in parallel. Until then, correct the schema and
   `check_component_vocab.py` prose: they currently document the duplication as a design
   choice, which discourages fixing it.
3. Deploy `_component_migration_map.py`, `_ac_components.py` and `validate_ac_schema.py`.
   See KI-BP-006 — that gap is the **trigger**, not the root cause. Fixing only the
   manifest makes the symptom disappear in consumer repos while leaving a required field
   that the package computes for itself.

There is a real requirement underneath this: an AC lives in one directory but can belong
to more than one component. That is genuine 1:N and worth keeping. It does not justify a
required, hand-authored, separately-spelled second field on all 3,154 records.

Filed as KI-ACS-003 while this work sat uncommitted; renumbered to 005 on landing because
main published a different KI-ACS-003 (id uniqueness) and a KI-ACS-004 in the interim.
Same churn the entry above records, and the same cause.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M5 (a validator that cannot run
is indistinguishable from one that passes).
