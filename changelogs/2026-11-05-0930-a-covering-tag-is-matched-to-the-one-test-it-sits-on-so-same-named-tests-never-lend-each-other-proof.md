---
title: "A covering tag is matched to the one test it sits on, so same-named tests never lend each other proof"
date: "2026-11-05"
time: "09:30"
type: manual
components: 
  - testing_quality
summary: "New shared matcher scripts/ac_store/covers_tag_identity.py ties each covers tag to its test by file, class chain and function; the done-proof check and the red-baseline reader both use it."
description: "TQ-500f-3-iii. scripts/ac_store/covers_tag_identity.py matches a tag on file path, class chain and function name, judges every parametrised case, resolves a test inherited from a mixin to every inheriting class, and refuses a tag that matches two tests as ambiguous_test_identity naming every candidate; a unique name-only match is still allowed. Nodeids with '..' components (tests outside the pytest rootdir) resolve to the same file. done_proof.py and the fast-lane red-baseline reader (_fl_red_baseline_support.py, _fl_common.py, fast_lane.py) use it instead of their own basename-plus-name matching, so two tests sharing a name are no longer refused batch-wide and no longer lend each other proof. The module is registered in the build deploy map. The TQ-500f-3-i h4 tests now expect per-test attribution."
breaking: false
---

## Entry
