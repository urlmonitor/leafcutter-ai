---
name: pr-review
description: |
  Workflow body for the /pr-review slash command.
  Owned by the pr-reviewer agent — invoke that agent rather than this
  workflow directly for model-pinned execution.
arguments:
  - name: action
    description: "auto (default) | target <ref> | explain <N>"
    required: false
---

# /pr-review — Pre-PR Self-Review

Invokes the `pr-reviewer` agent against the working diff.

## Usage

```
/pr-review                      # auto: review working diff vs base branch
/pr-review auto                 # same as above
/pr-review target <ref>         # review diff vs a named branch or SHA
/pr-review explain <N>          # deep-explain finding H-N or M-N from last review
```

## What It Does

1. Checks whether there is a diff to review. If the working tree is clean, reports "no diff to review" and exits.
2. Invokes `pr-review-toolkit:review-pr` against the diff (does NOT call sub-skills directly).
3. Classifies every finding as high / medium / low confidence.
4. Surfaces high-confidence findings; suppresses low-confidence ones with a visible tally.
5. When medium-confidence findings exceed 3, bundles them and escalates to Opus for a promote/drop decision.
6. Merges the Opus decision into the final report.
7. Always appends an `## Escalation` section naming the branch taken and the one-line reason.
8. **files_touched drift check** (non-blocking):
   1. Run `git diff --name-only $(git merge-base HEAD origin/main)..HEAD` to collect the set of actually-changed files.
   2. Infer the ticket path from the branch name (pattern: look for a `tickets/**/*.md` substring in the branch name) or by scanning `git log --oneline -20` for commit messages containing `tickets/.../*.md`. If neither yields a path, skip the step and emit a note: "files_touched drift check skipped: ticket path not inferable".
   3. Read the `files_touched` list from the inferred ticket's YAML frontmatter.
   4. Compute `actual − declared` (high-confidence: files changed but not listed in `files_touched`).
   5. Compute `declared − actual` (medium-confidence: files listed in `files_touched` but not changed; often intentional — agent may have found a more authoritative target).
   6. If both sets are empty, emit nothing. Otherwise emit the drift comment block using the format in "Output Format → files_touched Drift Comment" below.
   This step is strictly read-only: it runs only `git` read commands and reads the ticket file. It never modifies the ticket or any source file. The overall pr-reviewer status remains `ok` regardless of drift findings.

## Output Format

```
### Review Report

Base: <branch>
Diff size: <N lines across M files>

#### High-Confidence Findings
[H-1] <file>:<line> — <summary>
      <explanation>
      Sub-skill: <name>

#### Medium-Confidence Findings      (only when count <= 3 or Opus promotes)
[M-1] <file>:<line> — <summary>
      <explanation>
      Sub-skill: <name>

#### Suppression Tally
Suppressed: X low-confidence nits, Y medium findings dropped by Opus.
Run /pr-review explain <N> to re-examine any finding in detail.

## Escalation
Branch: <none | opus>
Reason: <one-line>

## files_touched Drift Comment    (only emitted when drift is detected)
files_touched drift detected:
  Actual changes not declared:
    - <path>
  Declared but not changed (may be intentional):
    - <path>
Update the ticket frontmatter or accept as intentional.
```

## Safety

`pr-reviewer` is read-only. It never modifies code, stages files, commits, or pushes. To act on findings, use `python-coder` or `sql-coder`.

For cross-file questions raised during `explain`, the agent delegates to `research-agent`.
