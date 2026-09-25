---
title: "A ticket marked done with a phase still open is now blocked at commit"
date: "2026-09-25"
time: "16:00"
type: manual
components:
  - commit_guardian
  - build_orchestration
summary: "The sign-off parity hook only checked a done ticket for a phase that was still open when the file sat in a done/ folder. Tickets have not been moved there since the frontmatter status: field became the lifecycle signal, and the hook runs without --enforce. A ticket reading status: done with pull-request: needed was therefore committed with no complaint. The hook now blocks a commit when a status: done ticket still lists any phase as needed or failed, wherever the file lives. All other parity findings stay warnings, as before."
description: "Before this change, check_ticket_signoff_parity.py applied the rule that a done ticket may have no needed or failed phase only to paths containing /done/. It also decided whether to block based on that path segment. BO-400c-1 retired the done/ move, so the rule never ran on new work. As a result, 51 tickets on main read status: done with pull-request: needed (KI-CG-20260925-signoff-parity-enforces-only-under-done-folder). The hook now reads status from the frontmatter with its existing parser. It reports each needed or failed agent on a status: done ticket, and only that report blocks the commit. Every other parity finding on a done ticket, such as a Sign-offs gap or a missing cross_layer_seam_answer, stays warn-only. Blocking those as well would have locked 638 of the 725 done tickets against any edit. Legacy done/ paths and --enforce still block on every violation. A missing, non-string or unparseable status counts as not done and never crashes the hook. Covered by BO-400c-5. The tests run the real hook on ticket files in a temp directory. One of those files uses CRLF line endings, and another test proves that a done ticket with only a non-blocking finding still exits 0 with the warning shown. Reverting the fix turns the two blocking tests red again. The existing done tickets are not reconciled here: 109 of them would now fail this rule if staged."
commits: [ddc4e47a]
breaking: false
---

## Entry
fix(commit-guardian): block a status: done ticket that still has a needed or failed phase (BO-400c-5)
