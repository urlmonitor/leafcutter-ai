#!/usr/bin/env python3
"""audit_ac_area.py — Evidence-based implementation audit for an AC area.

Given an AC *area* (a component name, an id prefix, or a store subpath), this
script enumerates that area's acceptance criteria and cross-references each one
against the actual repository:

* which test files under the test dirs cite the AC id,
* which source files under the source dirs cite the AC id.

It then emits a per-AC evidence table plus a first-pass verdict per leaf AC.

**Evidence is repo citations only.** The AC store's own ``work_status`` /
``implemented_by`` / ``covered_by`` fields are reported *for comparison* but
NEVER drive the verdict — a verdict is derived solely from which files in the
repo actually cite the AC id. Store claims that the repo does not corroborate
are surfaced as flags (``phantom-suspect``, ``unverified-coverage-claim``,
``stale-bookkeeping``, ``needs-test``). This is deliberate: the tool exists to
catch phantom-done, so it must not let a store field launder itself into a
"done" verdict.

This is the *mechanical* first stage of the ``ac-audit`` skill. It does NOT run
tests and does NOT make semantic judgements. The skill layer (``SKILL.md``)
runs the cited test suites for green-test ground truth and fans out verification
agents for the deep phantom-done checks (orphaned / dead / opposite-behaviour /
xfail-masked). Treat every verdict here as a hypothesis to verify.

Usage:
    python3 .claude/skills/ac-audit/scripts/audit_ac_area.py --prefix BO
    python3 .claude/skills/ac-audit/scripts/audit_ac_area.py --component ac-store --format json
    python3 .claude/skills/ac-audit/scripts/audit_ac_area.py --path build-orchestration --out /tmp/report.md

Selectors (at least one required):
    --component NAME   Match ACs whose ``component`` field equals NAME.
    --prefix PREFIX    Match ACs whose ``id`` starts with PREFIX (e.g. BO, ACS-100).
    --path SUBPATH     Match ACs whose file lives under <ac-root>/SUBPATH.

Options:
    --ac-root DIR      AC store root (default: discovered docs/acceptance-criteria).
    --tests-dir DIR    Test dir to scan for citations (repeatable; default: unit_tests, tests).
    --source-dir DIR   Source dir to scan for citations (repeatable; default: scripts, templates, config).
    --format FMT       markdown (default) or json.
    --out FILE         Write output to FILE instead of stdout.

Exit codes:
    0  Report produced.
    1  No AC matched the selector, or the AC root could not be located.
    2  Bad arguments (no selector given).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

AcRecord = dict[str, Any]

#: Broad AC-id token pattern. Captures the whole maximal token (so "BO-100"
#: is never captured out of "BO-1000"); results are intersected with the
#: in-scope id set, so occasional over-matches are harmless.
_AC_ID_RE = re.compile(r"[A-Z]{2,6}(?:-[A-Z]{2,6})?-\d+(?:[a-z]\d*)?(?:-[0-9a-z]+)*")

#: File extensions scanned for AC-id citations. ``.md`` is included because in
#: this repo agent/skill/command prompts (implementation artefacts) are Markdown.
_TEXT_EXTS = {".py", ".md", ".js", ".mjs", ".ts", ".json", ".yaml", ".yml", ".sh"}

#: Directory names never descended into when scanning for citations.
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".next", ".pytest_cache", "dist", "build"}

_LEAF_LEVELS = {"L2", "L3"}


def _read_text(path: Path) -> str | None:
    """Read *path* as UTF-8, tolerating decode and I/O errors.

    Args:
        path: File to read.

    Returns:
        The file text, or None when it cannot be read (logged at WARNING).
    """
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError as exc:
        logger.warning("Cannot read %s: %s", path, exc)
        return None


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
      1. an explicit ``--ac-root`` — its enclosing repo root is found by walking
         up until a directory containing ``docs/`` is seen (falling back to the
         grandparent when none matches);
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
        for candidate in [ac_root, *ac_root.parents]:
            if (candidate / "docs").is_dir():
                return candidate, ac_root
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


def load_ac_records(
    ac_root: Path,
    component: str | None,
    prefix: str | None,
    subpath: str | None,
) -> list[AcRecord]:
    """Load AC records matching the selector.

    Args:
        ac_root: AC store root directory.
        component: When set, keep ACs whose ``component`` field equals this.
        prefix: When set, keep ACs whose ``id`` starts with this.
        subpath: When set, keep ACs whose file lives under ``ac_root / subpath``.

    Returns:
        A list of AC records; each carries the extra key ``_group`` (the parent
        directory name, used as the epic grouping).
    """
    base = (ac_root / subpath) if subpath else ac_root
    paths = sorted({*base.rglob("*.yaml"), *base.rglob("*.yml")})
    records: list[AcRecord] = []
    for yaml_path in paths:
        text = _read_text(yaml_path)
        if text is None:
            continue
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as exc:
            logger.warning("Skipping unparseable AC %s: %s", yaml_path, exc)
            continue
        if not isinstance(data, dict) or "id" not in data:
            continue
        if component is not None and data.get("component") != component:
            continue
        if prefix is not None and not str(data.get("id", "")).startswith(prefix):
            continue
        data["_group"] = yaml_path.parent.name
        records.append(data)
    return records


def build_reference_map(
    dirs: list[Path],
    in_scope: set[str],
    repo_root: Path,
) -> dict[str, set[str]]:
    """Map each in-scope AC id to the set of files under *dirs* that cite it.

    Scans every text file under *dirs* (pruning ``_SKIP_DIRS`` so vendored trees
    are never entered), extracts AC-id tokens, and records a citation whenever a
    token is in *in_scope*.

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
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for name in filenames:
                if Path(name).suffix not in _TEXT_EXTS:
                    continue
                path = Path(dirpath) / name
                text = _read_text(path)
                if text is None:
                    continue
                tokens = {m.group(0) for m in _AC_ID_RE.finditer(text)}
                hit = tokens & in_scope
                if hit:
                    rel = _relative(path, repo_root)
                    for ac_id in hit:
                        out[ac_id].add(rel)
    return out


def read_ticket_statuses(repo_root: Path, implemented_by: list[Any]) -> tuple[bool, list[str]]:
    """Read the store's ticket claims for an AC (for display / flags only).

    Args:
        repo_root: Repository root, used to resolve relative ticket paths.
        implemented_by: The AC's ``implemented_by`` list (ticket path strings).

    Returns:
        ``(any_done, claimed_files)`` — whether any referenced ticket has
        ``status: done``, and the (existence-checked, non-ticket/non-AC-store)
        source files those tickets claim to have touched. These are STORE CLAIMS,
        surfaced for transparency; they never drive the verdict.
    """
    any_done = False
    claimed: list[str] = []
    for ref in implemented_by or []:
        ref_s = str(ref)
        if ".md" not in ref_s:
            continue
        candidate = Path(ref_s) if Path(ref_s).is_absolute() else repo_root / ref_s
        if not candidate.exists():
            continue
        text = _read_text(candidate)
        if text is None:
            continue
        match = re.match(r"^---\n(.*?)\n---", text, re.S)
        if not match:
            continue
        try:
            fm = yaml.safe_load(match.group(1))
        except yaml.YAMLError as exc:
            logger.warning("Cannot parse ticket frontmatter %s: %s", candidate, exc)
            continue
        if not isinstance(fm, dict):
            continue
        if fm.get("status") == "done":
            any_done = True
        for f in fm.get("files_touched") or []:
            fs = str(f)
            if fs.startswith("tickets/") or fs.startswith("docs/acceptance"):
                continue
            if (repo_root / fs).exists():
                claimed.append(fs)
    return any_done, claimed


def _looks_like_test(path: str) -> bool:
    """Return True when *path* is a test file (not merely a path containing 'test').

    Matches a ``test``/``tests`` path segment, or a ``test_*.py`` / ``*_test.py``
    filename — so production modules such as ``test_enforcement.py`` living under a
    source dir, or ``check_ticket_test_requirements.py``, are NOT treated as tests.

    Args:
        path: A file path string.

    Returns:
        True when the path denotes a test file.
    """
    p = path.split("::", 1)[0]
    parts = p.replace("\\", "/").split("/")
    if any(seg in ("test", "tests") for seg in parts[:-1]):
        return True
    name = parts[-1]
    return name.startswith("test_") and name.endswith(".py") or name.endswith("_test.py")


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
    """Compute the evidence verdict for one leaf AC from REPO CITATIONS ONLY.

    Store fields (``work_status``, ``implemented_by``, ``covered_by``) are read
    only to compute comparison flags — they never contribute to ``has_code`` /
    ``has_test`` or the verdict.

    Args:
        record: The AC record.
        test_refs: Test files (from the grep map) that cite this AC.
        source_refs: Source files (from the grep map) that cite this AC.
        repo_root: Repo root, for resolving ``implemented_by`` tickets.

    Returns:
        A dict with the verdict, the concrete cited code/test evidence, the
        store's own (untrusted) claims, and any bookkeeping flags.
    """
    ac_id = record.get("id", "?")

    # Evidence — grep citations only. A cited source file that is itself a test
    # counts as a test, never as code.
    tests = sorted(set(test_refs) | {s for s in source_refs if _looks_like_test(s)})
    code = sorted(s for s in source_refs if not _looks_like_test(s))
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

    # --- Store claims (untrusted; for comparison only) ---
    store_status = record.get("work_status")
    ticket_done, claimed_code = read_ticket_statuses(repo_root, record.get("implemented_by") or [])
    cb_tests, _cb_children = _split_covered_by(record.get("covered_by") or [])
    store_claims_done = store_status == "done" or ticket_done

    flags: list[str] = []
    if store_claims_done and not has_test:
        flags.append("phantom-suspect")  # store says done, no repo-cited test
    if cb_tests and not any(t.split("::")[0] in {r.split("::")[0] for r in tests} for t in cb_tests):
        flags.append("unverified-coverage-claim")  # covered_by test not corroborated by a citation
    if has_code and has_test and store_status != "done":
        flags.append("stale-bookkeeping")  # evidence exists, store not marked done
    if (has_code or store_claims_done) and not has_test:
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
        "store_claimed_code": sorted(set(claimed_code)),
        "store_ticket_done": ticket_done,
        "flags": flags,
    }


def _natkey(text: str) -> list[Any]:
    """Return a natural-sort key so ``BO-9`` sorts before ``BO-10``.

    Args:
        text: The string to key.

    Returns:
        A list of alternating string / int fragments.
    """
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", text)]


def _cell(items: list[str]) -> str:
    """Render a list of paths as one escaped Markdown table cell.

    Args:
        items: Path strings.

    Returns:
        A ``<br>``-joined, pipe-escaped cell, or an em-dash when empty.
    """
    return "<br>".join(x.replace("|", r"\|") for x in items) or "—"


def _verdict_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Tally verdicts across *rows*.

    Args:
        rows: Classified leaf rows.

    Returns:
        Mapping verdict -> count (all four verdicts present, zero-filled).
    """
    counts = {"FULLY_IMPLEMENTED": 0, "CODE_NO_TEST": 0, "TEST_NO_CODE": 0, "NOT_IMPLEMENTED": 0}
    for r in rows:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    return counts


def _cited_test_files(rows: list[dict[str, Any]]) -> list[str]:
    """Return the sorted set of test files cited across *rows* (node ids stripped).

    Args:
        rows: Classified leaf rows.

    Returns:
        Sorted unique test file paths.
    """
    return sorted({t.split("::")[0] for r in rows for t in r["tests"]})


def render_markdown(rows: list[dict[str, Any]], area: str) -> str:
    """Render the audit as a Markdown report.

    Args:
        rows: Classified leaf rows.
        area: Human label for the audited area.

    Returns:
        A Markdown string.
    """
    counts = _verdict_counts(rows)
    lines: list[str] = [
        f"# AC evidence audit — {area}",
        "",
        "> First-pass, grep-based, evidence = repo citations only (store fields are "
        "shown for comparison, never trusted). Run the cited test suites for "
        "green-test truth and verify flagged rows with a skeptical agent before "
        "trusting any verdict.",
        "",
        "## Summary (leaf ACs)",
        "",
        f"- FULLY_IMPLEMENTED (cited code + cited test): {counts['FULLY_IMPLEMENTED']}",
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
        gc = _verdict_counts(groups[group])
        lines.append(
            f"- **{group}** ({len(groups[group])}): "
            f"full={gc['FULLY_IMPLEMENTED']}, code-only={gc['CODE_NO_TEST']}, "
            f"test-only={gc['TEST_NO_CODE']}, none={gc['NOT_IMPLEMENTED']}"
        )
    lines += [
        "", "## Per-AC evidence", "",
        "| AC | Verdict | Store | Cited code | Cited tests | Store-claimed code | Flags |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in sorted(rows, key=lambda x: _natkey(str(x["id"]))):
        lines.append(
            f"| {r['id']} | {r['verdict']} | {r['store_work_status']} | {_cell(r['code'])} | "
            f"{_cell(r['tests'])} | {_cell(r['store_claimed_code'])} | {', '.join(r['flags'])} |"
        )

    by_flag: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        for f in r["flags"]:
            by_flag[f].append(str(r["id"]))
    lines += ["", "## Flags", ""]
    for flag in ("phantom-suspect", "unverified-coverage-claim", "stale-bookkeeping", "needs-test"):
        ids = by_flag.get(flag, [])
        lines.append(f"- **{flag}** ({len(ids)}): " + (", ".join(sorted(ids, key=_natkey)) or "none"))

    lines += ["", "## Cited test files (run these for green-test truth)", ""]
    lines += [f"- {tf}" for tf in _cited_test_files(rows)] or ["- (none)"]
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

    records = load_ac_records(ac_root, args.component, args.prefix, args.subpath)
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
        by_flag: dict[str, list[str]] = defaultdict(list)
        for r in rows:
            for f in r["flags"]:
                by_flag[f].append(str(r["id"]))
        payload = {
            "area": area,
            "total_records": len(records),
            "leaf_count": len(rows),
            "summary": _verdict_counts(rows),
            "flags": dict(by_flag),
            "cited_test_files": _cited_test_files(rows),
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
#   first-pass verdict + flags) into a reusable, area-parameterised evidence
#   engine. Intersects maximal AC-id tokens with the in-scope id set to avoid
#   prefix collisions (BO-100 vs BO-1000).
# - 2026-07-14 [ac-audit skill, post-review]: Hardened after a code review + an
#   independent logic check. Evidence is now REPO CITATIONS ONLY — store fields
#   (implemented_by/files_touched, covered_by, work_status) no longer contribute
#   to has_code/has_test/verdict; they are surfaced as store-claim columns and
#   as flags (phantom-suspect, unverified-coverage-claim) so the tool can no
#   longer launder a store claim into a "done" verdict (the exact phantom-done
#   failure it exists to catch). Also: precise _looks_like_test (path segment /
#   test_*.py / *_test.py filename, not bare substring) so production modules
#   like check_ticket_test_requirements.py / test_enforcement.py are not dropped;
#   UnicodeDecodeError-safe reads (errors="ignore") at all read sites; os.walk
#   with dir pruning instead of rglob; --ac-root repo-root validation; *.yml as
#   well as *.yaml; anchored frontmatter regex; natural-sort + pipe-escaped
#   Markdown cells; enriched JSON payload (summary/flags/cited_test_files).
# ====================================================================
