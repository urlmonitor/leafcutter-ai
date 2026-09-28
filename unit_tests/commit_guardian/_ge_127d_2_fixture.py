"""
MODULE: unit_tests/commit_guardian/_ge_127d_2_fixture.py
COVERS: GE-127d-2 (shared fixture module -- carries no tests of its own)

GOAL: Build REAL, isolated fixture repos for check_file_size.py's own
    refusal outcome -- the length it quotes, the limit it compares against,
    and (not yet implemented) a statement of what the quoted number measures
    -- and provide an INDEPENDENT (not production-imported) re-derivation
    engine so a test can prove the quoted number is reproducible from
    whatever the standard publishes, rather than asserting a hard-coded
    literal.

TEST-WRITER DESIGN DECISIONS (none of these are AC-pinned; python-coder must
    honor them the same way check_file_size_rule_parity.py's DISAGREEMENT /
    "Compared N surface(s)" vocabulary, pinned by GE-127d-1's own test-writer,
    was honored verbatim):

    1. WHERE "PUBLISHED" LIVES FOR THIS TEST SUITE: the refusal's own printed
       output, on the ``   Measures: <description>`` line (MEASURES_PREFIX)
       that ``_print_too_large_file`` must add immediately describing what
       the quoted length counts. This is genuinely "published" in the AC's
       sense -- every author who trips the gate reads it, it is regenerated
       fresh on every run from whatever rule is actually in force, and (per
       the it_requirements' own instruction to derive the statement FROM the
       measurement function rather than maintain it beside it) it is the one
       surface that CANNOT drift from the enforced rule without the
       implementation choosing to hardcode it -- exactly the injection this
       ticket's test_rationale names. README.md / commit_guardian.json
       updates remain documentation-expert's own deliverable and are not
       mechanically pinned here.
    2. THE TWO DISCARD MARKERS the description must name, verbatim substrings
       (case-insensitive), for the CURRENT rule in force: "triple-quoted" and
       "block comment". ``parse_discard_categories`` reads these out of
       whatever text is on the Measures line; a rule change that adds or
       drops a discard category must change which markers appear.
    3. THE ASYMMETRY GUIDANCE the refusal's dividing advice must state,
       pinned verbatim as HELPS_MARKER / NO_HELP_MARKER, replacing the
       existing FORBIDDEN_OLD_SENTENCE that forbids both actions in one
       breath without distinguishing them.
    4. THE INDEPENDENT RE-DERIVATION ENGINE (``independent_count_content_lines``)
       is coded here, in the test file, with its OWN compiled regexes --
       never by importing ``_file_size_ratchet.count_content_lines`` -- so
       equality against the gate's own quoted number is a genuine
       reproducibility proof, not a tautology. It is driven entirely by the
       CATEGORY SET parsed from the published Measures line, so it is
       exactly as informed as an author reading that line would be: today,
       with no Measures line at all, the parsed category set is empty and
       the derived count is the file's raw physical line count -- which
       diverges from the real quoted length the moment a fixture file
       contains a discarded region, which is deliberate and is this AC's
       RED baseline.

       IMPLEMENTS THE PUBLISHED RULE, NOT THE ENFORCED ONE (2026-09-22
       correction): "discarded" means the region contributes ZERO lines,
       trailing newline included -- the region and the line it occupied are
       both gone. A bare non-greedy substitution between a region's opening
       and closing delimiters (this engine's ORIGINAL shape, and
       production's ``count_content_lines`` shape, unchanged) strips the
       delimited span but leaves the newline that followed its closing
       delimiter behind as a phantom blank line, so every stripped region
       overcounts by exactly one line -- confirmed by probe (1 docstring:
       +1 to +3 depending on file; scales with the number of stripped
       regions, e.g. 25 functions each carrying one: overcount 27). This
       engine now consumes that trailing newline (an optional newline
       immediately after each closing delimiter) for BOTH quote styles and
       the block-comment category, so a file whose only difference from a
       docstring-free twin is the presence of that docstring counts
       identically to its twin -- the asymmetry descriptor
       (test_ge_127d_2_the_asymmetry_between_removable_and_non_removable_content_is_legible_from_the_outcome)
       requires exactly this and is this engine's own adversarial check.
       ``count_content_lines`` in production still carries the ORIGINAL
       (overcounting) shape -- that is python-coder's fix, not this ticket's
       -- so from this change forward, every existing descriptor that
       asserts production's quoted length equals this engine's rederivation
       over a file containing a discarded region is expected to go RED
       until production is corrected: that is the correct, intended
       consequence of encoding the rule AS PUBLISHED rather than as
       currently implemented, not a regression in this fixture.
    5. "CHANGING THE RULE IN FORCE" (test_spec's seam descriptor) is done by
       ``mutate_rule_to_also_discard_hash_comments``, which REASSIGNS the
       module-level ``count_content_lines`` name in the fixture's OWN COPY
       of ``_file_size_ratchet.py`` (appended, never edited in place). Every
       existing caller in that module (``measure_current_length``,
       ``get_previous_length``) resolves ``count_content_lines`` as a module
       global at CALL time, not at def time, so this reassignment changes
       their behaviour without needing to know or guess python-coder's
       eventual internal structure for the published-statement generator.
       This only touches the fixture's disposable copy; the real,
       pinned-by-this-AC's-own-implementation-notes rule in
       templates/scripts/commit_guardian/ is never touched.

DECISION HISTORY
- 2026-09-23 [GE-127d-2/test-writer, REWORK -- pr-reviewer H-1]: pr-reviewer
  found the "grew" verdict (GE-127b-1's ratchet-growth refusal,
  ``_print_grown_file``) structurally unreachable by every existing fixture
  here, because ``build_fixture_tree``/``write_and_stage`` never commit
  anything -- ``resolve_head_covered_paths`` always sees empty history, so
  ``_classify_file`` can only ever return "too_large", never "grew". Added
  ``commit_bypassing_hook`` (a plain, unintercepted ``git commit`` used ONLY
  before ``install_precommit()`` is called, to land an already-oversized
  file at HEAD for setup) plus three grown-file-specific parsers
  (``parse_grown_previous_and_new_length``, ``parse_permitted_length``) that
  read the "Previous length:" / "New length:" / "Limit:" labels
  independently of ``_LINES_LIMIT_RE``'s too-large-only shape, since
  ``_print_grown_file`` is not required to reuse that exact sentence. The
  new descriptor itself
  (``test_ge_127d_2_a_grown_already_oversized_file_states_the_new_length_the_permitted_length_and_what_is_measured``,
  in test_ge_127d_2.py) drives the "grew" verdict via a REAL ordinary commit
  through the REAL installed hook, per this AC's own reachability
  discipline -- not a direct ``run_check_file_size`` call, since the point
  under test is that this second refusal path is reachable at all.
- 2026-09-22 [GE-127d-2/test-writer]: Initial authoring.
- 2026-09-22 [GE-127d-2/test-writer, correction]: python-coder halted on
  test_ge_127d_2_the_asymmetry_between_removable_and_non_removable_content_is_legible_from_the_outcome
  (7/8 green) and diagnosed the cause as specific to a docstring at file
  position 0 -- that scoping was wrong. The real cause: this engine's
  ``re.sub`` patterns stripped each discarded region but never consumed the
  newline immediately following its closing delimiter, so every stripped
  region left a phantom blank line behind, independent of file position
  (probed: overcount scales with the number of stripped regions, e.g. 25
  docstring-bearing functions overcount by 27). Corrected
  ``independent_count_content_lines``'s three regexes to also consume that
  trailing newline, implementing the published rule ("discarded" = zero
  lines contributed, trailing newline included) rather than the rule as
  currently (mis-)implemented in production's own ``count_content_lines``,
  which this record does not touch. Four descriptors that previously agreed
  with production's buggy count on a file containing a discarded region
  (test_ge_127d_2_a_file_with_discarded_content_lets_the_author_reconcile_the_two_quantities,
  test_ge_127d_2_applying_the_published_rule_independently_arrives_at_the_quoted_length,
  test_ge_127d_2_changing_the_rule_in_force_changes_both_what_is_published_and_what_is_quoted,
  test_ge_127d_2_the_deployed_copy_quotes_a_length_reproducible_from_its_deployed_published_rule)
  now correctly disagree with unfixed production and are expected RED,
  joining the asymmetry descriptor, until python-coder corrects
  ``count_content_lines`` itself. No import of the production module was
  introduced; both quote-style regexes and the block-comment regex share
  the identical trailing-newline defect and were all three corrected the
  same way.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_SRC = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"

PYTHON = sys.executable
SUBPROCESS_TIMEOUT_SECONDS = 30
HOOK_COMMIT_TIMEOUT_SECONDS = 180

PRODUCTION_MODULES: tuple[str, ...] = (
    "check_file_size.py",
    "_file_size_ratchet.py",
    "_file_description.py",
    "_resolve_root.py",
    "config.py",
    "run_hook.py",
    "check_outcome.py",
)

MEASURES_PREFIX = "Measures:"
DISCARD_MARKER_TRIPLE_QUOTED = "triple-quoted"
DISCARD_MARKER_BLOCK_COMMENT = "block comment"
# Only ever expected to appear on a Measures line once the rule in force has
# been changed to ALSO discard '#' line comments (see
# ``mutate_rule_to_also_discard_hash_comments``) -- absent from the real,
# unmutated rule, where hash comments are counted, not discarded.
DISCARD_MARKER_HASH_COMMENT = "'#' comments are discarded"

# Pinned dividing-advice vocabulary (test-writer's own design decision, per
# this module's docstring point 3). The exact NAMED MUTATION target for a
# future adversarial review: reverting to FORBIDDEN_OLD_SENTENCE without
# these two markers must turn this test suite's asymmetry descriptor red.
HELPS_MARKER = "blank lines and '#' comments count toward this length and removing them WILL reduce it"
NO_HELP_MARKER = (
    "content inside triple-quoted strings or block comments does NOT count toward "
    "this length and removing it will NOT reduce it"
)
FORBIDDEN_OLD_SENTENCE = "DO NOT simply delete blank lines, comments, or docstrings to bypass this."

_LINES_LIMIT_RE = re.compile(r"Lines:\s*(\d+)\s*\(Limit:\s*(\d+)\)")

# The "grew" refusal (``_print_grown_file``) does not share
# ``_LINES_LIMIT_RE``'s single "Lines: N (Limit: M)" shape -- today it prints
# "Previous length: N lines" and "New length: M lines" on their own separate
# lines, and (per pr-reviewer's H-1 finding, 2026-09-23) states no permitted
# length at all. These three patterns are deliberately independent of
# ``_LINES_LIMIT_RE`` and of each other's exact surrounding prose -- each
# looks only for its own labeled number, anywhere in the block -- so they do
# not pin python-coder to reusing the too-large block's exact sentence, only
# to stating the three numbers this AC requires, each under its own label.
_GROWN_PREVIOUS_LENGTH_RE = re.compile(r"Previous length:\s*(\d+)\s*lines?")
_GROWN_NEW_LENGTH_RE = re.compile(r"New length:\s*(\d+)\s*lines?")
_PERMITTED_LENGTH_RE = re.compile(r"Limit:\s*(\d+)")

# A discarded region contributes ZERO lines -- the region AND the line it
# occupied are both gone -- so each pattern also consumes the single newline
# immediately following its closing delimiter, when one is present. Without
# the trailing `\n?`, `re.sub` strips only the delimited span itself and
# leaves that newline behind as a phantom blank line, overcounting by
# exactly one line per stripped region (see this module's docstring, point
# 4, "IMPLEMENTS THE PUBLISHED RULE, NOT THE ENFORCED ONE"). Re-derived
# independently from the published rule's own wording, not copied from
# production's (still-unfixed) regexes.
_INDEPENDENT_TRIPLE_DOUBLE_RE = re.compile(r'""".*?"""\n?', re.DOTALL)
_INDEPENDENT_TRIPLE_SINGLE_RE = re.compile(r"'''.*?'''\n?", re.DOTALL)
_INDEPENDENT_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/\n?", re.DOTALL)


def run(cmd: list[str], cwd: Path, timeout: int = SUBPROCESS_TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    """Run *cmd* for real in *cwd*, capturing text output, never raising."""
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, check=False)


def git(args: list[str], cwd: Path, timeout: int = SUBPROCESS_TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    """Run a real git command in *cwd*."""
    return run(["git", *args], cwd, timeout=timeout)


def init_repo(root: Path) -> None:
    """Initialize a real git repository with a deterministic identity."""
    git(["init", "-q"], root)
    git(["config", "user.email", "test-writer@example.com"], root)
    git(["config", "user.name", "GE-127d-2 fixture"], root)
    git(["config", "core.autocrlf", "false"], root)


def copy_production_modules(dest: Path) -> None:
    """Copy every module ``check_file_size.py`` needs into *dest*."""
    dest.mkdir(parents=True, exist_ok=True)
    for name in PRODUCTION_MODULES:
        shutil.copy2(_COMMIT_GUARDIAN_SRC / name, dest / name)


def build_fixture_tree(root: Path, *, line_limit: int = 5, checked_extensions: list[str] | None = None) -> Path:
    """Compose a full check-file-size fixture at *root*, git repo included.

    Returns:
        The destination directory, ``<root>/scripts/commit_guardian``.
    """
    dest = root / "scripts" / "commit_guardian"
    copy_production_modules(dest)
    extensions = checked_extensions if checked_extensions is not None else [".py"]
    config = {
        "file_size": {
            "_comment": "GE-127d-2 fixture config.",
            "line_limits": dict.fromkeys(extensions, line_limit),
            "default_limit": line_limit,
            "checked_extensions": extensions,
            "published_rule_surfaces": ["README.md", "commit_guardian.json"],
        }
    }
    (dest / "commit_guardian.json").write_text(json.dumps(config, indent=2), encoding="utf-8")
    (dest / "README.md").write_text("GE-127d-2 fixture placeholder.\n", encoding="utf-8")
    init_repo(root)
    return dest


def write_and_stage(root: Path, relative_path: str, content: str) -> Path:
    """Write *content* to *relative_path* under *root* and ``git add`` it."""
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    git(["add", relative_path], root)
    return path


def run_check_file_size(root: Path) -> subprocess.CompletedProcess:
    """Invoke the fixture's own copy of check_file_size.py directly."""
    return run([PYTHON, str(root / "scripts" / "commit_guardian" / "check_file_size.py")], root)


def combined_output(result: subprocess.CompletedProcess) -> str:
    """Merge stdout+stderr, the same way every caller in this suite reads output."""
    return result.stdout + result.stderr


def parse_lines_and_limit(text: str) -> tuple[int, int] | None:
    """Extract ``(quoted_length, permitted_limit)`` from a refusal's text."""
    match = _LINES_LIMIT_RE.search(text)
    return (int(match.group(1)), int(match.group(2))) if match else None


def parse_grown_previous_and_new_length(text: str) -> tuple[int, int] | None:
    """Extract ``(previous_length, new_length)`` from a "FILE GREW" refusal.

    Both numbers are parsed by their own independent label so a caller can
    tell which one the standard stated without depending on the two
    appearing on one line or in one particular order.
    """
    previous_match = _GROWN_PREVIOUS_LENGTH_RE.search(text)
    new_match = _GROWN_NEW_LENGTH_RE.search(text)
    if not previous_match or not new_match:
        return None
    return int(previous_match.group(1)), int(new_match.group(1))


def parse_permitted_length(text: str) -> int | None:
    """Extract a stated permitted length from any ``Limit: N`` mention.

    Deliberately independent of ``_LINES_LIMIT_RE``'s stricter, single-line
    "Lines: N (Limit: M)" shape, which is specific to the too-large
    refusal's own current presentation. The grown-file refusal is not
    required to repeat that exact sentence -- only to state, somewhere in
    its own block, the permitted length this AC requires. Returns ``None``
    when no such mention exists at all (today's RED state for the "grew"
    path).
    """
    match = _PERMITTED_LENGTH_RE.search(text)
    return int(match.group(1)) if match else None


def extract_measures_line(text: str) -> str | None:
    """Return the first line starting with MEASURES_PREFIX, stripped, or None."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(MEASURES_PREFIX):
            return stripped
    return None


def parse_discard_categories(measures_text: str | None) -> set[str]:
    """Read which discard categories a Measures line claims, by keyword.

    An absent Measures line (today's RED state -- the feature does not exist
    yet) yields an empty set, which is the CORRECT reading an author would
    make of "nothing published": nothing is known to be discarded.
    """
    if not measures_text:
        return set()
    lowered = measures_text.lower()
    categories: set[str] = set()
    if DISCARD_MARKER_TRIPLE_QUOTED in lowered:
        categories.add("triple_quoted")
    if DISCARD_MARKER_BLOCK_COMMENT in lowered:
        categories.add("block_comment")
    if DISCARD_MARKER_HASH_COMMENT.lower() in lowered:
        categories.add("hash_comment")
    return categories


def independent_count_content_lines(content: str, categories: set[str]) -> int:
    """Re-derive a line count from *content*, driven ONLY by *categories*.

    Coded with its own regexes, never by importing the production module,
    so agreement with the gate's own quoted number is a genuine
    reproducibility proof rather than calling the same function twice.
    """
    text = content
    if "triple_quoted" in categories:
        text = _INDEPENDENT_TRIPLE_DOUBLE_RE.sub("", text)
        text = _INDEPENDENT_TRIPLE_SINGLE_RE.sub("", text)
    if "block_comment" in categories:
        text = _INDEPENDENT_BLOCK_COMMENT_RE.sub("", text)
    if "hash_comment" in categories:
        text = "\n".join(ln for ln in text.splitlines() if not ln.strip().startswith("#"))
    return len(text.splitlines())


def python_lines_plain(counted_code_lines: int) -> str:
    """.py content with no triple-quoted or block-comment region at all.

    Every physical line is counted -- the DEGENERATE arm's own fixture.
    """
    return "\n".join(f"value_{i} = {i}" for i in range(counted_code_lines)) + "\n"


def python_lines_with_docstring(counted_code_lines: int, docstring_body_lines: int = 3) -> str:
    """.py content: one discarded module docstring + counted code lines.

    The docstring's OWN internal size never affects the quoted length (the
    whole ``\"\"\"...\"\"\"`` span is stripped as a single unit), so varying
    *docstring_body_lines* changes total physical lines without changing the
    quoted length -- the exact asymmetry this AC is about.
    """
    doc_lines = "\n".join(f"Docstring filler line {i}." for i in range(docstring_body_lines))
    docstring = f'"""\n{doc_lines}\n"""\n'
    code = "\n".join(f"value_{i} = {i}" for i in range(counted_code_lines))
    return f"{docstring}{code}\n"


def python_lines_with_all_categories(
    counted_code_lines: int,
    docstring_body_lines: int = 3,
    hash_comment_lines: int = 2,
    blank_lines: int = 2,
) -> str:
    """.py content combining a discarded docstring with COUNTED hash-comment
    and blank lines -- for the removable-versus-non-removable asymmetry.
    """
    doc_lines = "\n".join(f"Docstring filler line {i}." for i in range(docstring_body_lines))
    docstring = f'"""\n{doc_lines}\n"""\n'
    hashes = "\n".join(f"# comment line {i}" for i in range(hash_comment_lines))
    blanks = "\n" * blank_lines
    code = "\n".join(f"value_{i} = {i}" for i in range(counted_code_lines))
    return f"{docstring}{hashes}\n{blanks}{code}\n"


def python_lines_hash_and_blank_only(
    counted_code_lines: int, hash_comment_lines: int = 2, blank_lines: int = 2
) -> str:
    """.py content with COUNTED hash-comment and blank lines but NO
    discarded region -- the "docstring removed" variant of
    ``python_lines_with_all_categories`` used by the asymmetry descriptor.
    """
    hashes = "\n".join(f"# comment line {i}" for i in range(hash_comment_lines))
    blanks = "\n" * blank_lines
    code = "\n".join(f"value_{i} = {i}" for i in range(counted_code_lines))
    return f"{hashes}\n{blanks}{code}\n"


def mutate_rule_to_also_discard_hash_comments(dest: Path) -> None:
    """Simulate "the measurement rule in force changed" on the fixture's OWN
    copy of ``_file_size_ratchet.py`` only.

    Appends a redefinition of the module-level ``count_content_lines`` name.
    Existing in-module callers resolve that name as a global at CALL time
    (not at def time), so this changes their behaviour without requiring any
    assumption about python-coder's eventual published-statement design.
    """
    path = dest / "_file_size_ratchet.py"
    original = path.read_text(encoding="utf-8")
    override = (
        "\n\n"
        "# TEST-INJECTED MUTATION (GE-127d-2/test-writer): also discard '#' line\n"
        "# comments, simulating a changed rule for this disposable fixture copy only.\n"
        "_ORIGINAL_COUNT_CONTENT_LINES = count_content_lines\n"
        "\n\n"
        "def count_content_lines(content):  # noqa: F811 -- intentional test override\n"
        "    kept = [ln for ln in content.splitlines() if not ln.strip().startswith('#')]\n"
        "    return _ORIGINAL_COUNT_CONTENT_LINES(\"\\n\".join(kept))\n"
    )
    path.write_text(original + override, encoding="utf-8")


def write_precommit_config(root: Path) -> None:
    """Write a `.pre-commit-config.yaml` wiring the check-file-size hook ALONE."""
    body = (
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: check-file-size\n"
        "        name: Check File Size\n"
        "        entry: python scripts/commit_guardian/run_hook.py "
        "scripts/commit_guardian/check_file_size.py\n"
        "        language: system\n"
        "        pass_filenames: false\n"
        "        always_run: true\n"
    )
    (root / ".pre-commit-config.yaml").write_text(body, encoding="utf-8")


def install_precommit(root: Path) -> None:
    """Install the real pre-commit hook into *root*'s `.git/hooks/`."""
    result = run(["pre-commit", "install", "-f"], root)
    assert result.returncode == 0, f"pre-commit install failed: {result.stdout!r}{result.stderr!r}"


def commit(root: Path, message: str) -> subprocess.CompletedProcess:
    """Perform a REAL, ordinary `git commit` -- the production entry point."""
    return git(["commit", "-m", message], root, timeout=HOOK_COMMIT_TIMEOUT_SECONDS)


def commit_bypassing_hook(root: Path, message: str) -> subprocess.CompletedProcess:
    """Perform a real ``git commit`` for SETUP ONLY, with no pre-commit hook
    installed in *root* yet.

    Reaching the "grew" verdict requires an already-oversized file to exist
    at HEAD before the change under test is even staged -- and the FIRST
    commit that lands such a file cannot itself go through the real
    check-file-size hook, because an ordinary, correctly-behaving hook would
    refuse it (it is oversized). This helper must only ever be called
    BEFORE ``install_precommit()`` in a given fixture root -- at that point
    no ``.git/hooks/pre-commit`` script exists at all, so this is an
    ordinary, unintercepted ``git commit``, not a ``--no-verify`` bypass of
    an active hook. The REFUSAL under test is always produced by a
    subsequent, separate call to ``commit()`` made AFTER
    ``install_precommit()`` -- never by this function.
    """
    return git(["commit", "-m", message], root, timeout=HOOK_COMMIT_TIMEOUT_SECONDS)
