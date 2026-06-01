---
title: "Scaffold all ticket lifecycle folders from manifest"
status: done
components:
  - build_system
created: 2026-05-19
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
---

# 09: Scaffold all ticket lifecycle folders from manifest

## Actor / Goal

In order to have a complete ticket directory structure after build,
we need `build.py` to create every folder declared in `ticket_lifecycle.json`
— not just the ones that already exist on disk.

## Context

`ticket_lifecycle.json` defines the valid ticket folders (e.g.
`tickets/00_inbox`, `tickets/00_inbox/epics`, `tickets/01_todo`,
`tickets/99_done`, `tickets/99_rejected`). However, `build.py`
(`build_ticket_lifecycle()`) only creates folders that happen to already
exist in the template or were previously scaffolded. Missing folders like
`tickets/99_rejected` and `tickets/00_inbox/epics` are silently skipped.

This means ticket operations that try to move files to these folders fail
at runtime. The lifecycle manifest should be the single source of truth for
which folders exist.

## Acceptance Criteria

```gherkin
Given ticket_lifecycle.json declares folders including "99_rejected"
And tickets/99_rejected/ does not exist on disk
When build.py runs build_ticket_lifecycle()
Then tickets/99_rejected/ is created with a .gitkeep file

Given ticket_lifecycle.json declares a folder with has_epics_subfolder: true
And the epics/ subfolder does not exist
When build.py runs build_ticket_lifecycle()
Then the epics/ subfolder is created under that folder

Given all lifecycle folders already exist on disk
When build.py runs build_ticket_lifecycle()
Then no folders are modified or recreated (idempotent)
```

## Implementation Tasks

- [ ] Read all folder entries from `ticket_lifecycle.json` in `build_ticket_lifecycle()`
- [ ] Create each folder with `os.makedirs(exist_ok=True)` + `.gitkeep`
- [ ] Handle `has_epics_subfolder` flag to create nested `epics/` dirs
- [ ] Add `README.md` scaffolds for folders that have a `description` field
- [ ] Unit tests for missing-folder creation and idempotency

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Creates empty directories; `rm -r` removes them.
