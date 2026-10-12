---
title: "How to run the decision kernel from Codex"
description: "Install the kernel skill for OpenAI Codex (CLI and IDE extension), trust the workspace project so the prefix rule loads, start a run with $leafcutter <goal>, and answer the kernel's human questions in plain text or through request_user_input."
type: how-to
status: active
created: 2026-10-02
last_updated: 2026-10-02
components:
  - decision_kernel
related_docs:
  - docs/how-to/run-the-decision-kernel.md
  - docs/architecture/components/decision-kernel.md
related_code:
  - kernel/adapters/cli.py
  - kernel/adapters/codex/install.py
  - kernel/adapters/codex/rules.py
  - kernel/adapters/codex/SKILL.md
  - kernel/adapters/codex/openai.yaml
---

# How to run the decision kernel from Codex

Codex has no custom slash commands, so the kernel is a skill you call with `$leafcutter <goal>`.
It is transport only, like the Claude Code skill: the kernel decides, Codex relays. Set up
credentials first ([Step 1 of the main how-to](run-the-decision-kernel.md)).

## Steps

### Step 1 — Install the skill into the folder where Codex sessions start

```bash
python -m kernel install-skill --host codex --target-dir <workspace> --name leafcutter \
  --repository-root <repository> --json
```

- `<workspace>` is the folder you start Codex in. It need not be a git repository.
- `<repository>` is the checkout the kernel searches (ADRs, components, code). It defaults to the
  checkout you run the command from. `--workspace-id` defaults to its folder name. Both are
  written into the skill, so a session started elsewhere still scopes the kernel correctly.
- Run it from the up-to-date kernel checkout: the skill runs `<python> -m kernel` with that
  checkout as the working directory.

The command writes three files and lists them under `files` in its JSON:

| File | Purpose |
|---|---|
| `<workspace>/.agents/skills/leafcutter/SKILL.md` | The transport procedure. |
| `<workspace>/.agents/skills/leafcutter/agents/openai.yaml` | `allow_implicit_invocation: false`: only `$leafcutter` starts it. |
| `<workspace>/.codex/rules/leafcutter.rules` | `prefix_rule` entries allowing only the kernel `run`, `resume` and `status` commands. |

An existing file without the `leafcutter-kernel-skill` marker is never overwritten unless you add
`--force`; if any of the three is foreign, none is written.

### Step 2 — Trust the workspace project

Codex loads `.codex/rules/` only for a trusted project. The default sandbox has no network, so
without the rule the kernel command would be refused or prompt every time. Trust the folder:
accept the first-run trust prompt, or add to `~/.codex/config.toml` (Windows paths use doubled
backslashes inside the quotes):

```toml
[projects."C:\\Users\\you\\Code\\workspace"]
trust_level = "trusted"
```

The rule runs the matched command outside the sandbox without a prompt: network and file access
included. It matches only `<python> -m kernel run|resume|status`, never a bare `python`. Check it
with `codex execpolicy check --pretty --rules <workspace>/.codex/rules/leafcutter.rules -- <command>`.

The skill writes its scratch JSON into `<run_root>/client/` (see `paths.run_root`). If that folder
is outside the workspace, Codex asks to approve each write; to avoid that, add the run root to
`[sandbox_workspace_write] writable_roots` in `~/.codex/config.toml`.

### Step 3 — Start a run

Start Codex in `<workspace>` and type, with single quotes in `codex exec`:

```text
$leafcutter Should we cache the registry lookups?
```

Everything after `$leafcutter` is the goal, passed verbatim. Codex has no argument
substitution; the skill reads the goal from your message.

### Step 4 — Answer the kernel's questions

When the kernel needs a human decision, Codex shows its `question`, each choice with its
consequences and `why_research_cannot_settle`, once.

- With the `request_user_input` tool available (Plan mode), Codex asks through that picker.
- Otherwise (Default mode) it asks in plain text. Reply naming one choice, by label or id.
  If your reply is unclear it asks once more. It never picks for you.

The final report, limitations and a staged decision record are presented as in Claude Code.
Publishing the record (`decisions publish`) stays yours to run.

## Verification

Reinstall prints `"host": "codex"` and three paths under `files`. In Codex, `/skills` (CLI) or
typing `$` lists `leafcutter`; a plain message such as "decide X" does not start it.

## Troubleshooting

1. **Codex asks to approve the kernel command each time.** The project is not trusted, or the
   interpreter path in the rule differs from the one the skill ran. Reinstall from the same
   Python you run the kernel with.
2. **`$leafcutter` is not listed.** Restart Codex; skills load at session start.

## See Also

- [How to run the decision kernel](run-the-decision-kernel.md)
- [Decision kernel container overview](../architecture/components/decision-kernel.md)
- [Documentation Index](../INDEX.md)
