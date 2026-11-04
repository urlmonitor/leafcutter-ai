---
title: "TQ-200d-1-v: refresh-gate row passes on one catching tagged test"
date: "2026-11-04"
time: "12:00"
type: manual
components: 
  - testing_quality
summary: "The refresh-gate eval row passes when one tagged test catches the wrong version."
description: "The test-writer wrong_version_run eval check now passes when one tagged test catches the wrong version; tagged tests that pass under it do not block, and a tagged test failing on the fixed version still fails the row. Resolves KI-TQ-20261102-wrong-version-run-requires-every-tagged-test-to-catch. The build-pipeline verdict is unchanged."
---

## Entry
