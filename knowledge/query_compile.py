"""Compile a restricted authored recipe into actual scoped parameterized Cypher.

DECISION HISTORY
- 2026-10-09 09:46 [python-coder]: Remove obsolete compiler compatibility after explicit native saved-catalog re-admission. (#KM-400a-3-i/TICKET-20261009-KM-400a-3-i-native-query-maintenance)
- 2026-10-09 09:11 [python-coder]: Emit native queries while preserving versioned catalog admission identities. (#KM-400a-3-i/TICKET-20261009-KM-400a-3-i-native-query-maintenance)
- 2026-10-01 15:46 [python-coder]: New multi-relation queries compile through a trusted grammar. (#KM-500/TICKET-20261001-KM-500b-2)

MODULE: knowledge.query_compile
GOAL: Provide the scoped knowledge retrieval query_compile responsibility.
BUSINESS CONTEXT: Make attributable research capabilities reusable and explicitly governed.
ARCHITECTURE: Dependencies point inward to neutral contracts; see docs/architecture/components/knowledge-retrieval.md.
"""

from __future__ import annotations

import hashlib
import json
from .query_models import QueryDescriptor
from .errors import invalid

COMPILER_VERSION = "2"
# Digest-bearing vocabulary is frozen per compiler version. Registry growth must
# introduce a new compiler version and re-admit saved catalogs with fresh evidence.
COMPILER_LABELS = {
    "AcceptanceCriterion": "AC",
    "ADR": "ADR",
    "Component": "Component",
    "Agent": "Agent",
    "Skill": "Skill",
    "Ticket": "Ticket",
    "Document": "Document",
    "RoadmapPhase": "RoadmapPhase",
    "GlossaryTerm": "GlossaryTerm",
    "Flow": "Flow",
    "Mockup": "Mockup",
    "MockData": "MockData",
    "ChangelogEntry": "ChangelogEntry",
    "Capability": "Capability",
    "Decision": "Decision",
    "SourceFile": "SourceFile",
    "Test": "Test",
    "Lesson": "Lesson",
}
COMPILER_RELATIONSHIPS = {
    "component_membership": "COMPONENT_MEMBERSHIP",
    "covered_by": "COVERED_BY",
    "implemented_by": "IMPLEMENTED_BY",
    "depends_on": "DEPENDS_ON",
    "related_docs": "RELATED_DOCS",
    "ABOUT": "ABOUT",
    "CORRECTED_BY": "CORRECTED_BY",
    "TAUGHT": "TAUGHT",
    "USED_EVIDENCE": "USED_EVIDENCE",
}
COMPILER_NODE_LABELS = "|".join(COMPILER_LABELS.values())


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


def native_label(kind: str | None) -> str:
    """Resolve syntax exclusively from the immutable compiler-owned vocabulary.

    Args:
        kind: Validated semantic kind, or no kind constraint.

    Returns:
        A trusted native label or the frozen native label union.
    """
    if kind is None:
        return COMPILER_NODE_LABELS
    label = COMPILER_LABELS.get(kind)
    if label is None:
        invalid("query kind requires a newer compiler version")
    return label


def compile_query(descriptor: QueryDescriptor) -> dict:
    """Produce bounded Cypher and a digest over its full input contract.

    Args:
        descriptor: Validated authored operation, never executable text.

    Returns:
        Compiled query, constant parameters and immutable content digest.
    """
    recipe = descriptor.recipe
    conditions = predicates("n0", recipe.seed_kind, recipe.filters, "seed")
    seed_label = native_label(recipe.seed_kind)
    statement = f"UNWIND $arg_{recipe.seed_parameter} AS seed_id MATCH (n0:{seed_label} {{generation_key:$scope_key,canonical_id:seed_id}})"
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
        edge_label = COMPILER_RELATIONSHIPS.get(step.edge_type)
        if edge_label is None:
            invalid("query relationship requires a newer compiler version")
        node_label = native_label(step.kind)
        arrow = (
            f"<-[{rel}:{edge_label}]-"
            if step.direction == "incoming"
            else f"-[{rel}:{edge_label}]->"
        )
        where = [f"{rel}.generation_key=$scope_key", f"{rel}.edge_type=$step_{index}_edge"]
        where += predicates(node, step.kind, step.filters, f"step_{index}")
        statement += (
            f"CALL {{ WITH {previous} MATCH ({previous}){arrow}({node}:{node_label} {{generation_key:$scope_key}}) WHERE "
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
    result = {"cypher": statement, "constants": constants, "compiler_version": COMPILER_VERSION}
    result["digest"] = digest_data({"descriptor": descriptor.model_dump(), **result})
    return result
