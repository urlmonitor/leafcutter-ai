---
title: "fix(guardrail-engine): gate and correctly route the two GE-123 documentation ACs"
date: "2026-08-25"
time: 1612
type: manual
components: 
  - guardrail_engine
  - security_scanner
  - commit_guardian
summary: "Two acceptance criteria describing a security control required no reviewer at all, and named an agent that could not have written them. Both fixed; neither requirement changed."
description: "Changes three routing fields on GE-123c-5 and GE-123d-4-ii: change_target docs to prompt, risk_surface safety to contract_boundary, assigned_agent documentation-expert to llm-expert. No requirement text is touched on either record — criteria, title, level, depends_on, it_requirements, test_spec, work_status, readiness and priority are all unchanged, and both remain work_status todo awaiting approval. The gating half is the more surprising one: config/guardrail_gates.yaml maps the docs change target under a safety risk surface to an EMPTY mandatory-agent list, while the same change target under contract_boundary requires documentation-expert and pr-reviewer. Both records described a security control whose only defence is review, and both were therefore ungated — choosing the more alarming-sounding risk surface is precisely what removed the reviewers. The same block leaves the auth, privacy and cost surfaces empty for docs as well; only internal and contract_boundary carry agents. The new pairing is strictly stronger, requiring llm-expert, architect-review and pr-reviewer, and the documentation gates add documentation-expert and documentation-verifier independently of change target, so the genre owner is retained as a reviewer rather than displaced. The agent half deliberately reverses an earlier decision that was made on purpose and recorded as such: an IT PO enrichment on 2026-08-18 confirmed documentation-expert over llm-expert on the grounds that the content is reference documentation about a scanner's behaviour rather than agent-behaviour prompt text. That reasoning is about genre and is sound. It is reversed on capability, which it did not weigh — documentation-expert never authors files itself and every documentation genre it routes to targets the docs tree, so handed a skill file it can only emit a second copy of the passage under docs/reference/, which both records' own requirements forbid in as many words. Store precedent agrees eight to zero. The two records target the same passage in the same file as four GE-125 records corrected the same way, and one of those had cited GE-123d-4-ii as its precedent, so correcting only one tree would have left the store disagreeing with itself with the older record as the apparent authority. Each record's amended_by states the reversal and its grounds; amended_by is not mechanically required for these fields, so the entries are there for the reader rather than the hook."
breaking: false
---

## Entry
