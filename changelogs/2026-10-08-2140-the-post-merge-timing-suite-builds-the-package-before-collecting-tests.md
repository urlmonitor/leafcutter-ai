---
title: "The post-merge timing suite builds the package before collecting tests"
date: "2026-10-08"
time: "21:40"
type: manual
components: 
  - testing_quality
summary: "The new timing suite went red on its first runs even though both of its timing tests passed, because it did not build the package first; it now does."
description: "Selecting tests by marker still makes pytest import every test module, and four modules import files that only exist after the package build. Without that build the first two runs of the Post-merge timing suite on main failed on four collection errors, while the two timing tests themselves passed. The workflow now runs the build step before the timing lane, as the main CI test shards do. The requirement's notes record what the first runs showed."
---

## Entry
