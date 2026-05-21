# ADR-001: Self-Hosting Boundary — Config-Driven Path Resolution

## Status

Accepted (2026-05-19)

## Context

The leafcutter repository is simultaneously:
1. The package source (templates, scripts, config)
2. A target project that `build.py` writes into
3. The development environment for working on leafcutter itself

This creates confusion: `docs/vision.md` at root is a template placeholder, `tickets/` holds scaffold output, and `.claude/agents/` contains compiled agents that are also the dev tools. A newcomer cannot tell what is source vs output.

The brainstorm at `leafcutter-ai/docs/brainstorm-self-hosting.md` evaluated four options:
- **Option A:** Single repo, leafcutter eats itself (status quo — confusing)
- **Option B:** Two separate repos (overhead, submodule pain)
- **Option C:** Single repo, separate config targets (chosen)
- **Option D:** Templates as source of truth, no compilation (breaks `{{config.*}}` injection)

## Decision

We chose a variant of Option C: **all project content lives under `leafcutter-ai/`**, and `build.py` reads all scaffold target paths from `skills_config.json` rather than hardcoding them.

Specifically:
- **Tickets** live at `leafcutter-ai/tickets/` (config: `tickets_inbox_path`)
- **Docs** live at `leafcutter-ai/docs/` (config: `docs_root`)
- **Changelog** lives at `leafcutter-ai/docs/changelog/` (config: `changelog_folder`)
- **Build outputs** (`.claude/agents/`, `.claude/skills/`, `scripts/commit_guardian/`, etc.) go to the project root since that's where Claude Code expects them
- **`build.py` requires onboarding** — it refuses to run without `.claude/skills_config.json`, directing the user to run `/onboard` first

We did NOT implement a `--self` flag (as originally proposed). Instead, the config-driven approach is more general: any project can point paths wherever it wants, and leafcutter's own config simply points them into `leafcutter-ai/`.

## Consequences

**Positive:**
- Clear boundary: everything in `leafcutter-ai/` is source, everything at root is build output
- `build.py` works the same way for leafcutter itself and for consumer projects — no special modes
- Onboarding is required, which prevents unconfigured builds from polluting the tree

**Negative:**
- Root-level `scripts/commit_guardian/` and `scripts/doc_compliance/` are still build outputs at root (can't move them without breaking hook paths in `.pre-commit-config.yaml`)
- The glossary CLAUDE.md section uses marker-based idempotency, so changing `docs_root` doesn't auto-update existing markers — requires a one-time manual fix

## Alternatives

The `--self` flag approach was rejected because it adds a special code path that only leafcutter uses. Config-driven paths are more general and testable.
