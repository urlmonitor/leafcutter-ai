---
title: "docs(known-issues): give the secrets scanner its own register, and file the /plan-feature startup halt"
date: "2026-08-19"
time: 0937
type: manual
components: 
  - commit_guardian
  - ac_driven_dev
summary: "Secrets-scanning defects now live in one place instead of being mixed in with unrelated commit-hook issues, so 'what can a credential slip past right now' is answerable at a glance. Also records that the AC-authoring command cannot start at all, and tells you the wrong reason when it fails."
description: "Creates docs/known-issues/security-scanner.md and moves the prose-exemption defect into it as KI-SEC-001. That defect is the only entry in any register describing an actual credential exposure: ENTROPY_HIGH is disabled for WHOLE FILES under four path prefixes, and the match is not root-anchored, so any path containing a tickets, retrospectives, acceptance-criteria or skills segment at any depth loses entropy detection - including the scanner's own source and executable Python under templates/skills. It was filed under commit-guardian because the scanner runs as a hook; the split is by surface, not by component vocabulary, and the frontmatter still declares commit_guardian because security_scanner is not in components.json. KI-CG-004 is retired with a stub, following the KI-BO-002 precedent. The six GE-123 records that cite KI-CG-004 as an out-of-scope fence were deliberately left untouched - they are dated decisions and the stub resolves them in one hop. Also files KI-ACD-009: /plan-feature halts before any authoring agent with a message asserting that worktree-agent's charter forbids shell commands, when its permits_shell is true. The permission check collapses four distinct outcomes - dispatch failed, output unparseable, file unreadable, id absent - into one permissions verdict, and two independent causes were both live in the observed run: the deployed workflow reads a relative registry path that does not exist inside a worktree, and the dispatch itself hit an API error. Failing closed is right; asserting a specific false cause is not. While it holds, the mandated entry point for all new work is closed from any worktree."
breaking: false
---

## Entry
