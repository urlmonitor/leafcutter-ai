---
title: "/build-feature now hands agents the right file on Windows and on POSIX alike"
date: "2026-09-14"
time: "22:00"
type: manual
components:
  - build_orchestration
summary: "Fixes the path bug that made /build-feature build nothing on Windows: build-feature.js, plan-feature.js and build-epic.js now classify, join and compare paths from the string's own form, proven through the Node workflow harness and a Linux-safe unit test."
description: "On 2026-09-14, /build-feature spent about 975k subagent tokens on Windows and built nothing. Its path helper only recognised a leading '/' as absolute, so a Windows path like C:\\Users\\...\\07_TICKET.md was joined onto the worktree instead of being read as-is, and every ticket in the batch came back \"TICKET NOT FOUND\". BO-3900 (with BO-3900a to BO-3900d) is now implemented. build-feature.js, plan-feature.js and build-epic.js each carry their own copy of the same string-only classification: a drive letter, a UNC root, or a leading slash is absolute and is never joined onto anything; a path with no root is relative and is joined onto the worktree exactly once, with one separator spelling throughout; a path whose form nobody recognises (a bare drive letter, a rooted path with no drive, a blank value, or a value already carrying a second drive root) blocks only its own ticket, quoting the value verbatim, while its well-formed siblings still run. A predecessor named in depends_on resolves to the very ticket path the run dispatches it under, whichever separator it was spelled with. Every one of these is proven by running the real script's own top-level body through the Node workflow harness — not by testing a helper in isolation — and a Linux-safe unit test feeds the same Windows-shaped paths on the CI runner that never sees a real backslash. A new unit-test-only scanner catches a POSIX-only leading-'/' check landing in any workflow script in the future, derived from the script directory's own listing rather than a hard-coded file list."
commits:
breaking: false
---

## Entry

/build-feature, /plan-feature and the epic driver they share now resolve, join and compare ticket, epic, worktree and store paths from the path string's own form — never from the host operating system. A Windows absolute path reaches every phase agent as one path with one drive root; a relative path is joined onto the worktree exactly once; an epic member named by a path in one separator and depended on in another still resolves to the same dispatched ticket. A path form nobody recognises now blocks only its own ticket with a clear, quoted reason, instead of being silently joined onto the worktree the way the 2026-09-14 incident's corrupted value was. This closes BO-3900 and its four child records (BO-3900a–d).
