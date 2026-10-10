---
title: "A red post-merge run now opens one issue that says what broke and since when"
date: "2026-10-09"
time: "13:30"
type: manual
components: 
  - testing_quality
summary: "When the post-merge suite goes red on main, one issue labelled post-merge-red is opened or updated with the failing tests and the commits merged since the last green run, and the next green run closes it."
description: "A new Post-merge follow-up workflow runs after each completed Post-merge suite run. A red or incomplete run opens one issue labelled post-merge-red, or updates the open one, listing the failing tests, a link to the run, and the commits merged since the last green run on main. A green run closes the open notice with a link to the green run. Only the newest settled run on main may write, re-applying the same result writes nothing, and duplicate notices are closed in favour of the oldest. The workflow refuses to write when its verdict disagrees with the run's own conclusion or when the verdict artifact failed to download, re-labels or closes a notice created without its label, and never claims there is no green run when it only looked at the last hundred runs. Test names and commit subjects are shown inertly, so they cannot ping anyone or forge the notice's recorded state. Runs of the timing and fix-proof suites do not write this notice."
---

## Entry
