---
title: "Give TQ-600a-2 a real files_touched"
date: "2026-09-30"
time: "12:40"
type: manual
components: 
  - testing_quality
  - ac_store
summary: "TQ-600a-2 generated tickets with an empty files_touched; added the edit-surface doc_link so the coder has scope, and recorded that declared_files is not read by the generator."
description: "TQ-600a-2 verified READY with warnings on an empty files_touched, meaning a generated ticket would have given the coder no file scope at all. That is this repo's documented phantom-done vector, and a-2 is the worst record in the tree to ship scope-less: its own Implementation Notes name the obvious fallback, keying routing on the test_bp_900g_8 glob, as the silent mis-routing defect the AC exists to prevent. Both existing doc_links were at relationship describes, which the derivation correctly does not treat as edit surface. Added scripts/suite_performance/pytest_shared_reference_layout.py at modifies, since TQ-600a-5 built the routing selector, the private-copy path, the routing log and the terminal summary there and every clause of a-2 extends one of them. Now READY with zero warnings and one path. A second finding surfaced while fixing this: declared_files, shipped by ACD-1600c-4 as the only answer to which files a piece of work changes, is not read by the ticket generator at all. scripts/ac_store/_gtfa_files_touched.py contains zero references to it and derives files_touched from doc_links alone, so the canonical field is not consumed by the consumer that matters most. The declared_files block is kept because it is correct per ACD-1600c-4, but the doc_link is what gives the coder scope, and that trap is recorded in the doc_link's own relevance text. This is the third instance of one shape in a single day: a mechanism declared canonical and a consumer that never learned about it, alongside the cycle checker not knowing expects_from and the entry-kind vocabulary having no known-issues member. Also confirms that merging TQ-600a-5 unblocked a-2, since the dependency-dropping warning that accompanied every prior verify run is gone."
---

## Entry
