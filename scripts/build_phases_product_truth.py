"""
MODULE: build_phases_product_truth
GOAL: Deploy the product-truth tooling AND scaffold the record itself into a
    consumer project.
BUSINESS CONTEXT: build_phases.py is grandfathered many times over the
    400-content-line check-file-size limit, and the GE-127b-1 ratchet refuses
    any change that leaves an already-oversized file longer than it was.
    EPIC-TruthfulProjectRecord grew this phase substantially -- UXP-700a-1 added
    the write-if-absent record scaffold (directories, an index declaring zero
    artifacts, the checker's classifier/eval.jsonl start-up input and a written
    introduction) and UXP-700a-4-i added the by-name verification that every
    file the checker opens before checking begins was really installed. Carrying
    the whole phase out here restores headroom with no behaviour change, exactly
    as build_phases_knowledge.py did for the knowledge-plane phases.
ARCHITECTURE: One public phase function, ``build_product_truth``, re-exported
    from build_phases.py so every existing caller keeps working unchanged. Its
    imports of build_phases's private write/deploy helpers (``PACKAGE_ROOT``,
    ``_should_overwrite``, ``_files_content_identical``, ``record_deploy_failure``,
    ``_write``) and of the shared ``_uptodate_count`` module state are deferred
    to function scope, because build_phases.py imports this module at its own
    top level and a module-scope import back would be circular.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
import logging
from typing import Any

_log = logging.getLogger(__name__)


#: The artifact-type directories a record is made of, each paired with the
#: plain-language name the introduction calls it by. One list drives both the
#: scaffold and the generated introduction, so a type can never be created
#: without being introduced (UXP-700a-1).
_PRODUCT_TRUTH_ARTIFACT_TYPES: list[tuple[str, str, str]] = [
    ("flows", "journeys", "a journey — the path a person takes through the product"),
    ("mock-data", "example data", "the example records those screens are populated from"),
    ("mockups", "screens", "a screen a journey passes through"),
]


#: The derived lookups the index carries. Present-and-empty in a fresh record
#: so a consumer reading one never has to tell "no such lookup" apart from
#: "this lookup is empty" (UXP-700a-1).
_PRODUCT_TRUTH_DERIVED_LOOKUPS: tuple[str, ...] = ("by_component", "by_entity", "by_flow", "by_ac")


def _empty_product_truth_index() -> str:
    """Return the JSON text of an index declaring a complete, empty record."""
    index: dict[str, Any] = {
        "version": 1,
        "description": (
            "This project's product-truth record. Empty until the first journey, "
            "example-data set or screen is authored; regenerate it with "
            "docs/product-truth/scripts/generate_product_truth.py."
        ),
        "search_dimensions": [],
        "entity_registry": [],
        "artifacts": [],
    }
    for lookup in _PRODUCT_TRUTH_DERIVED_LOOKUPS:
        index[lookup] = {}
    return json.dumps(index, indent=2, ensure_ascii=False) + chr(10)


def _product_truth_introduction() -> str:
    """Return the introduction written into a fresh, empty record.

    Names each artifact type, the directory it lives in, and the first thing to
    author, so a project that has never used the tooling can start without
    reading the generator's source.
    """
    lines = [
        "# Product truth",
        "",
        "This is this project's **product-truth record**: what the product does,",
        "held as data rather than prose so it can be checked against the code.",
        "",
        "It is currently **empty** — nothing has been authored yet.",
        "",
        "## What lives where",
        "",
        "| Directory | Artifact type | What it holds |",
        "| --- | --- | --- |",
    ]
    for directory, type_name, blurb in _PRODUCT_TRUTH_ARTIFACT_TYPES:
        lines.append(f"| `{directory}/` | {type_name} | {blurb} |")
    lines += [
        "",
        "`index.json` is derived from those three directories — it is generated,",
        "never hand-edited. `schemas/` holds the JSON Schema each artifact is",
        "validated against, and `scripts/` the generator and checker themselves.",
        "",
        "## The first thing to author",
        "",
        "Start by writing one journey in `flows/` — a single path a person takes",
        "through the product, end to end. A journey is the only artifact that",
        "stands on its own; screens and example data are written to serve one.",
        "",
        "Then run:",
        "",
        "```",
        "python docs/product-truth/scripts/generate_product_truth.py",
        "python docs/product-truth/scripts/validate_product_truth.py",
        "```",
        "",
        "The first regenerates `index.json` from what you authored; the second",
        "checks the record and states what it examined.",
        "",
    ]
    return chr(10).join(lines)


#: Files the product-truth checker opens BEFORE it begins per-artifact
#: checking. A deploy that silently omits one of these installs a checker that
#: cannot start, so each is verified by name after the copy loop rather than
#: left to the glob (which simply yields one fewer file and reports nothing).
#: Declared as a list so a new start-up input is added here, once
#: (UXP-700a-4-i).
_PRODUCT_TRUTH_REQUIRED_FILES: tuple[str, ...] = (
    "schemas/flow.schema.json",
    "schemas/mock-data.schema.json",
    "schemas/mockup.schema.json",
    "schemas/classifier-eval.schema.json",
    "scripts/generate_product_truth.py",
    "scripts/validate_product_truth.py",
)


def _verify_product_truth_required_files(output_base: Path, dry_run: bool) -> None:
    """Fail the build when a declared start-up input was not installed.

    The copy loop above globs, so a file missing from the package source is
    simply never copied and the build would otherwise finish green having
    installed a checker that cannot run. Each missing file is RECORDED (not
    raised on the spot) so one run reports the whole remediation set; build.py
    raises once at the end (UXP-700a-4-i).

    Args:
        output_base: The target project's docs/product-truth/ directory.
        dry_run: When True, nothing was written, so nothing is verified.
    """
    # Deferred: build_phases imports THIS module at its own top level, so a
    # module-scope import back would be circular. Same pattern, and same
    # reason, as build_phases_knowledge.py.
    import build_phases as _bp  # noqa: PLC0415

    if dry_run:
        return
    product_truth_src = _bp.PACKAGE_ROOT / "docs" / "product-truth"
    for rel in _PRODUCT_TRUTH_REQUIRED_FILES:
        if not (output_base / rel).is_file():
            # Named repo-relative, the way a reader would go find it, rather
            # than as the absolute temp path of whichever install produced it.
            _bp.record_deploy_failure(
                "build_product_truth",
                f"docs/product-truth/{rel}",
                product_truth_src / rel,
            )


def _scaffold_product_truth_record(output_base: Path, dry_run: bool) -> int:
    """Write-if-absent scaffold of a complete, runnable, EMPTY record.

    Lays down one directory per artifact type, an index declaring zero
    artifacts with every derived lookup present and empty, the checker's
    classifier/eval.jsonl startup input, and a written introduction — so a
    project that has never used the tooling can run the checker to a stated
    verdict immediately after install instead of crashing on a missing input
    (UXP-700a-1, UXP-700a-1-i).

    Never touches an already-populated record (write-if-absent, force
    ignored — see this module's DECISION HISTORY for UXP-700a-1-ii).
    """
    # Deferred: build_phases imports THIS module at its own top level, so a
    # module-scope import back would be circular. Same pattern, and same
    # reason, as build_phases_knowledge.py.
    import build_phases as _bp  # noqa: PLC0415

    written = 0
    for data_subdir, _type_name, _blurb in _PRODUCT_TRUTH_ARTIFACT_TYPES:
        data_dir = output_base / data_subdir
        if not data_dir.exists():
            if dry_run:
                print(f"  [DRY-RUN] would create docs/product-truth/{data_subdir}/")
            else:
                data_dir.mkdir(parents=True, exist_ok=True)

    scaffold_files = [
        ("index.json", _empty_product_truth_index()),
        # The eval check's precondition. Seeded EMPTY (a zero-row .jsonl is a
        # valid, well-formed eval set) so the checker opens it, finds nothing
        # to check and says so, rather than crashing on a missing file before
        # per-artifact checking begins (UXP-700a-1-i).
        (str(Path("classifier") / "eval.jsonl"), ""),
        ("README.md", _product_truth_introduction()),
    ]
    for rel_name, content in scaffold_files:
        if _bp._write(output_base / rel_name, content, dry_run, force=False):
            print(f"  docs/product-truth/{Path(rel_name).as_posix()}")
            written += 1

    return written


def build_product_truth(target_root: Path, config: dict[str, Any],
                        dry_run: bool, force: bool) -> int:
    """Deploy product-truth tooling to ``<target_root>/docs/product-truth/``.

    Copies the package-owned product-truth generator/validator scripts
    (``docs/product-truth/scripts/*.py``) and their JSON schemas
    (``docs/product-truth/schemas/*.json``) into the consumer project's
    ``docs/product-truth/`` tree so they exist at runtime. The ``/plan-feature``
    workflow's product-truth phase (see EPIC wiring) invokes these scripts via
    ``python docs/product-truth/scripts/generate_product_truth.py`` relative to
    the project root; without this phase they are absent in a consumer or fresh
    worktree and the phase can only no-op.

    Both subdirectories are copied with a shallow ``*.py`` / ``*.json`` glob so
    that additional generator/validator scripts or schemas added later are
    deployed automatically without editing this phase. Only the package-owned
    ``scripts/`` and ``schemas/`` subdirectories are copied by this loop — the
    project-authored product-truth DATA (flows, mock-data, mockups,
    ``index.json``) is scaffolded separately (write-if-absent, never
    overwritten) by ``_scaffold_product_truth_record``.

    Files are copied verbatim (no template compilation). The compare-before-write
    guard prevents mtime churn on unchanged files.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary (accepted for interface parity; not consumed).
        dry_run: When True, logs intent but writes nothing.
        force: When True, overwrites existing files.

    Returns:
        Count of files written (or that would be written in dry-run mode).
    """
    # Deferred: build_phases imports THIS module at its own top level, so a
    # module-scope import back would be circular. Same pattern, and same
    # reason, as build_phases_knowledge.py.
    import build_phases as _bp  # noqa: PLC0415

    product_truth_src = _bp.PACKAGE_ROOT / "docs" / "product-truth"

    # (source_subdir, glob, dest_subdir) triples. The glob is intentionally
    # broad so new .py / .json files are picked up without editing this phase.
    deploy_groups = [
        (product_truth_src / "scripts", "*.py", "scripts"),
        (product_truth_src / "schemas", "*.json", "schemas"),
    ]

    output_base = target_root / "docs" / "product-truth"
    written = 0

    for src_dir, pattern, dest_subdir in deploy_groups:
        if not src_dir.is_dir():
            # BP-900g-9 (n_location_rule: all). The glob (pattern) applies
            # only WITHIN this declared subdir, so the subdir itself is a
            # declared entry, not a bare directory scan — a missing one is
            # the same dropped promise as a missing declared file. Was
            # warn-and-continue. Record and keep going so one run reports
            # the whole remediation set; build.py raises once at the end.
            _bp.record_deploy_failure("build_product_truth", dest_subdir, src_dir)
            continue

        output_dir = output_base / dest_subdir

        for src_file in sorted(src_dir.glob(pattern)):
            if not src_file.is_file():
                continue

            output_path = output_dir / src_file.name

            if not _bp._should_overwrite(output_path, force):
                continue

            if _bp._files_content_identical(src_file, output_path):
                _bp._uptodate_count += 1  # noqa: SLF001 -- shared build-run counter
                continue

            if dry_run:
                print(f"  [DRY-RUN] would copy docs/product-truth/{dest_subdir}/{src_file.name}")
                written += 1
            else:
                try:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src_file, output_path)
                except OSError as exc:
                    _log.warning(
                        "build_product_truth: failed to copy %s → %s: %s",
                        src_file,
                        output_path,
                        exc,
                    )
                    raise
                print(f"  docs/product-truth/{dest_subdir}/{src_file.name}")
                written += 1

    written += _scaffold_product_truth_record(output_base, dry_run)
    _verify_product_truth_required_files(output_base, dry_run)

    return written

"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-10 [python-coder]: Extracted build_product_truth and its scaffold /
  required-file helpers from build_phases.py, which the epic's additions had
  pushed from 2709 to 2862 content lines -- a growth the GE-127b-1 ratchet
  refuses for a file already over its limit. Pure move, following the
  build_phases_knowledge.py precedent set on 2026-09-09 for the same reason:
  build_phases.py re-exports build_product_truth, so build.py and every other
  caller are untouched. Helper imports stay function-scoped to avoid the
  circular import. (#EPIC-TruthfulProjectRecord)
====================================================================
"""
