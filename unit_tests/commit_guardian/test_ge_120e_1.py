"""
MODULE: test_ge_120e_1
GOAL: RED tests for GE-120e-1 -- the sole numeric collision on "GE-119" (a
    33-file goal-level tree that keeps the identifier, and a single
    parentless detail-level record about the contract-shrinking guard that
    must move to a free identifier) has to be repaired without breaking any
    of the fifteen coverage tags, the guard-source citation, or the two dated
    changelog citations that name it.
BUSINESS CONTEXT: See
    docs/acceptance-criteria/guardrail-engine/GE-120-numbers-mean-one-thing/GE-120e-1.yaml
    and tickets/00_inbox/TICKET-20260817-GE-120e-1.md. The repair has NOT
    happened yet at the time this module is authored -- every assertion below
    runs against the REAL on-disk AC store (docs/acceptance-criteria/), the
    REAL test tree (unit_tests/), the REAL guard source
    (templates/scripts/commit_guardian/check_contract_shrinking.py), and the
    REAL changelogs -- never a synthetic fixture -- because the defect this
    AC exists to prevent (a renumbering that silently repoints or orphans a
    citation) can only be observed on the actual artifacts. This mirrors the
    repo's own documented failure mode: EPIC-PhantomDoneFilesTouched shipped
    seven green sign-offs while the guarded behaviour was a total no-op,
    caught only once a test ran against a REAL on-disk artifact instead of a
    hand-typed fixture (CLAUDE.md, "Real-artifact behavioral spot-check
    before declaring done").
ARCHITECTURE: The repo root is resolved by walking up from this file's own
    location (never from cwd -- this suite is invoked from more than one
    working directory in this project; see
    unit_tests/commit_guardian/conftest.py, which resolves the same root the
    same way for the same reason). The moved record is located by an exact,
    distinctive TITLE match rather than by filename or by a hardcoded new
    identifier: per the ticket's hand-applied correction, both the BA and the
    IT PO independently missed six of the fifteen coverage tags precisely
    because they enumerated citations by looking in the file whose NAME
    contained the identifier, and the acceptance criterion is deliberately
    written against "an identifier no other artifact claims" -- not against
    the literal string "GE-121" -- so a concurrent mint of GE-121 by another
    session cannot invalidate these tests. The whole-collection uniqueness
    pass used by several tests is implemented inline (a full yaml.safe_load
    across the ~3000 files in the AC store measured ~10s locally, blowing the
    5s per-test performance budget many times over; the top-level ``id:``
    field is always an unindented first-class key in every record observed in
    this store, so a line-anchored regex is exact for this purpose and runs
    in well under a second). The 33-files-unchanged check compares against a
    fixed pre-repair commit (BASELINE_COMMIT below) rather than against
    origin/main, because origin/main does not contain the
    GE-119-green-means-checked/ tree at all on this AC-authoring branch (it
    was authored directly on this branch and has not merged) -- diffing
    against origin/main would raise "path does not exist" for every file, not
    produce a meaningful comparison.
    Do NOT move, rename, or edit any AC YAML, the guard source, the
    changelogs, or the two existing test modules from this file -- it is
    read-only with respect to all of those; it only reads and asserts.
"""

from __future__ import annotations

import os
import re
import subprocess
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Repo-root resolution -- walk up from __file__, never from cwd.
# ---------------------------------------------------------------------------


def _find_repo_root() -> Path:
    """Walk up from this file's own location to find the repo root.

    A directory qualifies when it has both a ``.git`` entry and a
    ``docs/acceptance-criteria`` directory -- the same two-part check used to
    disambiguate the leafcutter-ai repo root from its untracked parent
    workspace directory elsewhere in this project.
    """
    here = Path(__file__).resolve()
    for candidate in [here.parent, *here.parents]:
        if (candidate / ".git").exists() and (candidate / "docs" / "acceptance-criteria").is_dir():
            return candidate
    raise RuntimeError(f"could not locate the repo root by walking up from {here}")  # noqa: TRY003


REPO_ROOT = _find_repo_root()
AC_STORE_ROOT = REPO_ROOT / "docs" / "acceptance-criteria"
UNIT_TESTS_ROOT = REPO_ROOT / "unit_tests"

OLD_ID = "GE-119"
GOAL_RECORD_TITLE = "Trust that a green check actually checked something"
GOAL_FOLDER = AC_STORE_ROOT / "guardrail-engine" / "GE-119-green-means-checked"
MOVED_RECORD_TITLE = "The contract-shrinking guard distinguishes an edited test from a deleted one"

GUARD_SOURCE = REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_contract_shrinking.py"
CHANGELOG_MEANS_GOAL = (
    REPO_ROOT
    / "changelogs"
    / "2026-08-17-1204-changelog-pr-445-ge-119-acs-1200-acceptance-criteria-authored-2026-08-17.md"
)
CHANGELOG_MEANS_MOVED = (
    REPO_ROOT / "changelogs" / "2026-08-14-0037-fix-guardian-tell-an-edited-test-from-a-deleted-one-ge-119.md"
)
ACS_BARE_CITATION_FILE = AC_STORE_ROOT / "ac-store" / "ACS-1200-parked-ideas" / "ACS-1200a-2.yaml"

# The AC/ticket text describes the goal folder as "a folder of 33 files".
# `find <goal-folder> -type f | wc -l` against the real store measures 32, not
# 33, at authoring time -- another instance of the same "recorded by
# assumption, not verified against the real artifact" error this AC's own
# Implementation Notes already caught once (the "nine tags in one file" count
# was actually fifteen across two). Per design constraint 1 (assert on the
# real store, not a hand-typed number), this test asserts the VERIFIED count,
# not the ticket's stated one -- a test hard-coded to a wrong "33" could never
# go green under a correct repair, since a correct repair also leaves exactly
# 32 real files in place.
GOAL_FOLDER_EXPECTED_FILE_COUNT = 32

# Fixed pre-repair baseline commit: this branch's HEAD at the time this test
# module was authored (2026-08-17), confirmed via `git status --short` /
# `git diff HEAD -- <goal-folder>` to have zero diff against the working tree
# for GOAL_FOLDER at authoring time. A MOVING ref (e.g. HEAD read at test-RUN
# time) would itself become the repair commit once the coder phase commits,
# which would make the "unchanged" comparison vacuous -- it would always
# trivially pass because both sides would be the post-repair content.
# origin/main is not usable as the baseline here: it does not contain the
# GE-119-green-means-checked/ tree at all on this AC-authoring branch.
BASELINE_COMMIT = "4a83c82803786514d580826c2752bfcd08585e0c"

_EXCLUDED_DIRS = {".git", "node_modules", "__pycache__", ".leafcutter"}
_SCAN_EXTENSIONS = {".py", ".yaml", ".yml", ".md"}
_COVERS_TAG_PATTERN = re.compile(r"#\s*covers:\s*(\S+)")
_ID_LINE_PATTERN = re.compile(r"^id:\s*(.+?)\s*$")


def _iter_scan_files(root: Path, extensions: set[str] | None = None) -> list[Path]:
    """Walk *root*, excluding vendored/build/deploy directories, returning
    every file whose suffix is in *extensions* (default: py/yaml/yml/md)."""
    exts = extensions if extensions is not None else _SCAN_EXTENSIONS
    found: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDED_DIRS]
        for filename in filenames:
            path = Path(dirpath, filename)
            if path.suffix in exts:
                found.append(path)
    return found


def _citation_pattern(identifier: str) -> re.Pattern[str]:
    """A pattern matching *identifier* as a whole token -- not a sibling
    child identifier that merely starts with it. ``GE-119b`` and ``GE-119c-1``
    are DIFFERENT identifiers (children of the goal record) and must not be
    treated as citations of ``GE-119``: the negative lookahead excludes any
    trailing letter or digit that would extend the match into a longer id."""
    return re.compile(re.escape(identifier) + r"(?![A-Za-z0-9])")


def _build_ac_id_map() -> dict[str, list[Path]]:
    """The whole-collection uniqueness pass: map every AC id declared in the
    store (via a top-level, unindented ``id:`` line) to every file that
    declares it. More than one path under a key is a collision; the map is
    the source of truth every other test in this module consults to ask
    "does this identifier resolve to exactly one record?"
    """
    id_map: dict[str, list[Path]] = {}
    for path in AC_STORE_ROOT.rglob("*.yaml"):
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    match = _ID_LINE_PATTERN.match(line)
                    if match:
                        ac_id = match.group(1).strip("'\"")
                        id_map.setdefault(ac_id, []).append(path)
                        break
        except OSError:
            continue
    return id_map


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise AssertionError(f"{path}: expected a YAML mapping, got {type(data).__name__}")  # noqa: TRY003, TRY004
    return data


def _find_moved_record() -> tuple[Path, dict]:
    """Locate the moved (parentless, contract-shrinking-guard) record by its
    distinctive TITLE -- see module docstring for why title, not filename or
    a hardcoded identifier, is the lookup key. Returns (path, parsed_yaml).
    """
    grep = subprocess.run(
        ["grep", "-rlF", "--include=*.yaml", MOVED_RECORD_TITLE, str(AC_STORE_ROOT)],
        capture_output=True,
        text=True,
        check=False,
    )
    candidates = [Path(p) for p in grep.stdout.splitlines() if p.strip()]
    candidates = [p for p in candidates if GOAL_FOLDER not in p.parents]
    if len(candidates) != 1:
        raise AssertionError(  # noqa: TRY003
            f"expected exactly one AC record titled {MOVED_RECORD_TITLE!r} outside "
            f"{GOAL_FOLDER}, found {len(candidates)}: {candidates}"
        )
    path = candidates[0]
    return path, _load_yaml(path)


def _git_show(ref: str, relative_path: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"{ref}:{relative_path}"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(  # noqa: TRY003
            f"git show {ref}:{relative_path} failed: {result.stderr.decode(errors='replace')}"
        )
    return result.stdout


def _declared_parent_id(data: dict) -> str | None:
    """Return the parent id the record declares.

    Prefers the explicit ``parent`` field (per docs/reference/ac-schema.md:
    "Used when the structural parent cannot be mechanically derived from the
    ID format" -- which is exactly the case for any root-pattern id such as
    GE-121, since derive_parent_id() returns None for PREFIX-NNN ids) and
    falls back to the first ``depends_on`` entry, since ac-schema.md also
    requires "the child's depends_on field MUST include the parent AC ID".
    """
    explicit = data.get("parent")
    if explicit:
        return str(explicit).strip()
    depends_on = data.get("depends_on") or []
    if isinstance(depends_on, list) and depends_on:
        return str(depends_on[0]).strip()
    return None


class TestGE120e1(unittest.TestCase):
    """RED tests for GE-120e-1 -- see module docstring for full context."""

    def test_old_identifier_has_exactly_one_claimant_after_repair(self):
        # covers: GE-120e-1
        """Gherkin Then: exactly one record in the collection claims
        "GE-119", and it is the goal record; the whole-collection uniqueness
        pass reports no finding for that identifier.

        Pre-repair, TWO records claim GE-119 (the 33-file goal tree and the
        parentless contract-shrinking-guard record), so this must fail RED
        until the repair moves the second claimant away.
        """
        id_map = _build_ac_id_map()
        claimants = id_map.get(OLD_ID, [])
        self.assertEqual(
            len(claimants),
            1,
            f"expected exactly one claimant for {OLD_ID}, found {len(claimants)}: {claimants}",
        )
        winner = claimants[0]
        self.assertIn(
            GOAL_FOLDER,
            winner.parents,
            f"the sole {OLD_ID} claimant must be the goal-level record under {GOAL_FOLDER}, got {winner}",
        )
        data = _load_yaml(winner)
        self.assertEqual(
            data.get("title"),
            GOAL_RECORD_TITLE,
            f"{winner} claims {OLD_ID} but its title does not match the goal record's title",
        )

    def test_moved_record_claims_a_free_identifier_with_a_real_parent(self):
        # covers: GE-120e-1
        """Gherkin Then: the parentless record claims an identifier in the
        same namespace that no other artifact claims and that was not
        previously claimed by any retired artifact, declares a parent that
        exists, and that parent lists it among its children.

        Pre-repair, the moved record still claims GE-119 (it has not moved),
        so the very first assertion below must fail RED.
        """
        path, data = _find_moved_record()
        new_id = data.get("id")
        self.assertNotEqual(
            new_id,
            OLD_ID,
            f"moved record at {path} still claims {OLD_ID} -- the repair has not moved it to a free identifier yet",
        )
        # Accept ANY valid id in the guardrail-engine namespace -- root-format
        # (GE-121) or suffix-shaped under a parent (GE-111f, GE-111f-2).
        #
        # This assertion originally required root format (r"^GE-\d{3,}$"),
        # written when the AC's guidance still named GE-121. That guidance was
        # superseded before implementation: check_ac_parent_covered_by.py and
        # scan_ac_orphans.py both derive a record's parent from its id SHAPE via
        # derive_parent_id(), which returns None for a root-format id -- so both
        # hooks classify GE-121 as "root-level, no parent by definition" and skip
        # enforcement entirely. Neither reads the documented `parent:` field.
        # Requiring root format would therefore have forced a parent link that no
        # gate can police: the paper-only parent this AC exists to prevent.
        # Widening the regex here does NOT weaken the test -- the parent's
        # existence and its covered_by back-link are asserted below, and those
        # assertions are what actually carry the criterion.
        self.assertRegex(
            str(new_id),
            r"^GE-\d{3,}[a-z]?(-\d+)*(-i+)?$",
            f"moved record's new id {new_id!r} is not a valid identifier in the guardrail-engine (GE-) namespace",
        )

        id_map = _build_ac_id_map()
        claimants = id_map.get(new_id, [])
        self.assertEqual(
            len(claimants),
            1,
            f"expected exactly one file to claim {new_id}, found {len(claimants)}: {claimants}",
        )

        parent_id = _declared_parent_id(data)
        self.assertTrue(
            parent_id,
            f"moved record {new_id} declares no parent (checked the 'parent' field and depends_on)",
        )
        self.assertNotEqual(
            parent_id,
            OLD_ID,
            "GE-119 (the goal record) is explicitly forbidden as the new parent -- parenting under "
            "it would require adding a child to GE-119.yaml's covered_by, and that file must stay "
            "byte-identical to its pre-repair content",
        )
        parent_claimants = id_map.get(parent_id, [])
        self.assertEqual(
            len(parent_claimants),
            1,
            f"declared parent {parent_id!r} does not resolve to exactly one AC record: {parent_claimants}",
        )
        parent_data = _load_yaml(parent_claimants[0])
        covered_by = parent_data.get("covered_by") or []
        self.assertIn(
            new_id,
            covered_by,
            f"parent {parent_id} at {parent_claimants[0]} does not list {new_id} in its covered_by",
        )

    def test_goal_records_thirty_three_files_are_unchanged(self):
        # covers: GE-120e-1
        """Gherkin Then: every one of the files in the goal record's folder
        is unchanged -- the cheap direction (move the one parentless file,
        leave the 33-file tree alone) was actually taken. NOTE: the AC/ticket
        text says "33 files"; the real folder measures
        GOAL_FOLDER_EXPECTED_FILE_COUNT (32) at authoring time -- see the
        comment on that constant. This test name keeps the ticket's own
        "thirty_three" wording per the Test Requirements contract, but the
        assertion enforces the verified count.

        KNOWN NON-CONSTRAINING PRE-REPAIR: this assertion can trivially PASS
        before any repair exists, because nothing has touched the folder yet
        -- there is no way to make "nothing changed" fail before a change
        that could break it has been attempted. It becomes a real constraint
        the moment the coder phase starts editing this tree: see the test
        writer's completion report for the explicit flag on this point.
        """
        self.assertTrue(GOAL_FOLDER.is_dir(), f"{GOAL_FOLDER} does not exist")
        files = sorted(p for p in GOAL_FOLDER.rglob("*") if p.is_file())
        self.assertEqual(
            len(files),
            GOAL_FOLDER_EXPECTED_FILE_COUNT,
            f"expected exactly {GOAL_FOLDER_EXPECTED_FILE_COUNT} files under {GOAL_FOLDER}, found {len(files)}",
        )
        mismatches = []
        for path in files:
            relative = path.relative_to(REPO_ROOT).as_posix()
            baseline = _git_show(BASELINE_COMMIT, relative)
            current = path.read_bytes()
            if baseline != current:
                mismatches.append(relative)
        self.assertEqual(
            mismatches,
            [],
            f"{len(mismatches)} file(s) under the goal record's folder changed since {BASELINE_COMMIT}: {mismatches}",
        )

    def test_every_coverage_tag_resolves_to_exactly_one_record(self):
        # covers: GE-120e-1
        """Gherkin Then: every one of the fifteen coverage tags, in both
        modules, names the identifier the moved record now claims, so each
        tag resolves to exactly one record.

        Tags are discovered by SCANNING every .py file under unit_tests/, not
        by opening the two known filenames -- per the ticket's hand-applied
        correction, both the BA and the IT PO independently reported "nine,
        in one file" and missed the six tags living in
        test_contract_shrinking_ignores_mentions.py, whose filename does not
        contain the identifier. An assertion hard-coded to one filename would
        have passed the defective nine-tag repair; this one cannot.
        """
        _, moved_data = _find_moved_record()
        new_id = moved_data.get("id")
        self.assertNotEqual(new_id, OLD_ID, "moved record has not been given a new identifier yet")

        old_pattern = _citation_pattern(OLD_ID)
        new_pattern = _citation_pattern(new_id)

        tags_by_file: dict[Path, list[str]] = {}
        for path in _iter_scan_files(UNIT_TESTS_ROOT, {".py"}):
            try:
                with open(path, encoding="utf-8") as fh:
                    for line in fh:
                        match = _COVERS_TAG_PATTERN.search(line)
                        if match:
                            tags_by_file.setdefault(path, []).append(match.group(1))
            except OSError:
                continue

        all_tags = [(path, tag) for path, tags in tags_by_file.items() for tag in tags]
        old_tags = [(p, t) for p, t in all_tags if old_pattern.search(t)]
        new_tags = [(p, t) for p, t in all_tags if new_pattern.search(t)]

        self.assertEqual(
            old_tags,
            [],
            f"found {len(old_tags)} coverage tag(s) still naming {OLD_ID} -- every one of the "
            f"fifteen must be repointed to {new_id}: {old_tags}",
        )
        self.assertEqual(
            len(new_tags),
            15,
            f"expected 15 coverage tags naming {new_id} (9 in "
            "test_ge_119_contract_shrinking_rename_aware.py + 6 in "
            f"test_contract_shrinking_ignores_mentions.py), found {len(new_tags)}: {new_tags}",
        )

        per_file_counts: dict[str, int] = {}
        for path, _tag in new_tags:
            per_file_counts[path.name] = per_file_counts.get(path.name, 0) + 1
        self.assertEqual(
            per_file_counts.get("test_ge_119_contract_shrinking_rename_aware.py", 0),
            9,
            "expected 9 repointed tags in test_ge_119_contract_shrinking_rename_aware.py, "
            f"actual distribution: {per_file_counts}",
        )
        self.assertEqual(
            per_file_counts.get("test_contract_shrinking_ignores_mentions.py", 0),
            6,
            "expected 6 repointed tags in test_contract_shrinking_ignores_mentions.py -- this is "
            f"the module a filename-based search misses; actual distribution: {per_file_counts}",
        )

        id_map = _build_ac_id_map()
        self.assertEqual(
            len(id_map.get(new_id, [])),
            1,
            f"{new_id} does not resolve to exactly one AC record: {id_map.get(new_id, [])}",
        )

    def test_no_citation_of_either_identifier_resolves_to_zero_or_many(self):
        # covers: GE-120e-1
        """Gherkin Then: no citation of either identifier anywhere in the
        repository resolves to zero records or to more than one.

        This is the core assertion the AC's own Coverage note calls out:
        "Asserting only that the file was renamed does not cover it -- the
        references are where a renumbering does its damage." Every
        occurrence of GE-119 or its moved successor, anywhere in the
        repository (excluding .git/, node_modules/, __pycache__/, and
        .leafcutter/ -- the last being a deployed copy that would double-
        count every citation), must name an identifier that the
        whole-collection uniqueness pass resolves to exactly one record.
        """
        _, moved_data = _find_moved_record()
        new_id = moved_data.get("id")
        self.assertNotEqual(new_id, OLD_ID, "moved record has not been given a new identifier yet")

        id_map = _build_ac_id_map()
        old_pattern = _citation_pattern(OLD_ID)
        new_pattern = _citation_pattern(new_id)

        bad_citations: list[str] = []
        for path in _iter_scan_files(REPO_ROOT):
            try:
                with open(path, encoding="utf-8", errors="ignore") as fh:
                    lines = fh.readlines()
            except OSError:
                continue
            for lineno, line in enumerate(lines, 1):
                for identifier, pattern in ((OLD_ID, old_pattern), (new_id, new_pattern)):
                    if pattern.search(line):
                        count = len(id_map.get(identifier, []))
                        if count != 1:
                            bad_citations.append(
                                f"{path.relative_to(REPO_ROOT)}:{lineno} cites {identifier!r} "
                                f"which resolves to {count} record(s)"
                            )

        self.assertEqual(
            bad_citations,
            [],
            "every citation of GE-119 or its moved successor must resolve to exactly one AC "
            f"record; found {len(bad_citations)} that do not:\n" + "\n".join(bad_citations),
        )

    def test_dated_historical_records_are_not_repointed(self):
        # covers: GE-120e-1
        """Gherkin Then: each remaining citation of "GE-119" in a dated
        historical record either genuinely refers to the goal record, or
        states the identifier the moved record now carries -- so a blanket
        search-and-replace fails this test.

        Checks three dated/historical artifacts by name (these are the
        specific ones the ticket's Context section names as must-not-be-
        blanket-rewritten, not a general scan): the changelog that means the
        goal record must stay byte-identical; the changelog that means the
        moved record must keep its ORIGINAL citation untouched (verified as
        a substring of the repaired file, so appending a clarifying note is
        allowed but rewriting the citation is not) and gain a clarifying
        statement naming the new identifier; and the bare "GE-119" in
        ACS-1200a-2.yaml, which means the goal record, must stay untouched.
        """
        _, moved_data = _find_moved_record()
        new_id = moved_data.get("id")
        self.assertNotEqual(new_id, OLD_ID, "moved record has not been given a new identifier yet")

        goal_relative = CHANGELOG_MEANS_GOAL.relative_to(REPO_ROOT).as_posix()
        baseline_goal = _git_show(BASELINE_COMMIT, goal_relative)
        current_goal = CHANGELOG_MEANS_GOAL.read_bytes()
        self.assertEqual(
            current_goal,
            baseline_goal,
            f"{CHANGELOG_MEANS_GOAL} legitimately cites the goal record and must be byte-identical "
            "to its pre-repair content",
        )

        moved_relative = CHANGELOG_MEANS_MOVED.relative_to(REPO_ROOT).as_posix()
        baseline_moved_text = _git_show(BASELINE_COMMIT, moved_relative).decode("utf-8")
        current_moved_text = CHANGELOG_MEANS_MOVED.read_text(encoding="utf-8")
        self.assertIn(
            baseline_moved_text,
            current_moved_text,
            f"{CHANGELOG_MEANS_MOVED}'s original {OLD_ID} citation was rewritten instead of "
            "receiving a clarifying note -- a blanket search-and-replace fails this assertion "
            "because the ORIGINAL text must remain a substring of the repaired file",
        )
        new_pattern = _citation_pattern(new_id)
        self.assertTrue(
            bool(new_pattern.search(current_moved_text)),
            f"{CHANGELOG_MEANS_MOVED} does not carry a clarifying statement naming {new_id}",
        )

        acs_relative = ACS_BARE_CITATION_FILE.relative_to(REPO_ROOT).as_posix()
        baseline_acs = _git_show(BASELINE_COMMIT, acs_relative)
        current_acs = ACS_BARE_CITATION_FILE.read_bytes()
        self.assertEqual(
            current_acs,
            baseline_acs,
            f'{ACS_BARE_CITATION_FILE} cites the goal record ("exactly the failure GE-119 exists '
            'to close") and must be byte-identical to its pre-repair content',
        )


if __name__ == "__main__":
    unittest.main()
