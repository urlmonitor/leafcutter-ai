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

### KI-CG-003 — `check-contract-shrinking` has no merge-commit awareness, so it blames the base branch's history on the merge

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/scripts/commit_guardian/check_contract_shrinking.py:165-189` (`_get_staged_diff`)

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
