---
title: "KI-BO-20261009-completion-write-refuses-closes-the-script-allows — /build-feature's ticket close is a status-checker agent relaying a relative script call, and on the BO-4300 drive it refused closes that the shipped script and protocol both permit"
description: "high — writeTicketCompletion asks status-checker to run 'python3 scripts/set_ticket_status.py ... --status done'. On the BO-4300 drive it refused once citing the auto-close merge-commit condition, which status-checker.md has exempted for this dispatch since 2026-09-22, and once calling todo -> done an invalid transition, which every reachable copy of the script allows. The driver never sets in_progress, so every close is todo -> done, and the script's own --force help still says that transition needs --force. Separately verified: the command is a bare relative path that does not exist from the workspace parent or in a consumer install."
type: reference
category: reference
status: active
created: '2026-10-09'
last_updated: '2026-10-09'
components:
  - build_orchestration
  - supervisor_system
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/build-orchestration/open-low-ki-bo-20260831-1932.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260927-status-checker-runs-workflow-shell-commands.md
  - docs/architecture/adrs/ADR-047-single-writer-ticket-close-path.md
---

# KI-BO-20261009-completion-write-refuses-closes-the-script-allows — the close is an agent's judgment, not the script's verdict

- **Severity:** high. A ticket whose every phase passed is left open. The epic stalls on it,
  because the planner counts a dependency as met only when the ticket reads `done`
  (`build-feature.js:3078`), and the operator has to close it by hand, which is the very route
  ADR-047 closed.
- **Status:** open, no AC. The two refusals are session observations and their text was not
  retained here. The verified part is what the shipped code and templates say.
- **Occurrences:** at least 2 refusals during the BO-4300 drive (2026-09-28 to 2026-10-09).
- **First seen:** during the BO-4300 drive · **Filed:** 2026-10-09
- **Where:** `templates/workflows-js/build-feature.js:1324-1338` (`writeTicketCompletion`, the
  command at :1328); twin `templates/workflows-js/build-ticket.js:1156`;
  `templates/agents/status-checker.md:121-207` (Closing protocol and the auto-close trigger);
  `scripts/set_ticket_status.py:62-69` (allow-list) and :494-499 (`--force` help).

## Symptom

1. Earlier in the drive, the completion write was refused because the ticket's commit was not on
   `main`. That is the investigation-path auto-close condition. It can never hold inside an epic,
   whose branch is unmerged by construction.
2. Later, the completion write was refused as an invalid `todo -> done` transition.

## What the shipped code says

- **The merge condition does not apply to this dispatch.** Since `5a25ecfad` (2026-09-22),
  `status-checker.md:197-207` says the driver-dispatched write "does not reach this trigger at
  all". The dispatch prompt says the same (`build-feature.js:1326`). The epic branch was cut on
  2026-09-27, after that commit. So refusal 1 was the agent applying a rule that its own prompt
  exempts. Inferred cause: one prompt holds both the closing protocol and the auto-close trigger,
  and the model picked the wrong one.
- **`todo -> done` is allowed.** `ALLOWED_TRANSITIONS` includes `("todo", "done")` without
  `--force` (`scripts/set_ticket_status.py:62-69`, BO-400e-3). The same holds in every copy this
  drive could reach: the epic worktree's `scripts/` and `.leafcutter/scripts/`, and the workspace
  parent's `.leafcutter/scripts/`. So refusal 2 was not the script's allow-list.
- **The driver never sets `in_progress`.** `grep in_progress build-feature.js` finds nothing, so
  every close it attempts is from whatever status the ticket already holds, usually `todo`.
- **The script's help contradicts its allow-list.** `--force` is described as "Required for
  transitions like done -> in_progress or todo -> done" (:497-498). Inferred: an agent that reads
  `--help`, or reasons from it, will conclude `todo -> done` is invalid.

## Verified latent defect: the command path

`build-feature.js:1328` runs the bare relative path `python3 scripts/set_ticket_status.py`. Every
other script call in the file uses `{{config.output_root}}/scripts/...` (for example :1640), and
`finalize-feature.js:1496` uses `${WORKTREE_ROOT}/{{config.output_root}}/scripts/set_ticket_status.py`.

- The build deploys workflow tools into the output root (`scripts/build.py:1485-1487` passes
  `output_root` to `build_workflow_tools`), so a consumer install has
  `.leafcutter/scripts/set_ticket_status.py` and no `scripts/set_ticket_status.py`. The shims copy
  only `scripts/commit_guardian`, `scripts/doc_compliance` and `scripts/feedback`.
- In this repository the relative path works only because the package source is tracked at the
  checkout root. From the workspace parent, `scripts/` holds only `commit_guardian`,
  `doc_compliance`, `feedback` and `langfuse` (verified 2026-10-09), so the call fails.

Not observed failing this way on this drive. Recorded because it is the same write, and a refusal
from a missing file would look the same in the run report.

## Impact

Completion depends on how an agent interprets a two-rule prompt, so identical records can close or
not close. Combined with the planner's done-only dependency rule, one unclosed ticket blocks every
dependant. The usual remedy is a hand-written `status: done`, which bypasses the parity check that
the single-writer path exists to enforce.

## Fix direction

- Run `set_ticket_status.py` directly from the workflow, through a command step with no judgment
  (`command-step-runner`), and branch on its exit code. A close needs no agent.
- Use `{{config.output_root}}/scripts/set_ticket_status.py` with an absolute worktree root, as
  `finalize-feature.js` does. Change the twin in `build-ticket.js` too.
- Fix the `--force` help text to match the allow-list.
- If an agent must stay in the path, give the completion write its own prompt that does not
  contain the auto-close trigger at all.

**Related.** `KI-BO-20260831-1932` records how this write came to route through the script, and
the `todo -> done` widening. `KI-BO-20260927-status-checker-runs-workflow-shell-commands` covers
status-checker relaying shell commands it is registered as not permitted to run.
