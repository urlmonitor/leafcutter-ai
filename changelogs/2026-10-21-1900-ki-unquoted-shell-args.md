---
title: "Known issue filed: workflow shell commands paste paths and ids in unquoted"
date: "2026-10-21"
time: "19:00"
type: manual
components:
  - build_orchestration
summary: "KI-BO-20261021-unquoted-shell-args (high) records that fast-lane-ship.js's wrong-version and claim commands, and the red-baseline gate in build-feature.js and build-ticket.js, build shell lines with unquoted paths and ids. A path with a space halts every fast-lane drive fail-closed, and an id with shell metacharacters can inject a command."
description: "Docs only. New docs/known-issues/build-orchestration/open-high-ki-bo-20261021-unquoted-shell-args.md and its register row. Sites at origin/main: fast-lane-ship.js:1948-1950, :1971, :1976, :1989-1991 (wrong-version, #1280), :1233-1234 (claim), :1007-1009 and :1375-1376 (relayed); build-feature.js:2117-2121; build-ticket.js:1703-1707. Remediation directions recorded, not applied: the PR #1299 pattern of quoting every value and checking ids against ^[A-Za-z0-9._-]+$ first. fast-lane-ship.js is over the size ratchet, so the fix needs a skip or an equal shrink."
commits:
breaking: false
---

## Entry

Some build steps put folder paths and requirement ids straight into shell commands without
quoting them. A project in a folder whose name contains a space cannot finish a fast-lane build,
and an id containing shell characters could run a command nobody wrote. It is now recorded as a
known issue with every affected line and the fix already used in an open PR.
