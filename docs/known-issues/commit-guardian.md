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
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/scripts/commit_guardian/check_ac_parent_covered_by.py:134-150`, and the AC hook family generally

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

**This is the exact failure GE-120 fixed in the sibling module on the same day.** That work
removed the silent `except (json.JSONDecodeError, OSError): pass` and the `.exists()`
fallthrough from `doc_type_validators.py`, on the stated grounds that "a guard that quietly
answers a different question than the one it was configured with is enforcing a rule nobody
wrote." `diagram_type_validators.py` is the file GE-120 copied its ancestor-walk pattern
*from*, and it still has the behaviour that was removed.

**Fix direction.** Mirror GE-120 the rest of the way: raise a `FileNotFoundError` naming
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

### KI-CG-003 — `check-contract-shrinking` has no merge-commit awareness, so it blames the base branch's history on the merge

- **Severity:** high
- **Status:** FIXED 2026-08-18 — pending deletion once merged
- **Occurrences:** 2
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/scripts/commit_guardian/check_contract_shrinking.py:165-189` (`_get_staged_diff`)

**Fixed.** Hit a second time merging `origin/main` into `fix/ac-schema-conformance-33`,
blocked on the same `#461` test deletions. `_get_staged_diff` now narrows to files
differing from BOTH parents during a merge, matching the four sibling hooks.

Two things the original fix direction above does not mention, both found by review before
the fix landed:

- **Scoping the whole diff breaks the guard's conjunction.** The predicate spans two
  disjoint file sets — production changed AND a test weakened. Narrowing both halves lets
  an author take the base branch's production edit verbatim (removing it from scope) and
  skip the tests it broke; the pairing never forms. Production detection therefore stays
  on the full staged diff and only weakening detection is merge-scoped.
- **Three silent-pass paths.** Paths with spaces were split into two tokens, non-ASCII
  paths came back C-quoted (`core.quotePath` defaults true), and pathspecs after `--`
  resolve against CWD rather than the repo root. Each produced an unmatched pathspec, an
  empty diff, and a passing gate — an unmatched pathspec is not a git error. Fixed with
  `-z` NUL splitting and `:(top)` anchoring, plus a contradiction check that falls back to
  the full diff when a non-empty scope yields an empty diff.

Covered by `unit_tests/commit_guardian/test_ac_limits_merge_scope.py`
(`TestContractShrinkingMergeScoping`, `TestContractShrinkingMergeBehaviour`) — 17 tests,
including discriminating cases for each of the four defects above.

Delete this section once the fix is on `main`.

**Original report, kept for the record until deletion.**

**Symptom.** The guard blocks when a diff deletes test functions *and* touches production
files. It obtains that diff from a bare `git diff --cached`, with no check for `MERGE_HEAD`
and no comparison against the merge base. During a merge commit the staged diff is not
"what this commit changes" — it is everything the incoming branch changed since the fork
point. So merging an up-to-date `main` into a feature branch presents every test deletion
and every production edit `main` has accumulated as though the merging commit authored
them, and the guard blocks a commit whose own content is unrelated.

**Evidence.** Merging `origin/main` into `feat/bo-1500f-1-setup-dispatch-charter` on
2026-08-18 was blocked with 9 deleted test functions and 9 modified production files:

```text
[contract-shrinking guard] BLOCKED
  - test function deleted: 'test_ac3i_halts_when_a_batch_test_passes'
  - test function deleted: 'test_h2_red_baseline_cli_exits_0_when_all_red'
  ... (9 total)
Production files modified:
  - scripts/ac_store/done_proof.py
  - scripts/build_orchestration/fast_lane.py
  ... (9 total)
```

None of it belonged to the branch. Verified two ways: `git grep` for
`test_ac3i_halt_names_offending_ac_id` on `origin/main` returns nothing (so `main` deleted
it, in `#461`), and `git diff origin/main --stat -- scripts/` on the branch is **empty** —
the branch touches zero production files. `git diff origin/main -- unit_tests/ | grep "^-" |
grep "def test_"` is likewise empty: the branch deletes no test anywhere.

**Why it matters beyond the annoyance.** The only way past it is `SKIP=check-contract-shrinking`,
and the merge commit is exactly the commit where a genuine test deletion is easiest to hide.
Training people to skip this guard on merges disarms it at its highest-value moment. This is
the second guard in this file whose scope is "the git index" rather than "what changed here"
— see KI-CG-001 for the same root confusion in the AC hooks.

**Fix direction.** Detect a merge in progress (`.git/MERGE_HEAD` exists) and diff against
the merge base (`git diff $(git merge-base HEAD MERGE_HEAD)`) so only the merging branch's
own contribution is scanned — or skip the guard on merge commits explicitly and loudly,
which is at least honest about what is not being checked. A silent `--cached` on a merge is
neither.

---

### KI-CG-004 — Prose exemption disables entropy detection for WHOLE FILES, including executable Python under `templates/skills/`

- **Severity:** high
- **Status:** open — partially anticipated by `GE-123d-4-i` (draft), but that AC governs a *proposed* widening, not this existing behaviour
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/scripts/commit_guardian/check_secrets.py` — `_PROSE_FILE_PREFIXES` / `_is_prose_exempt`

**Symptom.** `ENTROPY_HIGH` is the only rule that catches an **opaque** credential — a
Stripe key, a JWT, a random API token — because such values carry no `password =`
style keyword for `GENERIC_SECRET` to match and no fixed prefix for `AWS_KEY` or
`PRIVATE_KEY`. That rule is switched off for entire files under four path prefixes.
The source comment states the scope plainly: *"Prose-only file prefixes — entire files
are exempt from entropy scanning."*

**Evidence.** A live-shaped token (`sk_live_…`, Shannon entropy **5.17**, threshold
4.5) run through the real `_is_prose_exempt`:

```
templates/skills/security-scanner/scripts/scan_secrets.py   EXEMPT — not reported
templates/skills/some-skill/scripts/helper.py               EXEMPT — not reported
tickets/00_inbox/TICKET-20260818-Example.md                 EXEMPT — not reported
docs/acceptance-criteria/guardrail-engine/GE-123.yaml       EXEMPT — not reported
docs/retrospectives/retro.md                                EXEMPT — not reported
scripts/build.py                                            reported
leafcutter-web/app/page.tsx                                 reported
```

**Why `templates/skills/` is the sharp edge.** It is on the prose list but it is not
prose — it holds executable Python, including the secrets scanner's own
`scan_secrets.py`. A credential pasted into any script under that prefix is
unreported by the very tool meant to catch it. The other three prefixes are genuinely
prose directories, so the exposure there is narrower, but a ticket is still a file a
developer will happily paste a token into while writing up an incident.

**Scope of the exemption, precisely.** It gates `ENTROPY_HIGH` only —
`AWS_KEY`, `PRIVATE_KEY`, `EXCHANGE_API_KEY` and `GENERIC_SECRET` still fire in these
paths. So the hole is exactly the class of credential that has no recognisable shape,
which is most modern opaque tokens.

**The exemption is far wider than four directories — the match is NOT root-anchored.**
`_is_prose_exempt` tests `("/" + prefix) in path_str`, a substring test against the
whole path. So the four prefixes are really four *directory names*, matching at **any
depth, in any subtree**. Measured with the same 5.17-entropy token:

```
tickets/00_inbox/note.md                    EXEMPT   (intended)
leafcutter-web/tickets/app.py               EXEMPT   (not intended)
src/vendor/tickets/handler.py               EXEMPT   (not intended)
some/deep/nested/docs/retrospectives/x.py   EXEMPT   (not intended)
unrelated/templates/skills/evil.py          EXEMPT   (not intended)
src/app.py                                  reported
```

This repository already ships `leafcutter-web/`. Any feature directory named
`tickets/`, any vendored dependency containing one, and any nested `templates/skills/`
loses entropy detection silently — for `.py` as readily as for `.md`. The original
framing of this issue (four known prose directories) understated it: the reachable
surface is any path containing one of those four segment names.

**Corollary — a test can be written that passes for the wrong reason.** A fixture
placed under any such path measures the exemption rather than the scanner. This is a
live authoring hazard, not a theoretical one; it is called out as a hard
`it_requirement` in the `GE-123a` and `GE-123c` subtrees for exactly that reason.

**Fix direction.** Three separable changes, in descending order of payoff:

- **Anchor the match at the repository root.** Compare path *segments* from the root
  rather than substring-testing the whole path. This is the single change that shrinks
  the surface from "any path containing these names" back to the four directories the
  exemption was written for, and it is the cheapest of the three.
- Gate the exemption by **file kind**, not only by path. A `.md` under `tickets/` is
  prose; a `.py` under `templates/skills/` is not. This closes the executable-code case
  that anchoring alone leaves open, since `templates/skills/` genuinely is on the list.
- Make the exemption **per finding** rather than per file. The existing rule discards
  every entropy finding in a matching file; the narrower rule is to discard only
  findings whose high entropy is explained by a benign token — which the module
  already computes for `TICKET-…` / `EPIC-…` identifiers and could extend.

**One more thing the fix must not trip over.** `_filter_prose_findings` passes
`finding.excerpt` as the line to test, and `scan_file` sets
`excerpt = line.strip()[:120]` (`scan_secrets.py:248` and `:254`). The exemption
therefore judges a **truncated** line: a benign explanatory token sitting past column
120 is invisible to it, so verdict can turn on line length alone. Any per-finding
rework needs the full matched value, not the excerpt.

**Relationship to in-flight work.** `GE-123d` proposes extending prose exemption to
`GENERIC_SECRET`, and `GE-123d-4-i` exists specifically to require a file-kind gate so
that widening does not inherit this defect. That is the right guard for the *new*
behaviour, but it does not repair the *existing* `ENTROPY_HIGH` exemption — this issue
covers that, and it should be fixed first so the new work is not built on top of it.

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
