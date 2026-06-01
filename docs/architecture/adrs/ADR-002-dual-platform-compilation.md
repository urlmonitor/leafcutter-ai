---
title: "ADR-002: Dual Platform Compilation for AI Agents"
type: "adr"
status: "active"
created: "2026-05-22"
last_updated: "2026-05-22"
components: []
---

# ADR-002: Dual Platform Compilation for AI Agents

## Status
Accepted

## Context
Originally, leafcutter-ai was heavily optimized for **Claude Code**. The system relied on generating custom `Skill()` tool declarations inside `CLAUDE.md` or similar files, leveraging Claude Code's specific capability to parse these tools and execute shell scripts or Python commands under the hood.

As our workflows have matured, we've identified the need to support other AI runtimes—specifically **Antigravity** and other environments that rely on standard MCP (Model Context Protocol) tool invocation rather than Claude Code's bespoke `Skill()` abstraction. Antigravity requires a different set of instructions and a different tool integration pattern (relying on native MCP rather than custom parsed CLI commands).

Maintaining two separate codebases or entirely different templates for each platform would violate our goal of having a single portable, configuration-driven package. 

## Decision
We will adopt a **Dual Platform Compilation** strategy using Jinja templating during the `build.py` phase. 

Instead of hardcoding Claude-only `Skill()` tools into our templates, we will:
1. Define our tool and skill capabilities in a generic data structure.
2. Use Jinja templates in the build pipeline (`build.py`) to compile the workflow output dynamically based on the target platform context.
3. For **Claude Code**, generate the legacy `Skill()` syntax.
4. For **Antigravity**, emit standard instructions and native MCP tool configurations.

## Consequences

**Positive:**
- **Broader Adopter Base:** Adopters using Antigravity can now leverage the leafcutter-ai workflow out of the box.
- **Single Source of Truth:** Core logic and prompt instructions remain unified in our template files.
- **Future Proofing:** Adding a third runner (e.g., Cursor/Windsurf full automation) in the future will just require a new compiler target in `build.py`, not a rewrite of all agents.

**Negative:**
- **Increased Complexity in Templates:** Templates will now contain more complex Jinja conditional logic (e.g., `{% if platform == 'claude' %} ... {% elif platform == 'antigravity' %} ... {% endif %}`).
- **Testing Overhead:** We must validate the compiled output for multiple platforms, increasing the test matrix in `unit_tests/` for our build step.
