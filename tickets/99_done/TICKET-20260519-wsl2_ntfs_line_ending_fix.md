---
title: "Fix phantom git modifications on WSL2/NTFS: .gitattributes + onboard detection"
status: todo
components:
  - documentation_system
  - infrastructure
created: 2026-05-19
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - leafcutter-ai/.gitattributes
  - leafcutter-ai/BOOTSTRAP.md
  - leafcutter-ai/templates/agents/onboard.md
agents:
  architect-review: not_needed
  python-coder: not_needed
  test-writer: not_needed
  test-runner: not_needed
  documentation-expert: needed
  change-scope-reviewer: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  status-checker: not_needed
  sql-coder: not_needed
  sql-query: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
---

# TICKET-20260519-wsl2_ntfs_line_ending_fix

## Actor / Goal

In order to eliminate phantom git modifications in the leafcutter submodule on WSL2/NTFS environments, we need to add a `.gitattributes` enforcing LF line endings and update the onboard wizard to detect WSL2 + NTFS mounts so that users are never blocked by cryptic "local changes would be overwritten" errors caused by CRLF noise.

## Context

On WSL2 when the working directory lives on `/mnt/c/` (an NTFS volume), Windows filesystem layer can add CRLF line endings to files that should be LF. Because `core.autocrlf` is not set and there is no `.gitattributes` enforcing LF in the leafcutter repo, git sees every tracked file as "modified" — even though no actual code changes exist.

This surfaces as:

```
fatal: Cannot update submodule 'leafcutter-ai'
error: Your local changes to the following files would be overwritten by checkout
```

The submodule content is identical; the diff is pure line-ending noise. The fix has two parts:

1. **Repo-level `.gitattributes`** — `* text=auto eol=lf` tells git to normalise all text files to LF on checkout, regardless of the host OS. This makes the repo resilient without requiring any per-user config.

2. **Onboarding detection** — the `/onboard` wizard should detect WSL2 + NTFS mount at startup and either auto-set `core.autocrlf=input` in the local git config, or surface a clear warning so the user can do it manually before `git submodule update --remote` is run.

Files affected:
- `leafcutter-ai/.gitattributes` — new file (root of the package)
- `leafcutter-ai/BOOTSTRAP.md` — add a "Windows / WSL2 prerequisite" section
- `leafcutter-ai/templates/agents/onboard.md` — add a WSL2+NTFS detection step

## Acceptance Criteria

```gherkin
Given a fresh clone on WSL2 at /mnt/c/ with no .gitattributes in leafcutter-ai
When the user runs git submodule update --remote
Then git reports phantom modifications in the submodule

Given leafcutter-ai/.gitattributes contains "* text=auto eol=lf"
When the user re-clones or runs git checkout on WSL2 at /mnt/c/
Then git submodule update --remote completes without "local changes" errors

Given the user runs /onboard on WSL2 at /mnt/c/
When the onboard wizard checks the environment
Then it either auto-sets core.autocrlf=input in the local git config
  OR surfaces a clear warning: "WSL2 + NTFS mount detected — set core.autocrlf=input before proceeding"

Given the user reads BOOTSTRAP.md
When they are on Windows or WSL2
Then there is a visible prerequisite section explaining the CRLF/LF issue and the fix command
```

## Sign-offs

- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] Create `leafcutter-ai/.gitattributes` with `* text=auto eol=lf` (and explicit overrides for binary files if needed, e.g. `*.png binary`)
- [ ] Add a "Windows / WSL2 Prerequisites" section to `leafcutter-ai/BOOTSTRAP.md` explaining: the CRLF gotcha, the diagnostic command (`git diff --stat` showing all-file modifications), and the fix (`git config core.autocrlf input`)
- [ ] Add a WSL2 + NTFS detection step to `leafcutter-ai/templates/agents/onboard.md`:
  - Detect: `uname -r | grep -i microsoft` AND `pwd | grep -q '^/mnt/'`
  - If both true: run `git config core.autocrlf input` automatically and log "WSL2/NTFS detected — set core.autocrlf=input"
  - If detection is ambiguous or auto-set is not desired: surface the warning as a PREREQUISITE block so the user can act before proceeding
- [ ] Verify that after applying `.gitattributes`, `git status` is clean on a WSL2/NTFS checkout (manual smoke test note — no automated test required)

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Fully reversible. `.gitattributes` is additive; removing it restores the prior behaviour. The `core.autocrlf=input` git config change is local and can be unset with `git config --unset core.autocrlf`. BOOTSTRAP.md additions are documentation-only.
- Cross-platform impact? `* text=auto eol=lf` is the widely-accepted standard for repos that must work across Windows/Mac/Linux. It should not break existing Linux or macOS users — files checked out on those systems already have LF.
