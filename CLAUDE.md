# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

## Shell Convention — MANDATORY

Every Bash tool call MUST be a single, simple command. Never chain with `&&`, `;`, `||`, pipes to other commands, or multi-line scripts. Never use `cd` — use absolute paths or `git -C` instead.

**Wrong** (triggers permission prompt, breaks auto-allow):
```
cd /some/project && python script.py --flag "value"
```

**Right** (single command, auto-allowed):
```
python /some/project/script.py --flag "value"
```

Rules:
1. Use absolute paths for the script AND its arguments.
2. Use `git -C <path>` instead of `cd <path> && git`.
3. Redirect stderr to `/tmp/` (not a relative path).
4. If a command needs environment variables, use `ENV=val command` syntax — that is a single command, not a chain.

## Commit Delegation — MANDATORY

`git commit` must never be called directly. Dispatch the `commit` agent via
the Agent tool instead.

Calling `git commit` directly bypasses the confirmation gate, the pre-commit
hook failure → autofix path, the sign-off recording, and the background-commit
safety checks that are built into the `commit` agent template. The
`enforce_commit_delegation` PreToolUse hook will block any direct `git commit`
call that does not originate from within the `commit` agent.

**Wrong:**
```bash
git commit -m "some message"
```

**Right:**
```
# Use the Agent tool to dispatch the commit agent:
# Agent tool → commit agent → dispatches COMMIT_AGENT_MODE=1 git commit internally
```

## Repository Structure

This repo IS the leafcutter-ai package. Origin: `git@github.com-urlmonitor:urlmonitor/leafcutter-ai.git`

When installed into a consumer project, this repo is cloned into a subdirectory (e.g. `my-project/leafcutter-ai/`). The consumer then runs `python leafcutter-ai/scripts/build.py --target-dir .` to deploy agents, skills, and hooks into their project root.

For local development of the package itself, the workspace looks like:

```
leafcutter/              <- workspace directory (not tracked by this repo)
  leafcutter-ai/         <- THIS repo (git root)
  .claude/               <- build outputs deployed by build.py
  scripts/               <- build outputs deployed by build.py
```

To rebuild the development environment: `./build-self.sh` (or equivalently, `python leafcutter-ai/scripts/build.py --target-dir .` from the parent directory). See [ADR-001](docs/architecture/adrs/ADR-001-self-hosting-boundary.md) for the self-hosting boundary convention.

SSH auth uses host alias `github.com-urlmonitor` (key: `~/.ssh/id_urlmonitor`).

<!-- glossary-section: leafcutter -->
## Glossary

Project jargon and terminology is tracked at [docs/glossary.md](docs/glossary.md).

Consult it for project-specific terms when reading code or docs.

- **To populate from scratch**: run `/glossary-bootstrap` (once after initial install
  or after a major codebase merge).
- **Ongoing additions**: the `check-glossary-coverage` pre-commit hook detects novel
  terms in staged files and dispatches the `glossary-triage` agent automatically.
- **Do NOT hand-edit to add entries** — always use the triage flow so the blacklist
  stays consistent. Manual edits are only for correcting existing entries.

<!-- roadmap-phase:start — AUTO-GENERATED from docs/roadmap.json; edits between these markers are overwritten on next render -->

| Roadmap | [docs/roadmap.json](docs/roadmap.json) | Current phase, exit criteria, and tickets advancing the outcome. Use `python portable-dev-workflow/scripts/roadmap_query.py --current-outcome` to list actionable tickets. |

Current phase: `phase_1`
Current outcome: Stable MVP that installs into any project and helps the user build good software — portable, self-onboarding, and reliable enough to use across multiple repos.

<!-- roadmap-phase:end -->

## Architecture Reference

| Document | Path | What it covers |
|----------|------|----------------|
| Agent Knowledge Plane | [docs/architecture/agent_knowledge_plane.md](docs/architecture/agent_knowledge_plane.md) | All 11 channels through which agents receive context at invocation time (pre-execution knowledge injection). |
| Agent Knowledge System | [docs/architecture/agent_knowledge_system.md](docs/architecture/agent_knowledge_system.md) | How agents classify, route, and persist learnings after task completion (post-execution knowledge capture). |
| Agent Delivery Workflows | [docs/architecture/agent_delivery_workflows.md](docs/architecture/agent_delivery_workflows.md) | Supervisor dispatch topology, ticket batching, and blocker adjudication flows. |
| Knowledge Query | [templates/skills/knowledge-query/SKILL.md](templates/skills/knowledge-query/SKILL.md) | Cross-surface knowledge graph query skill. Invokes `scripts/knowledge_query.py` to search nodes across all paths.json surfaces (agents, tickets, docs, skills, ADRs, hooks) with keyword filter, surface filter, JSON export, and edge list output. |
| Knowledge Graph Visualization | [scripts/visualise_knowledge_graph.py](scripts/visualise_knowledge_graph.py) | Generates a self-contained D3.js force-directed HTML graph from all knowledge surfaces. Run `python scripts/visualise_knowledge_graph.py --no-open` to write to `/tmp/leafcutter_knowledge_graph.html`; omit `--no-open` to open in the default browser. |

## Error Handling Policy

All Python code in this repository must follow these four rules. They are
enforced mechanically at commit time by Ruff (rules E722, BLE001, TRY); the
rules below explain the *why* so violations are understandable before you hit
the linter.

**Rule 1 — External I/O must be wrapped.**
All calls to `requests.*`, `open()`, `cursor.execute()`, subprocess calls,
and any other operation that crosses a process or system boundary must be
wrapped in `try/except <SpecificExceptionType>`. "External I/O" means any
call that can raise an OS, network, or database error.

```python
# Good
try:
    response = requests.get(url, timeout=10)
except requests.RequestException as exc:
    logger.warning("Request failed: %s", exc)
    raise

# Bad — no try/except around external call
response = requests.get(url)
```

**Rule 2 — Never bare except (Ruff E722).**
`except:` with no exception type is forbidden. Always name at least one
specific exception type. Ruff rule E722 blocks the commit on bare excepts.

```python
# Good
except ValueError as exc:

# Bad — bare except
except:
```

**Rule 3 — Never silently swallow (Ruff BLE001, TRY).**
Every `except` block must either (a) log the error at WARNING or higher via
the project logger, or (b) re-raise the exception (as-is or wrapped in a
typed exception). An empty block or one that only sets a flag without logging
is a violation. Ruff rules BLE001 and the TRY family catch common forms.

```python
# Good — log and re-raise
except OSError as exc:
    logger.warning("File operation failed: %s", exc)
    raise

# Good — wrap in typed exception
except OSError as exc:
    raise ConfigLoadError("Cannot read config") from exc

# Bad — silently swallowed
except OSError:
    pass
```

**Rule 4 — No try/except on pure internal functions.**
Functions that do not perform I/O, do not call external services, and do not
mutate shared state must NOT be wrapped in try/except by default. Adding
try/except to pure functions obscures bugs. If a pure function raises
unexpectedly, let it propagate — the caller at the I/O boundary is
responsible.

```python
# Good — pure function, no try/except
def calculate_offset(start: int, end: int) -> int:
    return end - start

# Bad — unnecessary try/except on pure function
def calculate_offset(start: int, end: int) -> int:
    try:
        return end - start
    except Exception:
        return 0
```

For deeper explanation of the Ruff rules, see:
- [E722](https://docs.astral.sh/ruff/rules/bare-except/) — bare-except
- [BLE001](https://docs.astral.sh/ruff/rules/blind-exception/) — blind exception catch
- [TRY](https://docs.astral.sh/ruff/rules/#tryceratops-try) — tryceratops family

## Pre-Drive Checklist

Run through these checks before invoking `/build-feature` or starting any epic drive.
Skipping them risks silent failures that are hard to diagnose after the fact.

### EMU account: open epic PR before drive (if applicable)

**What to check:** If you are operating under an Enterprise Managed User (EMU)
GitHub account, `gh pr create` is blocked at the CLI level. Before dispatching
any tickets:

```bash
# Switch to the non-EMU account
gh auth switch --user urlmonitor

# Push the epic branch to origin first
git push -u origin EPIC-<name>

# Then open the PR manually at:
# https://github.com/<org>/<repo>/compare/main...EPIC-<name>
```

Once the PR exists, the `pull-request` phase on each ticket should detect it via
`gh pr list --head EPIC-<name>` and push to the existing branch without re-opening.

**REST API fallback (when `gh pr create` is EMU-blocked):** the GraphQL
`createPullRequest` mutation that `gh pr create` uses can be blocked for EMU accounts,
but the REST endpoint is not. When `gh pr create` fails with the EMU error, create the
PR via the REST API instead:

```bash
gh api -X POST repos/<org>/<repo>/pulls \
  -f title="feat(...): <title>" \
  -f head="EPIC-<name>" \
  -f base="main" \
  -f body="<body>"
```

(Confirmed working in EPIC-AcPatternEnforcementIsMechanically PR #100/#102, 2026-06-18 —
`gh pr create` itself also succeeded under the `urlmonitor` account in the same session,
so try the CLI first and fall back to `gh api` only on the EMU error.)

**If you skip this:** The pull-request phase on the first ticket that tries `gh pr
create` under the EMU account will fail with "Unauthorized: As an Enterprise Managed
User, you cannot access this content (createPullRequest)".

**`gh pr merge` is EMU-blocked too — switch accounts before merging.** The same EMU
restriction applies to merging, not just creating, PRs. When the active gh account is
an EMU account (e.g. a corporate `*_roche` account), `gh pr merge` fails with
"Unauthorized: As an Enterprise Managed User, you cannot access this content
(mergePullRequest)". The fix is the same as for `gh pr create`: switch to the non-EMU
account first.

```bash
# Check which account is active (the EMU account is often the default):
gh auth status

# Switch to the non-EMU account before merging:
gh auth switch --user urlmonitor

# Then merge:
gh pr merge <N> --squash --delete-branch
```

(Observed in EPIC-Exceptionhandlingguardenforcestheerror finalize, 2026-06-18: the merge
failed under the active `henzeh_roche` account and succeeded immediately after
`gh auth switch --user urlmonitor`. The `gh api` REST fallback also works for merge:
`gh api -X PUT repos/<org>/<repo>/pulls/<N>/merge -f merge_method=squash`.)

### Feedback sink reachable

**What to check:** Verify that `debugging/logs/agent_telemetry.jsonl` (or the configured
remote endpoint, if any) is writable before the drive begins.

```bash
# Quick writability probe — should exit 0 and append one line
echo '{"probe":"pre-drive-check"}' >> debugging/logs/agent_telemetry.jsonl
```

If the command exits non-zero, the sink is unreachable — fix before invoking `/build-feature`.

**If the check fails:** Do not start the drive. The most common causes are:
- The `debugging/logs/` directory does not exist yet (`mkdir -p debugging/logs/`).
- A remote endpoint (future) is down — wait for it to recover or disable remote logging.
- A permissions issue on WSL2 NTFS mounts — remount or use a native Linux path.

**Why this matters:** During a past epic drive, the sink was unreachable for the entire
run. 23 `submit-failed` events occurred without detection — the drive completed but zero
telemetry was captured, making the retrospective impossible.
(Root cause ticket: TICKET-20260527-FeedbackSinkPreDriveCheck)

### Worktree pre-commit config (MANDATORY for worktree-based drives)

Worktrees do not inherit `.pre-commit-config.yaml` from the main working tree.
It is a `.leafcutter` symlink created by `install_shims` in the project root only —
a fresh worktree created from `origin/main` has neither the symlink nor a populated
`.leafcutter/`. If the worktree root lacks it, ALL package hooks are silently skipped
for the entire drive (`git commit` runs with `PRE_COMMIT_ALLOW_NO_CONFIG=1`).

**Check:**
```bash
ls <worktree-root>/.pre-commit-config.yaml 2>/dev/null || ls <worktree-root>/.leafcutter 2>/dev/null
```

**Fix (if absent):**
```bash
# Option A — symlink (preferred, requires native Linux FS):
ln -s <main-tree-root>/.leafcutter <worktree-root>/.leafcutter

# Option B — copy (for NTFS/WSL2 where symlinks are restricted):
cp <main-tree-root>/.pre-commit-config.yaml <worktree-root>/.pre-commit-config.yaml
```

**Why this matters:** During EPIC-AcPipelineDeployGaps (2026-06-17), all nine package
hooks were silently skipped for the entire drive. A post-drive diagnostic found 14
would-have-blocked findings (7 `check-feedback-id` + 7 `check-description-field`) that
required a dedicated fix commit after merge. If you cannot establish the config, run the
package hooks manually against the branch diff before merge.
(Permanent fix tracked in TICKET-20260617-Worktree_Precommit_Bootstrap.md)

**Latent hazard — `.security-allowlist` resolves via the symlink target, not the worktree
root.** The `check-secrets` hook computes its project root from `__file__` of the *resolved*
`.leafcutter` symlink target (under the workspace parent, e.g.
`/home/henzeh/projects/leafcutter/.leafcutter/`), so it reads the allowlist from the
**workspace-root** `.security-allowlist`, not the worktree's own copy. When you add a
suppression for a worktree-local false positive, add it to the workspace-root
`.security-allowlist` (or duplicate it to both) — a suppression placed only in the
worktree's `.security-allowlist` is silently ignored when the hook runs via the symlink path.
(Observed in EPIC-AcPatternEnforcementIsMechanically, 2026-06-18.)

### Land the scaffold commit on origin/main before creating the epic worktree

After running `/create-epic`, confirm the scaffold commit (Master_Plan.md + sub-ticket
stubs) is reachable from `origin/main` before calling `worktree-agent` to create the epic
worktree.

```bash
# The scaffold files must be reachable from origin/main (empty output = nothing missing):
git -C <repo> log --oneline origin/main..main
```

**`main` is PR-only (ruff branch-protection gate).** A direct `git push origin main` is
rejected with `GH013: ... Required status check "Lint (ruff)" is expected`. The scaffold
must go through its own PR:

```bash
# 1. Push the scaffold commit to a short-lived branch:
git -C <repo> push origin HEAD:scaffold/EPIC-<name>

# 2. Open a PR targeting main and merge it once the ruff check is green
#    (scaffold is tickets-only, so ruff passes trivially):
gh pr create --repo <org>/<repo> --base main --head scaffold/EPIC-<name> \
  --title "chore: scaffold EPIC-<name>" --body "..."
gh pr merge <N> --squash --delete-branch

# 3. Verify the scaffold is on origin/main before creating the epic worktree:
git -C <repo> fetch origin
git -C <repo> ls-tree -r origin/main --name-only tickets/00_inbox/epics/EPIC-<name>/
```

**If you skip this:** the epic worktree (created from `origin/main`) diverges at a stale
point — the scaffold files are unreachable inside it and ticket agents cannot read them
until the scaffold commit is cherry-picked onto the epic branch. Worse, when the scaffold
later reaches `origin/main` independently, the epic PR hits an add/add merge conflict on
those files at finalize (resolve in favor of the branch — the `status: done` versions win).
(Source: EPIC-AcPipelineDeployGaps retrospective, 2026-06-17, Findings #1 + #5;
scaffold-via-PR confirmed in EPIC-AcPatternEnforcementIsMechanically, 2026-06-18.)
