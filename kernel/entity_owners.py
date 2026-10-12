"""MODULE: kernel.entity_owners
GOAL: Build narrow meaning projections using trusted native readers and Python AST.
BUSINESS CONTEXT: A declaration or title explains identity without exposing implementation.
ARCHITECTURE: Called only by explicit index preparation; scope code is never imported.
"""

from __future__ import annotations

import ast
import hashlib
import json
import logging
from pathlib import Path

from knowledge.native_types import registry
from knowledge.native_types import acceptance_criterion, adr, component, decision, flow, glossary_term, ticket
from knowledge.native_types.registry import LABELS, ROLE_DESCRIPTIONS
from kernel.entity_records import bounded_meaning

logger = logging.getLogger(__name__)
PACKAGE_REGISTRY = Path(registry.__file__)
_READERS = {"GlossaryTerm": glossary_term.extract, "AcceptanceCriterion": acceptance_criterion.extract,
            "ADR": adr.extract, "Component": component.extract, "Decision": decision.extract,
            "Flow": flow.extract, "Ticket": ticket.extract}


def native_projections(root: Path, limit: int) -> tuple[list[dict], dict[str, str], dict, dict]:
    """Read canonical owners, retaining only identity, title or glossary definition."""
    result: list[dict] = []
    coverage = {"glossary": "current", "artifact_id": "current"}
    statuses, dependencies = {}, {}
    for kind, extract in _READERS.items():
        family = "glossary" if kind == "GlossaryTerm" else "artifact_id"
        statuses[kind] = "current"
        try:
            records = extract(root)
        except (OSError, ValueError, ImportError) as exc:
            logger.warning("entity owner %s unavailable: %s", kind, type(exc).__name__)
            coverage[family] = "partial"
            statuses[kind] = "partial"
            continue
        if kind == "AcceptanceCriterion":
            dependencies[kind] = [entry["path"] for record in records
                                  for entry in record.metadata.get("declared_files", [])
                                  if isinstance(entry, dict) and isinstance(entry.get("path"), str)]
        for record in records:
            text = record.metadata["definition"] if family == "glossary" else record.title
            fragment = record.locator
            locator = record.source_path + (fragment if fragment.startswith("#") else
                                           "#" + fragment if fragment else "")
            result.append({"family": family, "identity": record.native_id,
                "native_kind": kind, "meaning": bounded_meaning(text, limit),
                "names": [record.title] if family == "glossary" else [record.native_id],
                "path": record.source_path, "locator": locator})
    return result, coverage, statuses, dependencies


def vocabulary_projections(root: Path, limit: int) -> tuple[list[dict], dict[str, str], dict]:
    """Read declared vocabulary memberships, aliases and owner-authored descriptions."""
    result, coverage, patterns = [], {}, {}
    patterns.update({"Flow": flow._IDENTITY.pattern,
                     "Ticket": r"tickets/(?:[\w.-]+/)*[\w.-]+\.md"})
    for filename, family, collection in (("doc_types.json", "doc_type", "doc_types"),
                                        ("entry_kind_vocabulary.json", "entry_kind", "members")):
        path = root / "config" / filename
        try:
            values = json.loads(path.read_text(encoding="utf-8"))[collection]
        except (OSError, ValueError, KeyError, TypeError) as exc:
            logger.warning("entity vocabulary %s unavailable: %s", family, type(exc).__name__)
            coverage[family] = "unavailable"
            continue
        coverage[family] = "current"
        for name, value in values.items():
            if value.get("alias_of"):
                continue
            aliases = [key for key, row in values.items() if row.get("alias_of") == name]
            aliases += value.get("aliases", [])
            meaning = value.get("description", "")
            if not meaning:
                coverage[family] = "partial"
                continue
            rel = path.relative_to(root).as_posix()
            result.append({"family": family, "identity": name, "meaning": bounded_meaning(meaning, limit),
                "names": [name, *aliases], "aliases": aliases, "path": rel,
                "locator": f"{rel}#/{collection}/{name}"})
    try:
        schema = json.loads((Path(__file__).resolve().parents[1] / "config/ac_store_schema.json").read_text(encoding="utf-8"))
        patterns["AcceptanceCriterion"] = schema["properties"]["id"]["pattern"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        logger.warning("entity AC syntax unavailable: %s", type(exc).__name__)
    # These roles come from the reviewed package reader, not repository executable code.
    rel = "config/paths.json"
    coverage["native_kind"] = "current" if (root / rel).is_file() else "unavailable"
    if coverage["native_kind"] == "current":
        package_hash = hashlib.sha256(PACKAGE_REGISTRY.read_bytes()).hexdigest()
        for kind, label in LABELS.items():
            result.append({"family": "native_kind", "identity": kind, "native_kind": kind,
                "meaning": bounded_meaning(ROLE_DESCRIPTIONS[kind], limit), "names": list(dict.fromkeys([kind, label])),
                "aliases": [label] if label != kind else [], "path": rel,
                "package_source": True, "source_hash": package_hash,
                "locator": f"package:knowledge/native_types/registry.py#ROLE_DESCRIPTIONS/{kind}"})
    return result, coverage, patterns


def _signature(node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Render declaration syntax without inspecting or serializing its body."""
    if isinstance(node, ast.ClassDef):
        bases = ", ".join(ast.unparse(base) for base in node.bases)
        return f"class {node.name}({bases})" if bases else f"class {node.name}"
    prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
    returns = " -> " + ast.unparse(node.returns) if node.returns else ""
    return f"{prefix} {node.name}({ast.unparse(node.args)}){returns}"


def symbol_projections(relative: str, text: str, limit: int) -> list[dict]:
    """Project top-level Python declarations and class methods through AST only."""
    tree = ast.parse(text)
    module = relative.removesuffix(".py").replace("/", ".")
    result = []

    def visit(nodes: list[ast.stmt], parent: str = "") -> None:
        """Visit declared module/class members, without inferring dynamic exports."""
        for node in nodes:
            if not isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            name = parent + node.name
            identity = module + "." + name
            result.append({"family": "symbol", "identity": identity, "path": relative,
                "locator": relative + "::" + name,
                "names": list(dict.fromkeys([identity, relative + "::" + name, name, node.name])),
                "meaning": bounded_meaning(ast.get_docstring(node) or "", limit),
                "signature": _signature(node)[:limit]})
            if isinstance(node, ast.ClassDef):
                visit(node.body, name + ".")

    visit(tree.body)
    return result

# DECISION HISTORY
# ================================================================================
# - 2026-10-03 15:05 [python-coder]: Keep pre-intent meanings deterministic, scoped and separate from task evidence. (#TICKETLESS reason=user-approved-ac-first-DK300)
# - 2026-10-03 17:00 [python-coder]: Register trusted native readers statically and retain owner-specific Flow and Ticket reference syntax. (#DK-300/entity-context)
# - 2026-10-03 20:00 [python-coder]: Include canonical Component identities for permission-checked graph targets. (#TICKETLESS reason=user-approved-DK300-graph-routing)
