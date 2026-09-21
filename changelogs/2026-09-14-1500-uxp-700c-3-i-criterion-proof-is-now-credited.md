---
title: "UXP-700c-3-i's forward-slash index-key test is now credited as its criterion proof"
date: "2026-09-14"
time: "15:00"
type: manual
components: 
  - ux_prototyping
summary: "The test that index path keys use forward slashes on every platform now carries the name and covers/angle tags its ticket promised, so the proof-promise gate can credit UXP-700c-3-i's criterion angle."
description: "UXP-700c-3-i's ticket promises a criterion-angle test that index keys built from OS-native path objects are emitted with forward slashes, whatever the host's path separator. The assertion already existed as test_load_flows_emits_no_backslash_on_any_platform, but under a different name and with no covers or angle tags, so check-proof-promise-claim refused to let the ticket be marked done. The test is renamed to test_index_path_keys_use_the_canonical_separator_on_every_platform and tagged. It also now checks the index entry build_by_flow builds from the loader's key, not just the loader's output. No production code changes."
commits: 
breaking: false
---

## Entry
