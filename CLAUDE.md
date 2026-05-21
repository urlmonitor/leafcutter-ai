# CLAUDE.md — leafcutter

<!-- roadmap-phase:start — AUTO-GENERATED from leafcutter-ai/docs/roadmap.json; edits between these markers are overwritten on next render -->

| Roadmap | [leafcutter-ai/docs/roadmap.json](leafcutter-ai/docs/roadmap.json) | Current phase, exit criteria, and tickets advancing the outcome. Use `python portable-dev-workflow/scripts/roadmap_query.py --current-outcome` to list actionable tickets. |

Current phase: `phase_1`
Current outcome: Stable MVP that installs into any project and helps the user build good software — portable, self-onboarding, and reliable enough to use across multiple repos.

<!-- roadmap-phase:end -->

## Worktrees

`scripts/setup_ticket_worktree.py` does not exist yet. When you need to create a worktree (for `/build-feature`, `/worktree create`, or any ticket-driven workflow), use the built-in `EnterWorktree` tool directly instead of calling the missing script.

<!-- glossary-section: leafcutter -->
## Glossary

Project jargon and terminology is tracked at [leafcutter-ai/docs/glossary.md](leafcutter-ai/docs/glossary.md).

Consult it for project-specific terms when reading code or docs.

- **To populate from scratch**: run `/glossary-bootstrap` (once after initial install
  or after a major codebase merge).
- **Ongoing additions**: the `check-glossary-coverage` pre-commit hook detects novel
  terms in staged files and dispatches the `glossary-triage` agent automatically.
- **Do NOT hand-edit to add entries** — always use the triage flow so the blacklist
  stays consistent. Manual edits are only for correcting existing entries.
