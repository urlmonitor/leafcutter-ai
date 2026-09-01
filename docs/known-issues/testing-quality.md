---
title: "Known issues — testing-quality"
description: "Open, observed defects in the testing-quality component: the agent eval harness with its scoring and threshold gates, plus the test-isolation and verification-method defects that make a suite report the wrong answer — stale-module shadowing, incomplete fixtures, self-mirroring oracles, and verification that never asks what invokes the code. Recorded on sight so they are not lost, and read before adding new capability to this component."
type: reference
category: reference
status: active
created: 2026-08-18
last_updated: 2026-08-26
components:
  - testing_quality
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/how-to/prove-ac-done.md
---

# Known issues — testing-quality

Observed defects in this component that are **not yet fixed**. This file exists so a
defect noticed in passing can be recorded in seconds, without authoring a full
acceptance criterion for something nobody has decided to build yet.

## How to use this file

**Read it before adding new capability to this component.** Fixing what is already
broken takes precedence over building more.

**Adding an issue.** Append a new `### KI-TQ-NNN` section using the next free number.
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

### KI-TQ-001 — An unanswered eval row scores as an all-negative prediction, so a dead agent's floor is not zero

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `scripts/evals/run_agent_eval.py` — label-mode row loop, the `ModelInvocationError` handler

**Symptom.** When a model call fails or its reply cannot be parsed, the handler logs a
WARNING and sets `predicted = {}`. An empty prediction is then scored as *every axis
False*. For any gold row whose labels are all False, that is a **correct** answer. So a
row that never received a model answer can be recorded as a pass, and an agent that is
completely dead does not score 0% — it scores the all-negative fraction of its gold set.

**Evidence.** In a **locally passing** `pt-classifier` run (88.89%, threshold 70), rows
`clf-012` and `clf-014` each logged `model invocation/parse failed: No JSON object found
in model reply` and still printed `[PASS] ... exp=none got=none`. Two of the sixteen
"passes" had no model answer behind them; the honest figure is 14 of 16 answered rows.

The same arithmetic explains KI-TQ-002: the `pt-classifier` gold set has 4 all-negative
rows out of 18, and 4 ÷ 18 = 22.22% — exactly the score CI produces when no credentials
are present.

**Fix direction.** Treat a row carrying `parse_error` as **unscored** rather than as a
prediction: exclude it from the accuracy denominator and fail the run when unscored rows
exceed a small tolerance. Separately, an eval's floor should be stated explicitly —
compute the all-negative baseline for each gold set and require the configured threshold
to sit above it, so a threshold can never be cleared by silence.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M6.

---

### KI-TQ-002 — The CI eval job reports missing credentials as a low quality score

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `.github/workflows/agent-evals.yml:71` — `ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}`

**Symptom.** When the `ANTHROPIC_API_KEY` repository secret is unset, the env var is
empty, the `claude` CLI exits non-zero for every row, and each failure is absorbed by the
per-row handler in KI-TQ-001. The job then reports a **quality** verdict — "score 22.22%
below threshold 70.00%" — for a run in which no model was ever invoked. Nothing in the
output says "no credentials". A reader reasonably concludes the agent regressed.

**Evidence.** `Agent evals (affected)` is **not** a required status check. Verified
2026-08-18 against ruleset `17810993`, whose required contexts are exactly: `Lint (ruff)`,
`Component vocab style (components.json)`, `Test suite (pytest)`,
`Proof-of-done coverage check (BO-2500b)`, `Changelog entry present`, `AC store valid`.
So this does not block merges — it misinforms. It stays dormant until a PR touches the
trigger closure, then fails on every such PR, and fails dishonestly.

**Fix direction.** Detect the empty-credential case before running any row and fail the
job with an explicit infrastructure error, distinct from a threshold failure. A gate that
cannot run must say so rather than emit a number that looks like a measurement.

---

### KI-TQ-003 — The eval staleness gate asks you to stage a file that is gitignored

- **Severity:** low
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/scripts/commit_guardian/check_eval_staleness.py:156` (a commit-guardian hook, filed here because its subject is the eval workflow); `scripts/evals/results/.gitignore`

**Symptom.** On a stale result the hook prints `Re-run the affected eval(s) locally, then
re-stage the result:`. Re-staging is impossible: `scripts/evals/results/.gitignore` is
`*.json`, so no result file can ever enter the index.

**Evidence.** The gate nonetheless works, because `eval_selector.py` reads the result from
disk rather than from the index. Only the remediation message is wrong — which makes it a
documentation defect that costs the next person a confused minute, not a correctness one.

**Fix direction.** Reword the message to "re-run the eval so the on-disk result is fresh";
drop the staging instruction.

---

> **Entries `KI-TQ-004` … `KI-TQ-009` are recovered from an unmerged branch.** They were
> written between 2026-08-19 and 2026-08-25 while driving
> `EPIC-GE122UniquenessPassAndRepair`, into the parallel known-issues register PR #495
> invented (`KI-TQ-1` … `KI-TQ-7`), which lost every reconciliation conflict against this file
> and was discarded. The two registers turned out to be disjoint in subject matter — this file
> is entirely about the agent eval harness, that one entirely about test-isolation and
> verification-method defects — so the analysis below would have been lost with the branch.
> Every entry was re-verified against `main` at `37655862`, and each `Status` line says whether
> the code it describes is on `main` or only on the unmerged branch.
>
> One entry from that set was **dropped as no longer true**: it reported
> `test_ge_122e_1.py::test_goal_record_claims_a_new_id_and_its_folder_matches_origin_main`
> failing as a function of branch staleness, because it required `git diff origin/main --
> <folder>` to be empty. That assertion was amended on 2026-08-18 (before the entry was
> written) to a one-directional set difference — `missing = baseline_ids - current_ids`
> (`test_ge_122e_1.py:514`) — which tolerates `origin/main` growing ahead by design, and the
> baseline ref is now resolved from the first of `origin/main`, `main`, `HEAD^2` that exists.
> Both halves of the reported failure mode are gone.

---

### KI-TQ-004 — Bare-name `sys.modules` caching lets a stale deployed copy shadow the canonical module for a whole pytest session

- **Severity:** high — it can hide a real fix *and* a real bug, and it bit twice in one epic
- **Status:** open — code is on `main` and live
- **Occurrences:** 2 (same epic)
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-26 (re-verified against `37655862`)
- **Where:** `unit_tests/commit_guardian/test_commit_guardian_imports.py:85-105`
  (`_import_module_from_dir`), used at `:237`, `:334`, `:413`

**Symptom.** The helper caches modules in `sys.modules` under their **bare name**
(`_uniqueness_scanners`, not a package-qualified path):

```python
if module_name in sys.modules:
    return sys.modules[module_name]
...
sys.modules[module_name] = mod
```

Because `sys.modules` is process-global, the **first** load of that bare name in a pytest
session pins whichever copy existed at that moment for the rest of the run. Every later test
file doing `importlib.import_module("_uniqueness_scanners")` silently gets the pinned copy.

This repository keeps a canonical source tree (`templates/scripts/commit_guardian/`) and
deployed copies (`scripts/commit_guardian/`, `.leafcutter/scripts/commit_guardian/`) that
`build.py` regenerates. If the deployed copy is stale when the suite starts, the stale code is
what the whole session tests.

**Evidence — observed twice.**

1. A stale deployed copy raised `TypeError: Finding.__init__() got an unexpected keyword
   argument 'declared_states'` against source that had the field.
2. A correct fix to `_fast_scan_top_level_id` appeared not to work — the full suite reproduced
   the *old* bug — because a pre-`build.py` deployed copy had been pinned first.

Both cost real diagnosis time, and the second nearly produced a wrong conclusion about a fix
that was in fact correct.

**Why it is worse than an ordinary flake.** The failure direction is not consistent. A stale
deploy can make a good fix look broken (wasted effort) or a broken module look fixed (a false
green that ships).

**Detection.** If a fix verifies green in isolation but fails in the full suite — or vice versa
— suspect this before suspecting the fix. Compare the canonical and deployed copies directly:

```bash
diff templates/scripts/commit_guardian/<mod>.py scripts/commit_guardian/<mod>.py
```

**Workaround, and treat it as a standing rule.** Always run `build.py` before the full
`unit_tests/commit_guardian/` suite:

```bash
python3 scripts/build.py --target-dir <worktree_root> --force
```

**Fix direction.** Import sibling modules under a package-qualified or path-derived unique name
so two copies cannot collide in `sys.modules`, or clear the cached entry in a fixture teardown.
Per this repo's own guidance, fix it in the test files rather than a root `conftest.py` — a
global conftest has too wide a blast radius — and `importlib.reload()` is **not** a substitute,
because it masks cold-import bugs.

**Related:** `supervisor-system.md`'s `KI-SS-004` is the same hazard one layer up, at the
workflow runtime.

---

### KI-TQ-005 — Fixtures that never built the collection they assert over, three times in one epic

- **Severity:** high as a pattern
- **Status:** open as a pattern — the specific test files named below are **not on `main`**
  (they live on unmerged PR #495); the pattern and its diagnostic signature are what this entry
  is for
- **Occurrences:** 3 (one epic)
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-25
- **Where:** PR #495's `test_ge_122a_1.py` and `test_ge_122a_1_i.py`

**Symptom.** Three test files asserted properties of "a collection" while their fixtures never
created two, three, or four of its namespaces. They passed only because the fail-open they
should have caught was masking their own incompleteness:

| File | What the fixture omitted |
|---|---|
| `test_ge_122a_1.py::test_repaired_collection_passes_with_per_namespace_counts` | `tickets/` root and `ticket_lifecycle.json` |
| `test_ge_122a_1_i.py` (three tests) | `docs/architecture/adrs/`, `docs/architecture/diagrams/`, `ticket_lifecycle.json` |

The first of these was asserting *"a repaired collection passes"* over a collection that was
never there.

**Root cause / diagnostic signature.** Each was exposed only when the fail-open was closed —
which is the signature: **fixing a fail-open turns incomplete fixtures red.** Those failures
look exactly like a regression in the fix, and the tempting response is to weaken the new
assertion. That is backwards. In all three cases the assertions were correct as written and the
setup was short.

Note also how the second instance was mis-diagnosed at first. Only the work-items scanner logs
a warning on an unresolvable root (see `commit-guardian.md`'s `KI-CG-031`), so the visible
symptom named one missing file when three namespaces were actually unresolved. A silent failure
made an incomplete fixture look like a smaller problem than it was.

**Detection.** After closing any fail-open, expect newly-red tests and triage each with one
question: *is the assertion wrong, or was the fixture never complete?* Complete the fixture
without touching a single assertion and re-run. Green means the fixture was short. Still red
means the fix is wrong. **Wanting to change an assertion is the signal that you are about to
paper over a real defect.**

**Fix direction (pattern).** A shared fixture builder that constructs **all** of a collection's
namespaces by default, so a test must opt out of one explicitly rather than omit it by accident.
PR #495's `test_ge_122a_1_i.py` grew a `_resolve_non_ac_namespaces` helper doing exactly this,
with a comment warning against tidying it away.

**Pattern:** `docs/reference/false-green-mechanisms.md` — a test passing for the wrong reason,
where the bug and the test's blind spot are the same bug.

---

### KI-TQ-006 — A matcher widening measured by its own author's grep: estimated one false positive, actual twenty-three

- **Severity:** high as a pattern — the flawed measurement and the flawed code shared one author
  and one blind spot
- **Status:** open as a pattern. The specific instance is fixed and is recorded in
  `build-orchestration.md`'s `KI-BO-003`; **the general rule below has no enforcement** and that
  is why this stays open. `main` has since committed the same shape a second time — see
  `commit-guardian.md`'s final entry, whose own text records a per-marker cost generalised from
  the one marker that was measured.
- **Occurrences:** 2
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-26
- **Where:** `scripts/build_placeholder_detection.py` (`_is_marker_at_line_start`,
  `_LEADING_MARKER_PREFIX`)

**Symptom.** A matcher was widened. Its cost was estimated with a grep, and the estimate said
"one instance". The true cost was **23 false positives across 4,815 files**. The grep searched
for *bulleted* markers; the rule that shipped also accepted *bare indentation*:

```python
_LEADING_MARKER_PREFIX = re.compile(r"^\s*(?:[-*+]|\d+[.)])?\s*")
```

The bullet is **optional**, so bare indentation qualifies too — and in YAML block scalars and
wrapped markdown, *every* continuation line is indented. Any prose line beginning with the word
"placeholder" was flagged. **The shape that was never searched for is exactly the shape that was
wrong.**

**Evidence — three independent safety nets were green the whole time:**

| net | why it missed |
|---|---|
| 84 unit tests across two tripwire files | corpus authored from the same mental template as the grep |
| a canary asserting one file scans clean | that file happened to have no indented prose starting with the word |
| a full 3,729-test suite | nothing in it scans the AC store or agent templates |

A repo-wide before/after diff of the committed scanner against the working tree, over 4,815
files, is what actually measured it: 72 hits before, 94 after, **24 new — of which 23 were false
positives**, spanning 12 AC YAML files, 4 agent templates, a generated agent card, 4 tickets and
2 skill docs.

**Detection.** After changing any matcher, run it over the **whole repository** before and after
and diff the hit sets. Not a count — the actual set, with enough context to judge each new hit.
`git show HEAD:<file>` gives the baseline implementation, so this needs no branch juggling:

```python
before = load_module_from(git_show("HEAD:scripts/<matcher>.py"))
after  = load_module_from(worktree_path)
new    = after_hits - before_hits      # judge every element
```

**Fix direction (pattern).** For every matcher with a false-positive cost, keep a **repo-scale
canary** asserting zero hits over a large real corpus, not a handful of hand-picked files.
`test_ge122b_acceptance_criteria_tree_placeholder_hits_are_zero` scans all 3,092 AC YAML files
in ~1.3s. Scope it to the marker under test — that tree has legitimate `todo` hits which a naive
zero-hits assertion would have gone red on, pushing the next author to break `TODO` instead.
And measure **per marker**, never in aggregate: the second occurrence tightened the marker
responsible for 2 of 55 hits and left untouched the one responsible for 42.

**The generalisation, since this keeps being rediscovered:** an estimate produced by the person
who wrote the rule tests their model of the rule, not the rule. Only running it over data nobody
curated can falsify it.

---

### KI-TQ-007 — Six review rounds verified a component without once asking what invokes it

- **Severity:** critical as a pattern — the largest miss in the GE-122 review, and the one every
  other finding was standing on
- **Status:** open as a pattern. The **instance** is `commit-guardian.md`'s `KI-CG-021`. The
  **class** overlaps `build-orchestration.md`'s `KI-BO-011` (an unreachable file serving as a
  criterion's proof) and `KI-BO-028`, but is not the same: those are about a *test* pointed at
  dead code, this is about a *review method* that never leaves the source tree. Filed separately
  and cross-referenced rather than folded in, because the remedy below — a registration test on
  every hook AC — is not implied by either.
- **Occurrences:** 1 (six rounds)
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** the adversarial review method itself; instance at PR #495's
  `check_identifier_uniqueness.py`

**Symptom.** Rounds one through five of adversarial review each found real defects under a green
suite, and each verified the fix by importing the module or running the script directly. Round
six asked a different question — *what calls this in production?* — and the answer was **nothing**
(see `KI-CG-021`). Five rounds of increasingly careful verification had been measuring a
component that could not fire.

Every individual verification was accurate. **None of them was the question.**

**Detection.** For any gate, hook, or runner, verification is not complete until you have
answered, with a grep and not from memory:

1. What config registers this? (`commit_guardian.json`, `.pre-commit-config.yaml`, a CI workflow
   — name the file and the line.)
2. Does it survive `build.py` into a consumer layout? Build one in `/tmp` and run it.
3. Does the **production entry point** produce the observable effect — the exit code, the block,
   the message? Not the function. The entry point.
4. Is the output actually *seen*? A passing `pre-commit` hook's stdout is discarded
   (`KI-CG-026`).

**Fix direction (pattern).** Every hook AC should carry a registration test: assert the hook's id
appears in the deployed `.pre-commit-config.yaml` and that its script resolves. That is a
three-line test which would have failed on day one of the epic and saved six rounds.

**The general form:** *"does the code work"* and *"is the code reachable"* are different
questions, and a test suite answers only the first. Nothing in 3,772 passing tests could
distinguish this gate from a gate that had never been wired up, because nothing in it looked
outside the source tree.

---

### KI-TQ-008 — A repository-global tree-purity guard false-positives under concurrent agents

- **Severity:** medium — it manufactures failures indistinguishable from real ones
- **Status:** open — **the test file is NOT on `main`**; it lives on unmerged PR #495. Filed
  because the guard is good practice and will be copied, and the scoping defect should be fixed
  before it is.
- **Occurrences:** 3 (one session)
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** PR #495's `test_ge_122e_3.py` — `tearDownModule`

**Symptom.** The module has a `tearDownModule` that proves it never wrote to the real repository
— it snapshots `git status --porcelain` before the module runs and compares afterwards. The
guard itself is good practice: every fixture operates on a `shutil.copytree`'d tempdir, and this
catches a bug in the test file's own fixture code escaping the tempdir.

The problem is that `git status --porcelain` is **repository-global**. The guard cannot
distinguish "this module escaped its tempdir" from "some other process touched the tree", so
**any** concurrent activity trips it:

```
RuntimeError: The real repository working tree changed during this test
module's run.
BEFORE: ... (12 modified files)
AFTER:  ... + tickets/.../03_TICKET-20260818-GE-122a-2.md
```

That diff is a *different* agent editing a *different* ticket. Nothing was wrong.

**Evidence.** Observed three times in one session while several agents worked in one worktree.
Each occurrence cost an agent a diagnostic detour and a re-run. Two agents correctly identified
it as spurious; the danger is the third that does not — the failure is loud, alarming, and points
at the wrong thing. The mirror-image risk is an agent learning to dismiss this error and thereby
missing a real escape.

**Detection.** Compare the BEFORE and AFTER strings in the error. If the only difference is a
file this test module has no business touching, it is interference.

**Workaround.** Do not run the suite while another agent is writing to the worktree, and do not
write to the worktree while a suite is running. One writer at a time.

**Fix direction.** Narrow the guard's scope: snapshot only the paths this module could plausibly
touch (`docs/acceptance-criteria/`, `docs/architecture/`, `tickets/`), or diff only against paths
under `_REPO_ROOT` that the module's own fixtures reference. **Keep the guard** — it is the right
idea, just too wide.

---

### KI-TQ-009 — A test-local oracle that duplicated the production bug it was written to detect

- **Severity:** medium as a pattern, even where the instance is fixed
- **Status:** open as a pattern — **the instance is NOT on `main`** (PR #495's
  `test_ge_122e_3.py`) and is fixed on the branch; the pattern has no enforcement anywhere
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** PR #495's `test_ge_122e_3.py` (`_read_lifecycle_folder_names`) against its
  `_work_items_scanner.py`

**Symptom.** The test file defined its own local `_read_lifecycle_folder_names` helper carrying
the **identical basename-collapse defect** as the production function it was verifying. The exit
gate's oracle shared the blind spot of the code it was written to check.

It passed for exactly the reason the production bug was invisible: every real lifecycle folder
happens to sit one level under `tickets/`.

**Why this is a class, not an incident.** This is the same bias that once let a `files_touched`
parser defect survive an entire epic in this repository — synthetic fixtures and hand-written
oracles reproduce the implementation's assumptions, so they cannot falsify them. It is also
`KI-TQ-006` in miniature: a check authored from the same mental template as the thing it checks.
The branch committed it *inside the entry describing the fix for it*, which is the sharpest
available demonstration that knowing about the pattern does not prevent it.

**Detection.** When a test computes an expected value, ask whether it derives that value
**independently** or re-implements the logic under test. An oracle that mirrors the
implementation proves only self-consistency.

**Fix direction (pattern, not instance).** Derive oracles from the data, not from a
reimplementation — read the config's full declared paths rather than recomputing folder
discovery. Where a helper must be shared between a test and production code, **import the
production one**, so a bug shows up as a failure rather than as agreement.

---

### KI-TQ-010 — Nothing in the build pipeline asks whether a passing test is able to fail, and for a negative control that is the only question that matters

- **Severity:** high
- **Status:** open
- **Occurrences:** 2
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-31
- **Where:** `templates/agents/test-writer.md` (red-baseline protocol);
  `templates/agents/test-runner.md`; `templates/workflows-js/build-feature.js` `phaseOrder`;
  `CLAUDE.md` → "TDD Order — test-writer Must Precede python-coder"
- **2026-08-31: a second occurrence, in a different shape and with a shipped consequence** —
  see the end of this entry. Four green tests, an AC marked `done`, and the behaviour never
  worked; found only when the unfixed code broke a live 27-ticket build.

**Symptom.** The pipeline's only evidence that a test constrains anything is the **red baseline**:
the suite must fail before the coder runs. That check is structurally unavailable to a whole class
of test, and for that class nothing replaces it — a test that can never fail passes every phase,
every gate, and CI.

**The class.** A *negative control* asserts an **absence**: that some new input changes no
outcome. If the implementation is correct, the test is **green on arrival by construction**. There
is no red phase to capture. `CLAUDE.md`'s rule that a green `test-writer` phase is a TDD-order
violation inverts here — green is the expected pass — so the one mechanism that would have asked
"can this fail?" is not merely absent, it is documented to mean the opposite.

**Evidence.** `BP-1100g-3-i` (merged 2026-08-26, `8f55fd25`), four tests asserting that the
`# angle:` proof-kind tag feeds no pass, done, or eligibility decision. `test-writer` reported
all four green; `test-runner` re-ran and confirmed; `python-coder` signed off a correct no-op.
All three were accurate and none had reason to ask the next question.

A mutation proof run afterwards injected the exact leak the AC forbids — plumb `angles` through
`_scan_single_test_file`, then treat angle-carrying records as passing in `_classify_outcomes` —
and one of the four did not notice:

| test | angle | consumption leak | + plumbing leak | deployed leak |
|---|---|---|---|---|
| 1 | `criterion` | RED | RED | — |
| 2 | `seam` | green | RED | — |
| 3 | `real_artifact` | green | **GREEN** | — |
| 4 | `reachability` | green *(correct — deployed path)* | green *(correct)* | RED |

Test 3 carried **AC-5, the AC's headline clause** (*"removing every kind tag from the suite
changes no run outcome and no completion decision anywhere"*). Its only *failing* fixture test
carried no angle tag, and the likeliest real leak — "an angle-tagged test proves what it claims,
so count it passing" — is observable **only** on a test that is both tagged and failing. The
whole-suite strip test could not observe the leak it existed to forbid. Fixed in-flight by tagging
that fixture; the point of recording it is that nothing in the pipeline would have found it.

**Why the usual defences do not cover this.** The test had every mark of quality: real on-disk
fixtures, `yaml.safe_dump` rather than hand-typed YAML, the real production entry point, and
explicit anti-vacuity assertions (*"otherwise the equality assertion above is vacuous"*, *"otherwise
this test proves nothing"*). Those assertions guard against the fixture being empty or trivial.
**None of them can detect that the fixture, while non-trivial, does not span the failure mode.**
Self-certified non-vacuity is not falsifiability.

**Why high.** The repository's founding concern is work marked done that never runs. A negative
control that cannot fail is that defect *inside the instrument built to detect it*, and it is
self-concealing in the worst way: it is green, it stays green, and its greenness is later cited
as proof the invariant holds. `BP-1100g-4` will shortly consume this same axis in a commit-time
refusal, so the invariant `g-3-i` asserts is about to become load-bearing for merges.

**Fix direction.** Do not try to detect the class automatically from the AC text — `n_location_rule:
0`, an absence-shaped Then clause, and the word "negative control" in the notes are all
suggestive and none is reliable. Instead:

1. **Make the obligation explicit at the contract layer.** Where a red baseline is structurally
   unavailable, require a **mutation proof** in its place: name the mutation, show the test red
   under it, show it green after revert. That is the same evidence a red baseline provides —
   *this test discriminates* — obtained the only way available for an absence.
2. **Have `test-writer` say which it captured**, red baseline or mutation proof, and treat "green
   on arrival, no mutation proof" as an incomplete phase rather than a pass. It already records
   `red_baseline_verified: false` for these; that field currently means "correctly not applicable"
   and should mean "and here is what replaced it".
3. **Prefer per-mutation results over a single pass/fail.** The table above is what located the
   defect — three tests caught the leak and the aggregate looked fine. A mutation proof reported
   as one boolean would have said "the suite catches it" and test 3 would still be inert today.

**2026-08-31 — second occurrence: a fixture made vacuous by the very gate the code was supposed
to stop relying on. `TKT-600a-1` was marked `done` on a test that would pass on entirely
unfixed code.**

`TKT-600a-1` says *"files_touched contains only real edit-surface paths … and NOT illustrative
file paths that merely appear inside prose it_requirements bullets"*. It carries four tagged
tests. All four pass. It is `work_status: done`. The behaviour was never implemented.

The mechanism is worth stating precisely, because it is not the usual "the test asserts the
wrong thing" — the test asserts exactly the right thing, on inputs that cannot exercise it:

```
the test's own fixture — src/foo.py, deploy/foo.py (do not exist on disk)
   _build_files_touched(...)  ->  []                                    PASSES

the same narrative shape, naming paths that DO exist
   -> ['docs/acceptance-criteria', 'docs/retrospectives', 'templates/skills']

a real file mentioned only in order to say DO NOT edit it
   "Do not edit templates/skills/security-scanner/SKILL.md here; it is context only."
   -> ['templates/skills/security-scanner/SKILL.md']
```

`_build_files_touched` still harvests every slash-bearing token from prose. What removes the
fixture's paths is the **on-disk existence gate** — not the fix. The test therefore passes
identically before and after the change it was written to prove, which is this entry's question
("can this test fail?") answered *no*, arrived at by a route the red-baseline protocol cannot
see: the test was green on arrival because its inputs were unreachable, not because the
assertion was weak.

The third line is the sharpest consequence. An `it_requirement` whose entire purpose is to say
*"this file is context, do not edit it"* makes that file the ticket's declared edit surface.

**The consequence was not hypothetical.** The unfixed extractor produced the surfaces for
`EPIC-SuppressionNarrowsNeverDisables`: 10 of 27 tickets unusable, three carrying nothing but
bare directories, and two pointed at `docs/known-issues/commit-guardian.md` — a live document —
as the file to modify. The build was stopped mid-drive. Five days and one "done" AC after the
test was written, the first thing to actually detect the defect was a production run.

**What this adds to the fix direction above.** The three prescriptions there are about negative
controls with no red phase. This case adds a fourth, for tests that DO have a red phase on
paper: **a fixture must be capable of reaching the code under test.** A path-filtering test
whose fixture paths do not exist is filtered by the existence gate before the filter under test
ever runs. The cheap general form is the mutation proof this entry already recommends — reverting
the fix must turn the test red, and here it would not have.

**Related.** `KI-ACD-023` (the `files_touched` defect this test was supposed to prevent, now at
two occurrences). `KI-ACS-004` (`TKT-600a-1` is already cited there for a *different* failure —
`done` with an empty `implemented_by` — so the same record has now produced two distinct
done-quality defects).

**Related.** `KI-TQ-009` (a test-local oracle reproducing the production bug — same family: the
test agrees with the code instead of constraining it). `KI-TQ-005` (fixtures that never built the
collection they assert over).

**Pattern:** a quality bar enforced by one mechanism, applied to the class of work that mechanism
cannot see, where the absence of the check is documented as correct.

---

### KI-TQ-011 — The AC xfail-masking plugin is disabled on the only gate that blocks, so a red baseline for a not-done AC is unmergeable — and where masking does apply it makes the local run exit 0

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 1 (18 tests across 8 files, one PR)
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `scripts/ac_store/pytest_ac_enforcement.py` (`_strict_mode`, `pytest_runtest_makereport`,
  `pytest_terminal_summary`); `.github/workflows/ci.yml` → job `test` ("Test suite (pytest)"),
  `env: AC_ENFORCE_STRICT: "1"`

**Symptom.** Two mechanisms in this repository disagree about what a failing test covering a
not-done AC means, and each is individually reasonable:

- `pytest_ac_enforcement` downgrades such a failure to `xfail`. Its docstring states masking is
  **opt-out** — the default is to mask.
- CI's `test` job sets `AC_ENFORCE_STRICT: "1"`, which opts out **globally**. That job is a
  required status check, with a comment stating the intent plainly: *"a PR carrying a failing test
  now fails this check and cannot merge."*

The plugin's default therefore never applies in the one place a test outcome decides anything. It
masks only in local and ad-hoc runs.

**Measured, same file, same commit** (`unit_tests/build_orchestration/test_bo2400e_4_crlf_preservation.py`,
`54ca1f32f`):

| run | outcome | exit code |
|---|---|---|
| local, no flag | `3 xfailed` | **0** |
| CI, `AC_ENFORCE_STRICT=1` | 3 failures, required check red | non-zero |

**Consequence 1 — a red baseline cannot be merged.** The AC-driven practice authors a failing test
for an AC before the fix exists. That test cannot reach `main`: the required gate rejects it, no
matter that its redness is the point. The evidence either sits on a branch collecting merge
conflicts or is deleted. Observed on PR #602 — 18 red-baseline tests across 8 files, every one
green-by-xfail locally and every one a hard failure in CI run `32969277018`.

**Consequence 2 — where masking *does* apply, it inverts the local signal.** A masked run exits
**0** and prints `3 xfailed`. A developer cannot distinguish "the suite is clean" from "three
genuinely-broken behaviours are recorded and hidden" without reading a summary line that competes
with ~4,000 other results. The mechanism built so a known defect is not lost is the same mechanism
that makes it invisible to anyone not looking for it.

**Why this is not simply "CI is right".** The strict flag is a good decision and this entry does
not argue against it. The defect is that **both mechanisms are maintained while only one can ever
apply.** The plugin carries masking logic, a terminal-summary reporter, and its own test files
(`unit_tests/ac_store/test_pytest_ac_enforcement.py`,
`test_pytest_ac_enforcement_strict_on_ci.py`) for a behaviour the only blocking consumer switches
off. Either the masking default is wrong, or the global opt-out is too broad. Holding both means
the documented default is a fiction, and a practice built on it — author the red baseline first —
silently has no merge path.

**Fix direction.** Not "loosen the gate."

1. **Make the red baseline explicit rather than inferred.** `@pytest.mark.xfail(strict=True,
   reason="<AC-ID> red baseline — defect unfixed")` is honest in both environments: pytest core
   handles it before the plugin sees a failure, so it reports `xfail` under `AC_ENFORCE_STRICT=1`
   too, and `strict=True` turns the day-the-fix-lands XPASS into a failure that forces the mark's
   removal. The baseline retires itself instead of rotting.

   **Verified, not assumed** — two marked probes covering a not-done AC, run under
   `AC_ENFORCE_STRICT=1`:

   | probe | outcome under the strict flag |
   |---|---|
   | marked, body fails | `xfailed` — the mark survives the flag |
   | marked, body passes | `FAILED [XPASS(strict)]` — forces the mark's removal |

   The plugin logs `NOT masked (AC_ENFORCE_STRICT=1)` for the second and stays out of the way of
   the first, because `pytest_runtest_makereport` only ever intercepts a *failing* report and
   pytest core has already resolved the marked one.

   This cannot create phantom-done: `done_proof` already treats XFAIL as **not** satisfying the
   done gate (see `unit_tests/ac_store/test_bo2500a_done_proof.py` — an all-xfail run exits 0 and
   is still not done-eligible), so a marked baseline can be merged without becoming evidence.
2. **Then decide the plugin's fate on the numbers.** With explicit marks carrying the red
   baselines, count what dynamic masking still masks. If the answer is "nothing anyone relies on",
   delete it — a default that never applies where it matters is worse than no default, because it
   reads as a safety net.
3. **Whatever is kept, make a masked run non-silent** — a masked failure should not produce exit 0
   with no distinguishing signal beyond one summary line.

**Related.** `KI-TQ-010` (the red baseline is the pipeline's only falsifiability check — this entry
is about that same baseline being unable to merge). Project memory *"Red-baseline gate: one-red
rule"* and *"pytest xfail-masking"* record earlier encounters with the same plugin from the
opposite direction.

**Pattern:** two correct-looking mechanisms whose defaults contradict, where the one that loses is
the one every practice is written against.

---

### KI-TQ-20260831-mutation-probe-lands-in-the-wrong-copy — a mutation proof injected into `templates/` proves nothing, because the tests import the build output — and it fails green

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** any mutation proof in this repository that targets
  `templates/scripts/commit_guardian/*.py`; the tests that import via
  `_REPO_ROOT / "scripts" / "commit_guardian"` (a symlink to `.leafcutter/scripts/commit_guardian/`);
  `templates/agents/test-writer.md` (where the mutation-proof obligation is being added)

**Symptom.** `KI-TQ-010` establishes that a negative control must be falsified by injecting the
leak it forbids and confirming the test goes red. In this repository that procedure has a trap
that makes it silently do nothing.

Two copies of every commit-guardian module exist: the canonical source under
`templates/scripts/commit_guardian/`, and the build output under `scripts/commit_guardian/`
(a symlink to `.leafcutter/…`, regenerated by `build.py`). Unit tests import the **build
output** — `sys.path.insert(0, _REPO_ROOT / "scripts" / "commit_guardian")`. A mutation
applied to the template is therefore never loaded by the test that is supposed to catch it.

**Observed, on `BP-1100g-5-i`'s own verification (2026-08-31):**

| mutation target | result | what it appears to mean |
|---|---|---|
| `templates/scripts/commit_guardian/_cross_layer_seam_checks.py` | **4 passed** | "the negative control is dead" |
| `scripts/commit_guardian/_cross_layer_seam_checks.py` (deployed) | **3 failed, 1 passed** | the control is sound |

The same injection — neutering the reasoned-negative branch so a conforming
`result: not_applicable` reports as a shortfall — produced opposite verdicts depending only on
which copy was edited. Against the deployed copy the record-W clause failed with exactly the
message it should: *"record W (reasoned negative) must never be reported as a shortfall"*.

**Why this is high, and worse than an ordinary footgun.** It fails in the **green** direction.
A mutation that does not land looks identical to a test that cannot fail — the exact defect the
proof exists to detect. So the trap does not merely waste the check; it **manufactures a false
positive for `KI-TQ-010` itself**, and the natural response to "my negative control is dead" is
to rewrite a test that was already correct. Had the first result been believed, sound tests
would have been "fixed" and the real conclusion — that the control works — never reached.

A weaker tell exists and is worth knowing: the run time. The template-mutation run took 0.24s;
the landed-mutation run took 33.5s, because the deployed hook subprocess actually did work
once findings appeared. A mutation that changes nothing about how long the suite takes has
probably changed nothing at all.

**Cause.** Source/output duplication, plus an import path that resolves to the output. Neither
is wrong on its own — the tests import the deployed copy deliberately, because a guard is only
real if the deployed copy behaves — but nothing tells the person performing a mutation proof
which copy the test will load, and the two are byte-identical after any `build.py` run, so
inspection does not reveal the difference either.

**Remediation.** Two parts, and the first is cheap enough to do immediately.

1. **State the rule wherever the mutation-proof obligation is written** (`test-writer.md`, and
   the `TQ-500` criteria now specifying this): *mutate the copy the test imports, or run
   `build.py` after mutating the template.* Prefer mutating the deployed copy — it is the
   shorter loop and it is what the assertion actually exercises.
2. **Make the probe self-verifying.** A mutation proof should confirm the injection reached the
   code under test before concluding anything from the result — the mutated module's own
   `__file__` at import time is enough, and the deployed-vs-template distinction becomes
   observable rather than assumed. Without that, a green mutation run is indistinguishable
   from a dead test.

**How it was found.** By suspecting the result rather than accepting it. The four-green outcome
was the expected shape of a real defect and would have been reported as occurrence #6 of
`KI-TQ-010`; checking which copy the test imported, before writing that up, is the only reason
it was not.

**Related.** `KI-TQ-010` (the obligation this trap defeats — read them together; this entry is
the operational half). `BP-1100g-3-ii` (the same source-vs-deployed split, that time causing
the defect rather than hiding it). `TQ-500a-3` and `TQ-500c-2-i` (criteria that will require
mutation proofs and therefore inherit this trap). CLAUDE.md → "New Hook / Gate Dependencies
Must Be in the Build Deploy-Manifest" (the same two-copy hazard on the import axis).

**Pattern:** a verification step performed against a copy of the artifact that the verifier
does not load — where the failure mode is silence, and silence is the result that means "safe".

---

### KI-TQ-012 — A test fixture reassigns the real repository's commit identity, and every commit made afterwards is authored by the fixture

- **Severity:** high
- **Status:** open — recurs on every run of the suite; a config repair does not hold
- **Occurrences:** 3 observed the same day, from three different worktrees — and the offending code is **two** files with **six** call sites, not four in one: a third commit landed authored `GE-120e-1-i fixture`, which is a *different* fixture, so `unit_tests/portability/test_ge_120e_1_i.py` carries the identical defect at 2 further sites
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** `unit_tests/portability/test_ge_120e_1.py` — lines 234, 300, 344, 543 — **and
  `unit_tests/portability/test_ge_120e_1_i.py`**, 2 more sites (found by grepping
  `fixture@example.com` across the branch after a third misattributed commit; the entry
  originally named one file because that is the one whose identity happened to land first)
  (currently on branch `EPIC-TrustThatAGreenCheckActuallyChecked`, unmerged); leaks into
  `leafcutter-ai/.git/config`, shared by every worktree

**Symptom.** A commit made from the package's main checkout landed with this author:

```text
commit 0a6ccac5e7a2652f2b650c82b9515849e054972f
Author: GE-120e-1 fixture <ge120e1-fixture@example.com>
```

`git config --local --get-regexp '^user\.'` in `leafcutter-ai/` returned:

```text
user.email ge120e1-fixture@example.com
user.name  GE-120e-1 fixture
```

Every prior commit on `main` is authored `BrainCandy <105064581+urlmonitor@users.noreply.github.com>`.

**Cause.** The fixture builds its scenarios as **worktrees of the real repository**, not as
throwaway `git init` sandboxes:

```python
_run_git(["worktree", "add", "--detach", str(self.root), "HEAD"], cwd=_REPO_ROOT)
_run_git(["config", "user.email", "ge120e1-fixture@example.com"], cwd=self.root)
_run_git(["config", "user.name",  "GE-120e-1 fixture"],            cwd=self.root)
```

Setting an identity is legitimate — the fixture creates commits and CI has no global
`user.email`. The defect is the **scope**. Worktrees share `$GIT_COMMON_DIR/config`, so a plain
`git config` inside a worktree writes to the **shared configuration of the entire repository
family**, not to the worktree. `tearDownClass` calls `git worktree remove --force` and never
unsets the keys, so the identity outlives the fixture that set it.

This repository already has `extensions.worktreeConfig = true`, which means the correctly-scoped
form — `git config --worktree user.email …` — is available today. The fixture just does not use
it. Four sites, all identical.

**Why this is high and not cosmetic.** The leak is silent, persistent, and repository-wide:

- It affects **every** commit from that checkout afterwards, not just the test run — and
  because worktrees share the config, every worktree of the repo too. Any epic drive or fast-lane
  run committing while this is set produces misattributed commits under an address that is not a
  real contributor.
- `.git/config` is not tracked, so nothing in `git status`, no pre-commit hook, and no CI gate
  reports it. It is visible only if someone reads an author line — which is precisely the field
  everyone skims past.
- Misattribution is not locally repairable once pushed. Rewriting author metadata on merged
  history is a force-push to a protected branch.

**How it was found.** Incidentally, and late. The author line was noticed while confirming an
unrelated commit's contents with `git show --stat`. Nothing surfaced it deliberately. Had the
check not happened, the following fast-lane run would have committed and opened a PR under the
fixture identity, since the lane's worktree inherits the same shared config.

**Remediation.**

1. Change all four sites to `git config --worktree …`, which this repo's
   `extensions.worktreeConfig` already supports. One word per site.
2. Better still, stop mutating repository state at all: pass the identity per invocation with
   `git -c user.name=… -c user.email=… commit`, which cannot outlive the process, or set
   `GIT_AUTHOR_*` / `GIT_COMMITTER_*` in the subprocess environment.
3. Give `tearDownClass` an `unset` for anything it did set, so a mid-run failure cannot strand
   the value.
4. Add a guard: a test that asserts `user.email` in the repository config is unchanged across
   the suite would have caught this on the first run. The suite currently has no notion that
   the real repository is shared mutable state.

**Repair applied.** The two keys were reset to the correct identity and the affected commit
re-authored with `git commit --amend --reset-author` before it was pushed. The fixture itself is
untouched — it lives on an unmerged branch and fixing it belongs with that branch's work, not
with an unrelated docs change.

**Recurrence observed within the hour — this is not a historical leak.** The keys were reset at
roughly 20:00. The next commit, made about an hour later from a *different* worktree, was again
authored `GE-120e-1 fixture`. `git config --show-origin` located the value in the shared
`leafcutter-ai/.git/config`, and no pre-commit hook in that run executes pytest. The test file
does not exist on `main` at all — `unit_tests/portability/` there holds four files, none of them
`test_ge_120e_1.py`. So the re-set came from a **concurrent session running that branch's suite
in its own worktree**, and it reached across into every other worktree of the repository.

Three things follow that the single-occurrence framing above understates:

- The blast radius is the whole repository family, live and concurrent. Any agent committing
  anywhere while another runs this suite inherits the identity, with no signal at either end.
- A one-time repair is worthless. The value returns on the next run, so the fix has to be in the
  fixture, not in the config.
- Under the fleet of parallel agents this repository is designed around, "a test that mutates
  shared repository state" is not an isolation nicety — it is a race with a persistent,
  invisible loser.

**Related.** User-memory `feedback_test_isolation_pitfalls` records the sibling traps (root
`conftest.py` import blast radius; `importlib.reload()` masking cold-import bugs). `KI-TQ-008`
(a repository-global tree-purity guard false-positives under concurrent agents) is the same
underlying assumption from the other direction: tests here treat the real repository as private
scratch space when it is neither private nor scratch.

**Pattern:** a fixture that isolates the *filesystem* (a fresh worktree, removed on teardown)
while sharing the *configuration* that worktree points at — so the visible half of the sandbox
is convincing and the invisible half leaks permanently.
