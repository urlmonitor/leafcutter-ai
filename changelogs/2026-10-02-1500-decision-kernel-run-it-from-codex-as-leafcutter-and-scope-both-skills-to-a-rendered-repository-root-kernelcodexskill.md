---
title: "Decision kernel: run it from Codex as $leafcutter, and scope both skills to a rendered repository root (KernelCodexSkill)"
date: "2026-10-02"
time: "15:00"
type: feature
components: 
  - decision_kernel
summary: "install-skill gains --host codex, --repository-root and --workspace-id; both skills now carry a fixed scope."
description: "install-skill --host codex writes an explicit-only Codex skill, its openai.yaml policy and a prefix rule allowing only the kernel run, resume and status commands. Both the Claude Code and Codex skills now render repository_root and workspace_id at install time instead of asking the host to guess them, which had scoped a live run to the wrong folder."
---

## Entry
