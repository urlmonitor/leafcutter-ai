#!/usr/bin/env python3
"""
goal_to_epic.py — Batch orchestrator: goal AC → EPIC folder of tickets.

MODULE: goal_to_epic
GOAL: Walk the AC tree from a goal-level AC, collect all leaf ACs, generate
      one ticket per leaf via generate_ticket_from_ac.py, and assemble the
      results into a numbered EPIC folder under tickets/00_inbox/epics/.
BUSINESS CONTEXT: Implements ACD-1200a (goal-to-epic pipeline). Enables
      /build-feature to accept a goal-level AC id and produce a fully
      populated EPIC folder without manual assembly.
ARCHITECTURE: Standalone CLI script and the public facade of the pipeline.
      The implementation lives in fourteen sibling modules under ac_store/ (see
      the module map below); this file owns the dual-layout sibling resolution,
      re-exports every public and private name the pipeline exposes so existing
      import sites keep resolving, and holds main() plus the full pre-split
      DECISION HISTORY.

Module map (all deployed flat into <output_root>/scripts/ac_store/ — see
AC_STORE_DEPLOY_MAP in scripts/build_phases.py):

    epic_errors           ZeroLeafError, EpicFolderConflictError, CyclicDependencyError
    epic_runtime          default paths, worktree-root detection, shared logger
    epic_naming           quote stripping, PascalCase, concise epic-name derivation
    epic_ac_store         AC YAML lookups and target_epic stamping
    epic_dependencies     leaf dependency resolution and topological ordering
    epic_tickets          per-leaf ticket generation and frontmatter editing
    epic_assembly         EPIC folder assembly and single-location write
    epic_readiness        read-only readiness classification
    epic_readiness_gate   the interactive / TTY-aware readiness gate
    epic_master_plan      Master_Plan.md collection and rendering
    epic_ac_phases        AC-store-facing phase steps (--ac mode)
    epic_phases           post-assembly phases shared by both entrypoints
    epic_pipeline         run() (--ac mode) and build_epic_from_ids() (--ids mode)
    epic_cli              argument parser and --ids dispatch

Usage:
    python3 scripts/goal_to_epic.py --ac <ac_id> [--store-root <path>]
                                    [--inbox-dir <path>] [--dry-run]
                                    [--yes | --approved-only]
    python3 scripts/goal_to_epic.py --ids <id1,id2,...> [--store-root <path>]
                                    [--inbox-dir <path>]

Exit codes:
    0  EPIC folder created successfully (or --dry-run printed the plan).
    1  AC not found, zero-leaf condition, I/O error, conflict, or no-TTY
       run without an approval flag when unapproved ACs are present.

Complete AC index for the pipeline (the owning module is named for each; every
one of these annotations is repeated in that module's own docstring):

ACD-1200a-1: traverse_ac_tree returns only leaf ACs. [epic_pipeline]
ACD-1200a-1-i: L1-scoped traversal excludes sibling branches. [epic_pipeline]
ACD-1200a-2: generate_ticket_from_ac.py called once per leaf. [epic_tickets]
ACD-1200a-3: EPIC folder assembled with numeric prefixes. [epic_assembly]
ACD-1200a-3-i: Zero-leaf condition exits non-zero, no files written. [epic_assembly, epic_errors]
ACD-1200a-3-ii: apostrophe/quote characters are deleted in place. [epic_naming]
ACD-1200a-3-iii: ASCII-safe slug; dry-run/real-run name parity. [epic_naming]
ACD-1200a-6: Epic folder name is concise (≤5 PascalCase words, ≤40 chars). [epic_naming]
ACD-1200a-7: generate_master_plan() writes Master_Plan.md at epic folder root. [epic_master_plan, epic_phases]
ACD-1200a-8: generate_master_plan() writes Master_Plan.md into the EPIC folder. [epic_master_plan]
ACD-1200b-1: classify_readiness reads readiness field and classifies approved vs unapproved. [epic_readiness]
ACD-1200b-1-i: All-approved fast-path skips prompt; prints confirmation. [epic_readiness]
ACD-1200b-2: readiness_gate_prompt presents three-choice prompt and routes correctly. [epic_readiness_gate]
ACD-1200b-4: Non-interactive (no-TTY) run with --yes or --approved-only clears the
             readiness gate; without either flag and without a TTY it exits non-zero
             with a message naming both flags. [epic_readiness_gate, epic_cli]
ACD-1200c-1: resolve_leaf_dependencies emits only leaf-to-leaf edges. [epic_dependencies]
ACD-1200c-1-i: Cycle detection fires before any ticket files are written. [epic_dependencies, epic_pipeline]
ACD-1200c-2: Deterministic ordering via alphabetical tie-breaking. [epic_dependencies]
ACD-1200d-1: target_epic written via targeted line-level edit; idempotent. [epic_ac_store]
ACD-1200d-1-i: Differing target_epic triggers a per-AC overwrite/skip prompt. [epic_ac_store]
ACD-1200d-2: Exclusion guard — only ACs in included_ids are ever touched. [epic_ac_store]
ACD-1200a-9: each generated ticket is written only inside the epic folder; no loose inbox-root copy
             is left behind; implemented_by back-references name the epic-folder path (with prefix).
             [epic_assembly, epic_phases]
ACD-1200a-9-i: basename collision inside the epic folder is resolved by overwriting the existing
               epic-folder file in place; no renamed sibling or second copy is created; a WARNING
               is emitted for each overwritten file; implemented_by names the single epic-folder path.
               [epic_assembly]
BP-901: _find_worktree_root() is never called when both CLI paths are explicit. [epic_runtime, main]
TKT-016: implemented_by back-references are repo-relative on BOTH sides. [epic_phases]
TKT-017: depends_on is translated to co-located epic-folder filenames. [epic_phases]
BO-2600a-5: --ids takes the id list as authoritative; cross-tree ids preserved. [epic_pipeline, epic_cli]
"""

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Deploy-location-aware sibling resolution (AC-4 of EPIC-AcPipelineDeployGaps)
# ---------------------------------------------------------------------------
# When this file is deployed into .leafcutter/scripts/ac_store/ (consumer install),
# its sibling scripts are in the SAME directory (no ac_store/ subdirectory needed).
# When run from the source layout (scripts/goal_to_epic.py), siblings live under
# scripts/ac_store/.  The guard below detects which case is active at runtime.
#
# If parent.name == "ac_store" → deployed layout: siblings are alongside this file
# Otherwise                    → source layout:   siblings are in parent / "ac_store"
_scripts_dir = Path(__file__).parent
_sibling_dir = (
    _scripts_dir                           # deployed: siblings are alongside this file
    if Path(__file__).parent.name == "ac_store"
    else Path(__file__).parent / "ac_store"  # source layout: siblings are in ac_store/
)

# The sibling directory must be importable BEFORE the re-export block below.
# Pre-split this push lived inside run(); it is at module scope now because the
# pipeline modules are imported at load time. build_referential_integrity's
# closure guard resolves this shape (a sys.path push followed by plain imports)
# and will fail the build if any imported sibling is missing from
# AC_STORE_DEPLOY_MAP, which is the mechanical guarantee that all fourteen
# deploy. Twelve are imported directly below; epic_ac_phases and epic_phases
# arrive transitively via epic_pipeline, and are equally required at load time.
if str(_sibling_dir) not in sys.path:
    sys.path.insert(0, str(_sibling_dir))

# ---------------------------------------------------------------------------
# Re-exported pipeline surface
# ---------------------------------------------------------------------------
# Every public AND private top-level name this module exposed before the split
# is re-exported here, so `from goal_to_epic import _derive_epic_name` and
# friends keep resolving unchanged. __all__ declares them as the module's
# surface (and is what stops ruff F401 flagging the names main() does not use).

from epic_ac_store import (  # noqa: E402
    _find_ac_yaml_path,
    _get_ac_title,
    _read_target_epic_from_file,
    _write_target_epic_field,
    stamp_target_epic,
)
from epic_assembly import (  # noqa: E402
    _build_loose_to_epic_map,
    _remove_loose_inbox_tickets,
    _replace_implemented_by_entry,
    assemble_epic_folder,
)
from epic_cli import _build_parser, _run_ids_mode  # noqa: E402
from epic_dependencies import (  # noqa: E402
    _build_depends_on_index,
    _extract_cycle,
    _resolve_to_leaf_deps_from_index,
    resolve_leaf_dependencies,
    topological_sort,
)
from epic_errors import CyclicDependencyError, EpicFolderConflictError, ZeroLeafError  # noqa: E402
from epic_master_plan import (  # noqa: E402
    _collect_master_plan_data,
    _render_master_plan,
    generate_master_plan,
)
from epic_naming import (  # noqa: E402
    _EPIC_NAME_MAX_CHARS,
    _QUOTE_CHARS_TO_STRIP,
    _derive_epic_name,
    _normalize_non_ascii_punct,
    _strip_quote_chars,
    _summarise_title_via_llm,
    _to_pascal_case,
    _truncate_pascal_at,
)
from epic_pipeline import build_epic_from_ids, run  # noqa: E402
from epic_readiness import classify_readiness, print_fast_path_message  # noqa: E402
from epic_readiness_gate import (  # noqa: E402
    _gate_select_approved_ids,
    _print_readiness_report,
    _prompt_choice,
    _route_answer,
    dispatch_it_po_v3,
    readiness_gate_prompt,
)
from epic_runtime import (  # noqa: E402
    _DEFAULT_INBOX_DIR,
    _DEFAULT_STORE_ROOT,
    _derive_worktree_from_inbox,
    _find_worktree_root,
)
from epic_tickets import (  # noqa: E402
    _call_generate_ticket_from_ac,
    _read_ticket_frontmatter,
    _translate_ticket_depends_on,
    generate_tickets_for_leaves,
)

__all__ = [
    "_DEFAULT_INBOX_DIR", "_DEFAULT_STORE_ROOT", "_EPIC_NAME_MAX_CHARS",
    "_QUOTE_CHARS_TO_STRIP", "_build_depends_on_index", "_build_loose_to_epic_map",
    "_build_parser", "_call_generate_ticket_from_ac", "_collect_master_plan_data",
    "_derive_epic_name", "_derive_worktree_from_inbox", "_extract_cycle",
    "_find_ac_yaml_path", "_find_worktree_root", "_gate_select_approved_ids",
    "_get_ac_title", "_normalize_non_ascii_punct", "_print_readiness_report",
    "_prompt_choice", "_read_target_epic_from_file", "_read_ticket_frontmatter",
    "_remove_loose_inbox_tickets", "_render_master_plan",
    "_replace_implemented_by_entry", "_resolve_to_leaf_deps_from_index",
    "_route_answer", "_run_ids_mode", "_strip_quote_chars",
    "_summarise_title_via_llm", "_to_pascal_case", "_translate_ticket_depends_on",
    "_truncate_pascal_at", "_write_target_epic_field", "assemble_epic_folder",
    "build_epic_from_ids", "classify_readiness", "CyclicDependencyError",
    "dispatch_it_po_v3", "EpicFolderConflictError", "generate_master_plan",
    "generate_tickets_for_leaves", "main", "print_fast_path_message",
    "readiness_gate_prompt", "resolve_leaf_dependencies", "run",
    "stamp_target_epic", "topological_sort", "ZeroLeafError",
]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Entry point for goal_to_epic.py.

    Args:
        argv: Command-line arguments (default: sys.argv[1:]).

    Returns:
        Exit code: 0 on success, 1 on error.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Resolve the worktree root lazily: only when at least one default path is
    # needed.  When both --store-root and --inbox-dir are supplied explicitly,
    # _find_worktree_root() is never called (BP-901) — allowing the script to run
    # from a location outside any git tree (e.g. .leafcutter/scripts/) without
    # error.  run() still needs a worktree root to relativise absolute ticket
    # paths against the relative implemented_by values in the AC YAML store
    # (ACD-1200a-9), so in that branch it is derived from the supplied inbox_dir
    # by pure path math instead.  When inbox_dir does not follow the conventional
    # <worktree>/tickets/00_inbox shape, worktree_for_run stays None and run()
    # falls back to its non-relativised comparison (ValueError-guarded).
    worktree_for_run: Path | None = None
    if args.store_root and args.inbox_dir:
        ac_store_root = Path(args.store_root)
        inbox_dir = Path(args.inbox_dir)
        worktree_for_run = _derive_worktree_from_inbox(inbox_dir)
    else:
        try:
            worktree = _find_worktree_root(Path(__file__))
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        worktree_for_run = worktree
        ac_store_root = Path(args.store_root) if args.store_root else worktree / _DEFAULT_STORE_ROOT
        inbox_dir = Path(args.inbox_dir) if args.inbox_dir else worktree / _DEFAULT_INBOX_DIR

    if not ac_store_root.exists():
        print(f"ERROR: AC store root not found: {ac_store_root}", file=sys.stderr)
        return 1

    # --- Route to the appropriate mode ---

    if args.ids is not None:
        # --ids mode (BO-2600a-5): explicit id-list entrypoint.
        return _run_ids_mode(args.ids, ac_store_root, inbox_dir)

    # --ac mode: existing tree-traversal path (unchanged).
    run(
        ac_id=args.ac_id,
        ac_store_root=ac_store_root,
        inbox_dir=inbox_dir,
        dry_run=args.dry_run,
        worktree_root=worktree_for_run,
        yes=args.yes,
        approved_only=args.approved_only,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 [EPIC-GoalToEpic/01]: Initial implementation.
  Implements ACD-1200a: tree traversal via traverse_ac_tree() from
  scan_ac_store.py, batch ticket generation via subprocess calls to
  generate_ticket_from_ac.py, and EPIC folder assembly with 01_/02_/...
  numeric prefixes. ZeroLeafError raised before any filesystem writes
  (ACD-1200a-3-i). EpicFolderConflictError raised when the target EPIC
  folder already exists. PascalCase conversion via _to_pascal_case().
- 2026-06-05 [EPIC-GoalToEpic/02]: Readiness gate implementation.
  Implements ACD-1200b-1: classify_readiness() reads the readiness field
  from each leaf AC YAML (read-only), classifies into approved/unapproved,
  completes in <500ms for <=100 leaves. Implements ACD-1200b-1-i:
  all-approved fast-path via print_fast_path_message(). Implements
  ACD-1200b-2: readiness_gate_prompt() with three-choice routing (yes /
  review-all / cancel), IT PO v3 dispatch via dispatch_it_po_v3(), and
  re-read from disk after dispatch to prevent stale cache bugs. Gate
  integrated into run() before ticket generation begins.
- 2026-06-05 [EPIC-GoalToEpic/03]: Dependency wiring and topological sort.
  Implements ACD-1200c-1: resolve_leaf_dependencies() builds leaf-to-leaf
  dependency map by resolving transitive depends_on chains through composite
  ACs; only emits edges where both endpoints are in the generated leaf set;
  handles missing AC references gracefully; uses single-pass store index for
  O(n) performance. Implements ACD-1200c-1-i: topological_sort() via Kahn's
  BFS algorithm; raises CyclicDependencyError with full cycle path message
  before any file writes. Implements ACD-1200c-2: deterministic output via
  alphabetical tie-breaking; diamond dependencies produce no duplicates.
  run() wired to call resolve_leaf_dependencies + topological_sort before
  generate_tickets_for_leaves — cycle detection fires pre-write (ACD-1200c-1-i).
- 2026-06-05 10:35 [EPIC-GoalToEpic/04]: target_epic stamping. (#EPIC-GoalToEpic/04)
  Implements ACD-1200d-1: stamp_target_epic(included_ids, epic_name, store_root)
  writes target_epic field to each included AC YAML via targeted line-level edit
  (not yaml.dump) to preserve comments and field ordering. Idempotent: same
  value is a no-op (no file rewrite). Case-exact match to epic_name. Implements
  ACD-1200d-1-i: conflict detection when existing target_epic differs — per-AC
  prompt "ACD-xxx already belongs to EPIC-OldName. Overwrite with EPIC-NewName?
  (yes / skip)" routes on user answer. Implements ACD-1200d-2: exclusion guard
  — only ACs in included_ids are ever touched; all other AC files remain unread
  and unmodified. Helper functions: _find_ac_yaml_path(), _read_target_epic_from_file(),
  _write_target_epic_field() (regex-based targeted replace or append).
- 2026-06-08 00:00 [EPIC-AcParentChildLinkEnforcement/06]: Concise epic name derivation. (#EPIC-AcParentChildLinkEnforcement/06)
  Implements ACD-1200a-6: _derive_epic_name() replaces bare _to_pascal_case() in
  run(). When naive PascalCase result exceeds 40 characters, attempts LLM
  summarisation via _summarise_title_via_llm() (claude-3-5-haiku-latest, one-shot
  prompt for concise PascalCase of at most 5 words). Falls back to
  _truncate_pascal_at() which truncates at the last complete PascalCase word
  boundary within 40 characters when the model is unavailable or errors. Rejects
  naive concatenations like "Crossfieldconstraintsandrelationalreferencesareenforcedtogether".
- 2026-06-08 12:00 [EPIC-AcParentChildLinkEnforcement/07]: Master_Plan.md generation. (#EPIC-AcParentChildLinkEnforcement/07)
  Implements ACD-1200a-7: generate_master_plan() writes Master_Plan.md at the
  root of the assembled EPIC folder. The file follows the canonical create-epic
  structure (YAML frontmatter with epic_name, created, status, components,
  source_ac; ## Goal, ## Tickets, ## Dependencies, ## Agent Assignments sections).
  Helper functions: _read_ticket_frontmatter() parses ticket YAML frontmatter,
  _collect_master_plan_data() aggregates data from all numbered ticket files in
  the epic folder, _render_master_plan() renders the markdown content. run() now
  calls generate_master_plan() after assemble_epic_folder() succeeds; OSError
  during Master_Plan write is non-fatal (logged as WARNING; epic folder is already
  assembled at that point). Goal summary is derived from the AC title when no
  richer description is available.
- 2026-06-08 [EPIC-GoalToEpic/08]: Master_Plan.md generation. (#EPIC-GoalToEpic/08)
  Implements ACD-1200a-8: generate_master_plan() writes Master_Plan.md into the
  assembled EPIC folder immediately after assemble_epic_folder() completes. File
  includes: epic name and source AC id (identity block), goal AC criteria text
  (purpose statement via _read_ac_criteria()), ordered sub-ticket list with titles
  (via _read_ticket_title() parsing frontmatter YAML), and dependency graph edges
  expressed as depends_on per ticket filename. Idempotent: existing Master_Plan.md
  with identical content is not rewritten. OSError on write is caught and surfaces
  as a non-zero CLI exit. Helper functions: _read_ticket_title(), _read_ac_criteria(),
  generate_master_plan(). Integration point: run() calls generate_master_plan()
  after epic_folder is created, using the already-computed dep_graph and topo_order.
- 2026-06-18 [BP-901]: Defer _find_worktree_root() when both CLI paths are supplied.
  Root cause: main() called _find_worktree_root(Path(__file__)) unconditionally
  before checking whether --store-root / --inbox-dir were provided. When the script
  is deployed to .leafcutter/scripts/ (outside any git tree) and both flags are
  passed explicitly, the call raised FileNotFoundError and exited 1 even though
  the worktree value would never have been used (it only constructs the default
  paths). Fix: restructured the path-resolution block in main() to check whether
  both args.store_root and args.inbox_dir are present. If so, Path() wrappers are
  applied directly and _find_worktree_root() is not called at all. When either
  default is needed the try/except block runs as before. Covered by regression
  test tests/test_goal_to_epic_worktree_skip.py::TestMainSkipsWorktreeWhenBothPathsSupplied.
- 2026-06-22 [EPIC-GoalToEpicBugfixes/01]: Single-location write + correct implemented_by.
  Implements ACD-1200a-9: fixes dual-write bug where each generated ticket was
  written to tickets/00_inbox/<file>.md (loose) AND copied into the epic folder.
  Added _build_loose_to_epic_map(), _remove_loose_inbox_tickets(), and
  _replace_implemented_by_entry(). run() now calls these three helpers after
  assemble_epic_folder() succeeds: (1) builds the loose→epic path mapping,
  (2) updates implemented_by in each source AC YAML from the loose path to the
  epic-folder path (with numeric prefix), (3) removes the loose inbox copies.
- 2026-06-22 [EPIC-GoalToEpicBugfixes/02]: Basename collision resolution.
  Implements ACD-1200a-9-i: when a generated ticket's computed basename already
  exists at the epic-folder path, assemble_epic_folder() overwrites it in place
  rather than raising EpicFolderConflictError or minting a renamed sibling.
  A WARNING log line is emitted for each overwrite so the replacement is
  observable. The epic folder is now created with exist_ok=True so partial
  re-runs converge correctly. EpicFolderConflictError is no longer raised by
  assemble_epic_folder(); run() exception handler updated to catch OSError in
  its place. After the run exactly one ticket file with the computed basename
  exists at the epic-folder path, and implemented_by names that single path
  (consistent with ACD-1200a-9).
- 2026-06-22 [BP-901 regression fix]: Restore the BP-901 contract after the
  ACD-1200a-9 regression. EPIC-GoalToEpicBugfixes/01 (c2b2566) re-introduced a
  _find_worktree_root(Path(__file__)) call inside the both-paths-supplied branch
  of main() (wrapped in try/except FileNotFoundError) so run() could obtain a
  worktree root for loose-ticket-path relativisation. That call violated BP-901
  ("_find_worktree_root must NOT be called when both --store-root and --inbox-dir
  are supplied") — the regression test asserts zero calls, not merely a swallowed
  error. Fix: added _derive_worktree_from_inbox(), a pure path-math helper that
  derives the worktree root from the supplied inbox_dir (stripping the
  conventional tickets/00_inbox suffix), and replaced the _find_worktree_root
  call in the both-paths branch with it. This satisfies BOTH BP-901 (no
  filesystem walk / no _find_worktree_root call) and ACD-1200a-9 (run() still
  receives a worktree root for relativisation when inbox_dir follows the
  convention; falls back to None otherwise). Covered by
  tests/test_goal_to_epic_worktree_skip.py.
- 2026-07-20 [ACD-1200b-4]: Non-interactive readiness gate.
  Implements ACD-1200b-4: added --yes and --approved-only argparse flags to
  _build_parser(). Extended run() with matching yes/approved_only bool parameters
  (default False, backward-compatible). At the readiness gate in run(), TTY state
  is detected via sys.stdin.isatty(). When stdin has no controlling TTY and neither
  flag is set, the gate prints a clear error message naming --yes and --approved-only,
  then calls sys.exit(1) — never calls input(). When --yes or --approved-only is set,
  the gate proceeds with only the already-approved leaf ACs (same routing as choosing
  "yes" at the interactive prompt). Interactive (TTY present, no flags) behaviour is
  unchanged. main() passes args.yes and args.approved_only through to run().
- 2026-07-17 [ACD-1200a-3-iii]: ASCII-safe slug and dry-run/real-run parity.
  Implements ACD-1200a-3-iii: (1) Added _normalize_non_ascii_punct() to strip
  non-ASCII punctuation (em-dash, en-dash, smart quotes, etc.) to spaces before
  PascalCase conversion, ensuring the derived folder name contains only ASCII
  alphanumeric characters. (2) Updated _to_pascal_case() split regex to
  r"(?=[A-Z])|[\\s\\-_]+" so the function is idempotent on already-PascalCase
  strings (splits on PascalCase word boundaries in addition to whitespace/hyphens).
  (3) Removed redundant _to_pascal_case() call from assemble_epic_folder(); the
  caller (run()) already passes a pre-derived PascalCase epic_name from
  _derive_epic_name(), and re-applying the conversion corrupted the casing via
  str.capitalize() on a single-token PascalCase string. Both dry-run and real-run
  now use the same derived name from a single shared code path (n_location_rule: 1).
  Must not regress ACD-1200a-3-ii (apostrophe/quote stripping still applied via
  _strip_quote_chars() in _to_pascal_case()).
- 2026-08-12 [BO-2600a-5]: Explicit id-list entrypoint and two hygiene fixes.
  Implements BO-2600a-5: adds build_epic_from_ids(ids, *, store_root, inbox_dir)
  and a matching --ids CLI mode so fast_lane.resolve_connected_build_set() can
  pass its full connected-set result (including cross-tree prerequisites) directly
  to epic assembly without re-walking a single AC's subtree via traverse_ac_tree().
  Root defect closed: the existing --ac path re-walks the covered_by subtree and
  drops any leaf that lives outside the first AC's tree but was included by the
  connected-set resolution. The new path takes the id list as authoritative.
  Internals reused: resolve_leaf_dependencies (restricted to the given id set via
  the existing out-of-set edge filter), topological_sort, generate_tickets_for_leaves,
  assemble_epic_folder, generate_master_plan. --ac mode is preserved unchanged
  (backward compatible). Two hygiene fixes applied in the same pass:
  (a) _translate_ticket_depends_on() translates AC ids in ticket depends_on fields
  to co-located epic-folder filenames at generation time (so ticket_frontmatter_guard
  passes without a downstream hook auto-fix); (b) implemented_by back-references
  written into source AC YAMLs are repo-relative (start with "tickets/", never
  absolute worktree paths). CLI: _build_parser() now uses a mutually exclusive
  group (required=True) containing --ac and --ids; main() routes on args.ids.
  Covered by 6 unit tests in unit_tests/build_orchestration/test_bo_2600a_5.py;
  how-to documentation added in docs/how-to/goal-to-epic.md §5.
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
- 2026-09-14 12:00 [goal-to-epic-decompose]: Decomposed into fourteen sibling
  modules under scripts/ac_store/. This file was 2809 lines against a 400-line
  check_file_size limit, and carried three functions over the complexity
  threshold of 15 (_replace_implemented_by_entry at 19, run() at 18,
  _collect_master_plan_data at 16). Behaviour is unchanged: no CLI flag, exit
  code, printed string or public signature moved. See the module map in this
  file's header docstring for the split, and each sibling's own DECISION
  HISTORY for what moved there and what was edited in transit.

  Four decisions worth recording here rather than in a leaf module:
  (a) Every entry ABOVE this one is left byte-identical and in this file. They
      describe behaviour that now lives elsewhere, but relocating them would
      make each line an "added" line at commit time, and
      transform_decision_history rewrites added DECISION HISTORY entries —
      injecting the current UTC HH:MM and a TICKETLESS tail tag into records
      dated 2026-06. Fabricating timestamps on historical entries is a worse
      outcome than a slightly over-long history block, and keeping them here
      also satisfies "a complete list reachable from goal_to_epic.py".
  (b) The new modules live at scripts/ac_store/<name>.py, NOT in a
      scripts/goal_to_epic/ package. build_ac_store FLATTENS this file into
      <output_root>/scripts/ac_store/, so a package directory would not survive
      deploy; placing the siblings in ac_store/ makes source name and deployed
      name identical and lets the existing _sibling_dir guard resolve them.
  (c) The sys.path push moved from inside run() to module scope, because the
      re-export block needs the siblings importable at load time. The guard
      itself (_scripts_dir / _sibling_dir, the IfExp form) is untouched —
      scripts/build_referential_integrity.py cites it at five places as the
      canonical live instance of the dual-layout pattern.
  (d) Every extracted module logs through epic_runtime.get_logger(), never
      logging.getLogger(__name__). The logger NAME is observable: pre-split
      every record was emitted under "goal_to_epic", and
      tests/test_goal_to_epic_basename_collision.py asserts on exactly that via
      assertLogs("goal_to_epic", ...). One accepted micro-difference follows:
      when this file is run AS a script, __name__ is "__main__", so records
      that were previously named "__main__" are now named "goal_to_epic".
      Nothing formats the logger name (no handler is configured; WARNING goes
      to logging's lastResort handler, which prints the message alone), so no
      stdout/stderr output changes.
  (#TICKETLESS reason=file-size-decomposition-refactor)
====================================================================
"""
