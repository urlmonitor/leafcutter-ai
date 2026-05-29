---
title: "EPIC-CompletionManifestSignoff — Structured completion manifests added to all phase agents"
date: "2026-05-30"
time: "00:00"
type: epic_completion
components:
  - build_pipeline
  - signoff_workflow
summary: "Every phase agent now declares a default_artifact_checklist in its frontmatter. The signoff skill mandates a completion_manifest: YAML block in each sign-off comment, and ticket-supervisor validates manifest parity before accepting an ok status."
description: "15 commits across the EPIC-CompletionManifestSignoff branch (PR #24). Key changes: §2b added to signoff/SKILL.md specifying completion_manifest format, validation rules, and malformed-manifest retry behaviour; default_artifact_checklist frontmatter field added to 9 agent templates (test-runner, test-writer, adr-author, change-scope-reviewer, how-to-author, documentation-expert, and 3 others via bulk commit); §2.3 manifest validation block added to ticket-supervisor template requiring supervisors to parse the manifest, cross-reference the checklist, and reject ok+false parity violations; §2.3 Completion Manifest Validation step inserted into building-epics/SKILL.md. Ticket count: 23 sub-tickets (01 + 19 per-agent checklists + 03/04/05). The hybrid checklist model allows agents to define defaults in frontmatter with per-ticket overrides in ticket frontmatter."
epic: "EPIC-CompletionManifestSignoff"
adrs: []
commits:
  - 6902fc3
  - 66f373d
  - 2945ed9
  - 9c54f3a
  - 31253a7
  - 991ca46
  - 04e00a3
  - c9e8501
  - d6dc383
  - 2c14a16
  - c56407c
  - af02e16
  - 4027c9c
  - c914d2b
  - b7ecfca
breaking: false
migration_steps: []
---

## Entry

EPIC-CompletionManifestSignoff introduces structured self-reflection at the point of agent sign-off. Previously, phase agents declared `status: ok` with only a free-text comment. Now:

1. **Signoff skill §2b** specifies that every phase agent must append a `completion_manifest:` YAML block to its sign-off comment, listing each expected artifact as `true` (delivered) or `false` with `reason` and `remediation` fields.

2. **19 agent templates** received a `default_artifact_checklist:` frontmatter field enumerating the artifacts their phase is expected to produce. Tickets may override this list in their own frontmatter.

3. **ticket-supervisor §2.3** now parses the manifest, cross-references it against the checklist, and rejects any sign-off where a required artifact is marked `false` while status is `ok`. This closes the gap where agents could declare success without actually producing deliverables.

4. **building-epics/SKILL.md §2.3** documents the validation step so epic operators know manifests are enforced at the supervisor layer.

This is a non-breaking change. Agents that do not yet include a `completion_manifest:` block will continue to function; the validation logic only fires when a manifest is present. Adoption is progressive.
