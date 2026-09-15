"""
MODULE: sink_resolution
GOAL: Resolve where the knowledge-emission sink lives for this install --
    reading the build-time declaration, detecting staleness, handling
    ``--print-sink``, and warning when a pre-declaration legacy sink diverges
    -- as a cluster distinct from *draining* the sink once resolved.
BUSINESS CONTEXT: AC INF-400c-4-v established the build-time sink declaration
    (``config/knowledge_sink.json``) so every emit surface and the harvester
    resolve the same absolute path regardless of the invoking process's
    working directory. AC INF-400c-4-i hardened ``--print-sink`` specifically
    to REFUSE rather than fall back to a CWD-relative default, since the four
    shipped emit surfaces depend on it as their single source of truth. This
    module is entirely about *where things live*; it has no opinion on what
    happens to the sink's contents once a path is resolved -- that is
    ``harvest_learnings.harvest()``'s job.
ARCHITECTURE: Helper module for the Knowledge System component
    (docs/architecture/components/knowledge-system.md). Loaded by
    ``harvest_learnings.py`` as a required sibling module (see that file's
    ``_load_required_sibling_module``) rather than a bare top-level import,
    since ``harvest_learnings.py`` is itself loaded via
    ``importlib.util.spec_from_file_location`` by several pre-existing tests
    that do not add ``scripts/knowledge/`` to ``sys.path`` first. The
    ``logger`` here deliberately shares the name ``"harvest_learnings"`` with
    the logger in that file, so every printed/logged message this module
    produces is byte-for-byte identical to before the extraction --
    ``logging.getLogger`` returns the same singleton for a given name
    regardless of which module file calls it.

    The build deploys this file to ``<output_root>/scripts/knowledge/
    sink_resolution.py`` (see ``build_knowledge_scripts`` in
    ``scripts/build_phases_knowledge.py``), alongside ``harvest_learnings.py``
    itself.

# DECISION HISTORY
# - 2026-09-14 [python-coder/GE-127b-1 fix]: Extracted verbatim from
#   harvest_learnings.py (no behaviour change) to relieve the GE-127b-1
#   file-size ratchet, which refused a legitimate INF-400c-5-i fix because it
#   left that already-oversized file longer than it stood before. This
#   cluster (declaration read, default/staleness/legacy resolution,
#   --print-sink) is cohesive and self-contained -- no dependency on
#   entry_kind routing or _KNOWN_ENTRY_KINDS, so none of the
#   monkeypatch-visibility concerns that keep that cluster in
#   harvest_learnings.py itself apply here. Every function already took its
#   inputs (``output_root``, ``args``, ``resolved_sink``) as explicit
#   parameters rather than reading harvest_learnings module globals, so the
#   move required no signature changes -- only dropping each function's
#   leading underscore, since these are now this module's public API rather
#   than harvest_learnings.py-private helpers. ``harvest_learnings.py``'s
#   ``main()`` calls exactly three of these directly (``handle_print_sink``,
#   ``resolve_sink_or_log_stale``, ``warn_if_diverging_from_legacy``); the
#   rest are called only internally within this module.
#   (#INF-400c-5, GE-127b-1)
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger("harvest_learnings")

_LEGACY_SINK_RELATIVE_PARTS: tuple[str, ...] = (
    "leafcutter-ai",
    "debugging",
    "logs",
    "knowledge_emissions.jsonl",
)


def read_sink_declaration(output_root: Path) -> str | None:
    """Read the build-time knowledge-sink declaration, if one exists.

    Returns the declared absolute path string, or ``None`` when no
    declaration file is present (e.g. an un-built source-tree run) or it
    cannot be parsed -- callers fall back to the historical default in
    either case, per AC INF-400c-4-v ("nothing is written into nowhere").
    """
    declaration_path = output_root / "config" / "knowledge_sink.json"
    if not declaration_path.is_file():
        return None
    try:
        data = json.loads(declaration_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "Could not read sink declaration %s: %s", declaration_path, exc
        )
        return None
    value = data.get("knowledge_emission_sink")
    return value if isinstance(value, str) and value else None


def resolve_default_sink(output_root: Path) -> Path:
    """Resolve the sink path to use when ``--sink`` is not given on the CLI.

    Prefers the build-time declaration recorded beside this deployed script
    (AC INF-400c-4-v); falls back to the historical CWD-relative default
    when no declaration is present.
    """
    declared = read_sink_declaration(output_root)
    if declared is not None:
        return Path(declared)
    return Path("debugging/logs/knowledge_emissions.jsonl")


def recomputed_sink_for_output_root(output_root: Path) -> Path:
    """Recompute the conventional sink path from where this script currently lives.

    Mirrors ``build_knowledge_sink_declaration``'s own derivation in
    ``build_phases_knowledge.py`` (``<project_root>/debugging/logs/
    knowledge_emissions.jsonl``, where ``project_root == output_root.parent``)
    so that comparing this against a DECLARED value is what staleness
    detection (AC INF-400c-4-v) is built on: a declaration written for an
    install that has since been moved by hand still names its OLD absolute
    path verbatim, and that stops matching what this exact layout would
    produce right now -- without either path needing to exist on disk for
    the comparison itself to hold.

    Pure function: no I/O, no shared-state mutation.
    """
    return output_root.parent / "debugging" / "logs" / "knowledge_emissions.jsonl"


def stale_declaration_message(output_root: Path) -> str | None:
    """Return a staleness message if the build-time declaration no longer matches reality.

    AC INF-400c-4-v: a declared path whose install was moved by hand is
    reported as STALE, distinctly from a sink that has simply never been
    written to -- and without inventing a new exit status. Returns ``None``
    when there is no declaration to go stale, when the declared value is not
    an absolute path (AC INF-400c-4's own parity check is what rejects a
    non-absolute declaration outright; this staleness comparison is only
    meaningful for an absolute path that used to match this layout and no
    longer does -- a relative declared value never "used to match" an
    absolute recomputation, so treating it as stale would misreport a
    resolution-hazard case as an install-moved case), or when the declared
    value still matches what this layout would produce right now.
    """
    declared = read_sink_declaration(output_root)
    if declared is None or not Path(declared).is_absolute():
        return None
    if Path(declared) == recomputed_sink_for_output_root(output_root):
        return None
    return (
        f"Declared knowledge-emission sink is STALE: {declared} (its "
        "directory no longer exists -- this install was likely moved by "
        "hand after the build fixed this absolute path). A rebuild "
        "(python scripts/build.py --target-dir <project-root>) re-declares "
        "the sink at this install's current location."
    )


def handle_print_sink(output_root: Path) -> int:
    """Print the resolved absolute sink path, or refuse (AC INF-400c-4-i).

    Side-effect free: reads the declaration only.

    AC INF-400c-4-v established this flag and, at the time, had it fall back
    to a CWD-relative default when no declaration was present -- the same
    fallback the ordinary (non-print-sink) run still uses today, on purpose,
    for un-built source-tree runs (see ``resolve_default_sink``). AC
    INF-400c-4-i hardens THIS flag specifically: the four shipped emit
    surfaces are being repointed to depend on ``--print-sink`` as their
    single source of truth for an install-wide destination, so a fallback
    that resolves against wherever the calling process happens to stand
    would silently hand different agents different files -- the exact
    corpus split those surfaces exist to prevent. This is therefore a
    REFUSAL, not a warning: no path is printed to stdout on this path, only
    a message on stderr naming the missing declaration, and the ordinary
    run's fallback for un-built source trees is left untouched.
    """
    declared = read_sink_declaration(output_root)
    if declared is None:
        declaration_path = output_root / "config" / "knowledge_sink.json"
        print(
            "ERROR: no build-time knowledge-emission-sink declaration found "
            f"at {declaration_path}. Refusing to resolve --print-sink "
            "against the current working directory -- that would hand a "
            "different answer to every caller depending on where it is "
            "standing, which is the corpus split this refusal exists to "
            "prevent. Rebuild (python scripts/build.py --target-dir "
            "<project-root>) to declare the sink for this install.",
            file=sys.stderr,
        )
        return 1
    print(declared)
    return 0


def resolve_sink_or_log_stale(args: argparse.Namespace, output_root: Path) -> Path | None:
    """Resolve the sink path for an ordinary (non-print-sink) run.

    Returns the resolved ``Path`` when the run should proceed. Returns
    ``None`` when the build-time declaration is stale -- the staleness
    message has already been logged, and the caller should exit 1 (AC
    INF-400c-4-v: reused exit code, distinct message).

    An explicit ``--sink`` is the caller's own responsibility and is never
    checked for staleness -- only the DECLARED/default path is a build-time
    declaration that can go stale.
    """
    if args.sink is not None:
        return args.sink
    stale_message = stale_declaration_message(output_root)
    if stale_message is not None:
        logger.error(stale_message)
        return None
    return resolve_default_sink(output_root)


def legacy_sink_candidate(output_root: Path) -> Path:
    """Return the conventional pre-declaration sink location for *output_root*.

    Mirrors the concrete instance recorded in AC INF-400c-4-v's notes: in a
    development workspace whose build target is the workspace root, the
    operational stream's existing lines sit one level down, under the
    package clone's own ``debugging/logs/``. ``output_root``'s parent is the
    project root the build was pointed at.

    Pure function: no I/O, no shared-state mutation.
    """
    project_root = output_root.parent
    return project_root.joinpath(*_LEGACY_SINK_RELATIVE_PARTS)


def warn_if_diverging_from_legacy(resolved_sink: Path, output_root: Path) -> None:
    """Print+log a notice when a pre-existing legacy sink diverges from *resolved_sink*.

    AC INF-400c-4-v: adopting the declaration must not silently orphan
    records already accumulating elsewhere -- names BOTH locations once,
    and never touches either file itself. A no-op when the legacy candidate
    does not exist or is already the same file the declaration names.
    """
    legacy = legacy_sink_candidate(output_root)
    if legacy == resolved_sink or not legacy.is_file():
        return
    message = (
        f"NOTE: declared knowledge-emission sink is {resolved_sink}, which "
        f"differs from records already accumulating at {legacy}. Naming "
        "both here rather than silently diverging -- reconcile "
        "deliberately before relying on either being the complete history."
    )
    print(message)
    logger.warning(message)
