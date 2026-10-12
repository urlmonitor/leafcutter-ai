"""
MODULE: kernel.adapters.codex
GOAL: The Codex client: the transport-only skill template, its explicit-only policy, the
    prefix rules that pre-approve the kernel command, and the installer.
BUSINESS CONTEXT: Codex has no custom slash commands; a skill typed as `$leafcutter <goal>` is
    its native equivalent. Like Claude Code, Codex only carries packets and decides nothing.
ARCHITECTURE: SKILL.md and openai.yaml are data; `rules.py` renders the `.rules` file and
    `install.py` renders and installs all three. Not shipped to adopters.
"""

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: Package marker added with the Codex adapter.
#   (#KernelCodexSkill)
# ====================================================================
