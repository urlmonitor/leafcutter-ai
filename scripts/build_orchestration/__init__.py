"""
MODULE: scripts/build_orchestration/__init__.py
GOAL: Package init for the build_orchestration module.
BUSINESS CONTEXT: Groups helper modules that govern how a build run is
    planned and routed — e.g. which quality pipeline (fast vs heavy) to
    invoke for a given ticket.
ARCHITECTURE: Pure namespace package; imports are kept minimal so
    individual modules can be imported independently without side effects.
"""
