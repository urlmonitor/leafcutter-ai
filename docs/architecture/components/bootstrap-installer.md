---
title: "Bootstrap Installer — Self-Hosting Installation System"
description: "Self-hosting installation system that deploys leafcutter-ai agents, skills, hooks, and config scaffolds into consumer projects with zero manual setup."
flight_level: L3-Component
status: active
type: reference
created: 2026-06-08
last_updated: 2026-06-08
components:
  - bootstrap_installer
---

# Bootstrap Installer

## Overview

The Bootstrap Installer (`scripts/bootstrap_install.py`) handles the initial installation of the leafcutter-ai package into a consumer project. It runs the build pipeline, installs pre-commit hooks, and scaffolds config files to make the harness operational immediately.

## Responsibilities

- Deploy compiled agents, skills, and hooks to the consumer's `.claude/` directory
- Install the pre-commit hook chain via `pre-commit install`
- Scaffold config files from templates (skills_config.json, paths.json, etc.)
- Verify all required files are present after installation

## Entry Points

- `scripts/bootstrap_install.py` — main installer
- `build-self.sh` — convenience script for self-hosting development
- `BOOTSTRAP.md` — installation instructions for consumer projects

## Design

The installer is idempotent: running it multiple times on the same project does not corrupt existing configuration. Existing user-modified files are preserved.
