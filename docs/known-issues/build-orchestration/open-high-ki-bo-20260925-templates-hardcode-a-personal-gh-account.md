---
title: "KI-BO-20260925-templates-hardcode-a-personal-gh-account — five portable templates run 'gh auth switch --user urlmonitor', while the one config-driven site reads keys that exist nowhere"
description: "high (portability) — plan-feature, fast-lane-ship, quick-fix (JS and skill) and build-single-ticket ship a personal GitHub account to every adopter; finalize reads gh_target_account from a settings.json no layout has; none clears GH_TOKEN."
type: reference
category: reference
status: active
created: '2026-09-25'
last_updated: '2026-09-25'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/supervisor-system/open-high-ki-ss-20260826-agent-routed-around-a-blocked-capability.md
  - docs/analysis/2026-09-25-duplication-clusters-that-produce-known-issues.md
---

# KI-BO-20260925-templates-hardcode-a-personal-gh-account — five portable templates run 'gh auth switch --user urlmonitor', while the one config-driven site reads keys that exist nowhere

- **Severity:** high for the phase-1 outcome ("installs into any project"). In an adopter the switch fails or, worse, succeeds against an account that happens to exist.
- **Status:** open — no AC. Sites found by grep 2026-09-25.
- **Where:**
  - `templates/workflows-js/plan-feature.js:761` (and REST fallback `:760-790`)
  - `templates/workflows-js/fast-lane-ship.js:1757` ("continue anyway" on failure)
  - `templates/workflows-js/quick-fix.js:1047`
  - `templates/skills/quick-fix/SKILL.md:971`
  - `templates/skills/build-single-ticket/SKILL.md:152`
  - config-driven: `templates/workflows-js/finalize-feature.js:664-730` (`gh_target_account`, `gh_repo`)

## Divergences

- The finalize site reads `gh_target_account` from `<wt>/settings.json` or `config/settings.json`; neither file
  exists (grep finds the key only in a done ticket and a test), so in this repo finalize never switches while the
  five other sites always do.
- `build-single-ticket` tells the *pull-request* phase agent to apply the EMU steps, but `pull-request.md` contains
  no `gh auth` instructions and does not load that skill.
- None handles an environment `GH_TOKEN`, which overrides stored accounts in `gh`; `gh auth switch` then has no
  effect on the push/PR call.
- PR bodies: quick-fix uses `--body-file` after a backtick-interpolation incident (`:1072-1076`); plan-feature
  (`:768`, `:786`) and fast-lane still pass inline heredoc / `-f body="…"` bodies.

## Fix direction

One `open_pr.py` / `push_branch.py`: account from `skills_config.json` (absent → no switch), `GH_TOKEN` cleared for
the call, CLI first then REST fallback, body always from a file, returns `{pr_number, pr_url, path_used}` re-read
via `gh pr list --head`. Every workflow and the pull-request agent call it. Cluster 6 of the 2026-09-25
duplication analysis.
