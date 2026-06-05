---
description: "Leafcutter package knowledge hub — what it is, how to build, available agents/skills/commands, onboarding, and architecture docs."
---

# /leafcutter — Package Knowledge Hub

You are an expert on the **leafcutter-ai** package. Use this context to answer
any question about leafcutter: what it does, how to install it, how to build,
what agents/skills/commands exist, and how to extend it.

## What is leafcutter?

A domain-agnostic AI agent/skill/workflow package that installs into any project.
It provides the full development-lifecycle automation: ticket creation, TDD,
code review, commit, PR, and finalization — all orchestrated by a supervisor
pipeline.

**README:** `leafcutter-ai/README.md` — read this first for any question.
**Docs folder:** `leafcutter-ai/docs/`

## Key Architecture Docs

| Document | Path |
|----------|------|
| README (start here) | `leafcutter-ai/README.md` |
| Build Pipeline | `leafcutter-ai/docs/build-pipeline.md` |
| Agent Knowledge Plane | `leafcutter-ai/docs/architecture/agent_knowledge_plane.md` |
| Agent Delivery Workflows | `leafcutter-ai/docs/architecture/agent_delivery_workflows.md` |
| Ticket Lifecycle | `leafcutter-ai/docs/ticket-lifecycle.md` |
| Pre-Commit Hooks | `leafcutter-ai/docs/pre-commit-hooks.md` |
| Agent Inventory | `leafcutter-ai/docs/agents/README.md` |
| Agent Conventions | `leafcutter-ai/docs/agents/conventions.md` |
| ADRs | `leafcutter-ai/docs/architecture/adrs/` |
| Glossary | `leafcutter-ai/docs/glossary.md` |
| Roadmap | `leafcutter-ai/docs/roadmap.json` |

## How to Build

```bash
# Self-hosting (dev on leafcutter itself):
./build-self.sh
# or equivalently:
python leafcutter-ai/scripts/build.py --target-dir .  # run from the leafcutter/ parent dir

# Installing into a consumer project:
python leafcutter-ai/scripts/build.py --target-dir /path/to/project

# Validate only (no writes):
python leafcutter-ai/scripts/build.py --validate-only

# Dry run:
python leafcutter-ai/scripts/build.py --dry-run
```

## How to Onboard a New Project

Run `/onboard` inside the target project after cloning leafcutter-ai into it.
The onboard wizard auto-discovers the repo structure, generates a proposed
`skills_config.json`, and runs `build.py` on approval.

Manual steps: see `leafcutter-ai/BOOTSTRAP.md` or `leafcutter-ai/SETUP.md`.

## Dynamic Inventory

To get the current inventory of agents, skills, and commands, run:

```bash
python leafcutter-ai/scripts/leafcutter_inventory.py \
  --repo-root leafcutter-ai/ \
  --commands-dir .claude/commands/
```

Sections: `--section agents`, `--section skills`, `--section commands`, or `--section all`.

## Registries

| Registry | Path |
|----------|------|
| Agent registry | `leafcutter-ai/config/agent_registry.json` |
| Skill registry | `leafcutter-ai/config/skill_registry.json` |
| Package boundary | `leafcutter-ai/config/package_boundary.json` |
| Skills config schema | `leafcutter-ai/config/skills_config.schema.json` |

## Package Extension

All extensions flow through the `workflow-architect` agent:

| Goal | Skill dispatched |
|------|-----------------|
| Add a pre-commit hook | `create-hook` |
| Promote a project-local agent | `add-agent-to-package` |
| Promote a project-local skill | `add-skill-to-package` |
| Audit current package gap | `package-audit` |

## Responding to /leafcutter

When the user invokes this command:

1. If `$ARGUMENTS` is empty, print a concise summary of leafcutter (what it is,
   how to build, link to README) and offer to show agents, skills, commands,
   architecture, or run onboarding.

2. If `$ARGUMENTS` asks about agents/skills/commands/inventory, run the
   inventory script and present the output:
   ```bash
   python leafcutter-ai/scripts/leafcutter_inventory.py \
     --repo-root leafcutter-ai/ --commands-dir .claude/commands/ \
     --section <agents|skills|commands|all>
   ```

3. If `$ARGUMENTS` asks "how to build" or "build", show the build commands above.

4. If `$ARGUMENTS` asks about onboarding, explain `/onboard` and point to
   BOOTSTRAP.md.

5. If `$ARGUMENTS` asks about architecture or docs, read and summarize the
   relevant doc from the table above.

6. For any other question about leafcutter, read the README and relevant docs
   to answer it.
