"""
MODULE: unit_tests/commit_guardian/_ge_127e_2_fixture.py
COVERS: GE-127e-2 (shared fixture module -- carries no tests of its own)

GOAL: Fixture builders and extraction helpers for GE-127e-2's four
    invariants -- two different oversized files get different advice, a
    rearrangement at constant length moves the advice, a byte-identical copy
    at a different path gets identical advice, and the mandatory three-way
    mutation proof that the first two arms are load-bearing while the third
    is a genuine, independent control.

WHY A SEPARATE FIXTURE MODULE, REUSING RATHER THAN DUPLICATING
    ``_ge_127e_1_fixture.py``. That module already owns the git/subprocess
    plumbing (``run_check``, ``run_check_via_hook``, ``build_into``,
    ``fresh_repo_dir``, ``init_repo``, ``commit_all``, ``stage_all``) and the
    single-file printed-block extractors (``extract_named_portions``,
    ``extract_sides``, ``extract_quoted_length_and_limit``,
    ``has_no_division_marker``) this AC's arms need per-file. This module is
    imported alongside it (never copy-pasted) and adds only what GE-127e-2
    needs on top: (a) fixture content builders whose PARTS differ between
    two files while their TOTAL measured length is held equal, so the
    mutation proof below has real teeth; (b) a per-file output SPLITTER,
    because ``_ge_127e_1_fixture``'s extractors were built for a single
    refused file and read the whole combined output as one bag of
    part/side entries -- when two files are refused in the same run, that
    bag merges both files' entries, which is exactly wrong for an AC about
    telling the two files apart; (c) a DISPOSABLE, git-repo-local copy of
    the production commit_guardian modules (mirroring
    ``_ge_127d_2_fixture.py``'s ``copy_production_modules`` /
    ``mutate_rule_to_also_discard_hash_comments`` shape) so the mandatory
    mutation can be applied and run WITHOUT ever touching
    ``templates/scripts/commit_guardian/`` itself.

THE MUTATION, STATED ONCE HERE AND REUSED VERBATIM BY EVERY CALLER. Per the
    BA's injection (carried through from the ticket's Test Requirements):
    derive the named parts and the named division from the refused file's
    KIND and its MEASURED LENGTH alone, ignoring its content entirely -- a
    fixed table of part names per covered kind, apportioned across the
    measured length. ``mutate_description_to_kind_and_length_only`` applies
    this to a disposable copy's own ``_file_description.py`` by APPENDING a
    redefinition of ``describe_file`` (never editing the original text in
    place) -- ``check_file_size.py``'s ``from _file_description import
    describe_file`` binds the name only once the target module has finished
    executing top to bottom, so the appended definition is the one that
    reaches every caller, the same "reassign after full module exec" shape
    ``_ge_127d_2_fixture.mutate_rule_to_also_discard_hash_comments`` already
    established for a sibling module in this same directory.

WHY THE FIXTURES HOLD KIND AND TOTAL LENGTH EQUAL WHERE THE AC DOES NOT
    STRICTLY REQUIRE IT. The two-different-files arm's Gherkin only requires
    "different content"; it does not require equal length. This module's
    ``stage_two_different_files`` deliberately gives both files the SAME
    extension and the SAME total measured length anyway, because that is
    the one construction under which the mandatory mutation
    (kind+length-only) can be cleanly falsified: if the two files differed
    in length, a kind+length-only implementation would ALSO print
    different-looking advice for them (different portions, from the
    different quoted lengths) without ever reading content, and the arm
    would not distinguish a genuine content-derivation from that cheaper
    imposter. Same kind, same length, different content is the sharpest
    version of this arm, and it subsumes the weaker one the Gherkin states.

DECISION HISTORY
- 2026-09-23 [GE-127e-2/test-writer]: Initial authoring.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127e_1_fixture as e1  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"

_PYTHON = sys.executable
_SUBPROCESS_TIMEOUT_SECONDS = 60

# Re-exported for callers that want the shared plumbing under one import.
fresh_repo_dir = e1.fresh_repo_dir
init_repo = e1.init_repo
commit_all = e1.commit_all
stage_all = e1.stage_all
run_check = e1.run_check
run_check_via_hook = e1.run_check_via_hook
build_into = e1.build_into
extract_named_portions = e1.extract_named_portions
extract_sides = e1.extract_sides
extract_quoted_length_and_limit = e1.extract_quoted_length_and_limit
has_no_division_marker = e1.has_no_division_marker
make_part_source = e1.make_part_source
make_multi_part_fixture = e1.make_multi_part_fixture

# ---------------------------------------------------------------------------
# Fixture content -- same kind, same TOTAL measured length, different parts.
# ---------------------------------------------------------------------------

_TWO_FILES_A_PARTS = [("alpha_one", 150), ("alpha_two", 140), ("alpha_three", 150)]
_TWO_FILES_B_PARTS = [("beta_one", 200), ("beta_two", 240)]

_REARRANGE_INITIAL_PARTS = [("north_wing", 150), ("south_wing", 140), ("east_wing", 150)]
_REARRANGE_SECOND_PARTS = [("unified_block", 220), ("annex_block", 220)]

_COPY_PARTS = [("solo_gamma", 150), ("solo_delta", 140), ("solo_epsilon", 150)]


def stage_two_different_files(root: Path) -> tuple[str, str]:
    """Establish, then stage over their limit, two same-kind same-length files.

    Returns:
        (alpha_content, beta_content) -- the two files' full staged text.
    """
    alpha = root / "alpha.py"
    beta = root / "beta.py"
    alpha.write_text(make_part_source("placeholder_a", 10) + "\n", encoding="utf-8")
    beta.write_text(make_part_source("placeholder_b", 10) + "\n", encoding="utf-8")
    commit_all(root, "establish under-limit files")

    alpha_content = make_multi_part_fixture(_TWO_FILES_A_PARTS)
    beta_content = make_multi_part_fixture(_TWO_FILES_B_PARTS)
    alpha.write_text(alpha_content, encoding="utf-8")
    beta.write_text(beta_content, encoding="utf-8")
    stage_all(root)
    return alpha_content, beta_content


def stage_rearrangement_first(root: Path) -> tuple[Path, str]:
    """Establish an under-limit file, then stage its FIRST oversized form.

    Returns:
        (target_path, first_content).
    """
    target = root / "rearrange.py"
    target.write_text(make_part_source("placeholder", 10) + "\n", encoding="utf-8")
    commit_all(root, "establish under-limit file")

    content = make_multi_part_fixture(_REARRANGE_INITIAL_PARTS)
    target.write_text(content, encoding="utf-8")
    stage_all(root)
    return target, content


def stage_rearrangement_second(root: Path, target: Path) -> str:
    """Rewrite *target* to its SECOND form: different parts, equal total length."""
    content = make_multi_part_fixture(_REARRANGE_SECOND_PARTS)
    target.write_text(content, encoding="utf-8")
    stage_all(root)
    return content


def stage_byte_identical_copy(root: Path) -> tuple[str, Path, Path]:
    """Establish, then stage, one oversized file and a byte-identical copy
    of it at a second, differently-named, differently-nested path.

    Returns:
        (content, original_path, copy_path).
    """
    original = root / "original.py"
    copy_path = root / "nested_dir" / "copy.py"
    copy_path.parent.mkdir(parents=True, exist_ok=True)
    original.write_text(make_part_source("placeholder_o", 10) + "\n", encoding="utf-8")
    copy_path.write_text(make_part_source("placeholder_c", 10) + "\n", encoding="utf-8")
    commit_all(root, "establish under-limit files")

    content = make_multi_part_fixture(_COPY_PARTS)
    original.write_text(content, encoding="utf-8")
    copy_path.write_bytes(original.read_bytes())
    stage_all(root)
    return content, original, copy_path


# ---------------------------------------------------------------------------
# Per-file output splitter -- two refused files in ONE run's combined output.
# ---------------------------------------------------------------------------

_FILE_TOO_LARGE_BLOCK_RE = re.compile(
    r"❌ FILE TOO LARGE:\s*\n\s*(?P<filepath>\S+)\n(?P<body>.*?)(?=❌ FILE TOO LARGE:|\Z)",
    re.DOTALL,
)


def extract_per_file_too_large_blocks(output: str) -> dict[str, str]:
    """Split *output* into one block of text per over-limit refused file.

    Returns:
        Mapping of the printed filepath to that file's OWN slice of the
        combined output, so a caller can read parts/division PER FILE
        rather than seeing every refused file's entries merged into one
        bag -- which is what ``_ge_127e_1_fixture``'s single-file
        extractors would otherwise do if handed the combined output of a
        two-file run directly.
    """
    return {m.group("filepath").strip(): m.group("body") for m in _FILE_TOO_LARGE_BLOCK_RE.finditer(output)}


def block_for_suffix(blocks: dict[str, str], suffix: str) -> str:
    """Return the one block whose printed path ends with *suffix*.

    Raises:
        AssertionError: zero or more than one block matches -- a fixture
            sanity failure, never silently picking one.
    """
    matches = [body for path, body in blocks.items() if path.endswith(suffix)]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one block ending {suffix!r}, found {len(matches)} in {list(blocks)!r}")
    return matches[0]


# ---------------------------------------------------------------------------
# Disposable, git-repo-local copy of the production modules + the mutation.
# ---------------------------------------------------------------------------

_PRODUCTION_MODULES: tuple[str, ...] = (
    "check_file_size.py",
    "_file_size_ratchet.py",
    "_file_description.py",
    "_resolve_root.py",
    "config.py",
    "run_hook.py",
    "check_outcome.py",
    "commit_guardian.json",
)


def build_disposable_commit_guardian(root: Path) -> Path:
    """Copy the REAL production modules into *root*/scripts/commit_guardian.

    *root* must be (or become) a git repository; the returned directory's
    ``check_file_size.py`` is invoked with ``cwd=root`` -- the same
    layout-and-invocation shape ``_ge_127d_2_fixture.py``'s
    ``build_fixture_tree`` / ``run_check_file_size`` already establish and
    rely on in this same test package. The real
    ``templates/scripts/commit_guardian/`` tree is only ever READ here,
    never written to.
    """
    dest = root / "scripts" / "commit_guardian"
    dest.mkdir(parents=True, exist_ok=True)
    for name in _PRODUCTION_MODULES:
        shutil.copy2(_COMMIT_GUARDIAN_DIR / name, dest / name)
    return dest


def mutate_description_to_kind_and_length_only(dest: Path) -> None:
    """Apply the BA's injection to *dest*'s OWN copy of ``_file_description.py``.

    Appends a redefinition of ``describe_file`` that consults only the
    refused file's extension and its already-measured ``quoted_length`` --
    never its content -- via a fixed per-kind table of part names,
    apportioned evenly across the measured length. Because
    ``check_file_size.py`` imports ``describe_file`` via ``from
    _file_description import describe_file`` -- which binds the name only
    once this module has finished executing top to bottom -- the appended
    definition below is the one every caller receives. Only ever call this
    against a path produced by ``build_disposable_commit_guardian``; the
    real ``templates/scripts/commit_guardian/_file_description.py`` is never
    touched by this function.
    """
    path = dest / "_file_description.py"
    original = path.read_text(encoding="utf-8")
    override = (
        "\n\n"
        "# TEST-INJECTED MUTATION (GE-127e-2/test-writer): derive the named\n"
        "# parts and the named division from the refused file's KIND and its\n"
        "# MEASURED LENGTH alone, ignoring its content entirely -- a fixed\n"
        "# per-kind table of part names, apportioned across quoted_length.\n"
        "_KIND_ONLY_PART_NAMES = {\n"
        '    ".py": ["header_region", "body_region", "footer_region"],\n'
        '    ".sql": ["schema_prelude", "object_definitions", "trailer_region"],\n'
        "}\n"
        "\n\n"
        "def describe_file(filepath, content, quoted_length):  # noqa: F811 -- intentional test override\n"
        "    ext = Path(filepath).suffix.lower()\n"
        '    names = _KIND_ONLY_PART_NAMES.get(ext, ["region_a", "region_b", "region_c"])\n'
        "    count = len(names)\n"
        "    base_portion = quoted_length // count\n"
        "    remaining = quoted_length\n"
        "    parts = []\n"
        "    for index, name in enumerate(names):\n"
        "        portion = remaining if index == count - 1 else base_portion\n"
        "        parts.append(DescribedPart(name=name, portion=portion))\n"
        "        remaining -= portion\n"
        "    if len(parts) == 1:\n"
        "        return FileDescription(parts=parts, single_part_name=parts[0].name)\n"
        "    midpoint = count // 2\n"
        "    left, right = parts[:midpoint], parts[midpoint:]\n"
        "    side_a = ([part.name for part in left], sum(part.portion for part in left))\n"
        "    side_b = ([part.name for part in right], sum(part.portion for part in right))\n"
        "    return FileDescription(parts=parts, side_a=side_a, side_b=side_b)\n"
    )
    path.write_text(original + override, encoding="utf-8")


def run_check_in(root: Path) -> subprocess.CompletedProcess:
    """Invoke *root*'s own disposable ``scripts/commit_guardian/check_file_size.py``."""
    script = root / "scripts" / "commit_guardian" / "check_file_size.py"
    return subprocess.run(
        [_PYTHON, str(script)],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def fresh_disposable_repo(prefix: str) -> Path:
    """Create a fresh temp git repo directory (caller owns cleanup)."""
    root = Path(tempfile.mkdtemp(prefix=prefix))
    init_repo(root)
    return root
