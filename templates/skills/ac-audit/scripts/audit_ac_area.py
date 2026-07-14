#!/usr/bin/env python3
"""audit_ac_area.py — Evidence-based implementation audit for an AC area.

Given an AC *area* (a component name, an id prefix, or a store subpath), this
script enumerates that area's acceptance criteria and cross-references each one
against the actual repository:

* which test files under the test dirs cite the AC id,
* which source files under the source dirs cite the AC id,
* the ``status`` and ``files_touched`` of any ticket listed in ``implemented_by``.

It then emits a per-AC evidence table plus a first-pass verdict per leaf AC.

The AC store's own ``work_status`` / ``implemented_by`` / ``covered_by`` fields
are reported but **never trusted as ground truth** — they are compared against
the evidence and mismatches are flagged (``stale-bookkeeping`` when the store
says todo but tests cite it; ``phantom-suspect`` when the store/ticket claims
done or code exists but no test cites it).

This is the *mechanical* first stage of the ``ac-audit`` skill. It deliberately
does NOT run tests and does NOT make semantic judgements. The skill layer
(``SKILL.md``) runs the cited test suites for green-test ground truth and fans
out verification agents for the deep phantom-done checks (orphaned / dead /
opposite-behaviour code). Treat every verdict here as a hypothesis to verify.

Usage:
    python3 .claude/skills/ac-audit/scripts/audit_ac_area.py --prefix BO
    python3 .claude/skills/ac-audit/scripts/audit_ac_area.py --component ac-store --format json
    python3 .claude/skills/ac-audit/scripts/audit_ac_area.py --path build-orchestration --out /tmp/report.md

Selectors (at least one required):
    --component NAME   Match ACs whose ``component`` field equals NAME.
    --prefix PREFIX    Match ACs whose ``id`` starts with PREFIX (e.g. BO, ACS-100).
    --path SUBPATH     Match ACs whose file lives under <ac-root>/SUBPATH.

Options:
    --ac-root DIR      AC store root (default: <repo>/docs/acceptance-criteria).
    --tests-dir DIR    Test dir to scan for citations (repeatable; default: unit_tests, tests).
    --source-dir DIR   Source dir to scan for citations (repeatable; default: scripts, templates, config).
    --format FMT       markdown (default) or json.
    --out FILE         Write output to FILE instead of stdout.

Exit codes:
    0  Report produced.
    1  No AC matched the selector, or the AC root does not exist.
    2  Bad arguments (no selector given).
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

AcRecord = dict[str, Any]

#: Broad AC-id token pattern. Captures the whole maximal token (so "BO-100"
#: is never captured out of "BO-1000"); results are intersected with the
#: in-scope id set, so occasional over-matches are harmless.
_AC_ID_RE = re.compile(r"[A-Z]{2,6}(?:-[A-Z]{2,6})?-\d+(?:[a-z]\d*)?(?:-[0-9a-z]+)*")

#: File extensions scanned for AC-id citations.
_TEXT_EXTS = {".py", ".md", ".js", ".mjs", ".ts", ".json", ".yaml", ".yml", ".sh"}

#: Directories never scanned for citations.
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".next", ".pytest_cache", "dist", "build"}

_LEAF_LEVELS = {"L2", "L3"}


def _has_store(base: Path) -> bool:
    """Return True when *base* contains a ``docs/acceptance-criteria`` directory.

    Args:
        base: Candidate directory.

    Returns:
        True when the AC store lives directly under *base*.
    """
    return (base / "docs" / "acceptance-criteria").is_dir()


def discover_store(cli_ac_root: str | None) -> tuple[Path, Path]:
    """Locate the repo root and AC store, robust to where the script is deployed.

    Resolution order:
      1. an explicit ``--ac-root`` (repo root is inferred as its grandparent);
      2. the first ancestor of the cwd, then of this file, that contains
         ``docs/acceptance-criteria`` — checking both the ancestor itself and its
         ``leafcutter-ai/`` subdir (the package sits in a subdir of the workspace).

    Args:
        cli_ac_root: The ``--ac-root`` value, or None.

    Returns:
        ``(repo_root, ac_root)`` where ``repo_root`` is the directory containing
        ``docs/`` and ``ac_root`` is the AC store directory.

    Raises:
        FileNotFoundError: When no AC store can be located.
    """
    if cli_ac_root:
        ac_root = Path(cli_ac_root).resolve()
        return ac_root.parent.parent, ac_root
    starts = [Path.cwd().resolve(), Path(__file__).resolve()]
    for start in starts:
        for base in [start, *start.parents]:
            for candidate in (base, base / "leafcutter-ai"):
                if _has_store(candidate):
                    return candidate, candidate / "docs" / "acceptance-criteria"
    raise FileNotFoundError(  # noqa: TRY003
        "Could not locate docs/acceptance-criteria; pass --ac-root explicitly"
    )


def load_ac_records(
    ac_root: Path,
    repo_root: Path,
    component: str | None,
    prefix: str | None,
    subpath: str | None,
) -> list[AcRecord]:
    """Load AC records matching the selector.

    Args:
        ac_root: AC store root directory.
        repo_root: Repository root (for producing relative paths).
        component: When set, keep ACs whose ``component`` field equals this.
        prefix: When set, keep ACs whose ``id`` starts with this.
        subpath: When set, keep ACs whose file lives under ``ac_root / subpath``.

    Returns:
        A list of AC records; each carries the extra keys ``_path`` (repo-relative
        file path) and ``_group`` (the parent directory name, used as the epic
        grouping).
    """
    base = (ac_root / subpath) if subpath else ac_root
    records: list[AcRecord] = []
    for yaml_path in sorted(base.rglob("*.yaml")):
        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        except (yaml.YAMLError, OSError) as exc:
            logger.warning("Skipping unreadable AC %s: %s", yaml_path, exc)
            continue
        if not isinstance(data, dict) or "id" not in data:
            continue
        if component is not None and data.get("component") != component:
            continue
        if prefix is not None and not str(data.get("id", "")).startswith(prefix):
            continue
        rel = _relative(yaml_path, repo_root)
        data["_path"] = rel
        data["_group"] = yaml_path.parent.name
        records.append(data)
    return records


def _relative(path: Path, repo_root: Path) -> str:
    """Return *path* relative to *repo_root* when possible, else its string form.

    Args:
        path: The path to relativise.
        repo_root: The repository root.

    Returns:
        A repo-relative path string, or the absolute string when outside the repo.
    """
    try:
        return str(path.resolve().relative_to(repo_root))
    except ValueError:
        return str(path)


def build_reference_map(
    dirs: list[Path],
    in_scope: set[str],
    repo_root: Path,
) -> dict[str, set[str]]:
    """Map each in-scope AC id to the set of files under *dirs* that cite it.

    Scans every text file under *dirs*, extracts AC-id tokens, and records a
    citation whenever a token is in *in_scope*.

    Args:
        dirs: Directories to scan.
        in_scope: The set of AC ids we care about.
        repo_root: Repo root, for producing relative paths in the result.

    Returns:
        Mapping of AC id -> set of repo-relative file paths that cite it.
    """
    out: dict[str, set[str]] = {ac_id: set() for ac_id in in_scope}
    for root in dirs:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in _TEXT_EXTS:
                continue
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError as exc:
                logger.warning("Skipping unreadable file %s: %s", path, exc)
                continue
            tokens = {m.group(0) for m in _AC_ID_RE.finditer(text)}
            hit = tokens & in_scope
            if hit:
                rel = _relative(path, repo_root)
                for ac_id in hit:
                    out[ac_id].add(rel)
    return out


def read_ticket_meta(repo_root: Path, ticket_ref: str) -> tuple[str | None, list[str]]:
    """Read ``status`` and ``files_touched`` from a ticket referenced by an AC.

    Args:
        repo_root: Repository root, used to resolve a relative ticket path.
        ticket_ref: A path string from an AC's ``implemented_by`` list.

    Returns:
        ``(status, files_touched)``. ``status`` is None when the ticket cannot
        be read or is not a ticket path; ``files_touched`` is the parsed list
        (possibly empty).
    """
    if not ticket_ref or ".md" not in ticket_ref:
        return None, []
    candidate = Path(ticket_ref)
    if not candidate.is_absolute():
        candidate = repo_root / ticket_ref
    if not candidate.exists():
        return None, []
    try:
        text = candidate.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot read ticket %s: %s", candidate, exc)
        return None, []
    if not text.startswith("---"):
        return None, []
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None, []
    try:
        fm = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        logger.warning("Cannot parse ticket frontmatter %s: %s", candidate, exc)
        return None, []
    if not isinstance(fm, dict):
        return None, []
    ft = fm.get("files_touched") or []
    files = [str(f) for f in ft] if isinstance(ft, list) else []
    return fm.get("status"), files


def _looks_like_test(path: str) -> bool:
    """Return True when *path* looks like a test file.

    Args:
        path: A file path string.

    Returns:
        True when the path contains a ``test`` segment and is a Python file.
    """
    low = path.lower()
    return "test" in low and low.endswith(".py")


def _split_covered_by(covered_by: list[Any]) -> tuple[list[str], list[str]]:
    """Split an AC ``covered_by`` list into test references and child AC ids.

    Args:
        covered_by: The raw ``covered_by`` list from an AC record.

    Returns:
        ``(test_refs, child_ids)`` — entries that look like test paths vs the rest.
    """
    tests: list[str] = []
    children: list[str] = []
    for entry in covered_by or []:
        s = str(entry)
        if ".py" in s or "::" in s or _looks_like_test(s):
            tests.append(s)
        else:
            children.append(s)
    return tests, children


def classify(
    record: AcRecord,
    test_refs: set[str],
    source_refs: set[str],
    repo_root: Path,
) -> dict[str, Any]:
    """Compute the first-pass evidence verdict for one leaf AC.

    Args:
        record: The AC record.
        test_refs: Test files (from the grep map) that cite this AC.
        source_refs: Source files (from the grep map) that cite this AC.
        repo_root: Repo root, for resolving ``implemented_by`` tickets.

    Returns:
        A dict with the verdict, the concrete code/test evidence, the store's own
        claim, and any bookkeeping flags.
    """
    ac_id = record.get("id", "?")
    cb_tests, _cb_children = _split_covered_by(record.get("covered_by") or [])

    ticket_status: str | None = None
    ticket_code: list[str] = []
    for ref in record.get("implemented_by") or []:
        status, files = read_ticket_meta(repo_root, str(ref))
        if status is not None:
            ticket_status = status
            ticket_code += [f for f in files if not f.startswith("tickets/") and not f.startswith("docs/acceptance")]

    # Evidence — union of the grep map, the AC's own covered_by test links, and
    # any real (existing, non-ticket) source files a done ticket touched.
    tests = sorted(set(test_refs) | set(cb_tests))
    code = sorted(set(source_refs) | {f for f in ticket_code if (repo_root / f).exists()})
    # Source refs that are themselves test files should count as tests, not code.
    code = [c for c in code if not _looks_like_test(c)]

    has_test = bool(tests)
    has_code = bool(code)
    if has_code and has_test:
        verdict = "FULLY_IMPLEMENTED"
    elif has_code:
        verdict = "CODE_NO_TEST"
    elif has_test:
        verdict = "TEST_NO_CODE"
    else:
        verdict = "NOT_IMPLEMENTED"

    store_status = record.get("work_status")
    flags: list[str] = []
    if store_status != "done" and has_test and has_code:
        flags.append("stale-bookkeeping")  # looks done, store says otherwise
    if store_status == "done" and not has_test:
        flags.append("phantom-suspect")  # store says done, no test cites it
    if (ticket_status == "done" or has_code) and not has_test:
        flags.append("needs-test")

    return {
        "id": ac_id,
        "level": record.get("level"),
        "group": record.get("_group"),
        "title": record.get("title"),
        "store_work_status": store_status,
        "readiness": record.get("readiness"),
        "verdict": verdict,
        "code": code,
        "tests": tests,
        "ticket_status": ticket_status,
        "flags": flags,
    }


def render_markdown(rows: list[dict[str, Any]], area: str) -> str:
    """Render the audit as a Markdown report.

    Args:
        rows: Classified leaf rows.
        area: Human label for the audited area.

    Returns:
        A Markdown string.
    """
    from collections import defaultdict

    counts: dict[str, int] = defaultdict(int)
    for r in rows:
        counts[r["verdict"]] += 1
    lines: list[str] = [
        f"# AC evidence audit — {area}",
        "",
        "> First-pass, grep-based. Store fields are shown but NOT trusted. "
        "Run the cited test suites for green-test truth and verify phantom-suspect "
        "rows with a skeptical agent before trusting any verdict.",
        "",
        "## Summary (leaf ACs)",
        "",
        f"- FULLY_IMPLEMENTED (code + cited test): {counts['FULLY_IMPLEMENTED']}",
        f"- CODE_NO_TEST: {counts['CODE_NO_TEST']}",
        f"- TEST_NO_CODE: {counts['TEST_NO_CODE']}",
        f"- NOT_IMPLEMENTED: {counts['NOT_IMPLEMENTED']}",
        f"- total leaves: {len(rows)}",
        "",
    ]

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        groups[r["group"] or "(ungrouped)"].append(r)
    lines += ["## Per-group rollup", ""]
    for group in sorted(groups):
        gc: dict[str, int] = defaultdict(int)
        for r in groups[group]:
            gc[r["verdict"]] += 1
        lines.append(
            f"- **{group}** ({len(groups[group])}): "
            f"full={gc['FULLY_IMPLEMENTED']}, code-only={gc['CODE_NO_TEST']}, "
            f"test-only={gc['TEST_NO_CODE']}, none={gc['NOT_IMPLEMENTED']}"
        )
    lines += ["", "## Per-AC evidence", "", "| AC | Verdict | Store | Code | Tests | Flags |", "|---|---|---|---|---|---|"]
    for r in sorted(rows, key=lambda x: str(x["id"])):
        code = "<br>".join(r["code"]) or "—"
        tests = "<br>".join(r["tests"]) or "—"
        flags = ", ".join(r["flags"]) or ""
        lines.append(
            f"| {r['id']} | {r['verdict']} | {r['store_work_status']} | {code} | {tests} | {flags} |"
        )

    suspects = [r for r in rows if "phantom-suspect" in r["flags"]]
    stale = [r for r in rows if "stale-bookkeeping" in r["flags"]]
    lines += ["", "## Flags", ""]
    lines.append(f"- **phantom-suspect** (store=done but no cited test): {len(suspects)} — "
                 + (", ".join(str(r["id"]) for r in suspects) or "none"))
    lines.append(f"- **stale-bookkeeping** (evidence but store!=done): {len(stale)} — "
                 + (", ".join(str(r["id"]) for r in stale) or "none"))

    test_files = sorted({t.split("::")[0] for r in rows for t in r["tests"]})
    lines += ["", "## Cited test files (run these for green-test truth)", ""]
    lines += [f"- {tf}" for tf in test_files] or ["- (none)"]
    return "\n".join(lines)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Build the parser and parse *argv*.

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]``).

    Returns:
        Parsed arguments.
    """
    p = argparse.ArgumentParser(description="Evidence-based implementation audit for an AC area.")
    p.add_argument("--component")
    p.add_argument("--prefix")
    p.add_argument("--path", dest="subpath")
    p.add_argument("--ac-root")
    p.add_argument("--tests-dir", action="append", default=[])
    p.add_argument("--source-dir", action="append", default=[])
    p.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p.add_argument("--out")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Entry point.

    Args:
        argv: CLI arguments (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code.
    """
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    args = _parse_args(argv)
    if not (args.component or args.prefix or args.subpath):
        print("ERROR: give at least one selector: --component / --prefix / --path", file=sys.stderr)
        return 2

    try:
        repo_root, ac_root = discover_store(args.ac_root)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not ac_root.exists():
        print(f"ERROR: AC root not found: {ac_root}", file=sys.stderr)
        return 1

    records = load_ac_records(ac_root, repo_root, args.component, args.prefix, args.subpath)
    if not records:
        print("ERROR: no AC matched the selector.", file=sys.stderr)
        return 1

    tests_dirs = [Path(d) for d in args.tests_dir] or [repo_root / "unit_tests", repo_root / "tests"]
    source_dirs = [Path(d) for d in args.source_dir] or [
        repo_root / "scripts", repo_root / "templates", repo_root / "config",
    ]

    in_scope = {str(r["id"]) for r in records}
    test_map = build_reference_map(tests_dirs, in_scope, repo_root)
    source_map = build_reference_map(source_dirs, in_scope, repo_root)

    leaves = [r for r in records if r.get("level") in _LEAF_LEVELS]
    rows = [
        classify(r, test_map.get(str(r["id"]), set()), source_map.get(str(r["id"]), set()), repo_root)
        for r in leaves
    ]

    area = args.component or args.prefix or args.subpath or "?"
    if args.format == "json":
        payload = {
            "area": area,
            "total_records": len(records),
            "leaf_count": len(rows),
            "rows": rows,
        }
        output = json.dumps(payload, indent=1)
    else:
        output = render_markdown(rows, area)

    if args.out:
        try:
            Path(args.out).write_text(output, encoding="utf-8")
        except OSError as exc:
            print(f"ERROR: cannot write {args.out}: {exc}", file=sys.stderr)
            return 1
        print(f"Written: {args.out}")
    else:
        print(output)
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-07-14 [ac-audit skill]: Initial implementation. Generalises the
#   one-off BO-* audit (enumerate area ACs -> grep test/source citation maps ->
#   resolve implemented_by tickets -> first-pass verdict + phantom-suspect /
#   stale-bookkeeping flags) into a reusable, area-parameterised evidence
#   engine. Store fields are reported but never trusted; green-test truth and
#   deep phantom-done verification are layered by the skill (SKILL.md), not this
#   script. Scans .py/.md/.js/.json/.yaml under test and source dirs; intersects
#   maximal AC-id tokens with the in-scope id set to avoid prefix collisions
#   (BO-100 vs BO-1000).
# ====================================================================
