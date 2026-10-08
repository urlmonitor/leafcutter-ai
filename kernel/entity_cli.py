"""MODULE: kernel.entity_cli
GOAL: Explicit local entity-index maintenance without a runtime provider environment.
BUSINESS CONTEXT: Preparing meanings is a user-invoked operation, never an intake fallback.
ARCHITECTURE: Small CLI adapter around build_entity_index; one JSON result, no secrets.
"""

import logging
from pathlib import Path

from kernel.config import ConfigError, load_kernel_config
from kernel.entity_index import build_entity_index

logger = logging.getLogger(__name__)


def add_parser(commands) -> None:
    """Register entities build and its repository/configuration/output inputs."""
    parser = commands.add_parser("entities", help="prepare local entity meanings")
    verbs = parser.add_subparsers(dest="entity_command", required=True)
    build = verbs.add_parser("build", help="explicitly rebuild the local entity index")
    build.add_argument("--repository-root", type=Path, required=True)
    build.add_argument("--config", type=Path)
    build.add_argument("--output", type=Path)


def run(args) -> tuple[int, dict]:
    """Prepare metadata and report its identity, reader coverage and destination."""
    try:
        config = load_kernel_config(args.config)
        index = build_entity_index(args.repository_root, config, output_path=args.output)
    except (OSError, ValueError, ConfigError) as exc:
        logger.warning("entity index preparation failed: %s", type(exc).__name__)
        return 5, {"error": {"code": "entity_index_failed", "message": str(exc)}}
    return 0, {"kind": index.kind, "schema_version": index.schema_version,
               "repository_root": index.repository_root, "fingerprint": index.fingerprint,
               "entity_count": len(index.entries), "coverage": index.coverage,
               "limitations": index.limitations}

# DECISION HISTORY
# ================================================================================
# - 2026-10-03 15:05 [python-coder]: Keep pre-intent meanings deterministic, scoped and separate from task evidence. (#TICKETLESS reason=user-approved-ac-first-DK300)
