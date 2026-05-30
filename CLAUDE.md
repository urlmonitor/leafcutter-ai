# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.

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

## Pre-Drive Checklist

Run through these checks before invoking `/build-feature` or starting any epic drive.
Skipping them risks silent failures that are hard to diagnose after the fact.

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
