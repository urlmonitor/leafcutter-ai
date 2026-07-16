# Leafcutter Delivery Pipeline — Factual Content Brief (Current State)

> Source of truth: the `flow-site` worktree at
> `/home/henzeh/projects/leafcutter/leafcutter-ai/.claude/worktrees/flow-site`.
> Everything below is drawn from the actual command templates, skill files, agent
> registry, config, hooks, and docs in that checkout. Paths are cited inline.

Leafcutter is a **portable, self-hosting agentic software-delivery pipeline**. It
installs into any project by compiling a `templates/` tree into that project's
`.leafcutter/` (bridged to `.claude/` etc.), then drives work from a human intent
all the way to a merged PR through a chain of slash commands, a supervisor loop,
specialised phase agents, and mechanical pre-commit + finalize gates. The
**acceptance-criteria (AC) store is the authoritative backlog** — tickets are
*derived* from ACs, not authored directly (ADR-010, ADR-012).

---

## 1. The End-to-End Workflow (happy path)

The canonical journey has four user-facing slash commands. `/create-ticket` is
**RETIRED** (ADR-012) — it now only prints a pointer to `/plan-feature` +
`/build-ac`.

| # | Stage | Driver (command → engine) | Inputs | Outputs | Gate / review that follows |
|---|-------|---------------------------|--------|---------|----------------------------|
| 1 | **Plan** | `/plan-feature` → `scripts/workflows/plan-feature.js` (Workflow tool) | Natural-language feature request | AC YAML files in `docs/acceptance-criteria/` only (no tickets) | User confirmation gate after each authoring stage; user sets `priority` and `readiness: approved` at the final gate |
| 2 | **Select & generate ticket** | `/build-ac` → `ac-scanner` skill (`scan_ac_store.py` + `generate_ticket_from_ac.py`) | The AC store (only `readiness: approved` leaf ACs) | One ticket `.md` (or an epic folder in goal mode) with `implemented_by` back-link written to the AC | User prompt: `Build this ticket now? (yes / review / skip)` — then hands off to `/build-feature` (does NOT call it inline — depth cap, ADR-006) |
| 3 | **Build** | `/build-feature` → `build-feature` Workflow (batching inline; `ticket-supervisor` at depth 0) | Epic name / epic folder path / single ticket path | Committed code on a feature branch; ticket `agents:` map fully signed off | Per-phase gates run inside the drive: test-writer → coders → pr-reviewer → ac-validator → commit; PR opened |
| 4 | **Finalize** | `/finalize-feature` → `templates/workflows-js/finalize-feature.js` (Workflow, leaf) | Epic/branch name | Merged PR to `main`, synced local main, tickets closed / epic archived to `99_done`, worktree removed | HALT on merge conflict or test regression; confirmation gate on the PR merge and worktree removal |

There is also a fast lane: **`/quick-fix`** — an in-place bug-fix pipeline that runs
the full red→green TDD cycle in the *current* worktree with no new branch/worktree
(ADR-006 addendum, BP-600*).

### Stage detail

**Stage 1 — Plan (`/plan-feature`).** The workflow first dispatches **`ac-triage`**
(Haiku, read-only) which reads the AC store for the relevant component and classifies
the request as one of `strategic` / `behavioral` / `technical` / `covered`. It then
routes through the three authoring agents with user gates between them:

- **product-owner (PO)** — flight levels **L0/L1**. Customer value propositions (L0)
  and feature-benefit statements (L1). Speaks customer language, never engineering
  jargon; sets `origin_agent: product-owner`. (`templates/commands/po.md`)
- **business-analyst (BA)** — flight levels **L2/L3**. Decomposes each L1 into
  testable Given/When/Then Gherkin behaviours (L2) and edge-case/failure specs (L3);
  assigns `assigned_agent`, `estimated_complexity`, `depends_on`. (`templates/commands/ba.md`)
- **it-po (IT PO)** — **technical enrichment** of existing L2/L3 ACs: adds
  `assigned_agent`, `it_requirements`, `estimated_complexity`,
  `delivers_to`/`expects_from` contracts, `doc_links`. Must NOT touch the `criteria`
  field (that belongs to the BA). Uses architecture docs. (`templates/commands/it-po.md`;
  ADR-009 — IT PO has no source-code access.)

The individual agents can also be invoked directly via `/po`, `/ba`, `/it-po`. All
output lands in the AC store only. New ACs are created `readiness: draft`; the scanner
ignores everything that is not `readiness: approved`.

**Stage 2 — Select & generate (`/build-ac`).** Ranks ready ACs by priority
(critical→low) then complexity, generates a fully-wired ticket from the top AC, and
writes the `implemented_by` back-reference into the AC YAML. Three routing modes
(`templates/skills/build-ac/SKILL.md`):
- **leaf** (L2/L3, or empty `covered_by`) → single ticket.
- **goal** (L0/L1 with non-empty `covered_by`) → generates an epic from all leaf ACs
  beneath it (`goal_to_epic.py`).
- **l1_no_children** (L0/L1, empty `covered_by`) → error: decompose into L2/L3 first.

**Stage 3 — Build (`/build-feature`).** Resolves the target, sets up a worktree, and
drives each ready ticket through its declared phase agents. Epic-level dependency
batching is inlined into the command (ADR-006). See §3.

**Stage 4 — Finalize (`/finalize-feature`).** Deterministic 6-step (plus 3.5/pre-flight)
JS workflow. See §5.

All four commands require the **Workflow tool** (Claude Code ≥ 2.1.154). Each command
template hard-errors if the Workflow tool is unavailable rather than improvising an
LLM run.

---

## 2. The Acceptance-Criteria (AC) Store

**Location:** `docs/acceptance-criteria/`. It is the canonical, authoritative backlog
(ADR-010). `docs/acceptance-criteria/index.yaml` is the component registry; each
component gets its own subdirectory of `<PREFIX>-NNN.yaml` files. (`docs/acceptance-criteria/README.md`)

**Components (from `index.yaml`)** — each has an `id`, ALL-CAPS `prefix`, description,
owner, optional `directory_patterns`: `finalize` (FIN), `ticket-creation` (TKT),
`build-pipeline` (BP), `build-orchestration` (BO), `infrastructure` (INF),
`ux-prototyping` (UXP), `persona-management` (PER), `ac-store` (ACS),
`guardrail-engine` (GE), `knowledge-management` (KM), `testing-quality` (TQ),
`stakeholder-delivery` (SD), `ac-driven-dev` (ACD).

### Flight levels (who authors what)

| Level | Meaning | Authoring agent |
|-------|---------|-----------------|
| **L0** | Customer value proposition (root goal) | product-owner |
| **L1** | Feature benefit statement (sub-goal) | product-owner |
| **L2** | Testable Gherkin behaviour (Given/When/Then) | business-analyst |
| **L3** | Edge-case / failure-mode specification | business-analyst |
| (enrichment) | technical fields on L2/L3 | it-po |

L0/L1 are **composite** — their fulfilment is derived from children (via `covered_by`).
L2/L3 are the **leaf** implementation units the scanner turns into tickets.

### Readiness lifecycle (gates ticket generation)

| Readiness | Set by | Scanner picks up? |
|---|---|---|
| `draft` | product-owner-v3 / business-analyst-v3 | No |
| `reviewed` | it-po-v3 (after enrichment) | No |
| `approved` | User (via `/build-ac` or manual edit) | **Yes** |

`priority` ∈ {`critical`, `high`, `medium`, `low`}; set by the user at approval.

### Real AC YAML field list

Copied verbatim from
`docs/acceptance-criteria/ac-driven-dev/ACD-1100b-3-i.yaml` (an L3 leaf, `readiness: approved`):

```
id: ACD-1100b-3-i
components:            # list — component namespace(s)
  - ac-driven-dev
readiness: approved    # draft | reviewed | approved
priority: high         # critical | high | medium | low
title: "Edge case: no agent in the entire registry carries any version suffix"
component: ac-driven-dev   # scalar component (kebab-case)
level: L3               # L0 | L1 | L2 | L3
status: active          # active | deprecated
req_status: approved
work_status: todo
criteria: |             # Gherkin Given/When/Then (BA-owned; write-locked)
  Given ...
  When ...
  Then ...
depends_on:             # list of AC ids
  - ACD-1100b-3
doc_links:              # list of {path, relationship, status} or bare paths
  - path: docs/reference/agent-template-frontmatter.md
    relationship: describes
    status: exists
assigned_agent: python-coder     # IT-PO enrichment
estimated_complexity: S          # S | M | L | XL
it_requirements:                 # list of technical constraints
  - "..."
delivers_to: null                # inter-agent contract (downstream)
expects_from:                    # inter-agent contract (upstream)
  ac_id: ACD-1100b-3
  contract: "..."
origin_agent: BrainCandy         # authoring actor
created: 2026-06-05
amended_by: []
superseded_by: null
covered_by: []                   # child AC ids (composite fulfilment)
implemented_by: []               # ticket back-links (written by /build-ac)
change_target: config            # code | schema | docs | config
risk_surface: internal
```

An L0 example (`ACD-100.yaml`) additionally shows `covered_by: [ACD-100a, ACD-100b, …]`
populated and `assigned_agent: null` (composite goals aren't directly implemented).

**Pattern-reuse fields** also exist for reusable UI/behaviour patterns:
`pattern_slots`, `implements_pattern`, `pattern_bindings` (see the worked example in
`index.yaml`). The full schema is `config/ac_store_schema.json` (draft-07), enforced
by the `check-ac-schema` pre-commit hook.

---

## 3. The Agent Roster & Supervisor Model

### Depth model (ADR-006 — flatten the supervisor chain)

Claude Code enforces a **hard depth-1 limit** on Agent-tool nesting: an agent invoked
at depth 1 cannot itself invoke the Agent tool (the call is silently dropped). The
original three-tier chain (`epic-supervisor` → `ticket-supervisor` → phase agents) put
phase agents at depth 2, so they never ran. ADR-006 flattens it:

```
/build-feature (slash command, depth 0 — batching inline)
  ├── ticket-supervisor  (depth 0 — the executing context, NOT a spawned sub-agent)
  │     ├── test-writer        (depth 1, Agent tool)
  │     ├── python-coder       (depth 1, Agent tool)
  │     ├── pr-reviewer        (depth 1, Agent tool)
  │     ├── ac-validator       (depth 1, Agent tool)
  │     ├── commit             (depth 1, Agent tool)
  │     └── pull-request       (depth 1, Agent tool)
  └── (next ticket via inline loop — no Agent tool hop)
```

- **`epic-supervisor` is deprecated** (its batching logic is inlined into `/build-feature`).
- **`finalize-feature` LLM agent was removed** entirely (ADR-006 addendum) — the JS
  workflow is the sole depth-0 finalize path, because a depth-1 agent could never
  dispatch its specialists.
- `ticket-supervisor` is the depth-0 orchestrator. Its runbook is
  `templates/skills/building-epics/SKILL.md`; phase agents themselves use the `signoff`
  skill.

### The ticket-supervisor loop (`building-epics` §2)

1. Read frontmatter `agents:` map → pick the first `needed` agent in natural / priority
   order.
2. Spawn it (Agent tool, depth 1) with `{ticket_path}`. The agent does its work then
   runs the `signoff` skill.
3. Re-read the ticket; parse the **last `## Comments` heading** status tag.
4. Route on the tag (see below).
5. Loop until all agents are `{signed_off | not_needed}` → ticket `done`.

**Routing on comment status tag** (`ok` / `handoff` / `blocker` / `question`):
- `ok` → spawn next needed agent.
- `handoff` → spawn the named sibling next (overrides natural order).
- `blocker` → **failure-adjudication ladder**: (1) trivial mechanical retry of same
  agent, (2) cross-agent rework (respawn named sibling), (3) `brainstorm-lead`
  (spawns 2-3 `brainstorm-worker`s for open-ended design), (4) halt + escalate.
- `question` → halt the ticket, surface to user.

**Retry caps:** coder respawn 1/phase/ticket; sibling respawn 1/phase-pair/ticket;
brainstorm-lead 1/ticket. Exceeding a cap falls through to halt.

**Commit-phase serialization lock:** `<worktree_root>/.epic-commit-lock` (atomic
create-if-not-exists) serialises the `commit`/`pull-request` phases across sibling
tickets in one worktree.

### Canonical phase ordering (dispatch-tie priority — `building-epics` §2.1.1)

Lower number runs first:

| Priority | Agent |
|---|---|
| 1 | status-checker |
| 2 | adr-author |
| 3 | architecture-diagram-author |
| 3.5 | it-po |
| 4 | architect-review |
| **5** | **test-writer** (writes failing tests BEFORE coders) |
| 6 | python-coder / llm-expert |
| 7 | sql-coder / sql-query |
| 8 | frontend-coder |
| 9 | test-runner |
| 10 | change-scope-reviewer / documentation-expert / explanation-/how-to-/reference-author |
| **11** | **pr-reviewer** (final quality gate) |
| **11.5** | **ac-validator** (AC coverage gate) + **user-surface-smoker** (concurrent) |
| **11.7** | **ac-fulfillment-gate** (AC store fulfilment) |
| **12** | **commit** (atomic commit) |
| 13 | pull-request (push + open PR) |

**Ticket frontmatter `agents:` map** (real example, from
`tickets/99_done/EPIC-Theacdrivendevelopmentpipelineistheonly/07_TICKET-20260610-ACD-1100b-3-i.md`):

```yaml
agents:
  commit: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  pull-request: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  test-writer: needed
```

Status enum (`signoff` skill §1): `not_needed | needed | signed_off | failed`. A ticket
is `done`-eligible iff every `agents:` entry is in `{not_needed, signed_off}`.

### Notable roster members (from `templates/agents/`, ~55 templates)

- **Authoring:** product-owner(-v3), business-analyst(-v3), it-po(-v3), ac-triage.
- **Implementation:** python-coder, sql-coder (+ sql-*-creator specialists),
  frontend-coder (ADR-005), llm-expert.
- **Test/TDD:** test-writer (priority 5, red baseline), test-runner, test-failure-triage.
- **Review/gates:** pr-reviewer, architect-review, change-scope-reviewer, ac-validator,
  ac-fulfillment-gate, user-surface-smoker.
- **Git:** commit (confirmation-gated), pull-request (conflict-resolver on merge conflict),
  worktree-agent, status-checker.
- **Docs/knowledge:** documentation-expert (Diataxis router) + how-to/reference/
  explanation/adr/architecture-diagram authors, knowledge-harvester, glossary-triage.
- **Escalation:** brainstorm-lead + brainstorm-worker; research-agent (owns the search
  toolkit).
- **Meta/package:** workflow-architect, onboard, onboard-config-section, changelog-agent,
  retrospective-agent, feedback-analyst.

`config/agent_registry.json` is the single source of truth (id, tier, role,
`produces` trait, `requires_ticket_section`, `spawn_allowlist`); the supervisor reads
the `produces` trait to decide whether TDD guardrails apply (`production_code` → yes).

---

## 4. Tickets, Epics & Worktrees

### Folder lifecycle (`tickets/README.md`, `tickets/ticket_lifecycle.json`)

```
tickets/
  00_inbox/              proposed work (+ epics/EPIC-Name/ for multi-ticket work)
  01_todo/               actively in-flight (one git worktree per epic)
      EPIC-Name/ done/   completed sub-tickets within a live epic
  99_done/               archived finished epics + single tickets
  99_rejected/           decided-against work (kept for history)
```

`status:` frontmatter (`todo | in_progress | blocked | done | deferred`) is the
**authoritative lifecycle signal — not folder position**. Supervisors read frontmatter;
scripts do not shuffle tickets between folders as a pipeline.

### Naming

- Single ticket: `TICKET-YYYYMMDD-Name.md`
- Epic folder: `EPIC-Name/` with `Master_Plan.md`
- Sub-ticket: `NN_snake_case_slug.md` (`NN` = zero-padded execution order; `02a`/`02b`
  for parallel splits; gaps allowed)

### Epic structure

An epic = multi-ticket body of work sharing **one git worktree and one PR**.
`Master_Plan.md` (frontmatter `type: epic`) must include a `## Key Design Decisions`
section and a sub-ticket table.

### Real ticket frontmatter field list

From `07_TICKET-20260610-ACD-1100b-3-i.md`:

```yaml
advances_current_outcome: true
agents:                 # phase-agent status map (see §3)
  commit: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  pull-request: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  test-writer: needed
components:              # >=1 id
- ac-driven-dev
created: '2026-06-10'
depends_on:             # sibling filenames / AC ids, [] if none
- ACD-1100b-3
files_touched:          # physical footprint — drives parallel-safety batching
- docs/reference/agent-template-frontmatter.md
priority: high
requires_adr: false
requires_diagram: false
roadmap_phase: phase_1
source_ac: ACD-1100b-3-i    # back-link to the generating AC
status: todo
title: 'Edge case: no agent in the entire registry carries any version suffix'
```

Required frontmatter (per `commit_guardian.json` `ticket_frontmatter`): `title`,
`status`, `components`, `created`, `depends_on`. Optional `ac_coverage: N/M` (validated
count of ACs). The ticket body carries `## Acceptance Criteria` (Gherkin),
`## Implementation Tasks` (per-agent `### <agent>` checklists, gated by
`requires_ticket_section: true`), `## Sign-offs`, and `## Comments`.

### Worktree isolation (`feature` skill)

Epic/feature work runs in an isolated `git worktree` created **from `origin/main`**
(never from uncommitted changes), branch named after the epic, living beside the main
repo. One worktree per epic, reused across its tickets. Bootstrap runs
`build.py --target-dir .` and must establish `.pre-commit-config.yaml` (a `.leafcutter`
symlink, or a file copy on NTFS/WSL2) — otherwise **all package hooks silently skip**
for the whole drive (a documented, recurring hazard; there is a mandatory post-build
probe that HALTs if the config can't be established). `/quick-fix` is explicitly
forbidden from creating any worktree (ADR-006 BP-600a-2).

---

## 5. The Gates

### a) Pre-commit hooks (`templates/scripts/commit_guardian/commit_guardian.json`)

A large "commit guardian" manifest generates `.pre-commit-config.yaml`. Hooks are
tiered `transform` (auto-fix, fail-open) vs `judgment` (validate, may block). Key hooks:

- **Self-healing:** `ensure-precommit-config` (index 0; re-materialises the config).
- **Ticket/sign-off:** `check_ticket_signoff_parity.py` (three-place parity — see §5b),
  `check-feedback-id`, `check-commit-scope` (warn), `check-predone-scope`
  (files_touched vs diff, advisory).
- **AC store:** `check-ac-schema`, `check-ac-governance` (write-locks `criteria`,
  `title`, `req_status`, `depends_on` to authorised authors only — ACS-400),
  `check-ac-tree-limits`, `check-ac-parent-covered-by`, `check-ac-circular-deps`,
  `check-ac-pattern-refs`.
- **TDD:** `check-contract-shrinking` (blocks test deletion / `pytest.skip` / `xfail`
  staged alongside production code).
- **Error handling (repo policy):** `check-exception-handling` (AST: bare-except E722,
  blind `except Exception` BLE001, unwrapped I/O calls) — mirrors the four Ruff rules
  (E722, BLE001, TRY) that are the required CI gate.
- **Docs/arch:** `transform-doc-frontmatter`, `check-doc-frontmatter`,
  `check-structural-change`, `check-adr-coverage` (warn), `check-components-integrity`,
  mermaid drift/parent-link/complexity, `regenerate-roadmap-mirror`, `check-roadmap-schema`.
- **Quality:** `check_file_size` (400 py / 600 sql for new files), `check_complexity`
  (cyclomatic ≤ 15), `check_docstrings` (Google style), `check-secrets`,
  `check-placeholder-defaults` (AST guard against placeholder-dispatch defects),
  `check-glossary-coverage` (fail-open), `check-duplicate-code` (jscpd, off by default),
  `check-diff-coverage` (off by default).
- **Package integrity:** `check-build-drift`, `check-output-drift` (blocks direct edits
  to built output), `check-hook-parity`, `check-workflow-meta` (pure-literal `meta`).

Also PreToolUse hooks: `enforce_commit_delegation` (blocks direct `git commit` — must go
through the `commit` agent) and `check_commit_ticket_staged`.

### b) The sign-off protocol (`signoff` skill)

Every phase agent's final action. Status enum `not_needed | needed | signed_off |
failed`. The **three-place parity rule** (enforced by `check_ticket_signoff_parity.py`):
in one atomic operation an agent must (1) set `agents.<name>: signed_off` in frontmatter,
(2) tick `- [x] <name> — YYYY-MM-DD HH:MM` in `## Sign-offs`, (3) tick all its
`## Implementation Tasks` checkboxes. It then calls `submit_feedback.py` for a
`feedback-id`, appends a parser-strict `## Comments` heading
(`### YYYY-MM-DD HH:MM — <agent> (status: ok|blocker|question|handoff)`) containing a
`completion_manifest:` block, and stages the ticket. **Failed path:** set `failed`, leave
the checkbox unchecked with a `failed` timestamp, append a `blocker` comment, return a
structured payload so the supervisor can adjudicate/halt.

### c) Test-first TDD

`test-writer` (priority 5) runs *before* any coder, writes the failing tests, and
records a `red_baseline`. Coders make the red baseline green; `test-runner` (priority 9)
validates. The supervisor applies TDD guardrails based on the agent's `produces:
production_code` trait. Docs-only/config-only tickets auto-skip test-writer (empty/absent
`## Test Requirements` block). `check-contract-shrinking` blocks test weakening at
commit time. (ADR-004-tdd-workflow-enforcement.)

### d) PR + Ruff gate

`main` is **PR-only**: a direct push is rejected by branch protection (`Lint (ruff)`
required check). The `pull-request` agent opens/updates one PR per epic. Ruff (E722,
BLE001, TRY families + lint) is the required CI status; a non-required pytest job also
runs (with a known pre-existing baseline failure).

### e) `/finalize-feature` post-merge steps (`finalize-feature.js`)

Deterministic leaf workflow; every specialist dispatch is a flat depth-1 `agent()` call.
Each step probes observable state first (resumable after a crash):

- **Pre-flight:** status-checker reads current branch + worktree root.
- **Step 0:** capture baseline test run on `main` HEAD (test-runner; graceful on failure).
- **Step 1:** probe for an open PR (`gh pr list`); dispatch `pull-request` if missing.
- **Step 2:** merge `origin/main` into the worktree `--no-commit --no-ff` — **HALT on conflict**.
- **Step 3:** run post-merge tests + `test-failure-triage` — **HALT on regressions**
  (baseline-diffed).
- **Step 3.5:** pre-merge AC closure — reset the test-merge, set ticket `status: done`,
  mark source ACs done, commit on the feature branch.
- **Step 4:** merge the PR to `main` — only if tests pass (**confirmation-gated**).
- **Step 5:** sync local main (`git checkout main && git pull`).
- **Step 6:** report untracked pre-existing/flaky failures + scope detection (no writes on main).
- **Step 7:** remove the worktree (worktree-agent; gate delegated).

A separate `finalize-feature-archive-check` gate verifies every sub-ticket has
frontmatter `status: done` before an epic is archived to `99_done`. Full finalization
also produces a changelog (changelog-agent) and a retrospective (retrospective-agent).

---

## 6. The Package / Build Model

### `scripts/build.py` — the deploy engine

CLI entry point that compiles everything under `templates/` into a target project.
`main()` flow: parse args → `load_config()` → validate config + registry against schemas
→ deployment preflights (script-reference + tracked-source guards) → SemVer/version read
→ halt-guard (breaking-change check) → self-description validation → config migration →
deploy-collision guard → `_run_phases()` → write `VERSION`/`LEAFCUTTER_VERSION` + build
manifest + `.leafcutter.lock` → stale cleanup → install shims → install hooks →
post-build placeholder + referential-integrity scan.

**Deploy target — `.leafcutter` vs `.claude` (consolidated output root, ADR-004).**
Output root defaults to `<target>/.leafcutter` (config `output_root`). A **shim** step
(`install_shims`, config `shim_strategy: auto`, `--no-shims` to skip) then bridges to the
platform-native locations tools hardcode: `.claude/agents`, `.claude/skills`,
`.claude/commands`, `.claude/hooks`, `.claude/settings.json`, `.pre-commit-config.yaml`,
etc. User-curated scaffolds (vision, roadmap, glossary, tickets, components registry, AC
store, agent cards) write directly to the target root (write-if-absent, user-owned).

**Artifact phases** (three groups): artifacts→output_root (Agents, Workflow scripts, AC
store scripts, Skills, Commands, Claude settings, Workflows, Hooks, Pre-commit config,
Antigravity instructions); internal→output_root (Rules, Commit guardian, Feedback, Doc
compliance, Sync platforms, Workflow tools, Knowledge scripts); scaffolds→target root.

**CLI flags:** `--target-dir/-t`, `--config-path/-c`, `--dry-run`, `--validate-only`,
`--force` (no-op alias — overwrite is default), `--no-overwrite`, `--force-breaking`,
`--no-shims`, `--migrate`, `--update-diagrams`, `--seed-docs`, `--clean`,
`--self-description-enforcement {warning,error}`. A byte-identical compare-before-write
guard makes consecutive builds produce zero diff (idempotent — a phase-1 exit criterion).

**Dual/multi-platform compilation (ADR-002): yes.** Driven by `config["platforms"]`
(default `{claude: true, antigravity: true, cursor/copilot/cline: false}`). Agents/hooks/
workflows are emitted per active platform into per-platform subdirs (e.g. Claude
`agents`/`commands`; Antigravity `gemini/agents`/`gemini/workflows`).
`build_antigravity_instructions` compiles `templates/ANTIGRAVITY.md.template` →
`.gemini/instructions.md`.

Self-hosting: leafcutter builds itself (`./build-self.sh` = `build.py --target-dir .`
from the workspace parent). ADR-001 defines the self-hosting boundary; the parent
`leafcutter/` workspace is untracked build output, `leafcutter-ai/` IS the git repo.

### `skills_config.json` — the portable adopter config

No committed runtime `skills_config.json` ships in the package; it is generated per
adopter (by `/onboard`, written to `.claude/skills_config.json`). The package ships
`config/skills_config.default.json` (Bybit-Trader defaults) and
`config/skills_config.schema.json`. Skills/agents read values via a `_get(key, default)`
pattern; absent key/file → built-in default (behaviour preserved). `build.py` injects
these values into templates.

**Top-level keys** (schema): `output_root`, `shim_strategy`, `platforms`,
`tickets_*_path`, `ticket_lifecycle_path`, `test_command_*`,
`precommit_autofix_config_path`, `default_branch`, `collector_enforcer_paths`,
`top_level_packages`, `test_output_dir`, `worktree_base_path`, `settings_module`,
`docs_root`, `changelog_folder`, `changelog_categories_path`, `worktree_cleanup`,
`workflows`, `testing_context` (+ `project_description`, `common_commands`,
`architecture_overview`, `glossary`, `frontend`, `hooks`). `/onboard` groups keys into
five sections: **testing**, **packages**, **tickets**, **commands**, **project**.

### The `/onboard` wizard (`templates/agents/onboard.md`, Sonnet)

Portable guided install wizard. Auto-discovers repo structure, fans out one
`onboard-config-section` Haiku sub-agent per config section (parallel), assembles a
proposed `skills_config.json`, shows a diff for sign-off, and runs `build.py` on approval.
Steps: detect git/branch (+ WSL2 autocrlf, + Claude Code version warn < 2.1.154) → read
default + existing config → scan folders → read whitelist files (never `.env`/secrets) →
fan out 5 section sub-agents → offer frontend optional skills (webapp-testing) → merge
fragments → present diff + CLAUDE.md preview → write config on approval → run
`build.py --target-dir .` → verify outputs → `pre-commit install` → optional hook opt-in
(jscpd/diff-cover) → placeholder detection in vision/roadmap → interactive vision/roadmap
fill → glossary bootstrap prompt → post-onboard checklist. Documented to auto-fire on
SessionStart when `skills_config.json` is absent or all-default (note: no SessionStart
hook is wired in this checkout's `templates/settings.json`, so the concrete path is a
manual `/onboard`).

### `config/` registry files (one-line purposes)

`agent_registry.json` (+ `.schema.json`) — single source of truth for all agents;
`skill_registry.json` (+ `.schema`) — all skills; `ac_schema.json` / `ac_store_schema.json`
— AC record schemas; `guardrail_gates.yaml` — quality/enforcement gate definitions;
`paths.json` — canonical path constants injected into built agents/skills;
`package_boundary.json` — portable-vs-domain module classification (ADR-020);
`feedback_categories.yaml` — closed feedback vocabulary; `diagram_types.json` /
`doc_types.json` — canonical diagram/doc type values; `test_requirements.schema.json` —
ticket test-block schema; `ticket_lifecycle.json` — status state machine;
`roadmap.schema.json` — roadmap schema; `commit_message_patterns.json` — commit
classification; `version.json` — package version. (`docs/components.json` is the component
registry; `docs/roadmap.json` the roadmap instance.)

### Roadmap (`docs/roadmap.json`)

Machine-readable delivery plan. **Current phase: `phase_1`** —
*"Stable MVP that installs into any project and helps the user build good software —
portable, self-onboarding, and reliable enough to use across multiple repos."* Exit
criteria: clean install on a blank project with only `skills_config.json`;
`build.py --validate-only` returns 0; consecutive builds produce zero git diff
(idempotent); self-hosting parity. Later phases: `phase_2` Ecosystem Hardening
(version upgrades, contribution workflow, schema validation), `phase_3` Distribution and
Community (pip/npm packaging, versioned releases + changelogs, extension mechanism).

---

## Compact happy-path journey (numbered)

1. **User states a feature intent** → runs `/plan-feature "<request>"`.
2. **ac-triage** (Haiku) classifies the request (strategic / behavioral / technical / covered).
3. **product-owner** authors L0/L1 ACs (customer value) → user gate.
4. **business-analyst** decomposes into L2/L3 Gherkin ACs → user gate.
5. **it-po** adds technical enrichment (assigned_agent, contracts, complexity) → user gate.
6. User sets `priority` + `readiness: approved`; AC YAML files land in `docs/acceptance-criteria/`.
7. **`/build-ac`** ranks ready leaf ACs, generates a ticket (writes `implemented_by` back-link), prompts `yes / review / skip`.
8. **`/build-feature`** resolves the target and creates/reuses a `git worktree` off `origin/main` (bootstraps `.leafcutter` + pre-commit config).
9. **ticket-supervisor** (depth 0) drives the ticket: **test-writer (5)** writes failing tests → **python/sql/frontend-coder (6-8)** implement → **test-runner (9)** greens them.
10. **pr-reviewer (11)** self-reviews the diff; **ac-validator (11.5)** + **user-surface-smoker** confirm AC coverage; **ac-fulfillment-gate (11.7)** updates the AC store.
11. **commit (12)** stages + commits (pre-commit hooks fire: signoff parity, AC governance, exception handling, contract-shrinking, secrets, etc.); each phase signs off via the `signoff` skill.
12. **pull-request (13)** pushes the branch and opens one PR per epic; **Ruff CI** is the required gate on `main`.
13. **`/finalize-feature`** captures a test baseline, merges `origin/main` into the worktree (HALT on conflict), runs post-merge tests + triage (HALT on regression), closes tickets + marks source ACs done (step 3.5), merges the PR (confirmation-gated), syncs main, archives the epic to `99_done`, and removes the worktree.
14. **changelog-agent** + **retrospective-agent** produce the changelog and epic retrospective.

---

## Key reference paths

- Commands: `templates/commands/{plan-feature,build-feature,finalize-feature,po,ba,it-po,quick-fix,create-ticket}.md`
- Supervisor runbook: `templates/skills/building-epics/SKILL.md`
- Sign-off protocol: `templates/skills/signoff/SKILL.md`
- AC store: `docs/acceptance-criteria/` (`README.md`, `index.yaml`, `config/ac_store_schema.json`)
- Hooks: `templates/scripts/commit_guardian/commit_guardian.json`
- Finalize workflow: `templates/workflows-js/finalize-feature.js`
- Build engine: `scripts/build.py`; adopter config: `config/skills_config.default.json` + `.schema.json`
- Onboarding: `templates/agents/onboard.md`, `onboard-config-section.md`
- Roadmap: `docs/roadmap.json`
- ADRs: `docs/architecture/adrs/ADR-006` (flatten chain), `ADR-010` (AC store backlog), `ADR-012` (retire create-ticket), `ADR-002` (dual-platform), `ADR-001` (self-hosting), `ADR-004` (TDD + consolidated root), `ADR-005` (frontend-coder), `ADR-009` (IT-PO no code access)
```

