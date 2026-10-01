"""
MODULE: kernel.adapters
GOAL: Client adapters over the application service: the command-line interface and the Claude
    Code skill.
BUSINESS CONTEXT: Clients differ (CLI, skill, a future MCP tool) but all speak the same four
    service operations, so the kernel never depends on any one of them (Rev 3 section 5.1).
ARCHITECTURE: Adapters import the service and bootstrap; nothing outside `kernel/adapters`
    imports an adapter. The CLI is `python -m kernel` (see `kernel/__main__.py`).
"""

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 11:00 [python-coder]: Package marker added with the P7 client adapters.
#   (#KernelBootstrapV0/P7)
# ====================================================================
