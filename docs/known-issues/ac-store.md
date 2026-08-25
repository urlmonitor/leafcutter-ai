---
title: "Known issues — ac-store"
description: "Open, observed defects in the ac-store component: the acceptance-criteria YAML store, its truth fields, its schema validator, the done-proof oracle, and the scripts that read it and transition a criterion to done. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-19
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
root. That part is now easier than when this was written: as of 2026-08-19 (KI-ACS-001)
the CLI accepts a **directory** and walks it recursively, so a whole-store pass already
has its entry point — `validate_ac_schema.py docs/acceptance-criteria` — and a run that
resolves zero files exits non-zero instead of reporting the misleading
`No YAML files to validate.` What is still missing is the cross-file comparison itself,
which is the actual work here. Worth covering retired ids in the same pass:
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
things of the same record (observed on `BO-1500a-1`, `BO-1500b-1`, `BO-1500c-1`). Two more
live one layer lower, in how the oracle maps a tag to a test at all — see KI-ACS-008.

---

### KI-ACS-008 — The oracle's tag-to-test layer cannot see an async test or a parametrised one

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** `scripts/ac_store/done_proof.py` — `_TEST_DEF_RE` (line 95, consumed by
  `_scan_single_test_file`); `_find_nodeid_for_test` (consumed by `_classify_outcomes`)

KI-ACS-006 collects defects in the oracle's **composite resolution**. These two sit one
layer lower, in the step that decides which test a `# covers:` tag belongs to and which
pytest result belongs to that test. Both fail closed, so both present as the same
indistinguishable verdict a genuinely untested AC produces — which is precisely why they
survive: the operator reads "no linked test found" and goes looking for a missing test
that is in fact sitting right under the tag.

**D-1 — `async def` is not a test definition.** `_TEST_DEF_RE` is
`r"^\s*def\s+(test_\w+)"`. There is no `async` alternative, so an `async def test_*` line
never updates `current_function` in `_scan_single_test_file`. Every tag inside that
function is either dropped (nothing seen yet → `current_function is None`) or, worse,
attributed to whatever **sync** test happened to appear earlier in the file. An AC whose
tests are all async is unmarkable through the gate; an AC in a mixed file gets its proof
silently reassigned to an unrelated function.

**Evidence.** A consumer install (DIAGraph) has **23** ACs whose every covers-tagged test
is `async def`. Four of them are `DTW-104` — `DTW-104a-3-i`, `DTW-104d-1`, `DTW-104d-3`,
`DTW-104d-3-i` — and the rest are the `N4J-100*` Neo4j integration set, the `CQ-100b-2*`
lifespan set, and `IDP-100d-4`. This is not a corner: any repo testing an async API
surface (FastAPI, an async driver) writes async tests by default, so the gate is
structurally unusable for the whole layer.

**D-2 — a parametrised test never resolves.** `_find_nodeid_for_test` matches with
`nodeid.endswith(f"::{func_name}")`. `_PYTEST_RESULT_RE` correctly *captures* the
parametrised form — its pattern includes `(?:\[.*?\])?` — so the results dict holds
`…::test_x[case]`, which does not end with `::test_x`. Both the basename-scoped pass and
the suffix-only fallback miss, `_find_nodeid_for_test` returns `None`, and
`_classify_outcomes` books the test as non-passing with the reason `linked test not run`.
A green parametrised test therefore reads as evidence the test never executed.

**Evidence.** Live in DIAGraph: `MSN-102` is covered only by
`tests/test_materials_graphdb_502.py::test_neo4j_error_returns_502`, decorated
`@pytest.mark.parametrize("path", MATERIAL_ROUTES)`. Zero occurrences in this repo today —
which is why it has never fired here, not evidence that it is rare.

**Why it matters.** Both defects push in the **false-negative** direction: they report
covered ACs as uncovered. That is the safer direction of the two, but it is the direction
that makes the gate get switched off — an operator who cannot mark a correctly-tested AC
done reaches for `SKIP=` or `--no-verify`, and from then on the gate protects nothing.
D-1's misattribution path in a mixed sync/async file is additionally a false **positive**:
AC-A's tag can be proven by AC-B's sync test.

**Fix direction.** D-1 is a one-token regex change — `r"^\s*(?:async\s+)?def\s+(test_\w+)"`
— plus a test with an async-only fixture file. D-2 wants the match to compare the nodeid's
function segment with the parameter suffix stripped (`nodeid.rsplit("::", 1)[-1].split("[", 1)[0]
== func_name`) rather than a raw `endswith`, and should classify a parametrised test as
passing only when **every** matching nodeid passed — one green case out of five is not
proof. Note `_find_nodeid_for_test` returns a single nodeid today, so D-2's fix changes
its signature; do it as one AC with the caller.

**Related:** KI-ACS-006 (composite-resolution defects in the same oracle); KI-CG-006 (the
pre-commit gate disagrees with this oracle in both directions).

**Pattern:** `docs/reference/false-green-mechanisms.md` — the inverse case: a gate whose
false refusals train the operator to bypass it.

---

### KI-ACS-004 — An AC is marked `done` with no link to the code implementing it

- **Severity:** high
- **Status:** open — no AC authored yet; the semantics question below is the reason
- **Occurrences:** 18
- **First seen:** 2026-08-17 · **Last seen:** 2026-08-24
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

Three more on 2026-08-19: BO-2600b-1, -1-i and -1-ii, again via
`mark_ac_done.py --test-root`, again all three landing `implemented_by: []` after
passing the coverage gate, again filled in by hand. Recorded not because three more
adds information about the mechanism — it does not — but because the only reason the
count keeps rising instead of the defect being fixed is that hand-repair is cheap
enough each time to stay below the threshold at which anyone stops to fix it. That is
worth being explicit about: the workaround is what is keeping the bug alive.

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

### KI-ACS-007 — `components` is required and hand-authored while the package ships its deriver

- **Severity:** blocker
- **Status:** open
- **Occurrences:** 2
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-19
- **Where:** `scripts/ac_store/validate_ac_schema.py:225-230` · `config/ac_store_schema.json:521`
  · `scripts/ac_store/_component_migration_map.py` · `scripts/check_component_vocab.py:25`

**Second occurrence, 2026-08-19 — there is a THIRD copy of the vocabulary, and this entry
undercounted.** Registering the new `security_scanner` component exposed it. After adding
the id to `docs/components.json`, the two validators disagreed:

```
$ python3 scripts/check_component_vocab.py
OK: all `components` values are canonical components.json ids (full tree).

$ find docs/acceptance-criteria/guardrail-engine -name '*.yaml' \
      -exec python3 scripts/ac_store/validate_ac_schema.py {} +
  ...GE-123a.yaml: schema violation at components.1 —
  'security_scanner' is not one of ['ac_driven_dev', 'ac_store', ... 'worktree_manager']
```

Forty-two files failed. `check_component_vocab.py` reads `docs/components.json`;
`validate_ac_schema.py` validates against a **hand-maintained `enum` inside
`config/ac_store_schema.json`** that duplicates the same 42 ids. Adding a component
requires editing both, in the right order, and nothing says so — the first validator
reports full-tree success while the second rejects every record.

So the count in the text below is wrong: this is not two vocabularies bridged by a map, it
is **three** — `docs/components.json` (underscore, graph membership),
`docs/acceptance-criteria/index.yaml` (kebab, namespace and id prefixes, correctly
separate), and the schema `enum` (underscore, a straight duplicate of the first with no
mechanism keeping them in step). The entry's own prediction — *"parallel names bridged by a
map drift by construction"* — applies to the third copy most sharply, because it is not
even bridged by a map; it is a literal transcription.

**Fix direction for the third copy specifically.** Generate the schema `enum` from
`docs/components.json` at build time, or drop the `enum` and have the validator read the
registry the way `check_component_vocab.py` already does. Two validators disagreeing about
what a valid component id is means one of them is always wrong.

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

Filed as KI-ACS-003 while this work sat uncommitted, renumbered to 005 at merge time, and
renumbered again to 007 immediately afterwards — the 005 landed as a DUPLICATE. PR #496
merged three minutes before #497 and took both 005 and 006, so the number verified free at
authoring was taken by the time the merge button was pressed.

Worth recording rather than quietly correcting, because it is the third instance of one
mechanism in two days and the first two are already filed: KI-ACS-003 (the AC store has no
id-uniqueness gate) and KI-ACD-008 (id allocation reads a stale view of what is taken).
This register has the same hole and no gate at all. Checking a number is free is not
sufficient when the check and the merge are separated by any interval in which another PR
can land — the property that matters is uniqueness AT MERGE, and nothing asserts it. The
fix that would have caught all three is one gate over the merged tree, not more care at
authoring time.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M5 (a validator that cannot run
is indistinguishable from one that passes).

---

### KI-ACS-009 — The documented AC-store pre-flight runs a weaker validator than the required CI gate, so a clean local check does not predict CI

- **Severity:** medium
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** `CLAUDE.md` → "AC-store hygiene — bulk pre-flight", against the
  `check-ac-schema` pre-commit hook that the required `AC store valid` job runs

**Symptom.** There are two AC validators and they enforce different rules.
`scripts/ac_store/validate_ac_schema.py` checks the record against the schema. The
required CI job runs `pre-commit run check-ac-schema`, which additionally enforces
binding completeness, field preservation (ACS-500f-1), test-contract rules, and
derived-field rules such as `declares_side_effect` (BO-2900g-2). `CLAUDE.md`'s pre-flight
section prescribes only the former.

**A retracted correction, 2026-08-25 — and the retraction is the useful part.** On
2026-08-24 this paragraph was edited to say the `declares_side_effect` (BO-2900g-2) example
was fabricated and that no gate enforces the field. **That edit was wrong. The original
text was right, and has been restored.** `check-ac-schema` does enforce it: CI failed PR
#529 with *"declares_side_effect is authored as True but this AC's own Then clause derives
False — the two disagree … (BO-2900g-2)"*.

The mistake is worth keeping because it is this entry's own subject, one layer down. Two
agents independently grepped `scripts/commit_guardian/` and `.leafcutter/scripts/
commit_guardian/`, found nothing, and concluded the rule did not exist. The rule lives in
**`templates/scripts/commit_guardian/_ac_schema_validators.py`** — `templates/` is the
source the build deploys *from*; `scripts/commit_guardian/` in a worktree is a build output
frozen at whenever that worktree was last built (KI-BP-004). Running the hook locally
passed for exactly the same reason: the local hook was the stale copy, without the rule.

So the sequence was: entry states a true fact → two agents check it against the deployed
tree and get a false negative → entry is "corrected" into an untruth → CI, which builds
before running the hooks, contradicts all of it. Local hook agreement is not evidence the
rule is absent; it is evidence about the age of your deploy. Grep `templates/scripts/` when
asking what a hook enforces, and treat a passing local hook as unverified until CI agrees.

Running the weaker validator and seeing `OK: all N AC YAML files are valid` therefore establishes
much less than it appears to, and the gap is invisible because both are called "the
schema validator" in conversation.

**Evidence.** PR #510, 2026-08-19. `find ... -exec validate_ac_schema.py {} +` reported
all 82 files in the touched folder valid, and every folder-level run during authoring was
clean. CI then failed `AC store valid` on two of those same files —
`BO-2400c-1-v.yaml` and `BO-2600b-2.yaml` — both missing `declares_side_effect: true`,
a rule that had merged from main mid-branch and that the prescribed command does not
implement. Running `env --chdir=<repo> pre-commit run check-ac-schema --all-files`
reproduced the failure locally in one command, and confirmed the fix.

**Why it is worth recording rather than just remembering.** The pre-flight exists
specifically so store violations surface in a batch instead of as a per-commit cascade.
A pre-flight that runs a strictly weaker check than the gate it is meant to anticipate
does not do that job, and it is the second defect found in this same CLAUDE.md section —
the first being the bare-directory no-op now recorded as KI-ACS-001. Both share a shape:
the documented defence was believed to be equivalent to the enforced one.

**Fix direction.** Change the prescribed pre-flight command to the hook the gate actually
runs — `env --chdir=<repo-root> pre-commit run check-ac-schema --all-files` — and keep
`validate_ac_schema.py` only for single-file spot checks where its narrower scope is
understood. Longer term the two should not diverge silently: either the hook calls the
script, or the script grows the hook's rules, so there is one answer to "is this store
valid". Note the hook reads the git **index**, so files must be staged before it can see
them — an unstaged fix will appear not to work.
