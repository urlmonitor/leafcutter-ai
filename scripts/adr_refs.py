"""
MODULE: adr_refs
GOAL: Inventory every ADR file and every ADR reference in the repository, so
    numbering defects (duplicate integers, sequence gaps, references to ADR
    numbers that own no file) are visible in one command instead of being
    discovered one broken link at a time.
BUSINESS CONTEXT: ADR integers are chronologically meaningful and cross-referenced
    from agent templates, skills, hooks, tickets and docs. When two ADRs claim the
    same integer (the 2026-05-15 ADR-024 incident, and the 004/007/017/025
    collisions found on 2026-08-13) a bare `ADR-NNN` citation stops resolving to a
    single decision. check_adr_collision.py prevents NEW collisions at commit time;
    this module is the read-side counterpart that audits the collisions already in
    the tree and drives the renumbering that repairs them.
ARCHITECTURE: Pure read-only scanner plus an opt-in `--apply` renumbering mode.
    Scanning is a single walk of the repo matching a family of ADR citation forms
    (path, slug-qualified, bare, spaced, snake_case, letter-suffixed). Renumbering
    is deliberately two-tier: slug-qualified citations carry their own identity and
    are rewritten mechanically, while BARE `ADR-NNN` citations are ambiguous the
    moment a number is split across two files and are therefore reported for human
    triage, never rewritten silently. Standalone script — no imports from the
    leafcutter package, so it runs in a bare worktree.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ADR_DIR = Path("docs/architecture/adrs")

SKIP_DIRS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "dist", "build", ".next", "htmlcov",
}
SKIP_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".pdf", ".zip", ".gz",
    ".woff", ".woff2", ".ttf", ".eot", ".pyc", ".so", ".lock",
}

# An ADR filename: ADR-NNN-some-slug.md
FILENAME_RE = re.compile(r"^ADR-(\d{3})-(.+)\.md$")

# Highest integer treated as an ADR. The ADR sequence is zero-padded to three
# digits and is currently in the thirties; every acceptance-criterion id in this
# repo is >= 100 (ACD-1600, BO-2200, ACS-500, GE-104...). So a three-digit
# citation of 100 or more is an AC id that merely starts with "ADR" -- e.g.
# "ADR-400b" in docs/acceptance-criteria/ac-driven-dev/ -- not an ADR reference.
MAX_ADR_NUMBER = 99

# Citations that name an ADR with no file, and should stay that way.
#
# These are dated historical records -- a closed ticket stating what it intended
# to write, or a sign-off describing the corpus as it stood that day. Repointing
# them at a live ADR would make the record claim something that did not happen,
# so they are excluded from the broken-slug report instead of "fixed".
IGNORED_SLUGS = {
    # TICKET-20260530 declared this ADR as a deliverable and closed without it.
    "manifest-driven-build-orchestration",
    # A checklist placeholder; the same ticket records the real outcome as
    # ADR-013-portable-skill-script-deployment-boundary.
    "portable-skill-boundary",
}

# A citation. Three digits exactly (a 4th digit means it is an AC id such as
# ADR-1600b, not an ADR). An optional letter suffix captures the ADR-007b
# disambiguation workaround. An optional -slug captures the qualified form.
CITATION_RE = re.compile(
    r"""
    \bADR
    (?P<sep>[-_ ]?)
    (?P<num>\d{3})
    (?!\d)
    (?P<suffix>[a-z](?![a-z0-9-]))?
    (?P<slug>-[a-z0-9]+(?:-[a-z0-9]+)*)?
    """,
    re.VERBOSE | re.IGNORECASE,
)


@dataclass
class AdrFile:
    """One ADR markdown file on disk."""

    number: int
    slug: str
    path: Path


@dataclass
class Ref:
    """One ADR citation found in one file at one line."""

    number: int
    path: Path
    line: int
    text: str
    slug: str | None
    suffix: str | None
    orphan_slug: str | None = None
    source: str = ""

    @property
    def qualified(self) -> bool:
        """True when the citation names a slug, so it identifies one ADR."""
        return self.slug is not None


@dataclass
class Scan:
    """The full result of one repository scan."""

    files: list[AdrFile] = field(default_factory=list)
    refs: list[Ref] = field(default_factory=list)

    def by_number(self) -> dict[int, list[AdrFile]]:
        out: dict[int, list[AdrFile]] = defaultdict(list)
        for f in self.files:
            out[f.number].append(f)
        return dict(sorted(out.items()))

    def duplicates(self) -> dict[int, list[AdrFile]]:
        return {n: fs for n, fs in self.by_number().items() if len(fs) > 1}

    def gaps(self) -> list[int]:
        nums = {f.number for f in self.files}
        if not nums:
            return []
        return [n for n in range(min(nums), max(nums) + 1) if n not in nums]

    def dangling(self) -> dict[int, list[Ref]]:
        """Referenced numbers that own no ADR file."""
        owned = {f.number for f in self.files}
        out: dict[int, list[Ref]] = defaultdict(list)
        for r in self.refs:
            if r.number not in owned:
                out[r.number].append(r)
        return dict(sorted(out.items()))

    def refs_for(self, number: int) -> list[Ref]:
        return [r for r in self.refs if r.number == number]

    def orphan_slugs(self) -> dict[str, list[Ref]]:
        """Slug-qualified citations naming a slug that owns no ADR file.

        These are broken links: the citation looks authoritative because it
        names a decision, but nothing on disk answers to that name.
        """
        out: dict[str, list[Ref]] = defaultdict(list)
        for r in self.refs:
            if r.orphan_slug:
                out[r.orphan_slug].append(r)
        return dict(sorted(out.items()))


def _repo_root(start: Path) -> Path:
    """Resolve the git top level, falling back to the given directory."""
    try:
        out = subprocess.run(
            ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"WARN [adr_refs] git root lookup failed, using {start}: {exc}",
              file=sys.stderr)
        return start
    return Path(out.stdout.strip())


def _walk(root: Path):
    """Yield every scannable file under root."""
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() in SKIP_SUFFIXES:
            continue
        yield p


def scan(root: Path) -> Scan:
    """Walk the repository and collect ADR files and ADR citations."""
    result = Scan()

    adr_dir = root / ADR_DIR
    if adr_dir.is_dir():
        for p in sorted(adr_dir.glob("ADR-*.md")):
            m = FILENAME_RE.match(p.name)
            if m:
                result.files.append(
                    AdrFile(int(m.group(1)), m.group(2), p.relative_to(root))
                )

    known_slugs = {f.slug for f in result.files}

    for p in _walk(root):
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            print(f"WARN [adr_refs] unreadable {p}: {exc}", file=sys.stderr)
            continue
        if "ADR" not in text and "adr" not in text:
            continue
        rel = p.relative_to(root)
        for lineno, line in enumerate(text.splitlines(), start=1):
            for m in CITATION_RE.finditer(line):
                number = int(m.group("num"))
                if number > MAX_ADR_NUMBER:
                    continue
                slug = m.group("slug")
                orphan = None
                if slug is not None:
                    slug = slug.lstrip("-")
                    if slug not in known_slugs:
                        # Not a slug we own. A multi-word lowercase token in
                        # slug position is a broken link to an ADR that does
                        # not exist; anything shorter is prose, so treat the
                        # citation as bare.
                        if slug.count("-") >= 2 and slug not in IGNORED_SLUGS:
                            orphan = slug
                        slug = None
                result.refs.append(
                    Ref(
                        number=number,
                        path=rel,
                        line=lineno,
                        text=m.group(0),
                        slug=slug,
                        suffix=m.group("suffix"),
                        orphan_slug=orphan,
                        source=line,
                    )
                )
    return result


def _print_report(s: Scan) -> None:
    """Print the human-readable audit."""
    print(f"ADR files: {len(s.files)}   citations: {len(s.refs)}\n")

    print("== Inventory ==")
    for num, files in s.by_number().items():
        mark = "  <-- DUPLICATE" if len(files) > 1 else ""
        for i, f in enumerate(files):
            n_refs = len([r for r in s.refs_for(num) if r.slug == f.slug])
            head = f"ADR-{num:03d}" if i == 0 else " " * 7
            print(f"{head}  {f.slug:<45} qualified-refs={n_refs}{mark if i == 0 else ''}")

    dupes = s.duplicates()
    print(f"\n== Duplicates == ({len(dupes)} numbers, "
          f"{sum(len(v) for v in dupes.values())} files)")
    for num, files in dupes.items():
        bare = len([r for r in s.refs_for(num) if not r.qualified])
        print(f"ADR-{num:03d}: {len(files)} files, {bare} ambiguous bare citations")
        for f in files:
            qual = len([r for r in s.refs_for(num) if r.slug == f.slug])
            print(f"    {f.slug:<45} qualified-refs={qual}")

    gaps = s.gaps()
    print(f"\n== Gaps == ({len(gaps)})")
    print("  " + (", ".join(f"ADR-{n:03d}" for n in gaps) if gaps else "none"))

    dang = s.dangling()
    print(f"\n== Dangling references == ({len(dang)} numbers with no ADR file)")
    for num, refs in dang.items():
        where = sorted({str(r.path) for r in refs})
        print(f"ADR-{num:03d}: {len(refs)} citations in {len(where)} files")
        for w in where[:6]:
            print(f"    {w}")
        if len(where) > 6:
            print(f"    ... and {len(where) - 6} more")

    orphans = s.orphan_slugs()
    print(f"\n== Broken slugs == ({len(orphans)} named ADRs with no file)")
    for slug, refs in orphans.items():
        where = sorted({str(r.path) for r in refs})
        print(f"  {refs[0].text.split('-')[0]}-{refs[0].number:03d}-{slug}"
              f"  ({len(refs)} citations, {len(where)} files)")
        for w in where:
            print(f"      {w}")

    used = {f.number for f in s.files} | set(dang)
    free = [n for n in range(1, max(used) + 12) if n not in used]
    print("\n== Unclaimed numbers == (no file AND no citation)")
    print("  " + ", ".join(f"{n:03d}" for n in free[:20]))


def _print_occurrences(s: Scan, number: int) -> None:
    """Print every occurrence of one ADR number, grouped by qualification."""
    refs = s.refs_for(number)
    print(f"ADR-{number:03d}: {len(refs)} citations\n")
    qualified = [r for r in refs if r.qualified]
    bare = [r for r in refs if not r.qualified]

    by_slug: dict[str, list[Ref]] = defaultdict(list)
    for r in qualified:
        by_slug[r.slug or ""].append(r)
    for slug, group in sorted(by_slug.items()):
        print(f"-- qualified: {slug} ({len(group)})")
        for r in group:
            print(f"   {r.path}:{r.line}: {r.text}")

    print(f"\n-- bare / ambiguous ({len(bare)})")
    for r in bare:
        sfx = f" [suffix {r.suffix}]" if r.suffix else ""
        orph = f" [orphan slug: {r.orphan_slug}]" if r.orphan_slug else ""
        print(f"   {r.path}:{r.line}: {r.text}{sfx}{orph}")
        print(f"      | {r.source.strip()[:150]}")


_FM_RE = re.compile(r"""^(title|status|created):\s*(.*?)\s*$""", re.MULTILINE)
_HEADING_RE = re.compile(r"^# ADR-\d{3}[a-z]?:\s*(.+)$", re.MULTILINE)
_PROSE_STATUS_RE = re.compile(
    r"^## Status\s*\n+(\w+)(?:\s*\((\d{4}-\d{2}-\d{2})\))?", re.MULTILINE
)
_TABLE_STATUS_RE = re.compile(r"^\|\s*Status\s*\|\s*([^|]+?)\s*\|", re.MULTILINE)
_TABLE_DATE_RE = re.compile(r"^\|\s*(?:Date|Decided)\s*\|\s*([^|]+?)\s*\|", re.MULTILINE)


def _adr_meta(text: str) -> tuple[str, str, str]:
    """Extract (title, status, date) from one ADR, tolerating both layouts.

    Newer ADRs carry YAML frontmatter; older ones use a prose or table
    ``## Status`` block. Frontmatter wins where present.
    """
    fm: dict[str, str] = {}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            fm = {
                m.group(1): m.group(2).strip("\"'")
                for m in _FM_RE.finditer(text[:end])
            }

    title = fm.get("title", "")
    if not title:
        m = _HEADING_RE.search(text)
        title = m.group(1).strip() if m else "(untitled)"
    title = re.sub(r"^ADR-\d{3}[a-z]?:\s*", "", title).strip()

    status = fm.get("status", "")
    date = fm.get("created", "")
    if not status:
        m = _PROSE_STATUS_RE.search(text)
        if m:
            status, date = m.group(1), m.group(2) or date
        else:
            m = _TABLE_STATUS_RE.search(text)
            status = m.group(1) if m else "Unknown"
    if not date:
        m = _TABLE_DATE_RE.search(text)
        date = m.group(1) if m else "—"
    return title, status.capitalize(), date


def _build_index(s: Scan, root: Path) -> str:
    """Render docs/architecture/adrs/README.md from the ADRs on disk."""
    rows = []
    for f in sorted(s.files, key=lambda x: (x.number, x.slug)):
        try:
            text = (root / f.path).read_text(encoding="utf-8")
        except OSError as exc:
            raise SystemExit(f"ERROR [adr_refs] cannot read {f.path}: {exc}") from exc
        title, status, date = _adr_meta(text)
        name = f"ADR-{f.number:03d}"
        rows.append(f"| [{name}]({f.path.name}) | {status} | {title} | {date} |")

    return (
        '---\ntitle: "Architecture Decision Records"\n'
        'description: "Index of all Architecture Decision Records (ADRs) for the '
        'leafcutter-ai package, listing each decision\'s number, status, title, '
        'and date."\ntype: "reference"\n---\n\n'
        "# Architecture Decision Records\n\n"
        "This directory contains Architecture Decision Records (ADRs) for the "
        "leafcutter-ai\npackage. ADRs document significant architectural decisions "
        "— the context, the choice\nmade, and the consequences — so that future "
        "contributors can understand *why* things\nare the way they are.\n\n"
        "Every ADR owns exactly one integer. Regenerate this index after adding or\n"
        "renumbering an ADR:\n\n"
        "```bash\npython scripts/adr_refs.py --index --write\n```\n\n"
        "## Index\n\n"
        "| # | Status | Title | Date |\n|---|--------|-------|------|\n"
        + "\n".join(rows)
        + "\n"
    )


def _disambiguate(s: Scan, root: Path, spec: dict, dry_run: bool) -> int:
    """Retarget BARE ``ADR-NNN`` citations that a renumbering left pointing at
    the wrong decision.

    ``spec`` maps an old number to {new number: [path globs]}. Only bare
    citations are touched: the pattern refuses to match when the number is
    followed by ``-`` (a slug, already unambiguous and already rewritten) or by
    another digit. Scoping by glob is what makes this safe -- the caller states
    which files meant which decision, rather than the tool guessing.
    """
    total = 0
    for old, targets in spec.items():
        # A key like "007b" targets the invented letter-suffixed label the stale
        # README used to tell two same-numbered ADRs apart. Those are exact and
        # unambiguous, so they match as a whole token and the suffix is dropped.
        old_n, sfx = int(old[:3]), old[3:]
        if sfx:
            pat = re.compile(rf"\bADR([-_ ]?){old_n:03d}{sfx}\b", re.IGNORECASE)
        else:
            pat = re.compile(rf"\bADR([-_ ]?){old_n:03d}(?![-\d])", re.IGNORECASE)
        for new, globs in targets.items():
            new_n = int(new)
            matched: list[Path] = []
            for g in globs:
                matched.extend(
                    p for p in root.glob(g)
                    if p.is_file()
                    and not any(part in SKIP_DIRS for part in p.parts)
                )
            for p in sorted(set(matched)):
                try:
                    text = p.read_text(encoding="utf-8")
                except OSError as exc:
                    print(f"WARN [adr_refs] unreadable {p}: {exc}", file=sys.stderr)
                    continue
                def _renumber(m: re.Match[str], nn: int = new_n) -> str:
                    """Rewrite one bare citation, preserving its separator."""
                    return f"ADR{m.group(1)}{nn:03d}"

                new_text, n = pat.subn(_renumber, text)
                if not n:
                    continue
                total += n
                print(f"  ADR-{old_n:03d} -> ADR-{new_n:03d}  "
                      f"{p.relative_to(root)}: {n}")
                if not dry_run:
                    try:
                        p.write_text(new_text, encoding="utf-8")
                    except OSError as exc:
                        raise SystemExit(
                            f"ERROR [adr_refs] cannot write {p}: {exc}"
                        ) from exc
    print(f"\ntotal: {total} bare citations retargeted")
    if dry_run:
        print("DRY RUN — nothing written. Re-run with --write to apply.")
    return 0


def _fix_links(root: Path, dry_run: bool) -> int:
    """Repair ADR links that point at ``architecture/`` instead of ``architecture/adrs/``.

    ADRs live in ``docs/architecture/adrs/``. A link that names the parent
    directory resolves to nothing, but reads as valid, so it survives review.
    """
    pat = re.compile(r"(architecture/)(ADR-\d{3}-)")
    total, files = 0, 0
    for p in _walk(root):
        try:
            text = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"WARN [adr_refs] unreadable {p}: {exc}", file=sys.stderr)
            continue
        new_text, n = pat.subn(r"\1adrs/\2", text)
        if not n:
            continue
        total += n
        files += 1
        print(f"  {p.relative_to(root)}: {n}")
        if not dry_run:
            try:
                p.write_text(new_text, encoding="utf-8")
            except OSError as exc:
                raise SystemExit(f"ERROR [adr_refs] cannot write {p}: {exc}") from exc
    print(f"\ntotal: {total} links repaired in {files} files")
    if dry_run:
        print("DRY RUN — nothing written. Re-run with --write to apply.")
    return 0


def _load_plan(path: Path) -> dict[str, str]:
    """Load a renumbering plan: {"old-slug": "NNN", ...}."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"ERROR [adr_refs] cannot read plan {path}: {exc}") from exc
    return json.loads(raw)


def _apply(s: Scan, root: Path, plan: dict[str, str], dry_run: bool) -> int:
    """Rename planned ADR files and rewrite every qualified citation.

    Bare citations are never rewritten — after a number is split, a bare
    ``ADR-NNN`` no longer identifies one decision, so it is reported instead.
    """
    by_slug = {f.slug: f for f in s.files}
    moves: list[tuple[AdrFile, int, str]] = []
    for slug, new_num_s in plan.items():
        f = by_slug.get(slug)
        if f is None:
            raise SystemExit(f"ERROR [adr_refs] plan names unknown slug: {slug}")
        new_num = int(new_num_s)
        moves.append((f, new_num, f"ADR-{new_num:03d}-{slug}.md"))

    print("== Renames ==")
    for f, new_num, new_name in moves:
        if f.number == new_num:
            # Already at its target number. The file needs no move, but its
            # citations may still name an older number -- e.g. a newly authored
            # ADR adopting a slug that existing text cites at a foreign number.
            print(f"  ADR-{new_num:03d}-{f.slug}.md  (in place; citations only)")
            continue
        print(f"  ADR-{f.number:03d}-{f.slug}.md  ->  {new_name}")
        if not dry_run:
            src = root / f.path
            dst = src.with_name(new_name)
            try:
                subprocess.run(
                    ["git", "-C", str(root), "mv", str(src), str(dst)],
                    capture_output=True, text=True, check=True,
                )
            except subprocess.CalledProcessError as exc:
                raise SystemExit(
                    f"ERROR [adr_refs] git mv failed for {src}: {exc.stderr}"
                ) from exc

    # Rewrite qualified citations: any "ADR<sep>NNN-<slug>" whose slug is planned.
    edits: dict[Path, int] = defaultdict(int)
    slug_to_new = {f.slug: new_num for f, new_num, _ in moves}
    patterns = [
        (re.compile(rf"\bADR([-_ ]?)\d{{3}}(-{re.escape(slug)})\b"), new_num)
        for slug, new_num in slug_to_new.items()
    ]

    print("\n== Qualified citation rewrites ==")
    for p in _walk(root):
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            print(f"WARN [adr_refs] unreadable {p}: {exc}", file=sys.stderr)
            continue
        original = text
        for pat, new_num in patterns:

            def _renumber(m: re.Match[str], nn: int = new_num) -> str:
                """Rewrite one slug-qualified citation, keeping separator and slug."""
                return f"ADR{m.group(1)}{nn:03d}{m.group(2)}"

            text, n = pat.subn(_renumber, text)
            if n:
                edits[p.relative_to(root)] += n
        if text != original and not dry_run:
            try:
                p.write_text(text, encoding="utf-8")
            except OSError as exc:
                raise SystemExit(f"ERROR [adr_refs] cannot write {p}: {exc}") from exc

    for rel, n in sorted(edits.items()):
        print(f"  {rel}: {n}")
    print(f"  total: {sum(edits.values())} in {len(edits)} files")

    print("\n== Bare citations needing manual triage ==")
    total_bare = 0
    for f, _new, _name in moves:
        bare = [r for r in s.refs_for(f.number) if not r.qualified]
        if bare:
            total_bare += len(bare)
            print(f"  ADR-{f.number:03d} (split): {len(bare)} bare citations "
                  f"— run: adr_refs.py --adr {f.number}")
    if not total_bare:
        print("  none")

    if dry_run:
        print("\nDRY RUN — nothing written. Re-run with --write to apply.")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Audit and repair ADR numbering across the repository.",
    )
    ap.add_argument("--root", default=".", help="Repository root (default: cwd).")
    ap.add_argument("--adr", type=int, metavar="NNN",
                    help="List every occurrence of one ADR number.")
    ap.add_argument("--json", action="store_true", help="Emit the audit as JSON.")
    ap.add_argument("--index", action="store_true",
                    help="Regenerate the ADR README index from the files on disk.")
    ap.add_argument("--apply", metavar="PLAN.json",
                    help='Renumbering plan: {"slug": "NNN", ...}.')
    ap.add_argument("--disambiguate", metavar="MAP.json",
                    help='Retarget bare citations: {"old": {"new": [globs]}}.')
    ap.add_argument("--fix-links", action="store_true",
                    help="Repair ADR links missing the adrs/ path segment.")
    ap.add_argument("--write", action="store_true",
                    help="With --apply, actually rename and rewrite (default: dry run).")
    args = ap.parse_args(argv)

    root = _repo_root(Path(args.root).resolve())
    s = scan(root)

    if args.apply:
        return _apply(s, root, _load_plan(Path(args.apply)), dry_run=not args.write)

    if args.fix_links:
        return _fix_links(root, dry_run=not args.write)

    if args.disambiguate:
        return _disambiguate(
            s, root, _load_plan(Path(args.disambiguate)), dry_run=not args.write
        )

    if args.index:
        content = _build_index(s, root)
        if args.write:
            target = root / ADR_DIR / "README.md"
            try:
                target.write_text(content, encoding="utf-8")
            except OSError as exc:
                raise SystemExit(f"ERROR [adr_refs] cannot write {target}: {exc}") from exc
            print(f"wrote {target.relative_to(root)} ({len(s.files)} ADRs)")
        else:
            print(content)
        return 0

    if args.adr is not None:
        _print_occurrences(s, args.adr)
        return 0

    if args.json:
        print(json.dumps({
            "files": [{"number": f.number, "slug": f.slug, "path": str(f.path)}
                      for f in s.files],
            "duplicates": {str(n): [f.slug for f in fs]
                           for n, fs in s.duplicates().items()},
            "gaps": s.gaps(),
            "dangling": {str(n): sorted({str(r.path) for r in rs})
                         for n, rs in s.dangling().items()},
        }, indent=2))
        return 0

    _print_report(s)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-08-13 [adr-numbering]: Created to audit and repair the ADR numbering
  defects found on 2026-08-13 — four duplicated integers (004 x2, 007 x3,
  017 x3, 025 x2), one sequence gap (008), and a set of citations to ADR
  numbers that own no file. Deliberately splits citations into "qualified"
  (carries a slug, so mechanically rewritable) and "bare" (ADR-NNN alone,
  ambiguous once a number is split, so reported for human triage rather than
  rewritten). This is the read-side counterpart to check_adr_collision.py,
  which only prevents NEW collisions at commit time and cannot see the ones
  already merged.
====================================================================
"""
