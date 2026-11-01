"""
MODULE: unit_tests/evals/tq200d1ii/_pageset.py
GOAL: The page set the TQ-200d-1-ii bad cases are mutated from, and the mutations. Not a test file.
BUSINESS CONTEXT: The real pages are the gold once they exist; until then a minimal synthetic
    page set is built in tmp_path from the REAL registry and REAL template sentences, in exactly
    the entry format the AC fixes (heading, seven labelled parts, a blockquote plus the template
    path). Every bad case is that gold set with ONE thing swapped, so it can only fail for the
    reason the swap carries. The synthetic set is only a stand-in for the gold; the tests also
    judge the REAL pages (and are red while those do not exist).
ARCHITECTURE: ``gold_pages`` returns {page name: text}. ``entry_block``/``drop_entry``/``add_entry``
    work on the heading-to-next-heading span of one entry. ``mutate_*`` return a new dict.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import unit_tests.evals.tq200d1ii._helpers as h

TEMPLATES = REPO_TEMPLATES = h.REPO_ROOT / "templates" / "agents"
SYN_TEMPLATE = {
    "test-writer": "test-writer.md",
    "database-setting": "test-runner.md",
    "sql-test-writer": "sql-test-writer.md",
    "test-designer": "test-designer.md",
}


def sentences(template: str) -> list[str]:
    """Plain one-line prose sentences of a real template (no markup that could confuse a quote)."""
    out = []
    for line in (TEMPLATES / template).read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if 40 <= len(text) <= 240 and re.match(r"^[A-Za-z][A-Za-z0-9 ,.;:'()/-]+$", text) and text not in out:
            out.append(text)
    return out


def render_entry(kind: str, template: str, sentence: str | None, wrap: bool = False) -> str:
    """One entry in the AC's format; sentence None renders the 'none' form."""
    if sentence is None:
        tail = "**Template sentence:** none - this kind checks no sentence of a template."
    else:
        words = sentence.split(" ")
        lines = [" ".join(words[: len(words) // 2]), " ".join(words[len(words) // 2:])] if wrap else [sentence]
        tail = "**Template sentence:**\n\n" + "\n".join(f"> {ln}" for ln in lines) + f"\n\n- templates/agents/{template}"
    return (
        f"### `{kind}`\n\n"
        "**Used by:** the test-writer set.\n\n"
        "**Reads:** the produced test files.\n\n"
        f"**Passes when:** the produced test does what {kind} checks.\n\n"
        f"**Fails when:** the produced test does not do what {kind} checks.\n\n"
        "**Passing example:**\n\n```python\nassert rows == 3\n```\n\n"
        "**Failing example:**\n\n```python\nassert rows >= 0\n```\n\n"
        f"{tail}\n"
    )


def synthetic_pages() -> dict[str, str]:
    """A minimal valid page set: hub plus four family pages, built from the real registry."""
    fam, pool, used = h.family_of(), {}, {}
    pages = {h.HUB: "---\ntitle: hub\ntype: reference\n---\n\n# Hub\n\nSee the family pages.\n"}
    for family, name in h.FAMILY_PAGE.items():
        pool[family] = sentences(SYN_TEMPLATE[family])
        body = f"---\ntitle: {family}\ntype: reference\n---\n\n# {family}\n\nBack to the [hub]({h.HUB}).\n\n## Entries\n\n"
        pages[name] = body
    for i, (kind, family) in enumerate(sorted(fam.items())):
        n = used.get(family, 0)
        used[family] = n + 1
        sentence = None if i == 0 else pool[family][n]
        pages[h.FAMILY_PAGE[family]] += render_entry(kind, SYN_TEMPLATE[family], sentence, wrap=(i == 1)) + "\n"
    return pages


def gold_pages() -> dict[str, str]:
    """The real pages when all five exist, else the synthetic stand-in."""
    real = h.read_real_pages()
    return real if len(real) == len(h.ALL_PAGES) else synthetic_pages()


def entry_span(text: str, kind: str) -> tuple[int, int]:
    """Character span of one entry: its heading up to the next heading of level 1-3 (or the end)."""
    start = re.search(rf"^### `{re.escape(kind)}`\s*$", text, re.M)
    assert start, f"no entry for {kind}"
    nxt = re.search(r"^#{1,3} ", text[start.end():], re.M)
    return start.start(), start.end() + (nxt.start() if nxt else len(text) - start.end())


def page_of(pages: dict[str, str], kind: str) -> str:
    """Name of the page holding kind's entry."""
    for name, text in pages.items():
        if re.search(rf"^### `{re.escape(kind)}`\s*$", text, re.M):
            return name
    pytest.fail(f"{kind} has no entry")


def drop_entry(pages: dict[str, str], kind: str) -> dict[str, str]:
    """The pages with kind's entry removed."""
    name = page_of(pages, kind)
    a, b = entry_span(pages[name], kind)
    return {**pages, name: pages[name][:a] + pages[name][b:]}


def add_entry(pages: dict[str, str], to_page: str, new_kind: str, like: str) -> dict[str, str]:
    """The pages with a copy of like's entry, headed new_kind, appended to to_page."""
    src = page_of(pages, like)
    a, b = entry_span(pages[src], like)
    block = pages[src][a:b].replace(f"### `{like}`", f"### `{new_kind}`", 1)
    return {**pages, to_page: pages[to_page].rstrip("\n") + "\n\n" + block}


def quoted_kind(pages: dict[str, str], template: str | None = None) -> str:
    """The first kind (sorted) whose entry has a quote, optionally one citing the given template file."""
    for name, entry in sorted(h.all_entries(pages), key=lambda p: p[1]["kind"]):
        for _quote, path in h.quotes_of(entry):
            if path and (template is None or path.endswith("/" + template)):
                return entry["kind"]
    pytest.fail("no quoted entry in the page set")


def edit_entry(pages: dict[str, str], kind: str, fn) -> dict[str, str]:
    """The pages with fn applied to the text of kind's entry."""
    name = page_of(pages, kind)
    a, b = entry_span(pages[name], kind)
    return {**pages, name: pages[name][:a] + fn(pages[name][a:b]) + pages[name][b:]}


def drop_label(block: str, label: str) -> str:
    """The entry block without the line that opens part *label* (its content stays, unlabelled)."""
    return re.sub(rf"^\*\*{re.escape(label)}:\*\*[ \t]*", "", block, count=1, flags=re.M)


def empty_label(block: str, label: str) -> str:
    """The entry block with part *label* kept but its content on the label line removed and the lines after it too."""
    return re.sub(rf"^\*\*{re.escape(label)}:\*\*.*?(?=^\*\*|\Z)", f"**{label}:**\n\n", block, count=1, flags=re.M | re.S)


def swap_template_path(block: str, new_template: str) -> str:
    """The entry block citing another template file for its quote."""
    return re.sub(r"^- templates/agents/[\w.-]+\.md", f"- templates/agents/{new_template}", block, count=1, flags=re.M)


def template_lacking(sentence: str, exclude: str) -> str:
    """A real template file (not *exclude*) that does not contain the sentence."""
    for path in sorted(TEMPLATES.glob("*.md")):
        if path.name != exclude and h.norm(sentence) not in h.norm(path.read_text(encoding="utf-8")):
            return path.name
    pytest.fail("every template contains the sentence")


def write_pages(root: Path, pages: dict[str, str]) -> None:
    """Write pages under root/docs/reference (for tests that need a tree)."""
    ref = root / h.REF_DIR
    ref.mkdir(parents=True, exist_ok=True)
    for name, text in pages.items():
        (ref / name).write_text(text, encoding="utf-8", newline="\n")
