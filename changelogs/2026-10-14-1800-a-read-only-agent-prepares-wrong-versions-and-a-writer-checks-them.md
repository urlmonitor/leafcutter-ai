---
title: "A read-only agent prepares the named wrong versions, and a deterministic writer turns them into the runner's manifest"
date: "2026-10-14"
time: "18:00"
type: manual
components:
  - testing_quality
  - build_orchestration
summary: "New test-breaker agent (tools: Read only) reads the finished code and replies, per named wrong version, with exact-match replacements or 'could not be prepared'. New wrong_version_writer.py lists what is owed with per-name in-scope files and turns the reply into the alterations manifest the wrong-version runner reads, refusing test files, out-of-scope files, paths outside the repo and .git, and computing every diff itself."
description: "TQ-500g-1-iv and TQ-500g-1-ix (fast lane, manually orchestrated). Agent choice by Decision Kernel dec-124faaaa3d814050 (new agent); read-only design by kernel run run-92227a2a275f44ff, because registry_verification_flags rules A/C forbid Write without Bash; list mode and out-of-scope refusal decided by the user at the review gate. test-breaker: templates/agents/test-breaker.md, registry entry (category research, permits_shell false, not a ticket phase), reference doc docs/agents/coding/test-breaker.md, reciprocal ticket-supervisor spawn edge. Writer: `list` prints {owed:[{name, files}]} through the runner's own declared-scope reader (extended in place in _wvr_scope); `write` derives the same scope, applies replacements exactly-once and in sequence, all-or-nothing per name, LF old text matches CRLF checkouts, deletes any stale manifest first and writes the new one atomically under <git-dir>/leafcutter/work/<key>/, never copies outcome claims, and prints its JSON shape on every error. New optional AC test_spec field in_scope_files (unique, non-empty paths). Review findings (duplicate files, non-OSError crash) fixed test-first. Smoke test: the template, run by a fresh agent on the refresh-gate sandbox, produced a reply the writer and the real runner processed end to end."
commits:
breaking: false
---

## Entry

The wrong-version runs need someone to turn a name like "drop the retry_due condition" into an
actual change of the finished code. That is now a dedicated agent that can only read: it
replies with the exact text to replace, or says why the name cannot be done. A small,
tested writer then checks every replacement against the files each name may touch, makes
the altered copies outside the working tree, computes the real diff and hands the runner
its manifest. Anything the agent cannot do, or should not touch, is recorded by name and
leaves the work unfinished instead of disappearing.
