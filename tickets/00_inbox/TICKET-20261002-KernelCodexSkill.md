---
title: "Kernel: run the kernel procedure from Codex as $leafcutter, and scope both skills to a rendered repository root"
status: in_progress
components:
  - decision_kernel
created: 2026-10-02
depends_on: []
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - codex
  - skill
last_updated: 2026-10-02
agents:
  python-coder: needed
  commit: needed
---

# Kernel: run the kernel procedure from Codex as $leafcutter, and scope both skills to a rendered repository root

## Actor / Goal
In order to use the Decision Kernel from OpenAI Codex (the CLI and the IDE extension) as well as from Claude Code, we need `install-skill` to render a Codex skill from the same in-package source. In both hosts the kernel must always search the intended repository, whichever folder the session starts in.

## Context
- **Decision:** `dec-73b6db1907adc960` (run `run-c71cd33587cf4f5e`, approved by the user 2026-10-02). The chosen option renders the Codex skill from the same in-package source into the workspace root where sessions start, writes the repository root in at install time, and adds a prefix rule that allows only the kernel command.
- **Placement is for now only.** The user's long-term requirement is a separate ticket: `TICKET-20261002-KernelSkillSameBuildPath`.
- **Codex facts** (research, Codex CLI 0.160.0, 2026-10-01; full write-up with sources in the session scratchpad `codex-research.md`):
  - **No custom slash commands.** Custom prompts were removed in v0.118.0, and unknown `/commands` are rejected.
  - **Skills:**
    - Codex loads skills from `.agents/skills/<name>/SKILL.md`, in every directory from the project root down to the cwd, and from `~/.agents/skills`.
    - The user calls one explicitly with `$leafcutter <goal>`. Codex injects the whole SKILL.md, and the text after `$leafcutter` stays the user's message, so the skill reads the goal from it.
    - Frontmatter: only `name`, `description` and `metadata.short-description` are read. `allowed-tools` and `disable-model-invocation` are ignored.
    - `agents/openai.yaml` with `policy: allow_implicit_invocation: false` keeps the skill explicit-only.
  - **Questions:**
    - The structured `request_user_input` tool works only in Plan mode by default.
    - Codex's Default-mode instructions forbid multiple-choice questions written as text.
    - So the skill asks one short plain-text question and waits; it uses `request_user_input` only when that tool is available.
  - **Sandbox:** the default sandbox has no network.
    - A `prefix_rule(pattern=[...], decision="allow")` in `.codex/rules/*.rules` (trusted projects only) runs the matched command outside the sandbox without a prompt.
    - That rule is the narrow equivalent of `allowed-tools`. Use a specific prefix such as `<python> -m kernel run|resume|status`, never bare `python`.
- **Known defect fixed here:**
  - The Claude Code skill tells the host to send `"repository_root": "<absolute project root>"`.
  - From the user's workspace folder (`C:\Users\Hendrik\Code\leafcutter`, not a git repo), that scoped a live run to the wrong folder (`run-49c4f5e97f2d41d6`): no ADRs, no components, and the kernel still reported "completed".
- **Unchanged:** the kernel skill still never ships through `build.py` (`kernel/adapters/`, never `templates/`).

## Scope (no acceptance criteria, by user decision)
- **`install-skill` options:**
  - `--host claude_code|codex` (default `claude_code`).
  - `--repository-root DIR`, the repository the kernel scopes to, written into the skill. It defaults to the kernel checkout the command runs from.
  - `--workspace-id`, defaulting to the repository folder name.
- **Both skills:** render `repository_root` and `workspace_id` as fixed values instead of asking the host to guess them.
- **Codex adapter** (`kernel/adapters/codex/`), rendering:
  - **`<target>/.agents/skills/<name>/SKILL.md`:** the same transport-only procedure, adapted for Codex.
    - The goal is the user's text after `$<name>`.
    - Kernel commands run with an explicit working directory, so no env-var prefix is needed.
    - Submission files are written inside the client directory.
    - Human questions: show the kernel's question and choices once, accept the user's reply naming a choice, and never choose for the user. Use `request_user_input` if it is available.
  - **`<target>/.agents/skills/<name>/agents/openai.yaml`:** explicit-only invocation and a display name.
  - **`<target>/.codex/rules/<name>.rules`:** a `prefix_rule` allowing only the rendered kernel `run`, `resume` and `status` commands.
  - **Overwrite guard:** the same marker-based refusal as the Claude Code installer.
- **Tests:**
  - render tests for both hosts;
  - the rules file allows exactly the three subcommands;
  - no machine path is baked into committed templates;
  - `repository_root` is rendered;
  - the overwrite guard holds.
- **Docs:** a Codex section in `docs/how-to/run-the-decision-kernel.md` (install, trust the project, `$leafcutter`), and the CLI reference.
- **Install on this PC:**
  - Codex skill and rules into the workspace root.
  - Reinstall the Claude Code skill with the rendered repository root.
  - The repository root is the up-to-date main checkout used by the runtime: `worktrees/leafcutter-runtime`.

## Out of Scope
- Shipping either skill through `build.py`: see `TICKET-20261002-KernelSkillSameBuildPath`.
- Installing the Codex CLI.

## Comments
