"""
MODULE: __init__
GOAL: Thin composition adapters; knowledge remains independent of the kernel.
BUSINESS CONTEXT: Keep optional knowledge retrieval bounded and traceable.
ARCHITECTURE: Adapter between neutral knowledge transport and existing kernel contracts.
"""


# DECISION HISTORY
# ================================================================================
# - 2026-10-01 20:00 [python-coder]: Preserve canonical evidence and optional bounded retrieval. (#TICKET-20261001-KM-400e-3)
