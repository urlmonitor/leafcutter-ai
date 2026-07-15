---
title: "leafcutter-ai Vision"
description: "Product vision — what leafcutter-ai is, who it serves, and the outcomes it delivers"
type: cross-cutting
status: accepted
created: 2026-05-19
last_updated: 2026-05-21
components:
  - documentation_system
tags:
  - vision
  - roadmap
build_behavior: write_if_absent
---

# leafcutter-ai Vision

## Mission Statement

leafcutter-ai is a domain-agnostic agent/skill/workflow package that installs a full AI-assisted development workflow into any project. Edit one JSON config file, run `build.py`, and the complete system is generated: agents, skills, hooks, ticket lifecycle, documentation scaffolds, and quality gates. The goal is to make AI IDEs and agents (Claude Code, Antigravity, etc.) productive and disciplined in any codebase without requiring project-specific prompt engineering.

## Current Phase

**Current phase:** Phase 1 — Stable portable MVP

**Highest-priority outcome:** A reliable package that installs into any project, self-onboards the user via interactive config, and produces correct agents/skills/hooks without manual fixup.

## What We're NOT Doing (Yet)

The following are explicitly out of scope until a future phase decision:

- Multi-LLM support (non-Anthropic models)
- Package registry / versioned releases (npm, pip, etc.)
- GUI or web-based configuration interface
- Runtime telemetry dashboard or analytics
- Plugin marketplace for community-contributed agents/skills

## Strategic Assets / Differentiators

| Asset | Description | Why it matters |
|-------|-------------|----------------|
| Config-driven templating | `{{config.*}}` injection compiles portable templates into project-specific agents | One template set serves all adopters; no fork-and-edit pattern |
| Build-system architecture | `build.py` with phase-based dispatch, compare-before-write, manifest tracking | Deterministic, auditable builds; drift detection via pre-commit hooks |
| AC-driven delivery | Each acceptance criterion carries its own agent assignments, sign-offs, and work status — the requirement IS the work order | Eliminates drift between specs and execution; supervisors walk the AC hierarchy directly without an intermediate ticket layer |
| Self-hosting dogfood | leafcutter develops itself using its own agents and skills (ADR-001) | Every UX issue is discovered during development, not after release |
| Quality gate suite | Pre-commit hooks for build drift, secrets, doc coverage, structural changes | Adopters get guardrails without writing their own hook infrastructure |

## Roadmap (Phases)

### Phase 1 — Stable Portable MVP

**Done when:** A fresh clone installs into a new project via `build.py --target-dir .`, the onboard wizard populates `skills_config.json`, and all generated agents/skills/hooks function correctly without manual intervention.

Establishes the core value proposition: one command to get a working AI dev workflow.

### Phase 2 — Ecosystem Hardening

**Done when:** The package handles version upgrades gracefully (template migrations, config schema evolution), supports multiple concurrent consumer projects from a single package clone, and has a documented contribution workflow for adding new agents/skills.

Unlocks adoption beyond the original author by making the package maintainable by others.

### Phase 3 — Distribution and Community

**Done when:** The package is installable via a standard package manager, has versioned releases with changelogs, and supports community-contributed agents/skills via a documented extension mechanism.

Transitions from a personal tool to a shared open-source package.

## Success Criteria

| Criterion | Target | How to measure |
|-----------|--------|----------------|
| Clean install success rate | 100% on supported platforms (Linux, macOS, WSL2) | Run `build.py --target-dir .` on a blank project with only `skills_config.json` present |
| Agent/skill compilation accuracy | Zero template injection errors | `build.py --validate-only` returns 0; no `{{config.*}}` placeholders survive in compiled output |
| Build idempotency | Consecutive builds produce zero git diff | Run `build.py` twice; `git status` shows no changes |
| Self-hosting parity | leafcutter's own workflow uses the same agents it ships | All leafcutter development tickets are driven by compiled agents from its own templates |

## Key Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-19 | Self-hosting via config-driven paths, not `--self` flag (ADR-001) | More general; avoids special code paths. `skills_config.json` points paths into `leafcutter-ai/` for package development. |
| 2026-05-13 | YAML frontmatter stripping in template compilation | Keeps metadata in templates for tooling but out of compiled agent prompts |
| 2026-05-13 | Default overwrite semantics in build.py | Old skip-existing caused silently stale outputs; overwrite + compare-before-write is safer |
| 2026-05-14 | Compare-before-write guard | Eliminates mtime churn; `git status` stays clean for unchanged files |

## Epics Mapping

| Epic | Phase | Status | Notes |
|------|-------|--------|-------|
| EPIC-OnboardCompleteness | Phase 1 | active | Interactive onboard wizard and config validation |
| EPIC-LeafcutterVersioning | Phase 2 | planned | Version tracking, upgrade paths, migration support |
| EPIC-LeafcutterUpstreamChannels | Phase 3 | planned | Distribution, packaging, community extension points |

---

> See [CLAUDE.md](../CLAUDE.md) for the entry point that links here.
