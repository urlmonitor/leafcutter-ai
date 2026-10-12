---
title: "The package knowledge-hub command is now /leafcutter-help"
date: "2026-09-30"
time: "21:11"
type: manual
components: 
  - onboarding
  - build_pipeline
summary: "Renames the shipped /leafcutter knowledge-hub command to /leafcutter-help so the /leafcutter name is free for the Decision Kernel's runtime skill, and upgrades now remove the old installed copy by themselves."
description: "templates/workflows/leafcutter.md becomes templates/workflows/leafcutter-help.md with unchanged content apart from its own heading and 'Responding to' section, and both copies of leafcutter_inventory.py now name /leafcutter-help in their docstring. No registry, config, doc or test named the command, so nothing else changes. Upgrades clean up after themselves: the build now retires an installed command or workflow file whose template the package no longer ships, on a plain build and under --clean, when the previous install recorded that file and it is still byte-identical to what the package wrote. The old leafcutter.md therefore disappears from .leafcutter/commands/, .claude/commands/ and .gemini/workflows/ on the first build after upgrading, and check-output-drift stays green. Each removal is named in the build output. If you edited your installed leafcutter.md, the build keeps it and names it as kept; delete it yourself once you no longer need it, since check-output-drift reports it as a GAP until you do."
---

## Entry

Ticket: TICKET-20260930-RenameLeafcutterHubCommand
Ticket: TICKET-20260930-RetireRenamedCommandOutputs
