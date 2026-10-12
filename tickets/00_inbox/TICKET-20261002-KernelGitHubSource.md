---
title: "Kernel: a native read-only GitHub source for the facts decisions rest on"
status: todo
components:
  - decision_kernel
created: 2026-10-02
depends_on: []
priority: medium
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - retrieval
  - github
last_updated: 2026-10-02
agents:
  python-coder: needed
  commit: needed
---

# Kernel: a native read-only GitHub source for the facts decisions rest on

## Actor / Goal
In order for the kernel to answer questions such as "is CI green", "how long do the checks take" or "should these open PRs be combined" from verifiable evidence, we need a native read-only GitHub source.

## Context
- **Decision:** `dec-4673055ef54113d5` (run `run-9921881bfaa342ef`, approved by the user 2026-10-02), the hybrid option.
  - Facts the kernel decides on come from a native read-only GitHub source, as inspectable evidence.
  - Anything that is not a read (merging, commenting, re-running CI) never goes through the kernel. It stays host work, or is recorded as a capability gap.
- **Why it's needed:** on 2026-10-02 the kernel could not answer whether to combine PRs, because it cannot read GitHub.
- **Native-source contract** (Rev 3 section 10.3; `retrieve.repository`): each result carries identity, location (URL), revision (head SHA or `updated_at`), content hash and truncation. An unreachable source is reported as unavailable, never as an empty result.

## Scope (no ACs, by user decision)
- **Source:** a new read-only source, for example `repo.github`, covering:
  - pull requests (state, head SHA, files touched, mergeability);
  - check runs (name, status, conclusion, start and end times);
  - issues.
- **Authentication:** reuse the existing authenticated `gh` login (keyring), with no token in kernel config, run artifacts or traces. Use `env -u GH_TOKEN` semantics where relevant (see the memory note on gh).
- **Admission:** into `config/capability_registry.json` by recorded decision (ADR-055), with `side_effect_class: read_only`.
- **Unavailability:** rate limits and a missing or expired login are reported as "source unavailable", with the reason.
- **Tests:** fixtures for the API responses, the no-login path, and no write calls anywhere.

## Out of Scope
- Any GitHub write (merge, comment, push, re-run).

## Comments
