---
title: "Build pipeline: CI test shards install the Atlas web toolchain, so real-vitest proof tests run"
date: "2026-10-06"
time: "15:10"
type: manual
components: 
  - build_pipeline
summary: "The real-vitest done-proof tests now run in the CI test shards instead of failing for a missing toolchain."
description: "The CI test shards installed only the Python dependencies, so the composite real-vitest done-proof test failed on every shard run with a missing-toolchain error. Every test shard now sets up Node 20 and installs the Atlas web dependencies before pytest, exactly as the done-proof job does (about 30 seconds per shard). One rule now covers proof tests that need a runtime: a missing runtime fails with an install hint, because a skip is not proof; the only skip is a platform where the code cannot run at all (Windows, where the vitest launcher cannot start). The JS done-proof integration tests follow that rule instead of skipping whenever vitest was absent. Ticket: CiShardsInstallWebToolchain (2026-10-06)."
commits: []
---

## Entry
