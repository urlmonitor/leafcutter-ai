"""
MODULE: leafcutter_kernel
GOAL: Package root of the Leafcutter decision kernel: a resumable LangGraph runtime that
    routes goals to registered capabilities with Jev, gathers evidence, and hands bounded
    generative or human work to a cooperative client.
BUSINESS CONTEXT: Leafcutter must answer engineering decision and research questions with
    traceable evidence instead of one large prompt. This package is the Stage 1 MVP of the
    Revision 3 specification (docs/analysis/2026-09-30-leafcutter-kernel-spec-rev3.md).
ARCHITECTURE: Top-level package in leafcutter-ai only. It is not under templates/ or
    scripts/, so build.py never ships it to adopter projects. The module map and phase plan
    are in docs/analysis/2026-09-30-decision-kernel-design.md.
"""

__version__ = "0.1.0.dev0"

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 21:30 [claude]: Created the package marker in Phase 0 so the component
#   registration (docs/components.json: decision_kernel) lands in the same commit as the
#   new top-level package, as check-structural-change requires. (#KernelBootstrapV0/P0)
# ====================================================================
