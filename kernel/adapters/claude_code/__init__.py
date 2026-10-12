"""
MODULE: kernel.adapters.claude_code
GOAL: The Claude Code client: the transport-only skill template and its installer.
BUSINESS CONTEXT: Claude Code is the first cooperative host; it carries packets and answers
    between the user and the kernel and decides nothing (Rev 3 section 11.4).
ARCHITECTURE: SKILL.md is data; `install.py` renders and installs it. Not shipped to adopters.
"""

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 11:00 [python-coder]: Package marker added with the P7 client adapters.
#   (#KernelBootstrapV0/P7)
# ====================================================================
