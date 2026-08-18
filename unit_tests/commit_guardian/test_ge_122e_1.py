"""
MODULE: test_ge_122e_1
GOAL: Assert the POST-MERGE truth of the GE-119 identifier collision and its
    joint resolution. GE-119 was independently claimed by two unrelated
    records -- a goal-level tree ("Trust that a green check actually checked
    something") and a parentless detail-level record about the
    contract-shrinking guard -- and was resolved from BOTH sides at once: this
    branch moved the parentless record to GE-111f (already landed before this
    module was rewritten), and a separate, concurrently-authored change on
    origin/main (PR #453) independently renamed the goal-level tree itself
    from GE-119 to GE-120. After merging origin/main, GE-119 is a RETIRED
    identifier claimed by no record, and this tree's own former GE-120
    "numbers mean one thing" tree -- which collided head-on with the
    incoming GE-120 -- was renumbered to GE-122.
BUSINESS CONTEXT: See
    docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122e-1.yaml
    and tickets/00_inbox/TICKET-20260817-GE-122e-1.md. This module supersedes
    unit_tests/commit_guardian/test_ge_120e_1.py (git mv'd to this path/name)
    -- see the git history of this file for the original, pre-merge RED-test
    module and its documented authoring rationale. Every assertion below runs
    against the REAL on-disk AC store (docs/acceptance-criteria/), the REAL
    test tree (unit_tests/), the REAL guard source
    (templates/scripts/commit_guardian/check_contract_shrinking.py), and the
    REAL changelogs -- never a synthetic fixture -- for the same reason as
    the original module: the defect this AC exists to prevent (a renumbering
    that silently repoints or orphans a citation) can only be observed on the
    actual artifacts (CLAUDE.md, "Real-artifact behavioral spot-check before
    declaring done").
ARCHITECTURE: The repo root is resolved by walking up from this file's own
    location (never from cwd), matching
    unit_tests/commit_guardian/conftest.py's convention. Both surviving
    records (the goal-level tree and the moved contract-shrinking record) are
    located by an exact, distinctive TITLE match rather than by filename or a
    hardcoded identifier -- for the same reason the original module gave: a
    concurrent mint or a further renumbering must not invalidate these tests.
    The whole-collection uniqueness pass is implemented inline for the same
    performance reason as the original module (a full yaml.safe_load across
    ~3000 files measured ~10s locally; a line-anchored regex on the
    always-unindented top-level ``id:`` key runs in well under a second).

    GOAL-FOLDER BASELINE CHOICE (Task 3, bullet 2): the goal-level tree
    (docs/acceptance-criteria/guardrail-engine/GE-120-green-means-checked/)
    arrived on this branch VIA THE MERGE -- it did not exist on this branch
    before `git merge origin/main` ran, so there is no local pre-merge commit
    to diff it against (the original module's BASELINE_COMMIT technique is
    inapplicable here: that commit predates the merge and simply does not
    contain this folder under this name). A MEANINGFUL baseline IS available,
    however: origin/main itself, which is the one place this folder existed
    before the merge and the source of truth this reconciliation must not
    diverge from. This module therefore CHOSE the `git diff origin/main --
    <folder>` form of Task 3's bullet 2 (not the fallback), because it is
    directly obtainable, it is exactly what
    docs/architecture (the ticket's own Definition of Done) checks, and it is
    strictly stronger than a name-and-count check: it catches a
    content-level change to any file in the folder, not just a rename or a
    missing file. It is combined with the fallback's own structural
    assertion (every record in the folder claims a GE-120* id) as a second,
    independent signal, since the two checks fail on different mistakes (a
    content edit vs. an id drift) and neither alone covers both.

    "LIVE" VS. "DATED HISTORICAL" CITATIONS OF THE RETIRED GE-119 (Task 3,
    bullet 3): a repo-wide, unscoped substring scan for "GE-119" would fail
    on dozens of places this reconciliation was explicitly instructed to
    preserve -- this tree's own prose narrating the historical collision
    (every AC record in GE-122-numbers-mean-one-thing/, PROJECT_CONTEXT.md,
    the moved record's own amended_by history in GE-111f.yaml), the two
    dated changelog entries that legitimately describe what was true when
    they were written, this module's own sibling test modules discussing the
    rename, and the guard source's own historical annotation
    ("renumbered from GE-119"). None of those are the failure mode the AC's
    Coverage note is about ("the references are where a renumbering does its
    damage") -- that note is about MACHINE-RESOLVED citations: an `id:`
    declaration, a `# covers:` tag, or a `depends_on:`/`covered_by:` list
    entry that a tool resolves. Those three surfaces are asserted directly
    and exhaustively elsewhere in this module (zero id-declaration claimants
    for the retired identifier; zero coverage-tag citations of it in
    unit_tests/). This module's dedicated
    "LIVE citation" test therefore scopes its scan to the repository MINUS
    the known, accounted-for historical-narrative locations (changelogs/,
    the whole guardrail-engine AC component directory, unit_tests/, and the
    guard source file's own known historical annotation) and asserts ZERO
    remaining hits -- a citation of GE-119 turning up anywhere else in the
    repository (a script, an unrelated doc, a different component's AC) IS a
    live citation and IS a regression this test is designed to catch.

    Do NOT move, rename, or edit any AC YAML, the guard source, the
    changelogs, or the two existing GE-111f test modules from this file --
    it is read-only with respect to all of those; it only reads and asserts.
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
GUARDRAIL_ENGINE_ROOT = AC_STORE_ROOT / "guardrail-engine"

OLD_ID = "GE-119"
GOAL_RECORD_TITLE = "Trust that a green check actually checked something"
MOVED_RECORD_TITLE = "The contract-shrinking guard distinguishes an edited test from a deleted one"
EXPECTED_GOAL_FOLDER_NAME = "GE-120-green-means-checked"

GUARD_SOURCE = REPO_ROOT / "templates" / "scripts" / "commit_guardian" / "check_contract_shrinking.py"
CHANGELOG_MEANS_GOAL = (
    REPO_ROOT
    / "changelogs"
    / "2026-08-17-1204-changelog-pr-445-ge-119-acs-1200-acceptance-criteria-authored-2026-08-17.md"
)
CHANGELOG_MEANS_MOVED = (
    REPO_ROOT / "changelogs" / "2026-08-14-0037-fix-guardian-tell-an-edited-test-from-a-deleted-one-ge-119.md"
)

# Fixed pre-merge baseline commit for the TWO changelogs, which predate and
# are untouched by both this repair and the origin/main merge -- see the
# original module (test_ge_120e_1.py, now this file) for why this specific
# sha was chosen (this branch's HEAD at authoring time, confirmed empty diff
# for the compared files at that time). It is NOT used for the goal folder
# (see module docstring, "GOAL-FOLDER BASELINE CHOICE").
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
    child identifier that merely starts with it (e.g. ``GE-119b`` must not
    match a search for ``GE-119``)."""
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


def _find_record_by_title(title: str, *, exclude: Path | None = None) -> tuple[Path, dict]:
    """Locate an AC record by an exact, distinctive TITLE -- never by
    filename or a hardcoded identifier. Returns (path, parsed_yaml).

    The candidate set is first narrowed with a fast grep (a plain substring
    match on file content), then filtered by parsing each candidate's YAML
    and comparing its actual ``title`` FIELD for exact equality. The grep
    alone is not sufficient: several records in this AC store legitimately
    QUOTE another record's title inside prose (e.g. a rationale explaining
    why a given identifier was rejected as a parent), which is a substring
    hit but not a record whose own title is that string.
    """
    grep = subprocess.run(
        ["grep", "-rlF", "--include=*.yaml", title, str(AC_STORE_ROOT)],
        capture_output=True,
        text=True,
        check=False,
    )
    candidates = [Path(p) for p in grep.stdout.splitlines() if p.strip()]
    if exclude is not None:
        candidates = [p for p in candidates if exclude not in p.parents]
    matches = [(p, _load_yaml(p)) for p in candidates if _load_yaml(p).get("title") == title]
    if len(matches) != 1:
        raise AssertionError(  # noqa: TRY003
            f"expected exactly one AC record whose own title field equals {title!r}, "
            f"found {len(matches)} among {len(candidates)} substring-hit candidates: {[p for p, _ in matches]}"
        )
    return matches[0]


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


def _git_diff_against_ref(ref: str, relative_path: str) -> str:
    result = subprocess.run(
        ["git", "diff", ref, "--", relative_path],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        raise AssertionError(  # noqa: TRY003
            f"git diff {ref} -- {relative_path} failed: {result.stderr}"
        )
    return result.stdout


def _declared_parent_id(data: dict) -> str | None:
    """Return the parent id the record declares.

    Prefers the explicit ``parent`` field and falls back to the first
    ``depends_on`` entry (per docs/reference/ac-schema.md).
    """
    explicit = data.get("parent")
    if explicit:
        return str(explicit).strip()
    depends_on = data.get("depends_on") or []
    if isinstance(depends_on, list) and depends_on:
        return str(depends_on[0]).strip()
    return None


def _find_moved_record() -> tuple[Path, dict]:
    return _find_record_by_title(MOVED_RECORD_TITLE, exclude=GUARDRAIL_ENGINE_ROOT / EXPECTED_GOAL_FOLDER_NAME)


def _find_goal_record() -> tuple[Path, dict]:
    return _find_record_by_title(GOAL_RECORD_TITLE)


class TestGE122e1(unittest.TestCase):
    """Post-merge tests for GE-122e-1 -- see module docstring for full context."""

    def test_retired_identifier_has_zero_claimants(self):
        # covers: GE-122e-1
        """Gherkin Then: no record anywhere in the collection claims
        "GE-119" -- the identifier is RETIRED and must never be reissued.

        Pre-merge (on this branch alone) exactly one record claimed GE-119
        (the goal tree, after this repair's own move of the parentless
        record). Post-merge, origin/main's independent PR #453 renamed that
        same goal tree from GE-119 to GE-120, so the joint, merged truth is
        ZERO claimants -- not one. A repair that left the goal tree claiming
        GE-119 (failing to account for the merge) would fail this assertion.
        """
        id_map = _build_ac_id_map()
        claimants = id_map.get(OLD_ID, [])
        self.assertEqual(
            claimants,
            [],
            f"expected ZERO claimants for the retired {OLD_ID}, found {len(claimants)}: {claimants}",
        )

    def test_moved_record_claims_a_free_identifier_with_a_real_parent(self):
        # covers: GE-122e-1
        """Gherkin Then: the parentless record claims an identifier in the
        same namespace that no other artifact claims and that was not
        previously claimed by any retired artifact, declares a parent that
        exists, and that parent lists it among its children.

        Unaffected by the origin/main merge (that merge touched only the
        goal-level claimant, not this one), so this assertion is unchanged
        from the original module and should already be GREEN.
        """
        path, data = _find_moved_record()
        new_id = data.get("id")
        self.assertNotEqual(
            new_id,
            OLD_ID,
            f"moved record at {path} still claims {OLD_ID} -- it has not been moved to a free identifier",
        )
        # Accept ANY valid id in the guardrail-engine namespace -- root-format
        # or suffix-shaped under a parent (e.g. GE-111f) -- never hardcode the
        # literal chosen id, per the original module's design constraint.
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
            f"{OLD_ID} is forbidden as the new parent regardless of what it currently resolves to",
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

    def test_goal_record_claims_a_new_id_and_its_folder_matches_origin_main(self):
        # covers: GE-122e-1
        """Gherkin Then: the former goal record claims "GE-120", with its
        folder's content identical to origin/main's copy of it -- whatever
        the file count is at merge time (see below; it is NOT the 32 this
        AC's own criteria stated when it was authored).

        BASELINE CHOICE (see module docstring, "GOAL-FOLDER BASELINE
        CHOICE"): this test diffs the folder against origin/main directly
        (`git diff origin/main -- <folder>`), because the folder arrived on
        this branch via the merge and origin/main is the one meaningful
        pre-merge source of truth for it. An empty diff is exactly this
        ticket's own Definition of Done headline check #5. It is combined
        with a structural id-prefix assertion as a second, independent
        signal.

        NO HARDCODED FILE COUNT (found while writing this test): the goal
        folder held 32 files when this AC was authored, but origin/main's
        own further, unrelated work on that tree independently grew it to
        43 files before this branch merged -- a hardcoded count here would
        be exactly the kind of stale-measurement defect this AC's own
        history (see amended_by) has already been bitten by once. The
        content-identity diff against origin/main is count-agnostic and is
        the meaningful, durable assertion; the file count is not asserted
        as a fixed number anywhere in this test.
        """
        path, data = _find_goal_record()
        goal_id = data.get("id")
        self.assertNotEqual(
            goal_id,
            OLD_ID,
            f"goal record at {path} still claims the retired {OLD_ID}",
        )
        folder = path.parent
        self.assertEqual(
            folder.name,
            EXPECTED_GOAL_FOLDER_NAME,
            f"expected the goal record's folder to be named {EXPECTED_GOAL_FOLDER_NAME!r}, got {folder.name!r}",
        )

        files = sorted(p for p in folder.rglob("*") if p.is_file())
        self.assertGreater(
            len(files),
            0,
            f"expected at least one file under {folder}, found none",
        )
        for file_path in files:
            file_data = _load_yaml(file_path) if file_path.suffix == ".yaml" else None
            if file_data is not None:
                self.assertTrue(
                    str(file_data.get("id", "")).startswith("GE-120"),
                    f"{file_path} is under the goal folder but its id {file_data.get('id')!r} "
                    "does not start with GE-120",
                )

        relative = folder.relative_to(REPO_ROOT).as_posix()
        diff_output = _git_diff_against_ref("origin/main", relative)
        self.assertEqual(
            diff_output,
            "",
            f"the goal record's folder {folder} differs from origin/main -- this reconciliation "
            f"must not modify main's tree:\n{diff_output}",
        )

    def test_every_coverage_tag_resolves_to_exactly_one_record(self):
        # covers: GE-122e-1
        """Gherkin Then: every one of the fifteen coverage tags, in both
        modules, names the identifier the moved record now claims, so each
        tag resolves to exactly one record.

        Unaffected by the origin/main merge. Tags are discovered by SCANNING
        every .py file under unit_tests/, never by opening known filenames
        or hardcoding the new id -- per the original module's design
        constraint, both the BA and the IT PO independently missed six of
        the fifteen tags by searching by filename.
        """
        _, moved_data = _find_moved_record()
        new_id = moved_data.get("id")
        self.assertNotEqual(new_id, OLD_ID, "moved record has not been given a new identifier")

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
            f"found {len(old_tags)} coverage tag(s) still naming the retired {OLD_ID}: {old_tags}",
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
            f"expected 9 tags in test_ge_119_contract_shrinking_rename_aware.py: {per_file_counts}",
        )
        self.assertEqual(
            per_file_counts.get("test_contract_shrinking_ignores_mentions.py", 0),
            6,
            f"expected 6 tags in test_contract_shrinking_ignores_mentions.py: {per_file_counts}",
        )

        id_map = _build_ac_id_map()
        self.assertEqual(
            len(id_map.get(new_id, [])),
            1,
            f"{new_id} does not resolve to exactly one AC record: {id_map.get(new_id, [])}",
        )

    def test_no_live_citation_of_the_retired_identifier_remains(self):
        # covers: GE-122e-1
        """Gherkin Then: no LIVE citation -- any citation other than a dated
        historical record -- anywhere in the repository still names
        "GE-119".

        See module docstring ("LIVE VS. DATED HISTORICAL") for why this scan
        excludes changelogs/, tickets/ (a ticket body is a dated
        implementation record in exactly the same sense a changelog entry
        is -- see e.g. this AC's own ticket, which narrates the pre-repair
        and pre-merge state throughout), the whole guardrail-engine AC
        component directory, unit_tests/, and the guard source's own known
        historical annotation: those are the accounted-for locations this
        reconciliation was explicitly instructed to preserve, and the
        machine-resolved surfaces within them (id-declarations, coverage-tag
        citations) are asserted exhaustively by the other tests in this
        module. A citation of GE-119 turning up ANYWHERE else is a live
        citation and a real regression.
        """
        old_pattern = _citation_pattern(OLD_ID)
        changelogs_dir = REPO_ROOT / "changelogs"
        tickets_dir = REPO_ROOT / "tickets"

        live_hits: list[str] = []
        for path in _iter_scan_files(REPO_ROOT):
            if changelogs_dir in path.parents:
                continue
            if tickets_dir in path.parents:
                continue
            if GUARDRAIL_ENGINE_ROOT in path.parents or path.parent == GUARDRAIL_ENGINE_ROOT:
                continue
            if UNIT_TESTS_ROOT in path.parents:
                continue
            if path == GUARD_SOURCE:
                continue
            try:
                with open(path, encoding="utf-8", errors="ignore") as fh:
                    for lineno, line in enumerate(fh, 1):
                        if old_pattern.search(line):
                            live_hits.append(f"{path.relative_to(REPO_ROOT)}:{lineno}: {line.strip()}")
            except OSError:
                continue

        self.assertEqual(
            live_hits,
            [],
            f"found {len(live_hits)} LIVE citation(s) of the retired {OLD_ID} outside the known "
            f"historical-narrative locations:\n" + "\n".join(live_hits),
        )

    def test_dated_historical_records_are_not_repointed(self):
        # covers: GE-122e-1
        """Gherkin Then: a dated historical record MAY still cite the
        retired "GE-119", provided it also states the identifier the work
        now carries; rewriting a dated record's citation outright would make
        it claim something that did not happen, so the required fix is a
        clarifying addition, never a rewrite.

        Checks the two changelogs the AC's own Given clause names: the one
        meaning the goal record must stay byte-identical (it is untouched by
        both this repair and the origin/main merge); the one meaning the
        moved record must keep its ORIGINAL "GE-119" citation as a substring
        (a blanket search-and-replace would remove it) while also naming the
        new identifier.
        """
        _, moved_data = _find_moved_record()
        new_id = moved_data.get("id")
        self.assertNotEqual(new_id, OLD_ID, "moved record has not been given a new identifier")

        goal_relative = CHANGELOG_MEANS_GOAL.relative_to(REPO_ROOT).as_posix()
        baseline_goal = _git_show(BASELINE_COMMIT, goal_relative)
        current_goal = CHANGELOG_MEANS_GOAL.read_bytes()
        self.assertEqual(
            current_goal,
            baseline_goal,
            f"{CHANGELOG_MEANS_GOAL} legitimately cites the goal record as it was named when this "
            "changelog was written and must be byte-identical to its pre-repair content",
        )

        moved_relative = CHANGELOG_MEANS_MOVED.relative_to(REPO_ROOT).as_posix()
        baseline_moved_text = _git_show(BASELINE_COMMIT, moved_relative).decode("utf-8")
        current_moved_text = CHANGELOG_MEANS_MOVED.read_text(encoding="utf-8")
        self.assertIn(
            baseline_moved_text,
            current_moved_text,
            f"{CHANGELOG_MEANS_MOVED}'s original {OLD_ID} citation was rewritten instead of "
            "receiving a clarifying note",
        )
        new_pattern = _citation_pattern(new_id)
        self.assertTrue(
            bool(new_pattern.search(current_moved_text)),
            f"{CHANGELOG_MEANS_MOVED} does not carry a clarifying statement naming {new_id}",
        )


if __name__ == "__main__":
    unittest.main()
