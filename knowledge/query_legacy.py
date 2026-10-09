"""Validate frozen compiler-v1 catalog receipts; never execute this legacy output.

DECISION HISTORY
- 2026-10-09 09:11 [python-coder]: Emit native queries while preserving versioned catalog admission identities. (#KM-400a-3-i/TICKET-20261009-KM-400a-3-i-native-query-maintenance)
- 2026-10-01 15:46 [python-coder]: New multi-relation queries compile through a trusted grammar. (#KM-500/TICKET-20261001-KM-500b-2)

MODULE: knowledge.query_legacy
GOAL: Reproduce historical bytes solely to verify immutable admitted catalog records.
BUSINESS CONTEXT: Make attributable research capabilities reusable and explicitly governed.
ARCHITECTURE: Dependencies point inward to neutral contracts; see docs/architecture/components/knowledge-retrieval.md.
"""

from __future__ import annotations

import hashlib
import json
from .query_models import QueryDescriptor


def digest_data(data: object) -> str:
    """Hash deterministic JSON data.

    Args:
        data: JSON-serializable descriptor or verification record.

    Returns:
        Hexadecimal content digest.
    """
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def predicates(variable: str, kind: str | None, filters: dict, prefix: str) -> list[str]:
    """Build predicates from allowlisted properties and compiler-owned variable names.

    Args:
        variable: Compiler-generated node variable.
        kind: Optional declared kind.
        filters: Model-validated property to argument references.
        prefix: Compiler-generated constant parameter prefix.

    Returns:
        Parameterized predicate fragments.
    """
    result = [f"{variable}.kind=${prefix}_kind"] if kind else []
    result += [
        f"($arg_{name} IS NULL OR {variable}.{prop}=$arg_{name})"
        for prop, name in sorted(filters.items())
    ]
    return result


def compile_legacy_query(descriptor: QueryDescriptor) -> dict:
    """Reproduce version-1 bytes for catalog integrity validation only.

    Args:
        descriptor: Validated authored operation, never executable text.

    Returns:
        Compiled query, constant parameters and immutable content digest.
    """
    recipe = descriptor.recipe
    conditions = predicates("n0", recipe.seed_kind, recipe.filters, "seed")
    statement = f"UNWIND $arg_{recipe.seed_parameter} AS seed_id MATCH (n0:KREntity {{generation_key:$scope_key,canonical_id:seed_id}})"
    if conditions:
        statement += " WHERE " + " AND ".join(conditions)
    statement += " WITH DISTINCT n0 ORDER BY n0.canonical_id LIMIT $seed_limit "
    constants = {"seed_kind": recipe.seed_kind, "seed_limit": 20, "fanout": 10}
    statement += (
        "WITH collect(n0) AS seeds UNWIND CASE WHEN size(seeds)=0 THEN [null] ELSE seeds END AS n0 "
    )
    flags = []
    for index, step in enumerate(recipe.steps):
        previous, node, rel = f"n{index}", f"n{index + 1}", f"r{index}"
        arrow = f"<-[{rel}:KR_LINK]-" if step.direction == "incoming" else f"-[{rel}:KR_LINK]->"
        where = [f"{rel}.generation_key=$scope_key", f"{rel}.edge_type=$step_{index}_edge"]
        where += predicates(node, step.kind, step.filters, f"step_{index}")
        statement += (
            f"CALL {{ WITH {previous} MATCH ({previous}){arrow}({node}:KREntity {{generation_key:$scope_key}}) WHERE "
            + " AND ".join(where)
        )
        statement += f" WITH DISTINCT {node} ORDER BY {node}.canonical_id LIMIT $probe_fanout RETURN collect({node}) AS hits{index} }} "
        statement += f"WITH *, size(hits{index})>$fanout AS clipped{index} UNWIND CASE WHEN size(hits{index})=0 THEN [null] ELSE hits{index}[..$fanout] END AS {node} "
        flags.append(f"clipped{index}")
        constants.update({f"step_{index}_edge": step.edge_type, f"step_{index}_kind": step.kind})
    final = f"n{len(recipe.steps)}"
    clipped = " OR ".join(flags) or "false"
    statement += f"WITH {final}, max(CASE WHEN {clipped} THEN 1 ELSE 0 END) AS clipped ORDER BY {final}.canonical_id "
    statement += f"WITH collect({final}) AS found, max(clipped) AS clipped RETURN [n IN found[..$result_limit] | n.payload] AS payloads, (clipped=1 OR size(found)>$result_limit) AS expansion_truncated"
    result = {"cypher": statement, "constants": constants, "compiler_version": "1"}
    result["digest"] = digest_data({"descriptor": descriptor.model_dump(), **result})
    return result
