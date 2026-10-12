---
title: "Commit-guardian component doc: ADR-068 back-link added, stale registration claim corrected"
date: "2026-10-12"
time: "15:30"
type: manual
components: 
  - commit_guardian
summary: "The commit-guardian component doc now links to ADR-068, and no longer wrongly says the identifier-uniqueness hook is unregistered."
description: "ADR-068 (status Proposed; nothing is built against it) is now back-linked from related_docs in docs/architecture/components/commit-guardian.md, as write-adr.md section 8 point 3 requires. The doc also claimed check_identifier_uniqueness.py was not yet registered in any hook manifest; it is, as check-identifier-uniqueness, twice in templates/scripts/commit_guardian/commit_guardian.json with always_run true, so a reader would have wrongly concluded a live hook was dormant. That claim and a dated first-run remark are removed. The doc was over its 300-line limit (368 lines), so the growth ratchet refused an addition; it was trimmed to 331 lines by dropping three _operation_record.py rationale bullets already covered by that module docstrings. Anyone adding to this doc next must also remove lines."
commits: 
  - eeaf85f01
breaking: false
---

## Entry
