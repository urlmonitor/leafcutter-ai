"""
MODULE: build_shared_blocks
GOAL: Fill every empty shared-block marker pair in a workflow template from the one tracked
    source of that block, byte for byte, and resolve the commit step's published values
    inside block text.
BUSINESS CONTEXT: Workflow bodies cannot require or call each other (ADR-030), so logic several
    routes share is written once under ``templates/workflows-js/_shared/`` and copied into each
    route at install time (BO-4500b-1, generalising BO-4300c-3). A fix to a block then reaches
    every route on the next install.
ARCHITECTURE: Pure text functions, called by build_phases_workflows.py before config injection.
    The marker grammar is ``// <NAME>-START`` / ``// <NAME>-END`` on their own lines; the source
    of block NAME is ``_shared/<name lowercased>.js``. The set of blocks and the set of consumers
    are both derived (sources on disk, markers in templates) -- no name is listed in code.
    Placeholders of the form ``{{config.commit_step_*}}`` inside block text are resolved from
    ``config/commit_step.json`` of the package (BO-4500b-3), validated before anything is
    written; the file is read only when a block actually uses such a placeholder.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from template_compiler import inject_config

MARKER_RE = re.compile(r"^// ([A-Z][A-Z0-9-]*)-START[ \t]*$", re.MULTILINE)
MARKER_RE_BYTES = re.compile(rb"^// [A-Z][A-Z0-9-]*-START[ \t]*$", re.MULTILINE)
_COMMIT_STEP_PLACEHOLDER = "{{config.commit_step_"
_COMMIT_STEP_FILE = Path("config") / "commit_step.json"
HAND_KEPT_FILE = "hand-kept.json"
_FAMILIES = ("policy", "step", "check", "nothing")


class SharedBlockError(ValueError):
    """A shared-block fill or its configuration is invalid; nothing may be deployed."""


def load_commit_step_values(package_root: Path) -> dict[str, str]:
    """Return the ``commit_step_*`` placeholder values from ``config/commit_step.json``.

    Every value is a string ready for text substitution (numbers as digits, lists as JSON).
    Raises ``ValueError`` naming the setting and the file when the file is unreadable or
    ``max_transient_retries``, ``answer_version`` or ``reason_codes`` is missing or malformed.
    """
    path = package_root / _COMMIT_STEP_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        msg = (f"{path}: the commit step configuration (commit_step.json) cannot be read: {exc}")
        raise SharedBlockError(msg) from exc
    if not isinstance(data, dict):
        msg = (f"{path}: commit_step.json must hold one object")
        raise SharedBlockError(msg)
    values: dict[str, str] = {}
    for key in ("max_transient_retries", "answer_version"):
        value = data.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            msg = (
                f"{path}: {key} must be a non-negative integer in commit_step.json, got {value!r}; "
                f"no default is supplied"
            )
            raise SharedBlockError(msg)
        values[f"commit_step_{key}"] = str(value)
    codes = data.get("reason_codes")
    if not isinstance(codes, dict):
        msg = (f"{path}: reason_codes must be an object in commit_step.json")
        raise SharedBlockError(msg)
    for family in _FAMILIES:
        members = codes.get(family)
        if not isinstance(members, list) or not all(isinstance(m, str) for m in members):
            msg = (f"{path}: reason_codes.{family} must be a list of strings in commit_step.json")
            raise SharedBlockError(msg)
        values[f"commit_step_reason_codes_{family}"] = json.dumps(members)
    return values


def read_hand_kept(shared_dir: Path) -> dict[str, str]:
    """Return ``{block name: reason}`` from ``_shared/hand-kept.json`` (empty if absent).

    Raises ``SharedBlockError`` when the file is unreadable or is not one object of strings.
    """
    path = shared_dir / HAND_KEPT_FILE
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        msg = f"{path}: the hand-kept declaration cannot be read: {exc}"
        raise SharedBlockError(msg) from exc
    if not isinstance(data, dict) or not all(isinstance(v, str) and v.strip() for v in data.values()):
        msg = f"{path}: must hold one object mapping a block name to a non-empty reason"
        raise SharedBlockError(msg)
    return data


def resolve_commit_step(text: str, package_root: Path) -> str:
    """Resolve ``{{config.commit_step_*}}`` placeholders in block ``text`` (no-op without any)."""
    if _COMMIT_STEP_PLACEHOLDER in text:
        return inject_config(text, load_commit_step_values(package_root))
    return text


def _block_text(block: str, name: str, src_dir: Path, package_root: Path) -> str:
    """Return block ``block``'s source text with commit-step placeholders resolved."""
    source = src_dir / "_shared" / f"{block.lower()}.js"
    if not source.is_file():
        msg = (f"{name}: carries {block} markers but {source} is missing")
        raise SharedBlockError(msg)
    text = resolve_commit_step(source.read_text(encoding="utf-8"), package_root)
    return text if text.endswith("\n") else text + "\n"


def inline_shared_blocks(text: str, name: str, src_dir: Path, package_root: Path) -> str:
    """Fill every empty marker pair in ``text`` from its block source and return the result.

    A template without a marker pair is returned unchanged. A start marker without its end
    marker, a pair that already holds text (a hand copy) or a missing block source raises
    ``ValueError`` naming the template, so nothing is deployed.
    """
    parts: list[str] = []
    pos = 0
    for match in MARKER_RE.finditer(text):
        if match.start() < pos:
            continue
        block = match.group(1)
        end = text.find(f"// {block}-END", match.end())
        if end == -1:
            msg = (f"{name}: // {block}-START has no matching // {block}-END")
            raise SharedBlockError(msg)
        holds_text = bool(text[match.end():end].strip())
        has_source = (src_dir / "_shared" / f"{block.lower()}.js").is_file()
        if holds_text and not has_source and block in read_hand_kept(src_dir / "_shared"):
            continue  # declared hand-kept in _shared/hand-kept.json: not ours to fill
        if holds_text and not has_source:
            msg = (f"{name}: the {block} marker pair holds text but there is no _shared source "
                   f"for it; declare it hand-kept in _shared/{HAND_KEPT_FILE}")
            raise SharedBlockError(msg)
        if holds_text:
            msg = (
                f"{name}: the {block} marker pair already holds text; it must be empty "
                f"(the build fills it from _shared/{block.lower()}.js) -- no hand copies"
            )
            raise SharedBlockError(msg)
        parts.append(text[pos:match.end()])
        parts.append("\n" + _block_text(block, name, src_dir, package_root))
        pos = end
    parts.append(text[pos:])
    return "".join(parts)


def fill_template_bytes(raw: bytes, name: str, src_dir: Path, package_root: Path) -> bytes:
    """Return a template's bytes with its marker pairs filled (unchanged if it has none)."""
    if not MARKER_RE_BYTES.search(raw):
        return raw
    return inline_shared_blocks(raw.decode("utf-8"), name, src_dir, package_root).encode("utf-8")


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-10-22 [python-coder/BO-4500b-1]: Generalised the WORKSPACE-ANSWER-only
#   inliner (BO-4300c-3) to any block: sources are discovered under _shared/ and
#   consumers from their marker pairs, so adding a block needs no code change.
# - 2026-10-22 [python-coder/BO-4500b-3]: Block text may carry
#   {{config.commit_step_*}} placeholders, resolved from config/commit_step.json
#   and validated before anything is written, so the retry ceiling and the
#   reason-code families live in config, not in the block.
# - 2026-10-23 [python-coder/BO-4500b-1]: A marker pair holding text with no
#   _shared source is no longer skipped silently; it must be declared in
#   _shared/hand-kept.json or the fill refuses (no route is silently skipped).
# ===========================================================================
