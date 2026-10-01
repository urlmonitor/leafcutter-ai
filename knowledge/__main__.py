"""Standalone JSON CLI; no kernel initialization."""

from __future__ import annotations

from .errors import invalid, KnowledgeError

import argparse
import asyncio
import json
import sys
from pathlib import Path
from .config import KnowledgeConfig, build_retriever
from .contracts import KnowledgeRetrievalRequest


async def run(args: object) -> dict:
    """Execute one standalone JSON command and release owned resources.

    Args:
        args: Parsed standalone command arguments.

    Returns:
        dict: JSON-compatible outcome of the selected standalone command.
    """
    if args.command in {"capabilities", "retrieve", "evaluate"}:
        config = KnowledgeConfig(
            backend=args.backend,
            repository_id=args.repository_id,
            repository_root=args.root,
            embeddings_enabled=args.embeddings,
            embedding_model=args.embedding_model,
            embedding_dimensions=args.embedding_dimensions,
        )
        retriever = build_retriever(config)
        try:
            if args.command == "capabilities":
                return await retriever.capabilities()
            if args.command == "evaluate":
                from .evaluation import evaluate

                cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
                if any(case["request"]["repository_id"] != args.repository_id for case in cases):
                    invalid("evaluation repository differs from configured scope")
                return await evaluate(retriever, cases)
            text = (
                Path(args.request).read_text(encoding="utf-8")
                if args.request != "-"
                else sys.stdin.read()
            )
            request = KnowledgeRetrievalRequest.model_validate_json(text)
            if request.repository_id != args.repository_id:
                invalid("request repository differs from configured authorized scope")
            return (await retriever.retrieve(request)).model_dump(mode="json")
        finally:
            await retriever.close()
    from .cli_sync import run as sync_run

    return await sync_run(args)


def main() -> int:
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
        p.add_argument("--embeddings", action="store_true")
        p.add_argument("--embedding-model")
        p.add_argument("--embedding-dimensions", type=int)
        if name == "retrieve":
            p.add_argument("--request", required=True)
        if name == "evaluate":
            p.add_argument("--cases", required=True)
    from .cli_sync import add_parser

    add_parser(sub)
    args = parser.parse_args()
    try:
        result = asyncio.run(run(args))
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
