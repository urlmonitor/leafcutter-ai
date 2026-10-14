#!/usr/bin/env python3
"""
MODULE: requirement_rule_check
GOAL: Check the requirement records of one feature folder against the rule families,
    repair the three one-right-answer violations, and print ONE JSON report whose
    verdict (and exit status) decides whether an authoring stage is complete.
BUSINESS CONTEXT: ACD-2500a-1 / -1-i / -1-ii / -2. /plan-feature must not report an
    authoring stage complete on the stage agent's word. This script is run at the end of
    each stage; the workflow reads the exit status and the JSON report, never prose. It
    fails closed: zero records, an unreadable record, a family that raises, an unreadable
    rule source, a missing before-state or an unknown stage are all verdict `failed`.
ARCHITECTURE: Two-pass orchestration. Load the folder; pass 1 hands every record to
    every family; the orchestrator applies every `repair` through `_rc_edit` (the only
    writer); only the written records are re-loaded; pass 2 evaluates everything again.
    The report is the `fixed` entries of pass 1 plus every pass-2 finding (a `fixed`
    entry whose key still has a pass-2 finding is replaced by it). `passed` iff
    records_checked > 0 and pass 2 has no `needs a decision` or `failed` finding. Exit
    0 passed, 1 failed, 2 usage error. stdout is the JSON document and nothing else;
    logging goes to stderr and is configured inside `main()` only. `--changed-since REV` replaces
    --location/--for-ids: the checked set is every record file under --store-root that is
    modified, added or untracked against REV (_rc_changed); unchanged parents are still read and
    repaired through `ctx.sibling`; the report gains `records_to_commit` (sorted repo-relative POSIX
    paths of every record changed against REV after the run, repaired parents included). Nothing
    changed, or a git failure, is `failed`. `--for-ids` is `failed` for an id absent from the store
    or outside the checked folder. Flat sibling modules:
    _rc_report (Finding, verdict, dump), _rc_records (load, Context, before-state),
    _rc_record_schema (the store's record check as a caller), _rc_edit (the writer),
    and one _rc_* module per rule family. Deployed flat into <root>/scripts/ac_store/.

HOW A RULE FAMILY REGISTERS (read this before adding one):
  1. Write scripts/ac_store/_rc_<name>.py exposing
        NAME = FAMILY_X                      # the report's rule_family (see _rc_report)
        def evaluate_record(ctx, record) -> list[Finding]
     and, optionally, CLAIMS_SUBJECTS = ("components",) to take over a subject of the
     store's record check from the "record schema" adapter (read it with
     `_rc_record_schema.messages_for(ctx, record, subject)`).
  2. Register it: `import _rc_<name>` here and append the module to FAMILIES below
     (order is evaluation order). Add the module to AC_STORE_DEPLOY_MAP
     (scripts/build_phases_ac_store_rc.py). Nothing else changes.
  3. `evaluate_record` is PURE: it never writes. `record` is a dict subclass (read
     `record["covered_by"]`) with `.file`, `.path` and `.text`. `ctx` offers
     `ctx.records` (the checked folder, current pass), `ctx.sibling(id)`,
     `ctx.store_record(id)` / `ctx.id_index` (the whole store), `ctx.stage`,
     `ctx.before_state(record) -> (existed, readiness)`, `ctx.schema`,
     `ctx.registry_ids`, `ctx.surface_map_path` and `ctx.migration_map`.
  4. Build findings with `Finding.for_record(record, NAME, DISPOSITION_*, message,
     subject=..., line=..., detail=...)`. Findings are deduped on (file, record_id,
     rule_family, subject) and the highest disposition wins. Use `not evaluated` for a
     record the family could not judge (it never fails the verdict and is counted in
     family_counts).
  5. A repairing family returns a `fixed` finding with `repair=(field, how)` for the
     record the change lands on (the finding's file/record_id: a back-link lands on
     the PARENT): field in {covered_by, components, readiness}; how is ("set", value)
     or ("append", item). The orchestrator hands it to `_rc_edit.apply_edit`; a refused
     or unprovable write becomes a `failed` finding. A family that raises becomes a
     `failed` finding for that record and family; the run continues.

DECISION HISTORY:
  - 2026-10-14 [python-coder/ACD-2500a-1]: Created per the architect-review note
    (sections 1-3). `--stage` is validated here (not by argparse) so an unknown stage
    is a failed report, not an exit-2 usage error.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import yaml

import _rc_backlinks
import _rc_changed
import _rc_components
import _rc_contracts
import _rc_declared
import _rc_design_grounding
import _rc_doc_triggers
import _rc_readiness
import _rc_record_schema
import _rc_test_intent
from _ac_components import load_registry_ids
from _rc_edit import EditError, ProtectedFieldError, apply_edit
from _rc_records import (
    BeforeState,
    Context,
    Record,
    build_id_index,
    common_location,
    infer_repo_root,
    load_folder,
    load_one,
    load_paths,
    report_location,
    unreachable_id_findings,
)
from _rc_report import (
    DISPOSITION_FAILED,
    FAMILY_READINESS,
    FAMILY_RECORD_READABLE,
    FAMILY_RECORD_SCHEMA,
    Finding,
    build_report,
    dedupe,
    dump_report,
    family_counts,
    sort_findings,
)
from validate_ac_schema import load_ac_store_schema

logger = logging.getLogger("requirement_rule_check")

# Ordered rule-family registry; read at call time. See "HOW A RULE FAMILY REGISTERS".
FAMILIES: list[Any] = [
    _rc_record_schema, _rc_backlinks, _rc_components, _rc_readiness, _rc_contracts, _rc_doc_triggers,
    _rc_declared.FAMILY_SURFACE_RULE, _rc_declared.FAMILY_MODIFIES_RULE, _rc_test_intent,
    _rc_design_grounding,
]

STAGES = ("po", "ba", "itpo", "test-design", "approval")
_AUTHORING_STAGES = ("po", "ba", "itpo", "test-design")


def _build_parser() -> argparse.ArgumentParser:
    """The CLI parser (flags of architect-review section 1 plus --migration-map)."""
    parser = argparse.ArgumentParser(
        prog="requirement_rule_check",
        description="Check a feature folder's requirement records; print one JSON report.",
    )
    parser.add_argument("--location", help="the feature folder (required unless --for-ids / --changed-since)")
    parser.add_argument("--for-ids", help="comma-separated record ids; location = their deepest common folder")
    parser.add_argument("--changed-since", help="git REV: check every record file under the store changed against it")
    parser.add_argument("--store-root", help="default <repo-root>/docs/acceptance-criteria")
    parser.add_argument("--repo-root", help="default: nearest ancestor of the location holding docs/acceptance-criteria")
    parser.add_argument("--stage", help="one of: " + ", ".join(STAGES))
    parser.add_argument("--before-ref", help="git revision holding the readiness before-state")
    parser.add_argument("--before-snapshot", help="JSON file {id: readiness|null} (before-state)")
    parser.add_argument("--schema", help="override config/ac_store_schema.json")
    parser.add_argument("--components-registry", help="override docs/components.json")
    parser.add_argument("--surface-map", help="override config/surface_craft_map.yaml")
    parser.add_argument("--migration-map", help="override the namespace-to-graph-ids map (JSON or YAML)")
    return parser


def _resolve_folder(args: argparse.Namespace) -> tuple[Context, str, list[Finding]]:
    """The Context shell (paths only), the raw location string, and any id-lookup finding."""
    if args.repo_root:
        repo_root = Path(args.repo_root).resolve()
    else:
        seed = Path(args.location) if args.location else Path.cwd()
        repo_root = infer_repo_root(seed)
    store_root = Path(args.store_root).resolve() if args.store_root else repo_root / "docs" / "acceptance-criteria"
    ctx = Context(repo_root=repo_root, folder=repo_root, store_root=store_root, stage=args.stage or "")
    if args.changed_since:
        ctx.folder, ctx.changed_since = store_root, args.changed_since
        return ctx, args.changed_since, []
    if args.for_ids:
        ids = [i.strip() for i in args.for_ids.split(",") if i.strip()]
        ctx._index = build_id_index(store_root)  # noqa: SLF001 - preset: one walk per run
        folder = common_location(store_root, ids, ctx._index)  # noqa: SLF001
        raw = ",".join(ids)
        ctx.folder = folder if folder is not None else store_root / "(no such records)"
        return ctx, raw, unreachable_id_findings(ids, ctx._index, folder, raw)  # noqa: SLF001
    raw = args.location or ""
    candidate = Path(raw)
    if not candidate.is_absolute() and not candidate.exists():
        candidate = repo_root / raw
    ctx.folder = candidate.resolve()
    return ctx, raw, []


def _rule_source_findings(ctx: Context, args: argparse.Namespace) -> list[Finding]:
    """Load schema, registry and migration map into `ctx`; an unreadable source is a `failed` finding."""
    found: list[Finding] = []

    def fail(source: str, message: str) -> None:
        found.append(Finding(source, None, FAMILY_RECORD_SCHEMA, DISPOSITION_FAILED,
                             f"rule source unreadable: {message}", subject=f"rule-source:{source}"))

    ctx.schema_path = Path(args.schema) if args.schema else None
    ctx.schema, warning = load_ac_store_schema(ctx.schema_path)
    if warning:
        fail("config/ac_store_schema.json", warning)
    ctx.registry_path = Path(args.components_registry) if args.components_registry else ctx.repo_root / "docs" / "components.json"
    ctx.registry_ids = load_registry_ids(ctx.registry_path)
    if not ctx.registry_ids:
        fail("docs/components.json", f"components registry {ctx.registry_path.name} is missing, empty or unreadable")
    ctx.surface_map_path = Path(args.surface_map) if args.surface_map else None
    ctx.migration_map, error = _load_migration_map(args.migration_map)
    if error:
        fail("migration map", error)
    return found


def _load_migration_map(override: str | None) -> tuple[dict[str, Any], str | None]:
    """(namespace-to-graph-ids map, error): the --migration-map file, else the shipped map."""
    if override:
        try:
            data = yaml.safe_load(Path(override).read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            return {}, f"cannot read migration map {Path(override).name}: {exc}"
        return (data, None) if isinstance(data, dict) else ({}, "migration map is not a mapping")
    try:
        from _component_migration_map import MIGRATION_MAP  # noqa: PLC0415 - only when no override
    except ImportError as exc:
        return {}, f"shipped migration map unavailable: {exc}"
    return dict(MIGRATION_MAP), None


def _before_state(ctx: Context, args: argparse.Namespace, location: str) -> list[Finding]:
    """Validate the stage and set up the before-state; every gap is a `failed` finding."""
    if ctx.stage not in STAGES:
        message = f"unrecognised --stage {ctx.stage!r}; expected one of {list(STAGES)}"
        return [Finding(location, None, FAMILY_READINESS, DISPOSITION_FAILED, message, subject="stage")]
    if args.before_snapshot:
        ctx.before = BeforeState.from_snapshot_file(Path(args.before_snapshot))
    elif args.before_ref:
        ctx.before = BeforeState(ref=args.before_ref)
    elif ctx.stage in _AUTHORING_STAGES:
        message = "before-state unavailable: pass --before-ref or --before-snapshot for an authoring stage"
        return [Finding(location, None, FAMILY_READINESS, DISPOSITION_FAILED, message, subject="before-state")]
    return []


def _call_family(ctx: Context, family: Any, record: Record) -> list[Finding]:
    """Run one family on one record; any failure becomes a `failed` finding, never a skip."""
    name = getattr(family, "NAME", repr(family))
    try:
        produced = list(family.evaluate_record(ctx, record))
    except Exception as exc:  # noqa: BLE001 - fail closed: a raising family must not skip or abort the run
        logger.warning("rule family %r raised on %s: %s", name, record.file, exc)
        message = f"rule family {name!r} raised {type(exc).__name__}: {exc}"
        return [Finding.for_record(record, name, DISPOSITION_FAILED, message, subject="exception")]
    for item in produced:
        if not isinstance(item, Finding):
            message = f"rule family {name!r} returned {type(item).__name__}, not a Finding"
            return [Finding.for_record(record, name, DISPOSITION_FAILED, message, subject="bad-return")]
    return produced


def _evaluate(ctx: Context, records: list[Record], families: list[Any]) -> tuple[list[Finding], dict[str, int]]:
    """One pass: every record to every family. Returns (findings, records handed per family)."""
    ctx.records = records
    found: list[Finding] = []
    handed = {getattr(f, "NAME", repr(f)): 0 for f in families}
    for record in records:
        for family in families:
            found.extend(_call_family(ctx, family, record))
            handed[getattr(family, "NAME", repr(family))] += 1
    return found, handed


def _apply_repairs(ctx: Context, findings: list[Finding]) -> tuple[list[Finding], list[Finding], set[str]]:
    """Hand every repair to _rc_edit. Returns (fixed entries, write failures, files written)."""
    fixed: list[Finding] = []
    failures: list[Finding] = []
    touched: set[str] = set()
    for finding in findings:
        if finding.repair is None:
            continue
        field, how = finding.repair
        try:
            changed = apply_edit(ctx.repo_root / finding.file, field, how)
        except (ProtectedFieldError, EditError, OSError, yaml.YAMLError) as exc:
            logger.warning("repair of %s in %s refused: %s", field, finding.file, exc)
            failures.append(replace(finding, disposition=DISPOSITION_FAILED, repair=None,
                                    message=f"repair of {field!r} was not applied: {exc}"))
            continue
        if changed:
            logger.info("repaired %s in %s (%s)", field, finding.file, finding.message)
            touched.add(finding.file)
            fixed.append(replace(finding, repair=None))
    return fixed, failures, touched


def _reload(ctx: Context, records: list[Record], touched: set[str]) -> tuple[list[Record], list[Finding]]:
    """Re-load only the written records; one that no longer reads becomes a `failed` finding."""
    findings: list[Finding] = []
    kept: list[Record] = []
    for record in records:
        if record.file not in touched:
            kept.append(record)
            continue
        loaded = load_one(ctx.repo_root / record.file, ctx.repo_root)
        if isinstance(loaded, Record):
            kept.append(loaded)
        else:
            findings.append(loaded)
    return kept, findings


def _unrepaired(finding: Finding) -> Finding:
    """A pass-2 finding still carrying a repair means the repair did not stick."""
    if finding.repair is None:
        return finding
    return replace(finding, disposition=DISPOSITION_FAILED, repair=None,
                   message=f"still violated after the repair pass: {finding.message}")


def _load_scope(ctx: Context, setup: list[Finding]) -> tuple[list[Record], list[Finding], int]:
    """The records to check: the whole folder, or (--changed-since) the files git reports changed."""
    if not ctx.wide:
        return load_folder(ctx.folder, ctx.repo_root)
    try:
        files = _rc_changed.changed_record_files(ctx.repo_root, ctx.store_root, str(ctx.changed_since))
    except _rc_changed.ChangedError as exc:
        setup.append(Finding(str(ctx.changed_since), None, FAMILY_RECORD_READABLE, DISPOSITION_FAILED,
                             f"cannot list records changed since {ctx.changed_since}: {exc}", subject="git"))
        return [], [], 0
    return load_paths([ctx.repo_root / f for f in files], ctx.repo_root)


def _records_to_commit(ctx: Context) -> list[str]:
    """Record files changed against the rev AFTER the run (repaired parents included); [] on a git failure."""
    try:
        return _rc_changed.changed_record_files(ctx.repo_root, ctx.store_root, str(ctx.changed_since))
    except _rc_changed.ChangedError as exc:
        logger.warning("records_to_commit unavailable: %s", exc)  # _load_scope already reported it as `failed`
        return []


def run_check(ctx: Context, location: str, setup: list[Finding]) -> dict[str, Any]:
    """Load, evaluate, repair, reload, evaluate again; return the report dict."""
    families = list(FAMILIES)
    ctx.families = families
    records, load_findings, seen = _load_scope(ctx, setup)
    if ctx.before is not None:
        ctx.before.prefetch(records, ctx.repo_root)
        if ctx.before.error:
            setup.append(Finding(location, None, FAMILY_READINESS, DISPOSITION_FAILED,
                                 ctx.before.error, subject="before-state"))
    if seen == 0 and not any(f.subject == "git" for f in setup):
        what = f"changed since {ctx.changed_since}" if ctx.wide else f"found at {location!r}"
        setup.append(Finding(location, None, FAMILY_RECORD_READABLE, DISPOSITION_FAILED,
                             f"no requirement records {what}", subject="empty"))
    first, _ = _evaluate(ctx, records, families)
    fixed, failures, touched = _apply_repairs(ctx, first)
    ctx.forget_loaded()
    records, reload_failures = _reload(ctx, records, touched)
    second, handed = _evaluate(ctx, records, families)
    second = [_unrepaired(f) for f in second]
    second_keys = {f.key for f in second}
    kept_fixed = [f for f in fixed if f.key not in second_keys]
    everything = dedupe([*setup, *load_findings, *reload_failures, *failures, *kept_fixed, *second])
    ordered = sort_findings(everything)
    to_commit = _records_to_commit(ctx) if ctx.wide else None
    return build_report(location, seen, ordered, family_counts(handed, ordered), to_commit)


def main(argv: list[str] | None = None) -> int:
    """CLI entry: print the JSON report on stdout; exit 0 passed, 1 failed, 2 usage error."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else 2
    if not (args.location or args.for_ids or args.changed_since):
        parser.print_usage(sys.stderr)
        print("requirement_rule_check: one of --location, --for-ids or --changed-since is required", file=sys.stderr)
        return 2
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("[requirement_rule_check] %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    try:
        ctx, raw, setup = _resolve_folder(args)
        location = report_location(raw, ctx.folder, ctx.repo_root)
        setup = [*setup, *_rule_source_findings(ctx, args), *_before_state(ctx, args, location)]
        report = run_check(ctx, location, setup)
        for finding in report["findings"]:
            if finding["disposition"] in ("failed", "needs a decision"):
                logger.warning("%s: %s", finding["file"], finding["message"])
    finally:
        logger.removeHandler(handler)
    print(dump_report(report))
    return 0 if report["verdict"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
