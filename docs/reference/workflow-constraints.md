---
title: "Reference: Claude Code Workflow Script Constraints"
type: reference
status: active
created: 2026-06-01
last_updated: 2026-06-10
components:
  - build_pipeline
related_docs:
  - "templates/workflows-js/build-ticket.js"
  - "templates/workflows-js/build-epic.js"
  - "templates/workflows-js/create-ticket.js"
  - "scripts/workflows/plan-feature.js"
  - "docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md"
  - "docs/how-to/configure-workflow-allowlist.md"
  - "templates/agents/onboard.md"
---

# Workflow Script Constraints

This reference page documents the runtime constraints that apply to leafcutter's
Claude Code Workflow scripts (`build-ticket.js`, `build-epic.js`,
`create-ticket.js`). It covers the minimum version requirement, token cost
implications, the no-mid-run-steering constraint, and the crash-resume
mechanism.

---

## Minimum Version Requirement

**Minimum Claude Code version: 2.1.154**

Claude Code Workflow script support was introduced in v2.1.154. Users on older
versions receive only the legacy supervisor agent path — the three workflow
scripts are not installed and `/build-feature`, `/build-ticket`, and
`/create-ticket` fall back to direct agent invocation.

### How to verify your version

```bash
claude --version
```

The output reports the installed version. Alternatively, the environment
variable `CLAUDE_CODE_VERSION` is set by the runtime:

```bash
echo "$CLAUDE_CODE_VERSION"
```

### Feature availability by path

| Feature | Legacy agent path | Workflow script path (>= 2.1.154) |
|---|---|---|
| `/build-ticket` (drive a ticket) | Spawns `ticket-supervisor` agent | Runs `build-ticket.js` — all phase agents at depth 1 |
| `/build-epic` (drive an epic) | Spawns `epic-supervisor` agent (deprecated) | Runs `build-epic.js` — all tickets in parallel batches |
| `/create-ticket` | Legacy BA/refinement agents removed — use workflow path | Runs `create-ticket.js` — flat sequential/parallel dispatch |
| `/plan-feature` (AC authoring pipeline) | Spawns `ac-triage` → authoring agents chain | Runs `plan-feature.js` — triage → PO v3/BA v3/IT PO v3 with user gates |
| Permission prompts | Standard per-command prompts | Reduced via `allowedTools` allowlist in `settings.json` |
| Mid-run user steering | Available (agent responds to chat) | Only at `prompt()` checkpoints |

### Upgrade path

Download the latest Claude Code from the official distribution channel and run
`/onboard` again. The wizard detects the new version at Step 1b and offers to
install the workflow scripts into `.claude/commands/`.

---

## Token Cost Implications

Workflow scripts introduce one additional LLM call per workflow invocation —
the **planner agent** call — which reads the ticket or epic frontmatter and
returns the ordered phase list as JSON. This planner call consumes a small
number of input tokens (the ticket frontmatter) and outputs a compact JSON
array (typically 50–200 tokens).

### Per-invocation overhead

| Workflow | Extra calls per invocation | Typical extra token cost |
|---|---|---|
| `build-ticket.js` | 1 (planner) | ~200–500 input tokens; ~50–200 output tokens |
| `build-epic.js` | 1 (planner) per epic, plus 1 per ticket batch | ~200–800 input tokens per batch |
| `create-ticket.js` | 1 (planner) | ~100–300 input tokens; ~50–100 output tokens |

These figures are estimates based on typical ticket sizes. Very large tickets
(>2,000 tokens of frontmatter) may incur higher costs. The planner output is
always compact — it is a JSON array of phase names.

### Legacy path comparison

On the legacy agent path, there is no planner call. The supervisor agent
reads the ticket frontmatter directly as part of its own reasoning loop,
which does not add a separate LLM call but does add the frontmatter tokens
to the supervisor's working context on each loop iteration. Total token cost
is roughly comparable.

---

## No-Mid-Run-Steering Constraint

Once a workflow script starts, it runs **deterministically** — the JavaScript
runtime executes the phase loop without pausing for user input between phases.

This differs from the legacy agent path, where the supervisor is an LLM that
can read a mid-run message from the user and adjust course.

### Where user input IS possible

User steering is possible at explicit `prompt()` checkpoints embedded in
the workflow scripts. The current checkpoints are:

| Script | Checkpoint | When triggered |
|---|---|---|
| `create-ticket.js` | Open-questions review | When `business-analyst` surfaces open questions that require user clarification before refinement proceeds |

To add a steering checkpoint to a workflow script, use the `prompt()` function
provided by the Claude Code workflow runtime:

```javascript
const userAnswer = await prompt(
  "Describe the open questions here. How should we proceed?"
);
```

### Workaround for mid-run decisions

If you need to make a decision mid-run on the legacy agent path, you can type
into the Claude Code session and the supervisor will respond. On the workflow
path, the recommended approach is to:

1. Let the current phase complete.
2. Edit the ticket file directly — update the `agents:` map or add a comment.
3. Re-invoke the workflow; it will pick up from the last non-done phase.

---

## Crash-Resume Mechanism

If a workflow script crashes or is interrupted mid-run (e.g. network error,
session timeout, manual `Ctrl-C`), the ticket file's frontmatter `agents:`
map records which phases have already signed off.

### How resume works

Re-running `/build-feature <epic>` or `/build-ticket <ticket>` with the same
epic or ticket path will:

1. Read the `agents:` map from the ticket frontmatter.
2. Skip any phase whose status is already `signed_off` or `not_needed`.
3. Continue from the first phase whose status is `needed`.

The ticket file is the **durable state** — the workflow script is stateless.
As long as each completed phase agent updated the ticket frontmatter before
the crash, the resume is lossless.

### Recovery if a phase was interrupted mid-write

If a phase agent crashed after starting its work but before completing the
sign-off write, the ticket file may show `needed` for a phase that was
partially completed. In that case:

1. Inspect the phase agent's work (check `git diff` for any incomplete files).
2. Either revert the partial changes (`git checkout -- <file>`) and let the
   phase re-run cleanly, or manually complete the work and set the phase
   status to `signed_off` in the ticket frontmatter.
3. Re-invoke the workflow.

See `docs/how-to/drive-epic-manually.md` for manual recovery steps.

---

## Removed Legacy Agents (AC ACD-1100a-3)

The following seven agents were removed as part of EPIC-AcPipelineConsolidation.
No workflow script, skill file, or command template may dispatch these agent IDs
as spawn targets:

| Removed Agent ID | Replacement |
|---|---|
| `create-ticket` | `/create-ticket` workflow command (`create-ticket.js`) |
| `create-ticket-v2` | `/create-ticket` workflow command (`create-ticket.js`) |
| `business-analyst` | `business-analyst-v3` |
| `business-analyst-v2` | `business-analyst-v3` |
| `create-epic` | `/plan-feature` workflow command (`plan-feature.js`) |
| `refinement` | Inlined into `create-ticket.js` workflow |
| `it-po` (v1/v2) | `it-po-v3` |

These IDs must not appear as `subagent_type`, `agentType`, `spawn_allowlist`,
or `spawned_by` values in any file under `templates/skills/`, `templates/commands/`,
`scripts/workflows/`, or `config/agent_registry.json`. Any reference found is a
dispatch-target violation and must be removed.

---

## Cross-References

- `docs/how-to/configure-workflow-allowlist.md` — how to configure the
  `allowedTools` allowlist in `settings.json` to reduce permission prompts
  during workflow execution.
- `docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md` — the
  architectural decision that introduced the workflow scripts and the
  depth-1 dispatch model.
- `templates/workflows-js/` — the workflow script source files.
- `scripts/workflows/plan-feature.js` — the `/plan-feature` workflow script
  (AC authoring pipeline); replaced the legacy `/create-ac` command in v2.0.
- `templates/agents/onboard.md` — the onboarding wizard, which checks the
  Claude Code version at Step 1b and warns if below 2.1.154.
