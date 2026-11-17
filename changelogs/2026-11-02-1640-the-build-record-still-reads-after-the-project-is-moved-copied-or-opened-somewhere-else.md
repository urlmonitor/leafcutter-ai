---
title: "The build record still reads after the project is moved, copied or opened somewhere else"
date: "2026-11-02"
time: "16:40"
type: manual
components: 
  - build_pipeline
summary: "Template entries in .build_manifest.json are now recorded relative to the package, so the record keeps working when the project moves; an old location-bound record read after a move is reported as unreadable instead of as missing files."
description: "BP-1500d-2. build_helpers.py writes package-relative template keys (templates/...) and keeps the package position in package_root. check_build_drift.py re-anchors those keys through package_root and still accepts older records. check_output_drift.py reports a record whose keys are bound to the old location as UNREADABLE, naming the record and the project. The BP-1500d-1-i manual tests are updated to the new key shape."
breaking: false
---

## Entry
