"""
epic_tickets.py — Per-leaf ticket generation and ticket-frontmatter editing.

MODULE: epic_tickets
GOAL: Generate one ticket per leaf AC by delegating to
      generate_ticket_from_ac.py as a subprocess, and read/rewrite the YAML
      frontmatter of the tickets that come back — in particular translating
      ``depends_on`` AC ids into the co-located epic-folder filenames.
BUSINESS CONTEXT: Implements ACD-1200a-2 (one generate_ticket_from_ac.py call
      per leaf) and BO-2600a-5 AC-4 (generation-time AC-id -> ticket-filename
      translation so ticket_frontmatter_guard passes without a downstream hook
      auto-fix). Extracted from goal_to_epic.py so that file can meet the
      400-line check_file_size limit.
ARCHITECTURE: Subprocess boundary plus targeted text edits. Resolves its
      sibling generate_ticket_from_ac.py relative to its own directory, which
      is ``scripts/ac_store/`` in the source layout and
      ``<output_root>/scripts/ac_store/`` in the deployed layout — the same
      directory either way, so no dual-layout guard is needed here (unlike
      goal_to_epic.py, which lives one level up in the source tree). Imports
      epic_runtime (shared logger) only. Deployed flat beside goal_to_epic.py
      (see AC_STORE_DEPLOY_MAP in scripts/build_phases.py).

AC coverage owned by this module:
    ACD-1200a-2:  generate_ticket_from_ac.py is called once per leaf, in order.
    TKT-600b-1-i: the generator is told --location-kind epic_member rather than
                  being handed a path this caller does not yet know.
    BO-2600a-5:   depends_on AC ids are translated to co-located epic-folder
                  ticket filenames at generation time.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

from epic_runtime import get_logger

# This module always lives in ``ac_store/`` — in the source tree at
# ``scripts/ac_store/`` and in a consumer install at
# ``<output_root>/scripts/ac_store/`` — so its siblings are unconditionally
# alongside it. goal_to_epic.py needs an if/else guard for this because it
# lives at ``scripts/`` in source and is flattened into ``ac_store/`` on
# deploy; this module does not.
_sibling_dir = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


def _frontmatter_end_index(lines: list[str]) -> int | None:
    """Return the index of the closing ``---`` of a leading YAML frontmatter block.

    A file has frontmatter only when its very first line is ``---``; the block
    ends at the next line that is ``---``. Works with lines produced either by
    ``str.splitlines()`` or ``str.splitlines(keepends=True)`` because the
    comparison strips each line first.

    Args:
        lines: The file's lines, in order.

    Returns:
        int | None: Index of the closing ``---`` line, or None when the file
        has no opening ``---`` or the block is never closed.
    """
    if not lines or lines[0].strip() != "---":
        return None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return i
    return None


def _read_ticket_frontmatter(ticket_path: Path) -> dict:
    """Read and parse the YAML frontmatter from a ticket markdown file.

    Reads only the YAML front-matter block delimited by ``---`` markers
    at the top of the file. Returns an empty dict on any parse or I/O error.

    Args:
        ticket_path: Path to a ticket markdown file.

    Returns:
        Parsed frontmatter as a dict, or empty dict on failure.
    """
    try:
        content = ticket_path.read_text(encoding="utf-8")
    except OSError as exc:
        get_logger().warning("Cannot read ticket file %s: %s", ticket_path, exc)
        return {}

    lines = content.splitlines()
    end_idx = _frontmatter_end_index(lines)
    if end_idx is None:
        return {}

    yaml_text = "\n".join(lines[1:end_idx])
    try:
        data = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        get_logger().warning("YAML parse error in %s: %s", ticket_path, exc)
        return {}

    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Single-ticket generation (subprocess delegation)
# ---------------------------------------------------------------------------


def _call_generate_ticket_from_ac(
    ac_id: str,
    ac_root: Path,
    tickets_root: Path,
) -> str:
    """Invoke generate_ticket_from_ac.py for *ac_id* and return the ticket path.

    The function calls the script as a subprocess so that the ticket
    generation logic stays in its canonical home and is not duplicated here.
    The generated ticket path is read from the script's stdout line
    (``Written: <path>``).

    Args:
        ac_id: The leaf AC id to generate a ticket for.
        ac_root: Root directory of the AC YAML store.
        tickets_root: Root directory where tickets are written.

    Returns:
        Absolute path to the generated ticket file.

    Raises:
        subprocess.CalledProcessError: When the script exits non-zero.
        RuntimeError: When the script exits 0 but emits no ``Written:`` line.
    """
    script_path = _sibling_dir / "generate_ticket_from_ac.py"
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(script_path),
                "--ac",
                ac_id,
                "--ac-root",
                str(ac_root),
                "--tickets-root",
                str(tickets_root),
                # TKT-600b-1-i: the generator refuses rather than guess when
                # the phase-deferral declaration is location-dependent. This
                # caller builds epic MEMBERS by construction — every ticket it
                # emits is assembled into an epic folder below — so it declares
                # that kind rather than passing a path it does not yet know.
                # --tickets-root is explicitly not accepted as a substitute,
                # and must not be reached for here.
                "--location-kind",
                "epic_member",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        get_logger().warning(
            "generate_ticket_from_ac.py failed for AC %s: %s", ac_id, exc
        )
        raise
    for line in result.stdout.splitlines():
        if line.startswith("Written:"):
            return line[len("Written:"):].strip()
    raise RuntimeError(  # noqa: TRY003
        f"generate_ticket_from_ac.py exited 0 for AC {ac_id!r} "
        f"but emitted no 'Written:' line. stdout: {result.stdout!r}"
    )


# ---------------------------------------------------------------------------
# Batch ticket generation (ACD-1200a-2)
# ---------------------------------------------------------------------------


def generate_tickets_for_leaves(
    leaf_ids: list[str],
    ac_store_root: Path,
    tickets_root: Path,
) -> list[str]:
    """Generate one ticket per leaf AC and return the list of ticket paths.

    Calls :func:`_call_generate_ticket_from_ac` once per entry in *leaf_ids*,
    in order. The returned list preserves the same order as *leaf_ids*.

    Args:
        leaf_ids: Ordered list of leaf AC ids to generate tickets for.
        ac_store_root: Root directory of the AC YAML store.
        tickets_root: Root directory where individual tickets are written before
                      being assembled into the EPIC folder.

    Returns:
        Ordered list of absolute ticket file path strings — one per leaf AC.

    Raises:
        subprocess.CalledProcessError: Propagated from
            :func:`_call_generate_ticket_from_ac` when a leaf ticket cannot be
            generated.
    """
    ticket_paths: list[str] = []
    for leaf_id in leaf_ids:
        ticket_path = _call_generate_ticket_from_ac(leaf_id, ac_store_root, tickets_root)
        ticket_paths.append(ticket_path)
    return ticket_paths


# ---------------------------------------------------------------------------
# Depends-on translation helper (BO-2600a-5)
# ---------------------------------------------------------------------------


def _translate_ticket_depends_on(
    ticket_file: Path,
    raw_deps: list[str],
    ac_to_epic_filename: dict[str, str],
) -> None:
    """Write *raw_deps* into ticket_file's frontmatter, translated to epic filenames.

    Reads the YAML frontmatter from *ticket_file*, translates every entry in
    *raw_deps* that matches a key in *ac_to_epic_filename* to the corresponding
    epic-folder filename (falling back to the raw id unchanged when it is not
    a key in the map — e.g. a dependency outside the generated set), and writes
    the result as the ticket's ``depends_on`` field. No-ops when the file has no
    frontmatter or *raw_deps* is empty.

    This is the generation-time AC-id -> ticket-filename translation required by
    BO-2600a-5 AC-4 so ``ticket_frontmatter_guard`` passes without a downstream
    hook auto-fix.

    DECISION HISTORY:
        2026-08-13 (tgh-build regression fix): *raw_deps* is now supplied by the
        caller (sourced from :func:`resolve_leaf_dependencies`'s dependency graph,
        already built before ticket generation) instead of being read back from
        the ticket file's own frontmatter. generate_ticket_from_ac.py intentionally
        emits ``depends_on: []`` for every standalone ticket it writes (ACD-400b-7:
        a generated standalone ticket must never leak AC ids into depends_on, since
        ticket_frontmatter_guard requires every entry to resolve to a sibling ticket
        file). Reading the AC-level dependency list back out of the ticket file is
        therefore no longer possible — the caller must pass it explicitly from the
        AC store's own dependency graph.

    Args:
        ticket_file: Path to a ticket markdown file inside the assembled epic folder.
        raw_deps: The raw AC ids this ticket's source AC depends on (restricted to
            the generated set), as computed by :func:`resolve_leaf_dependencies`.
        ac_to_epic_filename: Mapping from AC id (e.g. ``"BO-5C1"``) to the
            corresponding epic-folder filename (e.g. ``"01_TICKET-BO-5C1.md"``).
    """
    _log = get_logger()

    if not raw_deps:
        return

    try:
        content = ticket_file.read_text(encoding="utf-8")
    except OSError as exc:
        _log.warning("Cannot read %s for depends_on translation: %s", ticket_file, exc)
        return

    lines = content.splitlines(keepends=True)
    end_idx = _frontmatter_end_index(lines)
    if end_idx is None:
        return

    yaml_text = "".join(lines[1:end_idx])
    try:
        fm = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        _log.warning("YAML parse error in %s: %s", ticket_file, exc)
        return

    if not isinstance(fm, dict):
        return

    translated = [
        ac_to_epic_filename.get(str(dep), str(dep))
        for dep in raw_deps
    ]

    fm["depends_on"] = translated
    new_fm_yaml = yaml.safe_dump(fm, allow_unicode=True, default_flow_style=False)
    body = "".join(lines[end_idx + 1:])
    new_content = f"---\n{new_fm_yaml}---\n{body}"

    try:
        ticket_file.write_text(new_content, encoding="utf-8")
    except OSError as exc:
        _log.warning(
            "Cannot write translated depends_on to %s: %s", ticket_file, exc
        )


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-08-13 (tgh-build regression fix): generate_ticket_from_ac.py's ACD-400b-7
  fix (a generated standalone ticket must never leak AC ids into depends_on)
  hardcoded every generated ticket's depends_on to [], which silently broke
  build_epic_from_ids()'s depends_on translation — _translate_ticket_depends_on()
  used to read the raw AC ids back out of each ticket's own frontmatter, but that
  frontmatter now always reads depends_on: []. Fixed by sourcing the raw AC-id
  dependency list from dep_graph (already computed at Step 1 via
  resolve_leaf_dependencies) instead of reading it back from the ticket file.
  _translate_ticket_depends_on() now takes raw_deps as an explicit parameter.
  generate_ticket_from_ac.py itself is unchanged — standalone ticket generation
  (ACD-400b-7) still emits depends_on: [] with no opt-in flag, so no call-site
  audit of that script was required.
- 2026-09-14 12:00 [goal-to-epic-decompose]: Moved here from
  scripts/goal_to_epic.py, which exceeded the 400-line check_file_size limit.
  All four functions moved with their bodies intact. Three edits, all
  behaviour-preserving:
  (1) the deferred `import logging; logging.getLogger(__name__)` calls became
      epic_runtime.get_logger(), so records keep the pre-split logger name
      "goal_to_epic" rather than picking up this module's __name__;
  (2) _read_ticket_frontmatter and _translate_ticket_depends_on each contained
      their own copy of the "first line is ---, scan for the closing ---" loop;
      both now call the shared _frontmatter_end_index(). The comparison is
      still `line.strip() == "---"`, which behaves identically for the
      keepends=True lines _translate_ticket_depends_on passes and the
      keepends=False lines _read_ticket_frontmatter passes. This removes a
      check_duplicate_code candidate and drops _translate_ticket_depends_on
      from cyclomatic 12 to 8;
  (3) _sibling_dir is computed here as Path(__file__).resolve().parent with no
      if/else guard, because this module is in ac_store/ under BOTH layouts.
      goal_to_epic.py's dual-layout IfExp guard is untouched — it is cited as
      the canonical live instance of that pattern by
      scripts/build_referential_integrity.py.

  unit_tests/ac_store/test_ticket_generation_batch.py (5 sites) and
  unit_tests/build_orchestration/test_bo_2600a_5.py (4 sites) previously did
  `patch("goal_to_epic._call_generate_ticket_from_ac", ...)`. Since
  generate_tickets_for_leaves moved here with its callee, that patch would
  rebind a name goal_to_epic re-exports but never calls. All nine were
  retargeted to `epic_tickets`; no assertion was changed.
  (#TICKETLESS reason=file-size-decomposition-refactor)
====================================================================
"""
