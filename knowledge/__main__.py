"""Standalone JSON CLI; no kernel initialization.
MODULE: knowledge.__main__
GOAL: Provide the scoped knowledge retrieval __main__ responsibility.
BUSINESS CONTEXT: Make attributable research capabilities reusable and explicitly governed.
ARCHITECTURE: Dependencies point inward to neutral contracts; see docs/architecture/components/knowledge-retrieval.md.
"""

from __future__ import annotations

from .errors import invalid, KnowledgeError

import argparse
import asyncio
import json
import sys
from pathlib import Path
from .config import KnowledgeConfig, build_retriever
from .contracts import KnowledgeRetrievalRequest


async def run(args: object, *, observer: object | None = None) -> dict:
    """Execute one standalone JSON command and release owned resources.

    Args:
        args: Parsed standalone command arguments.

    Returns:
        dict: JSON-compatible outcome of the selected standalone command.
    """
    from .cli_catalog import COMMANDS, run as catalog_run

    if args.command == "compare":
        from .evaluation_comparison import compare_reports

        baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        proposal = json.loads(Path(args.proposal).read_text(encoding="utf-8"))
        gates = json.loads(Path(args.gates).read_text(encoding="utf-8")) if args.gates else None
        return compare_reports(baseline, proposal, gates)
    if args.command == "assess":
        from .assessments import assess

        payload = json.loads(Path(args.request).read_text(encoding="utf-8"))
        if payload.get("repository_id") != args.repository_id:
            invalid("assessment repository differs from configured scope")
        return assess(payload)
    if args.command in COMMANDS:
        return await catalog_run(args)
    if args.command in {"capabilities", "retrieve", "evaluate"}:
        config = KnowledgeConfig(
            backend=args.backend,
            repository_id=args.repository_id,
            repository_root=args.root,
            query_catalog_root=getattr(args, "catalog_root", None),
            embeddings_enabled=args.embeddings,
            embedding_model=args.embedding_model,
            embedding_dimensions=args.embedding_dimensions,
        )
        retriever = (
            build_retriever(config, observer=observer)
            if observer is not None
            else build_retriever(config)
        )
        try:
            if args.command == "capabilities":
                return await retriever.capabilities()
            if args.command == "evaluate":
                from .evaluation import evaluate

                cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
                if any(
                    case.get("request", case.get("assessment", {})).get(
                        "repository_id", args.repository_id
                    )
                    != args.repository_id
                    for case in (cases.get("cases", []) if isinstance(cases, dict) else cases)
                ):
                    invalid("evaluation repository differs from configured scope")
                from .query_catalog import QueryCatalog

                catalog = QueryCatalog(args.catalog_root) if args.catalog_root else None
                return await evaluate(retriever, cases, query_catalog=catalog)
            text = (
                Path(args.request).read_text(encoding="utf-8")
                if args.request != "-"
                else sys.stdin.read()
            )
            from .query_catalog import QueryCatalog

            request = (
                QueryCatalog(args.catalog_root).request(json.loads(text))
                if getattr(args, "catalog_root", None)
                else KnowledgeRetrievalRequest.model_validate_json(text)
            )
            if request.repository_id != args.repository_id:
                invalid("request repository differs from configured authorized scope")
            return (await retriever.retrieve(request)).model_dump(mode="json")
        finally:
            await retriever.close()
    from .cli_sync import run as sync_run

    return await sync_run(args)


def main(*, observer: object | None = None) -> int:
    """Main.

    Returns:
        int: Zero for successful commands or two for typed/configuration failures.
    """
    parser = argparse.ArgumentParser(description="Standalone knowledge retrieval")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("capabilities", "retrieve", "evaluate"):
        p = sub.add_parser(name)
        p.add_argument("--backend", choices=["none", "neo4j"], default="none")
        p.add_argument("--repository-id", default="leafcutter")
        p.add_argument("--root", default=None)
        p.add_argument("--catalog-root", default=None)
        p.add_argument("--embeddings", action="store_true")
        p.add_argument("--embedding-model")
        p.add_argument("--embedding-dimensions", type=int)
        if name == "retrieve":
            p.add_argument("--request", required=True)
        if name == "evaluate":
            p.add_argument("--cases", required=True)
    comparison = sub.add_parser("compare")
    comparison.add_argument("--baseline", required=True)
    comparison.add_argument("--proposal", required=True)
    comparison.add_argument("--gates")
    assessment = sub.add_parser("assess")
    assessment.add_argument("--repository-id", default="leafcutter")
    assessment.add_argument("--request", required=True)
    from .cli_sync import add_parser

    add_parser(sub)
    from .cli_catalog import add_parser as add_catalog_parser

    add_catalog_parser(sub)
    args = parser.parse_args()
    try:
        result = asyncio.run(run(args, observer=observer))
        print(json.dumps(result, ensure_ascii=False))
        if result.get("status") in {"unavailable", "unsupported", "error", "stale"}:
            return 2
    except KnowledgeError as exc:
        print(
            json.dumps({"status": exc.code, "retryable": exc.retryable, "message": str(exc)}),
            file=sys.stderr,
        )
        return 2
    except ImportError:
        print(
            json.dumps(
                {
                    "status": "unavailable",
                    "message": "selected backend optional dependency is not installed",
                }
            ),
            file=sys.stderr,
        )
        return 2
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 15:46 [python-coder]: Bind verified reusable query versions through scoped retrieval. (#KM-500/TICKET-20261001-KM-500b-3)

# - 2026-10-01 [python-coder]: Preserve question evidence and explicit source support through bounded research. (#KM-500/KM-500e-2)
