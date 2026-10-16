"""
MODULE: kernel.split
GOAL: Detection of a bundled request: the bundle question, the deterministic gates and the split
    record's derived fields.
BUSINESS CONTEXT: ADR-053 and ADR-067: a request that holds several separate questions is offered
    as a split a person approves instead of ending as a capability gap.
ARCHITECTURE: Pure helpers (`text`, `detect`); the scheduler mixin that applies them lives in
    kernel.scheduler.nodes_split. Nothing here imports the scheduler.
"""

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-06 18:00 [python-coder]: New package for split detection and subject text helpers. (#TICKET-20261006-DK-400a-1)
# ====================================================================
