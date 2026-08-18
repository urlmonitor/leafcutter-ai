#!/usr/bin/env python3
"""
MODULE: ac_coverage_resolver
GOAL: Resolve the AC(s) a ticket's ``ac_traceability`` frontmatter block names,
    and verify the resolved AC(s)' store fields (``work_status``,
    ``implemented_by``, ``covered_by``), without ever signing off a
    verification that resolved zero ACs.
BUSINESS CONTEXT: The ticket generator (``generate_ticket_from_ac.py``) emits a
    TWO-KEY ``ac_traceability: {id, path}`` block on every generated ticket.
    The ``ac-fulfillment-gate`` agent template historically only extracted a
    THREE-key LIST form (``l2``, ``l3``, ``ac_path``) — on a generator-produced
    ticket its "working list" was therefore always empty, and its ok-rule
    ("every AC in the working list is passed or skipped") was vacuously true
    over that empty list: the gate signed off green having verified nothing
    (ACD-1900b-5-i). This module is the single, importable, side-effect-free
    coverage-resolution seam that both shapes funnel through, and its verdict
    step makes the vacuous-truth bug structurally impossible: ``compute_verdict``
    can never return ``ok: True`` over an empty resolved-AC list.
ARCHITECTURE: Pure read-only resolution + verification helper in
    ``scripts/ac_store/``. Reuses ``generate_ticket_from_ac._find_worktree_root``
    for repo-root discovery and ``generate_ticket_from_ac._find_ac_by_id`` for
    the ``source_ac`` fallback lookup, rather than re-implementing either (see
    the "EXACTLY ONE RESOLVER" constraint on ACD-1900b-5-i — this module is
    that resolver's seed; ACD-1900b-1 / ACD-1900b-5 extend it rather than
    adding a second). Deployed by ``build_ac_store``'s ``deploy_map`` in
    ``scripts/build_phases.py`` alongside its sibling AC-store scripts.
    Also runnable as a CLI (``python3 ac_coverage_resolver.py --ticket <path>``)
    so the ``ac-fulfillment-gate`` agent template — which only has Bash/Read/
    Edit tools, not a Python interpreter of its own — can invoke it via
    ``Bash`` and parse the emitted JSON verdict.

Resolution order (block-first, then source_ac; never silent):
    1. ``ac_traceability`` two-key form: ``{id, path}`` — authoritative, names
       the exact store file.
    2. ``ac_traceability`` list form: ``{l2, l3, ac_path}`` — the previously
       accepted BO-201 shape; preserved unchanged as a strict superset.
    3. ``source_ac`` fallback — consulted ONLY when the block resolves
       nothing. Never silently rescues an unrecognised block: the caller
       (``verify_ticket_coverage``) still surfaces the unrecognised keys it
       found even when this fallback succeeds.

Public API:
    resolve_coverage(ticket_path) -> {resolved_acs, block_keys_found, block_interpretable}
    verify_ticket_coverage(ticket_path) -> {ok, verified_count, resolved_acs,
        block_keys_found, block_interpretable, failures, message}
    compute_verdict(resolved_acs, ac_results) -> {ok, verified_count}

DECISION HISTORY:
    2026-08-18 [ACD-1900b-5-i/python-coder]: Created as the seed AC-store
    coverage resolver. Resolution is read-only and deterministic (no ticket or
    AC YAML file is ever mutated here — auto-fix stays downstream in the
    gate's own Step 3).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import yaml

import generate_ticket_from_ac as _gtfac

logger = logging.getLogger(__name__)

#: Recognised shape markers for the LIST form (BO-201 / the previously
#: accepted shape). Presence of ANY of these keys marks the block as an
#: interpretable list-form block, even if the named lists are empty.
_LIST_FORM_FIELDS = ("l2", "l3", "ac_path")

#: Fields checked on every resolved AC's store record.
_CHECKED_FIELDS = ("work_status", "implemented_by", "covered_by")


class FrontmatterParseError(Exception):
    """Raised when a ticket's YAML frontmatter block cannot be read or parsed."""


# ---------------------------------------------------------------------------
# Frontmatter / AC-record I/O
# ---------------------------------------------------------------------------


def _read_ticket_frontmatter(ticket_path: Path) -> dict[str, Any]:
    """Read and parse the YAML frontmatter block of a ticket file.

    Args:
        ticket_path: Path to the ticket markdown file.

    Returns:
        The parsed frontmatter dict (empty dict when the block parses to a
        non-dict, e.g. an empty document).

    Raises:
        FrontmatterParseError: When the file cannot be read, has no
            frontmatter block, the block is unterminated, or the block is
            invalid YAML. A parse failure must surface as a non-ok verdict
            naming the failure — it must never degrade into a resolved-count
            of zero silently treated as "nothing to verify".
    """
    try:
        text = ticket_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise FrontmatterParseError(
            f"Cannot read ticket file {ticket_path}: {exc}"
        ) from exc

    if not text.startswith("---"):
        raise FrontmatterParseError(
            f"Ticket file {ticket_path} has no YAML frontmatter block"
        )
    end = text.find("\n---", 3)
    if end == -1:
        raise FrontmatterParseError(
            f"Ticket file {ticket_path} frontmatter block is unterminated"
        )

    try:
        frontmatter = yaml.safe_load(text[3:end])
    except yaml.YAMLError as exc:
        raise FrontmatterParseError(
            f"Ticket file {ticket_path} frontmatter is invalid YAML: {exc}"
        ) from exc

    return frontmatter if isinstance(frontmatter, dict) else {}


def _load_ac_record(ac_yaml_path: Path) -> dict[str, Any] | None:
    """Load a single AC YAML record for coverage checking.

    Args:
        ac_yaml_path: Absolute path to the AC's store YAML file.

    Returns:
        The parsed record dict, or ``None`` when the file is missing, is not
        readable, or does not parse to a dict. The caller records this as a
        ``load_error`` failed field rather than silently dropping the AC.
    """
    try:
        with open(ac_yaml_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError) as exc:
        logger.warning(
            "ac_coverage_resolver: cannot load AC YAML %s: %s", ac_yaml_path, exc
        )
        return None
    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------------------
# Traceability-block interpretation
# ---------------------------------------------------------------------------


def _interpret_traceability_block(
    block: Any, repo_root: Path
) -> tuple[list[dict[str, str]], list[str], bool]:
    """Interpret an ``ac_traceability`` block into a resolved-AC list.

    Accepts both the two-key form (``{id, path}``, the shape the generator
    actually emits) and the list form (``{l2, l3, ac_path}``, the previously
    accepted BO-201 shape) — a present block that matches neither shape is
    reported as uninterpretable rather than silently yielding zero ACs with
    no explanation.

    Args:
        block: The raw value of the ticket frontmatter's ``ac_traceability``
            key (expected to be a dict; any other type is uninterpretable).
        repo_root: Repo root used to resolve repo-relative store paths.

    Returns:
        ``(resolved_acs, block_keys_found, block_interpretable)`` where each
        ``resolved_acs`` entry carries ``resolved_via: "traceability_block"``.
    """
    if not isinstance(block, dict):
        return [], [], False

    block_keys_found = sorted(block.keys())

    # Two-key form: authoritative when present -- it names the exact store
    # file rather than a directory a filename must be guessed inside.
    ac_id = block.get("id")
    ac_path_value = block.get("path")
    if ac_id and ac_path_value:
        ac_yaml_path = repo_root / str(ac_path_value)
        resolved = [{
            "ac_id": str(ac_id),
            "ac_yaml_path": str(ac_yaml_path),
            "resolved_via": "traceability_block",
        }]
        return resolved, block_keys_found, True

    # List form (BO-201): l2 / l3 lists plus a base ac_path directory. A
    # strict superset of the two-key form -- must keep working unchanged.
    if any(key in block for key in _LIST_FORM_FIELDS):
        base_path = block.get("ac_path") or ""
        l2_ids = block.get("l2") or []
        l3_ids = block.get("l3") or []
        named_ids = [*l2_ids, *l3_ids]
        resolved = [
            {
                "ac_id": str(named_id),
                "ac_yaml_path": str(repo_root / str(base_path) / f"{named_id}.yaml"),
                "resolved_via": "traceability_block",
            }
            for named_id in named_ids
        ]
        return resolved, block_keys_found, True

    # Present but neither recognised shape -- uninterpretable, not empty.
    return [], block_keys_found, False


# ---------------------------------------------------------------------------
# Public resolution API
# ---------------------------------------------------------------------------


def resolve_coverage(ticket_path: str) -> dict[str, Any]:
    """Resolve the AC(s) a ticket's traceability data names.

    Read-only and deterministic: never mutates the ticket or any AC YAML
    file, and returns the same result for the same inputs on repeated calls.

    Resolution order is block-first, then ``source_ac``: the block's own
    id/path (or l2/l3/ac_path) is authoritative when interpretable;
    ``source_ac`` is consulted only when the block yields nothing.

    Args:
        ticket_path: Path (str) to the ticket markdown file.

    Returns:
        ``{"resolved_acs": [...], "block_keys_found": [...], "block_interpretable": bool}``.
        ``resolved_acs`` entries: ``{"ac_id": str, "ac_yaml_path": str,
        "resolved_via": "traceability_block" | "source_ac"}``.

    Raises:
        FrontmatterParseError: When the ticket frontmatter cannot be read or
            parsed, or the repo root cannot be located.
    """
    path = Path(ticket_path)
    frontmatter = _read_ticket_frontmatter(path)

    try:
        repo_root = _gtfac._find_worktree_root(path)  # noqa: SLF001
    except FileNotFoundError as exc:
        raise FrontmatterParseError(str(exc)) from exc

    block = frontmatter.get("ac_traceability")
    resolved_acs, block_keys_found, block_interpretable = _interpret_traceability_block(
        block, repo_root
    )

    if not resolved_acs:
        source_ac = frontmatter.get("source_ac")
        if source_ac:
            ac_root = repo_root / _gtfac._DEFAULT_AC_ROOT  # noqa: SLF001
            found = _gtfac._find_ac_by_id(ac_root, source_ac)  # noqa: SLF001
            if found is not None:
                ac_yaml_path, _record = found
                resolved_acs = [{
                    "ac_id": str(source_ac),
                    "ac_yaml_path": str(ac_yaml_path),
                    "resolved_via": "source_ac",
                }]

    return {
        "resolved_acs": resolved_acs,
        "block_keys_found": block_keys_found,
        "block_interpretable": block_interpretable,
    }


def _check_ac_record(record: dict[str, Any] | None) -> tuple[bool, list[str]]:
    """Check ``work_status`` / ``implemented_by`` / ``covered_by`` on one AC record.

    Args:
        record: The parsed AC YAML record, or ``None`` when the file could
            not be loaded.

    Returns:
        ``(passed, failed_fields)``. When ``record`` is ``None`` the sole
        failed field is ``"load_error"``.
    """
    if record is None:
        return False, ["load_error"]

    failed_fields: list[str] = []
    if record.get("work_status") != "done":
        failed_fields.append("work_status")
    if not record.get("implemented_by"):
        failed_fields.append("implemented_by")
    if not record.get("covered_by"):
        failed_fields.append("covered_by")
    return (not failed_fields), failed_fields


def compute_verdict(
    resolved_acs: list[dict[str, Any]], ac_results: list[dict[str, Any]]
) -> dict[str, Any]:
    """Compute the ``ok`` / ``verified_count`` verdict.

    THE LOAD-BEARING INVARIANT: ``ok`` must be ``False`` whenever
    *resolved_acs* is empty, REGARDLESS of what *ac_results* contains. This is
    the vacuous-truth guard — an empty resolved-AC list must never satisfy
    "every AC passed", which is exactly how the pre-fix gate's "every AC in
    the working list is passed or skipped" rule went vacuously green on a
    generator-produced ticket.

    Args:
        resolved_acs: The resolved-AC list from ``resolve_coverage``.
        ac_results: Per-AC check results, each
            ``{"ac_id": str, "passed": bool, "failed_fields": list[str]}``.

    Returns:
        ``{"ok": bool, "verified_count": int}``.
    """
    verified_count = len(resolved_acs)
    if verified_count == 0:
        return {"ok": False, "verified_count": 0}
    ok = all(result.get("passed", False) for result in ac_results)
    return {"ok": ok, "verified_count": verified_count}


def _build_message(
    *,
    resolved_acs: list[dict[str, Any]],
    ac_results: list[dict[str, Any]],
    block_keys_found: list[str],
    block_interpretable: bool,
    verdict: dict[str, Any],
) -> str:
    """Build the human-readable verdict message.

    A present-but-unrecognised block's keys are ALWAYS enumerated in the
    message -- even when ``source_ac`` went on to rescue the resolution --
    so a future shape drift never becomes invisible the way this one was.
    """
    if not resolved_acs:
        keys_repr = ", ".join(block_keys_found) if block_keys_found else "(none)"
        return (
            f"Traceability block uninterpretable: found keys [{keys_repr}] -- "
            "unable to resolve any AC to verify from the traceability block "
            "or the source_ac fallback."
        )

    lines: list[str] = []
    if not block_interpretable and block_keys_found:
        lines.append(
            f"Traceability block carried unrecognised keys [{', '.join(block_keys_found)}] "
            "-- resolved via source_ac fallback instead."
        )

    if verdict["ok"]:
        lines.append(
            f"All {verdict['verified_count']} AC(s) verified. work_status, "
            "implemented_by, and covered_by fields are accurate."
        )
        return "\n".join(lines)

    lines.append("AC store fulfillment incomplete:")
    for result in ac_results:
        if result["failed_fields"]:
            fields_repr = ", ".join(result["failed_fields"])
            lines.append(f"{result['ac_id']}: failed fields -- {fields_repr}")
    return "\n".join(lines)


def verify_ticket_coverage(ticket_path: str) -> dict[str, Any]:
    """Resolve and verify AC store coverage for a ticket.

    Args:
        ticket_path: Path (str) to the ticket markdown file.

    Returns:
        ``{"ok": bool, "verified_count": int, "resolved_acs": [...],
        "block_keys_found": [...], "block_interpretable": bool,
        "failures": [{"ac_id": str, "field": str}, ...], "message": str}``.

    Raises:
        FrontmatterParseError: Propagated from ``resolve_coverage`` when the
            ticket frontmatter cannot be read or parsed.
    """
    resolution = resolve_coverage(ticket_path)
    resolved_acs = resolution["resolved_acs"]
    block_keys_found = resolution["block_keys_found"]
    block_interpretable = resolution["block_interpretable"]

    ac_results: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for entry in resolved_acs:
        ac_id = entry["ac_id"]
        record = _load_ac_record(Path(entry["ac_yaml_path"]))
        passed, failed_fields = _check_ac_record(record)
        ac_results.append({"ac_id": ac_id, "passed": passed, "failed_fields": failed_fields})
        for field in failed_fields:
            failures.append({"ac_id": ac_id, "field": field})

    verdict = compute_verdict(resolved_acs, ac_results)
    message = _build_message(
        resolved_acs=resolved_acs,
        ac_results=ac_results,
        block_keys_found=block_keys_found,
        block_interpretable=block_interpretable,
        verdict=verdict,
    )

    return {
        "ok": verdict["ok"],
        "verified_count": verdict["verified_count"],
        "resolved_acs": resolved_acs,
        "block_keys_found": block_keys_found,
        "block_interpretable": block_interpretable,
        "failures": failures,
        "message": message,
    }


# ---------------------------------------------------------------------------
# CLI entry point (for the ac-fulfillment-gate agent template, which has no
# Python interpreter of its own -- only Bash/Read/Edit tools)
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Resolve and verify AC store coverage for a ticket's ac_traceability block."
    )
    parser.add_argument("--ticket", required=True, help="Path to the ticket markdown file")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: print the verdict as JSON to stdout.

    Args:
        argv: Command-line arguments (default: ``sys.argv[1:]``).

    Returns:
        ``0`` when the verdict is ``ok``, ``1`` otherwise (including a
        frontmatter parse failure).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    try:
        result = verify_ticket_coverage(args.ticket)
    except FrontmatterParseError as exc:
        print(json.dumps({
            "ok": False,
            "verified_count": 0,
            "resolved_acs": [],
            "block_keys_found": [],
            "block_interpretable": False,
            "failures": [],
            "message": f"Frontmatter parse failure: {exc}",
        }, indent=2))
        return 1

    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
