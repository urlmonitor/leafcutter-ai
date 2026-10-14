"""Standalone retention-policy command: report which generations may be reclaimed.
MODULE: knowledge.cli_retention
GOAL: Expose the declared retention bound and its reclaimability verdicts without reclaiming.
BUSINESS CONTEXT: Operators must see what a declared bound would reclaim before anything is deleted.
ARCHITECTURE: Resolves the bound before any network access; delegates evaluation to the projection adapter.
"""

from __future__ import annotations

import argparse

from .config import KnowledgeConfig, resolve_retention_bound
from .errors import invalid

BOUND_SOURCE = "command line (--retention-max-generations, --retention-min-age-seconds)"


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register the read-only retention command.

    Args:
        subparsers: Argument-parser collection receiving the command.
    """
    parser = subparsers.add_parser("retention")
    parser.add_argument("--backend", choices=["none", "neo4j"], default="none")
    parser.add_argument("--repository-id", default="leafcutter")
    parser.add_argument("--retention-max-generations", type=int, default=None)
    parser.add_argument("--retention-min-age-seconds", type=int, default=None)


async def run(args: argparse.Namespace) -> dict:
    """Evaluate the declared retention bound; refuse before any network access if undeclared.

    Args:
        args: Parsed retention command arguments.

    Returns:
        dict: Declared bound, its source and a verdict per generation.
    """
    config = KnowledgeConfig(
        backend=args.backend,
        repository_id=args.repository_id,
        retention_max_generations=args.retention_max_generations,
        retention_min_age_seconds=args.retention_min_age_seconds,
    )
    bound = resolve_retention_bound(config, source=BOUND_SOURCE)
    if config.backend != "neo4j":
        invalid("retention evaluation requires the neo4j backend")
    from .adapters.neo4j_backend import Neo4jBackend
    from .adapters.neo4j_retention import evaluate_retention
    from .environment import resolve_database, resolve_neo4j

    backend = Neo4jBackend(
        *resolve_neo4j(config), database=resolve_database(config), query_timeout=config.query_timeout
    )
    try:
        report = await evaluate_retention(backend, args.repository_id, bound)
    finally:
        await backend.close()
    return {"status": "ok", **report}
