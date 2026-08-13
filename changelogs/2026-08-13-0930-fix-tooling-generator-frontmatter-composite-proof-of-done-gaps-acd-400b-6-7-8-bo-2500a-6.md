---
title: "fix(tooling): generator frontmatter + composite proof-of-done gaps (ACD-400b-6/-7/-8, BO-2500a-6)"
date: "2026-08-13"
time: "09:30"
type: manual
components: 
  - ac_store
  - ac_driven_dev
  - build_orchestration
summary: "Fixed four bugs in the AC/ticket generation and done-proof tooling that could send coders to the wrong file, hard-block generated tickets, mangle dotfile paths, or wrongly block merges on composite acceptance criteria."
description: "1 commit (4edd4eee5). generate_ticket_from_ac.py: _extract_local_paths() now accepts string-form doc_links entries (was silently dropping files_touched), depends_on no longer copies raw AC ids into the ticket frontmatter guard, and the path regex no longer strips the leading dot from dotfile paths. done_proof.py: a done COMPOSITE AC whose covered_by resolves to real child ACs now derives its proof-of-done from those children instead of requiring its own direct covers-tagged test; done leaves still require their own passing test. fast_lane.py: verify_green_and_coverage now reads verdict[eligible] structurally instead of substring-matching the old reason text."
commits: 
  - 4edd4eee5
breaking: false
---

## Entry
