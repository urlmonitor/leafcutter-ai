# leafcutter

Domain-agnostic agent/skill/workflow package for use across projects. Contains
configuration schemas, evaluators, and templates that are not tied to any
specific business domain (bybit-trader or otherwise).

A self-contained package that installs the full Bybit-Trader-style AI agent
development workflow into any project. Copy the package, edit one JSON config
file, run `build.py`, and get the complete system generated.

## What You Get

- **Agent prompts** (`.claude/agents/`): supervisor stack, phase agents, utility agents
- **Skills** (`.claude/skills/`): signoff, building-epics, create-ticket, feature, precommit-autofix, and more
- **Workflows** (`.claude/commands/`): `/build-feature`, `/commit`, `/pull-request`, etc.
- **Rules** (`.agents/rules/`): documentation, debug-scripts, git-commits
- **Pre-commit hooks** (`scripts/commit_guardian/`): quality gates on every commit
- **Doc compliance** (`scripts/doc_compliance/`): architecture doc freshness enforcement
- **Ticket lifecycle** (`tickets/`): inbox, todo, done, rejected folders with READMEs

## Purpose

Provides the reusable tooling layer for the leafcutter system:
agent registry configuration, selection criteria evaluation, and skill templates
that any adopter project can include verbatim.

## Key Files

- `config/agent_registry.json` — single source of truth for all agents, their
  spawn relationships, ticket-phase roles, and selection_criteria.
- `config/agent_registry.schema.json` — JSON Schema for agent_registry.json;
  enforces the two-tier trigger_condition format (ADR-018).
- `config/package_boundary.json` — classification map: which files in the live
  project are `portable` (move into package templates) vs `project-specific`
  (stay in the consumer project). Read by `scripts/package_audit.py`. Edit this
  file to reclassify items; the audit script reads it on every run.
- `scripts/package_audit.py` — repeatable gap analysis between package templates
  and the live project. Run `python leafcutter/scripts/package_audit.py`
  from the project root for a Markdown report. Pass `--json` for machine-readable
  output. Pass `--json-out <path>` to write a JSON sidecar alongside the report.
- `scripts/selection_criteria_evaluator.py` — DSL-first evaluator for
  `selection_criteria.trigger_conditions`; used by `business-analyst` to build
  the `agents:` map for new tickets.
- `scripts/worktree/sweep_processes.py` — cross-platform pre-removal sweep
  helper; terminates residual background worker processes and removes log files
  before `git worktree remove`. Invoked by the close-worktree workflow (Phase 3.5)
  and the worktree-agent remove action. Run with `--dry-run` to preview without
  acting. Config keys: `worktree_cleanup.kill_residual_processes`,
  `worktree_cleanup.log_globs`, `worktree_cleanup.protected_paths`.

## Critical Context

- `trigger_conditions` use the two-tier format per ADR-018: `{type: "dsl", expression: "..."}` for
  deterministic rules, `{type: "llm", expression: "..."}` for natural-language judgment calls.
- The DSL grammar v1 supports `contains`, `equals`, `matches` operators over
  `files_touched`, `title`, `description`, and `components` fields, with `AND`/`OR` combinators.
- LLM-type conditions are stubbed (raise `LLMEvaluationRequired`); actual LLM wiring
  is deferred to a follow-up ticket.

## Quick Start

```bash
# 1. Copy this directory into your project
cp -r leafcutter/ your-project/

# 2. Create your config file
cp leafcutter/config/skills_config.default.json your-project/.claude/skills_config.json
# Edit .claude/skills_config.json — update paths, test commands, branch name

# 3. Run build
cd your-project
python leafcutter/scripts/build.py --target-dir .

# 4. (Optional) Validate config only
python leafcutter/scripts/build.py --validate-only

# 5. (Optional) Dry run
python leafcutter/scripts/build.py --dry-run
```

## NEW_PROJECT_SETUP — Glossary Bootstrap

After completing the Quick Start above, run the glossary bootstrap once to seed
`docs/glossary.md` from your existing codebase:

```
/glossary-bootstrap
```

This scans all `.md`, `.py`, `.sql` files in your repo, classifies novel jargon
terms using the `glossary-triage` agent, and commits the initial glossary entries.
Run it after any major codebase merge as well. After the bootstrap, the
`check-glossary-coverage` pre-commit hook takes over for incremental per-commit
coverage.

See `leafcutter/templates/skills/glossary-bootstrap/SKILL.md` for full
documentation.

See `BOOTSTRAP.md` (human-readable guide) or `SETUP.md` (AI-readable) for
step-by-step adoption instructions.

## Package Structure

```
leafcutter/
  templates/
    agents/           ← agent templates with YAML frontmatter
    skills/           ← skill templates (SKILL.md + scripts)
    workflows/        ← workflow templates
    rules/            ← rule file templates
    pre-commit-hooks/ ← hook script templates
    ticket-lifecycle/ ← tickets/ folder structure + READMEs
    commit-guardian/  ← commit guardian config + scripts
    doc-compliance/   ← doc compliance config + scripts
  scripts/
    build.py          ← main build script
  config/
    skills_config.schema.json  ← JSON Schema for validation
    skills_config.default.json ← Bybit-Trader defaults
  docs/
    build-pipeline.md          ← source → build → output flow
    agentic-runtime-flow.md    ← how agents invoke each other
    ticket-lifecycle.md        ← ticket state machine
    pre-commit-hooks.md        ← hook sequence and configuration
  README.md
  BOOTSTRAP.md  (written by ticket 15)
  SETUP.md      (written by ticket 15)
```

## Design Principles

1. **If the AI would not change its behaviour based on the text, it should not be in the prompt.**
   Agent templates carry YAML frontmatter for adopter notes, config key declarations,
   and portability metadata. `build.py` strips all of this before generating runtime prompts.

2. **One config file per project.** The adopter edits `.claude/skills_config.json` once.
   Everything flows from there.

3. **Package is repo-ready.** This directory is structured to be extracted into its own
   git repo without restructuring. Domain artifacts (Bybit-Trader-specific agents/skills)
   remain outside the package in the target project.

4. **Overwrite by default.** Running `build.py` overwrites existing materialised files so
   that template edits always reach the target project. Use `--no-overwrite` to restore
   the legacy skip-existing behaviour (only absent files are written). `--force` is
   retained as a no-op alias for the new default.

## Configuration Keys

See `config/skills_config.schema.json` for the full schema.
Key fields:

| Key | Default | Purpose |
|-----|---------|---------|
| `tickets_inbox_path` | `tickets/00_inbox` | Root for proposed tickets |
| `tickets_todo_path` | `tickets/01_todo` | Root for in-flight tickets |
| `default_branch` | `main` | PR target branch |
| `test_command_live_trader` | `poetry run python -m unittest ...` | Fast test suite command |
| `worktree_base_path` | `../` | Parent dir for epic worktrees |
| `settings_module` | `settings` | Python module to verify after bootstrap |

## Extending the Package

All extensions to `leafcutter` must flow through the `workflow-architect`
agent and its four dispatch skills. **Do not edit package files directly.**

| What you want to add | How |
|----------------------|-----|
| A new pre-commit hook | Invoke `workflow-architect` → it uses the `create-hook` skill |
| A new portable agent | Invoke `workflow-architect` → it uses the `add-agent-to-package` skill |
| A new portable skill | Invoke `workflow-architect` → it uses the `add-skill-to-package` skill |
| Audit current package gap | Invoke `workflow-architect` → it uses the `package-audit` skill |

The `package-audit` skill runs `scripts/package_audit.py` and presents a Markdown
table of all portable files not yet in the package templates, grouped by section
(commit-guardian / agents / skills). See
[ADR-020](docs/architecture/adrs/ADR-020-leafcutter-package-boundary.md)
for the classification heuristics.

`workflow-architect` is selected automatically when a ticket's `files_touched`
contains `leafcutter` or when the ticket involves adding a hook,
agent, or skill to the package (see its entry in `config/agent_registry.json`).

### Post-build DECISION HISTORY sync

After running `python leafcutter/scripts/build.py --force`, the
regenerated `.pre-commit-config.yaml` (root) AND
`leafcutter/.pre-commit-config.yaml` (build artifact copy) both
require a DECISION HISTORY entry — today's date plus `HH:MM` timestamp —
before the next `git commit`. Staging with `git add -A` first will overwrite
your manual edit, so update DECISION HISTORY in both files BEFORE staging.

Format (after the existing entries, before the closing `# ===` sentinel):

```
# - 2026-MM-DD HH:MM [<author>]: <one-line summary of what build.py changed>.
```

The `check-documentation` hook flags the regenerated file as a structural
change and will block the commit until DECISION HISTORY is updated. This is
not optional — the dual update is the established convention, codified by
EPIC-FeedbackCollection retro KI.

### Hook-to-config sync discipline

When migrating an existing pre-commit hook from `scripts/commit_guardian/` into
`leafcutter/templates/commit-guardian/`, the same commit MUST also
add every constant the hook imports from `config.py` to the **template** copy
of `config.py`. The live copy already has the constants; the template usually
does not. A missing constant causes `ImportError` at startup in every consumer
project that builds from the template — the exact failure mode that produced
unplanned blockers during EPIC-WorkflowArchitect (T09).

The `create-hook` skill (Step 5a) enforces this for newly-scaffolded hooks.
For migrations, run:

```bash
grep -E "^from config import" leafcutter/templates/commit-guardian/<hook_name>.py
```

and confirm every imported name has a matching `<NAME>: <type> = _get(...)`
line in `leafcutter/templates/commit-guardian/config.py`.

## Maintenance

- To add a new agent: (1) add an entry in `agent_registry.json`, (2) create the template
  file at the specified `template_path`, (3) run `scripts/build.py --validate`.
- To add a new DSL operator or field: update `selection_criteria_evaluator.py` and add
  tests in `unit_tests/portable_dev_workflow/test_selection_criteria_evaluator.py`.
- All `dsl`-type conditions in `agent_registry.json` are validated at pre-commit time via
  the schema conformance test.

## Artifact Inventory

### Generic-Portable Agents (go into templates/agents/)

- Supervisor stack: `epic-supervisor`, `ticket-supervisor`, `build-single-ticket`,
  `create-ticket`, `create-epic`, `brainstorm-lead`, `brainstorm-worker`, `research-agent`
- Phase agents: `python-coder`, `pr-reviewer`, `commit`, `pull-request`, `worktree-agent`,
  `status-checker`, `test-runner`, `architect-review`, `conflict-resolver`
- Utility: `documentation-expert`, `code-refactoring-specialist`
- Package management: `workflow-architect` (tier: supervisor, role: orchestration)
  — stewards the leafcutter surface: agent registry, hook registry,
  skill registry, and build pipeline. Dispatches four skills: `create-hook`,
  `add-agent-to-package`, `add-skill-to-package`, `package-audit`.

### Generic-Portable Skills (go into templates/skills/)

- Lifecycle: `signoff`, `build-single-ticket`, `building-epics`, `create-ticket`, `feature`
- Code quality: `complexity-reduction`, `doc-enforcer`, `code-analysis`, `import-scanner`
- Commit: `precommit-autofix`, `ship`

### Generic-Portable Commit-Guardian Hooks (go into templates/commit-guardian/)

These 10 hooks are fully config-driven and contain no project-specific paths.
All bybit-trader defaults are encoded in `commit_guardian.json` and overridable
per consumer project.

| Hook | Purpose |
|------|---------|
| `check_build_drift.py` | Detects template/generated-output drift via `build.py --dry-run` |
| `check_secrets.py` | Scans staged files for secrets; scanner path via `security_scanner.scripts_dir` |
| `check_doc_length.py` | Enforces per-extension line limits on new files |
| `check_structural_change.py` | Blocks structural commits without `docs/components.json` update |
| `check_components_integrity.py` | Validates `docs/components.json` schema and cross-references |
| `check_adr_coverage.py` | Advisory warning when structural changes land without an ADR |
| `check_adr_cross_reference.py` | Validates ADR cross-reference links are not broken |
| `check_infra_docs.py` | Enforces inline comments on high-impact infra keywords |
| `check_agent_diagrams.py` | Validates agent diagrams are up to date |
| `check_agent_registry.py` | Validates `agent_registry.json` schema compliance |

### Domain-Only Artifacts (stay in Bybit-Trader, NOT in this package)

Everything marked `domain: bybit-trader` by the portability audit (ticket 08):
database-agent, prod-deploy, sql-coder, reporting-agent, strategy-builder,
db skill, strategy-* skills, analyze-trades, fetch-prod-logs, pipeline-health,
prod-puller, find-context-candle, scheduling-enforcer, collector-enforcer.

## Architecture Docs

- [ADR-020: Package Boundary](docs/architecture/adrs/ADR-020-leafcutter-package-boundary.md) — decision criteria for portable vs project-specific classification
- [Build Pipeline](docs/build-pipeline.md) — source → build → output flow
- [Agentic Runtime Flow](docs/agentic-runtime-flow.md) — agent interaction at runtime
- [Ticket Lifecycle](docs/ticket-lifecycle.md) — ticket state machine
- [Pre-Commit Hooks](docs/pre-commit-hooks.md) — hook sequence and configuration
- [Agent Delivery Workflows](docs/architecture/agent_delivery_workflows.md) — slash commands → agents → supervisors (extensive flow diagrams)
- [Agent Inventory & Front Door](docs/agents/README.md) — complete agent registry and tier summary
- [Agent Authoring Conventions](docs/agents/conventions.md) — frontmatter, patterns, visibility classes, tool allowlists

### Agent Reference Docs (by role)

| Folder | Agents | Count |
|---|---|---|
| [supervisor/](docs/agents/supervisor/) | epic-supervisor, ticket-supervisor, brainstorm-lead | 3 |
| [ticket-creation/](docs/agents/ticket-creation/) | create-ticket, create-epic, business-analyst, refinement | 4 |
| [coding/](docs/agents/coding/) | python-coder, research-agent, architect-review, architecture-author | 4 |
| [sql/](docs/agents/sql/) | sql-coder, sql-function/index/procedure/table/view-creator | 6 |
| [documentation/](docs/agents/documentation/) | documentation-expert, adr-author, explanation/how-to/reference-author | 5 |
| [git/](docs/agents/git/) | commit, pull-request, pr-reviewer, conflict-resolver, precommit-autofix | 5 |
| [utility/](docs/agents/utility/) | status-checker, test-runner, worktree-agent | 3 |
