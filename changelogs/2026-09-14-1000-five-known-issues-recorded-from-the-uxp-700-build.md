---
title: "Six known issues recorded from the UXP-700 build"
date: "2026-09-14"
time: "10:00"
type: manual
components: 
  - commit_guardian
  - security_scanner
  - build_orchestration
  - build_pipeline
summary: "Six defects hit while building EPIC-TruthfulProjectRecord are now in the known-issues registers, each with a reproduction, where the defect lives, and a fix direction."
description: "Six defects hit on 2026-09-14 while building EPIC-TruthfulProjectRecord are recorded, each reproduced before it was written up. (1) KI-CG-20260914-done-proof-precommit-ignores-test-required: the pre-commit done-proof gate refuses a docs-only AC marked test_required: false, while the CI gates it approximates exempt it. (2) KI-CG-20260914-exception-hook-blocks-silently: the PostToolUse exception-handling hook calls a bare ruff executable, and when ruff is only importable it exits 2 with its explanation on stdout, so every Python write shows an empty blocking error. (3) KI-SEC-20260914-entropy-flags-test-class-names: ENTROPY_HIGH flags CamelCase test class names that carry an AC id, and its allowlist remedy was refused by the permission classifier as weakening security. (4) KI-BO-20260914-commit-agent-rewrites-co-author-trailer: the commit agent replaced a caller-supplied Co-Authored-By trailer with its own model name. (5) KI-BP-20260914-build-crashes-on-a-cp1252-stdout: build.py dies with UnicodeEncodeError when its output is piped on Windows. (6) KI-CG-20260914-contract-guard-crashes-on-diff-bytes: the contract-shrinking guard decodes the staged diff as cp1252, crashes on the first undecodable byte, and blocks the commit instead of failing open. KI-BP-20260910-1240 also records two more text-mode writers producing CRLF."
commits: 
breaking: false
---

## Entry
