---
title: "A test that keeps passing only on retry now turns the post-merge run red"
date: "2026-10-09"
time: "23:45"
type: manual
components: 
  - testing_quality
summary: "Correctness tests that pass only on retry are now listed on a separate post-merge-flaky issue that never holds pull requests, and a test that does so in two of the last five runs makes the run red."
description: "A shared-layout test that fails and then passes on a fresh machine may be catching a real, intermittent corruption, so a single retry pass is no longer only a log line. Each such test is listed, with the run's link and how many of the last five settled runs it passed on retry in, on a post-merge-flaky issue; that issue never affects whether pull requests are held, and it closes once all five runs have been read and none had one. A test that passed only on retry in two of the last five runs makes the run red and is named in the run summary. The count comes from the earlier runs' saved results, never from the issue, so closing or editing the issue changes nothing; a run whose history could not be fully read says so in its summary. A red run followed by a green run on the same commit names its failing tests on the same issue as candidates for the timing lane. Timing-lane tests never escalate. The window and threshold live in post_merge_tunables.json."
---

## Entry
