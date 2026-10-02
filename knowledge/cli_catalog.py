"""Standalone discover, verify and explicitly activate authored query commands.

DECISION HISTORY
- 2026-10-01 15:46 [python-coder]: Activation is separate from read-only verification. (#KM-500/TICKET-20261001-KM-500b-3)

MODULE: knowledge.cli_catalog
GOAL: Provide the scoped knowledge retrieval cli_catalog responsibility.
BUSINESS CONTEXT: Make attributable research capabilities reusable and explicitly governed.
ARCHITECTURE: Dependencies point inward to neutral contracts; see docs/architecture/components/knowledge-retrieval.md.
"""

from __future__ import annotations

import json
from pathlib import Path
from .errors import invalid, CatalogIOError
from .query_catalog import QueryCatalog
from .query_admission import build_query_admission
from .config import KnowledgeConfig, build_retriever

COMMANDS = {"catalog-list", "query-verify", "query-register"}


def add_parser(sub: object) -> None:
    """Register standalone catalog commands.

    Args:
        sub: Existing argparse subcommand collection.
    """
    for name in sorted(COMMANDS):
        parser = sub.add_parser(name)
        parser.add_argument("--catalog-root", required=True)
        if name == "catalog-list":
            continue
        parser.add_argument("--backend", choices=["neo4j"], default="neo4j")
        parser.add_argument("--repository-id", required=True)
        parser.add_argument("--source-sha", required=True)
        parser.add_argument("--candidate", required=True)
        parser.add_argument("--root")
        if name == "query-register":
            parser.add_argument("--allow-catalog-write", action="store_true")
            parser.add_argument("--expected-active-digest")


async def run(args: object) -> dict:
    """Verify actual queries and activate only when the caller explicitly selects writes.

    Args:
        args: Parsed standalone CLI options.

    Returns:
        Catalog descriptors or measured proof/activation receipt.
    """
    catalog = QueryCatalog(args.catalog_root)
    if args.command == "catalog-list":
        return {"status": "ok", "queries": catalog.descriptors()}
    if args.command == "query-register" and not args.allow_catalog_write:
        invalid("query registration requires explicit --allow-catalog-write")
    try:
        candidate = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise CatalogIOError("candidate_read") from exc
    config = KnowledgeConfig(
        backend=args.backend,
        repository_id=args.repository_id,
        repository_root=args.root,
        query_catalog_root=args.catalog_root,
    )
    retriever = build_retriever(config)
    port = build_query_admission(config, retriever)
    try:
        if args.command == "query-register":
            return await port.verify_and_activate(
                candidate,
                repository_id=args.repository_id,
                source_sha=args.source_sha,
                expected_active_digest=args.expected_active_digest,
            )
        return await port.verify(
            candidate, repository_id=args.repository_id, source_sha=args.source_sha
        )
    finally:
        await retriever.close()
