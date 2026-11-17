"""Application CLI adding opt-in existing tracing to neutral knowledge commands.

MODULE: knowledge_cli
GOAL: Compose observability without importing the kernel from neutral knowledge.
BUSINESS CONTEXT: Standalone callers see explicit observation availability.
ARCHITECTURE: Thin app composition with the existing tracer, secret loader and spool.
"""
from __future__ import annotations

from typing import Any

import argparse
import sys
from pathlib import Path
from integrations.knowledge_observation import RetrievalObserver


def build_observer(config_path: Path | None) -> tuple[Any, Any]:
    """Compose opt-in tracing while keeping initialization failure caller-visible.

    Args:
        config_path: Explicit kernel observability configuration or None.

    Returns:
        Observer and owned tracer, without affecting retrieval availability.
    """
    if config_path is None:
        return RetrievalObserver(), None
    try:
        from kernel.config import load_kernel_config, repo_root
        from kernel.bootstrap import resolve_run_root, TELEMETRY_SPOOL
        from kernel.observability.langfuse_tracer import LangfuseTracer
        from kernel.secrets import load_secrets
        config = load_kernel_config(config_path)
        tracer = LangfuseTracer(secrets=load_secrets(), config=config.langfuse,
            policy=config.data_policy, deny_globs=config.retrieval.deny_globs,
            spool_path=resolve_run_root(config, repo_root()) / TELEMETRY_SPOOL)
        return RetrievalObserver(tracer), tracer
    except (OSError, ValueError, RuntimeError, ImportError):
        return UnavailableObserver(), None


class UnavailableObserver:
    """Report a sanitized initialization failure without retrying the query."""

    def observe(self, request: Any, result: Any) -> dict:
        """Return a stable unavailable envelope for the final successful retrieval.

        Args:
            request: Final scoped request.
            result: Final retrieval response.

        Returns:
            Caller-visible telemetry availability with no speculative link.
        """
        return {"state": "unavailable", "trace_id": None, "trace_url": None,
                "reason": "Observation initialization unavailable", "request_id": request.request_id,
                "retrieval_id": result.retrieval_id}


def main() -> int:
    """Run neutral command parsing with an explicitly configured observation owner.

    Returns:
        Neutral command exit code, preserved even when telemetry shutdown fails.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--observability-config", type=Path)
    options, remaining = parser.parse_known_args()
    observer, tracer = build_observer(options.observability_config)
    from knowledge.__main__ import main as neutral_main
    previous = sys.argv
    try:
        sys.argv = [previous[0], *remaining]
        return neutral_main(observer=observer)
    finally:
        sys.argv = previous
        if tracer is not None:
            try:
                tracer.shutdown()
            except (OSError, ValueError, RuntimeError, TimeoutError):
                import logging
                logging.getLogger(__name__).warning("Observation shutdown unavailable; retrieval was not retried")


if __name__ == "__main__":
    raise SystemExit(main())

# DECISION HISTORY
# - 2026-10-01 [python-coder]: Preserve scoped answer obligations and honest observation through existing runtime owners. (#KM-500/KM-500e-1)
