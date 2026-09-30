"""
MODULE: kernel.__main__
GOAL: Entry point for `python -m kernel`.
BUSINESS CONTEXT: The repository has no installable console script, so the CLI is invoked as a
    module (design part 5); the Claude Code skill runs exactly this command.
ARCHITECTURE: Delegates to `kernel.adapters.cli.main` and exits with its code.
"""

from __future__ import annotations

import sys

from kernel.adapters.cli import main

if __name__ == "__main__":
    sys.exit(main())

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 12:15 [python-coder]: Thin module entry so `python -m kernel` works without a
#   packaging change. (#KernelBootstrapV0/P7)
# ====================================================================
