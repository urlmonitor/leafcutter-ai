---
title: "Precommit-Autofix Routing Reference"
type: reference
status: active
created: 2026-05-07
last_updated: 2026-05-07
components:
  - "infrastructure"
related_docs:
  - "docs/agents/README.md"
  - "docs/agents/conventions.md"
  - "docs/architecture/adrs/ADR-006-agent-model-tiers.md"
---

# Precommit-Autofix Routing Reference

This document is the authoritative hook-by-hook routing audit for `.claude/precommit-autofix.json`.
It was produced by ticket 10 (`tickets/09_done/EPIC-CodingAgents/10_precommit_autofix_wiring.md`).

The routing JSON is the operational source of truth — edit that file to change routing. This doc
explains *why* each hook was classified the way it was and records the verification recipe.

---

## Classification Rules

| Category | Description | Tier |
|---|---|---|
| `mechanical` | Output is deterministic given the error: add a field, fix a date, add a tag. No semantic judgment. | Haiku |
| `structural` | Requires reading surrounding code, authoring real prose, or refactoring logic. | Sonnet |
| `design` | Architectural write-up; judgment about system intent required. | Opus (via gatekeeper) |
| `investigation` | Root-cause analysis + code fix under constraints. | Opus (via smart-bug-resolver) |
| `auto` | Handled automatically by the commit guardian; no agent dispatch. | — |

---

## Hook Inventory and Classification

Audit date: 2026-05-07. Source: `.pre-commit-config.yaml` (14 active hooks, 1 commented-out).

| Hook ID | Category | Effective Model | Rationale |
|---|---|---|---|
| `check-root-files` | mechanical | haiku | Move a misplaced file into the right folder — no semantic judgment, path is in the error output. |
| `check-debug-scripts` | mechanical | haiku | Add three required metadata fields (purpose/category/owner) to a script header — fixed recipe. |
| `check-doc-frontmatter` | mechanical | haiku | Fix YAML frontmatter fields on `docs/*.md` — dates, required keys, types. Schema-driven, no prose. |
| `check-doc-links` | mechanical | haiku | Add or repair `DOC_LINKS` trace links. **Note: this hook always exits 0 (advisory-only)** — it never blocks a commit so the agent entry is a no-op in practice. Classified mechanical so that if the hook is ever promoted to blocking, routing is pre-set correctly. |
| `check-sql-dependencies` | mechanical | haiku | Add the mandatory `-- dependencies:` tag to SQL views/matviews. Fixed one-liner addition. |
| `check-docstrings` | mechanical | haiku | Add or repair Google-style docstrings to Python functions/classes. Template-driven, no design. |
| `check-infra-docs` | mechanical | haiku | Add inline comments to docker-compose/Dockerfile/init-db.sh/.env.* files. Fixed comment format. |
| `check-documentation` | structural | sonnet | Generate or update READMEs and SQL headers. Requires reading neighbouring code and writing real prose. Cannot be template-filled from the error message alone. |
| `check-complexity` | structural | sonnet | Reduce Python cognitive complexity (max CC 15). Requires extracting helpers, flattening control flow, and preserving behaviour. Pure refactoring judgment. |
| `check-sql-complexity` | structural | sonnet | Reduce SQL structural complexity (max score 50). Requires splitting CTEs, extracting views, and simplifying joins with domain knowledge. |
| `check-file-size` | structural | sonnet | Split a file that exceeds the line budget along logical boundaries without changing behaviour. Requires understanding module structure. |
| `check-folder-density` | structural | sonnet | Propose a sub-folder split when a folder exceeds 15 non-markdown files. Requires understanding existing organisational patterns. |
| `missing-adr` | design | opus (via architecture-planner) | Architectural change without an ADR. Needs a real design write-up with rationale and consequences. The `architecture-planner` agent pins `model: opus` in its frontmatter; this is intentional — ADR content is load-bearing for future decisions. **Note: `missing-adr` is a logical rule, not a named hook in `.pre-commit-config.yaml`. It handles ADR-detection logic that may be embedded in `check-documentation` or enforced via a future hook.** |
| `run-unit-tests` | investigation | opus (via smart-bug-resolver) | Failing `live_trader` unit tests. Requires hypothesis generation, root-cause analysis, and targeted fix without papering over. `smart-bug-resolver` pins `model: opus`; justified because a quick patch is exactly the failure mode this hook exists to prevent. |
| `apply-sql-changes` | auto | — | Auto-applied by the commit guardian. No agent dispatch needed or correct. |

**Commented-out hook (excluded from routing):** `run-sql-tests` — disabled because it requires a running database (30+ seconds). Run manually: `python -m pytest unit_tests/sql_functions -v`. Not included in routing JSON.

---

## Coverage Status

As of 2026-05-07:

- All 14 active hooks covered in `.claude/precommit-autofix.json`.
- Zero hooks in `.pre-commit-config.yaml` missing from routing JSON.
- One phantom rule (`missing-adr`) present in routing JSON with no matching hook ID in config — this is intentional (see table above).

---

## Wiring Status: Commit Agent (Ticket 09)

Ticket 09 (`09_commit_agent.md`) implements the `commit` agent at `.claude/agents/commit.md`.
That agent is the orchestration glue that calls `precommit-autofix` on hook failure.

**Status as of this audit (2026-05-07):** Ticket 09 is in parallel implementation. The expected
wiring contract is:

1. The `commit` agent runs `git commit`.
2. On hook failure, it invokes the `precommit-autofix` skill via the `Skill` tool or a direct
   call to the skill's procedure (reading `.claude/precommit-autofix.json` to route).
3. It retries the commit once after the fix.
4. On second failure, it surfaces the hook output to the user and stops.

When ticket 09 lands, verify the wiring by checking `.claude/agents/commit.md` for:
- Frontmatter: `model: sonnet`, `tools: Bash, Read, Edit, Write, Agent`
- System prompt references to `precommit-autofix` skill by name
- Single-retry policy documented

---

## Verification Recipe

Use these commands to reproduce the audit and catch future drift:

```bash
# 1. List all active hook IDs in .pre-commit-config.yaml
python3 -c "
import yaml, json
with open('.pre-commit-config.yaml') as f:
    config = yaml.safe_load(f)
hooks = [h['id'] for r in config['repos'] for h in r.get('hooks', [])]
with open('.claude/precommit-autofix.json') as f:
    routing = json.load(f)
routed = {r['hook_id'] for r in routing['rules']}
hook_set = set(hooks)
print('ACTIVE HOOKS:', sorted(hooks))
print('MISSING FROM ROUTING:', sorted(hook_set - routed))
print('PHANTOM RULES:', sorted(routed - hook_set))
"

# 2. Smoke-check mechanical routing (frontmatter failure)
# Stage a docs/*.md with a missing 'type' field, run git commit, observe:
#   - precommit-autofix invoked
#   - Haiku sub-agent fixes the frontmatter
#   - retry commit succeeds

# 3. Smoke-check structural routing (complexity failure)
# Stage a Python function with CC > 15, run git commit, observe:
#   - precommit-autofix invoked
#   - Sonnet sub-agent refactors
#   - diff surfaced to user
#   - retry commit succeeds (or agent stops after one retry per ticket-09 policy)
```

---

## Drift Prevention (Stretch Task)

A future lint script could fail the test suite if a hook in `.pre-commit-config.yaml` is missing
from `.claude/precommit-autofix.json`. This was flagged in the ticket as a stretch task (out of
scope for ticket 10 as a hard requirement). If added, place it in
`scripts/commit_guardian/check_routing_coverage.py` and register it as a `pre-commit` hook with
`stages: [pre-push]` to keep it out of the fast commit loop.
