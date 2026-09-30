---
title: "File-size gate refusals now quote a length you can reproduce, and stop promising help they cannot deliver"
date: "2026-09-28"
time: "08:58"
type: manual
components: 
  - commit_guardian
  - precommit_hooks
summary: "Fixed the pre-commit file-size check so the line count it quotes when refusing a file actually matches the published limit, added an automated check that catches the two from drifting apart again, and removed a suggestion to run a helper that cannot act on a pre-commit refusal."
description: "5 commits on EPIC-FilesStayWorkable (PR #937): a line-counting bug in commit_guardian/check_file_size.py overcounted every file with a docstring or block comment, so refusals quoted a length longer than the rule allows; describe_measurement_rule() now derives the published rule from the live counting behaviour and both refusal paths print it; a new check-file-size-rule-parity gate reconciles published vs enforced limits; the size refusal no longer suggests /code-refactoring-specialist. 4 of 9 GE-127 tickets; GE-127e-3 stays todo pending its GE-127e-3-i constraint child."
pr: 937
commits: 
  - 03913a68
  - aaa021a3
  - 625685d5
  - 2a481150
  - 194a12c5
breaking: false
---

## Entry

The file-size commit gate was refusing files while quoting a line count the
author could not reproduce, and offering help that never arrived. Four
changes on this branch fix that.

**The refusal number was wrong.** `count_content_lines` left one phantom
counted line behind for every triple-quoted string or block-comment region it
discarded, so every Python file measured LONGER than the published rule
implied — the error scales with how many docstrings a file has.
`check_file_size.py` itself was measured at 293 lines where the published
rule, applied by hand, gives 277 (the limit for a `.py` file is 400, so this
file was never actually at risk — the point is that the two numbers
disagreed at all). Fixed; a `\r?` correction closes the same gap on CRLF
files.
**This means some files previously refused as over the limit were not
actually over it.**

**The rule is now published, not hand-maintained.** `describe_measurement_rule()`
states the counting rule by probing the live behaviour of the counting
function itself, so the stated rule cannot drift from the code that enforces
it. Every refusal now prints a `Measures:` line, and both refusal paths —
crossing the limit, and growing further while already over it — state the
permitted length.

**A new gate catches drift between the two.** `check-file-size-rule-parity`
reconciles the published rule against the enforced one across every
configured surface, so a limit corrected in one place and left stale in
another no longer passes silently.

**The refusal stopped pointing at `/code-refactoring-specialist`.** The
command exists and works, but it is a live-agent-session affordance; the
refusal fired from a non-interactive pre-commit subprocess where nothing can
act on it. A plain verdict replaces a promise the tool could not keep.

This lands 4 of the 9 tickets in the GE-127 tree. `GE-127e-3` stays
`work_status: todo` — its constraint child `GE-127e-3-i` is not yet built —
and the remaining five tickets will be built fresh off current `main`.
