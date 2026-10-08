"""Read native changelog fields, retaining auditable historical emitter defects.

BUSINESS CONTEXT: KM-400a-3-i exposes complete authored fields in the graph.
ARCHITECTURE: Strict YAML is authoritative. Two failing emitter shapes alone have
literal compatibility readers; graph publication remains outside this module.
An entry with no frontmatter, or an empty one, fails with its source and reason.
"""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

import yaml

from knowledge.native_types.common import NativeRecord, frontmatter, read_json, read_text, relative


def _stores(root: Path) -> list[Path]:
    """Use deployed configuration first, then its development source declaration."""
    directory = "changelogs"
    for prefix in ("leafcutter/", ""):
        config = root / (prefix + "templates/scripts/commit_guardian/commit_guardian.json")
        relative(root, config)
        if config.exists():
            value = read_json(config)
            if not isinstance(value, dict):
                raise ValueError("changelog configuration must be an object")
            directory = value.get("changelogs_dir", "changelogs")
            break
    if not isinstance(directory, str) or not directory.strip():
        raise ValueError("changelogs_dir must be a nonempty string")
    paths = [root / directory, root / "docs/changelog"]
    for path in paths:
        relative(root, path)
        if path.exists() and not path.is_dir():
            raise ValueError(f"changelog store must be a directory: {relative(root, path)}")
    return paths


def _parts(path: Path, source: str) -> tuple[str, str]:
    """Keep exact frontmatter and body with only whole-line delimiters recognized.

    An entry without a frontmatter block (including an empty file) is malformed:
    it fails with its source instead of becoming an empty record.
    """
    text = read_text(path)
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != "---":
        raise ValueError(f"malformed changelog {source}: no frontmatter block")
    end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if end is None:
        raise ValueError(f"unclosed changelog frontmatter: {path.name}")
    return "".join(lines[1:end]), "".join(lines[end + 1 :])


def _field_span(lines: list[str], field: str) -> tuple[int, int] | None:
    starts = [i for i, line in enumerate(lines) if re.match(rf"^{field}:", line)]
    if len(starts) != 1:
        return None
    start = starts[0]
    end = next(
        (i for i in range(start + 1, len(lines)) if lines[i] and not lines[i][0].isspace()),
        len(lines),
    )
    return start, end


def _literal_description(fragment: str) -> str | None:
    """Invert only the emitter's quote escaping; every backslash remains literal."""
    match = re.fullmatch(r'description: "(.*)"\r?\n?', fragment)
    if match is None:
        return None
    value = match[1]
    if any(char == '"' and (i == 0 or value[i - 1] != "\\") for i, char in enumerate(value)):
        return None
    return value.replace('\\"', '"')


def _literal_migration_list(fragment: str) -> list[str] | None:
    """Accept the emitter's simple two-space dash lines, never YAML continuations."""
    lines = fragment.splitlines()
    if not lines or not re.fullmatch(r"migration_steps:[ \t]*", lines[0]):
        return None
    values = []
    for line in lines[1:]:
        if not line.startswith("  - "):
            return None
        value = line[4:]
        # A nested collection, tag, quote or block scalar needs YAML semantics;
        # compatibility parsing cannot unambiguously reconstruct its intent.
        if not value or value[0].isspace() or value[0] in "|>[{'\"&*!?%-":
            return None
        values.append(value)
    return values or None


def _recover(raw: str, error: yaml.YAMLError, source: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Recover the failing field only; siblings must still parse as strict YAML."""
    lines = raw.splitlines(keepends=True)
    mark = getattr(error, "problem_mark", None)
    problem = getattr(error, "problem", "") or ""
    context = getattr(error, "context", "") or ""
    candidate = None
    if "unknown escape character" in problem and "double-quoted scalar" in context:
        candidate = ("description", "emitter_literal_description", _literal_description)
    elif problem == "mapping values are not allowed here":
        candidate = ("migration_steps", "emitter_literal_migration_list", _literal_migration_list)
    field = candidate[0] if candidate else "frontmatter"
    failure = f"unsupported malformed changelog {source}, field {field}"
    if candidate is None or mark is None:
        raise ValueError(failure) from error
    span = _field_span(lines, field)
    if span is None or not span[0] <= mark.line < span[1]:
        raise ValueError(failure) from error
    start, end = span
    fragment = "".join(lines[start:end])
    value = candidate[2](fragment)
    if value is None:
        raise ValueError(failure) from error
    rewritten = "".join(lines[:start]) + field + ": null\n" + "".join(lines[end:])
    try:
        metadata = yaml.safe_load(rewritten)
    except yaml.YAMLError as sibling_error:
        raise ValueError(failure + "; another field is malformed") from sibling_error
    if not isinstance(metadata, dict):
        raise ValueError(failure)
    metadata[field] = value
    return metadata, {
        "mode": "compatibility",
        "field": field,
        "rule": candidate[1],
        "raw_fragment": fragment,
        # This safe_load exception contains <unicode string>, line and column,
        # never the temporary checkout path used by common.frontmatter's wrapper.
        "original_error": str(error),
    }


def extract(root: Path) -> list[NativeRecord]:
    """Read each current and legacy entry once without applying today's write rules."""
    sources = {}
    for store in _stores(root):
        if store.exists():
            for path in store.glob("*.md"):
                source = relative(root, path)
                if path.is_file() and path.name.casefold() not in {"readme.md", "index.md"}:
                    sources[path.resolve()] = source
    records = []
    for path, source in sorted(sources.items(), key=lambda item: item[1]):
        raw, body = _parts(path, source)
        try:
            metadata, _ = frontmatter(path)
            parsing = {"mode": "strict"}
        except ValueError as error:
            if not isinstance(error.__cause__, yaml.YAMLError):
                raise ValueError(f"invalid changelog frontmatter: {source}") from error
            metadata, parsing = _recover(raw, error.__cause__, source)
        # A blank or comment-only block parses to None, which frontmatter() reports as {};
        # an authored empty mapping ({}) stays a valid, distinct value.
        if not metadata and yaml.safe_load(raw) is None:
            raise ValueError(f"malformed changelog {source}: empty frontmatter")
        title = metadata.get("title")
        description = metadata.get("description")
        if not isinstance(description, str):
            description = metadata.get("summary")
        records.append(
            NativeRecord(
                kind="ChangelogEntry",
                native_id=source,
                source_path=source,
                metadata=metadata,
                title=title if isinstance(title, str) and title else path.stem,
                description=description if isinstance(description, str) else "",
                derived={"body": body, "frontmatter_raw": raw, "parsing": parsing},
            )
        )
    return records


# DECISION HISTORY
# ================================================================================
# - 2026-10-06 12:00 [python-coder]: A changelog with no frontmatter block, or an empty
#   one, fails with its source and reason instead of becoming an empty record
#   (KM-400a-1-xiii; TICKET-20261006-KnowledgeRealCorpusTestsDeriveCensus).
