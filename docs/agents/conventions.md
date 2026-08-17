---
title: "Agent Authoring Conventions"
description: "Operational how-to for authoring agents: frontmatter schema, file layout, visibility classes (including the confirmation-gate rules), tool allowlists, patterns, and sign-off lifecycle."
type: reference
status: active
created: 2026-05-07
last_updated: 2026-06-17
components:
  - "infrastructure"
related_docs:
  - "docs/architecture/adrs/ADR-033-agent-model-tiers.md"
  - "templates/skills/signoff/SKILL.md"
  - "tickets/09_done/EPIC-AgentFoundation/Master_Plan.md"
  - "tickets/09_done/EPIC-AgentFoundation/done/02_reference_agent_trade_report_runner.md"
related_code:
  - ".claude/agents/"
  - ".claude/skills/"
  - ".claude/commands/"
---

# Agent Authoring Conventions

This document is the operational how-to for writing a new agent. It translates the policy in [`ADR-006: Agent Model Tiers and Gatekeeper Escalation`](../architecture/adrs/ADR-033-agent-model-tiers.md) into actionable rules so a fresh contributor can author a correct agent without re-deriving the policy from first principles.

If you only have ten minutes, read this file. If you need to know *why* a rule exists, follow the cross-link to the matching ADR section.

The sections below cover the conventions surfaces and the deployed-agent registry:

1. [Frontmatter Schema](#1-frontmatter-schema)
2. [File Layout](#2-file-layout)
3. [Visibility Classes](#3-visibility-classes)
4. [Tool Allowlists](#4-tool-allowlists)
5. [Patterns](#5-patterns)
6. [Gatekeeper Escalation Registry](#6-gatekeeper-escalation-registry)
7. [Sign-off Lifecycle](#7-sign-off-lifecycle)

---

## 1. Frontmatter Schema

Every agent file at `.claude/agents/<agent>.md` opens with a YAML frontmatter block that pins four fields. All four are **required**.

| Field | Type | Allowed values | Notes |
|---|---|---|---|
| `name` | string | kebab-case identifier matching the filename stem | Must be unique across `.claude/agents/`. See §2 for the slash-command-collision rule. |
| `description` | string (multi-line allowed) | free text, but must follow one of the three visibility-class shapes in §3 | This field drives auto-trigger reliability. Vague descriptions fail to fire. |
| `model` | enum | `haiku`, `sonnet`, or `opus` | One of three tiers. See [ADR-006 §2.1](../architecture/adrs/ADR-033-agent-model-tiers.md#21-three-tier-model-ladder). Default is `sonnet`; reach for `haiku` only when the work is fully mechanical, and for `opus` only when the agent is the escalation target of a Sonnet gatekeeper. |
| `tools` | comma-separated list | tier-floor minimums in §4 | An **empty** `tools:` value means *no tools* — not "all default tools". The Haiku floor is `Bash, Read`; never leave the field blank. |

### 1.1 Allowed `model:` values cross-referenced to ADR-006

| Value | Tier | When to pick it |
|---|---|---|
| `haiku` | Haiku — see [ADR-006 §2.1](../architecture/adrs/ADR-033-agent-model-tiers.md#21-three-tier-model-ladder) | Mechanical, deterministic procedures with no judgement. Inputs map to outputs by a fixed recipe. |
| `sonnet` | Sonnet — see [ADR-006 §2.1](../architecture/adrs/ADR-033-agent-model-tiers.md#21-three-tier-model-ladder) | Standard SWE work bounded by clear patterns. The default for nearly every agent. |
| `opus` | Opus — see [ADR-006 §2.1](../architecture/adrs/ADR-033-agent-model-tiers.md#21-three-tier-model-ladder) | Novel synthesis or escalation. Only valid as the spawn target of a Sonnet gatekeeper; never picked at the agent's own frontmatter level outside that role. |

### 1.2 Copy-pasteable example

```yaml
---
name: my-agent
description: |
  One-paragraph description following one of the three visibility-class shapes
  in §3 of docs/agents/conventions.md.
  Use when: <concrete trigger 1>; <concrete trigger 2>.
model: sonnet
tools: Bash, Read
---

System prompt body goes here.
```

### 1.3 Empty-`tools:` rule

> An empty `tools:` value means **no tools**, not "all default tools".

A Haiku agent that omits `tools:` or sets it to an empty list cannot Read or Bash and is useless. The Haiku floor is `Bash, Read`. The Sonnet floor is `Bash, Read, Write, Edit`. See §4 for the full tier table and the strict-research-delegation rule. The rationale is in [ADR-006 §2.6](../architecture/adrs/ADR-033-agent-model-tiers.md#26-tool-allowlist--strict-research-delegation).

---

## 2. File Layout

An agent is up to **three** files, in three folders:

| Path | Status | Purpose |
|---|---|---|
| `.claude/agents/<agent>.md` | always | The agent itself: frontmatter + system prompt. The only file that pins `model:` and `tools:`. |
| `.claude/commands/<command>.md` | user-facing only | The canonical workflow body that runs when `/<command>` is typed. Surfaced as a slash command directly by Claude Code. Also loaded by Skill-Wrapper and Multi-Skill Dispatcher agents end-to-end. |
| `docs/agents/<family>/<agent>.md` | always | Reference doc: when-to-use, inputs, outputs, escalation behaviour. The discoverable entry point a new contributor opens to learn what the agent does. |

**Slash command surface.** Workflow files are built directly to `.claude/commands/` where Claude Code discovers them as slash commands. Each user-facing slash command corresponds to a workflow file at `.claude/commands/<command>.md`; the workflow body **is** the slash-command body.

Two consequences for agent authors:

1. **Do NOT hand-edit files in `.claude/commands/`.** They are build outputs (gitignored) and will be overwritten by `build.py`. Add the slash-command surface by creating a workflow template at `leafcutter/templates/workflows/<command>.md`.
2. **Auto-trigger via agent description, explicit invocation via slash command.** Prose intent matching ("how are trades doing?") routes to the agent via its `description` field and runs the agent's pinned model. Explicit `/<command>` resolves to the workflow body and runs on the user's current session model. The two surfaces are separate; the agent and the workflow are co-canonical and load each other where appropriate (the agent loads the workflow by path; the workflow stays untouched).

The wrapped skill or workflow stays at `.claude/skills/<skill>/SKILL.md` or `.claude/commands/<workflow>.md` and is **not modified** by the wrapper agent's body. The workflow's frontmatter `description:` may be neutered to avoid duplicate auto-trigger surface (see `.claude/commands/trade-report.md` for the canonical example: description names the agent that owns the workflow). See [ADR-006 Operational consequences](../architecture/adrs/ADR-033-agent-model-tiers.md#4-consequences) ("Skill-Wrapper agents do not modify the wrapped skill").

### 2.1 Canonical family directories

`docs/agents/` is partitioned into **families** by purpose:

| Family | Purpose | Populated by |
|---|---|---|
| `coding/` | Coding agents — review, refactoring, research, dispatching, etc. | [EPIC-CodingAgents] |
| `analytics/` | Analytics and reporting agents — `reporting-agent` (Multi-Skill Dispatcher serving `/trade-report`, `/pipeline-health`, `/project-report`). | [EPIC-SkillRunnerAgents] |
| `ops/` | Operations agents — `prod-puller`, `docker-cleanup`, `fetch-prod-logs`. | [EPIC-SkillRunnerAgents] |

To add a **new family directory** (e.g. `docs/agents/research/`):

1. Open a PR that adds the directory plus at least one occupant.
2. Update `docs/agents/README.md` (the family index, ticket 03) to list the new family with a one-line description of when it applies.
3. Cite the gap that motivated the new family (the existing three did not cover this purpose) in the PR description.

Do not create empty family directories speculatively.

### 2.2 Slash-command vs agent-name collision rule

The slash command in `.claude/commands/<command>.md` is what the user types; the agent in `.claude/agents/<agent>.md` is what runs. Their identifiers are **distinct namespaces**, and the convention is to keep them visibly different so the user-facing surface stays stable when the agent gets renamed or rewritten.

#### 2.2a Single-skill Skill Wrappers — `-runner` suffix

Skill-Wrapper agents take a `-runner` suffix so the slash command can keep the bare verb:

- Slash command `/pipeline-health` → invokes agent `pipeline-health-runner` (planned by [EPIC-SkillRunnerAgents]).
- An agent named `pipeline-health` paired with command `/pipeline-health` is **forbidden**: the names collide and any future tooling that scans both directories has no way to disambiguate. The suffix is the disambiguator.
- For non-wrapper agents that have no slash-command surface (internal agents, gatekeepers spawned only by other agents), pick whatever bare name is clearest; collision is impossible because there is no command.

#### 2.2b Multi-Skill Dispatchers — role-based noun name

Multi-Skill Dispatcher agents use a **role-based noun** name (e.g. `reporting-agent`, future `coding-agent`, `ops-agent`). A single dispatcher serves multiple slash commands, so neither the bare verb nor the `-runner` suffix applies:

- Slash command `/trade-report` → invokes agent `reporting-agent`.
- Slash command `/project-report` → also invokes `reporting-agent` (once that workflow lands in [EPIC-SkillRunnerAgents]).
- The role noun is the disambiguator: it signals the agent's scope (analytics reporting, coding tasks, ops tasks) rather than the specific command it happens to be serving today.

This convention is also called out in [ADR-006 Operational consequences](../architecture/adrs/ADR-033-agent-model-tiers.md#4-consequences).

---

## 3. Visibility Classes

Every agent's `description` field declares **exactly one** of three classes. The class shapes the field's wording and controls whether the parent model auto-delegates to the agent.

The full policy is in [ADR-006 §2.5](../architecture/adrs/ADR-033-agent-model-tiers.md#25-visibility-classes); this section translates it into one ready-to-paste example per class.

### 3.1 User-facing

Auto-triggers when the user's intent matches. Description **must** include one or more concrete when-to-use examples — vague descriptions ("Reviews code") fail to fire.

```yaml
description: |
  Generates the live trade execution report from pnl_trades_v2.
  Use when: user types /trade-report; asks "how are trades doing?";
  or requests a profitability / open-positions / system-health snapshot.
```

### 3.2 Confirmation-gated

User-facing for the *gate*, but waits for an explicit yes before performing the destructive action. Description **must** name both the destructive action and the gate phrasing.

```yaml
description: |
  Drafts the commit message and stages the diff, then asks
  "OK to commit?" before running git commit. Never commits without
  an explicit yes. Use when: user types /commit; or asks to commit
  the current change.
```

The confirmation gate applies *once*, at the boundary where the destructive action commits. Sub-agents below the gate (e.g. a `commit-runner` spawning `precommit-fixer`) do not re-prompt; the gate covers the entire spawn tree below it. See [ADR-006 §2.8](../architecture/adrs/ADR-033-agent-model-tiers.md#28-clarifications-on-edge-cases).

#### 3.2.1 A confirmation-gated agent must never be *spawned* to serve an interactive action

The confirmation gate requires the **human user's own** same-turn reply. A relayed "yes" — one passed in by a coordinator, supervisor, or any parent agent — does not satisfy the gate and the agent will (correctly) refuse it. A spawned sub-agent has **no direct human channel**: the user only ever replies to the top-level session, never to a sub-agent. Therefore:

- **Do NOT** dispatch `commit`, `pull-request`, or any confirmation-gated agent via the `Agent` tool to perform an interactive (non-supervised) commit/push/PR. The sub-agent waits for a confirmation it can never receive, and the action deadlocks.
- When the human authorizes the action **directly in the conversation**, the top-level session performs it directly — `COMMIT_AGENT_MODE=1 git commit …` for commits (the env flag satisfies the `enforce_commit_delegation` hook), `git push` + `gh pr create` for PRs.
- Gated agents are spawned **only** in the supervised pipeline path, where they auto-authorize on the `ticket_path` branch (see [the `commit` template Step 3](git/commit.md) and [building-epics §5.0](../../templates/skills/building-epics/SKILL.md)). That is the *inverse* of the [§3.2 downstream rule](#32-confirmation-gated): the gate is satisfied upstream by the `/build-feature` dispatch and the pre-commit gates, not by a per-commit prompt.

This is the same deadlock class as the supervised-commit `question`-status hang fixed on 2026-06-17: a gate whose answer cannot reach the agent is unsatisfiable, not merely slow.

### 3.3 Internal

Never auto-triggers. Only spawned by other agents. Description **must** end with the literal suffix `(internal — invoked by parent agents only)`.

```yaml
description: |
  Deep architectural review for cross-cutting changes. Spawned by
  architect-review when the diff exceeds the small-case bar
  (internal — invoked by parent agents only).
```

### 3.4 Auto-trigger reliability rule

> Auto-trigger reliability is **driven entirely by the `description` field**. A vague description ("Reviews code") fails to fire; a description with concrete when-to-use examples fires reliably.

There is no automated lint at this layer — the description *is* the auto-trigger contract. Test by reading the description aloud: if you cannot point at the verbs and nouns that match a user request, the description is too vague.

### 3.5 Hybrids forbidden

> An agent is **exactly one** class — never two.

A user-facing description on an internal-only agent will misfire as auto-trigger noise. An internal-suffixed description on a user-facing agent will silently never fire. When a description could read as more than one class, the agent file must pick one and reword. See [ADR-006 §2.5](../architecture/adrs/ADR-033-agent-model-tiers.md#25-visibility-classes) and the hybrid-ambiguity clarification in [§2.8](../architecture/adrs/ADR-033-agent-model-tiers.md#28-clarifications-on-edge-cases).

---

## 4. Tool Allowlists

Each spawned agent's `tools:` is the **minimum** needed to do its job. The full rationale (context isolation, payload size, cost) is in [ADR-006 §2.6](../architecture/adrs/ADR-033-agent-model-tiers.md#26-tool-allowlist--strict-research-delegation); the per-tier floors are below.

### 4.1 Tier-floor minimums

| Tier | Minimum `tools:` | Add-on if applicable |
|---|---|---|
| Haiku | `Bash, Read` | — |
| Sonnet | `Bash, Read, Write, Edit` | `+ Agent` if the agent spawns sub-agents |
| Opus | `Bash, Read, Write, Edit` (when invoked as the spawn target of a gatekeeper) | `+ Agent` if it spawns further sub-agents |

`*` (all tools) is **never** allowed unless the agent file carries an inline comment block citing this section and ADR-006 as justification.

### 4.2 Strict research-delegation rule

> The following tools are **removed** from every non-research agent: `Grep`, `Glob`, all `mcp__jcodemunch__*`, all `mcp__plugin_serena_serena__*`, all `mcp__plugin_context7_context7__*`.

All cross-cutting search goes through a single `research-agent` (defined in [EPIC-CodingAgents]). It keeps the full search toolkit and returns curated findings to its caller. Spawned agents do not reproduce the parent's research surface inside their own context — they ask the research-agent and receive a structured answer.

Why: a spawned agent with `Grep` + `Glob` reproduces the parent's research surface inside its own context, balloons return payloads, and undermines the cost rationale for spawning in the first place.

### 4.3 Carve-outs

There are exactly **two** carve-outs from §4.2:

1. **The user-facing Opus session.** It is the project's interactive surface, not a spawned agent — it keeps `Grep`, `Glob`, `jcodemunch`, `serena`, and `context7` because the user steers it directly. The strict-research rule applies only to *spawned* agents under `.claude/agents/`.
2. **`research-agent` itself.** It keeps everything because its whole job is research; otherwise the rule would be self-defeating.

A new author who reads §4.2 and wonders why their interactive Opus session still has `Grep` is the most likely point of confusion. The answer is here: the rule applies to spawned agents, not to the user-facing session. See [ADR-006 §2.6](../architecture/adrs/ADR-033-agent-model-tiers.md#26-tool-allowlist--strict-research-delegation).

### 4.4 Tier-floor exception comment-justification rule

If a Haiku agent legitimately needs a tool above its tier floor (e.g. `Edit` for a mechanical-but-write-side task), the agent file **must** carry a comment block at the top of the system-prompt body that documents the exception:

```markdown
<!--
TOOL EXCEPTION: this Haiku agent uses Edit (above the Haiku floor of Bash, Read)
because <one-line reason>. See docs/agents/conventions.md §4.4 and
docs/architecture/adrs/ADR-033-agent-model-tiers.md §2.6.
-->
```

The same rule applies in reverse: a Sonnet agent that drops *below* the Sonnet floor (omits `Write` and `Edit` because it is read-only) does not need a justification — narrowing the allowlist is always allowed and indeed encouraged. Only **widening** above tier floor requires the comment block. Tier-floor *drift across tiers* without justification is a review-blocker.

---

## 5. Patterns

Three named patterns cover every agent in the planned epics: **Skill Wrapper**, **Gatekeeper Escalation**, and **Multi-Skill Dispatcher**. All three are defined in [ADR-006 §2.2](../architecture/adrs/ADR-033-agent-model-tiers.md#22-pattern-a--skill-wrapper), [§2.3](../architecture/adrs/ADR-033-agent-model-tiers.md#23-pattern-b--gatekeeper-escalation), and [§2.4](../architecture/adrs/ADR-033-agent-model-tiers.md#24-pattern-c--multi-skill-dispatcher); this section translates each into authoring rules.

### 5.1 Skill Wrapper

A Skill Wrapper is a thin agent file (~10 lines body) that pins a model, declares a minimum tool allowlist, and executes one canonical skill or workflow. The wrapped skill stays canonical and untouched — the wrapper does not reshape it.

Every Skill Wrapper carries the **canonical anomaly clause verbatim** in its system prompt. The clause text is below; copy it byte-for-byte. Compliance can be grep-checked across `.claude/agents/`.

> After completing your primary task, append an `## Anomalies` section. Flag anything unusual that warrants deeper interpretation: unexpected values, unfamiliar patterns, results that contradict prior runs, or signals suggesting a different agent should pick up the trace. The section is empty when nothing is unusual — do not invent anomalies. Phrase findings so an Opus session can pick them up for follow-up without re-running your work.

This file is the single source of truth for the clause text. Wrappers copy it; they do not paraphrase. A future `check_agents.py` guard could grep for the canonical wording.

#### 5.1.1 Worked example — `log-fetch-runner` (hypothetical single-skill Haiku wrapper)

This is a short hypothetical that keeps the Skill Wrapper pattern grounded with a concrete single-skill agent. For a fully-annotated example of a multi-skill agent that dispatches across several slash commands and escalates on anomaly density, see **§5.2.1** (the `reporting-agent` dispatcher).

```yaml
---
name: log-fetch-runner
description: |
  Fetches recent worker, SQL, and console logs from the production host.
  Use when: user types /fetch-prod-logs, asks "show me the logs",
  or needs a log tail from brain.vierhenze.de.
model: haiku
tools: Bash, Read
---

Load and execute `.claude/commands/fetch-prod-logs.md` end-to-end.

After completing your primary task, append an `## Anomalies` section. Flag anything unusual that warrants deeper interpretation: unexpected values, unfamiliar patterns, results that contradict prior runs, or signals suggesting a different agent should pick up the trace. The section is empty when nothing is unusual — do not invent anomalies. Phrase findings so an Opus session can pick them up for follow-up without re-running your work.
```

**Annotations:**

- `name: log-fetch-runner` — kebab-case, matches the filename stem. The `-runner` suffix avoids collision with the slash command `/fetch-prod-logs` per §2.2a. The slash command keeps the bare verb; the agent gets the disambiguating suffix.
- `description: …Use when: …` — user-facing visibility class (§3.1). Three concrete when-to-use phrasings so the parent model auto-triggers reliably.
- `model: haiku` — log fetching is a fully mechanical procedure (SSH → docker exec → tail); no judgement is required. Textbook Haiku per [ADR-006 §2.1](../architecture/adrs/ADR-033-agent-model-tiers.md#21-three-tier-model-ladder).
- `tools: Bash, Read` — the Haiku floor. Search tools removed per §4.2; `Agent` omitted because this wrapper never spawns sub-agents.
- **System prompt body** — two sentences plus the canonical anomaly clause verbatim.

> **Note:** `/trade-report` is served by the `reporting-agent` Multi-Skill Dispatcher (§5.2), not by a single-skill Skill Wrapper. Refer to §5.2.1 for that fully-annotated example.

### 5.2 Multi-Skill Dispatcher

A Multi-Skill Dispatcher is a **single Sonnet agent** that routes multiple slash commands to their matching workflows via a dispatch table, applies the canonical anomaly clause uniformly, and — when anomaly density is high — spawns an Opus sub-agent inline rather than waiting for the user-facing session to decide. This collapses the "one Skill Wrapper per command" approach into a single agent file per domain.

See [ADR-006 §2.4](../architecture/adrs/ADR-033-agent-model-tiers.md#24-pattern-c--multi-skill-dispatcher) for the upstream definition and rationale.

Authoring rules:

- `model: sonnet` always. The Opus sub-agent is spawned inline; it is not a separate persistent agent file.
- `tools: Bash, Read, Agent` always — `Agent` is required because the dispatcher may spawn Opus inline.
- The system prompt opens with a **dispatch table** (markdown table: `Command | Workflow`). Planned-but-not-yet-shipped rows are listed with a *(planned)* annotation so authors know where to add when a new workflow lands.
- The system prompt carries the **canonical anomaly clause verbatim** (§5.1 text). Compliance can be grep-checked.
- **Anomaly-density gate:** when a run produces ≥3 distinct anomaly classes, OR any single anomaly that contradicts a structural assumption (e.g. a strategy underperforms its baseline by >50% in one run; a risk-budget cap is breached unexpectedly), spawn an Opus sub-agent inline via the `Agent` tool (`subagent_type: general-purpose`, `model: opus`) and emit **both** `## Anomalies` and `## Escalation` in the same run. Below the density threshold, emit only `## Anomalies`.
- The system prompt **must** include: "Do not spawn sub-agents for reasons other than anomaly-density escalation." and "Do not modify the wrapped workflow files."
- The dispatcher's `description` field must be user-facing (§3.1) and name every command it serves today; planned future commands may be mentioned parenthetically.

#### 5.2.1 Worked example — `reporting-agent` (first Multi-Skill Dispatcher, shipped by [ticket 02](../../tickets/00_inbox/epics/EPIC-AgentFoundation/02_reference_agent_trade_report_runner.md))

```yaml
---
name: reporting-agent
description: |
  Multi-skill analytics dispatcher. Generates structured reports on live
  trading execution, pipeline health, and project activity.
  Use when: user types /trade-report, asks "how are trades doing?",
  or requests a profitability / open-positions / system-health snapshot.
  Also dispatches /pipeline-health and /project-report once those
  workflows land in EPIC-SkillRunnerAgents.
model: sonnet
tools: Bash, Read, Agent
---

## Dispatch Table

| Command | Workflow |
|---|---|
| `/trade-report` | `.claude/commands/trade-report.md` |
| `/pipeline-health` | `.claude/commands/pipeline-health.md` *(planned — EPIC-SkillRunnerAgents)* |
| `/project-report` | `.claude/commands/project-report.md` *(planned — EPIC-SkillRunnerAgents)* |

<!-- To extend: add a row when EPIC-SkillRunnerAgents introduces a new report skill. -->

Resolve the inbound command against the table. Load and execute the matching workflow end-to-end. Return all standard report sections defined in that workflow.

After completing your primary task, append an `## Anomalies` section. Flag anything unusual that warrants deeper interpretation: unexpected values, unfamiliar patterns, results that contradict prior runs, or signals suggesting a different agent should pick up the trace. The section is empty when nothing is unusual — do not invent anomalies. Phrase findings so an Opus session can pick them up for follow-up without re-running your work.

### Anomaly-density gate

When a run produces **≥3 distinct anomaly classes**, OR **any single anomaly that contradicts a structural assumption** (e.g. a strategy underperforms its baseline by >50% in one run; a risk-budget cap is breached unexpectedly), the density threshold is met. Spawn an Opus sub-agent inline via the `Agent` tool (`subagent_type: general-purpose`, `model: opus`) and emit **both** `## Anomalies` (your findings) and `## Escalation` (routing decision plus Opus interpretation) in the same run. Below the threshold, emit only `## Anomalies`.

**Trade-report-specific anomaly examples:**

- Actual win rate diverging from strategy-average win rate by more than 20 percentage points (model drift or regime change).
- Open-position count or capital exposure exceeding configured caps (risk-budget breach).
- A `strategy_id` deployed unusually frequently versus prior runs (strategy concentration).
- Query 1A–1J failures that are not a "fresh deploy / no data" case — distinguish "no data" (empty `pnl_trades_v2` on a fresh deploy: legitimate, not anomalous) from "data missing unexpectedly".
- Strong long-only or short-only skew that contradicts the strategy mix.

Do not modify `.claude/commands/trade-report.md` or any other workflow file.
Do not spawn sub-agents for reasons other than anomaly-density escalation.
```

**Annotations:**

- `name: reporting-agent` — role-based noun per §2.2b. Not `/trade-report-runner` — the agent serves multiple commands, so the bare verb or `-runner` suffix would misrepresent its scope.
- `description: …Use when: …` — user-facing (§3.1). Names today's command (`/trade-report`) plus planned future commands parenthetically so the description remains accurate as the dispatch table grows.
- `model: sonnet` — structured data extraction with inline escalation gate; no novel synthesis at the dispatcher level. Not Haiku (the escalation gate requires light judgement). Not Opus (the dispatcher itself does no synthesis — Opus is spawned only when the density gate fires).
- `tools: Bash, Read, Agent` — `Agent` is required for the inline Opus spawn. Search tools (`Grep`, `Glob`, `jcodemunch`, `serena`, `context7`) are **removed** per the strict-research-delegation rule (§4.2): every file the workflows touch is named explicitly.
- **Dispatch table** — the first block in the system prompt. Planned rows are marked *(planned)* so authors can see where to add without guessing.
- **Anomaly clause** — copied verbatim from §5.1. Grep-checkable.
- **Density gate** — when the threshold fires, `## Escalation` is emitted alongside `## Anomalies`; this is the explicit exception to the no-fusion rule (§5.5, [ADR-006 §2.8](../architecture/adrs/ADR-033-agent-model-tiers.md#28-clarifications-on-edge-cases)).

### 5.3 Gatekeeper Escalation

A Gatekeeper agent pins **Sonnet** and decides "is this small or big?" before doing any work. The small case it handles inline. The big case it routes to a sub-agent pinned at Opus, spawned via the `Agent` tool. Both branches end with a mandatory `## Escalation` section in the agent's output that records the routing decision and reason — even when no escalation occurred (for example: `not escalated: change is local to one file`).

Authoring rules:

- The agent's `model:` is `sonnet`. The Opus sub-agent is a separate file (`<gatekeeper>-deep.md`) with `model: opus` and the internal visibility class (§3.3).
- The gatekeeper's `tools:` includes `Agent` (so it can spawn) plus the Sonnet floor.
- The system prompt **must** end with: "Whichever branch fires, append `## Escalation` to your output naming the chosen branch and the one-line reason. Never skip this section."
- Escalation rate is observable via the `## Escalation` log lines. Sustained rates above 50% mean the gatekeeper is on the wrong tier and the agent should be revisited per [ADR-006 §6](../architecture/adrs/ADR-033-agent-model-tiers.md#6-review-criteria). For the Multi-Skill Dispatcher specifically, the density-gate trip rate review criterion is in [ADR-006 §6](../architecture/adrs/ADR-033-agent-model-tiers.md#6-review-criteria) (>25% trigger rate).

The full worked example (`architect-review`) is in [ADR-006 §2.3](../architecture/adrs/ADR-033-agent-model-tiers.md#23-pattern-b--gatekeeper-escalation); [EPIC-CodingAgents] will ship the agent file. For a complete inventory of every deployed gatekeeper agent — including Opus target type (separate file vs inline spawn) and escalation trigger — see [§6 Gatekeeper Escalation Registry](#6-gatekeeper-escalation-registry) below.

### 5.4 Nesting depth — soft cap of 3

A spawned agent may itself spawn sub-agents up to **depth 3** below the user-facing session:

- Depth 0: user-facing session.
- Depth 1: agent the session spawns.
- Depth 2: sub-agent that depth-1 agent spawns.
- Depth 3: leaf agent at the bottom.

Beyond depth 3, the parent agent **should refuse to spawn** unless its `## Escalation` section explicitly justifies the additional layer with a warning line of the form:

```
WARNING: spawned at depth N (>3). Reason: <one-line>.
```

This is a *soft* cap — refusal is a SHOULD, not a MUST — to allow legitimate cases (e.g. a `research-agent` parallelising sub-research-agents). Telemetry on these warnings drives the future hard-cap decision. See [ADR-006 §2.7](../architecture/adrs/ADR-033-agent-model-tiers.md#27-nesting-depth--soft-cap-of-3).

### 5.5 Anomaly versus escalation

The two log sections are **never fused** in Skill Wrappers and Gatekeeper agents:

- `## Anomalies` is for Skill Wrappers — output annotations flagging interesting findings. The wrapper does not auto-spawn on an anomaly; the user-facing session decides whether to spawn an Opus interpreter.
- `## Escalation` is for Gatekeepers — routing decisions logged on every run, whether or not escalation actually fired.

A Skill Wrapper does not emit `## Escalation`; a Gatekeeper does not emit `## Anomalies`. The **Multi-Skill Dispatcher** (§5.2) is the explicit exception: when its anomaly-density gate trips, it emits both sections in the same run. See [ADR-006 §2.8](../architecture/adrs/ADR-033-agent-model-tiers.md#28-clarifications-on-edge-cases).

---

## 6. Gatekeeper Escalation Registry

This section is the single-source-of-truth inventory of every deployed Sonnet→Opus gatekeeper agent in this project. Each row names the Sonnet gatekeeper, its Opus escalation target, whether that target is a **separate named agent file** or an **inline spawn** (anonymous `general-purpose` Opus agent spawned via the `Agent` tool), and the one-line trigger that causes escalation.

For authoring rules that apply to all gatekeepers, see [§5.3 Gatekeeper Escalation](#53-gatekeeper-escalation). For the upstream policy and pattern definition, see [ADR-006 §2.3](../architecture/adrs/ADR-033-agent-model-tiers.md#23-pattern-b--gatekeeper-escalation).

### 6.1 Registry Table

| Sonnet gatekeeper | Agent file | Opus target | Opus as | Escalation trigger |
|---|---|---|---|---|
| `architect-review` | `.claude/agents/architect-review.md` | `.claude/agents/architect-review-deep.md` | separate file | Blast radius exceeds small-case rubric: > 5 affected files, ≥ 3 components, cross-module boundary, or any always-large trigger fires (Alembic migration, hypertable change, public API change, ADR contract change). |
| `conflict-resolver` | `.claude/agents/conflict-resolver.md` | `.claude/agents/conflict-resolver-deep.md` | separate file | Any conflict hunk is classified as structural: function-signature diff, same logic-block rewritten on both branches, file moved/renamed on one branch, incompatible abstractions at the same call site, or cross-cutting rename. |
| `prod-deploy` | `.claude/agents/prod-deploy.md` | — (anonymous Opus) | inline spawn | Post-deploy smoke check output is ambiguous, or log content contains an unfamiliar error class that cannot be classified as "accept", "hold for inspection", or "rollback recommended" by Sonnet inline. |
| `pr-reviewer` | `.claude/agents/pr-reviewer.md` | — (anonymous Opus) | inline spawn | Medium-confidence finding count exceeds 3; Opus is asked to promote or drop each medium finding. |

### 6.2 Maintenance Rule

When a new gatekeeper agent ships, its author **must** add a row to the table above in the same PR that introduces the agent file. The ticket that introduces the gatekeeper should cite this section in its acceptance criteria.

When a gatekeeper's escalation trigger or Opus target changes (e.g. a `-deep` agent is added for an agent that previously used inline spawn), the row must be updated in the same PR that changes the agent file. This table does not auto-generate — it is maintained manually and is the authoritative reference.

---

## 7. Sign-off Lifecycle

> **Rule**: Any agent invoked with `ticket_path` MUST load
> `.claude/skills/signoff/SKILL.md` and follow the atomic sign-off recipe on
> completion — whether the phase succeeded or failed.

This rule applies to every phase agent: `python-coder`, `sql-coder`,
`architect-review`, `pr-reviewer`, `commit`, `pull-request`, `status-checker`,
`test-runner`, `documentation-expert`, `database-agent`, `worktree-agent`,
`research-agent`, and all SQL specialists. It does NOT apply to the supervisor
agents (`epic-supervisor`, `ticket-supervisor`) — they are not phase agents and
have no row in the `agents:` map. It does NOT apply to `brainstorm-lead` or
`brainstorm-worker` — they are read-only analysts with no ticket-mutation role.

### 7.1 Status enum (canonical location)

The status enum `{not_needed, needed, signed_off, failed}` lives exclusively in
`.claude/skills/signoff/SKILL.md §1`. That file is the **single source of
truth**. Do not duplicate the enum in agent prompts, ticket templates, scripts,
or any other document. Any change to the enum (adding a new value, deprecating
one) is an edit to that skill file and that file alone.

### 7.2 Atomic sign-off recipe

On completing a phase, the agent must update two surfaces atomically:

1. Frontmatter `agents:` line: `<agent-name>: needed` → `<agent-name>: signed_off`
   (or `failed` on the failure path).
2. `## Sign-offs` checklist line: `- [ ] <agent-name>` → `- [x] <agent-name> — YYYY-MM-DD HH:MM`.

Both edits must succeed. If the second edit fails after the first succeeds, the
agent MUST revert the first edit before returning. The complete recipe, edge
cases, and failure path are in `.claude/skills/signoff/SKILL.md §2–§4`.

### 7.3 Parity guard

The pre-commit guard `scripts/commit_guardian/check_ticket_signoff_parity.py`
validates that `agents:` and `## Sign-offs` are in sync. It runs in warn-only
mode until the legacy grandfathering migration (EPIC-AgentSupervisor ticket 11)
is complete, then flips to `--enforce`.

### 7.4 Decision record

The canonical status enum, the atomic sign-off recipe, and the parity rules the
pre-commit guard enforces are specified in the
[`signoff` skill](../../templates/skills/signoff/SKILL.md).

---

## Compatibility

This document is the second-most-linked file in the agent documentation tree (after `docs/agents/README.md`, ticket 03). It is cited by every reference doc under `docs/agents/coding/`, `docs/agents/analytics/`, and `docs/agents/ops/` in the downstream epics.

> **Revisions to this document force agent-frontmatter migration** once tickets 02 + 03 and the downstream epics ([EPIC-CodingAgents], [EPIC-SkillRunnerAgents]) adopt these conventions.

Specifically, any edit that changes:

- the allowed `model:` values,
- the per-tier `tools:` floors or the strict-research-delegation list,
- the canonical anomaly clause text in §5.1,
- the visibility-class shapes in §3,
- or the slash-command-collision rule in §2.2,

must ship with a migration plan that updates every existing agent file. The clause text in §5.1 is grep-checkable; the other rules require a manual sweep. Flag any such edit in the PR description with the list of agent files that need updating, and prefer additive changes (new optional fields, new patterns) over breaking changes whenever possible.

[EPIC-CodingAgents]: ../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md
[EPIC-SkillRunnerAgents]: ../../tickets/00_inbox/epics/EPIC-SkillRunnerAgents/Master_Plan.md
