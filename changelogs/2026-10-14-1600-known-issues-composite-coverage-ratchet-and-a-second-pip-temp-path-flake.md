---
title: "Known issues: the coverage ratchet counts tested composite ACs as untested, and the pip temp-path flake recurs"
date: "2026-10-14"
time: "16:00"
type: manual
components: 
  - ac_store
  - testing_quality
summary: "Files KI-ACS-20261014: the KM-ADM-005 untagged-done ratchet requires a `# covers:` tag on a composite AC itself, although the done-proof gate proves a composite through its children. Records a second occurrence of KI-TQ-20261010, the setup_ticket_worktree test flake caused by a temp path containing 'pip'."
description: "New docs/known-issues/ac-store/open-low-ki-acs-20261014-untagged-done-ratchet-counts-composites-as-untested.md, indexed in docs/known-issues/ac-store.md. test_untagged_done_ac_backlog_does_not_grow counts every done AC whose own id has no `# covers:` tag. A composite is proved by its leaves under BO-2500a-6, so marking a fully tested parent done fails the required pytest check: on PR #1199 the count went from 244 to 245. The rule decided on 2026-10-14 is that a top-level AC should not need its own tests when its children have them. The KI lists the redundant parent tags added as workarounds, for removal once fixed. docs/known-issues/testing-quality/open-low-ki-tq-20261010-bootstrap-tests-fail-when-the-temp-path-contains-pip.md records its second occurrence (PR #1186, temp dir /tmp/tmpnpipvc1f), which was first misread as a mock leaking between tests."
breaking: false
---

## Entry
