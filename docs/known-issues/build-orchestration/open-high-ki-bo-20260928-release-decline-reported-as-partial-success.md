---
title: "KI-BO-20260928-release-decline-reported-as-partial-success — when the fast lane's release agent declines, its schema-shaped `released: []` reply is reported as \"Release: partially succeeded\", so the claimed ACs stay in_progress and nothing marks the release as failed"
description: "high — buildReleaseOutcomeFields() treats any array-valued `released` as an attempted release. A release agent that declines still has to fill RELEASE_SCHEMA, returns `released: []`, and the run reports release_attempted: true, release_error: null. The claim path separates a decline from a real result; the release path does not. Seen live in fast-lane run wf_e5633af0-efb on 2026-09-25."
type: reference
category: reference
status: active
created: '2026-09-28'
last_updated: '2026-09-28'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260901-1620.md
  - docs/known-issues/build-orchestration/resolved/resolved-high-ki-bo-020.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-023.md
---

# KI-BO-20260928-release-decline-reported-as-partial-success — when the fast lane's release agent declines, its schema-shaped `released: []` reply is reported as "Release: partially succeeded", so the claimed ACs stay in_progress and nothing marks the release as failed

- **Severity:** high. The behaviour is wrong and nothing reports it. A release that never ran is
  reported as an attempted release with no error. The ACs it should have returned to `todo` stay
  `in_progress`, and a later fast-lane run aimed at them is refused. The only signal is the
  "partially succeeded" wording and an empty `released_ac_ids`, which do not look like a failure.
  `release_error` is `null`, so anything that checks that field for a failed release finds none.
  This is the same result `KI-BO-020` was filed for (stranded claims after an aborted run), except
  that the output now says the release partly worked.
- **Status:** open. No AC.
- **Occurrences:** 2 live. Fast-lane run `wf_e5633af0-efb`, 2026-09-25 ~12:30 UTC, for
  `INF-1100d-3-ii`. Recorded as side finding 1 of Occurrence 4 in `KI-BO-20260901-1620`. Not
  re-reproduced. Fast-lane run `wf_23078e50-7a4`, 2026-09-28, for `ACD-1600c-4` (Occurrence 2).
- **First seen:** 2026-09-25 · **Last seen:** 2026-09-28 (Occurrence 2; code re-read 2026-09-28 on
  `origin/main` at `95903bbb`, and again at `ae85a2a1` for Occurrence 2)
- **Where:** `templates/workflows-js/fast-lane-ship.js`:
  - `RELEASE_SCHEMA`, `:423-430`. The only required field is `released`, and it has no refusal flag.
  - `buildReleaseOutcomeFields()`, `:543-588`. The branch at `:551-570` handles any array-valued
    `released`.
  - Its nine callers, which run on every halting path after the claim: `:1182`, `:1256`, `:1283`,
    `:1344`, `:1369`, `:1457`, `:1484`, `:1588`, `:1708`.
  - For comparison, the claim-side guard at `:1084-1091`.

## Symptom

Every halting path after the claim dispatches a release agent (`RELEASE_EXECUTOR_AGENT_TYPE =
"python-coder"`, `:515`) with `schema: RELEASE_SCHEMA`. The engine enforces the schema, so an agent
that declines still has to return an object with a `released` array. The natural decline-shaped
reply is `{"released": [], "message": "<why I will not do this>"}`.

`buildReleaseOutcomeFields()` then does this:

```js
var releasedIds =
  reply && Array.isArray(reply.released)
    ? reply.released
    : null;

if (releasedIds !== null) {
  // ... release_attempted: true, release_error: null
  // note: unreleased.length === 0 ? "Release: succeeded — ..."
  //                                : "Release: partially succeeded — ..."
}
```

An empty array is still an array, so a decline takes the success branch. Every claimed id is then
"unreleased", and the note reads `Release: partially succeeded — returned to todo; <ids> left at
in_progress; ...`. The list before "returned to todo" is empty. The fail-closed branch (`:572-587`,
`release_attempted: false`, `release_error: <detail>`, "Release: refused or unreadable") is reached
only when `released` is missing or is not an array. The schema makes that case unlikely.

The function's own header comment (`:491-500`) says it "Fails CLOSED" and that a refusal is
"reported as NOT released". That holds for the refusal shape `KI-BO-020` saw
(`{"status": "refused", ...}`, a reply with no `released` key). It does not hold once the dispatch
carries a schema. BO-2400f-10-ii added the schema so that a real success is not read as a failure
(`:417-422`). As a side effect, a refusal is now read as a partial success.

**The claim path already handles this.** The claim dispatch (`:1051-1072`) tells the agent what to
return if it cannot run the command, `{"claimed":[],"excluded_claimed":[],"target_refused":true,
"message":"<why>"}`. The guard at `:1084-1091` (BO-2400f-7-iii) then turns an unusable reply, or
`target_refused` with an empty `excluded_claimed`, into "The claim was never attempted". The
release prompt and schema have no equivalent flag, and `buildReleaseOutcomeFields()` has no
equivalent guard.

**Why `released: []` cannot be read as "the release ran and freed nothing" in general.** The real
CLI (`scripts/build_orchestration/fast_lane.py` `release` subcommand, `:548-553`, which calls
`release_claim()` in `_fl_lifecycle.py:358-402`) can print `{"released": []}` legitimately: when
no ids were passed, or when every id is missing from the store or fails with an `OSError`. So an
empty list alone does not distinguish "ran, freed nothing" from "never ran". The reply has to
carry an explicit marker. The CLI's exit code is 0 in both cases, and the release prompt tells the
agent to "Ignore non-zero exit".

## Occurrence 1 — 2026-09-25, fast-lane run `wf_e5633af0-efb` (`INF-1100d-3-ii`)

Not re-reproduced. The account below is from `KI-BO-20260901-1620` Occurrence 4, which was built
from the run record on the reporting machine (outside the repository). The claim succeeded. The
context-bundle dispatch (`python-coder`) declined, and the run dispatched
`release-on-context-bundle-fail` (`python-coder`, `:1175-1181`). That agent also declined
("Declined to execute. This request asked python-coder to act..."). The run ended `blocked` with:

- note: "Release: partially succeeded — returned to todo; INF-1100d-3-i, INF-1100d-3-ii left at
  in_progress"
- `release_attempted: true`, `release_error: null`
- `unreleased_ac_ids: ["INF-1100d-3-i", "INF-1100d-3-ii"]`

Both ACs were left `in_progress`. In that run they were in the copy of the store inside the run's
worktree, which the same occurrence records as having been created in a different repository.
That worktree no longer exists, so the stranded state went with it. In the normal layout the store
the run writes is the one the next run reads.

## Occurrence 2 — 2026-09-28, fast-lane run `wf_23078e50-7a4` (`ACD-1600c-4`)

Reported by the operator's session from the run's result. Not re-reproduced. Same path as
Occurrence 1: `fastlane-context-bundle` (`python-coder`) declined (recorded as Occurrence 5 of
`KI-BO-20260901-1620`), and the run dispatched `release-on-context-bundle-fail` to `python-coder`,
which declined too. The run's result carried:

- note: "Release: partially succeeded", with nothing listed as returned to todo
- `release_attempted: true`, `release_error: null`, `release_executor: "python-coder"`
- `released_ac_ids: []`
- all five claimed ACs (`ACD-1600c-4`, `ACD-1600c-4-i`, `-4-ii`, `-4-iii`, `-4-iv`) left
  `in_progress` in the store inside the run's worktree

That is exactly the field combination the Detection section below describes, on a build of main
that already carries the release-reporting fix (BO-2400f-10-ii). Re-checked on `ae85a2a1`:
`buildReleaseOutcomeFields()` (`fast-lane-ship.js:543-588`) still takes the success branch for any
array-valued `released` (`:551-570`), `RELEASE_EXECUTOR_AGENT_TYPE` is still `"python-coder"`
(`:515`), and the release dispatch after a context-bundle failure is still `:1175-1181`. The
chartered executor `command-step-runner` exists on main since 2026-09-28 but no fast-lane dispatch
uses it yet (see `KI-BO-20260901-1620` Occurrence 5), so the decline that feeds this defect is
still expected on every halting run.

The stranded ACs were in the run's worktree copy of the store. That worktree was itself opened in
the wrong place (`KI-BO-20260928-fast-lane-worktree-step-runs-another-clones-script`
Occurrence 2), so the stranded state is not in the store a normal run reads. Release it with the
Workaround below, pointed at that worktree's store, before removing the worktree, or delete the
worktree.

## Detection

- A fast-lane `blocked` / `halt` result whose note contains `Release: partially succeeded —
  returned to todo;` with nothing between the dash and "returned", or whose fields show
  `released_ac_ids: []` together with `release_attempted: true` and `release_error: null`.
- After any halted fast-lane run, ACs from its build set still at `work_status: in_progress`:
  `grep -rln "work_status: in_progress" <ac-store-root>` and compare with the run's `ac_ids`.
- A later `/fast-lane-build` on the same ids halting with "connected set already claimed / in
  progress" when no other run is live.

## Workaround

Release the stranded ids by hand with the same CLI the release agent should have run, from the
worktree (or repository) whose store holds the claim:

```bash
python3 scripts/build_orchestration/fast_lane.py release --ac-ids <ID1>,<ID2> --ac-root <ac-store-root>
```

It prints `{"released": [...]}` and is idempotent: an AC already at `todo` is a no-op. It only
changes `work_status`. If it prints `released: []` for ids that are still `in_progress`, the ids
were not found under that `--ac-root` (check you are in the right store). Or the write failed,
which is logged as a warning (see also `KI-BO-023`). Editing `work_status: in_progress` back to
`todo` in each AC YAML by hand also works.

## Suggested fix

1. **Give the release the claim path's decline contract.** Add a boolean (for example
   `release_refused`) to `RELEASE_SCHEMA`. Change the release prompt the same way the claim
   prompt was changed: "If you cannot run this command at all, return `{"released": [],
   "release_refused": true, "message": "<why>"}`." In `buildReleaseOutcomeFields()`, send
   `release_refused === true` to the fail-closed branch with `release_attempted: false` and
   `release_error` set to the reply. This mirrors `:1084-1091`. Change it once, in the builder and
   the one prompt template shape, not at each of the nine call sites.
2. **Also catch an unflagged decline.** An agent that declines may ignore the instruction and only
   write prose in `message`. When `released` is empty, the claimed list is not, and `message`
   reads as a refusal, treat the reply as not attempted too. `isAgentRefusal()` /
   `AGENT_REFUSAL_MARKERS` exist in `templates/workflows-js/plan-feature.js:1934-1992`, but not in
   `fast-lane-ship.js`. Workflow scripts are self-contained (ADR-024), so reusing them means copying
   them or moving them to a shared build-time include. The current marker list would **not** match
   the observed text: "Declined to execute" and "does not match my role" hit none of the entries
   ("declines to" and "i decline" are there, "declined to" is not). Extend the list and test it
   against the observed wording.
3. **Never say "partially succeeded" when nothing was released.** Even for a truthful
   `released: []` from the CLI, a note reading "partially succeeded — returned to todo;" with an
   empty list is misleading. If `releasedIds` is empty and `claimed` is not, the note should say
   that nothing was released.
4. **Regression tests** in `unit_tests/workflows/test_bo2400f_10ii_release_reporting.py`. That file
   already covers a `{"status": "refused"}` reply, a JSON-string success and an unreadable reply.
   It has no schema-shaped decline. Add:
   (a) `{"released": [], "release_refused": true, "message": "..."}` → `release_attempted: false`,
   `release_error` non-null, every claimed id in `unreleased_ac_ids`;
   (b) `{"released": [], "message": "Declined to execute. This request asked python-coder to act ..."}`
   with a non-empty claim → the same;
   (c) a truthful `{"released": []}` with a non-empty claim → no "partially succeeded" wording.
   Deploying the fixed script also needs the usual rebuild of the deployed workflow copies (see
   `KI-BP-008` Occurrence 3 on stale copies).

The root cause of the decline itself is `KI-BO-20260901-1620`: `python-coder` is not chartered to
run the release. That is tracked there and fixing it would make this path rarer. It does not
remove the need for this guard, because any agent can decline.

## Related

- `KI-BO-20260901-1620` Occurrence 4, the run this was observed in. It also records the
  context-bundle refusal and the worktree created in another repository.
- `KI-BO-020` (resolved), the original stranded-claims defect, where `status-checker` refused the
  release and the reply was discarded. Its fix introduced `buildReleaseOutcomeFields()` and the
  schema whose side effect this is.
- BO-2400f-7-iii, the claim-side decline-versus-contention guard at `fast-lane-ship.js:1084-1091`.
- `KI-BO-023`, another way the release path strands ACs in `in_progress` (a `ValueError` escapes
  handlers that catch only `OSError`).
