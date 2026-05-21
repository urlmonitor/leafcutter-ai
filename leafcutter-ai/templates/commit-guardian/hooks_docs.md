# Commit Guardian — Hooks Reference

This document describes every hook registered in `commit_guardian.json`. Each row
gives the hook ID, trigger scope, failure mode (blocking / advisory / fail-open),
and the escape hatch for bypassing or suppressing the hook when legitimate.

| Hook ID | Trigger | Failure mode | Escape hatch |
|---|---|---|---|
| `check-build-drift` | `leafcutter/templates/` files staged | Blocking | None — built output must stay in sync with templates. Run `build.py` to regenerate. |
| `check-secrets` | Any staged file | Blocking | Add path to `.security-allowlist` (reviewed by a human). |
| `check-doc-length` | `docs/**/*.md` staged | Blocking | Break the doc into sub-documents; no length bypass token. |
| `check-structural-change` | New model / service / live-trader module staged | Blocking | Add `[NO-ARCH-UPDATE]` to the commit message (for vendored code, pure renames, or refactors that don't change the component surface). |
| `check-components-integrity` | `docs/components.json` staged | Blocking | Fix the JSON schema error; no bypass token. |
| `check-adr-coverage` | New migration / model / service staged | **Advisory (warn)** | No bypass needed — this is informational only. |
| `check-adr-cross-reference` | `docs/**/*.md` staged | **Advisory (warn)** | No bypass needed. |
| `check-infra-docs` | `docker-compose.yml`, `Dockerfile.*`, `.env.*` staged | Blocking | Add an inline comment justifying the high-impact setting. |
| `check-agent-diagrams` | Any staged file | Blocking | Fix the diagram drift or add the missing diagram. |
| `check-agent-registry` | Any staged file | Blocking | Register the agent in `docs/components.json` / `agent_registry.json`. |
| `check-mermaid-drift` | `docs/architecture/**/*.md` staged | **Disabled** | Enabled after `compute_diagram_hash.py` seeds existing diagrams. |
| `check-mermaid-parent-link` | `docs/architecture/**/*.md` staged | Blocking | Add the bidirectional parent link. |
| `check-diagram-naming` | `docs/architecture/**/*.md` staged | **Disabled** | Enabled after the rename sweep ticket completes. |
| `check-paths-integrity` | `leafcutter/config/paths.json` staged | Blocking | Fix the JSON schema error. |
| `check-architecture-scaffolds` | `leafcutter/templates/docs/architecture/` staged | Blocking | Fix the scaffold integrity error. |
| `check-feedback-id` | `tickets/**/*.md` staged | Blocking | Ensure every signoff comment contains `feedback-id:`. |
| `check-output-drift` | `.claude/agents/`, `.claude/skills/`, `.claude/commands/` staged | Blocking | Edit the template source, not the built copy. Run `build.py` to propagate. |
| `check-glossary-coverage` | `*.md`, `*.py`, `*.sql` staged | **Fail-open (advisory)** | Always exits 0; unexpected errors print a warning. |
| `check-placeholder-defaults` | `*.py` staged | Blocking | (A) Add `# default-path-smoke: <module_stem>` in a test file under `unit_tests/` that exercises the default dispatch path without overriding the parameter. (B) Add `# noqa: default-path-smoke <reason>` in the first 5 lines of the module (requires human review of justification). See ADR-035. |

## check-placeholder-defaults — extended notes

**What it detects:** A Python module that simultaneously contains:

1. A function whose docstring or any `return` string literal matches
   `(?i)\b(placeholder|stub|standalone[-_ ]mode|TODO[: ]|FIXME[: ])\b`.
2. Another function in the same module with a parameter defaulting to `None`,
   immediately rebound via `if x is None: x = <placeholder_fn>`.

**Why it exists:** The EPIC-GlossaryAutomation post-mortem (2026-05-18) identified
this exact structural anti-pattern in `glossary_bootstrap.py` and `check_glossary_coverage.py`.
The tests all overrode the `dispatch_fn` parameter, so the placeholder default path was never
exercised — resulting in a user-facing slash command that silently misfired in production.

**False-positive risk:** Near-zero. Both signals must appear in the **same** module. Modules
with placeholder docstrings during scaffolding (signal 1 only) do not fire. Modules with
`None`-default factory patterns that do not rebind to a placeholder (signal 2 only) do not fire.

**Escape hatch A (preferred):** Add a test that calls the function **without** overriding the
default parameter, and add the marker line at the top of the test file:
```python
# default-path-smoke: check_glossary_coverage
```

**Escape hatch B (explicit opt-out):** If the placeholder is intentional (e.g. an interface
stub in a library), add the suppression at the module top:
```python
# noqa: default-path-smoke This module is an abstract base — dispatch_fn must always be supplied by callers.
```

**ADR cross-reference:** ADR-035 — `docs/architecture/adrs/ADR-035-ast-placeholder-default-hook.md`
