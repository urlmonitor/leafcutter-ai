---
title: "Reference pages and two diagrams explain the wrong-version runs and the consumer-test sweep"
date: "2026-10-23"
time: "16:00"
type: manual
components:
  - testing_quality
  - build_orchestration
summary: "New docs/reference/wrong-version-runs.md explains which tests are in scope, which wrong versions run, every result word and stop reason, the put-back, the four routes and the /build-epic backstop. docs/reference/consumer-test-sweep.md lists what the sweep checks before every commit and the words of its findings. Two C4 level-3 diagrams show the components (c3-035) and one run from alteration to put-back with its failure paths (c3-036)."
description: "TQ-500g-5, TQ-500g-5-i, TQ-500g-5-ii (docs only). User decisions 2026-10-23: the reference is split into a main page and a sweep companion; docs/how-to/fast-lane-build.md and docs/testing/test-angles.md get one pointer each without growing; the diagrams are root L3 diagrams. The pages follow the merged code where it differs from the AC text (recorded in the ACs). Known limits documented, including verified reading true with applicable false when no covering test is in scope (filed as a known issue)."
commits:
breaking: false
---

## Entry

The wrong-version runs and the consumer-test sweep now have reference pages. If a build
stops before it commits, look up the reason it printed on these pages. They say what the
reason means and what to do about it, for example strengthen the test, record the edit, or
put the code back.
