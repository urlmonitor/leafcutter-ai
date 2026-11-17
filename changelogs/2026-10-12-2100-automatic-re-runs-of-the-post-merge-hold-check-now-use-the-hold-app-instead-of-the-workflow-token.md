---
title: "Automatic re-runs of the post-merge hold check now use the hold App instead of the workflow token"
date: "2026-10-12"
time: "21:00"
type: manual
components: 
  - testing_quality
summary: "When the post-merge result changes, pull requests whose hold check needs a re-run are now re-run with the dedicated hold GitHub App; the workflow token can no longer request any re-run."
description: "The earlier approach asked GitHub to re-run a pull request hold check with the workflow token, and the re-run failed on start-up. The follow-up job now runs in the post-merge-hold environment, mints a short-lived token for the hold App scoped to Actions write on this repository only, and uses it solely to request the re-run; every read still uses the workflow token, which no longer holds any write scope on that job. If the App credential is missing or cannot be minted, nothing is re-run and each pull request that needed a re-run is listed in the post-merge notice with the reason rerun_no_credential. Re-runs stay off until the repository variable POST_MERGE_REEVAL_RERUN is set to true, which should be done only after the App has Actions: Read and write permission and the installation has accepted it."
---

## Entry
