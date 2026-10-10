---
title: "Setting a ticket's status keeps its line endings"
date: "2026-10-09"
time: "06:25"
type: manual
components:
  - build_orchestration
summary: "On Windows, setting a ticket's status rewrote the whole record with CRLF line endings; on Linux, a CRLF record came back all-LF. set_ticket_status.py now changes only the status line and leaves every other byte as it was."
description: "scripts/set_ticket_status.py read the ticket in text mode, which turned CRLF into LF, and wrote it in text mode, which turned every LF into the platform's line ending. One completion write by /build-feature on Windows turned 280 lines of an LF ticket into CRLF, which showed up as a whole-file diff and a git line-ending warning. The script now reads and writes with no newline translation. The frontmatter split keeps the opening '---' line whole, and the status line, replaced or inserted, keeps its own ending (or the title line's ending when it is inserted). Four tests cover LF, CRLF, mixed-ending and status-absent records (BO-400b-4)."
commits: [23856f360]
breaking: false
---

## Entry
