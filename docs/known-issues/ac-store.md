---
title: "Known issues — ac-store"
description: "Open, observed defects in the ac-store component: the acceptance-criteria YAML store, its truth fields, its schema validator, the done-proof oracle, and the scripts that read it and transition a criterion to done. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-26
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
- **Occurrences:** 6
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-26
- **Where:** `scripts/ac_store/generate_ticket_from_ac.py` — the `--verify` readiness report

**2026-08-26 — four more, consecutively, on one AC chain.** Every ticket generated for the
`BP-1100g` chain needed its surface corrected by hand before it could be dispatched, and in each
case the generated `files_touched` was non-empty, so the readiness check passed:

| ticket | generated surface | what was missing |
|---|---|---|
| `BP-1100g-1` | 1 path | named the **deployed** `.claude/agents/test-writer.md`; the source is `templates/` |
| `BP-1100g-3` | 1 path | the entire **prompt** surface — `llm-expert` sat in the agents map with no file to edit — plus both test files |
| `BP-1100g-3-i` | 1 path | named `done_proof.py`, the one file that AC's `n_location_rule: 0` **forbids** touching, and gave the tests nowhere to land |
| `BP-1100g-4` | 1 path | the new hook module, the deploy-manifest entry, and the test file — see **KI-ACS-014**, the path it *did* name is untracked |

The `BP-1100g-3-i` case is the sharpest: `reference_file_path` is the file the tests **observe**,
and the generator copies it into `files_touched` as the file the ticket **edits**. On a negative
control those are opposites, so the readiness report passed a surface that instructed the
implementer to do the one thing the AC prohibits.

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

**Second occurrence, 2026-08-25 — the prose fallback can name a BUILD OUTPUT as the
edit surface, and the sentence it scrapes may be one warning against exactly that.**
Found on the first ticket generated after the test-contract fix, `BP-1100g-1`. Report:

```
[PASS] files_touched has 3 path(s) from doc_links
```

The three were `docs/testing/test-angles.md`, `templates/agents/test-writer.md`, and
`.claude/agents/test-writer.md`. The third is not one of that AC's five `doc_links`
— it came from the prose fallback, scraped out of the it_requirement sentence *"The
taught set must be present in the DEPLOYED copy (`.claude/agents/test-writer.md`), not
only in `templates/`"*. That sentence exists to say the deployed copy is the
**assertion target**; the derivation read it as an **edit target**. And
`.claude/agents` is a symlink to `.leafcutter/agents`, so it is a build output that
`build.py` regenerates from `templates/`.

This occurrence is worth recording separately from the first because the consequence is
not a merely-inaccurate list — it is a live phantom-done trap, on the AC whose whole
purpose is preventing phantom-done:

1. `BP-1100g-1`'s fourth `test_spec` entry is a **reachability** test that runs
   `build.py` and then reads the DEPLOYED `.claude/agents/test-writer.md`, deliberately,
   because the agent runtime loads the built copy.
2. An implementer following `files_touched` edits the deployed copy. That test passes
   immediately.
3. `templates/` is untouched, so the next `build.py` overwrites the deployed copy and
   the work disappears.
4. The ticket has already closed green.

Also, in the same report, the directory where all four tests land
(`unit_tests/prompt_assembly/`) was **absent** from `files_touched`, which would have
made the actual deliverable read as unexpected scope to `change-scope-reviewer`. So the
derived surface was wrong in both directions at once, and the count-based check called
it `PASS`.

Worked around on the ticket by hand (correct `files_touched`, plus an `out_of_scope`
naming `.claude/agents/` and `.leafcutter/` so a diff there is a hard violation), not
fixed at source.

**Sharpened fix direction.** Beyond reporting provenance honestly: the derivation should
never emit a path under a known build-output root as an edit surface. Those roots are
already knowable — `.leafcutter/` and everything symlinked into it from `.claude/` — so
this is a filter, not a judgement. A path that resolves inside a build output is either
an assertion target or a mistake, and in both cases it does not belong in
`files_touched`.

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
- **Occurrences:** 2
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-26
- **Where:** `CLAUDE.md` → "AC-store hygiene — bulk pre-flight", against the
  `check-ac-schema` pre-commit hook that the required `AC store valid` job runs

**2026-08-26 — reproduced exactly, on the same rule this entry's retraction story is about.**
Generating the `BP-1100g-4` ticket, `validate_ac_schema.py` over the whole `BP-1100`
feature folder reported `OK: all 58 AC YAML files are valid`. The very next `git commit`
was blocked by `check-ac-schema` on one of those 58:

```
BP-1100g-4.yaml: declares_side_effect is authored as True but this AC's own Then
clause derives False — the two disagree ... (BO-2900g-2)
```

Same store, same moment, two validators, opposite verdicts — and the weaker one is the
command `CLAUDE.md` still prescribes. Two details worth adding to the record. First, the
disagreement was **pre-existing since 2026-08-17** and surfaced only because that record
happened to be staged: the hook reads the git index, so a store-wide violation is
structurally invisible until something touches the file (the forward-ratchet property this
register keeps rediscovering). Second, the resolution direction is not symmetric —
`criteria` is the authored requirement and the fixed point, so the derived boolean yields
to it, never the reverse.

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

---

### KI-ACS-010 — The store's test vocabulary is Python-only, so 29 web-app ACs are unvalidatable landmines

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 2
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `config/ac_store_schema.json` → `test_spec[].framework` and
  `test_spec[].type`, against the ACs under `docs/acceptance-criteria/ux-prototyping/`
  and `docs/acceptance-criteria/build_pipeline/BP-1400-web-app-ci-gate/`; **and the
  identical pair** in `config/test_requirements.schema.json` →
  `$defs.test_entry.properties.framework.enum` (`:74`) and `...type.enum`

**Symptom.** `test_spec[].framework` permits exactly `unittest` and `pytest`; `test_spec[].type`
permits exactly `unit`, `integration`, `e2e`, `behavioral`. The repo now contains a Next.js
app under `leafcutter-web/`, and the ACs written for it declare the tests that app actually
uses — `framework: vitest` (40 entries), `framework: playwright` (2), and `type: component`
(12). None of those three values is in either enum, so **every one of those records fails
the store schema right now**, on `main`, unmodified.

**Why nothing has caught fire.** The required `AC store valid` job is diff-scoped by
design — `ci.yml:210` explains the choice, and it is a defensible one. The consequence is
that a record can be invalid indefinitely and cost nobody anything until the moment
somebody edits it for an unrelated reason, at which point they inherit a failure they did
not cause and cannot fix without either widening the schema or falsifying their own test
contract. `ci.yml:212` states the intended bargain plainly — *"Touch a broken record and
you own it"* — which is a fair rule for 57 orphaned children and an unfair one here,
because these 29 records are not malformed. They are correct descriptions of real tests
that the schema has no vocabulary for.

This is the exact shape BO-2900g-3's MIGRATE-DO-NOT-DEFER constraint was written against:
*"'The hook validates staged files only, so existing records are not invalidated in bulk'
is not a mitigation — it converts an immediate, visible breakage into a landmine that
fires on whoever next edits an untouched record for an unrelated reason."* Here the
narrowing was never a decision at all; the schema simply predates the web app.

**Evidence.** 2026-08-25, at `d37687ff`, whole-store run:

```
$ python scripts/ac_store/validate_ac_schema.py docs/acceptance-criteria
AC schema validation FAILED:
  ... 28 files: schema violation at test_spec ...
```

Single-record reproduction, showing it is the enum and not a malformed record:

```
$ python scripts/ac_store/validate_ac_schema.py \
    docs/acceptance-criteria/ux-prototyping/UXP-596-decision-diamonds/UXP-601.yaml
AC schema validation FAILED: ... 'framework': 'vitest', 'type': 'component' ...
exit: 1
```

28 files fail the schema validator; a 29th carries the same vocabulary and is caught only
by the stricter hook (KI-ACS-009). The whole-store run was only possible at all because
KI-ACS-001 was fixed on 2026-08-19 — before that the bare-directory form exited 0 without
reading anything, which is why a population this size went unnoticed.

**Second occurrence, 2026-08-25 — the same gap exists in a second schema, and the two are
coupled.** `config/test_requirements.schema.json` `$defs.test_entry` carries a
byte-identical `framework` enum (`["unittest", "pytest"]`, `:74`) and `type` enum
(`["unit", "integration", "e2e", "behavioral"]`), also under `additionalProperties: false`.
That schema governs the `## Test Requirements` block in a **ticket** body.

The coupling is `generate_ticket_from_ac.py::_test_descriptors_from_spec` (`:1451-1454`),
which copies the AC's `test_spec[].framework` and `[].type` straight through onto the
emitted ticket descriptor:

```python
if item.get("framework"):
    entry["framework"] = item["framework"]
if item.get("type"):
    entry["type"] = item["type"]
```

So widening only the AC schema does not finish the job. A web-app AC would validate,
`/build-ac` would generate a ticket carrying `framework: vitest` / `type: component`, and
those are values the ticket schema forbids — the defect would move one step downstream
rather than being fixed.

That downstream failure would be **silent**, which is the worse half.
`test_requirements.schema.json` is enforced by no hook and no CI gate; it is a declared
contract cited in `templates/agents/test-writer.md` and pinned by two unit tests
(`test_bo_2900g_3`, `test_bo_2900g_4`). Nothing would refuse the malformed ticket — the
generator would simply emit a descriptor violating the contract `test-writer` is
instructed to conform to.

**One precision about the affected records.** They are web-app ACs but not exclusively
web-app *tests*: `BP-1400c-1` pairs a Playwright e2e entry with a `pytest` entry targeting
`unit_tests/build_pipeline/` (it asserts the CI workflow wires the route-smoke job and does
not set `continue-on-error`). Across the 28 validator-visible records the entries are 40
`vitest`, 2 `playwright`, 1 `pytest`. A record is refused if *any* single entry uses an
unlisted value, so a mixed-stack AC is refused on its JS half alone.

**Fix direction.** Widen both enums rather than rewriting 29 records to say something
untrue about themselves: add `vitest` and `playwright` to `framework`, and decide
deliberately whether `component` joins the level axis or those 12 entries move to an
existing level. Note the axis question is genuine and should not be settled by reflex —
`component` is a test **level** (heavier than a unit test, lighter than e2e, renders a
component in a DOM), so it belongs on `type` and not on `angle`; adding it to `angle`
would repeat the level/kind muddle BO-2900g-3 exists to have removed. Whichever way it
goes, per BO-2900g-3 the change must move the affected records in the same commit, not
leave them for whoever touches them next.

**Do both schemas in the one change, and add a test asserting the two vocabularies are
equal.** They are hand-duplicated today with nothing holding them in step, which is how
they drift apart again the moment one is edited alone. Because
`config/ac_store_schema.json` is a package surface, the change needs an AC declaring
`package_surface: true` or `check-package-surface-declaration` will refuse the commit.

**Where to build it.** Prefer **AR-100** ("Every part of your codebase has a specialist who
genuinely owns it") over a standalone `ac_store` patch. AR-100's criteria require that
there be "no unclaimed technologies where the system quietly falls back on whoever happens
to be nearby", and this is its first concrete instance — the repo gained a TypeScript web
app and the store's test vocabulary never followed. Patched as three enum values, the next
JS tool reproduces it; built as "every vocabulary admits the technologies this repo ships",
it does not.

**Related.** KI-ACS-009 (the pre-flight is weaker than the gate — the reason a
locally-clean folder run does not clear these). BO-2900g-3 (the MIGRATE-DO-NOT-DEFER
constraint this violates). `ACS-200h`, named at `ci.yml:215` as the unbuilt whole-store
backstop, is the check that would have surfaced this on day one.

---

### KI-ACS-011 — `documentation_triggers: []` is refused on an L2 while `null` is accepted, so declaring "no documentation needed" is uncommittable

- **Severity:** medium
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/ac_store/validate_ac_schema.py:238-260` — the BO-2200a-5 L1-only constraint and its `is not None` guard

**Symptom.** The L1-only rule is entered only when the field is present **and not null**:

```python
if "documentation_triggers" in data and data["documentation_triggers"] is not None:
    ...
    if ac_level != "L1":
        errors.append("... permitted only on L1 ACs ...")
```

So an L2 that omits the field passes, an L2 that sets it to `null` passes, and an L2 that
sets it to `[]` is refused. All three mean the same thing — this record carries no
documentation obligation — and the rule's own purpose (BO-2200a-5: obligations are
declared at feature level) is untouched by an empty list. The check keys on presence, not
on whether an obligation is actually being asserted.

**Evidence.** The same 2026-08-25 whole-store sweep that surfaced KI-ACS-010 refused
**8 records**, all in `testing-quality/TQ-300-tooling-coverage-recovery`: `TQ-300a-1`,
`-a-2`, `-a-3`, `-b-1`, `-b-2`, `-b-3`, `-c-1`, `-c-2`. Every one is `level: L2` with
`documentation_triggers: []` **and** a `documentation_rationale` — e.g. *"Internal test
coverage for existing tooling; no user-facing behavior is added, so no how-to or diagram
adds value."*

Note the asymmetry that makes this look unintended rather than strict: the author's prose
justification for adding no documentation is accepted on an L2, while the machine-readable
form of the same statement is rejected.

**Fix direction.** Two defensible answers, and it is a convention call for whoever owns the
enrichment fields rather than an obvious bug fix:

1. **Treat `[]` as `null`** — change the guard to skip when the list is empty, so the rule
   fires only on a record actually asserting a trigger. Keeps the eight records as written.
2. **Strip the field from the eight** and keep the rationale — if the rule is meant to
   prohibit the field's presence at L2 outright, regardless of value.

(1) is the smaller change and preserves an explicit "considered, none needed" signal that
(2) discards. Either way the eight records and the rule must be settled together; fixing
one without the other leaves the store inconsistent with its own validator.

**Related.** Same sweep, same cause of invisibility as KI-ACS-010: the whole-store run only
became possible when KI-ACS-001 was fixed on 2026-08-19, and `AC store valid` is
diff-scoped, so these eight sit dormant until someone edits one for an unrelated reason.

---

### KI-ACS-012 — 193 approved code-AC leaves have no test contract, and each one blocks the next person to touch it

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-08-25 (measured) · **Last seen:** 2026-08-25
- **Where:** the AC store as a whole, against `check-ac-schema`'s rule *"approved code
  AC must declare a test contract"* (`_ac_schema_validators.py`)

**Symptom.** 193 records are simultaneously `readiness: approved`, `status: active`,
`change_target: code`, leaves (`covered_by: []`), and carry **no `test_spec` and no
`test_required: false`**. Every one of them fails `check-ac-schema` — the strict hook the
required `AC store valid` job runs — the moment it appears in a commit's index.

They are invisible today for the usual reason: the AC hooks read the **staged index**, not
the store. An untouched violating record is structurally unreachable, so `main` is green
while 193 records are individually unmergeable.

**Why this is worse than an ordinary backlog.** The cost does not fall on whoever created
it. It falls on the next person to edit that record for an unrelated reason — a typo, a
`covered_by` back-link, a component rename — who then cannot commit until they author a
test contract for somebody else's acceptance criterion. That is a tax on exactly the
maintenance work the store most needs, and it is the same forward-ratchet shape already
recorded in KI-ACS-010 and in `CLAUDE.md` → "AC-store commits — stage the parent alongside
the child".

**Evidence.** Measured 2026-08-25 at `fd502a7b` by walking the store and applying the
hook's own predicate:

```
approved ACTIVE code-AC LEAVES with no test contract: 193
  ac-store            49        knowledge-management 12
  guardrail-engine    37        persona-management   12
  ac-driven-dev       21        ticket-creation       9
  build_pipeline      20        build-orchestration   6
  testing-quality     14        infrastructure       13

work_status todo: 165   done: 28
```

**The 28 already marked `done` are the sharper half.** Approved, code, leaf, finished —
and no statement anywhere of what would have proven it. They cannot be triaged by reading
the contract, because there isn't one; each needs its criteria read against whatever code
was actually written. That is a strictly harder job than the 165 `todo` records, where the
contract can still be authored before the work.

**Found by hitting one.** `TKT-500f-7` blocked a commit on 2026-08-25 during unrelated AC
authoring — the amendment touched the file, the file entered the index, and the rule fired
on a record nobody in that change had written. It was fixed properly (five descriptors
authored from its own Gherkin, not silenced with `test_required: false`). The sweep that
followed found `TKT-500f-6-i`, `-6-ii` and `-6-iii-a` armed the same way in the same
folder, and then 193 store-wide.

**Fix direction.** Do **not** bulk-add `test_required: false` — that converts an honest
blocker into 193 silent waivers and is the exact move `TKT-500g` was authored to forbid.
Two honest options, in order:

1. **Measure and ratchet first.** Land the count as a test with a `HIGH_WATER_MARK`, the
   way `KM-ADM-005` did for `KI-KM-002`, so the population cannot grow while it is being
   drawn down. Cheap, and it stops the bleeding.
2. **Drain by component**, authoring real contracts. `ac-store` (49) and
   `guardrail-engine` (37) are 45% of the total between them.

A third option worth considering explicitly rather than by default: if the rule is right
but the enforcement point is wrong, the gate could warn on an untouched violating record
and block only on a newly-created one. That keeps the ratchet without taxing maintenance.
It is a real trade — it also means the 193 never surface again on their own — so it should
be a decision, not a drift.

**Related.** `KI-KM-002` (244 of 607 done ACs with no covering test — the same question
asked of tests rather than of contracts; a record can appear in both). `KI-KM-008` (241
`todo` records with a covering test — the store lying in the opposite direction).
`KI-ACS-010` (the other diff-scoped landmine population found the same day).

---

### KI-ACS-013 — `delivers_to` and `expects_from` are the two ends of one edge keyed on different things, so the forward half is not traversable and nothing validates either

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `config/ac_store_schema.json` (the `delivers_to` / `expects_from` declarations);
  `scripts/ac_store/validate_ac_schema.py`; `templates/scripts/commit_guardian/check_ac_schema.py`

**Symptom.** You cannot ask the store "what consumes this criterion?" and get an answer from
the criterion itself. You have to build a reverse index over every record in the store, which
is what had to be done to answer that question for a single record on 2026-08-25.

**Root cause — the two ends of the edge are keyed on different things.** Measured across all
3,376 records:

```
delivers_to entry shapes            expects_from entry shapes
  714  [agent, contract]              1651  [ac_id, contract]
   51  [ac_id, agent, contract]         46  [agent, contract]
   14  [ac_id, contract]               119  {}          <- empty dict
    3  [<bare AC id as the KEY>]         7  [<bare AC id as the KEY>]
```

`expects_from` is **AC-keyed**; `delivers_to` is **agent-keyed**. These are supposed to be the
reverse of each other. An agent name does not identify a record, so the forward direction
cannot be walked: `expects_from` gives you "which criterion produces what I need", and
`delivers_to` gives you a role name shared by hundreds of records.

**The store has already voted.** 65 `delivers_to` entries carry an `ac_id` key that no schema
documents and no validator reads — 51 alongside `agent`, 14 instead of it. Authors reached for
the missing field and added it themselves.

**Nothing validates either field.** `config/ac_store_schema.json` accepts
`null | string | object (additionalProperties: true) | array`. `validate_ac_schema.py` and
`check_ac_schema.py` contain **zero** occurrences of `delivers_to`. So:

- **29 `delivers_to.agent` values name no registered agent** (60 are registered). Crucially,
  most are **not errors** — `finalize-feature` (×6), `create-ticket` (×6),
  `diagram-classifier` (×5), `build-feature` (×2), `create-ac-workflow`, `ci`, `eval-runner`.
  These name a real consumer that simply is not an agent: a workflow, a CI job, a runner.
  One genuinely is malformed: `TKT-100g` carries
  `agent: "product-owner | business-analyst-v3"`, two names in one string.
- **119 `expects_from` entries are empty dicts** — a contract declaring nothing.
- **10 entries across both fields are shape-malformed**, with a bare AC id used as the dict
  *key* rather than as a value (`BP-006a-1`, `BP-006a-2`, `BP-006b-1`, `BP-006b-2`,
  `BP-006c-1`, `BP-006c-2`, `UXP-600` ×3).

**Why "restrict `agent` to the registry" is the wrong fix on its own.** It is the obvious
first idea and it would refuse 29 records, of which roughly two-thirds name a legitimate
non-agent consumer. That mistakes *not an agent* for *wrong*, and would push authors to name
a plausible agent instead of the true consumer — strictly worse information. The precedent
worth copying is `ADR-035`, which made the fast lane's producer roster **data** rather than
a hardcoded literal while keeping it closed; the equivalent here is a declared consumer
vocabulary that admits workflows and CI, not the agent registry alone.

**Fix direction.** Three separable pieces, most valuable first:

- **Document `ac_id` on `delivers_to` and make it the edge key**, mirroring `expects_from`.
  That is what makes the graph traversable in both directions, and 65 records already do it.
  `agent` stays as useful colour — which role will do the work — but stops being the identity.
- **Validate what is present.** An `ac_id` must resolve to a record in the store; an `agent`
  must resolve against a declared consumer vocabulary wider than
  `config/agent_registry.json`. Follow `ACS-100i-9`'s shape: one shared helper imported by
  both entry points, one format string, no second list in the JSON schema.
- **Refuse the malformed shapes** — the 10 bare-AC-id-as-key entries and the 119 empty
  `expects_from` dicts. These are unambiguous, and unlike the 29 they have no defensible
  reading.

**Scope note.** `assigned_agent` is getting exactly this treatment right now
(`ACS-100i-9..11`, registry validation via a shared `_ac_agents.py`; `ADR-035` for the
roster). `delivers_to.agent` and `expects_from.agent` were not in that scope and remain
unvalidated, so the store now has one producer field that is checked and two consumer fields
that are not.

**What it costs today.** Quiet, but not small, and the quietness is the problem.

Nothing here breaks a build. The only live readers are `pr-reviewer`'s Cross-File Contract
Tracing and `ac-validator` §2d, both LLMs told to open the consuming file named in the
contract, so a wrong or absent value degrades a review pass rather than failing a gate.

**Raised from `medium` to `high` on 2026-08-26.** The first assessment weighed the blast
radius of a single bad value, which is genuinely low. That was the wrong unit. Three things
together make this a `high`:

- **It silently disables two review checks across the whole store.** `ac-validator` treats a
  contract gap as a **blocker** and `pr-reviewer` as a **high-confidence finding**. Point
  either at a contract naming no openable consumer and it has two options — skip, or invent
  a consumer. The first makes the check a no-op that reads as performed; the second produces
  a fabricated finding against correct work. Both are the false-green shape this repo exists
  to prevent, sitting *inside* the machinery meant to catch it.
- **The traversal gap has a compounding cost.** Every question of the form "what depends on
  this?", "is this AC terminal?", "what breaks if I change this contract?" requires a
  full-store scan. That is not a one-off inconvenience: it is a tax on every future
  reasoning pass over the store, and it is why an authoring session in 2026-08-25 had to
  build a reverse index over 3,376 records to answer that question for one record.
- **The store is actively drifting away from the fix.** 64% of populated `delivers_to`
  entries name their own `assigned_agent`, and 65 records have already invented an
  undocumented `ac_id` key. Every week this stays open, more records are authored to a
  convention the schema does not describe, and the eventual correction gets larger. The
  sibling field `assigned_agent` is being validated right now (`ACS-100i-9..11`), so the gap
  between the checked producer field and the unchecked consumer fields is widening rather
  than closing.

The severity reflects the store-wide, compounding, self-concealing character of the defect —
not the cost of any one wrong value.

**Related.** `KI-ACS-012` (approved code leaves with no test contract — the same shape asked
of `test_spec`). `KI-ACD-015` (`expects_from` is invisible to the build sequencer, so
ordering must live in `depends_on` — a separate defect, and the reason neither of these
fields should be used to express ordering).

---

### KI-ACS-014 — `reference_file_path` can name a symlinked build output that git does not track, and nothing checks it resolves to a source file

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `it_requirements.reference_file_path` in any AC record;
  `templates/scripts/commit_guardian/_ac_schema_validators.py` (no resolution check);
  `scripts/ac_store/generate_ticket_from_ac.py` (copies the value into `files_touched`)

**Symptom.** An AC's `reference_file_path` — the field that tells the implementer which file
the work lives in, and which the generator copies into the ticket's `files_touched` — can name a
path that exists on disk but is **not tracked by git**. Work done there is not wiped by the next
build. It is never committed at all.

**Evidence.** `BP-1100g-4` names `scripts/commit_guardian/commit_guardian.json`:

```
scripts/commit_guardian -> ../.leafcutter/scripts/commit_guardian
git ls-files scripts/commit_guardian                                 ->  (no output)
git ls-files templates/scripts/commit_guardian/commit_guardian.json  ->  tracked
```

`scripts/commit_guardian` is a symlink into the build-output tree created by `install_shims`.
The source is `templates/scripts/commit_guardian/`. An implementer following the AC literally
would register the new hook in the deployed manifest, watch it work locally — the deployed copy
is what the hooks actually load — and ship nothing.

**Why this is worse than the ordinary deployed-copy trap.** The familiar failure (KI-BP-004, and
the `.claude/agents` case corrected on the `BP-1100g-1` ticket) is *edit the output, lose it on
the next build*. There the change is at least visible in `git status` until then, so a routine
`git add -A` or a review catches it. Here the path is untracked, so:

- `git status` shows nothing,
- the commit contains nothing,
- the PR diff contains nothing,
- and every local check passes, because locally the change is real.

The failure is silent at every layer that would normally notice, and it presents as "the work is
done and working" right up until someone else pulls.

**It is not a flaw in this AC's authoring.** `BP-1100g-4`'s own constraint explains that the
primary implementation is a new module and that `reference_file_path` *must resolve to an
existing file* — the field's contract forces the author toward whatever path exists today, and
the deployed symlink resolves while the not-yet-created source module does not. The field's
validation rule ("must exist") and its purpose ("the file you will edit") are in tension, and the
rule that is mechanically checked is the one that does not matter.

**Scope.** Not yet measured across the store. The exposure is any AC whose `reference_file_path`
points under `scripts/commit_guardian/`, `scripts/doc_compliance/`, `scripts/feedback/`,
`.claude/`, or `.leafcutter/` — the symlinked shim roots listed in `build.py`'s `install_shims`
output. Worth a sweep; deliberately not asserted here without one.

**Fix direction.** Add a resolution check to `check-ac-schema`: `reference_file_path` must be a
path `git ls-files` reports as tracked. That is one call, it is exact, and it catches every
member of this family rather than the symlink roots someone remembers to enumerate. A path that
exists but is untracked should fail with the tracked source suggested where one can be inferred
(`scripts/X/...` → `templates/scripts/X/...`).

Then resolve the field's tension, which the check will expose rather than fix: either allow
`reference_file_path` to name a file the work will *create* (a `reference_file_status: planned`
sibling), or rename the field to what it currently means — the nearest existing anchor — and give
the generator a separate, honest surface field. As long as one field means both "where to look"
and "what to edit", tickets will keep being generated with the wrong one.

**Related.** `KI-ACS-002` (the generator copies this value into `files_touched` and the readiness
report passes it on a count, so nothing downstream catches it either). `KI-ACS-009` (a rule that
lives in `templates/` while agents grep the deployed copy — the same source-versus-output
confusion, one layer up).

**Pattern:** a required field validated for existence but not for the property that makes it
useful, where the wrong answer is silent at every layer that would normally catch it.

---

### KI-ACS-015 — A `test_spec` descriptor has no link to the criterion it was promised for, so "which behaviour is this proof for" is unrepresentable

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `config/ac_store_schema.json` → `properties.test_spec[]`

**Symptom.** A `test_spec` entry carries `name`, `target_dir`, `framework`, `type`, `angle` and
`description`. It carries **nothing identifying which Then clause it was written to prove.** An
AC with four criteria clauses and four descriptors records no mapping between them; the pairing
exists only in the author's head and, loosely, in the prose of `description`.

**Where it bites.** `BP-1100g-4` requires a refusal naming *"the piece of work, the stated
behaviour, and the kind of proof that was promised and never claimed."* Two of those three are
directly available — the AC id, and the `angle`. The third is not derivable from the store at
all, so the AC as written cannot be satisfied exactly. That ticket resolves it by approximation
(name the AC leaf and its `criteria`, plus the descriptor's `description`), which is adequate for
L2/L3 leaves where one leaf is roughly one behaviour, and explicitly forbids the implementer from
adding a `criterion_ref` field as an unscoped schema change.

**Why medium and not low.** It is fine today because leaves are small. It stops being fine in two
directions that are already in motion: an L2 with several distinct Then clauses cannot say which
descriptor covers which, and any future check comparing promises against claims per-behaviour —
which is precisely the direction `BP-1100g` is heading — has to operate per-AC instead, coarsening
its own signal. The approximation is also invisible: nothing marks the resulting refusal message
as approximate, so it reads as precise.

**Fix direction.** An optional `criterion_ref` on the descriptor, identifying the clause by index
or by a short authored slug. Optional matters — 3,000+ existing descriptors have no such link and
a required field would fail the store wholesale. Then have `it-po` populate it going forward, and
let any per-behaviour consumer degrade explicitly to per-AC when it is absent, rather than
silently.

Do **not** infer the mapping by matching descriptor `description` text against clause text. That
is the same "read the prose and guess" move this component family exists to eliminate, and it
would be a guess presented as a citation.

**Related.** `KI-ACS-013` (`delivers_to`/`expects_from` keyed on different things — the same
class: an edge the store implies but does not represent). `KI-ACS-012` (leaves with no
`test_spec` at all).

**Pattern:** a record that carries the *what* of a promise but not the *what for*, where the
missing half is only noticed by the first consumer that needs to cite it.
