---
title: "fix(guardrail-engine): gate the remaining three GE-123 documentation ACs and reroute the two that target a skill file"
date: "2026-08-25"
time: 1908
type: manual
components: 
  - guardrail_engine
  - security_scanner
  - commit_guardian
summary: "Completes the correction started in #554. Five documentation acceptance criteria in this tree required no reviewer at all, and four of them named an agent that cannot write the file they target."
description: "PR #554 corrected two of the five documentation records in the GE-123 tree. The other three were missed, and were found while sizing the tree for epic generation — goal mode would have produced tickets dispatching documentation-expert at a skill file. GE-123a-4 and GE-123b-5 get the full correction applied to their two siblings: change_target docs to prompt, risk_surface safety to contract_boundary, assigned_agent documentation-expert to llm-expert. Four of the five records in this tree name templates/skills/security-scanner/SKILL.md as the file they modify, and documentation-expert cannot author it: the agent delegates all authoring to genre specialists and every genre in the doc-types registry resolves to a path under the docs tree, so a skill file is unreachable for it and the only available route would emit a second copy of the passage into docs/reference. Store precedent is eight to zero in favour of llm-expert for acceptance criteria naming a skill file. GE-123c-4 is deliberately treated differently and only its risk surface changes: it modifies docs/how-to/managing-pre-commit-hooks.md, a real how-to in the docs tree, which is exactly what documentation-expert exists to route, so its agent and change target are correct and are left alone. That distinction is written into the record so a later consistency sweep does not reroute it to match its siblings — the four moved because of where their output lands, not because they are documentation. The gating defect applies to all three: the guardrail configuration maps the docs change target under a safety risk surface to an empty mandatory-agent list, so every one of these records required no reviewer on documentation describing a security control whose only defence is review. The same block leaves the auth, privacy and cost surfaces empty for docs as well; only internal and contract_boundary carry agents. No requirement text changes anywhere in this commit and all three records remain work_status todo."
breaking: false
---

## Entry
