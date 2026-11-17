---
title: "The one-knowledge-sink-outside-every-worktree requirement INF-400c-4 is marked done again"
date: "2026-10-14"
time: "18:11"
type: manual
components: 
  - infrastructure
summary: "INF-400c-4, the requirement that knowledge is written to one sink outside every working copy, is marked done again because the condition set when it was reopened has been met."
description: "One AC-store commit (bc4511c7d), store data only. Flips INF-400c-4 work_status from todo to done and adds an amended_by entry; criteria are unchanged. It was reopened on 2026-10-09 to return to done when the INF-500d-4 feedback-sink feature landed. That feature is on main (#1169, #1207, #1221; INF-500d-4 done). Children INF-400c-4-i, -iii, -iv, -v and -vi are done; -ii is superseded, and check-done-proof skips superseded children since the KI-ACS-016 fix (#1229)."
commits: 
  - bc4511c7d
breaking: false
---

## Entry

**INF-400c-4 is marked done.** It was reopened on 2026-10-09 with the note "return to done
when the INF-500d-4 feedback-sink feature lands". That feature is now on main (#1169, #1207
and #1221), and INF-500d-4 is done.

- **Children:** -i, -iii, -iv, -v and -vi are done. The only other child, -ii, is superseded.
- **Proof check:** check-done-proof skips superseded children since the KI-ACS-016 fix
  (#1229). Before that fix, -ii was the sole reason this flip was refused on 2026-10-12.

Only `work_status` changed (todo to done), with an `amended_by` entry. The criteria are
unchanged. No code changes.
