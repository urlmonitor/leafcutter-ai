---
title: Fix phantom git modifications on WSL2/NTFS complete
date: "2026-05-19"
time: "18:30"
type: ticket_completion
components: 
  - documentation_system
  - infrastructure
summary: "Adds .gitattributes, BOOTSTRAP.md WSL2 section, and onboard wizard NTFS detection to eliminate CRLF-induced phantom modifications on WSL2."
description: "Added .gitattributes enforcing LF line endings, WSL2 prerequisites in BOOTSTRAP.md, and auto-detection step in the onboard wizard to prevent phantom git modifications on NTFS mounts."
commits: 
  - da39102
  - b8b3b06
ticket: "TICKET-20260519-wsl2_ntfs_line_ending_fix"
---

## Entry
