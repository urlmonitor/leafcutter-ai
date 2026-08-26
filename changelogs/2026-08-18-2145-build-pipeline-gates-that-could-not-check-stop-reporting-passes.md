---
title: "Build-pipeline gates that could not check stop reporting passes"
date: 2026-08-18
time: "21:45"
type: manual
components:
  - build_pipeline
  - commit_guardian
  - build_orchestration
summary: >-
  Build-pipeline guards that used to exit clean without actually checking anything
  now block, report a gap, or were removed — and about half of those fixes were
  themselves wrong on the first attempt, caught only by a second, adversarial pass.
---

## What changed

`EPIC-BuildPipelinePhantomRemediation`. Every item here shares one shape: a check
that could not do its job reported success anyway. This entry covers both the
initial drive and a subsequent remediation round that found and corrected several
defects in the initial drive's own fixes — read the "Corrected on review" section
before trusting any claim below at face value.

**Hook parity blocks instead of informing (`BP-100i-3`).** A script present in the
canonical template tree but absent from the deployed tree produced an INFO line and
`exit 0`. It now blocks the commit, naming the missing scripts and the deployed
directory inspected. A regression test now runs the hook AS A PROCESS and asserts
exit code 1 — added after review found that both ways of breaking the wiring
(discarding the result, removing the call) had previously left all 39 tests green.

**Skill-pointer resolution accepts a declared registry entry, not just a canonical
template directory (`BP-1300a-1`).** The build's skill-pointer check originally
resolved `skill_id` against the deployed `.claude/skills/` tree as well as the
canonical source, so a stale deploy could satisfy a pointer whose canonical target
had been deleted. It was tightened to check `templates/skills/` only — but the
schema explicitly permits `portable: false` skills that have no `template_path` at
all, declared only in `config/skill_registry.json`. Resolution now accepts either a
`templates/skills/<id>/` directory or a `skill_registry.json` declaration; a pointer
satisfying neither fails the build deterministically.

**Command-reference reachability guard (`BP-900g-1`).** A real guard, replacing a
check that could not distinguish a reachable command reference from an unreachable
one. Its regex initially matched only 4 of the 9 live call sites in the real
corpus — it required a quote immediately after `(`, so the keyword forms
(`Skill(skill="…")`, `Workflow(name: "…")`) and the backtick form were invisible.
A probe carrying three deliberately bogus targets in those forms returned zero
verdicts, which also means an earlier "full-tree scan found 0 problems" result was
partly the scanner failing to look. It now
scans all five real call forms across all five platform command surfaces (not just
Claude's), fails closed on unreadable input, and no longer aborts the build when the
optional `workflows.enabled` toggle is off.

**The build manifest and the drift gates that read it (`BP-100k-1`, `BP-100k-2`,
`BP-100k-3`, `BP-100k-3-i`).** See "The manifest problem was worse than described,
and the fix that shipped had its own gap" below — this is the section most worth
reading in full.

**Presence-only assertions stop counting as coverage (`BP-1100b-4`, `BP-1100b-5`).**
Two parts. The test harness now executes a workflow body inside a Node `vm` context
contextified with exactly the ADR-030 injected globals, so `require`, `module`,
`process` and friends throw `ReferenceError` — a workflow that depends on them can
no longer pass a harness test while failing against the real engine. And a new
pre-commit hook rejects newly added assertions whose entire coverage is a grep for
a symbol's presence over a scanned source file, with a `# presence-only: <reason>`
waiver for deliberate cases. The guard's own detection logic needed two further
review rounds — see "Corrected on review" below.

**The finalize journal mechanism was deleted, then its replacement was found to
still not prove the thing it claimed (`BO-1000c-1a`).** See "BO-1000c-1a — redefined
twice, and still not done" below. Do not read the AC's `work_status` as settled
without reading that section.

**The Step 6a auto-ticketing contradiction is resolved (`FIN-100e-1`, `FIN-100e-2`).**
Two ACs described behaviour the code had been deliberately built *not* to perform.
They are formally superseded with a stated rationale rather than left asserting a
fiction.

## The manifest problem was worse than described, and the fix that shipped had its own gap

The epic's own working notes claimed the manifest "records every managed template
and every deployed output" and cited 269 output mappings and 156 template
fingerprints. Both the claim and the numbers were wrong at the time they were
written, and the underlying defect was worse than "not every output": 16
`.agents/rules/*` keys in the manifest pointed at a directory the build never
creates. `build_rules()` runs as one of `build.py`'s `internal_phases`, which
invoke every phase with `output_root`, not `target_root` — despite the phase
function's parameter being named `target_root`. `_compute_output_mappings`
trusted the parameter name instead of the actual call convention, so it recorded
`<target_root>/.agents/rules/` while the files really land at
`<output_root>/.agents/rules/`. The 16 real files went unrecorded, and no gate —
not a GAP, not an EXEMPT, not even a warning — ever looked at them. The RESULT line
was clean because the comparison set was wrong, not because nothing had drifted.

The mapping is now corrected to `<output_root>/.agents/rules`, derived from the
real copy set rather than a second hardcoded inventory that could drift from it.
Current real numbers on this repo: 275 output mappings, 157 template fingerprints —
not the 269/156 the epic's mid-drive notes stated.

Beyond that specific fix, this round also:

- Made the drift-gate scan directories DERIVED from the manifest's own keys rather
  than hardcoded, so the manifest and the gate cannot disagree about where to look
  (this is what the `.agents/rules` defect would have needed to be structurally
  impossible, not just fixed once).
- Added a `verified == 0` floor to both drift gates: a run that compared nothing no
  longer exits as though it compared everything. This was observed live —
  `verified=0` against 275 recorded mappings — during the remediation round itself.
- Changed the RESULT line to break `uncomparable` into `exempt=` and `gaps=`, with
  only `gaps` driving the verdict. This resolved an apparent contradiction between
  `BP-100k-3` and `BP-100k-3-i` that the two-way count could not represent.
- Made `build.py` record `output_mappings_error` as manifest DATA when the mapping
  computation itself fails, so a consumer's hook can tell "no outputs" apart from
  "computation died." Previously the only signal was a build-time `UserWarning`
  long gone by the time a hook ran, and the manifest looked well-formed and simply
  empty.
- Emptied the drift-gate exemption registry entirely. It had held four entries
  whose own `ground` text read "Candidate for manual deletion" — real findings the
  gate had correctly surfaced, silenced rather than cleaned up — and all four
  named machine-local paths behind a symlink that would have shipped into every
  consumer install. Those four orphaned artifacts were deleted rather than
  re-exempted — and once the scan set became manifest-derived, the gate
  immediately surfaced **four more** orphans under `.gemini/` that the hardcoded
  directory list had never looked at. Eight in total were deleted. The four extra
  are the clearest evidence the derived scan set was worth doing: they had been
  sitting in the deployed tree for months, and nothing had ever reported them.
- Re-anchored `validate_agent_self_description` on the PACKAGE root rather than
  `target_root`. In this repo's own documented local build
  (`./build-self.sh`, which passes the parent workspace as the target), the
  validator previously examined ZERO agent templates and printed "all agents
  pass," while CI — which happens to run package-root == target-root — examined
  the real set. Same clause, opposite verdicts depending on which build invoked it.
- Unified `check_output_drift()`'s dual contract so the function and its `main()`
  share one scan/report/verdict path instead of two that could disagree.

## Corrected on review — the presence-only guard's own detection was wrong twice

The presence-only guard (`BP-1100b-5`) needed real fixes, not just a first pass,
because its detection logic reproduced the exact failure mode it exists to catch:

- Its backward waiver scan was originally unbounded and did not respect hunk
  boundaries. One waiver comment ended up waiving every later assertion in the
  file, across hunks 900 lines apart — and the same unbounded, symmetric matching
  produced FALSE POSITIVES against genuine runtime-value assertions. The scan is
  now bounded to 10 lines and resets at each hunk boundary.
- Source references written as pathlib joins — the actual idiom used throughout
  this codebase — were previously invisible to the scanner; they are now matched.
- Bare identifiers are now recognised, so the guard's own criteria example
  (`emit_agent_telemetry`) is detected rather than silently missed.
- Two deployed-path globs were missing from `scanned_source_globs` entirely: the
  `scripts/**` entries covering the deployed copies of `templates/workflows-js/*.js`
  and `templates/scripts/commit_guardian/*.py`. Without them, a presence-only
  assertion over the deployed surface — most of what a real consumer install
  actually has — passed silently.
- The guard's own `fixture_exempt_paths` config key is REMOVED. It was added so
  the guard would not block its own test file, on the stated justification that a
  `# presence-only:` waiver placed inside a fixture would be consumed by the
  scanner under test and invert the fixture's assertion. That justification does
  not hold: the scanner only ever receives the diff as a STRING argument, so a
  waiver comment in the test module's own Python source is invisible to the
  scanner and works exactly like any other waiver — verified directly. The
  exemption route was not just unneeded, it was strictly worse than the waiver it
  replaced: an exempt path skips the scan entirely and prints nothing, where the
  waiver route prints the accepted exception and its reason, which is the whole
  point of the AC. The key is gone, replaced by the ordinary waiver marker, plus a
  new regression test asserting that a stale or hand-added
  `fixture_exempt_paths` entry is now inert — the identical diff still violates
  with the key present, empty, or absent.

Also in this round: the E2 test harness now records a parse failure on
`HarnessResult.error`. One `console.log` inside a workflow body under test had
corrupted the harness's JSON payload and produced `dispatch_count=0` with
`error=""` — indistinguishable from a genuine clean zero-dispatch run, which is
exactly the failure class the harness exists to detect. And
`test_bp_100k_3_i.py` no longer builds into the developer's own live tree (its
`.leafcutter` is a symlink shared by every worktree on this machine); it now
builds into an isolated, consumer-shaped layout using the real `build.py` CLI and
all phases.

All of the above is green: 4447 passed, ruff clean.

## BO-1000c-1a — redefined twice, and still not done

`BO-1000c-1a` was redefined once during the epic's first pass, then re-scoped
again on 2026-08-25 and reverted to `work_status: todo`. Do not treat either
earlier version of this AC as settled.

First redefinition (2026-08-18): the shipped implementation obtained `fs` through
the CommonJS module loader inside a `try`/`catch` that logged a WARNING and let
the run report success. Under ADR-030 a workflow body has no module loader, so the
journal this AC required had never written a single line, while the AC read
`work_status: done` and ten presence-only tests grepped its call sites and stayed
green. The mechanism was deleted and the requirement was redefined onto the E2
engine's own per-run journal, dropping granularity from per-step to per-agent-
dispatch because that journal does not persist `log()` output.

Second re-scope (2026-08-25): an adversarial review found the AC had again been
marked done on coverage its own test module's docstring says cannot verify it.
The load-bearing clause is that the journal is "readable while the run is still
in flight." Every one of the five tests reads a JSON blob AFTER the harness's
subprocess has already exited — one of them is literally named
`test_agent_dispatch_records_are_still_readable_after_the_run_ends`, which
falsifies the in-flight clause rather than verifying it. The review also showed
the tests do not discriminate: deleting the E2 engine's journal file entirely
left all five tests green, because four of the five only assert that finalize
dispatches agents in monotonic step order, which is true independent of any
journal.

The AC's criteria were narrowed to keep only what the unit layer genuinely
proves — durability after process exit, dispatch order, and an absence guard on
the deleted mechanism reappearing — and `work_status` reverted to `todo`. The
in-flight requirement was not dropped; it moved to a new, open AC (`BO-1000c-4`)
rather than being quietly absorbed into a narrowed parent where it would look
resolved.

## Not covered

None of this hardening runs in CI. The drift gates (`check_build_drift`,
`check_output_drift`) are pre-commit-only, and `.build_manifest.json` is
gitignored — filed as `KI-BP-011`. Separately, the manifest still PREDICTS
deploy paths from phase-call conventions rather than observing what the build
actually wrote, which is the architectural root cause of the `.agents/rules`
defect above and remains true of the fix — filed as `KI-BP-012`.

The `cross_agent` failure classification still resolves by *skipping* the failing
phase rather than routing back to the agent that must do the work, and reports
those skips inside an otherwise-successful summary. Adjacent to the handoff-
routing defect fixed separately in `BO-3000`, but untouched here.

`BO-1000c-1b`, `BO-1000c-2` and `BO-1000c-2-i` consume the old journal contract
and must be re-read against the twice-revised one before they are built. This is
recorded on `BO-1000c-1a`'s `amended_by` entries rather than left for someone to
discover.
