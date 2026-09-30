---
title: "The package knowledge-hub command is now /leafcutter-help"
date: "2026-09-30"
time: "21:11"
type: manual
components: 
  - onboarding
  - build_pipeline
summary: "Renames the shipped /leafcutter knowledge-hub command to /leafcutter-help so the /leafcutter name is free for the Decision Kernel's runtime skill."
description: "templates/workflows/leafcutter.md becomes templates/workflows/leafcutter-help.md with unchanged content apart from its own heading and 'Responding to' section, and both copies of leafcutter_inventory.py now name /leafcutter-help in their docstring. No registry, config, doc or test named the command, so nothing else changes. Upgrade action for adopters: the build does not remove a renamed workflow template's installed copy. A scratch consumer build before and after the rename showed that both a plain build and a --clean build leave the old leafcutter.md in .leafcutter/commands/, .claude/commands/ and .gemini/workflows/ next to leafcutter-help.md. Delete those three leafcutter.md files by hand after upgrading, or the stale hub will keep answering to /leafcutter. Until they are deleted, the check-output-drift hook reports each installed copy as a GAP and fails every commit, and rerunning build.py does not clear it because the template no longer exists."
---

## Entry

Ticket: TICKET-20260930-RenameLeafcutterHubCommand
