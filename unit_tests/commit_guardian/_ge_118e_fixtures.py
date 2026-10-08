"""
MODULE: _ge_118e_fixtures
GOAL: Private helpers for test_ge_118e.py -- extract the machine-marked
    examples from the two GE-118e documents and run the real
    check_doc_frontmatter.py guard over each one.
BUSINESS CONTEXT: AC GE-118e makes the document-frontmatter reference and the
    pre-commit-hooks guide EXECUTABLE DOCUMENTATION: every example is a fenced
    block marked ``yaml accepted`` or ``yaml refused`` and a test runs it
    through the guard. A ``yaml refused`` block is followed immediately by a
    ``text`` block quoting the guard's actual refusal line(s).
ARCHITECTURE: Pure extraction (no I/O beyond reading the document) plus one
    subprocess runner. Never falls back to a literal on failure -- a missing
    file or an unparseable block fails the test through ``fail()``.
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTMATTER_DOC = REPO_ROOT / "templates" / "docs" / "architecture" / "FRONTMATTER.md"
README_DOC = REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "README.md"
GUARD = REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_doc_frontmatter.py"
VALIDATORS = REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "frontmatter_validators.py"
BASE_DOC = REPO_ROOT / "docs" / "reference" / "ac-schema.md"

PATH_FIELD_NAMES = ("related_docs", "related_code", "architecture_diagrams")

_FENCE_OPEN = re.compile(r"^\s*```(.*)$")
_FENCE_CLOSE = re.compile(r"^\s*```\s*$")


def fail(message: str, cause: BaseException | None = None) -> None:
    """Fail the calling test with *message* (chained to *cause* when given)."""
    raise AssertionError(message) from cause


@dataclass(frozen=True)
class Example:
    """One marked example lifted out of a document."""

    kind: str  # "accepted" or "refused"
    mapping: dict
    refusal_lines: tuple  # stripped lines of the following ``text`` block
    source: str
    line: int


def _fenced_blocks(text: str) -> list[tuple[str, str, int]]:
    """Return every fenced block as (info string, body, 1-based opening line)."""
    blocks: list[tuple[str, str, int]] = []
    info = None
    start = 0
    body: list[str] = []
    for number, raw in enumerate(text.splitlines(), start=1):
        if info is None:
            match = _FENCE_OPEN.match(raw)
            if match:
                info = match.group(1).strip()
                start = number
                body = []
        elif _FENCE_CLOSE.match(raw):
            blocks.append((info, "\n".join(body), start))
            info = None
        else:
            body.append(raw)
    return blocks


def read_document(path: Path) -> str:
    """Read a document; an unreadable one fails the test (never swallowed)."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"cannot read document under test {path}: {exc}", exc)
    return ""


def _parse_block(path: Path, info: str, body: str, line: int) -> dict:
    try:
        mapping = yaml.safe_load(body)
    except yaml.YAMLError as exc:
        fail(f"{path.name}:{line}: '{info}' block does not parse standalone: {exc}", exc)
    if not isinstance(mapping, dict):
        fail(
            f"{path.name}:{line}: '{info}' block must be a YAML mapping of "
            f"frontmatter fields, got {type(mapping).__name__}"
        )
    return mapping


def extract_examples(path: Path) -> list[Example]:
    """Extract every ``yaml accepted`` / ``yaml refused`` block from *path*.

    Any other fenced block is ignored. A ``yaml refused`` block must be
    followed IMMEDIATELY by a ``text`` block (the quoted guard output).
    """
    blocks = _fenced_blocks(read_document(path))
    examples: list[Example] = []
    for index, (info, body, line) in enumerate(blocks):
        if info not in ("yaml accepted", "yaml refused"):
            continue
        kind = info.split()[1]
        mapping = _parse_block(path, info, body, line)
        refusal: tuple = ()
        if kind == "refused":
            following = blocks[index + 1] if index + 1 < len(blocks) else None
            if following is None or following[0] != "text":
                fail(
                    f"{path.name}:{line}: 'yaml refused' block is not immediately "
                    f"followed by a 'text' block quoting the guard's refusal message"
                )
            refusal = tuple(ln.strip() for ln in following[1].splitlines() if ln.strip())
            if not refusal:
                fail(f"{path.name}:{line}: the 'text' block after a refused example is empty")
        examples.append(Example(kind, mapping, refusal, path.name, line))
    return examples


def base_frontmatter() -> dict:
    """Required doc fields copied from a real passing doc in this repo."""
    text = read_document(BASE_DOC)
    parts = text.split("---", 2)
    if len(parts) < 3:
        fail(f"base doc {BASE_DOC} has no frontmatter")
    real = yaml.safe_load(parts[1])
    base = {key: real[key] for key in ("title", "type", "status", "created", "last_updated")}
    base["components"] = []
    return base


def _create_referenced_paths(root: Path, example: Example) -> None:
    """Create on disk every path string the example references."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from frontmatter_path_resolver import resolve_frontmatter_path_entry

    for field in PATH_FIELD_NAMES:
        entries = example.mapping.get(field)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            resolved = resolve_frontmatter_path_entry(entry, field)
            if not isinstance(resolved, str):
                continue  # a refused entry names no path to create
            target = (root / resolved).resolve()
            if root not in target.parents:
                fail(f"example path {resolved!r} escapes the fixture root")
            try:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("placeholder\n", encoding="utf-8")
            except OSError as exc:
                fail(f"cannot create {target}: {exc}", exc)


def run_guard(example: Example) -> subprocess.CompletedProcess:
    """Run the real guard, as a subprocess, over a doc built from *example*."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve()
        try:
            subprocess.run(
                ["git", "init", "-q", str(root)], check=True, capture_output=True, text=True
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            fail(f"cannot init fixture project root: {exc}", exc)
        _create_referenced_paths(root, example)
        merged = {**base_frontmatter(), **example.mapping}
        doc = root / "docs" / "ge118e_example.md"
        try:
            doc.parent.mkdir(parents=True, exist_ok=True)
            doc.write_text(
                "---\n" + yaml.safe_dump(merged, sort_keys=False) + "---\n\n# Example\n",
                encoding="utf-8",
            )
            return subprocess.run(
                ["python3", str(GUARD), "--file", str(doc)],
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            fail(f"guard subprocess failed to run: {exc}", exc)
    return subprocess.CompletedProcess([], 1)
