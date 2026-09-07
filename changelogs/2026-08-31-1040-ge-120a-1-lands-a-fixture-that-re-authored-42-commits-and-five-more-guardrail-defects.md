---
title: "GE-120a-1 lands, a test fixture that re-authored 42 commits is stopped, and five more guardrail defects are filed"
date: "2026-08-31"
time: "10:40"
type: manual
components:
  - ac_store
  - build_pipeline
  - commit_guardian
  - testing_quality
summary: "Completes the first ticket of EPIC-TrustThatAGreenCheckActuallyChecked, salvages an abandoned drive's uncommitted work, repairs an unparseable documentation contract in all 25 applicable tickets, and files six execution-verified known issues including a test fixture that had been silently re-authoring every commit in the repository."
description: "One acceptance criterion is complete: GE-120a-1 — a check that could not perform its inspection now reports a degraded outcome rather than a clean pass — with work_status done, implemented_by and covered_by populated, and its code, architecture doc and AC record committed. Around it, three pieces of recovery and repair. First, an earlier abandoned drive had left 5,728 insertions uncommitted in the worktree; these are salvaged as an explicit WIP commit (red-baseline tests for GE-120a-1, a-4, b-2-i, c-1-i, e-1-i, e-3-ii and e-4-i, the new check_outcome.py, and edits to four commit-guardian checks), with the branch then brought current with origin/main from 52 behind and audited for non-additive deletions. 35 of those tests pass and 18 remain red under xfail-masking for acceptance criteria whose implementations are not yet written; the commit message says so rather than implying an epic that is further along than it is. Second, documentation-verifier was fail-closing on every ticket in the epic: its Step 2 parses the target documentation path as the second pipe-delimited field of each AC-N line in the documentation-expert contract block, while the generator emits a bracketed genre and an em-dash separator, so required_docs came out empty and the agent blocked at priority 11.9 without ever reaching the diff check — on ticket 01 the required doc was in fact present. Scoped measurement found 0 of 25 applicable tickets parseable; all 25 are rewritten and re-measured at 25 of 25. The 12 tickets with no contract block are the 12 without documentation-expert in their agents map, so their absence is correct. A whole-file grep reports 2 tickets as already correct and both are false — the pipe it matches is inside documentation-verifier's own blocker comment quoting the expected format as remediation — and that measurement trap is recorded alongside the entry. Third, six known issues, each verified by running the code rather than reading it. KI-TQ-012 (high): unit_tests/portability/test_ge_120e_1_i.py builds its sandbox with git worktree add from the real repository and then sets user.email and user.name with git config inside it; a linked worktree shares .git/config with its parent, so the identity landed in leafcutter-ai/.git/config and every one of the workspace's worktrees and sessions inherited it — 42 commits across local branches are authored GE-120e-1-i fixture, from sessions that never ran these tests, and teardown removes the worktree without ever unsetting the keys. Nothing reached main because squash-merge rewrites the author, which is exactly why it went unnoticed for eleven days. Both keys are unset; the 42 commits are left as they are. KI-CG-035 (medium): check_hook_parity resolves runtime_dir and deployed_output_dir from Path.cwd() as distinct configured paths, but scripts/commit_guardian is a build-created symlink to .leafcutter/scripts/commit_guardian, so its two parity legs compare one directory and the runtime-versus-canonical question is never asked; under the shared-install symlink the pre-drive checklist recommends, it reports another branch's files as defects in yours and its run build.py remediation would deploy unmerged templates over the tree every other session reads. A third defect was added after a second observation: it fail-opens to a silent exit 0 when its roots do not resolve, where two sibling hooks resolve correctly or fail closed from the same directory. KI-CG-20260831-glossary-coverage-detector-path-unreachable (high): check-glossary-coverage loads its detector from a path present in no leafcutter layout, fail-opens to exit 0 on nearly every commit, and its dedicated detector-not-found message is dead code because spec_from_file_location returns a populated spec for a nonexistent path — so a blanket handler relabels the FileNotFoundError as an unexpected error, and CLAUDE.md documents the hook as live and auto-dispatching. KI-CG-20260831-twenty-hooks-registered-nowhere (high): twenty check scripts sit in the canonical directory registered in no manifest, no pre-commit config and no CI workflow, ten of them carrying live-looking config blocks with thresholds; check_ac_coverage prints 178 no-coverage warnings and exits 0, check_doc_coverage crashes with an unhandled traceback, and check_ticket_test_requirements hangs. KI-CG-20260831-test-ac-tags-dead-three-ways (medium): the test-to-AC traceability gate is unregistered, warn-only by default, and the config key that would escalate it is absent from the shipped config; it found 20 real untagged tests in one file and exited 0. KI-BP-20260831-generator-emits-unparseable-doc-contract (high): the format defect above traced to its source — this is the second epic to hand-fix the generator's output rather than the generator, and making the line parseable exposes two content defects it does not cure, a directory from an unrelated AC family named as a documentation target and six tickets naming source files as documentation targets, which may satisfy the diff check incidentally and report a documentation gate satisfied on a commit that documented nothing. KI-CG-024 is also corrected in place: it describes check_ticket_signoff_parity as live and silently skipping check 6, when the hook is unregistered and skips all six because it never runs, while precommit-autofix.json carries autofix routing for it. New entries use the KI-AREA-YYYYMMDD-slug form, sequential numbering having been retired after it produced ten collisions in a day. The epic remains incomplete: 36 of 37 tickets are outstanding, ticket 02 will still fail because its documentation target is a directory, and one ticket drive costs roughly 1.3 million subagent tokens — an earlier full-fan-out drive exhausted the API quota and completed nothing, reporting nine tickets as blocked with prose indistinguishable from genuine blockers."
breaking: false
---

## Entry

### Completed

- **`GE-120a-1`** — a check that could not perform its inspection reports a degraded outcome, not
  a clean pass. `work_status: done`, `implemented_by` and `covered_by` populated.

### Recovered

- Salvaged 5,728 uncommitted insertions from an abandoned earlier drive; merged `origin/main`
  (52 behind) with a non-additive-deletion audit.
- Repaired the documentation contract in **25 of 25** applicable tickets (0 were parseable).

### Filed

| Entry | Severity |
|---|---|
| `KI-TQ-012` — fixture set git identity in the shared repo config; 42 commits re-authored | high |
| `KI-CG-035` — parity hook's two legs alias to one directory; unsafe remediation; fail-open | medium |
| `KI-CG-20260831-glossary-coverage-detector-path-unreachable` | high |
| `KI-CG-20260831-twenty-hooks-registered-nowhere` | high |
| `KI-CG-20260831-test-ac-tags-dead-three-ways` | medium |
| `KI-BP-20260831-generator-emits-unparseable-doc-contract` | high |

Plus an in-place correction to `KI-CG-024`.

### Also in this PR (2026-09-01)

Three more acceptance criteria landed after the entry above was written:

- **`GE-120c-1`** — an out-of-process harness that runs the *deployed* checks from a real
  second working copy, asserting only on observable subprocess output. Its self-demonstration
  clause is covered: pointed at a source-tree-only check, the harness fails.
- **`GE-120e-1`** — one shared authored-change derivation (`_authored_change.py`) that both
  self-deriving checks consume, so "what did the author change" has a single answer. A git
  failure reports could-not-check rather than re-widening to the whole staged tree. ADR-038.
- **`GE-120e-2`** — the manifest now declares `change_set_source` on all 59 entries; absent is
  a failure naming the entry, never a default. ADR-038 Amendment 2.

Four `pr-reviewer` findings were closed along the way, three of them the same defect shape: a
sibling test file authored against a speculative API the implementing ticket named differently.
Also fixed an unreachable `except json.JSONDecodeError` branch shadowed by a preceding
`except (OSError, ValueError)`, and a DECISION HISTORY entry that claimed a refactor the diff
did not contain.

### Still open

34 of 37 tickets. Three red-baseline test files are deferred out of this PR and recorded in the
epic's Master_Plan with restore instructions — they cover ACs that are not built, and CI's
`AC_ENFORCE_STRICT=1` correctly refuses to merge a red baseline (`KI-TQ-011`). Ticket 36's file
additionally carries its own fixture bug (no `mkdir` before `git init`). Ticket 02's
documentation target is a directory from an unrelated AC family; six tickets name source files
as documentation targets.
