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

To rebuild the development environment: `./build-self.sh` (or equivalently, `cd .. && python leafcutter-ai/scripts/build.py --target-dir .`). See [ADR-001](docs/architecture/adrs/ADR-001-self-hosting-boundary.md) for the self-hosting boundary convention.

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

**If you skip this:** The pull-request phase on the first ticket that tries `gh pr
create` under the EMU account will fail with "Unauthorized: As an Enterprise Managed
User, you cannot access this content (createPullRequest)".

### Feedback sink reachable

**What to check:** Verify that `debugging/logs/agent_telemetry.jsonl` (or the configured
remote endpoint, if any) is writable before the drive begins.

```bash
# Quick writability probe — should exit 0 and append one line
echo '{"probe":"pre-drive-check"}' >> debugging/logs/agent_telemetry.jsonl \
  && echo "Sink OK" || echo "Sink UNREACHABLE — fix before invoking /build-feature"
```

**If the check fails:** Do not start the drive. The most common causes are:
- The `debugging/logs/` directory does not exist yet (`mkdir -p debugging/logs/`).
- A remote endpoint (future) is down — wait for it to recover or disable remote logging.
- A permissions issue on WSL2 NTFS mounts — remount or use a native Linux path.

**Why this matters:** During a past epic drive, the sink was unreachable for the entire
run. 23 `submit-failed` events occurred without detection — the drive completed but zero
telemetry was captured, making the retrospective impossible.
(Root cause ticket: TICKET-20260527-FeedbackSinkPreDriveCheck)
