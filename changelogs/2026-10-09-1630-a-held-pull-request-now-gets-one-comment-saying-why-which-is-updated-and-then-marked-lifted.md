---
title: "A held pull request now gets one comment saying why, which is updated and then marked lifted"
date: "2026-10-09"
time: "16:30"
type: manual
components: 
  - testing_quality
summary: "When the Post-merge suite status check holds a pull request, it posts one comment explaining why, edits that same comment on every later check, and marks it lifted once the pull request passes."
description: "The Post-merge suite status check now explains itself on the pull request. While a pull request is held, one comment from the check states the reason in plain words: which tests are failing on main and since when, with links to the run and the post-merge-red notice and the commits merged since the last green run; or that the last run did not complete, is stale, or could not be read. Each later check edits the same comment, recording when it was judged and for which head commit, and never adds a second one. When the pull request passes, the comment is edited once to say the hold was lifted and why, with the earlier details folded away. The check only ever edits its own comment on that pull request, shows test names and other untrusted text as plain code so they cannot ping anyone, never sends its token to another site, and a failure to write the comment never changes whether the pull request is held."
---

## Entry
