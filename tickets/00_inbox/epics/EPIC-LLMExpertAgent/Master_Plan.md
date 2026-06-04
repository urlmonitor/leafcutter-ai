---
title: "EPIC: Introduce llm-expert agent — LLM craft peer to the coding agents"
type: epic
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on: []
priority: high
---

# EPIC: Introduce llm-expert agent

In order to have a specialist that owns the craft of writing, auditing, and maintaining the text inside agent templates, skill files, and slash-command prompts — the way `python-coder` owns Python files — we need an `llm-expert` agent that BA and IT PO can dispatch when a ticket requires prompt engineering, agent authoring, or skill authoring work.

The leafcutter coding-agent family (`python-coder`, `sql-coder`, `frontend-coder`) follows a consistent pattern: each agent has a dedicated `PROJECT_CONTEXT.md`, loads domain-specific skills, and is dispatched by `ticket-supervisor` as a first-class ticket phase. The same pattern does not yet exist for the craft of writing LLM instructions themselves. This epic delivers the agent template, internal knowledge base, registry wiring, and auditing infrastructure to close that gap.

## Sub-Tickets

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_agent_template.md](./01_agent_template.md) | Create `templates/agents/llm-expert.md` agent template with all body sections (Pre-Flight Reads, Prompt-Quality Checklist, Stop-and-Ask Rule, Skills, Implementation Sequence, Response Payload, Sign-off, Constraints). | `[ ]` |
| 02 | [02_project_context.md](./02_project_context.md) | Create `docs/agents/llm-expert/PROJECT_CONTEXT.md` with six knowledge sections (shell convention, agent frontmatter schema, skill frontmatter schema, signoff protocol, nesting/spawn-allowlist rules, prompt-quality checklist with examples). | `[ ]` |
| 03 | [03_registry_and_docs.md](./03_registry_and_docs.md) | Wire the agent into `config/agent_registry.json`, add `llm-expert` to ticket-supervisor's spawn_allowlist, and add a row to `docs/agents/README.md`. | `[ ]` |
| 04 | [04_prompt_audit_skill.md](./04_prompt_audit_skill.md) | Create a `prompt-audit` skill that systematically audits agent templates and skill files against the Prompt-Quality Checklist, encapsulating heuristics for compound bash, missing signoff, and tool allowlist mismatches. | `[ ]` |
