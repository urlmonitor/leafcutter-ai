---
title: "KI-BO-20260927-quick-fix-gitignored-target — /quick-fix takes a gitignored deployed copy as target_file, so a coder that correctly edits the tracked template trips the scope-expansion halt"
description: "medium — quick-fix.js never checks whether target_file is tracked; the dirty-file guard and the scope guard both key on the literal path, so the correct fix (the template) is reported as scope expansion. Observed 2026-09-25 on scripts/commit_guardian/check_ac_governance.py."
type: reference
category: reference
status: active
created: '2026-09-27'
last_updated: '2026-09-27'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-010.md
---

# KI-BO-20260927-quick-fix-gitignored-target — /quick-fix takes a gitignored deployed copy as target_file, so a coder that correctly edits the tracked template trips the scope-expansion halt

- **Severity:** medium. The run halts with a false "scope expansion" after the fix is already written. No wrong code lands, but the run has to be finished by hand.
- **Status:** open — no AC. The missing check is confirmed in code. The halt was observed live.
- **Occurrences:** 1 (2026-09-25, `/quick-fix` for ACS-400e-5)
- **First seen:** 2026-09-25 · **Last seen:** 2026-09-25
- **Where:** `templates/workflows-js/quick-fix.js` — the diagnosis guard at `:219-226` accepts any `target_file` string. The dirty-file check at `:345-348` greps `git status` output, which never lists ignored files. The fix constraint is at `:668-686`, and the scope-expansion halt at `:725-742`.

## Symptom

`target_file` was `scripts/commit_guardian/check_ac_governance.py`. That path is build output:
`git check-ignore -v` reports `.gitignore:12:scripts/commit_guardian`. Its tracked source is
`templates/scripts/commit_guardian/check_ac_governance.py`. `python-coder` correctly edited the
template. The guard then halted:

```text
Fix (scope expansion): python-coder reports the fix requires changes beyond
scripts/commit_guardian/check_ac_governance.py.
Additional files needed: templates/scripts/commit_guardian/check_ac_governance.py, <build copy>
```

## Mechanism

Nothing between the guard at `:220` and the fix phase asks whether `target_file` is tracked.
The literal path is then used as the only file the coder may change (`:673`) and as the one
expected modified path (`:733`). If the coder follows the repo rule "edit the template, never
the build copy", the template is by construction an unexpected extra file. If the coder edits
the ignored copy instead, the change can never be committed and the next `build.py` erases it.
Either way the pipeline cannot succeed. The dirty-file guard at `:345` has the same blind spot,
because `git status --porcelain` omits ignored paths.

## Fix direction

In the Guards phase, run `git check-ignore -q -- <target_file>` and `git ls-files --error-unmatch -- <target_file>`.
When the file is ignored, map it to its tracked source (the build manifest already records
output-to-source mappings; `templates/<path>` is the common case) and continue with that path,
logging the substitution. If no source can be found, refuse up front with the advice "pass
the tracked source path". Add a harness test that uses an ignored target.

**Pattern:** a single-file guard keyed on a path the repository does not own, so the correct change always looks out of scope.
