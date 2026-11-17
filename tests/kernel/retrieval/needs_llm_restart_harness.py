"""Fresh-process kernel seam harness with a clearly scripted host responder."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from integrations.retrieval_needs_llm import make_experiment_service
from tests.kernel.retrieval.test_retrieval_needs_llm import ROOT, begin, controlled_response, submission


async def run(args):
    if args.action == "start":
        service, envelope, packet, body = await begin(args.run_root)
        try:
            output = {"envelope": envelope.model_dump(mode="json"),
                      "submission": submission(envelope, packet, controlled_response(body["request"]))}
        finally:
            await service._env.aclose()
    else:
        saved = json.loads(args.input.read_text(encoding="utf-8"))
        service = make_experiment_service(ROOT, args.run_root)
        try:
            final = await service.resume_run(saved["envelope"]["run_id"], saved["submission"])
            output = final.model_dump(mode="json")
        finally:
            await service._env.aclose()
    args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("start", "resume"))
    parser.add_argument("--run-root", type=Path, required=True)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
