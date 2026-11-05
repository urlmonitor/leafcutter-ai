---
title: A drift check that cannot read the build record now says so instead of passing
date: "2026-11-04"
time: "12:00"
type: manual
components: 
  - build_pipeline
summary: "check-build-drift and check-output-drift no longer warn and exit 0 when .build_manifest.json is missing or unreadable; they report that they could not read it, naming the project and the record file, with an exit code distinct from the all-clear."
description: "BP-1500d-4. Absent record: 'COULD NOT READ the build record .build_manifest.json for the project at <project>', exit 3. Present but unreadable (malformed JSON, or entries keyed to the location the record was written in): the same report marked INDETERMINATE, exit 2. Exit 0 remains the all-clear only. Effect: a commit in a checkout whose install was never built is now refused by these two hooks until build.py is run. The tests that asserted the old exit-0 fail-open (BP-100k-3 H-1, GE-118b) are updated."
breaking: false
---

## Entry
