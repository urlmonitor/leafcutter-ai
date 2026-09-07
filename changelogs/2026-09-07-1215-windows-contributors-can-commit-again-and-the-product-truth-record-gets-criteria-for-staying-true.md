---
title: "Windows contributors can commit again, and the product-truth record gets criteria for staying true"
date: "2026-09-07"
time: "12:15"
type: manual
components: 
  - ux_prototyping
  - build_pipeline
  - ac_store
  - commit_guardian
summary: "A store-relative path built with the platform separator made the product-truth validator unpassable on Windows, which blocked every acceptance-criteria commit on that platform; the fix is one line, and the acceptance criteria the defect exposed now exist."
description: "load_flows() built each store-relative path with str(path.relative_to(STORE)), which renders with os.sep. index.json was generated on a POSIX host, so a Windows rebuild produced backslash paths and _check_derived_indexes reported drift against an unmodified, correct store. Because check-product-truth-validate fires on (^docs/product-truth/|^docs/acceptance-criteria/.*\.yaml$), a Windows contributor could not commit ANY acceptance-criteria YAML -- the only escape being --no-verify, which disables every other gate at the same time. The write direction was worse: a Windows run in write mode rewrote index.json with backslashes, breaking every POSIX contributor and CI, so the file flipped separator on each platform's turn. Paths in a JSON manifest are identifiers, not filesystem paths, so they are now emitted with .as_posix(); this is the only relative_to site in either script. Measured before the fix: 14 of 14 by_flow entries differed, all separator-only, zero genuine content differences -- never store drift. The regression test asserts on string content rather than a pathlib round-trip, which would pass vacuously on POSIX, the platform that cannot reproduce the bug, and is mutation-proved. Auditing the store for that defect surfaced that nothing specified the record's own lifecycle, so this also lands UXP-700 (a truthful project record) with five L1s cut by failure mode rather than by activity: no record or a fake one, a vacuous check passing as real, drift from the code, example content posing as the product, and a record outgrowing its reviewers. UXP-800 takes the production-side children off UXP-490, which was carrying nine against a 3-7 cap. No ids were renamed. covered_by is settled as a direct-children list and written into ac-schema.md, which also now records that declares_side_effect is derived from the record's own Then clause rather than authored. All 72 records are approved -- draft and reviewed are both scanner-invisible, so approval is what makes them buildable. Three known-issues entries were filed; two remain open."
pr: 731
adrs: []
commits: 
  - 26f35212
  - 18cf1b5d
  - e6303df9
  - 61e76b58
breaking: false
---

## Entry
