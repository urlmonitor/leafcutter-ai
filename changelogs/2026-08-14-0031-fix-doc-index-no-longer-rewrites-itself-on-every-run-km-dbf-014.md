---
title: "Fix: doc index no longer rewrites itself on every run (KM-DBF-014)"
date: "2026-08-14"
time: "00:31"
type: manual
components: 
  - knowledge_management
summary: "Regenerating the documentation index no longer creates a spurious file change when nothing actually changed, removing a recurring source of pre-commit hook failures."
description: "1 commit (12b087de0, Bug Fixes): generate_doc_index.py dropped the datetime.now(timezone.utc) 'Generated:' header stamp that rewrote docs/INDEX.md on every run even absent doc changes. That guaranteed unstaged diff was the reliable trigger for pre-commit stash-restore failures ('patch does not apply' / stash conflicts). created/last_updated frontmatter already carries the timing info and is preserved; a genuine doc change still updates the index, guarded by a new idempotency test."
pr: 432
commits: 
  - 12b087de0
---

## Entry
