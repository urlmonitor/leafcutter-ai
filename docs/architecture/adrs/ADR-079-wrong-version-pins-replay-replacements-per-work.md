---
title: "ADR-079: Wrong-Version Pins Replay Replacements, per Piece of Work, in the Workspace"
description: "Once a named wrong version has been prepared and has passed its checks for a piece of work, later runs of that work replay its replacements (file, old text, new text) on the code as it stands now, and do not ask the preparer again. Pins are keyed by work key and kept in the workspace's private git directory, and a failure to save them fails the gate. Without pins, the gate tested a behaviourally different guess on each run for 6 of 13 preparable names."
type: "adr"
status: "active"
created: "2026-10-25"
last_updated: "2026-10-25"
deciders:
  - BrainCandy
  - adr-author
components:
  - testing_quality
  - build_orchestration
related_docs:
  - docs/analysis/2026-10-23-the-wrong-version-gate-tests-a-different-guess-each-run.md
  - docs/known-issues/build-orchestration/open-low-ki-bo-20261023-test-breaker-no-op-alterations.md
  - docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500g-1-xi.yaml
  - docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500g-1-ix.yaml
  - docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500g-1-iii.yaml
  - docs/architecture/components/build-orchestration.md
  - docs/architecture/adrs/ADR-030-dual-engine-workflow-support.md
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
  - docs/architecture/adrs/ADR-050-runtime-reachability-guard-refuses-not-warns.md
  - templates/workflows-js/_shared/README.md
related_code:
  - scripts/build_orchestration/_wvp_store.py
  - scripts/build_orchestration/_wvp_plan.py
  - scripts/build_orchestration/_wvw_list.py
  - scripts/build_orchestration/_wvw_write.py
  - scripts/build_orchestration/wrong_version_writer.py
  - scripts/build_orchestration/wrong_version_gate.py
  - templates/workflows-js/_shared/wrong-version-runs.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/fast-lane-ship.js
---

# ADR-079: Wrong-Version Pins Replay Replacements, per Piece of Work, in the Workspace

## Status

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-10-25 |
| Author | adr-author (for BrainCandy), from ticket `TQ-500g-1-xi` |
| Supersedes | — |

## Context

The wrong-version gate checks that a test can fail. For each `must_catch` name a test
declares (for example "drop the retry_due condition"), the test-breaker agent (the
preparer) writes a replacement into the code. The runner then checks that the test
catches the altered copy. The writer (`wrong_version_writer.py`, requirement
[TQ-500g-1-ix](../../acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500g-1-ix.yaml))
turns the preparer's reply into a manifest and altered copies under
`<git-dir>/leafcutter/work/<work-key>/`. Before writing the next manifest it deletes the
previous one (`_wvw_write._clean`). It does not keep the replacements themselves, so
nothing can be reused.

This was measured on 2026-10-23
([analysis](../../analysis/2026-10-23-the-wrong-version-gate-tests-a-different-guess-each-run.md)).
Across three gate rounds, the preparer turned the same name into a behaviourally
different alteration for 6 of 13 preparable names on BO-2900a-2-i, and for 4 of 7 on
BO-2900a-1-ii. A test written to catch round N's guess was then judged against round
N+1's guess. The ticket never converged, each round cost 0.34 to 0.60M tokens, and some
survivors were equivalent to the code as written. Deterministic preparation is not
available: neither the agent frontmatter nor the workflow `agent()` options carry a
temperature or a seed.

Two facts from the code limit any reuse:

- The runner writes the whole `altered_copy` over the file. If a copy stored by an
  earlier run were replayed, it would also undo every code change made since.
- A cleaned or moved work folder (`_wvw_write._clean` today, and the move into history
  under TQ-500g-1-xv) loses anything stored inside it.

Ticket `TQ-500g-1-xi` (epic
`EPIC-OnceANamedWrongVersionIsPreparedAnd`) records two user decisions, made by
BrainCandy on 2026-10-24. Pins are kept in the workspace and are not durable. A pin
that cannot be saved fails the gate.

## Decision

1. **A pin stores replacements, never copies.** A pin MUST store the ordered list of
   replacements the writer actually applied, `[{path, old, new}]`. It MUST NOT store an
   altered copy or a diff. On every run, a pinned name MUST be rebuilt by applying its
   replacements to the files as they stand now, through `_wvw_prepare.alter`. That keeps
   the same path refusals, the same exactly-once rule and the same CRLF rule. An altered
   copy from an earlier run MUST NOT be applied, copied or used as input.

2. **A pin is taken from what was applied, not from the reply.** The replacements MUST
   come from the manifest entry's `replacements` key, which records what the writer
   applied. They MUST NOT come from the preparer's raw reply. Manifest entries will gain
   three additive keys: `replacements` (`[]` for `could_not_prepare`), `alteration_id`
   (`null` for `could_not_prepare`) and `source`. Under this ADR, `source` is
   `"pinned"` or `"prepared: not pinned"`. The keys from TQ-500g-1-ix keep their meaning,
   and the runner still applies `files[].altered_copy`.

3. **Pins are kept in the workspace's private git directory, outside the work folder.**
   The pin file for a work key MUST be at `<git-dir>/leafcutter/pins/<work-key>.json`.
   `<git-dir>` is the result of `git rev-parse --absolute-git-dir`, the same call the
   writer already makes. One function, `_wvp_store.pin_path`, MUST own this rule. No
   other code builds a pin path. Pins MUST NOT be placed under
   `<git-dir>/leafcutter/work/<work-key>/`, so that cleaning or moving that folder cannot
   reach them.

   Pins are private to the workspace. They are never committed, and they are lost when
   the workspace is removed. The next run in a new workspace then prepares the names and
   pins them again. This location is a user decision, not a default. If it is revisited,
   the change MUST be limited to `_wvp_store.pin_path`.

4. **Pins are keyed by work key, then by normalised name.** The store MUST be addressed
   first by work key (for example `07_TICKET-refresh-gate`). Inside that, it MUST be
   addressed by `_wvr_scope.norm_name(name)`. A second normaliser MUST NOT be written.
   A run for one work key MUST NOT read or apply pins stored under another, even when
   both guard the same requirement and name the same wrong versions. Pins MUST NOT be
   keyed by requirement id, or by name alone.

5. **The pin file has a fixed shape and is written atomically.** The file MUST have this
   shape, in this key order:
   `{work_key, pins: {<norm name>: {name, replacements: [{path, old, new}], alteration_id,
   failed_check: null | {check, files_sha256}, reset, cleared_alteration_id}}}`.
   It MUST be written to a temporary file in the same folder and then moved into place
   with `os.replace`. The same pins MUST always produce a byte-identical file. A crash
   MUST NOT leave a partial pin file.

6. **One function gives an alteration its identity.** `_wvp_store.alteration_id` MUST
   return `"sha256:"` followed by the first 16 hex characters of the SHA-256 of the
   canonical JSON of the ordered replacement list. Canonical means `sort_keys` true,
   separators `,` and `:`, UTF-8, and no ASCII escaping. It MUST be computed from the
   replacements alone, so a change elsewhere in the file leaves the identity unchanged.
   TQ-500g-1-xv, -xvi and -xvii MUST reuse this function and MUST NOT fork it.

7. **"The fix undone" is never pinned.** "The fix undone" and its aliases MUST NOT be
   planned, pinned or read from the pin store. On every run, the runner MUST build them
   from git: the changed code as it stood at the base ref.

8. **One plan decides each owed name, and the write step does not trust a stale plan.**
   `_wvp_plan` MUST decide exactly one source for each owed name of
   `_wvw_list.derive_owed`. That function stays the one reading of owed names and
   files. The source is the pin, a declaration (TQ-500g-1-xvii) or a new preparation.
   Under this ADR, a name is prepared when its work key holds no usable pin for it.

   `wrong_version_writer.py list --work-key <key>` MUST print exactly one JSON object
   with the keys `{owed, to_prepare, decisions, error}`. Each `to_prepare` item MUST be
   byte-identical to its `owed` item, and the items MUST keep the owed order. With
   `--work-key`, the list step MUST write only
   `<git-dir>/leafcutter/work/<key>/plan.json`, and nothing in the working tree.
   Without `--work-key`, it MUST behave as today: `to_prepare` equals `owed`,
   `decisions` is `[]`, and nothing is written.

   `plan.json` carries a fingerprint over three things: the owed list, the pin file's
   bytes, and the bytes of every file a planned replacement names. The write step MUST
   use the plan only when that fingerprint still matches. Otherwise it MUST recompute
   the plan in-process with the same `_wvp_plan` function. It MUST NOT take a plan, a
   `to_prepare` list or any scope from the route or from the reply. If the reply also
   answers a pinned or declared name, the answer MUST be listed in
   `ignored_reply_names` and MUST NOT be used.

9. **Only checked preparations are pinned, and a reset is never overwritten.** A new
   step, `wrong_version_writer.py pin --work-key <key> --manifest <path>
   --test-root <path>`, reads the runner's run JSON on stdin. It MUST print exactly one
   JSON object `{pinned, kept, error}`. It MUST exit 0 when it wrote the store or left
   it unchanged, and 1 otherwise.

   A manifest entry whose `source` starts with `prepared` or `re-prepared` MUST become
   the name's pin only when every verdict row for that name is `caught` or `survived`,
   and the run was not cut short. A survivor MUST still be pinned, because survival
   judges the test, not the alteration. A `did_not_load`, `not_applied`,
   `not_executed`, `invalid` or `not_run` row MUST block the pin. Entries whose source
   is `pinned` or `declared` MUST NOT rewrite the store, so a declaration is never
   pinned.

   Replacing a name's pin MUST be compare-and-swap. The pin is replaced only when the
   stored entry still equals what this run's plan read, or when there was none. That way
   a reset made while a run was in progress is never overwritten by that run. This
   promotion rule MUST live in `_wvp_store` and MUST NOT live in `finish`.

10. **A pin-write failure fails the gate.** After the runner has run, `finish`
    (`wrong_version_gate.py`) MUST call the pin step with the same work key, the
    manifest path the writer printed, and the same test root. It MUST put the pin
    step's JSON, unchanged, under a new additive key `pins` (`null` when the pin step was
    not called). If the pin step exits 1 or prints no parseable JSON, `gate_passed` MUST
    be `false` and `stopped_at` MUST be `"pin"`. This failure MUST NOT be reported only
    as a warning. The next run depends on these records, and the same refuse-not-warn
    reasoning is set out in
    [ADR-050](ADR-050-runtime-reachability-guard-refuses-not-warns.md).

11. **Routes ask the preparer only for `to_prepare`.** The list command in each route
    MUST pass `--work-key "<work key>"`. That is the same key the route passes to
    `finish`. The route MUST check that `to_prepare` is an array, and otherwise halt as
    blocked with `wrong_version_step` `"list"`. It MUST dispatch the test-breaker only
    when `to_prepare` is non-empty, and send `wrong_versions = listed.to_prepare`
    unchanged. `finish` MUST still run every time, with an empty here-document when
    nothing was prepared.

    The routes hold no decision logic. Per
    [ADR-030](ADR-030-dual-engine-workflow-support.md), they only dispatch and parse
    fail-closed. The identical wrong-version block of `build-feature.js` and
    `build-ticket.js` MUST move into
    `templates/workflows-js/_shared/wrong-version-runs.js`, which the build inlines
    between `// WRONG-VERSION-RUNS-START` / `-END` markers. `fast-lane-ship.js` keeps its
    own block. Its change MUST be paid for inside the same file under the file-size
    ratchet, and no `check-file-size` skip is allowed.

## Consequences

### Positive

- The same named wrong version is tested on every run of a piece of work. A test written
  to catch it stays caught, so a ticket can converge.
- Names already pinned are not sent to the preparer. When nothing needs preparing, the
  test-breaker is not dispatched at all, which saves most of the 0.34 to 0.60M tokens a
  round cost.
- Because pins are rebuilt from the current files, code changes made after pinning
  survive in the altered copy. A pin cannot silently revert a coder's work.
- `alteration_id` gives every alteration a stable name. Later work (TQ-500g-1-xv history,
  -xvi reset, -xvii declarations) can say "caught *this* alteration" without a second
  identity scheme.
- Keying by work key keeps one ticket's pins out of a sibling ticket's run.

### Negative

- A bad first guess is locked in, whether it is a no-op or equivalent to the code as
  written. Survivors are pinned too. The answers are the effect check (TQ-500g-1-xiv,
  [no-op KI](../../known-issues/build-orchestration/open-low-ki-bo-20261023-test-breaker-no-op-alterations.md))
  and the explicit reset (TQ-500g-1-xvi), and both come later. Until they land, a pin
  can only be cleared by removing the workspace.
- Fresh guesses no longer explore new readings of a name, and that exploration found a
  real gap in round III. Authors who want two readings must write two names.
- Pins are lost when the workspace is removed. A new workspace for the same work pays
  for one full preparation again. This is the accepted cost of the workspace-private
  location.
- A pin-store write failure now blocks a gate that would otherwise have passed. That
  adds a new way for a run to stop.

### Operational

- Pins live at `<git-dir>/leafcutter/pins/<work-key>.json`. They are invisible to
  `git status`, are never committed, and are not cleaned by the writer's work-folder
  cleanup. To inspect them, read that file in the workspace's git directory.
- `finish` output gains `pins`, and `stopped_at` can now be `"pin"`. Anything that parses
  `finish` MUST accept both.
- Existing route tests that stub the list reply
  (`unit_tests/workflows/_tq500g1v_fixtures.py` and the -vi route-sequence tests) must
  add `to_prepare` to their stubs in the same change. The fail-closed check MUST NOT be
  weakened to keep an old stub green.
- `_wvp_store.py` and `_wvp_plan.py` are deployed by the existing directory glob for
  `scripts/build_orchestration/`. No deploy-list edit is needed, but the deployed writer
  and gate must be exercised from a deployed layout to prove it.
- Calling `list` without `--work-key` keeps today's behaviour, so callers that predate
  this ADR are unaffected.

## Alternatives

- **Deterministic preparation (temperature 0 or a seed).** Rejected. Neither the agent
  frontmatter nor the workflow `agent()` options carry a temperature or a seed. Even at
  temperature 0, LLM output is not guaranteed to be identical, and the preparer's inputs
  change as the code changes.
- **Store and replay the altered copy.** Rejected. The runner writes the whole copy over
  the file, so replaying an earlier copy would undo every code change made since that run.
  This is the exact failure `test_second_new_run_reapplies_pinned_replacement_to_current_code`
  must catch.
- **Pin from the preparer's raw reply.** Rejected. The reply can contain answers the
  writer refused or did not apply. A pin taken from it would replay replacements that
  were never checked.
- **Keep pins inside `<git-dir>/leafcutter/work/<work-key>/`.** Rejected. `_wvw_write._clean`
  deletes from that folder today, and TQ-500g-1-xv moves it into history, so run 2 would
  find no pin.
- **A durable location (the operational log root of ADR-069, or committed in the repo).**
  Rejected by user decision (BrainCandy, 2026-10-24). A committed pin would put workspace
  bookkeeping into the project history and into code review. A durable store outlives the
  code it was validated against. Losing pins with the workspace costs only one more
  preparation.
- **Key pins by requirement id or by name alone.** Rejected. Two pieces of work that guard
  the same requirement and name the same wrong version can target different code. Sharing
  a pin would apply one ticket's replacement to another's code.
- **Pin at write time, before the runner's verdict.** Rejected. That would pin
  alterations that did not load or changed nothing (`did_not_load`, `not_applied`), and
  lock in a broken preparation that no check ever passed.
- **Report a pin-write failure as a warning.** Rejected by user decision (2026-10-24).
  If the gate passes and the pins are not saved, the next run silently prepares new
  guesses, and the run looks like it is converging when it is not.
- **Let the route decide what to prepare.** Rejected. Decision logic in the workflow
  bodies is duplicated across three routes and cannot be unit-tested in Python. Per
  ADR-030 the routes only dispatch and parse fail-closed. The write step also refuses a
  plan supplied by the route.

## References

- Ticket: `tickets/00_inbox/epics/EPIC-OnceANamedWrongVersionIsPreparedAnd/02_TICKET-20261024-TQ-500g-1-xi.md`
- Requirement: [TQ-500g-1-xi](../../acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500g-1-xi.yaml)
- Evidence: [The wrong-version gate tests a different guess each run](../../analysis/2026-10-23-the-wrong-version-gate-tests-a-different-guess-each-run.md), invariants 1, 4 and 5 and recommendation items 1 and 3
- Shared block grammar: [`templates/workflows-js/_shared/README.md`](../../../templates/workflows-js/_shared/README.md)
- Self-hosting boundary: [ADR-001](ADR-001-self-hosting-boundary.md). Edit `templates/` and `scripts/` sources only.
