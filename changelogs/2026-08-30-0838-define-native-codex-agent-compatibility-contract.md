---
title: "Define and approve the native Codex agent compatibility contract"
date: "2026-08-30"
time: "08:38"
type: manual
components:
  - agent_registry
  - build_pipeline
  - template_compiler
  - skills_system
summary: "Leafcutter now has an approved, versioned contract for compiling its canonical Claude agent definitions into native Codex agents."
description: "Adds the AGC-100 acceptance-criteria hierarchy and a schema-validated compatibility policy that maps source model aliases and tool capabilities to Codex-native targets. All 24 AC records are explicitly approved with a user audit entry. The contract covers all 59 non-deprecated launchable registry identities, deterministic native agent generation, skill publication, diagnostics, documentation, and live compatibility proof. This change defines the build contract; it does not yet generate the Codex artifacts."
commits:
breaking: false
---

## Entry

The Claude agent Markdown remains the canonical role source. The approved
contract specifies native Codex outputs in `AGENTS.md`, `.codex/agents/`, and
`.agents/skills/`, backed by a machine-readable conversion policy and JSON
Schema. Unknown model or capability aliases fail closed so incompatible agents
cannot be published silently.
