"""
MODULE: unit_tests/evals/tq200d1ii/_helpers.py
GOAL: The registry, the page parser and the drift checks for the TQ-200d-1-ii assertion-kinds
    reference (a hub page plus four family pages). Not a test file.
BUSINESS CONTEXT: The reference is worth having only while it cannot drift from the scorers
    (every registered kind has one entry) or from the agent templates (every quoted sentence is
    still there, word for word). The checks here return problem tuples ``(code, subject)`` so a
    test can pin the exact problem a bad page set carries. They read the REAL registry
    (``produced_tests_scoring.KINDS``); the kind-to-page mapping is derived from the registering
    module, never hard-coded.
ARCHITECTURE: ``family_of`` maps kind -> family from the sub-registries. ``parse_page`` turns
    one page into entries (heading ``### `<kind>```, labelled parts ``**Label:**`` at line start,
    fenced code ignored). ``check_*`` take a ``pages`` dict {file name: text} and a ``root``
    (the repo root whose templates/agents/ holds the templates), so the same code judges the real
    pages and a mutated copy.
"""

from __future__ import annotations

import posixpath
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
EVALS_DIR = REPO_ROOT / "scripts" / "evals"
if str(EVALS_DIR) not in sys.path:
    sys.path.insert(0, str(EVALS_DIR))

import designer_eval  # noqa: E402
import produced_tests_db  # noqa: E402
import produced_tests_scoring  # noqa: E402
import sql_test_writer_eval  # noqa: E402

REF_DIR = "docs/reference"
HUB = "produced-tests-eval-assertion-kinds.md"
FAMILY_PAGE = {
    "test-writer": "produced-tests-eval-assertion-kinds-test-writer.md",
    "database-setting": "produced-tests-eval-assertion-kinds-database-setting.md",
    "sql-test-writer": "produced-tests-eval-assertion-kinds-sql-test-writer.md",
    "test-designer": "produced-tests-eval-assertion-kinds-test-designer.md",
}
ALL_PAGES = [HUB, *FAMILY_PAGE.values()]
PARTS = ["Used by", "Reads", "Passes when", "Fails when", "Passing example", "Failing example", "Template sentence"]
HEADING = re.compile(r"^### `([^`\n]+)`\s*$")
LABEL = re.compile(r"^\*\*(" + "|".join(PARTS) + r"):\*\*[ \t]*(.*)$")
PATH_LINE = re.compile(r"^- (templates/agents/[\w.-]+\.md)\s*$")
LINK = re.compile(r"\]\(([^)\s]+)\)")


def family_of() -> dict[str, str]:
    """Kind -> family, from the module that registers it (the db, sql and designer sub-registries)."""
    out = {}
    for kind in produced_tests_scoring.KINDS:
        if kind in designer_eval.KINDS:
            out[kind] = "test-designer"
        elif kind in sql_test_writer_eval.KINDS:
            out[kind] = "sql-test-writer"
        elif kind in produced_tests_db.KINDS:
            out[kind] = "database-setting"
        else:
            out[kind] = "test-writer"
    return out


def read_real_pages() -> dict[str, str]:
    """The real pages that exist (a missing page is simply absent from the dict)."""
    pages = {}
    for name in ALL_PAGES:
        path = REPO_ROOT / REF_DIR / name
        if path.is_file():
            pages[name] = path.read_text(encoding="utf-8")
    return pages


def norm(text: str) -> str:
    """Whitespace-normalise: every run of whitespace becomes one space."""
    return re.sub(r"\s+", " ", text).strip()


def parse_page(text: str) -> list[dict]:
    """Entries of one page: {kind, parts: {label: [lines]}, labels: [label, ...]}. Fenced code is skipped."""
    entries, cur, part, fenced = [], None, None, False
    for line in text.splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
        if not fenced and (m := HEADING.match(line)):
            cur = {"kind": m.group(1), "parts": {}, "labels": []}
            entries.append(cur)
            part = None
            continue
        if not fenced and line.startswith("#"):
            cur, part = None, None
            continue
        if cur is None:
            continue
        lab = None if fenced else LABEL.match(line)
        if lab:
            part = lab.group(1)
            cur["labels"].append(part)
            cur["parts"].setdefault(part, []).append(lab.group(2))
        elif part:
            cur["parts"][part].append(line)
    return entries


def all_entries(pages: dict[str, str]) -> list[tuple[str, dict]]:
    """(page name, entry) over every page."""
    return [(name, e) for name, text in pages.items() for e in parse_page(text)]


def check_kinds(pages: dict[str, str]) -> set[tuple[str, str]]:
    """Problems with the kind set: missing, stale, on_two_pages, wrong_page, missing_page."""
    fam, problems, seen = family_of(), set(), {}
    for name in ALL_PAGES:
        if name not in pages:
            problems.add(("missing_page", name))
    for name, entry in all_entries(pages):
        seen.setdefault(entry["kind"], []).append(name)
    for kind, where in seen.items():
        if kind not in fam:
            problems.add(("stale", kind))
        elif len(where) > 1:
            problems.add(("on_two_pages", kind))
        elif where[0] != FAMILY_PAGE[fam[kind]]:
            problems.add(("wrong_page", kind))
    problems |= {("missing", k) for k in fam if k not in seen}
    return problems


def quotes_of(entry: dict) -> list[tuple[str, str | None]]:
    """(quote text, template path or None) pairs of an entry's Template sentence part."""
    out, buf = [], []
    for line in entry["parts"].get("Template sentence", [])[1:]:
        if line.startswith(">"):
            buf.append(line[1:].strip())
        elif (m := PATH_LINE.match(line)) and buf:
            out.append((norm(" ".join(buf)), m.group(1)))
            buf = []
    if buf:
        out.append((norm(" ".join(buf)), None))
    return out


def check_quotes(pages: dict[str, str], root: Path) -> set[tuple[str, str]]:
    """Problems with quotes: not_verbatim, no_template_path, no_such_template, no_quote."""
    problems = set()
    for _name, entry in all_entries(pages):
        kind = entry["kind"]
        head = norm((entry["parts"].get("Template sentence") or [""])[0])
        quotes = quotes_of(entry)
        if not quotes and not head.lower().startswith("none"):
            problems.add(("no_quote", kind))
        for quote, path in quotes:
            if path is None:
                problems.add(("no_template_path", kind))
            elif not (root / path).is_file():
                problems.add(("no_such_template", kind))
            elif quote not in norm((root / path).read_text(encoding="utf-8")):
                problems.add(("not_verbatim", kind))
    return problems


def check_parts(pages: dict[str, str]) -> set[tuple[str, str]]:
    """Problems with parts: missing_part:<label>, empty_part:<label>, repeated_part:<label>."""
    problems = set()
    for _name, entry in all_entries(pages):
        for label in PARTS:
            n = entry["labels"].count(label)
            body = norm(" ".join(entry["parts"].get(label, [])))
            if n == 0:
                problems.add((f"missing_part:{label}", entry["kind"]))
            elif n > 1:
                problems.add((f"repeated_part:{label}", entry["kind"]))
            elif not body:
                problems.add((f"empty_part:{label}", entry["kind"]))
    return problems


def links_in(text: str) -> list[str]:
    """Link targets of a markdown text, fragment dropped."""
    return [t.split("#")[0] for t in LINK.findall(text)]


def resolves_to(target: str, base_dir: str, dest: str) -> bool:
    """True when a relative link target, read from base_dir, is the repo path dest."""
    return posixpath.normpath(posixpath.join(base_dir, target)) == dest


def section(text: str, heading_prefix: str) -> str:
    """Body of the ``## `` section whose heading starts with heading_prefix ('' when absent)."""
    out, on = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            on = line[3:].startswith(heading_prefix)
            continue
        if on:
            out.append(line)
    return "\n".join(out)


def check_readme(text: str, readme_dir: str, root: Path) -> set[tuple[str, str]]:
    """Problems with the evals README: no_hub_link, broken_hub_link, kind_name, no_section."""
    body = section(text, "Produced-tests mode")
    if not body:
        return {("no_section", "")}
    hub = f"{REF_DIR}/{HUB}"
    problems = set()
    if not any(resolves_to(t, readme_dir, hub) for t in links_in(body) if t):
        problems.add(("no_hub_link", ""))
    elif not (root / hub).is_file():
        problems.add(("broken_hub_link", ""))
    pages = [f"{REF_DIR}/{n}" for n in ALL_PAGES]
    for line in body.splitlines():
        named = [k for k in produced_tests_scoring.KINDS if re.search(rf"(?<!\w){re.escape(k)}(?!\w)", line)]
        linked = any(resolves_to(t, readme_dir, p) for t in links_in(line) for p in pages)
        if named and not (linked and len(named) == 1):
            problems.update(("kind_name", k) for k in named)
    return problems


def check_index(index_text: str, pages: dict[str, str]) -> set[tuple[str, str]]:
    """Problems with the reference index and back-links: hub_lines:<n>, family_in_index, no_back_link."""
    problems = set()
    hub = f"{REF_DIR}/{HUB}"
    hub_lines = [ln for ln in index_text.splitlines() if any(resolves_to(t, REF_DIR, hub) for t in links_in(ln))]
    if len(hub_lines) != 1:
        problems.add((f"hub_lines:{len(hub_lines)}", ""))
    for name in FAMILY_PAGE.values():
        if any(resolves_to(t, REF_DIR, f"{REF_DIR}/{name}") for t in links_in(index_text)):
            problems.add(("family_in_index", name))
        if name not in pages:
            problems.add(("missing_page", name))
        elif not any(resolves_to(t, REF_DIR, hub) for t in links_in(pages[name])):
            problems.add(("no_back_link", name))
    return problems
