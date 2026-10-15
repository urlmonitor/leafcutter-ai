"""
MODULE: unit_tests/commit_guardian/test_ge_127g_3.py
COVERS: GE-127g-3 -- the set-aside population is exactly the declared locations,
    so a document a person writes is still judged however it is named or wherever
    it sits.

GOAL: One test per declared test_spec descriptor. Each drives the REAL
    check_doc_length.py as a subprocess against a real throwaway git repo with a
    real ``git add`` and reads the verdict (exit code and the documents named)
    from the gate's own output -- never a pattern-vs-path assertion. Every length
    is derived from the shipped limits and every expected set is computed from
    the tree or the fixture the test constructed, never pinned.

REACHABILITY ENTRY POINT (resolved, BP-1100g-2 Step 1.1): CLI script --
    ``python templates/scripts/commit_guardian/check_doc_length.py`` run with cwd
    at the staged repo.

Wrong versions the descriptors catch: suffix-based membership (arm 1); bare
    filename match / leftover excluded_files (arms 2, 4); whole-docs/ or
    widened-to-parent set-aside (arms 3, 4); a deny-list beside the declared
    set (arm 4).

DECISION HISTORY
- 2026-10-14 [GE-127g-3/test-writer]: Initial authoring.
- 2026-10-14 [GE-127g-3/mutation-review]: Arm 4 stayed green under the
    bare-filename and deny-list mutations because no staged hand-authored doc
    resembled a declared member. Each hand-authored directory now also stages
    run-time-derived resemblance documents (declared basenames, README.md,
    declared-directory suffixes).
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127g_5_fixture as fx  # noqa: E402

LIMIT = fx.shipped_limit()
ADR_LIMIT = int(
    json.loads((fx.GUARDIAN_DIR / fx.CONFIG_NAME).read_text(encoding="utf-8"))["doc_length"]["max_lines_adr"]
)
OVER = max(LIMIT, ADR_LIMIT) + 40  # over every authored limit (AC: 340 vs 300)
SMALL = 20
CARDS_DIR = "docs/agents/cards/"
PROBE = "ge127g3-probe.md"
REPO_DOCS = fx.base.REPO_ROOT / "docs"


def _declared_paths(guardian: Path) -> list[str]:
    return fx.base.set_aside_paths(guardian)


def _inside_declared(rel: str, declared: list[str]) -> bool:
    """Independent restatement of membership, used only to compute expectations."""
    return any(rel.startswith(d) if d.endswith("/") else rel == d for d in declared)


def _hand_authored_directories(declared: list[str]) -> list[str]:
    """Every docs/ directory (repo-relative, '/'-terminated) holding a hand-authored .md, from the real tree."""
    found: list[str] = []
    for dirpath, dirnames, filenames in os.walk(REPO_DOCS):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d != "__pycache__"]
        rel_dir = Path(dirpath).relative_to(fx.base.REPO_ROOT).as_posix() + "/"
        if any(
            name.endswith(".md") and not _inside_declared(rel_dir + name, declared) for name in filenames
        ):
            found.append(rel_dir)
    return sorted(found)


def _refused_names(result) -> set[str]:
    return fx.base.named_docs(fx.output_of(result))


def test_hand_authored_document_with_the_generated_suffix_is_still_judged(tmp_path: Path) -> None:
    # covers: GE-127g-3
    # covers: GE-127g
    # angle: discrimination
    """Arm 1. A hand-authored ``.card.md`` OUTSIDE the declared cards directory,
    over the limit, is refused and named -- while a generated card inside the
    declared directory, staged in the same commit and equally over the limit, is
    not named. The two differ only by location.

    Must implement: membership by declared location alone. Wrong version caught:
    membership by the ``.card.md`` suffix (the hand-authored doc would be set
    aside and the commit would complete).
    """
    guardian = fx.base.copy_guardian(tmp_path / "guardian")
    assert CARDS_DIR in _declared_paths(guardian), "precondition: shipped declaration names the cards directory"
    hand = "docs/guides/hand-written.card.md"
    generated = f"{CARDS_DIR}generated-agent.card.md"
    repo = fx.build_repo(tmp_path / "repo", committed={}, staged={hand: OVER, generated: OVER})

    result = fx.run_gate(repo, guardian)

    assert result.returncode == fx.base.REFUSED_EXIT, (
        f"commit completed (exit {result.returncode}) over a hand-authored .card.md: {fx.output_of(result)!r}"
    )
    assert _refused_names(result) == {hand}, (
        f"named {sorted(_refused_names(result))!r}, expected exactly {hand!r}: {fx.output_of(result)!r}"
    )


def test_declared_filename_does_not_exempt_the_same_name_elsewhere(tmp_path: Path) -> None:
    # covers: GE-127g-3
    # angle: discrimination
    """Arm 2. The declaration lists a README.md INSIDE one location; a
    hand-authored README.md outside every declared location, over the limit, is
    refused and named, while the declared README.md staged alongside it (equally
    over the limit) is not.

    Wrong versions caught: matching a declared entry against any document sharing
    its filename at any depth; leaving ``excluded_files`` basename matching in
    place beside the declaration.
    """
    declared_readme = "docs/gen-alpha/README.md"
    guardian = fx.make_guardian(tmp_path / "guardian", [fx.entry(declared_readme, fx.GROUND_A, 100000)])
    hand = "docs/guides/README.md"
    repo = fx.build_repo(tmp_path / "repo", committed={}, staged={hand: OVER, declared_readme: OVER})

    result = fx.run_gate(repo, guardian)

    assert result.returncode == fx.base.REFUSED_EXIT, (
        f"commit completed (exit {result.returncode}) over a hand-authored README.md: {fx.output_of(result)!r}"
    )
    assert _refused_names(result) == {hand}, (
        f"named {sorted(_refused_names(result))!r}, expected exactly {hand!r}: {fx.output_of(result)!r}"
    )


def test_one_over_limit_document_per_hand_authored_directory_is_refused_and_named(tmp_path: Path) -> None:
    # covers: GE-127g-3
    # angle: criterion
    """Arm 3. One over-limit document is staged in EACH docs/ directory of this
    repository that holds a hand-authored document (directory list derived from
    the real tree at run time); the commit is refused and the documents named are
    ALL of them.

    Wrong versions caught: declaring the whole of docs/ set aside; widening a
    declared directory entry to a parent of itself.
    """
    guardian = fx.base.copy_guardian(tmp_path / "guardian")
    declared = _declared_paths(guardian)
    directories = _hand_authored_directories(declared)
    assert directories, "the repository tree yielded no hand-authored docs/ directory"
    probes = {f"{d}{PROBE}" for d in directories}
    assert not any(_inside_declared(p, declared) for p in probes), "probe document inside a declared location"
    repo = fx.build_repo(tmp_path / "repo", committed={}, staged={p: OVER for p in probes})

    result = fx.run_gate(repo, guardian)

    assert result.returncode == fx.base.REFUSED_EXIT, (
        f"commit completed (exit {result.returncode}) over {len(probes)} hand-authored documents"
    )
    named = _refused_names(result)
    assert named == probes, (
        f"not named: {sorted(probes - named)!r}; named but not staged: {sorted(named - probes)!r}"
    )


def _declared_suffixes(declared: list[str]) -> set[str]:
    """Multi-part filename suffixes (e.g. ``.card.md``) carried by real files inside each declared directory."""
    suffixes: set[str] = set()
    for d in declared:
        location = fx.base.REPO_ROOT / d
        if not d.endswith("/") or not location.is_dir():
            continue
        for path in location.rglob("*.md"):
            suffix = "".join(Path(path.name).suffixes)
            if suffix != ".md":
                suffixes.add(suffix)
    return suffixes


def _resemblance_names(declared: list[str]) -> set[str]:
    """Filenames that RESEMBLE a declared member without being inside a declared location.

    The basename of every exact declared entry, README.md (the live instance:
    hand-authored READMEs under docs/), and one name per suffix the real files
    in each declared directory carry -- all derived from the declaration and
    the real tree at run time.
    """
    names = {d.rsplit("/", 1)[-1] for d in declared if not d.endswith("/")}
    names.add("README.md")
    names.update(f"ge127g3-resembles{suffix}" for suffix in _declared_suffixes(declared))
    return names


def _staged_set(declared: list[str], directories: list[str]) -> dict[str, int]:
    """Per hand-authored directory: a probe plus every resemblance name; plus documents inside every declared location.

    A resemblance document that would itself land inside a declared location
    (e.g. ``docs/`` + ``roadmap.md`` is the declared ``docs/roadmap.md``) is not
    added as a hand-authored document -- it is a declared member and is staged
    as such below.
    """
    staged = {f"{d}{PROBE}": SMALL for d in directories}
    resemblances = _resemblance_names(declared)
    for d in directories:
        for name in resemblances:
            rel = f"{d}{name}"
            if not _inside_declared(rel, declared):
                staged[rel] = SMALL
    for d in declared:
        if d.endswith("/"):
            staged[f"{d}ge127g3-a.md"] = SMALL
            staged[f"{d}README.md"] = SMALL
        else:
            staged[d] = SMALL
    return staged


def _set_aside_named(output: str) -> set[str]:
    return set(re.findall(r"set aside:\s*(\S+\.md)", output))


def test_judged_population_falls_by_exactly_the_declared_locations_size(tmp_path: Path) -> None:
    # covers: GE-127g-3
    # angle: discrimination
    """Arm 4. Over ONE staged set spanning docs/, the gate is run twice -- once
    with the declaration empty, once with the shipped declaration. The judged
    figure falls by exactly the number of staged documents inside the declared
    locations (computed here from the staged set, not pinned), the set-aside
    figure equals that number, and every document reported as set aside lies
    inside a declared location.

    Every hand-authored directory also carries documents that RESEMBLE a
    declared member -- the basename of each exact declared entry, README.md, and
    each filename suffix the real declared directories' files carry -- while
    lying outside every declared location.

    Wrong versions caught: bare-filename matching (the same-basename documents
    outside the declared locations would also fall out of the judged figure);
    suffix-based membership (the suffix-carrying documents would fall out); a
    deny-list beside the declared set (it names only the documents arms 1-2
    use, so the resemblance documents in every other directory still fall
    out); setting the whole of docs/ aside (the judged figure would fall by far
    more than the declared locations hold).
    """
    populated = fx.base.copy_guardian(tmp_path / "guardian_populated")
    empty = fx.make_guardian(tmp_path / "guardian_empty", [])
    declared = _declared_paths(populated)
    directories = _hand_authored_directories(declared)
    staged = _staged_set(declared, directories)
    expected_aside = {rel for rel in staged if _inside_declared(rel, declared)}
    assert expected_aside and len(expected_aside) < len(staged), "fixture must straddle the declared locations"
    repo = fx.build_repo(tmp_path / "repo", committed={}, staged=staged)

    before = fx.run_gate(repo, empty)
    after = fx.run_gate(repo, populated)
    out_before, out_after = fx.output_of(before), fx.output_of(after)

    assert before.returncode == fx.CLEAN_EXIT, f"empty-declaration run refused: {out_before!r}"
    assert after.returncode == fx.CLEAN_EXIT, f"populated-declaration run refused: {out_after!r}"
    judged_before = fx.count_of(out_before, "judged")
    judged_after = fx.count_of(out_after, "judged")
    assert judged_before == len(staged), f"empty declaration: judged {judged_before}, staged {len(staged)}"
    assert judged_after is not None and judged_before - judged_after == len(expected_aside), (
        f"judged fell from {judged_before} to {judged_after}; documents inside declared locations: {len(expected_aside)}"
    )
    assert fx.count_of(out_after, "set aside") == len(expected_aside), f"set-aside figure wrong: {out_after!r}"
    reported = _set_aside_named(out_after)
    assert reported == expected_aside, (
        f"reported set aside but not declared: {sorted(reported - expected_aside)!r}; "
        f"declared but not reported: {sorted(expected_aside - reported)!r}"
    )
